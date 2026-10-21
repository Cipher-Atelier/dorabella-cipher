"""Post-freeze orchestration only: at most two disjoint fixed-case runners."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,json,sys,time
H=Path(__file__).resolve().parents[1]
cases=[c for c in json.loads((H/'data/search_inputs.json').read_text()) if c['kind'] in ('real','null')]
def one(c):
 with (H/'logs'/(c['id']+'.log')).open('a') as out:
  r=subprocess.run([sys.executable,str(H/'code/run.py'),'--kind',c['kind'],'--case',c['id']],stdout=out,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError((c['id'],r.returncode))
 x=json.loads((H/'results'/(c['id']+'.json')).read_text());print(c['id'],x['score'],'seconds',x['seconds'],flush=True)
 return c['id']
with ThreadPoolExecutor(max_workers=2) as ex:
 for name in ex.map(one,cases):pass
print('COMPLETE',len(cases),flush=True)
