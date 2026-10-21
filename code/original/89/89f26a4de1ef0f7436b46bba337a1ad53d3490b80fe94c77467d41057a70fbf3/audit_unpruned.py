"""Post-run check only; never changes the frozen search."""
import engine as e
from run import check_frozen
import numpy as np,json,time,argparse
ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);a=ap.parse_args();ph=check_frozen()
c=next(c for c in json.loads((e.H/'data/search_inputs.json').read_text()) if c['id']==a.case);g=np.array(c['glyph'],np.int64);m=np.load(e.H/'data/scoring.npz');args=[m[k] for k in ['lp','children','vals']]
r=json.loads((e.H/'results'/(a.case+'.json')).read_text());inc=-1e100;ties=[];blocks=[];t0=time.time()
for pi in range(16):
 t=time.time();x=e.scan(g,pi,0,e.NQ,*args,e.P,e.Q,e.LETTER,inc,True)
 if x[0]>inc:inc=x[0];ties=list(x[2])
 elif x[0]==inc:ties+=list(x[2])
 assert x[3]==e.NQ
 blocks.append(dict(pidx=pi,score=x[0],ties=list(x[2]),full_C_and_W=x[3],seconds=time.time()-t))
ties=sorted(set(ties));assert inc==r['score'] and ties==r['exact_ties']
out=dict(id=a.case,status='passed',score=inc,exact_ties=ties,full_C_and_W=e.NK,seconds=time.time()-t0,blocks=blocks,protocol_sha256=ph)
(e.H/'checks'/('unpruned_'+a.case+'.json')).write_text(json.dumps(out,indent=2));print(a.case,'UNPRUNED PASS',inc,len(ties),out['seconds'],flush=True)
