from pathlib import Path
import json
import numpy as np
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/v7/noisy'
def main():
 cases=json.loads((OUT/'inputs.json').read_text())['cases'];records={c['id']:json.loads((OUT/'records'/(c['id']+'.json')).read_text()) for c in cases}
 from wordsearch_v4 import WordSearch
 from wordpolish_v3 import char_score
 engine=WordSearch()
 diagnostics=[]
 for c in cases:
  if c['kind']=='positive':
   rr=records[c['id']];txt=np.array([ord(v)-97 for v in c['plaintext']]);truth_score=float(char_score(txt,engine.lp)+.5*engine.scorer.score(txt)-4*c['n_errors']/87)
   diagnostics.append({'id':c['id'],'truth_penalized_score':truth_score,'selected_score':rr['best']['score'],'accuracy':rr['accuracy'],'wrong_selected_outranks_truth':rr['accuracy']<1 and rr['best']['score']>truth_score+1e-10,'search_failed_to_reach_truth_score':rr['best']['score']<truth_score-1e-10})
 result={'truth_diagnostics':diagnostics,'records':len(records),'positive_texts':12,'positive_records':36,'groups':{},'real':{}}
 for e in (0,2,4):
  cc=[c for c in cases if c['kind']=='positive' and c['n_errors']==e];rr=[records[c['id']] for c in cc]
  b=np.array([r['baseline_accuracy'] for r in rr]);n=np.array([r['accuracy'] for r in rr])
  result['groups'][str(e)]={'n':len(rr),'baseline_mean':float(b.mean()),'new_mean':float(n.mean()),'baseline_ge90':int(np.sum(b>=.9)),'new_ge90':int(np.sum(n>=.9)),'baseline_exact':int(np.sum(b==1.)),'new_exact':int(np.sum(n==1.)),'new_min':float(n.min()),'improved':int(np.sum(n>b+1e-12)),'worsened':int(np.sum(n<b-1e-12)),'changed_glyphs_cases':sum(r['best']['edits']>0 for r in rr),'mean_proposed_edits':float(np.mean([r['best']['edits'] for r in rr])), 'exact_corrected_cipher':sum(np.array_equal(r['best']['corrected_glyphs'],c['true_glyph']) for c,r in zip(cc,rr)), 'records':[{'id':r['id'],'baseline':r['baseline_accuracy'],'new':r['accuracy'],'edits':r['best']['edits']} for r in rr]}
 for name in ('hauer_real','hart_real'):
  r=records[name];ns=[records[c['id']] for c in cases if c['kind']=='null' and c['source']==name];values=[x['best']['score'] for x in ns];delta=[x['best']['score']-x['baseline']['score'] for x in ns];gain=r['best']['score']-r['baseline']['score'];k=sum(v>=r['best']['score']-1e-12 for v in values)
  result['real'][name]={'score':r['best']['score'],'baseline_score':r['baseline']['score'],'gain':gain,'best_zero_edit_score':max(x['score'] for x in r['frontier'] if x['edits']==0),'gain_over_best_zero':r['best']['score']-max(x['score'] for x in r['frontier'] if x['edits']==0),'edits':r['best']['edits'],'text':r['best']['text'],'segmentation':r['best']['segmentation'],'corrections':r['best']['corrections'],'null_ge':k,'null_n':len(ns),'p_plus_one':(k+1)/(len(ns)+1),'null_mean':float(np.mean(values)),'null_gain_mean':float(np.mean(delta)),'null_gain_ge':sum(v>=gain-1e-12 for v in delta)}
 actual=max(records[n]['best']['score'] for n in ('hauer_real','hart_real'));combined=[max(records[f'{name}_null_{j:02d}']['best']['score'] for name in ('hauer_real','hart_real')) for j in range(19)]
 k=sum(v>=actual-1e-12 for v in combined);ci=binomtest(k,19).proportion_ci();result['paired_max_transcription']={'real_max':actual,'ge':k,'n':19,'p_plus_one':(k+1)/20,'binomial95':[ci.low,ci.high],'control_values':combined}
 (OUT/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
