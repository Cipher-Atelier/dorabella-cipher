"""Single own fixture attempt. Does not import broker or any foreign module."""
import datetime, hashlib, json, os, pathlib, resource, shutil, sys, time
R = pathlib.Path(__file__).resolve().parent
A = R / 'smoke_attempt'
T = time.monotonic()
if A.exists():
    print('REFUSED_PREVIOUS_SMOKE_ATTEMPT', flush=True)
    raise SystemExit(3)
A.mkdir()
for name, value in [('RLIMIT_AS', 64*1024**2), ('RLIMIT_CPU', 10),
                    ('RLIMIT_FSIZE', 8388608), ('RLIMIT_NOFILE', 64), ('RLIMIT_CORE', 0)]:
    resource.setrlimit(getattr(resource, name), (value, value))

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(65536), b''): h.update(b)
    return h.hexdigest()

def emit(x): print(json.dumps(x, sort_keys=True), flush=True)

def save(p, x):
    b = (json.dumps(x, sort_keys=True, indent=2) + '\n').encode()
    with p.open('xb') as f:
        assert f.write(b) == len(b)
        f.flush(); os.fsync(f.fileno())

def tick():
    if time.monotonic() - T >= 30:
        raise RuntimeError('INCOMPLETE_BUDGET_DEADLINE')

def fds():
    d = {}
    for p in pathlib.Path('/proc/self/fd').iterdir():
        try: d[p.name] = os.readlink(p)
        except FileNotFoundError: pass
    return d

result = {'version': 'BE-W16-WRITER-REPAIR-v1', 'status': 'STOP', 'cases': [],
          'begin_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'pid': os.getpid(), 'no_children_created': True, 'old_STOP_unchanged': True}
baseline = fds()
code = 2
try:
    freeze = json.loads((R/'SMOKE_FREEZE.json').read_text())
    result['freeze_sha256'] = digest(R/'SMOKE_FREEZE.json')
    for r in freeze['files']:
        assert (R/r['path']).stat().st_size == r['bytes'] and digest(R/r['path']) == r['sha256'], 'FROZEN_IDENTITY'
    assert list(sys.version_info[:3]) == freeze['python_version'], 'PYTHON_VERSION'
    assert digest(pathlib.Path(sys.executable)) == freeze['python_sha256'], 'PYTHON_IDENTITY'
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'PYTHON_FLAGS'
    current = int(pathlib.Path('/sys/fs/cgroup/memory.current').read_text())
    maximum = pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip()
    free = shutil.disk_usage(R).free
    result['resource_gate'] = {'memory_current': current, 'memory_max': maximum, 'disk_free': free}
    assert maximum == '8589934592' and current < 5468942336 and free >= 64*1024**2, 'RESOURCE_GATE'
    save(A/'START.json', result)
    emit({'SMOKE_START': result})
    # The only non-stdlib import is our newly written, hash-pinned writer.
    sys.path.insert(0, str(R/'runtime'))
    from verified_shards import VerifiedShards, WriterError
    block = bytes(range(256))*256
    small = b'0123456789abcdefghijklmnopqrstuv'
    assert len(small) == 32

    class Proxy:
        def __init__(self, f, mode, trace): self.f, self.mode, self.trace = f, mode, trace
        def __getattr__(self, n): return getattr(self.f, n)
        def write(self, b):
            if self.mode == 'none': return None
            if self.mode == 'zero': return 0
            if self.mode == 'negative': return -1
            if self.mode == 'excess': return len(b)+1
            return self.f.write(b[:7] if self.mode == 'short' else b)
        def flush(self):
            self.f.flush()
            if self.mode == 'flush': raise OSError('INJECT_FLUSH')
            self.trace.append('flush_returned')
        def close(self):
            self.f.close(); self.trace.append('close_returned')
            if self.mode == 'close': raise OSError('INJECT_CLOSE')

    class ObservedWriter(VerifiedShards):
        def __init__(self, folder, mode):
            self.mode, self.trace, self.injected = mode, [], False
            def own_tick():
                tick()
                if mode == 'deadline': raise RuntimeError('INCOMPLETE_BUDGET_DEADLINE')
            super().__init__(folder, 'frames', own_tick)
        def _open_write(self, path):
            self.trace.append('open:'+path.name)
            f = super()._open_write(path)
            return Proxy(f, self.mode, self.trace) if path.suffix == '.bin' else f
        def _sync(self, f):
            if self.mode == 'fsync': raise OSError('INJECT_FSYNC')
            super()._sync(f); self.trace.append('fsync_returned')
        def _verify_path(self, path, wanted, h):
            if path.suffix == '.bin' and not self.injected:
                self.injected = True
                if self.mode == 'truncate':
                    with path.open('r+b') as f: f.truncate(wanted[2]-1)
                elif self.mode == 'hash':
                    with path.open('r+b') as f:
                        b = f.read(1); f.seek(0); f.write(bytes([b[0]^1]))
                    os.utime(path, ns=(wanted[3], wanted[3]))
                elif self.mode == 'replace':
                    b = path.read_bytes(); path.rename(path.with_suffix('.original'))
                    path.write_bytes(b)
                elif self.mode == 'append':
                    with path.open('ab') as f: f.write(b'!')
            value = super()._verify_path(path, wanted, h)
            self.trace.append('verified:'+path.name)
            return value
        def _write_receipt(self, rec):
            if self.mode == 'receipt': raise OSError('INJECT_RECEIPT')
            super()._write_receipt(rec)
            self.trace.append('receipt_committed:'+rec['path'])

    def exact_bytes(folder, expected):
        # Independent sequential byte comparison, not just writer's hash.
        i = offset = total = 0; h = hashlib.sha256()
        for p in sorted(folder.glob('frames.*.bin')):
            with p.open('rb') as f:
                for b in iter(lambda: f.read(65536), b''):
                    tick(); h.update(b); total += len(b); pos = 0
                    while pos < len(b):
                        assert i < len(expected), 'EXTRA_BYTES'
                        n = min(len(expected[i])-offset, len(b)-pos)
                        assert b[pos:pos+n] == expected[i][offset:offset+n], 'BYTE_MISMATCH'
                        offset += n; pos += n
                        if offset == len(expected[i]): i += 1; offset = 0
        assert i == len(expected) and offset == 0, 'MISSING_BYTES'
        return {'bytes': total, 'sha256': h.hexdigest()}

    fixtures = [
        ('POS_ROTATION','normal',None), ('POS_SHORT_RETURN','short',None),
        ('NEG_RETURN_NONE','none','WRITER_WRITE_RETURN'),
        ('NEG_RETURN_ZERO','zero','WRITER_WRITE_RETURN'),
        ('NEG_RETURN_NEGATIVE','negative','WRITER_WRITE_RETURN'),
        ('NEG_RETURN_EXCESS','excess','WRITER_WRITE_RETURN'),
        ('NEG_FLUSH','flush','INJECT_FLUSH'), ('NEG_FSYNC','fsync','INJECT_FSYNC'),
        ('NEG_CLOSE','close','INJECT_CLOSE'),
        ('NEG_ROTATION_TRUNCATE','truncate','WRITER_FILE_ID'),
        ('NEG_HASH','hash','WRITER_READBACK_HASH'),
        ('NEG_REPLACE','replace','WRITER_FILE_ID'),
        ('NEG_APPEND','append','WRITER_FILE_ID'),
        ('NEG_RECEIPT','receipt','INJECT_RECEIPT'),
        ('NEG_DEADLINE','deadline','INCOMPLETE_BUDGET_DEADLINE')]
    assert [x[0] for x in fixtures] == freeze['fixtures'], 'FIXTURE_ORDER'
    for name, mode, expected_error in fixtures:
        tick(); folder = A/name; folder.mkdir(); w = ObservedWriter(folder, mode)
        before = fds(); ack = False; error = None; checks = {}
        try:
            if name == 'POS_ROTATION':
                expected = [block]*127+[block[:65535], b'Q', b'R', block]
                for b in expected: w.write(b)
                w.close(); ack = True
                assert w.closed and not w.failed and w.n == 2
                assert [p.stat().st_size for p in sorted(folder.glob('frames.*.bin'))] == [8388608,65537]
                assert w.trace.index('receipt_committed:frames.000.bin') < w.trace.index('open:frames.001.bin')
                assert w.trace[-1] == 'receipt_committed:frames.001.bin'
                checks = exact_bytes(folder, expected)
                assert checks == freeze['positive_rotation_bytes'], 'FROZEN_EXPECTED_BYTES'
            elif name == 'NEG_ROTATION_TRUNCATE':
                for _ in range(128): w.write(block)
                w.write(b'R'); ack = True
            else:
                w.write(small); w.close(); ack = True
                if expected_error is None:
                    checks = exact_bytes(folder, [small])
                    assert checks == freeze['positive_short_bytes']
        except (WriterError, OSError, RuntimeError) as e:
            error = str(e)
        finally:
            w.close()
        assert error == expected_error, (name, 'ERROR_CLASS', error, expected_error)
        if expected_error is not None:
            assert not ack and w.failed, (name,'BAD_ACK')
            try: w.write(b'X')
            except WriterError as e: assert str(e) == 'WRITER_NOT_WRITABLE'
            else: raise AssertionError('POISON_NOT_ENFORCED')
            assert not (folder/'frames.001.bin').exists(), 'NEXT_SHARD_AFTER_FAILURE'
        else: assert ack and w.closed and not w.failed
        assert fds() == before, (name,'FD_LEAK')
        row = {'name':name,'expected_error':expected_error,'actual_error':error,
               'ack':ack,'failed':w.failed,'closed':w.closed,'chunks_opened':w.n,
               'accepted_bytes':w.total,'receipt_bytes':w.receipt_bytes,
               'cleanup_error':w.cleanup_error,'fd_cleanup':True,'checks':checks,'trace':w.trace}
        result['cases'].append(row); save(folder/'case_result.json',row)
        emit({'FIXTURE_COMPLETE':{k:v for k,v in row.items() if k!='trace'}})
    assert len(result['cases']) == 15
    assert fds() == baseline, 'FINAL_FD_LEAK'
    assert sum(p.stat().st_size for p in A.rglob('*') if p.is_file()) < 20*1024**2, 'OUTPUT_TOTAL'
    tick();result['status']='PASS_SMOKE_ONLY';code=0
except BaseException as e:
    result['error'] = repr(e)
finally:
    result.update(end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  elapsed=time.monotonic()-T, exit_code=code,
                  maxrss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  fd_before=baseline,fd_after=fds(),cleanup=(fds()==baseline))
    if result['elapsed'] >= 30 or not result['cleanup']:
        result['status']='STOP';result['exit_code']=code=2
    save(A/'result.json',result)
    rows=[{'path':str(p.relative_to(A)),'bytes':p.stat().st_size,'sha256':digest(p)}
          for p in sorted(A.rglob('*')) if p.is_file()]
    save(A/'closed_files.json',{'files':rows,'status':result['status']})
    emit({'SMOKE_TERMINAL':{k:v for k,v in result.items() if k!='cases'},
          'result_sha256':digest(A/'result.json'),
          'closed_files_sha256':digest(A/'closed_files.json')})
raise SystemExit(code)
