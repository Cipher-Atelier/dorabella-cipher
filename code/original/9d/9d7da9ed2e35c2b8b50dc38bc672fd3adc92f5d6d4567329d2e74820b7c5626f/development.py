from pathlib import Path
import json,time,hashlib,os,sys
sys.dont_write_bytecode=True
from engine import *
H=Path(__file__).parent
lp,sc,ch,v=load_model();print('loaded',ch.shape,flush=True)
rng=np.random.default_rng(202610011100)
checks=[]
for t in range(5):
 g=rng.integers(0,24,size=43,dtype=np.int64)
 p0=int(rng.integers(0,40312));p1=p0+2
 tt=time.time();a=scan_block(g,lp,ch,v,P8,Q,LETTER,p0,p1,-1e100,-1)
 b=brute_block(g,lp,ch,v,P8,Q,LETTER,p0,p1)
 ss=b[:,0]+.5*b[:,1];bi=p0*768+int(np.argmax(ss))
 assert abs(a[0]-ss.max())<1e-12 and a[1]==bi
 for row in a[3]:
  k=(int(row[0])-p0)*768+int(row[1])*256
  assert max(b[k:k+256,1])<=row[3]+1e-10
 for ix,cc,ww in zip(a[4],a[5],a[6]):
  assert abs(cc-b[ix-p0*768,0])<1e-12 and abs(ww-b[ix-p0*768,1])<1e-12
 checks.append({'p0':p0,'p1':p1,'keys':len(b),'evaluated_word':len(a[4]),'max_error':float(np.max(np.abs(b[a[4]-p0*768,0]-a[5]))),'seconds':time.time()-tt})
 print('check',checks[-1],flush=True)
g=rng.integers(0,24,size=43,dtype=np.int64);tt=time.time()
a=scan_block(g,lp,ch,v,P8,Q,LETTER,0,256,-1e100,-1)
print('benchmark',time.time()-tt,'words',len(a[4]),'keys',256*768,flush=True)
(H/'audit/development.json').write_text(json.dumps({'seed':202610011100,'checks':checks,'benchmark_seconds':time.time()-tt,'benchmark_word_evals':len(a[4]),'benchmark_keys':256*768,'on_synthetic_uniform_glyphs_only':True},indent=2))
