"""Own bounded file/IPC primitives; prepared, not executed."""
import hashlib,json,os,pathlib,struct,time
FRAME=65536;SHARD=8388608;AUDIT=100663296
def raw(x):return (json.dumps(x,separators=(',',':'),sort_keys=True,ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def put(p,x):
 with pathlib.Path(p).open('xb') as f:f.write(raw(x));f.flush();os.fsync(f.fileno())
class Shards:
 def __init__(self,folder,name,budget=AUDIT):self.folder=pathlib.Path(folder);self.name=name;self.budget=budget;self.n=0;self.f=None;self.size=0;self.total=0
 def write(self,b):
  if len(b)>FRAME or self.total+len(b)>self.budget:raise RuntimeError('INCOMPLETE_BUDGET_OUTPUT')
  if self.f is None or self.size+len(b)>SHARD:
   if self.f:self.f.flush();self.f.close()
   self.f=(self.folder/('%s.%03d.bin'%(self.name,self.n))).open('xb');self.n+=1;self.size=0
  self.f.write(b);self.f.flush();self.size+=len(b);self.total+=len(b)
 def close(self):
  if self.f:self.f.flush();self.f.close();self.f=None
class Chain:
 def __init__(self):self.h=hashlib.sha256();self.frames=0;self.bytes=0
 def add(self,d,b):
  packet=struct.pack('>BI',d,len(b))+b;self.h.update(packet);self.frames+=1;self.bytes+=len(b);return packet
 def result(self):return dict(sha256=self.h.hexdigest(),frames=self.frames,bytes=self.bytes)
def memory():
 return {n:(pathlib.Path('/sys/fs/cgroup')/n).read_text().strip() for n in ['memory.max','memory.current','memory.events','memory.stat']}
def admit():
 m=memory();return m,m['memory.max']=='8589934592' and int(m['memory.current'])<5468942336
