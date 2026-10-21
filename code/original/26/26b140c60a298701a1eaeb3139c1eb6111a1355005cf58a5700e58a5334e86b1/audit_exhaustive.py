"""Supplemental verification only: EVERY prefix key gets both C and W.
This does not change the frozen main selection, inputs or test protocol.
"""
from pathlib import Path
import sys,os,json,hashlib,time,argparse,fcntl
sys.dont_write_bytecode=True
from engine import *
from run import sha,arrsha,atomic_json,check_frozen,utc
H=Path(__file__).parent
NAMES=['bailey_05','elgar_caractacus_postcard','hauer_real','hart_real','hauer_real_pair_00','hart_real_pair_00']

def one(case,arrays):
 dest=H/'audit/unpruned'/case['id'];dest.mkdir(parents=True,exist_ok=True)
 g=np.array(case['prefix'],np.int64);best=-1e100;ties=[];blocks=[];seconds=0.
 for start in range(0,40320,1024):
  stop=min(start+1024,40320);ix=start//1024;p=dest/f'block_{ix:03d}.json'
  if p.exists():r=json.loads(p.read_text())
  else:
   t=time.monotonic();a=brute_block(g,*arrays[:3],P8,Q,arrays[3],start,stop)
   scores=a[:,0]+.5*a[:,1];mx=float(scores.max());ids=(start*768+np.flatnonzero(scores==mx)).tolist()
   r={'start':start,'stop':stop,'keys':len(scores),'max_score':mx,'max_ids':ids,
      'score_matrix_sha256':arrsha(a),'seconds':time.monotonic()-t,'completed_utc':utc()}
   atomic_json(p,r)
  if r['max_score']>best:best=r['max_score'];ties=r['max_ids']
  elif r['max_score']==best:ties+=r['max_ids']
  blocks.append({'file':str(p.relative_to(H)),'sha256':sha(p)});seconds+=r['seconds']
 t=json.loads((H/'checkpoints'/case['id']/'training_result.json').read_text())
 assert best==t['train_score'] and min(ties)==t['key_id'] and sorted(ties)==t['exact_tie_ids']
 r={'case':case['id'],'all_keys_fully_scored':NK,'C_and_W_for_every_key':True,
   'main_best_score':t['train_score'],'unpruned_best_score':best,'key_id':min(ties),'ties':sorted(ties),
   'same_maximum_and_all_ties':True,'block_manifests':blocks,'seconds':seconds}
 atomic_json(dest/'verified.json',r)
 print(case['id'],'UNPRUNED VERIFIED',NK,'both C,W scores','ties',len(ties),'seconds',round(seconds,3),flush=True)
 return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
 check_frozen();lock=(H/'runner.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 frozen={'main_protocol_sha256':sha(H/'frozen_protocol.json'),'audit_code_sha256':sha(__file__),
   'cases':NAMES,'budget':'All30965760 keys, BOTH C and W, no bounds or shortlist. Prefix43 only. Same strict maximum and lexID tie.',
   'full_matrices':'Not retained; block hashes and extrema retained. Script regenerates all matrices.'}
 p=H/'audit/unpruned_protocol.json'
 if p.exists():assert json.loads(p.read_text())==frozen
 else:atomic_json(p,frozen)
 cases=json.loads((H/'data/search_inputs.json').read_text());cases=[next(c for c in cases if c['id']==n) for n in NAMES]
 d=np.load(H/'data/scoring.npz');arrays=(d['lp'],d['children'],d['vals'],d['letter'])
 brute_block(np.arange(43,dtype=np.int64)%24,*arrays[:3],P8,Q,arrays[3],0,1)
 from concurrent.futures import ThreadPoolExecutor
 with ThreadPoolExecutor(max_workers=a.workers) as ex:out=list(ex.map(lambda c:one(c,arrays),cases))
 atomic_json(H/'audit/unpruned_summary.json',{'cases':len(out),'all_keys_fully_scored':len(out)*NK,
   'all_agree':all(r['same_maximum_and_all_ties'] for r in out),'results':out})
if __name__=='__main__':main()
