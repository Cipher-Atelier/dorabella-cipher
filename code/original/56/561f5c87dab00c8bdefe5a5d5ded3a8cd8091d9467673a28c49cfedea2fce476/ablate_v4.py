"""Development-only ablation: remove word-sized moves, keep word-aware
acceptance, same restart and proposal counts. Not a timing-matched test.
"""
import json,time
import numpy as np
from wordscore_v3 import ROOT
from scan_v4 import Pipeline

def main():
 out=ROOT/'results/v4';frozen=json.loads((out/'frozen_protocol.json').read_text())
 cases=json.loads((out/'inputs.json').read_text())['cases'];cases=[c for c in cases if c['id'] in ('history_03','lamb_06','lamb_07')]
 p=Pipeline();conf=dict(frozen['config'],word_move_probability=0.)
 for case in cases:
  path=out/'development'/f"{case['id']}_letter_moves_only.json"
  if path.exists():continue
  b=json.loads((ROOT/case['cached_v3']).read_text())
  r=p.run(np.array(case['orientation']),np.array(case['arcs_zero_based']),b,conf,tag=frozen['seed_namespace'])
  a=np.frombuffer(case['plaintext'].encode(),np.uint8).astype(np.int64)-97
  r['accuracy_diagnostic']=float(np.mean(np.array(r['decoded'])==a))
  r['development_only_not_independent']=True;r['word_move_probability']=0.
  path.write_text(json.dumps(r,indent=2));print(case['id'],r['accuracy_diagnostic'],r['best_score'],r['seconds'],flush=True)
if __name__=='__main__':main()
