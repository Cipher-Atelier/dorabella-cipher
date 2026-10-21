"""Two source-inspected Elgar excerpts: sensitivity of trigram-preserving controls.
No Dorabella re-search, retraining, or plaintext supplied to unknown-key solver.
"""
from pathlib import Path
import sys,json,hashlib,re,time,argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from automata import canonical
from conditional_v7 import euler_shuffle
from count_bigrams_v7 import count_strings
from language import stable_seed
from fastsolve import solve_fast
from wordsearch_v4 import WordSearch
from wordpolish_v3 import char_score
OUT=HERE/'results'/'elgar';OUT.mkdir(exist_ok=True)
def grams(s,k):return [tuple(map(int,s[i:i+k])) for i in range(len(s)-k+1)]
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def draw_k3(s,rng):
 v=grams(s,2);types=sorted(set(v));idx={v:i for i,v in enumerate(types)}
 enc=np.array([idx[p] for p in v]);z=euler_shuffle(enc,rng)
 out=np.array(list(types[int(z[0])])+[types[int(i)][-1] for i in z[1:]],np.uint8)
 assert Counter(grams(out,3))==Counter(grams(s,3))
 assert list(out[:2])==list(s[:2]) and list(out[-2:])==list(s[-2:])
 assert Counter(map(int,out))==Counter(map(int,s))
 return out

def make_inputs(proto):
 p=OUT/'inputs.json'
 if p.exists():return json.loads(p.read_text())
 sources=json.loads((HERE/'sources'/'elgar_excerpts.json').read_text())
 rng=np.random.default_rng(proto['seed']);cases=[];metadata=[]
 for source in sources:
  text=re.sub('[^a-z]','',source['excerpt'].lower())[:87]
  assert len(text)==87 and len(set(text))<=24
  norm=np.array([ord(c)-97 for c in text]);sym=canonical(norm)
  g=rng.permutation(24)[sym];orig_id=source['id']
  cases.append({'id':orig_id,'kind':'known_positive','source_id':orig_id,'glyph':g.tolist(),'plaintext':text})
  total,_=count_strings(grams(g,2))
  metadata.append({'id':orig_id,'exact_trigram_strings':str(total),'source':source,'distinct_plain_letters':len(set(text)),'plaintext':text})
  for j in range(proto['nulls_per_excerpt']):
   z=draw_k3(g,rng)
   cases.append({'id':f'{orig_id}_null_{j:02d}','kind':'trigram_null','source_id':orig_id,'glyph':z.tolist()})
 obj={'protocol':proto,'sources':metadata,'cases':cases};dump(p,obj);return obj

def compute(c,engine,proto):
 p=OUT/'records'/(c['id']+'.json');p.parent.mkdir(exist_ok=True)
 if p.exists():return json.loads(p.read_text())
 t=time.monotonic()
 # Unknown-key solver receives only canonical glyphs and fixed model parameters.
 seq=canonical(np.array(c['glyph']));score,key=solve_fast(seq,engine.lp,engine.p1,*proto['char_search'],stable_seed(seq,'round8_elgar_k3_char'))
 text=''.join(chr(int(i)+97) for i in key[seq]);rec=engine.run(seq,key[seq],proto['word_search'],tag='round8_elgar_k3_word')
 d={'id':c['id'],'kind':c['kind'],'glyph':c['glyph'],'source_id':c['source_id'],
    'character':{'score':float(score/(len(seq)-3)),'text':text,'key':key.tolist()},'word':rec,'seconds':time.monotonic()-t}
 if c['kind']=='known_positive':
  true=c['plaintext'];pred=''.join(chr(i+97) for i in rec['decoded'])
  d['accuracy_character']=sum(x==y for x,y in zip(text,true))/87
  d['accuracy_word']=sum(x==y for x,y in zip(pred,true))/87
  d['errors_word_1_based']=[i+1 for i,(x,y) in enumerate(zip(pred,true)) if x!=y]
  true_char=float(char_score(np.array([ord(x)-97 for x in true],np.int64),engine.lp))
  true_word=float(engine.scorer.score(true));d['true_scores']={'char':true_char,'word':true_word,'combined':true_char+0.5*true_word}
 dump(p,d);print(c['id'],round(d['character']['score'],6),round(d['word']['score'],6),round(d['seconds'],2),flush=True)
 return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
 frozen=json.loads((HERE/'frozen_elgar_protocol.json').read_text())
 for rel,sha in frozen['sha256'].items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==sha
 proto=frozen['protocol'];data=make_inputs(proto);eng=WordSearch()
 s=canonical(np.array(data['cases'][0]['glyph']));solve_fast(s,eng.lp,eng.p1,1,1,1)
 eng.run(s,np.arange(26)[s],{'restarts':1,'iterations':1,'final_greedy_sweeps':1},tag='compile')
 with ThreadPoolExecutor(max_workers=a.workers) as pool:
  records=list(pool.map(lambda c:compute(c,eng,proto),data['cases']))
 summary={'protocol':proto,'record_count':len(records),'dictionary_metadata':eng.scorer.metadata,'sources':data['sources'],'results':{}}
 for source in data['sources']:
  sid=source['id'];real=next(r for r in records if r['id']==sid);null=[r for r in records if r['kind']=='trigram_null' and r['source_id']==sid]
  out={'accuracy_character':real['accuracy_character'],'accuracy_word':real['accuracy_word'],'true_scores':real['true_scores'],'errors_word_1_based':real['errors_word_1_based'],'null_draws':len(null),'distinct_null_inputs':len({tuple(r['glyph']) for r in null}),'draws_equal_original':sum(r['glyph']==real['glyph'] for r in null)}
  for meth in ['character','word']:
   actual=real[meth]['score'];sc=[r[meth]['score'] for r in null];k=sum(x>=actual-1e-12 for x in sc)
   out[meth]={'real_score':actual,'controls_ge':k,'n':len(sc),'p_plus_one_descriptive':(k+1)/(len(sc)+1),'null_mean':float(np.mean(sc))}
  summary['results'][sid]=out
 dump(OUT/'summary.json',summary);print(json.dumps(summary['results'],indent=2),flush=True)
if __name__=='__main__':main()
