"""Own bounded storage primitives, no search or language logic."""
import pathlib,json,hashlib,struct
def raw(x):return (json.dumps(x,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
class Shards:
 def __init__(self,folder,name,total):
  self.folder=pathlib.Path(folder);self.name=name;self.total=total;self.written=0;self.n=0;self.f=None;self.size=0
 def write(self,b):
  if len(b)>65536 or self.written+len(b)>self.total:raise RuntimeError('INCOMPLETE_BUDGET_AUDIT:'+self.name)
  if self.f is None or self.size+len(b)>8388608:
   if self.f:self.f.flush();self.f.close()
   self.f=(self.folder/('%s.%03d.jsonl'%(self.name,self.n))).open('xb');self.n+=1;self.size=0
  self.f.write(b);self.f.flush();self.size+=len(b);self.written+=len(b)
 def close(self):
  if self.f:self.f.flush();self.f.close();self.f=None
class Chain:
 def __init__(self):self.h=hashlib.sha256();self.frames=0;self.bytes=0
 def add(self,ch,d,b):self.h.update(struct.pack('>BBI',1 if ch=='pat' else 2,d,len(b))+b);self.frames+=1;self.bytes+=len(b)
 def result(self):return dict(sha256=self.h.hexdigest(),frames=self.frames,bytes=self.bytes)
def records(folder,name):
 for p in sorted(pathlib.Path(folder).glob(name+'.*.jsonl')):
  with p.open('rb') as f:
   for b in f:
    if not b.endswith(b'\n'):raise RuntimeError('INCOMPLETE_RECORD:'+str(p))
    yield json.loads(b)
