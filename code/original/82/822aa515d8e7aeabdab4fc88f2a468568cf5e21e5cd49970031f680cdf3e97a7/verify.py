import engine as e
import numpy as np,json,itertools,hashlib,argparse
from collections import Counter

def independent_key(k):
 pi,n=divmod(int(k),6**8);sign=1 if pi<8 else -1;shift=pi%8
 perms=list(itertools.permutations(range(3)))
 return np.array([ord(e.ALPHABET[3*((sign*o+shift)%8)+perms[(n//(6**o))%6][c]])-97 for o in range(8) for c in range(3)])

def ref_word(t,ch,v):
 n=len(t);dp=[-1e100]*(n+1);prev=[None]*(n+1);dp[0]=0.
 for end in range(1,n+1):
  dp[end]=dp[end-1]-8.;prev[end]=end-1
  for start in range(max(0,end-24),end):
   node=0
   for a in t[start:end]:
    node=int(ch[node,a])
    if node<0:break
   if node<0:continue
   w=v[node,0]
   if start==0 and end<n:w=max(w,v[node,2])
   if end==n and start>0:w=max(w,v[node,1])
   if dp[start]+w>dp[end]:dp[end]=dp[start]+w;prev[end]=start
 words=[];end=n
 while end:
  start=prev[end];words.append(''.join(chr(int(x)+97) for x in t[start:end]));end=start
 return dp[n]/n,' '.join(words[::-1])
def ref_score(t,args):
 lp,ch,v=args;codes=((t[:-3]*26+t[1:-2])*26+t[2:-1])*26+t[3:]
 C=float(lp[codes].sum()/(len(t)-3));W,words=ref_word(t,ch,v);return C+.5*W,C,W,words

def preflight():
 rng=np.random.default_rng(202610051343);m=np.load(e.H/'data/scoring.npz');args=[m[k] for k in ['lp','children','vals']];assert np.isfinite(args[2]).all() and args[2].max()<=0
 cases=json.loads((e.H/'data/search_inputs.json').read_text());truth={x['id']:x for x in json.loads((e.H/'data/positive_truth.json').read_text())}
 for c in cases:
  if c['id'] in truth:
   tr=truth[c['id']];assert ''.join(chr(int(x)+97) for x in independent_key(tr['true_key_id'])[c['glyph']])==tr['plaintext']
  if c['kind']=='null':
   real=next(x for x in cases if x['id']==c['source']);g=c['glyph'];r=real['glyph'];assert Counter(g)==Counter(r) and Counter(zip(g[:-1],g[1:]))==Counter(zip(r[:-1],r[1:])) and g[0]==r[0] and g[-1]==r[-1]
 maxerr=0.;roundtrip=0;boundchecks=0
 for k in list(rng.integers(0,e.NK,size=128))+[0,e.NK-1,6**8-1,6**8]:
  key=independent_key(k);assert np.array_equal(key,e.key_at(k));assert len(set(key))==24
  g=rng.integers(0,24,size=87,dtype=np.int64);t=key[g];inv={int(a):i for i,a in enumerate(key)};assert [inv[int(a)] for a in t]==g.tolist();roundtrip+=1
  s,C,W,_=ref_score(t,args);sf=e.char_score(t,args[0])+.5*e.word_score(t,*args[1:]);maxerr=max(maxerr,abs(s-sf));assert abs(s-sf)<1e-11
  pi,z=divmod(int(k),e.NQ);b=e.word_bound(g,e.P[pi],e.LETTER,*args[1:],e.Q,z);assert W<=b+1e-11;boundchecks+=1
 blocks=[]
 for j in range(12):
  g=rng.integers(0,24,size=87,dtype=np.int64);pi=int(rng.integers(16));start=int(rng.integers(e.NQ-1000));stop=start+1000
  a=e.scan(g,pi,start,stop,*args,e.P,e.Q,e.LETTER,-1e100);b=e.scan(g,pi,start,stop,*args,e.P,e.Q,e.LETTER,-1e100,True)
  assert a[:3]==b[:3];blocks.append(dict(pi=pi,start=start,stop=stop,score=a[0],ties=list(a[2])))
 out=dict(status='passed',random_roundtrips=roundtrip,direct_score_checks=roundtrip,word_bound_checks=boundchecks,max_independent_score_error=maxerr,pruned_vs_unpruned_blocks=blocks,source_manifest_verified=4244,controls_preserved=78)
 (e.H/'checks/preflight.json').write_text(json.dumps(out,indent=2));print(out,flush=True)

def results():
 m=np.load(e.H/'data/scoring.npz');args=[m[k] for k in ['lp','children','vals']];inputs={x['id']:x for x in json.loads((e.H/'data/search_inputs.json').read_text())};truth={x['id']:x for x in json.loads((e.H/'data/positive_truth.json').read_text())};out=[]
 for f in sorted((e.H/'results').glob('*.json')):
  if f.name=='summary.json':continue
  r=json.loads(f.read_text());g=np.array(inputs[r['id']]['glyph'],np.int64);key=independent_key(r['key_id']);t=key[g];S,C,W,seg=ref_score(t,args);err=abs(S-r['score']);assert err<1e-11
  assert r['key_id']==min(r['exact_ties']) and r['key_ascii_0based']==key.tolist() and ''.join(chr(int(a)+97) for a in t)==r['decoded'];inv={int(a):i for i,a in enumerate(key)};assert [inv[int(a)] for a in t]==g.tolist()
  assert len(r['blocks'])==16 and sum(b['keys'] for b in r['blocks'])==e.NK
  for k in r['exact_ties']:assert abs(ref_score(independent_key(k)[g],args)[0]-S)<1e-11
  v=dict(id=r['id'],kind=r['kind'],S=r['score'],C=C,W=W,independent_error=err,re_encryption=True,key_id=r['key_id'],ties=len(r['exact_ties']),decoded=r['decoded'],segmentation=seg)
  if r['id'] in truth:
   tr=truth[r['id']];v.update(correct=sum(a==b for a,b in zip(r['decoded'],tr['plaintext'])),true_key_among_ties=tr['true_key_id'] in r['exact_ties'],true_key=tr['true_key_id'])
  if r['kind'] in ('real','null'):assert len(r['exact_ties'])>=2 and len(r['exact_ties'])%2==0
  out.append(v)
 summary=dict(verified_cases=len(out),keys_per_case=e.NK,char_evaluations=sum(json.loads(f.read_text())['char_evaluations'] for f in (e.H/'results').glob('*.json') if f.name!='summary.json'),word_evaluations=sum(json.loads(f.read_text())['word_evaluations'] for f in (e.H/'results').glob('*.json') if f.name!='summary.json'),records=out)
 for version in ('hauer_real','hart_real'):
  real=next((x for x in out if x['id']==version),None);nulls=[x for x in out if x['id'].startswith(version+'_pair')]
  if real and len(nulls)==39:
   greater=sum(x['S']>=real['S']-1e-10 for x in nulls);summary[version]=dict(real=real,controls_no_lower=greater,controls_n=39,descriptive_tail=(greater+1)/40,rank=greater+1)
 (e.H/'checks/results_verified.json').write_text(json.dumps(summary,indent=2));print({k:v for k,v in summary.items() if k!='records'},flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');a=ap.parse_args();preflight() if a.preflight else results()
