"""Prepared diagnostic I/O only. No execution during preparation; no probability logic."""
from pathlib import Path
import os,stat,json,time,hashlib

CAP=8388608
def need(value,message):
    if not value:raise RuntimeError('EVIDENCE_'+message)
def digest(data):return hashlib.sha256(data).hexdigest()
def stamp(st):
    return {k:getattr(st,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}
def identity(a,b):return (a['st_dev'],a['st_ino'])==(b['st_dev'],b['st_ino'])
def path_stat(path):
    s=stamp(os.lstat(path));need(stat.S_ISREG(s['st_mode']) and s['st_nlink']==1,'REGULAR_SINGLE_LINK');return s
def raw_open(path):
    return os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
def atomic_json(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.tmp')
    with tmp.open('x') as f:
        json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def read_snapshot(path,tick=lambda:None):
    """Hash exact bytes of a stable open descriptor; no atime comparison."""
    path=Path(path);fd=raw_open(path)
    try:
        before=stamp(os.fstat(fd));need(before==path_stat(path),'READ_OPEN_IDENTITY')
        need(0<=before['st_size']<=CAP,'READ_SIZE');h=hashlib.sha256();n=0;lines=0;last=b''
        while True:
            tick();b=os.read(fd,65536)
            if not b:break
            h.update(b);n+=len(b);lines+=b.count(b'\n');last=b[-1:];need(n<=CAP,'READ_CAP')
        after=stamp(os.fstat(fd));on_path=path_stat(path)
        need(before==after==on_path,'READ_CHANGED:'+json.dumps({'before':before,'after':after,'path':on_path},separators=(',',':')))
        need(n==after['st_size'],'READ_EOF_SIZE')
        return {'path':str(path.resolve()),'before':before,'after':after,'bytes':n,'sha256':h.hexdigest(),
                'newlines':lines,'last_newline':last==b'\n','EOF':True,'monotonic':time.monotonic()}
    finally:os.close(fd)

class Journal:
    """Preserve BufferedWriter write/flush order; observe through a separate read fd."""
    def __init__(self,path,tick):
        self.path=Path(path);self.tick=tick;self.start=time.monotonic();self.writer=self.path.open('xb')
        self.reader=raw_open(self.path);self.initial=stamp(os.fstat(self.writer.fileno()))
        need(self.initial==stamp(os.fstat(self.reader))==path_stat(self.path),'WRITER_OPEN_IDENTITY')
        self.audit_path=self.path.with_name(self.path.stem+'_writer_events.jsonl')
        self.audit=self.audit_path.open('xb',buffering=0);self.audit_hash=hashlib.sha256();self.audit_bytes=0
        self.intended=hashlib.sha256();self.actual=hashlib.sha256();self.n=0;self.records=0
        self.pending=None;self.closed=False
        self.emit({'event':'OPEN','path':str(self.path.resolve()),'writer_fd':self.writer.fileno(),
                   'reader_fd':self.reader,'identity':self.initial})
    def emit(self,value):
        value=dict(value,monotonic=time.monotonic());raw=(json.dumps(value,separators=(',',':'))+'\n').encode()
        caps={'INTENT':512,'AFTER_FLUSH':1024,'WRITE_FLUSH_READ':1024,'OPEN':2048,'CLOSE':2048}
        need(len(raw)<=caps[value['event']],'AUDIT_RECORD_BOUND')
        need(self.audit_bytes+len(raw)<=CAP,'WRITER_AUDIT_CAP');view=memoryview(raw)
        while view:
            self.tick();n=self.audit.write(view);need(n is not None and n>0,'AUDIT_SHORT_WRITE');view=view[n:]
        self.audit_hash.update(raw);self.audit_bytes+=len(raw)
    def write(self,data):
        self.tick();need(not self.closed and self.pending is None,'WRITE_STATE')
        need(type(data) is bytes and data.endswith(b'\n') and b'\n' not in data[:-1] and len(data)<=66000,'RECORD_DOMAIN')
        need(self.n+len(data)<=CAP,'JOURNAL_CAP')
        self.pending=data;self.intended.update(data)
        self.emit({'event':'INTENT','record':self.records+1,'start':self.n,'bytes':len(data),'sha256':digest(data)})
        count=self.writer.write(data);self.write_count=count
        need(count==len(data),'WRITE_RETURN_LENGTH');return count
    def flush(self):
        self.tick();self.writer.flush()
        if self.pending is None:return
        raw=self.pending;before=self.n;after=before+len(raw)
        w=stamp(os.fstat(self.writer.fileno()));r=stamp(os.fstat(self.reader));p=path_stat(self.path)
        self.emit({'event':'AFTER_FLUSH','record':self.records+1,'write_return':self.write_count,
                   'writer':w,'reader':r,'path':p,'expected_end':after})
        need(identity(w,self.initial) and w==r==p and w['st_size']==after,'FLUSH_IDENTITY_SIZE')
        need(self.writer.tell()==after and os.lseek(self.writer.fileno(),0,os.SEEK_CUR)==after,'WRITER_OFFSET')
        pieces=[];got=0
        while got<len(raw):
            self.tick();b=os.pread(self.reader,len(raw)-got,before+got);need(bool(b),'PREAD_SHORT')
            pieces.append(b);got+=len(b)
        physical=b''.join(pieces);need(physical==raw,'WRITTEN_BYTES_DIFFER')
        self.actual.update(physical);self.n=after;self.records+=1
        e=json.loads(raw);kind='request' if 'request' in e else 'response'
        self.emit({'event':'WRITE_FLUSH_READ','record':self.records,'start':before,'end':after,'write_return':self.write_count,
                   'channel':e['channel'],'kind':kind,'seq':e[kind][0],'intended_sha256':digest(raw),
                   'physical_sha256':digest(physical),'stat':w})
        self.pending=None
    def close(self):
        if self.closed:return
        try:
            self.flush();before=stamp(os.fstat(self.writer.fileno()))
            need(before==path_stat(self.path) and before['st_size']==self.n,'BEFORE_CLOSE')
            self.writer.close();closed_at=time.monotonic()
            # No journal fsync is added: distinguish visibility/close from crash durability.
            h=hashlib.sha256();n=0
            while n<self.n:
                self.tick();b=os.pread(self.reader,min(65536,self.n-n),n);need(bool(b),'FINAL_PREAD_SHORT');h.update(b);n+=len(b)
            need(not os.pread(self.reader,1,n),'FINAL_EXTRA_BYTES')
            after=stamp(os.fstat(self.reader));need(before==after==path_stat(self.path),'AFTER_CLOSE_IDENTITY')
            need(h.hexdigest()==self.actual.hexdigest()==self.intended.hexdigest(),'WRITER_HASH_CHAIN')
            self.emit({'event':'CLOSE','records':self.records,'bytes':n,'sha256':h.hexdigest(),'identity':after,'closed_at':closed_at})
            self.audit.close();os.close(self.reader);self.closed=True
            receipt={'status':'WRITER_CLOSED_CONSISTENT','path':str(self.path.resolve()),'initial':self.initial,'final':after,
                     'records':self.records,'bytes':n,'intended_sha256':self.intended.hexdigest(),
                     'physical_incremental_sha256':self.actual.hexdigest(),'closed_fd_sha256':h.hexdigest(),
                     'write_flush_before_response':True,'close_completed_monotonic':closed_at,
                     'audit_path':str(self.audit_path.resolve()),'audit_sha256':self.audit_hash.hexdigest(),'audit_bytes':self.audit_bytes,
                     'journal_fsync_added':False,'completion_monotonic':time.monotonic()}
            atomic_json(self.path.with_name(self.path.stem+'_writer_completion.json'),receipt)
        except BaseException:
            # No successful completion receipt on evidence failure. Original exception is re-raised.
            for handle in (self.writer,self.audit):
                try:handle.close()
                except Exception:pass
            if not self.closed:
                try:os.close(self.reader)
                except OSError:pass
            self.closed=True;raise

class ReadWitness:
    """I/O substitution only; original verifier's real()/ipc()/need() stay unchanged."""
    def __init__(self,tick):self.tick=tick;self.receipts=[];self.handles=[]
    def iter_rows(self,path):
        path=Path(path);fd=raw_open(path);h=hashlib.sha256();n=0;rows=0;eof=False;error=None
        before=stamp(os.fstat(fd));receipt={'path':str(path.resolve()),'before':before,'EOF':False,'error':None}
        self.receipts.append(receipt)
        try:
            need(before==path_stat(path) and before['st_size']<=CAP,'VERIFIER_OPEN')
            with os.fdopen(fd,'rb') as handle:
                fd=None;self.handles.append(handle)
                for raw in handle:
                    self.tick();need(len(raw)<=CAP,'ROW_BYTES');h.update(raw);n+=len(raw);rows+=1
                    need(n<=CAP,'VERIFIER_BYTES');receipt.update(bytes=n,sha256=h.hexdigest(),records=rows)
                    yield json.loads(raw)
                eof=True;after=stamp(os.fstat(handle.fileno()))
                receipt['after']=after;receipt['path_after']=path_stat(path)
                need(before==after==receipt['path_after'] and n==after['st_size'],'VERIFIER_CHANGED_OR_SHORT')
        except BaseException as exc:error=repr(exc);raise
        finally:
            if fd is not None:os.close(fd)
            receipt.update(bytes=n,sha256=h.hexdigest(),records=rows,EOF=eof,error=error,monotonic=time.monotonic())
    def finish(self):
        for handle in self.handles:
            if not handle.closed:handle.close()
        for receipt in self.receipts:
            if not receipt['EOF'] and receipt['error'] is None:receipt['error']='INCOMPLETE_ITERATION'
    def load(self,path):
        path=Path(path);fd=raw_open(path);receipt={'path':str(path.resolve()),'EOF':False,'error':None}
        self.receipts.append(receipt)
        try:
            before=stamp(os.fstat(fd));receipt['before']=before
            need(before==path_stat(path) and before['st_size']<=CAP,'JSON_OPEN')
            chunks=[];n=0
            while True:
                self.tick();b=os.read(fd,65536)
                if not b:break
                n+=len(b);need(n<=CAP,'JSON_CAP');chunks.append(b)
            raw=b''.join(chunks);after=stamp(os.fstat(fd));on_path=path_stat(path)
            receipt.update(after=after,path_after=on_path,bytes=n,sha256=digest(raw),EOF=True,monotonic=time.monotonic())
            need(before==after==on_path and n==after['st_size'],'JSON_CHANGED')
            # Frozen JSON inputs/outputs are UTF-8; no numeric transformation or normalization.
            return json.loads(raw.decode('utf-8'))
        except BaseException as exc:receipt['error']=repr(exc);raise
        finally:os.close(fd)
