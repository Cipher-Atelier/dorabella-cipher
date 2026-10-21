"""Oracle diagnostics only; never counted as blind recovery."""
import json,numpy as np
from automata import variants,canonical,transform
from language import stable_seed
from fastsolve import solve_fast
from scan_v3 import Pipeline,PROTOCOL
from wordpolish_v3 import polish,char_score,fast_word
from wordscore_v3 import ROOT
from historical_check import cases as development_cases

def main():
 p=Pipeline();cases=[]
 old={q[0]:q for q in development_cases()}
 label,o,c,truth,info=old['history_03']
 cases.append((label,o,c,truth,info['generating_rule'],ROOT/'results/v2/historical/history_03.json',ROOT/'results/v3/dev_history_03.json'))
 for row in json.loads((ROOT/'results/v3/heldout/inputs.json').read_text())['cases']:
  if row['id'] in ['lamb_06','lamb_07']:
   cases.append((row['id'],np.array(row['orientation']),np.array(row['arcs_zero_based']),np.frombuffer(row['plaintext'].encode(),np.uint8).astype(np.int64)-97,row['generating_rule'],ROOT/f"results/v3/heldout/{row['id']}_v2bank.json",ROOT/f"results/v3/heldout/{row['id']}.json"))
 out=[]
 for label,o,c,truth,rule,bpath,rpath in cases:
  bank=json.loads(bpath.read_text());r=json.loads(rpath.read_text());vs=variants(o,c)
  correct=canonical(transform(o,c,rule));j=next(i for i,(seq,_) in enumerate(vs) if np.array_equal(seq,correct))
  ranks=[]
  for stage in bank['stages']:
   sc=np.array(stage['all_best_scores']);ranks.append({'stage':stage['stage'],'searched':j in stage['searched_indices'],'rank':int(1+sum(sc>sc[j]+1e-10))})
  s,key=solve_fast(correct,p.lp,p.p1,128,20000,stable_seed(correct,'v3_oracle'))
  s2,txt,m,tr=polish(key[correct],p.lp,p.ch,p.v,.5,30)
  row={'id':label,'blind_accuracy':float(np.mean(np.array(r['decoded'])==truth)),
    'true_pattern_index':j,'true_pattern_ranks':ranks,'correct_pattern_in_final_bank':j in [q['index'] for q in r['candidates']],
    'oracle_accuracy_before_polish':float(np.mean(key[correct]==truth)),'oracle_accuracy_after_polish':float(np.mean(txt==truth)),
    'oracle_score_after_polish':s2,'true_text_score':char_score(truth,p.lp)+.5*fast_word(truth,p.ch,p.v),
    'false_winner_score':r['best_score'],'oracle_text':txt.tolist(),'generating_rule':rule,
    'not_a_blind_result':True}
  out.append(row);print(json.dumps(row),flush=True)
 (ROOT/'results/v3/oracle_diagnostics.json').write_text(json.dumps(out,indent=2))
 # Score the known truths without feeding them into the search.
 truths=[]
 for row in json.loads((ROOT/'results/v3/heldout/inputs.json').read_text())['cases']:
  txt=np.frombuffer(row['plaintext'].encode(),np.uint8).astype(np.int64)-97
  truths.append({'id':row['id'],'char_score':char_score(txt,p.lp),'word_score':fast_word(txt,p.ch,p.v),
   'combined_score':char_score(txt,p.lp)+.5*fast_word(txt,p.ch,p.v)})
 (ROOT/'results/v3/heldout_true_scores.json').write_text(json.dumps(truths,indent=2))
if __name__=='__main__':main()
