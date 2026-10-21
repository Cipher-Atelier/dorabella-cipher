"""Round9 order-sensitive walk audit, writing only round9.
Primary: sum of squared distances from each printed row's initial point, over all
87 endpoints. Shorter/compact paths have smaller statistic. Null 1 uniformly
permutes each row's multiset; null 2 independently samples uniformly from each
row's complete directed-bigram/endpoints-preserving ensemble. No language model.
"""
from pathlib import Path
import sys,json,hashlib,subprocess,math,time
from collections import Counter
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path[:0]=[str(ROOT),str(ROOT/'round8')]
from count_bigrams_v7 import count_strings
from exact_study import COEFF,le_exact,vals
OUT=HERE/'results'/'geometry';OUT.mkdir(parents=True,exist_ok=True)
ROWS=((0,29),(29,60),(60,87))
PROTOCOL={'id':'round9-order-sensitive-geometry-v1','seed':2026100109,
 'n_monte_carlo':99999,'primary':'sum over all three printed rows of squared cumulative radius at every glyph',
 'direction':'orientation*pi/4; distance arcs 1..3','row_initial':'origin separately for each printed row',
 'tail':'lower, compact paths','nulls':['rowwise uniform multiset permutation','independent uniform rowwise exact directed-bigram/endpoints ensemble'],
 'secondary':'per-row exact tails; first two rows combined labelled diagnostic, not selected discovery',
 'transcriptions':'both reported separately, no best-version selection',
 'constraints':'no resets at dots, no image edits, no language or key optimisation',
 'scope':'exploratory direction inherited from previous rounds; protocol frozen before new statistic/control results'}
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze():
 files=[Path(__file__),ROOT/'round8/enumerate_kgrams.cpp',ROOT/'round8/exact_study.py',ROOT/'count_bigrams_v7.py',ROOT/'results/v7/conditional/inputs.json']
 obj={'protocol':PROTOCOL,'sha256':{str(p.relative_to(ROOT)):sha(p) for p in files}}
 p=HERE/'frozen_geometry_protocol.json'
 if p.exists():assert json.loads(p.read_text())==obj
 else:dump(p,obj)
 return obj

def pair_sq(points):
 x,y,dx,dy=np.moveaxis(points,-1,0)
 return np.stack([2*(x*x+y*y)+dx*dx+dy*dy,2*(x*dx+y*dy)],axis=-1)
def path_measures(a):
 a=np.asarray(a,dtype=np.int64)
 v=COEFF[a//3]*(a%3+1)[...,None]
 p=np.cumsum(v,axis=1);r=pair_sq(p)
 return r.sum(axis=1),r[:,-1]
def exact_rows(s,stem):
 data=[];meta=[]
 for r,(start,end) in enumerate(ROWS):
  seq=s[start:end];n=count_strings(seq.tolist())[0]
  prefix=OUT/f'{stem}_row{r+1}';inp=prefix.with_suffix('.input.txt');raw=prefix.with_suffix('.bin')
  inp.write_text(f'{len(seq)} 2\n'+' '.join(map(str,seq))+'\n')
  p=subprocess.run([str(HERE/'enumerate_kgrams'),str(inp),str(raw),str(n)],text=True,capture_output=True,check=True)
  a=np.fromfile(raw,np.uint8).reshape(-1,len(seq));assert len(a)==n
  assert len(np.unique(a,axis=0))==n
  assert np.all(a[:,0]==seq[0]) and np.all(a[:,-1]==seq[-1])
  assert np.all(np.sort(a,axis=1)==np.sort(seq))
  target=np.sort(seq[:-1]*24+seq[1:]);c=a.astype(np.int64)
  assert np.all(np.sort(c[:,:-1]*24+c[:,1:],axis=1)==target)
  assert np.count_nonzero(np.all(a==seq,axis=1))==1
  st,ep=path_measures(c);obs,oep=path_measures(seq[None,:])
  assert np.all(ep==oep)
  triple_count=count_strings([tuple(seq[i:i+2]) for i in range(len(seq)-1)])[0]
  m={'row':r+1,'n':n,'trigram_cardinality':int(triple_count),'stat_observed_2E_A_B':obs[0].tolist(),
    'stat_observed':float(vals(obs)[0]),'endpoint_2R2_A_B':oep[0].tolist(),
    'exact_le':int(le_exact(st,obs[0]).sum()),'exact_equal':int(np.all(st==obs[0],axis=1).sum()),
    'mean_energy':float(vals(st).mean()),'median_energy':float(np.median(vals(st))),
    'mean_changed_positions':float(np.sum(a!=seq,axis=1).mean()),'checks':'all strings unique; all pair counts, endpoints, unigrams, energy endpoints checked',
    'enumerator':json.loads(p.stdout)}
  np.savez_compressed(prefix.with_suffix('.npz'),sequences=a,energy_pairs=st)
  raw.unlink();data.append((a,st));meta.append(m)
 return data,meta

def MC(s,rowdata,style,rng):
 n=PROTOCOL['n_monte_carlo'];draws=np.empty((n,len(s)),np.uint8)
 energies=np.empty((n,3,2),np.int64);indices=[]
 for r,(start,end) in enumerate(ROWS):
  if style=='bigram':
   a,stats=rowdata[r];ix=rng.integers(len(a),size=n);draws[:,start:end]=a[ix];energies[:,r]=stats[ix];indices.append(ix)
  else:
   for i in range(n):draws[i,start:end]=rng.permutation(s[start:end])
   energies[:,r]=path_measures(draws[:,start:end])[0]
  assert np.all(np.sort(draws[:,start:end],axis=1)==np.sort(s[start:end]))
 obs=np.stack([path_measures(s[a:b][None,:])[0][0] for a,b in ROWS])
 result={'n':n,'primary':tail(energies.sum(axis=1),obs.sum(axis=0)),
   'first_two_diagnostic':tail(energies[:,:2].sum(axis=1),obs[:2].sum(axis=0)),
   'per_row_diagnostic':[tail(energies[:,r],obs[r]) for r in range(3)],
   'distinct_joint_sequences':len(np.unique(draws,axis=0)),
   'mean_positions_changed':float(np.sum(draws!=s,axis=1).mean())}
 return result,draws,energies

def tail(a,obs):
 k=int(le_exact(a,obs).sum());return {'le':k,'n':len(a),'p_plus_one':(k+1)/(len(a)+1),
 'observed_energy':float(vals(obs)),'null_mean':float(vals(a).mean()),'null_quantiles_1_5_50_95_99':np.quantile(vals(a),[.01,.05,.5,.95,.99]).tolist()}

def implementation_checks():
 rng=np.random.default_rng(2026100129);maxerr=0.
 for i in range(1000):
  a=rng.integers(0,24,size=(1,int(rng.integers(3,40))))
  ep,p=path_measures(a);v=(a%3+1)*np.exp(1j*(a//3)*np.pi/4)
  independent=np.abs(v.cumsum(axis=1))**2
  maxerr=max(maxerr,float(abs(vals(ep)[0]-independent.sum())))
  assert np.isclose(vals(ep)[0],independent.sum(),atol=1e-9)
 # Exhaustive toy mean versus permutation expectation; permutations of indices
 # repeat equal glyph strings with equal multiplicity, appropriate here.
 import itertools
 toy=np.array([0,12,3,15,1]);a=np.array([toy[list(p)] for p in itertools.permutations(range(5))])
 e,p=path_measures(a);expected=(len(toy)+1)/6*(((toy%3+1)**2).sum()+2*vals(p[0]))
 assert np.isclose(vals(e).mean(),expected)
 return {'complex_independent_checks':1000,'max_abs_error':maxerr,'toy_exhaustive_permutations':len(a),'toy_mean_matches_formula':True}

def main():
 frozen=freeze();subprocess.run(['g++','-O3','-std=c++17',str(ROOT/'round8/enumerate_kgrams.cpp'),'-o',str(HERE/'enumerate_kgrams')],check=True)
 results={'protocol':PROTOCOL,'implementation_checks':implementation_checks(),'cases':{}}
 cases=[c for c in json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'] if c['kind']=='real']
 for ci,c in enumerate(cases):
  s=np.array(c['glyph'],np.int64);data,meta=exact_rows(s,c['id']);out={'rows':meta,'joint_bigram_cardinality':str(math.prod(m['n'] for m in meta)),
  'joint_trigram_cardinality':str(math.prod(m['trigram_cardinality'] for m in meta))}
  for si,style in enumerate(['unigram','bigram']):
   rng=np.random.default_rng(np.random.SeedSequence([PROTOCOL['seed'],ci,si]))
   summary,draws,energies=MC(s,data,style,rng);out[style]=summary
   np.savez_compressed(OUT/f'{c["id"]}_{style}_mc.npz',sequences=draws,energy_pairs=energies)
  results['cases'][c['id']]=out;dump(OUT/'summary.json',results)
  print(c['id'],json.dumps(out,indent=2),flush=True)
 if frozen!=freeze():raise AssertionError('changed protocol')
if __name__=='__main__':main()
