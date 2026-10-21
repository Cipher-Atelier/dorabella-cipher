"""Implementation checks independent of statistical interpretations."""
import json, hashlib, importlib.metadata, platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from audit import load_cipher, pairings, mi
from automata import canonical, definitions, transform, inverse
from language import build_model, solve, stable_seed, score_key, affected_windows, delta_swap
ROOT=Path(__file__).resolve().parent

def main():
    _,rows,o,c=load_cipher();logp,p1=build_model();seq=canonical(3*o+c);rng=np.random.default_rng(8871)
    definitions_checked=0
    for rule in definitions():
        z=transform(o,c,rule);oo,cc=inverse(z,rule)
        assert np.array_equal(oo,o) and np.array_equal(cc,c)
        assert np.array_equal((z//3)%4,o%4)
        definitions_checked+=1
    assert definitions_checked==672
    assert len(list(pairings(list(range(8)))))==105
    key=rng.permutation(26).astype(np.int64)
    where,lens=affected_windows(seq,int(seq.max())+1)
    max_err=0.
    for _ in range(1000):
        i=int(rng.integers(seq.max()+1));j=int(rng.integers(26))
        if i==j:continue
        delta=delta_swap(seq,key,logp,where,lens,i,j)
        old=score_key(seq,key,logp);key[i],key[j]=key[j],key[i]
        actual=score_key(seq,key,logp)-old
        max_err=max(max_err,abs(delta-actual));assert abs(delta-actual)<1e-8
    def worker(_):
        return solve(seq,logp,p1,2,3000,stable_seed(seq,'thread_check'))
    ref=worker(0)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(worker,range(8)):
            assert abs(result[0]-ref[0])<1e-10
            assert np.array_equal(result[1],ref[1])
    from scan import scan_one
    recomputed=scan_one(o,c,logp,p1)
    summary=json.loads((ROOT/'results/scan_summary.json').read_text())
    for metric in ['best_score','identity_score','improvement']:
        assert abs(recomputed[metric]-summary['observed'][metric])<1e-10
    a=json.loads((ROOT/'results/audit.json').read_text())
    d=np.load(ROOT/'results/audit_null_arrays.npz')
    assert np.sum(d['shuffle'][:,0]>=41)==a['tests']['shuffle_fixed_axis']['hits']
    assert np.sum(d['shuffle'][:,1]>=41)==a['tests']['shuffle_best_of_105_pairings']['hits']
    assert np.sum(d['conditional'][:,0]>=27)==a['tests']['polarity_within_base_opposites']['hits']
    records=[json.loads(s) for s in (ROOT/'results/scan_records.jsonl').read_text().splitlines()]
    assert len(records)==108 and len(set(r['id'] for r in records))==108
    out={'round_trip_rules_checked':definitions_checked,'score_delta_checks':1000,
         'max_score_delta_error':max_err,'thread_determinism_checks':8,
         'full_Dorabella_scan_reproduced':True,'scan_records_unique':108,
         'stored_null_arrays_match_summary':True,'status':'passed'}
    (ROOT/'results/implementation_checks.json').write_text(json.dumps(out,indent=2))
    env={'python':platform.python_version(),'packages':{p:importlib.metadata.version(p) for p in ['numpy','scipy','numba','gensim']}}
    (ROOT/'environment.json').write_text(json.dumps(env,indent=2))
    (ROOT/'requirements.txt').write_text('\n'.join(f'{k}=={v}' for k,v in env['packages'].items())+'\n')
    print(json.dumps(out,indent=2));print(env)
if __name__=='__main__':main()
