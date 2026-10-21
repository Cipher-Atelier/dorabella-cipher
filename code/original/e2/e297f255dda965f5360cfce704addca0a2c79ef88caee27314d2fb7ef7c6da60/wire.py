"""Own bounded byte protocol. No LM arithmetic, subprocesses or author imports."""
import json,re
CAP=65536
def encode(x):
 raw=(json.dumps(x,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
 if len(raw)>CAP:raise ValueError('FRAME_BOUND')
 return raw
def decode(raw):
 if type(raw) is not bytes or not raw.endswith(b'\n') or b'\n' in raw[:-1] or len(raw)>CAP:raise ValueError('FRAME_BYTES')
 return json.loads(raw)
def request(raw,seq,allowed):
 x=decode(raw)
 if type(x) is not list or len(x)!=3 or type(x[0]) is not int or x[0]!=seq:raise ValueError('REQUEST_ID')
 _,dataset,items=x
 if dataset=='close' and items==[]:return dataset,[]
 if type(dataset) is not str or dataset not in allowed or type(items) is not list or len(items)>776:raise ValueError('REQUEST_DOMAIN')
 result=[]
 for item in items:
  if type(item) is not list or len(item)!=2:raise ValueError('ITEM')
  t,key=item
  if type(t) is not int or not 1<=t<=6 or type(key) is not list or len(key)!=(t-1)%3+1:raise ValueError('ARITY')
  for s in key:
   if type(s) is not str or not 2<=len(s)<=256 or len(s)%2 or not re.fullmatch('[0-9a-f]+',s):raise ValueError('KEY_HEX')
  k=tuple(bytes.fromhex(s) for s in key)
  if any(any(c<33 or c>126 for c in word) for word in k):raise ValueError('KEY_ASCII')
  result.append((t,k))
 return dataset,result
def packet(seq,offset,values,done):
 if type(seq) is not int or not 1<=seq<=2049 or type(offset) is not int or not 0<=offset<=776 or type(done) is not bool or len(values)>128:raise ValueError('PACKET_HEADER')
 for row in values:
  if type(row) is not list or len(row)!=3 or type(row[0]) is not bool:raise ValueError('VALUE_SHAPE')
  yes,v,n=row
  if yes:
   if type(v) is not str or not 2<=len(v)<=192 or len(v)%2 or not re.fullmatch('[0-9a-f]+',v):raise ValueError('VALUE_HEX')
   if type(n) is not int or not 1<=n<=10000000:raise ValueError('ROW')
  elif v is not None or n is not None:raise ValueError('MISSING')
 return encode([seq,offset,values,done])
