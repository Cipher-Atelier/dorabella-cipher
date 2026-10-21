"""Prepared LM IPC broker; never executed during preparation."""
from pathlib import Path
import sys,json,time
sys.dont_write_bytecode=True
B=Path(__file__).resolve().parent;sys.path.insert(0,str(B))
from disk_contract import DiskLM
from wire import request,packet
def main():
 role=sys.argv[1]
 if role not in ['adapted_broker','real_broker']:raise RuntimeError('ROLE')
 ds=json.loads((B/'datasets.json').read_text());allowed=['base','edge'] if role=='adapted_broker' else ['real']
 deadline=json.loads((B/'attempt/phase_deadline.json').read_text())['deadline']
 def tick():
  if time.monotonic()>=deadline:raise RuntimeError('DEADLINE')
 stores={};log=(B/'attempt'/f'{role}_ipc.jsonl').open('xb')
 stats={'requests':0,'lookups':0,'response_frames':0,'response_bytes':0,'max_frame':0,'closed':False}
 try:
  for name in allowed:
   es=[]
   for e in ds[name]:
    e=dict(e)
    for k in ['path','index_path']:
     if not Path(e[k]).is_absolute():e[k]=str(B/e[k])
    es.append(e)
   stores[name]=DiskLM(es,tick,3 if name!='real' else 4096)
  for seq in range(1,513):
   tick();raw=sys.stdin.buffer.readline(65537);name,items=request(raw,seq,allowed)
   stats['requests']=seq;log.write(b'{"request":'+raw.rstrip(b'\n')+b'}\n');log.flush()
   if stats['lookups']+len(items)>20000:raise RuntimeError('LOOKUP_BOUND')
   chunks=range(0,len(items),128) if items else [0]
   for offset in chunks:
    vals=[]
    for table,key in items[offset:offset+128]:
     r=stores[name].lookup(table,key);vals.append([r['found'],r['value_hex'],r['last_row_1based']]);stats['lookups']+=1
    out=packet(seq,offset,vals,offset+len(vals)==len(items));tick()
    log.write(b'{"response":'+out.rstrip(b'\n')+b'}\n');log.flush()
    sys.stdout.buffer.write(out);sys.stdout.buffer.flush()
    stats['response_frames']+=1;stats['response_bytes']+=len(out);stats['max_frame']=max(stats['max_frame'],len(out))
   if name=='close':stats['closed']=True;break
  if not stats['closed']:raise RuntimeError('NO_CLOSE')
 finally:
  stats['stores']={k:s.stats for k,s in stores.items()}
  for s in stores.values():s.close()
  log.close()
 (B/'attempt'/f'{role}_terminal.json').write_text(json.dumps(stats,indent=2)+'\n')
if __name__=='__main__':main()
