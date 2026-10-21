"""Always perform a FRESH full prefix recomputation, never accept cached outputs.
Example: python round11/reproduce.py --case hauer_real --case hart_real
"""
from pathlib import Path
import sys,os,json,tempfile,argparse,fcntl
sys.dont_write_bytecode=True
from engine import *
from run import check_frozen,run_case,atomic_json
H=Path(__file__).parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',action='append',required=True);a=ap.parse_args()
 check_frozen();lock=(H/'runner.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 inp=json.loads((H/'data/search_inputs.json').read_text());known={c['id']:c for c in inp};assert set(a.case)<=set(known)
 (H/'audit/reproductions').mkdir(exist_ok=True)
 dest=Path(tempfile.mkdtemp(prefix='fresh-',dir=H/'audit/reproductions'))
 d=np.load(H/'data/scoring.npz');arrays=(d['lp'],d['children'],d['vals'],d['letter']);out=[]
 for name in a.case:
  r=run_case(known[name],arrays,dest)
  old=json.loads((H/'checkpoints'/name/'training_result.json').read_text())
  for k in ['train_score','key_id','exact_tie_ids','word_evaluations']:assert r[k]==old[k]
  for i in range(40):
   x=json.loads((dest/name/f'block_{i:03d}.json').read_text());y=json.loads((H/'checkpoints'/name/f'block_{i:03d}.json').read_text())
   assert x['array_sha256']==y['array_sha256']
  out.append({'case':name,'fresh_full30965760_search':True,'all40_arrays_identical':True})
 atomic_json(dest/'verified.json',out);print('Fresh repeat directory:',dest,flush=True)
if __name__=='__main__':main()
