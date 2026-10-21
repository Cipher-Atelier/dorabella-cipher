"""Build a compact machine-readable summary and human research log."""
import csv,hashlib,json,platform,sys,importlib.metadata
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent

def main():
 d=ROOT/'results/v3'
 frozen=json.loads((d/'frozen_protocol.json').read_text());held=json.loads((d/'heldout/summary.json').read_text())
 fresh=json.loads((d/'fresh_null/summary.json').read_text());cached=json.loads((d/'cached/summary.json').read_text())
 checks=json.loads((d/'implementation_checks.json').read_text());pool=json.loads((d/'keypool_diagnostic.json').read_text())
 summary={'round':3,'status':'No decryption, no new mechanism established','development':frozen['development_summary'],
  'new_validation':held,'fresh_controls':fresh,'cached_controls':{k:v for k,v in cached.items() if k!='best_candidate'},
  'keypool_diagnostic':{k:v for k,v in pool.items() if k not in ['all_candidates','best','old_char_best']},'checks':checks}
 (d/'summary.json').write_text(json.dumps(summary,indent=2))
 rows=[]
 for f in sorted(d.glob('dev_history_*.json')):
  r=json.loads(f.read_text());rows.append({'set':'development','id':r['id'],'accuracy_v2':r['old_accuracy'],'accuracy_v3':r['accuracy'],'score_v3':r['best_score'],'gain':r['improvement']})
 for sub,name in [('heldout','new_validation'),('cached','cached_comparison'),('fresh_null','fresh_comparison')]:
  for f in sorted((d/sub).glob('*.json')):
   if f.name.endswith('_v2bank.json') or f.name in ['inputs.json','summary.json']:continue
   r=json.loads(f.read_text());rows.append({'set':name,'id':r['id'],'accuracy_v2':r.get('v2_accuracy',''),'accuracy_v3':r.get('accuracy',''),'score_v3':r['best_score'],'gain':r['improvement']})
 with (d/'cases.csv').open('w',newline='') as fp:
  w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 env={'python':sys.version,'platform':platform.platform(),'packages':{m:importlib.metadata.version(m) for m in ['numpy','numba','scipy','gensim','textblob']}}
 (ROOT/'environment_round3.json').write_text(json.dumps(env,indent=2));(ROOT/'requirements_round3.txt').write_text('\n'.join(f'{m}=={v}' for m,v in env['packages'].items())+'\n')
 print('Summary rows',len(rows),'new validation exact',sum(r['new']==1 for r in held['cases']),'old exact',sum(r['old']==1 for r in held['cases']))
if __name__=='__main__':main()
