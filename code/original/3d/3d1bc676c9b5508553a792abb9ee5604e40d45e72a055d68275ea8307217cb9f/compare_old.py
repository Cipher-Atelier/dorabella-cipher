"""Untouched round-1 pipeline, evaluated on the NEW held-out round-2 cases.
This is a paired method comparison, not a new tuning step.
"""
from pathlib import Path
import json,time
import numpy as np
from scan_v2 import new_positives
from scan import scan_one
from language import build_model
out=Path('results/v2/old_on_new');out.mkdir(exist_ok=True);lp,p1=build_model()
for label,o,c,truth,info in new_positives():
    path=out/f'{label}.json'
    if path.exists():continue
    t=time.monotonic();r=scan_one(o,c,lp,p1)
    r['accuracy']=float(np.mean(np.array(r['decoded'])==truth));r['id']=label;r['seconds']=time.monotonic()-t
    path.write_text(json.dumps(r,indent=2));print(label,r['accuracy'],r['seconds'],flush=True)
rows=[json.loads((out/f'{case[0]}.json').read_text()) for case in new_positives()]
summ={'cases':len(rows),'mean_accuracy':float(np.mean([r['accuracy'] for r in rows])),
      'at_least_90_percent':sum(r['accuracy']>=.9 for r in rows)}
(out/'summary.json').write_text(json.dumps(summ,indent=2));print(summ,flush=True)
