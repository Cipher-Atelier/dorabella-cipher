"""Exploratory, fully calibrated categorical change-point diagnostic.
Tests shifts in symbol frequencies, not every possible key or cipher change.
No letters or model fitting; G2 pooled over all allowed cut positions.
"""
from pathlib import Path
import sys,json,hashlib,itertools
from collections import Counter
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from conditional_v7 import euler_shuffle
OUT=HERE/'results'/'change_point';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'id':'round9-change-point-v1','seed':2026100149,'n_random_controls_each':9999,
 'primary':'max multinomial two-segment G2 over all cuts with at least 12 glyphs on each side',
 'cuts':list(range(12,76)),'alphabet':'full 24 glyphs; no geometry grouping or plaintext guesses',
 'controls':['uniform whole-sequence multiset permutations','uniform whole-sequence directed bigram and endpoints preserving','complete existing global trigram and endpoints preserving ensemble'],
 'fixed_cuts_diagnostic':[12,29,60,65],
 'scope':'frequency regime changes only; not all cipher/key changes; exploratory, no global correction for previous rounds',
 'transcriptions':'both separately; no choose-best p-value'}
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def freeze():
 paths=[Path(__file__),ROOT/'conditional_v7.py',ROOT/'results/v7/conditional/inputs.json']
 obj={'protocol':PROTOCOL,'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
 p=HERE/'frozen_change_point_protocol.json'
 if p.exists():assert json.loads(p.read_text())==obj
 else:dump(p,obj)
 return obj
@njit(cache=True)
def stats(a,minside=12):
 N,L=a.shape;out=np.empty((N,L-2*minside+1));flog=np.zeros(L+1)
 for k in range(1,L+1):flog[k]=k*np.log(k)
 for r in range(N):
  totals=np.zeros(24,np.int64);left=np.zeros(24,np.int64)
  for t in range(L):totals[a[r,t]]+=1
  const=flog[L]
  for k in range(24):const-=flog[totals[k]]
  for t in range(1,L-minside+1):
   left[a[r,t-1]]+=1
   if t<minside:continue
   v=const-flog[t]-flog[L-t]
   for k in range(24):v+=flog[left[k]]+flog[totals[k]-left[k]]
   out[r,t-minside]=2*v
 return out

def summary(a,values,obs,s,random):
 N=len(a);threshold=obs.max();mx=values.max(axis=1);ge=int(np.sum(mx>=threshold-1e-10))
 out={'n':N,'primary_max_G2':{'ge':ge,'fraction':(ge+1)/(N+1) if random else ge/N,'estimator':'(k+1)/(n+1)' if random else 'exact k/N','observed':float(threshold)},
  'fixed_cuts_diagnostic':{},'mean_changed_positions':float(np.sum(a!=s,axis=1).mean()),'distinct_input_sequences':len(np.unique(a,axis=0))}
 for cut in PROTOCOL['fixed_cuts_diagnostic']:
  j=cut-12;k=int(np.sum(values[:,j]>=obs[j]-1e-10))
  out['fixed_cuts_diagnostic'][str(cut)]={'G2':float(obs[j]),'ge':k,'fraction':(k+1)/(N+1) if random else k/N,'distinct_prefixes':len(np.unique(a[:,:cut],axis=0))}
 return out

def checks():
 rng=np.random.default_rng(777);maxerr=0
 for i in range(100):
  a=rng.integers(0,24,size=(1,87));sc=stats(a)[0]
  for t in range(12,76):
   table=np.stack([np.bincount(a[0,:t],minlength=24),np.bincount(a[0,t:],minlength=24)])
   exp=table.sum(axis=1)[:,None]*table.sum(axis=0)[None,:]/87
   mask=table>0;v=2*np.sum(table[mask]*np.log(table[mask]/exp[mask]))
   maxerr=max(maxerr,abs(sc[t-12]-v));assert abs(sc[t-12]-v)<1e-10
  perm=rng.permutation(24);assert np.allclose(stats(perm[a]),sc,atol=1e-10)
 # Maximum at the known sharp synthetic change, disjoint half-alphabets.
 a=np.array([[0,1]*22+[2,3]*21+[2]],np.uint8);sc=stats(a)[0];assert int(np.argmax(sc))+12==44
 return {'independent_contingency_checks':6400,'relabel_invariance_cases':100,'max_abs_error':maxerr,'sharp_synthetic_change_cut':44}

def main():
 freeze();out={'protocol':PROTOCOL,'implementation_checks':checks(),'cases':{}}
 cases=[c for c in json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'] if c['kind']=='real']
 for ci,c in enumerate(cases):
  s=np.asarray(c['glyph'],np.uint8);obs=stats(s[None,:])[0];top=np.argsort(-obs,kind='stable')
  res={'observed_by_cut':obs.tolist(),'maximizing_cut_after_1_based':int(top[0])+12,'top_five_cuts':[int(i)+12 for i in top[:5]],'nulls':{}}
  for k,style in enumerate(['unigram','bigram','trigram']):
   rng=np.random.default_rng(np.random.SeedSequence([PROTOCOL['seed'],ci,k]));n=PROTOCOL['n_random_controls_each']
   if style=='trigram':a=np.load(ROOT/f'round8/results/{c["id"]}_trigrams.npz')['sequences']
   else:
    a=np.array([rng.permutation(s) if style=='unigram' else euler_shuffle(s,rng) for i in range(n)],np.uint8)
    assert np.all(np.sort(a,axis=1)==np.sort(s))
    if style=='bigram':
     assert np.all(a[:,0]==s[0]) and np.all(a[:,-1]==s[-1])
     b=a.astype(np.int64);ss=s.astype(np.int64);assert np.all(np.sort(b[:,:-1]*24+b[:,1:],axis=1)==np.sort(ss[:-1]*24+ss[1:]))
   values=stats(a);res['nulls'][style]=summary(a,values,obs,s,style!='trigram')
   np.savez_compressed(OUT/f'{c["id"]}_{style}.npz',sequences=a,statistics=values)
  out['cases'][c['id']]=res;dump(OUT/'summary.json',out);print(c['id'],json.dumps(res,indent=2),flush=True)
 freeze()
if __name__=='__main__':main()
