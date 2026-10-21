"""Own frame-file writer; no model, search, IPC serialization or foreign imports.
Closed chunks are verified before rotation proceeds or final close returns.
No claim of immutable storage or survival of a host crash.
"""
import hashlib
import json
import os
import pathlib
import stat

FRAME = 65536
SHARD = 8388608
AUDIT = 100663296
RECEIPT_MAX = 2048
RECEIPTS_MAX = 32768


class WriterError(RuntimeError):
    pass


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


class VerifiedShards:
    def __init__(self, folder, name, tick, budget=AUDIT):
        self.folder = pathlib.Path(folder)
        self.name = name
        self.tick = tick
        self.budget = budget
        self.n = self.size = self.total = self.receipt_bytes = 0
        self.f = None
        self.path = None
        self.h = None
        self.closed = self.failed = False
        self.cleanup_error = None

    def _open_write(self, path):
        # Unbuffered FileIO; short returns are handled explicitly below.
        return path.open('xb', buffering=0)

    def _sync(self, f):
        os.fsync(f.fileno())

    def _write_all(self, f, b, accepted=None):
        view = memoryview(b)
        while view:
            self.tick()
            n = f.write(view)
            if type(n) is not int or not 0 < n <= len(view):
                raise WriterError('WRITER_WRITE_RETURN')
            if accepted is not None:
                accepted(view[:n])
            view = view[n:]

    def _accept(self, b):
        self.h.update(b)
        self.size += len(b)
        self.total += len(b)

    def _abort(self):
        self.failed = True
        if self.f is not None:
            try:
                self.f.close()
            except BaseException as e:
                self.cleanup_error = repr(e)
            finally:
                self.f = None

    def _verify_path(self, path, want_stat, want_hash):
        self.tick()
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        fd = os.open(path, flags)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or identity(before) != want_stat:
                raise WriterError('WRITER_FILE_ID')
            h = hashlib.sha256()
            count = 0
            while count < want_stat[2]:
                self.tick()
                b = os.read(fd, min(FRAME, want_stat[2] - count))
                if not b:
                    raise WriterError('WRITER_READBACK_EOF')
                count += len(b)
                h.update(b)
            self.tick()
            if os.read(fd, 1):
                raise WriterError('WRITER_READBACK_EXTRA')
            after = os.fstat(fd)
            named = path.lstat()
            if identity(after) != want_stat or identity(named) != want_stat:
                raise WriterError('WRITER_FILE_CHANGED')
            if h.hexdigest() != want_hash:
                raise WriterError('WRITER_READBACK_HASH')
            return {'dev': after.st_dev, 'ino': after.st_ino,
                    'bytes': count, 'mtime_ns': after.st_mtime_ns,
                    'sha256': h.hexdigest()}
        finally:
            os.close(fd)

    def _write_receipt(self, record):
        b = (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
        if len(b) > RECEIPT_MAX or self.receipt_bytes + len(b) > RECEIPTS_MAX:
            raise WriterError('WRITER_RECEIPT_BOUND')
        p = self.path.with_suffix('.closed.json')
        with self._open_write(p) as f:
            self._write_all(f, b)
            f.flush()
            self._sync(f)
            st = identity(os.fstat(f.fileno()))
            if st[2] != len(b):
                raise WriterError('WRITER_RECEIPT_SIZE')
        self._verify_path(p, st, hashlib.sha256(b).hexdigest())
        self.receipt_bytes += len(b)

    def _seal_chunk(self):
        if self.f is None:
            return
        self.tick()
        self.f.flush()
        before = os.fstat(self.f.fileno())
        if (before.st_dev, before.st_ino) != self.open_identity or before.st_size != self.size:
            raise WriterError('WRITER_PRE_CLOSE_SIZE_ID')
        self._sync(self.f)
        synced = os.fstat(self.f.fileno())
        if identity(synced) != identity(before):
            raise WriterError('WRITER_SYNC_CHANGED')
        wanted = self.h.hexdigest()
        self.f.close()
        if not self.f.closed:
            raise WriterError('WRITER_NOT_CLOSED')
        self.f = None
        readback = self._verify_path(self.path, identity(synced), wanted)
        self._write_receipt({'schema': 'BE-WRITER-CLOSE-v1', 'chunk': self.n - 1,
                             'path': self.path.name, 'accepted_bytes': self.size,
                             'accepted_sha256': wanted, 'readback': readback,
                             'flush_returned': True, 'fsync_returned': True,
                             'writer_closed': True})

    def write(self, b):
        if self.closed or self.failed:
            raise WriterError('WRITER_NOT_WRITABLE')
        try:
            self.tick()
            if len(b) > FRAME or self.total + len(b) > self.budget:
                raise RuntimeError('INCOMPLETE_BUDGET_OUTPUT')
            if self.f is None or self.size + len(b) > SHARD:
                self._seal_chunk()  # Must succeed, including receipt, before open.
                self.path = self.folder / ('%s.%03d.bin' % (self.name, self.n))
                self.f = self._open_write(self.path)
                st = os.fstat(self.f.fileno())
                if not stat.S_ISREG(st.st_mode) or st.st_size != 0:
                    raise WriterError('WRITER_NEW_FILE')
                self.open_identity = (st.st_dev, st.st_ino)
                self.n += 1
                self.size = 0
                self.h = hashlib.sha256()
            self._write_all(self.f, b, self._accept)
            self.f.flush()
        except BaseException:
            self._abort()
            raise

    def close(self):
        if self.closed:
            return
        if self.failed:
            self._abort()
            return  # Cleanup only, never a successful completion acknowledgement.
        try:
            self._seal_chunk()
            self.closed = True
        except BaseException:
            self._abort()
            raise
