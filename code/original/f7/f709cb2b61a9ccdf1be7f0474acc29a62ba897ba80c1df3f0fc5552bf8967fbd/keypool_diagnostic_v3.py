"""DIAGNOSTIC ONLY, designed AFTER v3 held-out outcomes.
Keep the best letter key from EACH restart rather than only the global best.
No changes to the primary v3 protocol or its reported validation results.
"""
import numpy as np
from numba import njit
from language import score_key
from fastsolve import prepare,encode_windows,delta_cached,apply_swap
@njit(cache=True,nogil=True)
def solve_pool(seq,logp,p1,restarts,iterations,seed):
    np.random.seed(seed);K=int(seq.max())+1;wh,dc,ln=prepare(seq)
    counts=np.bincount(seq,minlength=26);rankc=np.argsort(counts)[::-1];rankp=np.argsort(p1)[::-1]
    freqkey=np.zeros(26,np.int64)
    for i in range(26):freqkey[rankc[i]]=rankp[i]
    # Precompute acceptance temperatures once, avoiding exp per iteration.
    invtemp=np.exp(4.382026634673881*np.arange(iterations)/max(1,iterations-1))/4.
    best=-1.e100;bestkey=freqkey.copy()
    pool_scores=np.zeros(restarts);pool_keys=np.zeros((restarts,26),np.int64)
    for r in range(restarts):
        if r==0:key=freqkey.copy()
        else:key=np.random.permutation(26)
        codes=encode_windows(seq,key)
        value=score_key(seq,key,logp)
        rbest=value;rkey=key.copy()
        if value>best:best=value;bestkey=key.copy()
        for it in range(iterations):
            i=np.random.randint(K);j=np.random.randint(26)
            if i==j:continue
            d=delta_cached(codes,key,logp,wh,dc,ln,i,j)
            if d>=0 or np.random.random()<np.exp(d*invtemp[it]):
                apply_swap(codes,key,wh,dc,ln,i,j);value+=d
                if value>rbest:rbest=value;rkey=key.copy()
                if value>best:best=value;bestkey=key.copy()
        for sweep in range(15):
            improved=False
            for i in range(K):
                for j in range(i+1,26):
                    d=delta_cached(codes,key,logp,wh,dc,ln,i,j)
                    if d>1.e-10:
                        apply_swap(codes,key,wh,dc,ln,i,j);value+=d;improved=True
                        if value>rbest:rbest=value;rkey=key.copy()
                        if value>best:best=value;bestkey=key.copy()
            if not improved:break
        pool_scores[r]=score_key(seq,rkey,logp);pool_keys[r]=rkey
    return pool_scores,pool_keys

if __name__=='__main__':
 import json,time
 from automata import variants
 from historical_check import cases
 from scan_v3 import Pipeline
 from wordpolish_v3 import polish
 from language import stable_seed
 from wordscore_v3 import ROOT
 p=Pipeline();case=next(q for q in cases() if q[0]=='history_03');label,o,c,truth,info=case
 bank=json.loads((ROOT/'results/v2/historical/history_03.json').read_text());vs=variants(o,c)
 finalists=sorted(set(x['index'] for x in bank['top_candidates'])|{bank['identity_index']})
 collected=[];t=time.monotonic()
 for j in finalists:
  seq,rule=vs[j];scores,keys=solve_pool(seq,p.lp,p.p1,64,20000,stable_seed(seq,'v3_pool_diagnostic'))
  # Deduplicate within this candidate only, without using truth.
  seen=set()
  for r,key in enumerate(keys):
   raw=key[seq];sig=raw.tobytes()
   if sig in seen:continue
   seen.add(sig);s,txt,m,tr=polish(raw,p.lp,p.ch,p.v,.5,30)
   collected.append({'pattern_index':j,'restart':r,'rule':rule,'raw_char_score':float(scores[r]/84),
    'combined_score':s,'raw_decoded':raw.tolist(),'decoded':txt.tolist()})
 print('Kept',len(collected),'distinct outputs in',time.monotonic()-t,flush=True)
 best=sorted(collected,key=lambda q:(-q['combined_score'],q['decoded']))[0]
 # Read truth ONLY after selection to report diagnostics.
 oldbest=max(collected,key=lambda q:q['raw_char_score'])
 result={'id':label,'diagnostic_not_independent_validation':True,'no_oracle_automaton_used':True,
 'finalists':finalists,'restarts_per_finalist':64,'iterations':20000,'unique_key_hypotheses':len(collected),
 'best_by_old_char_accuracy':float(np.mean(np.array(oldbest['raw_decoded'])==truth)),
 'best_by_new_word_accuracy':float(np.mean(np.array(best['decoded'])==truth)),
 'best':best,'old_char_best':oldbest,'all_candidates':collected,'seconds':time.monotonic()-t}
 (ROOT/'results/v3/keypool_diagnostic.json').write_text(json.dumps(result,indent=2))
 print('Old-char selection',result['best_by_old_char_accuracy'],'New-word selection',result['best_by_new_word_accuracy'],flush=True)
