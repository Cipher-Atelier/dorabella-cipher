"""Frozen third-round pipeline: unchanged v2 proposal search + lexical rerank.
Truth never enters this function. Cached v2 candidate banks may be reused,
because the proposal model, code, seeds and budgets are unchanged.
"""
from pathlib import Path
import hashlib,json,time
import numpy as np
from language import build_model
from automata import variants,canonical
from wordscore_v3 import WordScorer,ROOT
from wordpolish_v3 import build_trie,polish,char_score,fast_word
PROTOCOL={'id':'word_rerank_v3','alpha':.5,'max_sweeps':30,
 'proposal_search':'unchanged scan_v2.scan_one, modern-news 4-gram',
 'proposal_candidates':'saved top eight plus identity, deduplicate by pattern index',
 'local_search':'deterministic best-improving global letter-pair swaps, at most 30 sweeps',
 'final_objective':'mean news conditional 4-gram log probability + 0.5 * Viterbi word log score / length',
 'selection':'maximize combined score; tie break lexicographic plaintext',
 'development':'8 Stevenson cases already used in round2; reuse, not independent',
 'alpha_trials':[.25,.5,1.,2.,4.],
 'chosen_on_development':'maximize count >=90%, then mean accuracy, then smaller alpha',
 'new_validation':'12 Lamb letter openings, new plaintexts, fixed without checking scores',
 'negative_control':'same 99 v2 permutations and fixed v2 banks; new rerank on each; exploratory, NOT fresh independent null sample',
 'limits':['No retraining on a complete historical corpus; dictionary is a pre-existing lexical resource.',
 'Word unigram scoring does not test syntax or meaning.',
 'Only eight v2 finalists plus identity are refined; missing correct hypotheses can still be missed.',
 'No transcription changes; no 3/4-state automata; all transformations preserve axis/arcs.']}

class Pipeline:
 def __init__(self):
  self.lp,self.p1=build_model();self.scorer=WordScorer();self.ch,self.v=build_trie(self.scorer)
 def run(self,o,c,bank):
  t0=time.monotonic();cand=variants(o,c);raw=canonical(3*o+c)
  entries=[dict(x) for x in bank['top_candidates']]
  ii=bank['identity_index']
  if all(x['index']!=ii for x in entries):
   entries.append({'index':ii,'rule':cand[ii][1],'score':bank['identity_score'],'decoded':bank['identity_decoded']})
  rows=[]
  for e in entries:
   original=np.array(e['decoded'],dtype=np.int64)
   s,txt,mapping,trace=polish(original,self.lp,self.ch,self.v,PROTOCOL['alpha'],PROTOCOL['max_sweeps'])
   seq=cand[e['index']][0]
   # Every equal cipher token must still have one and only one output letter,
   # and different tokens must have distinct outputs (injective substitution).
   mapping_token={}
   for tok,val in zip(seq,txt):
    if int(tok) in mapping_token:assert mapping_token[int(tok)]==int(val)
    mapping_token[int(tok)]=int(val)
   assert len(set(mapping_token.values()))==len(mapping_token)
   assert np.array_equal(txt,mapping[original]);assert np.all(np.diff(trace)>=-1e-10)
   ws,seg=self.scorer.score(txt,True)
   assert abs(ws-fast_word(txt,self.ch,self.v))<1e-10
   assert abs(s-(char_score(txt,self.lp)+PROTOCOL['alpha']*ws))<1e-9
   rows.append({'index':e['index'],'rule':e['rule'],'combined_score':s,
    'char_score':char_score(txt,self.lp),'word_score':ws,'decoded':txt.tolist(),
    'token_to_letter':mapping_token,'segmentation_for_diagnostics_only':seg,
    'letter_permutation':mapping.tolist(),'trace':trace.tolist(),
    'proposal_char_score':e['score'],'proposal_decoded':e['decoded']})
  rows.sort(key=lambda q:(-q['combined_score'],q['decoded']))
  b=rows[0];ident=next(x for x in rows if x['index']==ii)
  return {'id':bank.get('id'),'best_score':b['combined_score'],'identity_score':ident['combined_score'],
    'improvement':b['combined_score']-ident['combined_score'],'decoded':b['decoded'],
    'best_index':b['index'],'identity_index':ii,'candidates':rows,'seconds':time.monotonic()-t0}

if __name__=='__main__':
 from historical_check import cases
 out=ROOT/'results/v3';out.mkdir(exist_ok=True)
 p=Pipeline();rs=[]
 for label,o,c,a,info in cases():
  b=json.loads((ROOT/'results/v2/historical'/f'{label}.json').read_text());r=p.run(o,c,b)
  r['accuracy']=float(np.mean(np.array(r['decoded'])==a));r['old_accuracy']=b['accuracy'];rs.append(r)
  (out/f'dev_{label}.json').write_text(json.dumps(r,indent=2));print(label,r['accuracy'],flush=True)
 # Freeze all source and data model hashes before any new validation decoding.
 files=['scan_v3.py','wordscore_v3.py','wordpolish_v3.py','scan_v2.py','fastsolve.py','automata.py','language.py','data/english_model.npz']
 hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
 frozen={'protocol':PROTOCOL,'sha256':hashes,'lexicon':p.scorer.metadata,
  'development_summary':{'n':len(rs),'old_ge90':sum(x['old_accuracy']>=.9 for x in rs),
    'new_ge90':sum(x['accuracy']>=.9 for x in rs),'mean_old':float(np.mean([x['old_accuracy'] for x in rs])),
    'mean_new':float(np.mean([x['accuracy'] for x in rs]))}}
 (out/'frozen_protocol.json').write_text(json.dumps(frozen,indent=2));print(frozen['development_summary'])
