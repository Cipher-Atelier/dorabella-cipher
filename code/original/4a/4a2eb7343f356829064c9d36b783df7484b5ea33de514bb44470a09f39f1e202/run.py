import engine as e
import numpy as np,json,time,hashlib,datetime,argparse

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,obj):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2));tmp.replace(p)
def check_frozen():
 f=json.loads((e.H/'protocol.json').read_text())
 for p,h in f['sha256'].items():assert sha(e.H/p)==h,(p,'changed')
 return sha(e.H/'protocol.json')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kind',default='positive,regression');ap.add_argument('--case',default=None);a=ap.parse_args()
 ph=check_frozen()
 if any(k in a.kind.split(',') for k in ('real','null')):
  v=json.loads((e.H/'checks/results_verified.json').read_text());pos=[r for r in v['records'] if r['kind'] in ('positive','regression')]
  assert len(pos)==14 and sum(r['correct']==87 for r in pos)>=12 and sum(r['correct'] for r in pos)>=1194,'Frozen sensitivity gate did not pass'
 cases=json.loads((e.H/'data/search_inputs.json').read_text());m=np.load(e.H/'data/scoring.npz');args=[m[k] for k in ['lp','children','vals']]
 for c in cases:
  if c['kind'] not in a.kind.split(',') or (a.case and c['id']!=a.case):continue
  out=e.H/'results'/(c['id']+'.json')
  if out.exists():continue
  g=np.array(c['glyph'],np.int64);inc=-1e100;ties=[];wn=0;blocks=[];t0=time.time()
  ck=e.H/'checkpoints'/c['id'];ck.mkdir(parents=True,exist_ok=True)
  for pi in range(16):
   bp=ck/f'{pi:02d}.json'
   if bp.exists():b=json.loads(bp.read_text());assert b['protocol_sha256']==ph and b['incoming']==inc
   else:
    t=time.time();r=e.scan(g,pi,0,e.NQ,*args,e.P,e.Q,e.LETTER,inc)
    b=dict(pidx=pi,incoming=inc,score=r[0],key_id=r[1],exact_ties=list(r[2]),word_evaluations=r[3],C=r[4],W=r[5],word_bound=r[6],seconds=time.time()-t,keys=e.NQ,protocol_sha256=ph);atomic(bp,b)
   if b['score']>inc:inc=b['score'];ties=b['exact_ties']
   elif b['score']==inc:ties+=b['exact_ties']
   wn+=b['word_evaluations'];blocks.append(b)
  ties=sorted(set(ties));key=e.key_at(ties[0]);text=''.join(chr(int(x)+97) for x in key[g]);r=dict(id=c['id'],kind=c['kind'],source=c.get('source'),score=inc,key_id=ties[0],exact_ties=ties,key_ascii_0based=key.tolist(),decoded=text,char_evaluations=e.NK,word_evaluations=wn,seconds=time.time()-t0,completed_utc=stamp(),protocol_sha256=ph,blocks=blocks)
  atomic(out,r);print(c['id'],r['score'],'key',r['key_id'],'ties',len(ties),'W',wn,'seconds',r['seconds'],flush=True)
if __name__=='__main__':main()
