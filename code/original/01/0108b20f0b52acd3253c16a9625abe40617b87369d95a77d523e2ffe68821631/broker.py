"""Own bounded broker, NEW EXECUTABLE, PREPARED ONLY. Never computes LM scores."""
import os,sys,pathlib,json,time,select,resource
B=pathlib.Path(__file__).resolve().parent;R=B.parent;sys.path[:0]=[str(B),str(B/'reused')]
from common import raw,Shards,Chain,put
from store import Store
from disk_contract import DiskLM
def main():
 A=pathlib.Path(os.environ['BE_ATTEMPT']);end=float(os.environ['BE_DEADLINE']);dataset=os.environ['BE_DATASET'];rd,wr=map(int,sys.argv[1:]);t=time.monotonic()
 def tick():
  if time.monotonic()>=end:raise RuntimeError('INCOMPLETE_BUDGET_DEADLINE')
 def send(seq,off,part,done):
  tick();b=raw([seq,off,part,done])
  if len(b)>65536:raise ValueError('RESPONSE_FRAME')
  packet=chain.add(2,b)
  # Split the binary container, not the framed protocol.
  for j in range(0,len(packet),65536):log.write(packet[j:j+65536])
  view=memoryview(b)
  while view:
   tick();n=os.write(wr,view)
   if n<=0:raise ValueError('IPC_WRITE')
   view=view[n:]
 ds=json.loads((R/'datasets_all.json').read_text())[dataset]
 store=Store(ds['index'],ds['source'],tick);lm=DiskLM(ds['lm'],tick,4096);log=Shards(A,'frames');chain=Chain();seq=0;counts={'prefix':0,'words':0,'lm':0,'lm_lookups':0,'close':0};buffer=b'';status='STOP';error=None
 try:
  while True:
   tick()
   if b'\n' not in buffer:
    if len(buffer)>=65536:raise ValueError('REQUEST_FRAME')
    if not select.select([rd],[],[],.05)[0]:continue
    b=os.read(rd,min(4096,65536-len(buffer)))
    if not b:raise ValueError('IPC_EOF')
    buffer+=b;continue
   b,buffer=buffer.split(b'\n',1);b+=b'\n';q=json.loads(b);seq+=1
   if type(q) is not list or len(q)!=3 or q[0]!=seq:raise ValueError('REQUEST_SEQUENCE')
   packet=chain.add(1,b)
   for j in range(0,len(packet),65536):log.write(packet[j:j+65536])
   _,op,arg=q
   if op not in counts or op=='lm_lookups':raise ValueError('OP')
   counts[op]+=1
   if op=='prefix':
    v=store.prefix(arg);send(seq,0,[v],True)
   elif op=='words':
    if counts[op]>3870:raise RuntimeError('INCOMPLETE_BUDGET_WORD_BATCHES')
    send(seq,0,store.words(arg),True)
   elif op=='lm':
    if counts['lm']>258 or not isinstance(arg,list) or len(arg)>776 or counts['lm_lookups']+len(arg)>100104:raise RuntimeError('INCOMPLETE_BUDGET_LM')
    for off in (range(0,len(arg),128) if arg else [0]):
     values=[]
     for table,key in arg[off:off+128]:
      tick();v=lm.lookup(table,tuple(bytes.fromhex(k) for k in key));values.append([v['found'],v['value_hex'],v['last_row_1based']]);counts['lm_lookups']+=1
     send(seq,off,values,off+len(values)==len(arg))
   else:
    if arg is not None or buffer:raise ValueError('CLOSE_DOMAIN')
    send(seq,0,['closed'],True);status='BROKER_COMPLETE';break
 except BaseException as exc:error=repr(exc);raise
 finally:
  log.close();store.close();lm.close();os.close(rd);os.close(wr)
  result={'status':status,'error':error,'chain':chain.result(),'counts':counts,'prefix_source_bytes':store.read_bytes,'physical_words':store.word_calls,'lm_stats':lm.stats,'elapsed':time.monotonic()-t,'CPU':time.process_time(),'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'closed':True}
  put(A/'broker_terminal.json',result);print('BROKER_COMPUTED '+raw(result).decode().strip(),flush=True)
if __name__=='__main__':main()
