"""Apply frozen v3 to ALL cached v2 searches, without recomputing proposals."""
import hashlib,json
from pathlib import Path
import numpy as np
from scan_v3 import Pipeline
from wordscore_v3 import ROOT

def main():
 out=ROOT/'results/v3/cached';out.mkdir(exist_ok=True)
 frozen=json.loads((ROOT/'results/v3/frozen_protocol.json').read_text())
 for f,h in frozen['sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
 p=Pipeline();rows=[]
 for inp in ['dorabella_inputs.json','null_inputs.json']:
  for case in json.loads((ROOT/'results/v2'/inp).read_text()):
   src=ROOT/'results/v2'/f"{case['id']}.json";path=out/f"{case['id']}.json"
   if path.exists():r=json.loads(path.read_text())
   else:
    bank=json.loads(src.read_text());r=p.run(np.array(case['orientation']),np.array(case['arcs_zero_based']),bank)
    r['cached_proposal_source']=str(src.relative_to(ROOT));r['cached_proposal_sha256']=hashlib.sha256(src.read_bytes()).hexdigest()
    path.write_text(json.dumps(r,indent=2))
   rows.append(r)
   if len(rows)%10==0 or len(rows)==1:print('Done',len(rows),case['id'],flush=True)
 real=rows[0];null=rows[1:];assert len(null)==99
 summary={'n_controls':99,'proposal_banks_reused_not_recomputed':True,'all_word_refinements_new':True,
  'real':{k:real[k] for k in ['best_score','identity_score','improvement','best_index','identity_index']},
  'comparisons':{}}
 for k in ['best_score','identity_score','improvement']:
  vals=np.array([r[k] for r in null]);n=int(np.sum(vals>=real[k]-1e-10))
  summary['comparisons'][k]={'real':real[k],'null_mean':float(vals.mean()),'exceedances':n,'p_add_one':(n+1)/100}
 summary['best_candidate']=real['candidates'][0]
 (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary['comparisons'],indent=2))
 print('Candidate (NOT decryption)',summary['best_candidate']['segmentation_for_diagnostics_only'])
if __name__=='__main__':main()
