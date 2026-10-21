import json,time,concurrent.futures
import numpy as np
from wordsearch_v4 import ROOT
from scan_v4 import Pipeline
from historical_check import cases
from validate_v3 import cases as lamb_cases
hist=[x for x in cases() if x[0]=='history_03'][0]
ls=lamb_cases();todo=[(hist[0],hist[1],hist[2],hist[3],ROOT/'results/v3/dev_history_03.json')]
for k in (6,7):
 x=ls[k];a=np.frombuffer(x['plaintext'].encode(),np.uint8).astype(np.int64)-97
 todo.append((x['id'],np.array(x['orientation']),np.array(x['arcs_zero_based']),a,ROOT/'results/v3/heldout'/f"{x['id']}.json"))
p=Pipeline();config={'restarts':64,'iterations':16000}
out=ROOT/'results/v4/development';out.mkdir(parents=True,exist_ok=True)
def work(case):
 label,o,c,a,path=case
 if (out/f'{label}_large.json').exists():return json.loads((out/f'{label}_large.json').read_text())
 bank=json.loads(path.read_text());r=p.run(o,c,bank,config,tag='v4_development_large')
 r['accuracy']=float(np.mean(np.array(r['decoded'])==a));r['baseline_accuracy']=float(np.mean(np.array(bank['decoded'])==a))
 for x in r['candidates']:x['accuracy_diagnostic']=float(np.mean(np.array(x['decoded'])==a))
 r['configuration_overrides']=config
 (out/f'{label}_large.json').write_text(json.dumps(r,indent=2))
 print(label, 'old',r['baseline_accuracy'],'new',r['accuracy'],'sec',r['seconds'],r['candidates'][0]['segmentation'],flush=True)
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rr=list(pool.map(work,todo))
