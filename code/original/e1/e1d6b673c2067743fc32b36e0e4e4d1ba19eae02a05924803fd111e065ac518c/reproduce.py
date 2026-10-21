"""Recompute missing/full score matrices and verify their exact array hash.
Usage: python round10/reproduce.py --case hauer_real
       python round10/reproduce.py --all
No previous-round files are modified. Frozen numerical protocol is checked.
"""
from pathlib import Path
import os,sys,argparse,json,hashlib
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
os.environ.setdefault('NUMBA_CACHE_DIR',str(HERE/'cache'))
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import numpy as np
from table_search import setup,all_scores,P8,P3,LETTER

def main():
 p=argparse.ArgumentParser();p.add_argument('--case',action='append');p.add_argument('--all',action='store_true');p.add_argument('--save',action='store_true',help='Write the regenerated matrix into round10/results/records')
 a=p.parse_args()
 if not a.all and not a.case:p.error('choose --all or --case ID')
 cases,lp,sc,ch,v=setup();known={c['id'] for c in cases}
 if a.case and not set(a.case)<=known:p.error('unknown case id')
 for c in cases:
  if not a.all and c['id'] not in a.case:continue
  r=json.loads((HERE/'results/records'/(c['id']+'.json')).read_text())
  q=all_scores(np.array(c['glyph'],np.int64),lp,ch,v,P8,P3,LETTER)
  assert hashlib.sha256(q.tobytes()).hexdigest()==r['scores_sha256'],c['id']
  assert int(np.argmax(q[:,0]+.5*q[:,1]))==r['best_key']
  assert int(np.argmax(q[:,2]+.5*q[:,3]))==r['prefix_key']
  if a.save:np.savez_compressed(HERE/'results/records'/(c['id']+'_scores.npz'),scores=q)
  print(c['id'],'all 241920 full and prefix scores verified',flush=True)
if __name__=='__main__':main()
