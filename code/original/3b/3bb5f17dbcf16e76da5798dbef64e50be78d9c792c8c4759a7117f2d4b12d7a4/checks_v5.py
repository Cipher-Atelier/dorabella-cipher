"""Technical checks for the new, finite affine-orientation experiment.
No oracle-assisted result is counted as an independent decipherment.
"""
import json, platform, importlib.metadata, csv
import numpy as np
from numba import njit
from model_v5 import ROOT,OUT,LETTER,ALPHABET,load_model,sha
from affine_v5 import rules,decode,encode,evaluate
from wordpolish_v3 import char_score,fast_word
from audit import tail

@njit(cache=True)
def test_inverse(rs,z):
    for rule in rs:
        encrypted=encode(z,rule)
        restored=decode(encrypted//3,encrypted%3,rule)
        if not np.array_equal(z,restored):raise ValueError('inverse failed')
        if not np.array_equal(encrypted%3,z%3):raise ValueError('arcs changed')

@njit(cache=True)
def all_outputs(o,c,rs):
    out=np.empty((len(rs),len(o)),np.uint8)
    for i in range(len(rs)):out[i]=decode(o,c,rs[i])
    return out

def main():
    model=load_model();lp,scorer,children,vals=model;rs=rules();rng=np.random.default_rng(2026092607)
    z=rng.integers(0,24,87);test_inverse(rs,z)
    # Independent Python definition does not call the compiled transform.
    max_word_error=0.;max_score_error=0.
    for _ in range(200):
        o=rng.integers(0,8,87);c=rng.integers(0,3,87);rr=rs[int(rng.integers(len(rs)))];out=[]
        mode,a,b,k,h,previous=map(int,rr)
        for t,(oi,ci) in enumerate(zip(o,c)):
            ri=(a*int(oi)+b*previous+k*t+h)%8;out.append(3*ri+int(ci));previous=int(oi) if mode==0 else ri
        assert np.array_equal(decode(o,c,rr),out)
        text=LETTER[np.array(out)];s=''.join(chr(int(v)+97) for v in text)
        max_word_error=max(max_word_error,abs(scorer.score(s)-fast_word(text,children,vals)))
    frozen=json.loads((OUT/'frozen_protocol.json').read_text())
    for path,expected in frozen['hashes'].items():assert sha(ROOT/path)==expected,path
    assert scorer.metadata==frozen['lexicon']
    cases=json.loads((OUT/'inputs.json').read_text())['cases'];records=[];ncandidates=0;accuracy_detail=[]
    for case in cases:
        rec=json.loads((OUT/'records'/f"{case['id']}.json").read_text());records.append(rec)
        o=np.array(case['orientation']);c=np.array(case['arcs'])
        assert rec['rules_evaluated']==32768
        for candidate in rec['top_candidates']:
            r=rs[candidate['rule_index']];z=decode(o,c,r);text=LETTER[z]
            s=''.join(chr(int(v)+97) for v in text)
            assert s==candidate['plaintext']
            assert np.array_equal(encode(z,r),3*o+c)
            cs=char_score(text,lp);ws=fast_word(text,children,vals)
            error=abs(cs+.5*ws-candidate['score']);assert error<1e-9
            max_score_error=max(error,max_score_error);ncandidates+=1
        assert rec['best_score']==max(q['score'] for q in rec['top_candidates'])
        if case['kind']=='positive':
            truth=case['plaintext'];zz=np.array([ALPHABET.index(ch.upper()) for ch in truth]);r=np.array(case['generating_rule'])
            assert np.array_equal(encode(zz,r),3*o+c)
            errors=[i+1 for i,(a,b) in enumerate(zip(truth,rec['best_text'])) if a!=b]
            assert abs(rec['accuracy']-(87-len(errors))/87)<1e-12
            accuracy_detail.append(dict(id=case['id'],errors=errors))
    repeats=[]
    for name in ('hauer_real','hart_real','hauer_null_000','hart_null_000'):
        case=next(x for x in cases if x['id']==name);o=np.array(case['orientation']);c=np.array(case['arcs'])
        s=evaluate(o,c,rs,lp,children,vals);rec=next(x for x in records if x['id']==name)
        assert abs(float(s.max())-rec['best_score'])<1e-12
        out=all_outputs(o,c,rs)
        info=dict(id=name,best_score_exact_match=True,distinct_plaintexts=len(np.unique(out,axis=0)))
        if case['kind']=='real':
            old=np.load(OUT/f'{name}_all_scores.npz')['scores'];assert np.array_equal(s,old)
            info['all_32768_scores_bitwise_identical']=True
        repeats.append(info)
    summary=json.loads((OUT/'summary.json').read_text());assert len(records)==232==summary['n_completed']
    byid={x['id']:x for x in records}
    both=[max(byid[f'hauer_null_{i:03d}']['best_score'],byid[f'hart_null_{i:03d}']['best_score']) for i in range(99)]
    assert tail(np.array(both),max(byid['hauer_real']['best_score'],byid['hart_real']['best_score']))==summary['max_over_both_transcriptions']
    geo=json.loads((OUT/'geometry.json').read_text());null=np.load(OUT/'geometry_nulls.npz')
    for name,v in geo['variants'].items():
        assert tail(null['variant_'+name][:,0],v['observed']['same_axis'])==v['tests']['fixed_axes']
        assert tail(null['variant_'+name][:,1],v['observed']['same_axis'])==v['tests']['best_of105_pairings']
    environment=dict(python=platform.python_version(),packages={p:importlib.metadata.version(p) for p in ('numpy','numba','scipy','gensim','textblob')})
    (ROOT/'environment_round5.json').write_text(json.dumps(environment,indent=2))
    result=dict(all_rules_inverse_and_arc_preserving=32768,independent_python_transforms=200,
          dictionary_score_max_error=max_word_error,final_candidate_score_max_error=max_score_error,
          checked_records=len(records),checked_final_candidates=ncandidates,full_search_repeats=repeats,
          frozen_hashes_match=True,sensitivity_error_positions=accuracy_detail,
          all_sensitive_errors_only_first_position=all(x['errors'] in ([],[1]) for x in accuracy_detail),
          evaluated_rule_definitions_main_series=len(records)*len(rs),
          note='32768 definitions include equivalent outputs; no heuristic pruning in this finite family')
    (OUT/'implementation_checks.json').write_text(json.dumps(result,indent=2))
    cols=['id','kind','transcription','permutation_id','best_score','best_static_score','improvement','raw_notebook_score','accuracy','exact_recovery','generating_rule_rank','rules_evaluated','seconds','best_text']
    with (OUT/'results.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(records)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
