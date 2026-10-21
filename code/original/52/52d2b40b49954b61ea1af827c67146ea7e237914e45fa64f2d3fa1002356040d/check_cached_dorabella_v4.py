"""Recompute old, unchanged stages rather than trusting only their hashes."""
import json,time
import numpy as np
from audit import load_cipher
from wordscore_v3 import ROOT
from scan_v3 import Pipeline
from scan_v2 import scan_one

p=Pipeline();_,_,o,c=load_cipher();t=time.monotonic()
bank,_=scan_one(o,c,p.lp,p.p1);bank['id']='dorabella';fresh=p.run(o,c,bank)
old=json.loads((ROOT/'results/v3/cached/dorabella.json').read_text())
for k in ['best_score','identity_score','improvement','best_index','identity_index','decoded']:
 assert old[k]==fresh[k],(k,old[k],fresh[k])
for x,y in zip(old['candidates'],fresh['candidates']):
 for k in ['index','rule','combined_score','decoded','trace','letter_permutation']:
  assert x[k]==y[k],k
out={'old_v2_and_v3_fully_recomputed':True,'all_v3_candidate_texts_scores_and_traces_identical':True,'seconds':time.monotonic()-t}
(ROOT/'results/v4/cached_stages_verified.json').write_text(json.dumps(out,indent=2));print(out)
