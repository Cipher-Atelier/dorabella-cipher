"""Own exact prefix and membership storage. No scoring/arithmetic/solver."""
import pathlib,re,sqlite3
TABS=re.compile(rb'\t+');WS=b' \t\n\r\v\f'
class Store:
 def __init__(self,index,source,tick):
  self.tick=tick;self.db=sqlite3.connect(pathlib.Path(index).resolve().as_uri()+'?mode=ro',uri=True,timeout=0)
  self.db.execute('PRAGMA query_only=ON');self.db.execute('PRAGMA cache_size=-4096');self.db.execute('PRAGMA mmap_size=0');self.db.set_progress_handler(lambda:(self.tick() or 0),10000)
  self.f=open(source,'rb');self.size=pathlib.Path(source).stat().st_size;self.read_bytes=0;self.prefix_calls=0;self.word_calls=0
 def prefix(self,key):
  self.tick();self.prefix_calls+=1
  if self.prefix_calls>3870:raise RuntimeError('INCOMPLETE_BUDGET_PREFIX_REQUESTS')
  if not isinstance(key,str) or not 1<=len(key)<=46 or not re.fullmatch('[a-zA-Z0-9+!\-]+',key):raise ValueError('PREFIX_DOMAIN')
  values=[];refs=[];previous=0
  for seq,order,pattern,offset,n,count,longest in self.db.execute('SELECT seq,original_order,pattern,offset,raw_bytes,count,longest FROM segments WHERE pattern=? ORDER BY seq',(key.encode('ascii'),)):
   self.tick()
   if not previous<seq<=7548932 or not 0<n<=118052 or not 0<=offset<offset+n<=self.size:raise ValueError('SEGMENT_BOUND')
   if self.read_bytes+n>67108864:raise RuntimeError('INCOMPLETE_BUDGET_PREFIX_SOURCE_BYTES')
   previous=seq;self.f.seek(offset);b=self.f.read(n);self.read_bytes+=len(b)
   if len(b)!=n:raise ValueError('SEGMENT_TRUNCATED')
   fields=TABS.split(b.rstrip(WS).replace(b' ',b''));v=fields[2:]
   if not v or (int(fields[0]),fields[1],len(v),max(map(len,v)))!=(order,pattern,count,longest):raise ValueError('SEGMENT_CONTENT')
   if any(not x or len(x)>46 or any(c<33 or c>126 for c in x) for x in v):raise ValueError('CANDIDATE_DOMAIN')
   take=min(50-len(values),len(v));values.extend(v[:take]);refs.append([seq,offset,n,take])
   if len(values)==50:break
  L=len(values);picks=[values[((2*r+1)*L)//16].decode('ascii') for r in range(8)] if L else []
  return {'length':L,'picks':picks,'segments':refs}
 def words(self,keys):
  if not isinstance(keys,list) or len(keys)>128:raise ValueError('WORDS_BATCH')
  if self.word_calls+len(keys)>493812:raise RuntimeError('INCOMPLETE_BUDGET_PHYSICAL_WORDS')
  out=[]
  for hx in keys:
   self.tick();b=bytes.fromhex(hx)
   if len(b)>87 or b.hex()!=hx:raise ValueError('WORD_DOMAIN')
   self.word_calls+=1;out.append(bool(self.db.execute('SELECT 1 FROM words WHERE word=?',(b,)).fetchone()))
  return out
 def close(self):self.f.close();self.db.close()
