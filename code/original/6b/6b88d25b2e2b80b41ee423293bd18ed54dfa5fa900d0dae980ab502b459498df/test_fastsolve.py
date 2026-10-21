import json,time
from pathlib import Path
import numpy as np
from automata import canonical
from audit import load_cipher
from language import build_model,score_key,solve,stable_seed
from fastsolve import prepare,encode_windows,delta_cached,apply_swap,solve_fast
p,p1=build_model();_,_,o,c=load_cipher();s=canonical(3*o+c)
rng=np.random.default_rng(20260925);errors=[];cases=[]
for n in range(20):
    seq=canonical(rng.integers(0,24,87))
    key=rng.permutation(26);w,d,l=prepare(seq);co=encode_windows(seq,key)
    for it in range(100):
        i=int(rng.integers(seq.max()+1));j=int(rng.integers(26))
        before=score_key(seq,key,p);delta=delta_cached(co,key,p,w,d,l,i,j)
        apply_swap(co,key,w,d,l,i,j)
        exact=score_key(seq,key,p)
        errors.append(abs(exact-before-delta))
        assert np.array_equal(co,encode_windows(seq,key))
        assert errors[-1]<1e-9
for seed in range(5):
    a,ka=solve(s,p,p1,4,4000,seed);b,kb=solve_fast(s,p,p1,4,4000,seed)
    cases.append({'seed':seed,'original':a,'cached':b,'keys_equal':bool(np.array_equal(ka,kb))})
    assert abs(a-b)<1e-8
bench={}
for name,f in [('original',solve),('cached',solve_fast)]:
    t=time.monotonic();a,k=f(s,p,p1,128,20000,42);bench[name]={'seconds':time.monotonic()-t,'score':a/84}
print(json.dumps({'max_delta_error':max(errors),'cached_code_updates':len(errors),'same_seed_cases':cases,'benchmark':bench},indent=2))
Path('results/fastsolve_checks.json').write_text(json.dumps({'max_delta_error':max(errors),'cached_code_updates':len(errors),'same_seed_cases':cases,'benchmark':bench},indent=2))
