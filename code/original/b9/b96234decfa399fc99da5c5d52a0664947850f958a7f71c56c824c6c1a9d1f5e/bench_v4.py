import json,time,numpy as np
from wordsearch_v4 import WordSearch,CONFIG,ROOT
from automata import variants
from historical_check import cases
p=WordSearch();
case=list(cases())[3];label,o,c,a,info=case
bank=json.loads((ROOT/'results/v3/dev_history_03.json').read_text());vv=variants(o,c)
# First compile on a small, non-diagnostic input, then measure real runs.
x=bank['candidates'][0];seq=vv[x['index']][0]
p.run(seq,x['decoded'],{'restarts':1,'iterations':1},tag='compile')
print('ready',len(p.children),flush=True)
rows=[]
for x in bank['candidates']:
 r=p.run(vv[x['index']][0],x['decoded'],{'restarts':8,'iterations':6000},tag='development_v4a')
 r.update(index=x['index'],accuracy=float(np.mean(np.array(r['decoded'])==a)))
 rows.append(r);print(label,x['index'],r['accuracy'],r['score'],r['seconds'],r['segmentation'],flush=True)
(ROOT/'results/v4').mkdir(exist_ok=True)
(ROOT/'results/v4/initial_development_history03.json').write_text(json.dumps(rows,indent=2))
