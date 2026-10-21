"""Atomic, resumable prefix-only computations. Solver never receives suffix/truth."""
from pathlib import Path
import sys,os,json,hashlib,time,datetime,argparse,fcntl
sys.dont_write_bytecode=True
from engine import *
H=Path(__file__).parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def arrsha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def atomic_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
 tmp.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n');os.replace(tmp,path)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def check_frozen():
 p=H/'frozen_protocol.json';f=json.loads(p.read_text())
 for n,h in f['hashes'].items():
  assert sha(ROOT/n)==h,'frozen dependency changed: '+n
 return f

def run_case(case,arrays,dest=None,progress=False):
 lp,ch,v,letter=arrays
 out=H/'checkpoints' if dest is None else Path(dest)
 folder=out/case['id'];folder.mkdir(parents=True,exist_ok=True)
 final=folder/'training_result.json'
 if final.exists():return json.loads(final.read_text())
 g=np.array(case['prefix'],np.int64);assert len(g)==43
 fp=sha(H/'frozen_protocol.json');ih=arrsha(g)
 best=-1e100;bestid=-1;ties=[];wordeval=0;sumsecs=0.;blocks=[]
 starttime=utc();chunk=1024
 for start in range(0,len(P8),chunk):
  stop=min(start+chunk,len(P8));idx=start//chunk
  mp=folder/f'block_{idx:03d}.json';ap=folder/f'block_{idx:03d}.npz'
  if mp.exists():
   r=json.loads(mp.read_text());assert r['protocol_sha256']==fp and r['input_sha256']==ih
   assert (r['start'],r['stop'])==(start,stop)
   assert r['incoming_score']==best and r['incoming_id']==bestid
   assert r['incoming_ties']==ties
   assert ap.exists() and sha(ap)==r['file_sha256']
   with np.load(ap) as a:
    for k,h in r['array_sha256'].items():assert arrsha(a[k])==h
   best=r['best_score'];bestid=r['best_id'];ties=r['ties']
  else:
   # An orphan NPZ cannot establish completion. Preserve it rather than overwrite.
   if ap.exists():os.rename(ap,ap.with_suffix(f'.orphan-{time.time_ns()}.npz'))
   t=time.monotonic();b,bi,tt,stats,ids,cc,ww=scan_block(g,lp,ch,v,P8,Q,letter,start,stop,best,bestid)
   all_ties=sorted(set(tt.tolist()+ (ties if b==best else [])))
   assert bi==min(all_ties)
   arraysout={'char_max':stats[:,2],'word_upper':stats[:,3],
     'word_evaluated':stats[:,4].astype(np.int32),'scored_ids':ids,'C':cc,'W':ww}
   temp=ap.with_name(ap.name+'.tmp')
   with temp.open('wb') as f:np.savez_compressed(f,**arraysout)
   os.replace(temp,ap)
   r={'case':case['id'],'block':idx,'start':start,'stop':stop,'protocol_sha256':fp,'input_sha256':ih,
    'incoming_score':best,'incoming_id':bestid,'incoming_ties':ties,'best_score':float(b),'best_id':int(bi),
    'ties':all_ties,'char_keys':(stop-start)*768,'word_evaluations':len(ids),'pruned_keys':(stop-start)*768-len(ids),
    'array_sha256':{k:arrsha(a) for k,a in arraysout.items()},'file_sha256':sha(ap),
    'seconds':time.monotonic()-t,'completed_utc':utc()}
   atomic_json(mp,r);best=b;bestid=bi;ties=all_ties
  blocks.append({'block':idx,'json_sha256':sha(mp),'npz_sha256':sha(ap)})
  wordeval+=r['word_evaluations'];sumsecs+=r['seconds']
  if progress and idx%10==0:print(case['id'],'block',idx+1,'/40',flush=True)
 key=key_at(bestid)
 r={'case':case['id'],'kind':case['kind'],'protocol_sha256':fp,'input_sha256':ih,
    'status':'complete','keys':NK,'train_length':43,'train_score':float(best),'key_id':int(bestid),
    'key_ascii_0based':key.tolist(),'decoded_prefix':''.join(chr(int(x)+97) for x in key[g]),
    'exact_tie_count':len(ties),'exact_tie_ids':ties,'word_evaluations':wordeval,'pruned_keys':NK-wordeval,
    'blocks':blocks,'cpu_work_seconds_sum':sumsecs,'execution_start_utc':starttime,'completed_utc':utc(),
    'suffix_seen_by_solver':False}
 atomic_json(final,r)
 print(case['id'],'COMPLETE','keys',NK,'W',wordeval,'prefix_S',round(best,6),'ties',len(ties),'seconds',round(sumsecs,3),flush=True)
 return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kind',default='all');ap.add_argument('--case',action='append');ap.add_argument('--workers',type=int,default=4);ap.add_argument('--dest');ap.add_argument('--progress',action='store_true')
 a=ap.parse_args();check_frozen()
 # A single advisory lock protects main/repeat runners from accidental duplicate launches.
 lock=(H/'runner.lock').open('a+')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('Another round11 runner owns the lock; no duplicate launched.')
 cases=json.loads((H/'data/search_inputs.json').read_text())
 selected=[c for c in cases if (a.kind=='all' or c['kind'] in a.kind.split(',')) and (not a.case or c['id'] in a.case)]
 if a.case:assert len(selected)==len(set(a.case)),'unknown case'
 if not a.dest and any(c['kind'] in ('real','null') for c in selected):
  p=H/'audit/positives_verified.json';assert p.exists(),'Complete and verify positive controls first.'
  assert json.loads(p.read_text())['protocol_sha256']==sha(H/'frozen_protocol.json')
 d=np.load(H/'data/scoring.npz');arrays=(d['lp'],d['children'],d['vals'],d['letter'])
 # Compile using an artificial sequence only.
 scan_block(np.arange(43,dtype=np.int64)%24,*arrays[:3],P8,Q,arrays[3],0,1,-1e100,-1)
 state={'pid':os.getpid(),'started_utc':utc(),'command':sys.argv,'case_count':len(selected),'status':'running'}
 statepath=H/'logs'/f'run_state_{os.getpid()}.json';atomic_json(statepath,state)
 try:
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=a.workers) as ex:list(ex.map(lambda c:run_case(c,arrays,a.dest,a.progress),selected))
  state.update(status='completed',completed_utc=utc());atomic_json(statepath,state)
 except BaseException as e:
  state.update(status='failed',error=repr(e),failed_utc=utc());atomic_json(statepath,state);raise

if __name__=='__main__':main()
