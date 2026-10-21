"""Independent of pruning: compute C and W for all keys for six frozen cases."""
from engine import *
from run import sha,arrsha,atomic_json,check_frozen,utc
import json,time,argparse,fcntl
from concurrent.futures import ThreadPoolExecutor

def one(case,arrays,apsha):
 folder=H/'audit/unpruned'/case['id'];folder.mkdir(parents=True,exist_ok=True)
 g=np.array(case['glyph'],np.int64);ih=arrsha(g);best=-1e100;ties=[];blocks=[];seconds=0.
 for start in range(0,40320,1024):
  stop=min(start+1024,40320);idx=start//1024;p=folder/f'block_{idx:03d}.json'
  if p.exists():
   r=json.loads(p.read_text());assert r['audit_protocol_sha256']==apsha and r['input_sha256']==ih
   assert r['start']==start and r['stop']==stop and r['keys']==(stop-start)*768
   assert r['incoming_best']==best and r['incoming_ties']==ties
  else:
   t=time.monotonic();a=brute_block(g,*arrays[:3],P8,Q,arrays[3],start,stop)
   ss=a[:,0]+.5*a[:,1];mx=float(ss.max());ids=(np.flatnonzero(ss==mx)+start*768).tolist()
   r={'case':case['id'],'audit_protocol_sha256':apsha,'input_sha256':ih,'start':start,'stop':stop,'keys':len(a),'incoming_best':best,'incoming_ties':ties,'block_max':mx,'block_tie_ids':ids,'matrix_sha256':arrsha(a),'elapsed_wall_seconds':time.monotonic()-t,'completed_utc':utc()}
   atomic_json(p,r)
  if r['block_max']>best:best=r['block_max'];ties=r['block_tie_ids']
  elif r['block_max']==best:ties+=r['block_tie_ids']
  seconds+=r['elapsed_wall_seconds'];blocks.append({'block':idx,'sha256':sha(p)})
  if idx%10==0:print(case['id'],'UNPRUNED',idx+1,'/40',flush=True)
 tr=json.loads((H/'checkpoints'/case['id']/'training_result.json').read_text())
 assert best==tr['train_score'] and min(ties)==tr['key_id'] and sorted(ties)==tr['exact_tie_ids']
 r={'case':case['id'],'audit_protocol_sha256':apsha,'all_keys_fully_scored':NK,'C_and_W_for_every_key':True,'full87_training':True,'same_maximum_and_all_ties':True,'score87':best,'key_id':min(ties),'exact_tie_ids':sorted(ties),'blocks':blocks,'block_elapsed_wall_seconds_sum':seconds,'completed_utc':utc()}
 atomic_json(folder/'verified.json',r)
 print(case['id'],'UNPRUNED VERIFIED',NK,'ties',len(ties),'seconds',round(seconds,3),flush=True)
 return r

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);a=parser.parse_args();assert 1<=a.workers<=4
 f=check_frozen();lock=(H/'runner.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 names=f['protocol']['verification']['full_unpruned_cases']
 protocol={'main_protocol_sha256':sha(H/'frozen_protocol.json'),'audit_code_sha256':sha(__file__),'cases':names,'keys_per_case':NK,'objective':'All87, both C and W on every key, no pruning; float64 strict max/minID and all exact ties.','matrices':'Computed, not retained; per-block SHA256, exact maximum and all ties retained. Reproducible using this code.'}
 p=H/'audit/unpruned_protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 else:atomic_json(p,protocol)
 apsha=sha(p);cases=json.loads((H/'data/search_inputs.json').read_text());selected=[next(c for c in cases if c['id']==n) for n in names]
 d=np.load(H/'data/scoring.npz',allow_pickle=False);arrays=tuple(d[k] for k in ['lp','children','vals','letter']);brute_block(np.arange(87,dtype=np.int64)%24,*arrays[:3],P8,Q,arrays[3],0,1)
 started=utc();t=time.monotonic()
 with ThreadPoolExecutor(max_workers=a.workers) as pool:r=list(pool.map(lambda c:one(c,arrays,apsha),selected))
 atomic_json(H/'audit/unpruned_summary.json',{'cases':len(r),'all_keys_fully_scored':len(r)*NK,'all_agree':all(x['same_maximum_and_all_ties'] for x in r),'audit_protocol_sha256':apsha,'started_utc':started,'completed_utc':utc(),'elapsed_wall_seconds':time.monotonic()-t,'results':r})
if __name__=='__main__':main()
