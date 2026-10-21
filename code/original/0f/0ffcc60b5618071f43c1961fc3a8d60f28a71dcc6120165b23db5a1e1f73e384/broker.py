"""NEW recovered broker, unexecuted. Real complete FETCH, no scoring."""
import os,sys,json,time,select,pathlib,resource
sys.dont_write_bytecode=True
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B));R=B.parent
from adapter import CompactPatList
from disk_contract import DiskLM
from transport_contract import Channels,pat_request,encode_pat
from wire import request,packet
from audit_io import raw,Shards,Chain
def main():
 A=pathlib.Path(os.environ['TS_ATTEMPT']);deadline=float(os.environ['TS_DEADLINE'])
 fds=list(map(int,sys.argv[1:]));assert len(fds)==4 and len(set(fds))==4
 routes={'lm':(fds[0],fds[1]),'pat':(fds[2],fds[3])}
 def tick():
  if time.monotonic()>=deadline:raise RuntimeError('INCOMPLETE_BUDGET_WORK_DEADLINE')
 ds=json.loads((R/'datasets.json').read_text())['real'];inputs=json.loads((R/'model_inputs.json').read_text())
 patpath=next(x['path'] for x in inputs if x['path'].endswith('.patlst'));idx=next(x['path'] for x in inputs if x['path'].endswith('.sqlite'))
 specs={x['pattern']:x for x in json.loads((R/'catalogue/catalogue.json').read_text())}
 p=None;lm=None;status='STOP';error=None;ordinal=0;lookups=0;words=0;mux=Channels();chain=Chain();t=time.monotonic()
 logs={'pat':Shards(A,'pat_refs',24*1024**2),'lm':Shards(A,'lm_raw',16*1024**2)}
 stats={c:dict(requests=0,response_frames=0,response_bytes=0,max_frame=0) for c in routes}
 def send(ch,b):
  tick();chain.add(ch,2,b)
  if ch=='lm':logs[ch].write(raw({'ordinal':ordinal,'direction':2,'raw':b.decode('ascii')}))
  v=memoryview(b)
  while v:
   tick();n=os.write(routes[ch][1],v)
   if n<=0:raise RuntimeError('IPC_WRITE')
   v=v[n:]
  q=stats[ch];q['response_frames']+=1;q['response_bytes']+=len(b);q['max_frame']=max(q['max_frame'],len(b))
 try:
  lm=DiskLM(ds,tick,4096);p=CompactPatList(idx,patpath,tick)
  while not all(mux.closed.values()):
   tick();active={routes[c][0]:c for c in routes if not mux.closed[c]}
   rr,_,_=select.select(list(active),[],[],.05)
   for fd in rr:
    ch=active[fd];ready=mux.feed(ch,os.read(fd,min(4096,65536-len(mux.buffers[ch]))))
    if ready is None:continue
    b,seq=ready;ordinal+=1;chain.add(ch,1,b);stats[ch]['requests']=seq
    if ch=='lm':
     logs[ch].write(raw({'ordinal':ordinal,'direction':1,'raw':b.decode('ascii')}));name,items=request(b,seq,['real'])
     if lookups+len(items)>794624:raise RuntimeError('INCOMPLETE_BUDGET_LM_LOOKUPS')
     for off in (range(0,len(items),128) if items else [0]):
      values=[]
      for table,key in items[off:off+128]:
       v=lm.lookup(table,key);values.append([v['found'],v['value_hex'],v['last_row_1based']]);lookups+=1
      send(ch,packet(seq,off,values,off+len(values)==len(items)))
     if name=='close':mux.close(ch)
    else:
     op,arg=pat_request(b,seq);rec={'ordinal':ordinal,'request':b.decode('ascii')}
     if op=='meta':logs[ch].write(raw(rec));send(ch,encode_pat(seq,['value',{'maxlen':p.maxlen}]))
     elif op=='word':
      if words>=200000:raise RuntimeError('INCOMPLETE_BUDGET_MEMBERSHIP')
      words+=1;rec['found']=bool(p.is_word(arg));logs[ch].write(raw(rec));send(ch,encode_pat(seq,['value',int(rec['found'])]))
     elif op=='list':
      if arg.decode('ascii') not in specs:raise RuntimeError('PATTERN_NOT_IN_CATALOGUE')
      d=specs[arg.decode('ascii')];rec['catalogue_id']=d['id'];logs[ch].write(raw(rec));values=p.candidates(arg)
      if values is None:
       if d['count']!=0:raise RuntimeError('CATALOGUE_PRESENCE')
       send(ch,encode_pat(seq,['value',None]))
      else:
       count=len(values)
       if count!=d['count']:raise RuntimeError('CATALOGUE_COUNT')
       send(ch,encode_pat(seq,['begin',count]));payload=0
       for off in range(0,count,64):
        part=[v.decode('ascii') for v in values[off:off+64]];payload+=sum(map(len,part));send(ch,encode_pat(seq,['chunk',off,part]))
       if payload!=d['payload']:raise RuntimeError('CATALOGUE_PAYLOAD')
       send(ch,encode_pat(seq,['end',count,payload]));values=None
     elif op=='close':logs[ch].write(raw(rec));send(ch,encode_pat(seq,['value','closed']));mux.close(ch)
  status='BROKER_COMPLETE'
 except BaseException as e:error=repr(e);raise
 finally:
  result={'status':status,'error':error,'chain':chain.result(),'transactions':ordinal,'lookups':lookups,'membership':words,'channels':stats,'closed':mux.closed,'lm':lm.stats if lm else None,'pat':p.stats if p else None,'elapsed':time.monotonic()-t,'cpu':time.process_time(),'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
  if p:p.close()
  if lm:lm.close()
  for f in logs.values():f.close()
  for fd in fds:os.close(fd)
  with (A/'broker_terminal.json').open('x') as f:json.dump(result,f,sort_keys=True);f.write('\n')
  print('BROKER_COMPUTED '+json.dumps(result,sort_keys=True),flush=True)
if __name__=='__main__':main()
