"""Diagnose screening false negatives using the known rules of positive controls.
This is an oracle diagnostic, not an additional Dorabella attack or validation score.
"""
from pathlib import Path
import json
import numpy as np
from automata import canonical, transform, variants
from language import build_model, solve, stable_seed
from scan import create_positives
ROOT=Path(__file__).resolve().parent

def main():
    lp,p1=build_model();rows=[]
    records={r['id']:r for r in map(json.loads,(ROOT/'results/scan_records.jsonl').read_text().splitlines())}
    for label,o,c,truth,info in create_positives(8,np.random.default_rng(20260928)):
        correct=canonical(transform(o,c,info['generating_rule']))
        sc,key=solve(correct,lp,p1,128,20000,stable_seed(correct,'refine_v1'))
        r={'id':label,'full_pipeline_accuracy':records[label]['decipherment_accuracy'],
           'oracle_given_correct_rule_accuracy':float(np.mean(key[correct]==truth)),
           'oracle_given_correct_rule_score':float(sc)/84}
        scores=[];idx=None
        for i,(s,_) in enumerate(variants(o,c)):
            a,_=solve(s,lp,p1,2,4000,stable_seed(s,'screen_v1'));scores.append(a)
            if np.array_equal(s,correct):idx=i
        assert idx is not None
        r['correct_pattern_screen_rank']=int(1+np.sum(np.array(scores)>scores[idx]+1e-10))
        rows.append(r);print(r,flush=True)
    (ROOT/'results/screening_diagnostic.json').write_text(json.dumps({'cases':rows,
        'oracle_mean_accuracy':float(np.mean([r['oracle_given_correct_rule_accuracy'] for r in rows])),
        'caution':'True transformation is supplied to the oracle. Do not report its accuracy as full blind-search accuracy.'},indent=2))
if __name__=='__main__':main()
