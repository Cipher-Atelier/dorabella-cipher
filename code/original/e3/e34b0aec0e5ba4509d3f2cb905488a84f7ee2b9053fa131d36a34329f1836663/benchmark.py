import engine as e
import numpy as np,json,time
m=np.load(e.H/'data/scoring.npz');args=[m[k] for k in ['lp','children','vals']]
rng=np.random.default_rng(202610051338)
g=rng.integers(0,24,size=87,dtype=np.int64)
t=time.time();e.scan(g,0,0,10,*args,e.P,e.Q,e.LETTER,-1e100);print('compile',time.time()-t,flush=True)
out=[]
for n in [10000,100000,e.NQ]:
 t=time.time();r=e.scan(g,0,0,n,*args,e.P,e.Q,e.LETTER,-1e100);out.append(dict(n=n,seconds=time.time()-t,W=r[3],S=r[0],word_bound=r[6]));print(out[-1],flush=True)
(e.H/'checks/benchmark.json').write_text(json.dumps(out,indent=2))
