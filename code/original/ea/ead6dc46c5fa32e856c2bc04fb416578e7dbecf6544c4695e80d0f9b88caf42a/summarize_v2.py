"""Summarize only COMPLETE v2 runs; no interpolation or extrapolation."""
from pathlib import Path
import json,csv,hashlib,platform,importlib.metadata
import numpy as np
from scipy.stats import beta
ROOT=Path(__file__).resolve().parent;P=ROOT/'results/v2'

def load(name):return json.loads((P/name).read_text())
def exact_ci(k,n):
 return [float(beta.ppf(.025,k,n-k+1)) if k else 0.,float(beta.ppf(.975,k+1,n-k)) if k<n else 1.]

def main():
 frozen=json.loads((ROOT/'results/v2_frozen_protocol.json').read_text())
 for name,h in frozen['sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name+' changed after freeze'
 obs=load('dorabella.json');null=[load(f'null2_{i:03d}.json') for i in range(99)]
 news=[load(f'heldout_{i:02d}.json') for i in range(16)]
 old=[load(f'old_on_new/heldout_{i:02d}.json') for i in range(16)]
 hist=[load(f'historical/history_{i:02d}.json') for i in range(8)]
 neg={}
 for m in ('identity_score','best_score','improvement'):
  vals=np.array([r[m] for r in null]);k=int(np.sum(vals>=obs[m]-1e-12))
  neg[m]={'observed':obs[m],'null_n':99,'null_mean':float(vals.mean()),'null_sd':float(vals.std(ddof=1)),
   'exceedances':k,'p_plus_one':(k+1)/100,'binomial_95_interval_for_tail_probability':exact_ci(k,99),
   'null_min':float(vals.min()),'null_max':float(vals.max())}
 def acc(rows):
  vals=np.array([r['accuracy'] for r in rows]);k=int(np.sum(vals>=.9))
  return {'n':len(rows),'mean_accuracy':float(vals.mean()),'min_accuracy':float(vals.min()),
   'successes_at_90':k,'binomial_success_95_interval':exact_ci(k,len(rows)),
   'best_score_min':min(r['best_score'] for r in rows),'best_score_max':max(r['best_score'] for r in rows),
   'note':'Success interval presumes independent representative Bernoulli trials; historical convenience sample does not establish that.'}
 summary={'frozen_protocol_sha256':frozen['sha256']['results/v2_protocol.json'],
  'development':load('development_summary.json'),'heldout_news_old':acc(old),'heldout_news_new':acc(news),
  'heldout_news_exact_generating_equality_pattern_selected':sum(r['best_index']==r['true_pattern_index'] for r in news),
  'historical_convenience_sample':acc(hist),'null_comparison':neg,
  'dorabella':{k:obs[k] for k in ['best_score','identity_score','improvement','best_rule','candidate_text','distinct_patterns']},
  'paired_accuracy': [{'id':n['id'],'old_accuracy':o['accuracy'],'new_accuracy':n['accuracy']} for o,n in zip(old,news)],
  'historical_cases':[{'id':r['id'],'accuracy':r['accuracy'],'true_score':r['true_score'],'best_score':r['best_score']} for r in hist],
  'historical_oracle_diagnosis':load('historical/oracle_diagnosis.json'),
  'completed_case_records':8+16+1+99+16+8,
  'limitations':['Two-state polarity-XOR family only, not all finite state machines',
   'Simulated annealing is not a proof of a global optimum',
   'Modern news language model is imperfect for 19th-century letters',
   'Historical letter openings form a small nonrandom related sample',
   'News recovery is NOT probability of solving Dorabella',
   'Shuffled glyph null is NOT the null of every possible historical cipher',
   'Geometry and candidate family were chosen exploratorily in previous rounds',
   'Transcription ambiguity remains; no new blind glyph annotation has been performed']}
 (ROOT/'results/round2_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 with (ROOT/'results/round2_cases.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['id','group','best_score','identity_score','improvement','accuracy'])
  for group,rows in [('development',[load(f'positive_{i:02d}.json') for i in range(8)]),('news_new',news),('news_old',old),('dorabella',[obs]),('null',null),('historical',hist)]:
   for r in rows:w.writerow([r['id'],group,r['best_score'],r['identity_score'],r['improvement'],r.get('accuracy','')])
 env={'python':platform.python_version(),'packages':{k:importlib.metadata.version(k) for k in ('numpy','numba','scipy','gensim')}}
 (ROOT/'environment_round2.json').write_text(json.dumps(env,indent=2))
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
