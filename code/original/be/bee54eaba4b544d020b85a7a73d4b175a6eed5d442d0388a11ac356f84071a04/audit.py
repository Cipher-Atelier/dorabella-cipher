"""Full replay of persisted random inputs and scores; separate arithmetic checks."""
from pathlib import Path
import json, math, hashlib
import numpy as np
import experiment as e
R=Path(__file__).resolve().parent
e.verify_protocol()
manifest=json.loads((R/'results/manifest.json').read_text())
for name,h in manifest.items():assert e.sha(R/name)==h,name
cases=json.loads((R/'data/cases.json').read_text());report=dict(cases=0,control_sequences_replayed=0,relabels_replayed=0,independent_scores=0,max_independent_error=0.,normalized_conditional_contexts=0)
records=[]
for c in cases:
    g=np.array(c['glyph']);rec=json.loads((R/'results'/f"{c['id']}.json").read_text());records.append(rec)
    model=e.fit(g[:43]);v,logs,parts=e.score_many(g,model)
    assert v[0]==rec['gain_bits'];assert logs[0].tolist()==rec['mixture_log2_probabilities']
    err=abs(float(v[0])-e.independent_score(g));assert err<1e-10
    report['independent_scores']+=1;report['max_independent_error']=max(report['max_independent_error'],err)
    if 'conditional' in rec:
        a=np.load(R/'results'/f"{c['id']}_controls.npz");rng=np.random.default_rng(c['control_seed'])
        for z in a['glyph']:
            fresh=np.r_[g[:42],e.euler_shuffle(g[42:],rng)]
            assert np.array_equal(z,fresh)
            assert np.array_equal(z[:43],g[:43]) and e.bigrams(z)==e.bigrams(g)
        cv,cl,cp=e.score_many(a['glyph'],model)
        assert np.array_equal(cv,a['gain_bits']);assert np.array_equal(cl,a['mixture_log2']);assert np.array_equal(cp,a['factorization_log2'])
        n=len(cv);ge=int(np.sum(cv>=v[0]-1e-10));assert ge==rec['conditional']['ge'] and (ge+1)/(n+1)==rec['conditional']['p_plus_one']
        report['control_sequences_replayed']+=n
        if c['kind']=='real':
            assert str(e.cardinality(g[42:]))==rec['conditional']['exact_support_size']
            # 100 selected controls per real input, independent direct-count scoring.
            for z in a['glyph'][np.linspace(0,n-1,100,dtype=int)]:
                x=e.independent_score(z);y=e.score_many(z,model)[0][0];err=abs(x-y);assert err<1e-10
                report['independent_scores']+=1;report['max_independent_error']=max(report['max_independent_error'],err)
    if 'relabel' in rec:
        a=np.load(R/'results'/f"{c['id']}_relabels.npz");rng=np.random.default_rng(c['relabel_seed']);rv=[]
        for p in a['permutations']:
            assert np.array_equal(p,rng.permutation(24));z=p[g];rv.append(e.score_many(z,e.fit(z[:43]))[0][0])
        assert np.array_equal(rv,a['gain_bits']);n=len(rv);ge=int(np.sum(np.array(rv)>=v[0]-1e-10));assert ge==rec['relabel']['ge']
        report['relabels_replayed']+=n
        # Every pair of preceding glyphs and every possible next glyph.
        for prior2 in range(24):
            for prior1 in range(24):
                gs=np.array([[prior2,prior1,nextg] for nextg in range(24)])
                for fm,ff in zip(model,e.features(gs)):
                    probs=np.ones((24,2))
                    for (l1,l2),(x,k) in zip(fm,ff):
                        probs[:,0]*=np.exp2(l1[x[:,1],x[:,2]]);probs[:,1]*=np.exp2(l2[x[:,0],x[:,1],x[:,2]])
                    assert np.allclose(probs.sum(0),1,atol=1e-13)
                    report['normalized_conditional_contexts']+=1
    report['cases']+=1
pos=[r for r in records if r['kind']=='second_order'];neg=[r for r in records if r['kind']=='first_order']
detect=lambda r:r['gain_bits']>0 and r['conditional']['p_plus_one']<=.01
s=json.loads((R/'results/summary.json').read_text());assert sum(map(detect,pos))==s['synthetic']['second_order_detected'];assert sum(map(detect,neg))==s['synthetic']['first_order_false_positives']
report['protocol_and_original_result_hashes_verified']=True
report['summary_counts_verified']=True
e.dump(R/'audit_result.json',report)
print(json.dumps(report,indent=2))
