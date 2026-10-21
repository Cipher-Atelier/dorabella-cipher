"""Convenience sample of eight letter openings, NOT random historical corpus.
Source: Project Gutenberg 622, first eight 'MY DEAR MOTHER' openings returned
by the source-text find, stripped of salutation. Extracted before solving.
No language-model retraining and no algorithm changes. Body truncation 87 letters.
"""
from pathlib import Path
import json,hashlib,time,datetime
import numpy as np
from automata import canonical,definitions,inverse,transform
from language import build_model,score_key
from scan_v2 import scan_one,PROTOCOL
EXTRACTS=[
(1254,"Wick lies at the end or elbow of an open triangular bay, hemmed on either side by shores, either cliff or steep earth-bank"),
(1394,"The last two days have been dreadfully hard, and I was so tired in the evenings that I could not write. In fact, last night I went to sleep immediately after dinner, or very nearly so."),
(1446,"Another storm: wind higher, rain thicker: the wind still rising as the night closes in and the sea slowly rising along with it; it looks like a three days' gale."),
(1767,"I am here at last, sitting in my room, without coat or waistcoat, and with both window and door open, and yet perspiring like a terra-cotta jug or a Gruyere cheese."),
(2137,"I am too happy to be much of a correspondent. Yesterday we were away to Melford and Lavenham, both exceptionally placid, beautiful old English towns. Melford scattered all round a big green,"),
(2749,"We have here fallen on the very pink of hotels. I do not say that it is more pleasantly conducted than the Pavillon, for that were impossible; but the rooms are so cheery and bright and new,"),
(2801,"I received yesterday two most charming letters—the nicest I have had since I left—December 26th and January 1st: this morning I got January 3rd."),
(4569,"About criticisms, I was more surprised at the tone of the critics than I suppose any one else. And the effect it has produced in me is one of shame. If they liked that so much, I ought to have given them something better, that's all.")]

def cases():
 import re
 rng=np.random.default_rng(729034);rules=list(definitions());out=[]
 for i,(line,raw) in enumerate(EXTRACTS):
  text=re.sub('[^a-z]','',raw.lower())[:87];assert len(text)==87
  a=np.frombuffer(text.encode(),np.uint8).astype(np.int64)-97;seq=canonical(a);assert seq.max()<24
  z=rng.permutation(24)[seq]
  for j in range(1000):
   rule=rules[int(rng.integers(len(rules)))];o,c=inverse(z,rule)
   if not np.array_equal(canonical(3*o+c),seq):break
  else:raise RuntimeError('Nontrivial rule not found')
  assert np.array_equal(transform(o,c,rule),z)
  out.append((f'history_{i:02d}',o,c,a,{'source_line_start':line,'generating_rule':rule,'plaintext_sha256':hashlib.sha256(text.encode()).hexdigest()}))
 return out

def main():
 out=Path('results/v2/historical');out.mkdir(exist_ok=True);lp,p1=build_model();cs=cases()
 manifest={'source':'https://www.gutenberg.org/ebooks/622.txt.utf-8','edition':'Stevenson, Letters, vol. 1, Gutenberg 622',
  'extraction':'First eight MY DEAR MOTHER openings visible in source-text find, remove salutation, retain first 87 ASCII letters; not a random corpus sample',
  'sample_fixed_before_solving':True,'no_retuning':True,'utc_created':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'cases':[{'id':label,'o':o.tolist(),'c':c.tolist(),'info':info} for label,o,c,a,info in cs]}
 if not (out/'protocol.json').exists():(out/'protocol.json').write_text(json.dumps(manifest,indent=2))
 for label,o,c,a,info in cs:
  path=out/f'{label}.json'
  if path.exists():continue
  t=time.monotonic();r,cand=scan_one(o,c,lp,p1);r.update({'id':label,'source_info':info,'accuracy':float(np.mean(np.array(r['decoded'])==a)),'true_score':float(score_key(a,np.arange(26),lp))/84,'seconds':time.monotonic()-t})
  path.write_text(json.dumps(r,indent=2));print(label,r['accuracy'],r['best_score'],r['seconds'],flush=True)
 rows=[json.loads((out/f'{case[0]}.json').read_text()) for case in cs]
 summ={'n':len(rows),'mean_accuracy':float(np.mean([r['accuracy'] for r in rows])),
  'at_least_90_percent':sum(r['accuracy']>=.9 for r in rows),'min_accuracy':min(r['accuracy'] for r in rows),
  'mean_best_score':float(np.mean([r['best_score'] for r in rows]))}
 (out/'summary.json').write_text(json.dumps(summ,indent=2));print(summ,flush=True)
if __name__=='__main__':main()
