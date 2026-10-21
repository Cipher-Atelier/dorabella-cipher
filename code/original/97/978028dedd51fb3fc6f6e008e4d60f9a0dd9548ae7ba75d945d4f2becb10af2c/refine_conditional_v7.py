"""Sensitivity of the exact-bigram comparison to a deeper key search.
Additional exploratory run, motivated by optimizer variability observed during
round7. Same refinement, initial-stage budget and seeds for real and controls.
The initial-stage unigram comparison is NOT re-used as a refined comparison.
"""
from pathlib import Path
import json,hashlib,time,argparse
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from automata import canonical
from wordsearch_v4 import WordSearch
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'results/v7/conditional';OUT=ROOT/'results/v7/conditional_refined';OUT.mkdir(parents=True,exist_ok=True)
CONFIG={'restarts':128,'iterations':16000}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
 engine=WordSearch();allcases=json.loads((BASE/'inputs.json').read_text())['cases'];cases=[c for c in allcases if c['kind'] in ('real','bigram')]
 assert len(cases)==200
 (OUT/'records').mkdir(exist_ok=True)
 tracked=[Path(__file__),ROOT/'wordsearch_v4.py',BASE/'inputs.json',BASE/'frozen.json']
 manifest={'config':CONFIG,'ids':[c['id'] for c in cases],'hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'status':'additional exploratory sensitivity run, chosen after initial real scores were seen; NOT preregistered'}
 m=OUT/'frozen.json'
 if m.exists():assert json.loads(m.read_text())==manifest
 else:m.write_text(json.dumps(manifest,indent=2))
 tasks=[c for c in cases if (BASE/'records'/(c['id']+'.json')).exists() and not (OUT/'records'/(c['id']+'.json')).exists()]
 s=canonical(np.array(cases[0]['glyph']));engine.run(s,np.arange(26)[s],{'restarts':1,'iterations':1},tag='compile')
 def run(c):
  old=json.loads((BASE/'records'/(c['id']+'.json')).read_text());seq=canonical(np.array(c['glyph']));t=time.monotonic()
  rec=engine.run(seq,np.array(old['decoded']),CONFIG,tag='v7_conditional_refinement')
  rec.update(id=c['id'],kind=c['kind'],source=c.get('source'),glyph=c['glyph'],initial_score=old['score'],seconds_refinement=time.monotonic()-t)
  rec['text']=''.join(chr(x+97) for x in rec['decoded']);assert rec['score']>=old['score']-1e-10
  (OUT/'records'/(c['id']+'.json')).write_text(json.dumps(rec,indent=2));print(c['id'],round(old['score'],6),'->',round(rec['score'],6),flush=True)
 with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(run,tasks))
 if all((OUT/'records'/(c['id']+'.json')).exists() for c in cases):
  result={}
  for name in ('hauer_real','hart_real'):
   real=json.loads((OUT/'records'/(name+'.json')).read_text());values=[json.loads((OUT/'records'/(c['id']+'.json')).read_text())['score'] for c in cases if c['kind']=='bigram' and c['source']==name];k=sum(v>=real['score']-1e-12 for v in values)
   result[name]={'score':real['score'],'initial_score':real['initial_score'],'mean':float(np.mean(values)),'ge':k,'n':len(values),'p_plus_one':(k+1)/100,'text':real['text'],'segmentation':real['segmentation']}
  result['records']=len(cases);(OUT/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 else:print('Partial run; completed ready inputs only. Resume after initial records finish.')
if __name__=='__main__':main()
