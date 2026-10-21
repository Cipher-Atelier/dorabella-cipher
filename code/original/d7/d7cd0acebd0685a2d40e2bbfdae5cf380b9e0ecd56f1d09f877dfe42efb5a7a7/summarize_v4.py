"""Build summaries only from saved completed records; never extrapolate counts."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
from scipy.stats import beta
from wordscore_v3 import ROOT

def proportion_ci(k,n):
 return [0. if k==0 else float(beta.ppf(.025,k,n-k+1)),
         1. if k==n else float(beta.ppf(.975,k+1,n-k))]

def metrics(rows, field='accuracy'):
 vals=np.array([r[field] for r in rows]);return {'n':len(vals),'mean_accuracy':float(vals.mean()),
     'at_least_90':int(np.sum(vals>=.9)),'exact':int(np.sum(vals>=1.-1e-12)),
     'minimum':float(vals.min()),'ge90_binomial_interval_descriptive':proportion_ci(int(np.sum(vals>=.9)),len(vals))}

def main():
 out=ROOT/'results/v4';manifest=json.loads((out/'inputs.json').read_text())['cases'];rows=[];missing=[]
 for case in manifest:
  p=out/'cases'/f"{case['id']}.json"
  if not p.exists():missing.append(case['id']);continue
  r=json.loads(p.read_text());rows.append(r)
 if missing:
  print('NOT COMPLETE:',len(rows),'of',len(manifest),'missing',missing)
  return
 summary={'date':'2026-09-26','completed':len(rows),'samples':{},'null_comparisons':{},'cases':[]}
 for group in ('regression','heldout'):
  group_rows=[r for r in rows if r['group']==group]
  summary['samples'][group]={'new':metrics(group_rows),'old':metrics(group_rows,'baseline_accuracy'),
      'true_pattern_wins':sum(r['true_pattern_won'] for r in group_rows),
      'improved':sum(r['accuracy']>r['baseline_accuracy']+1e-12 for r in group_rows),
      'worsened':sum(r['accuracy']<r['baseline_accuracy']-1e-12 for r in group_rows)}
 real=next(r for r in rows if r['id']=='dorabella');nulls=[r for r in rows if r['group']=='null']
 assert len(nulls)==39
 for key in ('best_score','identity_score','improvement'):
  vals=np.array([r[key] for r in nulls]);k=int(np.sum(vals>=real[key]-1e-10))
  summary['null_comparisons'][key]={'dorabella':real[key],'mean_control':float(vals.mean()),
     'sd_control':float(vals.std(ddof=1)),'exceedances':k,'n':len(vals),
     'p_add_one':(k+1)/(len(vals)+1),'binomial_ci_for_exceedance_fraction':proportion_ci(k,len(vals))}
 summary['dorabella']={k:real[k] for k in ['best_score','identity_score','improvement','best_index','identity_index','decoded']}
 summary['dorabella']['text']=''.join(chr(x+65) for x in real['decoded'])
 summary['dorabella']['segmentation']=real['candidates'][0]['segmentation']
 summary['dorabella']['previous_v3_score']=real['baseline_score']
 summary['candidate_count']=sum(r['finalist_count'] for r in rows)
 summary['annealing_score_evaluations']=summary['candidate_count']*64*16000
 summary['candidate_statistics']=[]
 for group in ('heldout','null','real'):
  for r in [r for r in rows if r['group']==group]:
   b=r['candidates'][0];summary['candidate_statistics'].append(dict(id=r['id'],group=group,
       char_score=b['char_score'],word_score=b['word_score'],combined=b['score']))
 for r in rows:
  summary['cases'].append({k:r[k] for k in ('id','group','best_score','identity_score','improvement','accuracy','baseline_accuracy','true_pattern_won','full_seconds') if k in r})
 for label in ('history_03','lamb_06','lamb_07'):
  p=out/'development'/f'{label}_letter_moves_only.json'
  if p.exists():
   r=json.loads(p.read_text());summary.setdefault('development_ablation',[]).append(dict(id=label,letter_moves_accuracy=r['accuracy_diagnostic'],word_moves_accuracy=next(r['accuracy'] for r in rows if r['id']==label)))
 (out/'summary.json').write_text(json.dumps(summary,indent=2))
 print(json.dumps({k:v for k,v in summary.items() if k not in ('cases','candidate_statistics')},indent=2))
if __name__=='__main__':main()
