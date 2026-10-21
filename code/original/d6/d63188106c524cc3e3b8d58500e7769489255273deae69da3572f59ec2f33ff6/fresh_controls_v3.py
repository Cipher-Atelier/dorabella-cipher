"""39 fresh permutations; same frozen complete v2+v3 pipeline on each.
Fixed n=39 for this additional computational check; no stopping on p-value.
The underlying family and statistics remain historically exploratory.
"""
import json,hashlib,time,concurrent.futures
import numpy as np
from audit import load_cipher
from scan_v2 import scan_one
from scan_v3 import Pipeline
from wordscore_v3 import ROOT

def main():
 frozen=json.loads((ROOT/'results/v3/frozen_protocol.json').read_text())
 for f,h in frozen['sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
 out=ROOT/'results/v3/fresh_null';out.mkdir(exist_ok=True)
 _,_,o,c=load_cipher();rng=np.random.default_rng(2026092504);cases=[]
 for i in range(39):
  idx=rng.permutation(len(o));cases.append({'id':f'fresh_{i:02d}','orientation':o[idx].tolist(),'arcs_zero_based':c[idx].tolist()})
 manifest={'n':39,'seed':2026092504,'stopping_rule':'fixed n, no sequential significance stopping','cases':cases}
 path=out/'inputs.json'
 if path.exists():assert json.loads(path.read_text())==manifest
 else:path.write_text(json.dumps(manifest,indent=2))
 p=Pipeline()
 def work(case):
  dest=out/f"{case['id']}.json"
  if dest.exists():return json.loads(dest.read_text())
  a=np.array(case['orientation']);b=np.array(case['arcs_zero_based']);t=time.monotonic()
  bank,_=scan_one(a,b,p.lp,p.p1);bank['id']=case['id']
  (out/f"{case['id']}_v2bank.json").write_text(json.dumps(bank,indent=2))
  r=p.run(a,b,bank);r['full_seconds']=time.monotonic()-t
  dest.write_text(json.dumps(r,indent=2));print(r['id'],r['best_score'],round(r['full_seconds'],1),flush=True);return r
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(work,cases))
 real=json.loads((ROOT/'results/v3/cached/dorabella.json').read_text())
 summ={'n':39,'all_proposal_searches_computed_fresh':True,'comparisons':{}}
 for key in ['best_score','identity_score','improvement']:
  vals=np.array([r[key] for r in rows]);k=int(np.sum(vals>=real[key]-1e-10))
  summ['comparisons'][key]={'real':real[key],'null_mean':float(vals.mean()),'exceedances':k,'p_add_one':(k+1)/40}
 (out/'summary.json').write_text(json.dumps(summ,indent=2));print('SUMMARY',json.dumps(summ),flush=True)
if __name__=='__main__':main()
