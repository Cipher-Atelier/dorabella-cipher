"""Twelve new Lamb letter openings, fixed before decoding; convenience sample.
No test truth is used by candidate generation/refinement/ranking.
"""
import json,re,hashlib,time,concurrent.futures
import numpy as np
from automata import definitions,canonical,inverse,transform
from scan_v2 import scan_one
from scan_v3 import Pipeline
from wordscore_v3 import ROOT
from language import documents,corpus_path
EXTRACTS=[
(895,"Make yourself perfectly easy about May. I paid his bill when I sent your clothes. I was flush of money, and am so still to all the purposes of a single life;"),
(3004,"I don't know why I write, except from the propensity misery has to tell her griefs. Hetty died on Friday night, about eleven o'clock, after eight days' illness;"),
(3034,"I feel myself unable to thank you sufficiently for your kind letter. It was doubly acceptable to me, both for the choice poetry and the kind, honest prose which it contained."),
(3065,"I have taken to-day and delivered to Longman and Co., Imprimis: your books, viz., three ponderous German dictionaries, one volume (I can find no more) of German and French ditto,"),
(3125,"I am going to ask a favor of you, and am at a loss how to do it in the most delicate mariner. For this purpose I have been looking into Pliny's Letters,"),
(3325,"You need not imagine any apology necessary. Your fine hare and fine birds (which just now are dangling by our kitchen blaze) discourse most eloquent music in your justification."),
(3524,"Had you written one week before you did, I certainly should have obeyed your injunction; you should have seen me before my letter. I will explain to you my situation."),
(3653,"I have received a very kind invitation from Lloyd and Sophia to go and spend a month with them at the Lakes. Now, it fortunately happens (which is so seldom the case)"),
(4128,"Since the date of my last tetter, I have been a traveller, A strong desire seized me of visiting remote regions. My first impulse was to go aod see Paris."),
(4322,"I must positively write, or I shall miss you at Toulouse. I sit here like a decayed minute-hand (I lie; that does not sit), and being myself the exponent of no time,"),
(4370,"The general scope of your letter afforded no indications of insanity, but some particular points raised a scruple. For God's sake, don't think any more of Independent Tartary."),
(4592,"I have been very unwell since I saw you. A sad depression of spirits, a most unaccountable nervousness; from which I have been partially relieved by an odd accident.")]

def cases():
 rng=np.random.default_rng(2026092503);rules=list(definitions());out=[]
 train=documents(corpus_path('lee_background.cor'))
 for i,(line,raw) in enumerate(EXTRACTS):
  plain=re.sub('[^a-z]','',raw.lower())[:87];assert len(plain)==87
  assert not any(plain in doc for doc in train)
  a=np.frombuffer(plain.encode(),np.uint8).astype(np.int64)-97;seq=canonical(a);assert seq.max()<24
  z=rng.permutation(24)[seq]
  for _ in range(1000):
   rule=rules[int(rng.integers(len(rules)))];o,c=inverse(z,rule)
   if not np.array_equal(canonical(3*o+c),seq):break
  else:raise RuntimeError('No nontrivial rule')
  assert np.array_equal(transform(o,c,rule),z)
  out.append({'id':f'lamb_{i:02d}','source_line_start':line,'source_excerpt':raw,'plaintext':plain,
    'plaintext_sha256':hashlib.sha256(plain.encode()).hexdigest(),'orientation':o.tolist(),
    'arcs_zero_based':c.tolist(),'generating_rule':rule})
 return out

def main():
 out=ROOT/'results/v3/heldout';out.mkdir(exist_ok=True)
 frozen=json.loads((ROOT/'results/v3/frozen_protocol.json').read_text())
 for f,h in frozen['sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
 rows=cases();manifest={'source':'https://www.gutenberg.org/cache/epub/10125/pg10125.txt',
  'selection':'12 visible openings from separate Lamb letters; convenience sample; not random; source typos retained',
  'seed':2026092503,'test_cases_not_used_to_fit_or_select_v3':True,'cases':rows}
 path=out/'inputs.json'
 if path.exists():assert json.loads(path.read_text())==manifest
 else:path.write_text(json.dumps(manifest,indent=2))
 p=Pipeline()
 def work(case):
  dest=out/f"{case['id']}.json"
  if dest.exists():return json.loads(dest.read_text())
  o=np.array(case['orientation']);c=np.array(case['arcs_zero_based']);start=time.monotonic()
  bank,_=scan_one(o,c,p.lp,p.p1);bank['id']=case['id'];bank['seconds']=time.monotonic()-start
  (out/f"{case['id']}_v2bank.json").write_text(json.dumps(bank,indent=2))
  r=p.run(o,c,bank)
  truth=np.frombuffer(case['plaintext'].encode(),np.uint8).astype(np.int64)-97
  r['accuracy']=float(np.mean(np.array(r['decoded'])==truth));r['v2_accuracy']=float(np.mean(np.array(bank['decoded'])==truth))
  r['best_available_accuracy']=max(float(np.mean(np.array(x['decoded'])==truth)) for x in r['candidates'])
  r['full_seconds']=time.monotonic()-start
  dest.write_text(json.dumps(r,indent=2));print(case['id'],'old',round(r['v2_accuracy'],4),'new',round(r['accuracy'],4),'time',round(r['full_seconds'],1),flush=True)
  return r
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(work,rows))
 summary={'n':len(results),'old_ge90':sum(r['v2_accuracy']>=.9 for r in results),'new_ge90':sum(r['accuracy']>=.9 for r in results),
  'old_mean':float(np.mean([r['v2_accuracy'] for r in results])),'new_mean':float(np.mean([r['accuracy'] for r in results])),
  'min_accuracy':min(r['accuracy'] for r in results),'cases':[{'id':r['id'],'old':r['v2_accuracy'],'new':r['accuracy'],'best_available':r['best_available_accuracy']} for r in results]}
 (out/'summary.json').write_text(json.dumps(summary,indent=2));print('SUMMARY',summary,flush=True)
if __name__=='__main__':main()
