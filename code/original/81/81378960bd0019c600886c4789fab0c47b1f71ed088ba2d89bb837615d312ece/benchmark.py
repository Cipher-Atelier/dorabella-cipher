from engine import *
import json,time,platform,hashlib
from concurrent.futures import ThreadPoolExecutor
A=np.load(H/'data/scoring.npz');arrays=tuple(A[k] for k in ['lp','children','vals','letter'])
lp,ch,v,letter=arrays;assert np.array_equal(LETTER,letter)
report={'python':sys.version,'numpy':np.__version__,'numba':__import__('numba').__version__,'llvmlite':__import__('llvmlite').__version__,'cpu_count':os.cpu_count(),'affinity':sorted(os.sched_getaffinity(0)),'checks':[],'benchmarks':[],'warmup_seconds':None}
g=np.arange(87,dtype=np.int64)%24
t=time.monotonic();scan_block(g,*arrays[:3],P8,Q,letter,0,1,-1e100,-1);brute_block(g,*arrays[:3],P8,Q,letter,0,1);report['warmup_seconds']=time.monotonic()-t
# Deterministic predeclared synthetic tests, full score equality and bound checks.
for seed,ps in [(1301,0),(1302,137),(1303,20160),(1304,40319)]:
 g=np.random.default_rng(seed).integers(0,24,87,dtype=np.int64)
 for n in [43,87]:
  b=brute_block(g[:n],*arrays[:3],P8,Q,letter,ps,ps+1);r=scan_block(g[:n],*arrays[:3],P8,Q,letter,ps,ps+1,-1e100,-1);s=b[:,0]+.5*b[:,1];ties=np.flatnonzero(s==s.max())+ps*768
  assert r[0]==s.max() and r[1]==ties.min() and sorted(r[2])==list(ties)
  for m in range(3):assert b[m*256:(m+1)*256,1].max()<=r[3][m,3]+1e-9
  report['checks'].append({'seed':seed,'length':n,'P8_index':ps,'keys':768,'winner':int(r[1]),'score':float(r[0]),'ties':ties.tolist(),'passed':True})
def bench(seed,start,count=256):
 g=np.random.default_rng(seed).integers(0,24,87,dtype=np.int64);t=time.monotonic();r=scan_block(g,*arrays[:3],P8,Q,letter,start,start+count,-1e100,-1)
 return {'seed':seed,'start':start,'stop':start+count,'keys':count*768,'fresh_incumbent':True,'seconds':time.monotonic()-t,'word_evaluations':len(r[4]),'score':float(r[0]),'input_sha256':hashlib.sha256(g.tobytes()).hexdigest()}
for seed,start in [(1311,0),(1312,10000),(1313,30000)]:
 r=bench(seed,start);report['benchmarks'].append(r);print('BENCH',r,flush=True)
t=time.monotonic()
with ThreadPoolExecutor(max_workers=4) as ex: rr=list(ex.map(lambda x:bench(*x),[(1321,0),(1322,10000),(1323,20000),(1324,30000)]))
report['parallel4']={'seconds':time.monotonic()-t,'runs':rr};report['estimated_94_series_seconds_parallel4']=report['parallel4']['seconds']*(40320/256)*(94/4)
(H/'checks/benchmark.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
