"""Oracle diagnosis only. The true rule is supplied; not blind recovery.
No changes to scanning, training, or hypothesis selection are made here.
"""
from pathlib import Path
import json
import numpy as np
from historical_check import cases
from automata import canonical,transform,variants
from language import build_model,stable_seed,score_key
from fastsolve import solve_fast
out=Path('results/v2/historical');lp,p1=build_model();rows=[]
for label,o,c,truth,info in cases():
 source=out/f'{label}.json'
 if not source.exists():continue
 row=json.loads(source.read_text());correct=canonical(transform(o,c,info['generating_rule']))
 # Three independent oracle budgets equal to the three pipeline stages.
 sc=-1e100;key=None
 for stage,restarts,iterations in [('screen',8,16000),('middle',32,20000),('final',128,20000)]:
  s,k=solve_fast(correct,lp,p1,restarts,iterations,stable_seed(correct,'v2_'+stage))
  if s>sc:sc=s;key=k
 cand=variants(o,c);idx=next(j for j,(s,_) in enumerate(cand) if np.array_equal(s,correct))
 r={'id':label,'blind_accuracy':row['accuracy'],'oracle_accuracy':float(np.mean(key[correct]==truth)),
  'true_plaintext_score':float(score_key(truth,np.arange(26),lp))/84,
  'blind_winning_score':row['best_score'],'oracle_best_score':float(sc)/84,
  'oracle_plaintext_accuracy_is_not_blind_accuracy':True,
  'true_pattern_survived_all_stages':all(idx in st['searched_indices'] for st in row['stages']),
  'true_pattern_ranks':[int(1+np.sum(np.array(st['all_best_scores'])>st['all_best_scores'][idx]+1e-10)) for st in row['stages']]}
 rows.append(r);print(r,flush=True)
(out/'oracle_diagnosis.json').write_text(json.dumps({'cases':rows,'caution':'True transformations are supplied to this diagnostic. This is NOT another independent accuracy estimate.'},indent=2))
