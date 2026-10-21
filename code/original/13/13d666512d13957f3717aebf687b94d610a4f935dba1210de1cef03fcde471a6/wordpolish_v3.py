"""Word-aware greedy refinement of the SAME eight saved hypotheses.
No access to plaintext. Bijective letter swaps only, so inverse cipher constraints
remain satisfied. Not a new exhaustive search of keys or state machines.
"""
from pathlib import Path
import numpy as np
from numba import njit
from wordscore_v3 import WordScorer,CONFIG,ROOT

def build_trie(scorer):
 nodes=[{}];vals=[[-1e100]*3]
 for k,d in enumerate([scorer.words,scorer.pre,scorer.suf]):
  for w,v in d.items():
   node=0
   for ch in w:
    c=ord(ch)-97
    if c not in nodes[node]:nodes[node][c]=len(nodes);nodes.append({});vals.append([-1e100]*3)
    node=nodes[node][c]
   vals[node][k]=v
 children=np.full((len(nodes),26),-1,np.int32)
 for node,d in enumerate(nodes):
  for c,v in d.items():children[node,c]=v
 return children,np.array(vals,dtype=np.float64)

@njit(cache=True)
def fast_word(text,children,vals):
 n=len(text);dp=np.full(n+1,-1e100);dp[0]=0.
 for start in range(n):
  v=dp[start]-8.
  if v>dp[start+1]:dp[start+1]=v
  node=0
  for end in range(start,min(n,start+24)):
   node=children[node,text[end]]
   if node<0:break
   v=vals[node,0]
   if start==0 and end+1<n:v=max(v,vals[node,2])
   if end+1==n and start>0:v=max(v,vals[node,1])
   value=dp[start]+v
   if value>dp[end+1]:dp[end+1]=value
 return dp[n]/n

@njit(cache=True)
def char_score(text,lp):
 val=0.
 for t in range(len(text)-3):val+=lp[((text[t]*26+text[t+1])*26+text[t+2])*26+text[t+3]]
 return val/(len(text)-3)

@njit(cache=True,nogil=True)
def polish(text,lp,children,vals,alpha=.25,max_sweeps=30):
 text=text.copy();mapping=np.arange(26);score=char_score(text,lp)+alpha*fast_word(text,children,vals)
 trace=np.zeros(max_sweeps+1);trace[0]=score;steps=0
 for sweep in range(max_sweeps):
  used=np.bincount(text,minlength=26);best=score;bi=-1;bj=-1
  for i in range(26):
   for j in range(i+1,26):
    if used[i]+used[j]==0:continue
    trial=text.copy()
    for t in range(len(text)):
     if text[t]==i:trial[t]=j
     elif text[t]==j:trial[t]=i
    s=char_score(trial,lp)+alpha*fast_word(trial,children,vals)
    if s>best+1e-10:best=s;bi=i;bj=j
  if bi<0:break
  for t in range(len(text)):
   if text[t]==bi:text[t]=bj
   elif text[t]==bj:text[t]=bi
  for t in range(26):
   if mapping[t]==bi:mapping[t]=bj
   elif mapping[t]==bj:mapping[t]=bi
  score=best;steps+=1;trace[steps]=score
 return score,text,mapping,trace[:steps+1]

if __name__=='__main__':
 import json,time
 from historical_check import cases
 from language import build_model
 scorer=WordScorer();ch,v=build_trie(scorer);lp,_=build_model();out=[];t=time.time()
 for label,o,c,a,info in cases():
  r=json.loads((ROOT/'results/v2/historical'/f'{label}.json').read_text());rows=[]
  for x in r['top_candidates']:
   s,text,mapping,trace=polish(np.array(x['decoded']),lp,ch,v)
   assert abs(fast_word(text,ch,v)-scorer.score(text))<1e-10
   rows.append({'index':x['index'],'rule':x['rule'],'score':s,'decoded':text.tolist(),'letter_permutation':mapping.tolist(),
    'trace':trace.tolist(),'word_score':scorer.score(text),'char_score':char_score(text,lp),
    'segmentation':scorer.score(text,True)[1],'accuracy_diagnostic':float(np.mean(text==a))})
  rows.sort(key=lambda x:(-x['score'],x['decoded']));b=rows[0]
  out.append({'id':label,'old_accuracy':r['accuracy'],'new_accuracy':b['accuracy_diagnostic'],'candidates':rows,
   'true_combined_score':char_score(a,lp)+.25*fast_word(a,ch,v)})
  print(label,'old',round(r['accuracy'],4),'new',round(b['accuracy_diagnostic'],4),'available',round(max(q['accuracy_diagnostic'] for q in rows),4),b['segmentation'],flush=True)
 (ROOT/'results/v3/polish_development.json').write_text(json.dumps({'alpha':.25,'max_sweeps':30,'cases':out,'seconds':time.time()-t},indent=2))
 print('Seconds',time.time()-t,'Trie nodes',len(ch),flush=True)
