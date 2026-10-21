"""Deterministic word-unigram segmentation for reranking, not semantic proof.
Vocabulary is the installed TextBlob spelling frequency list, frozen by hash.
No Dorabella words or test excerpts are added to the dictionary.
Partial words may occur at the ends of an 87-letter crop.
"""
from pathlib import Path
import hashlib,json,math,re
import numpy as np
ROOT=Path(__file__).resolve().parent
CONFIG={'max_word':24,'unknown_logp_per_letter':-8.,'partial_end_penalty':-2.,
        'single_letter_words':['a','i'],'objective':'Viterbi sum log unigram probabilities / character count'}

def load_lexicon():
 import textblob
 path=Path(textblob.__file__).parent/'en/en-spelling.txt'
 counts={}
 for line in path.read_text().splitlines():
  if not line or line.startswith(';'):continue
  w,n=line.split()
  if re.fullmatch('[a-z]+',w) and (len(w)>1 or w in ('a','i')):counts[w]=int(n)
 total=sum(counts.values());lp={w:math.log(n/total) for w,n in counts.items()}
 pre={};suf={}
 for w,n in counts.items():
  for k in range(1,min(len(w),CONFIG['max_word']+1)):
   pre[w[:k]]=pre.get(w[:k],0)+n
   suf[w[-k:]]=suf.get(w[-k:],0)+n
 p={w:math.log(n/total)+CONFIG['partial_end_penalty'] for w,n in pre.items()}
 s={w:math.log(n/total)+CONFIG['partial_end_penalty'] for w,n in suf.items()}
 meta={'filename':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'words':len(counts),'tokens':total,'source':'https://github.com/sloria/TextBlob/blob/dev/src/textblob/en/en-spelling.txt',
       'header':path.read_text().splitlines()[:5],'config':CONFIG}
 return lp,p,s,meta

class WordScorer:
 def __init__(self):self.words,self.pre,self.suf,self.metadata=load_lexicon()
 def score(self,text,explain=False):
  if not isinstance(text,str):text=''.join(chr(int(x)+97) for x in text)
  text=text.lower();n=len(text)
  assert n and re.fullmatch('[a-z]+',text)
  dp=[-1e100]*(n+1);dp[0]=0.;back=[None]*(n+1)
  for end in range(1,n+1):
   dp[end]=dp[end-1]+CONFIG['unknown_logp_per_letter'];back[end]=(end-1,'?'+text[end-1])
   for start in range(max(0,end-CONFIG['max_word']),end):
    w=text[start:end];v=self.words.get(w,-1e100);label=w
    if start==0 and end<n and self.suf.get(w,-1e100)>v:v=self.suf[w];label='…'+w
    if end==n and start>0 and self.pre.get(w,-1e100)>v:v=self.pre[w];label=w+'…'
    value=dp[start]+v
    if value>dp[end]:dp[end]=value;back[end]=(start,label)
  if explain:
   parts=[];i=n
   while i>0:
    i,label=back[i];parts.append(label)
   return dp[-1]/n,' '.join(parts[::-1])
  return dp[-1]/n

if __name__=='__main__':
 from historical_check import cases
 scorer=WordScorer();out=[]
 for label,o,c,a,info in cases():
  r=json.loads((ROOT/'results/v2/historical'/f'{label}.json').read_text())
  cand=r['top_candidates'];rows=[]
  for x in cand:
   sc,seg=scorer.score(x['decoded'],True)
   rows.append({'index':x['index'],'char_score':x['score'],'word_score':sc,
                'accuracy':float(np.mean(np.array(x['decoded'])==a)),'segmentation':seg})
  out.append({'id':label,'true_word_score':scorer.score(a),'candidates':rows})
  print(label,'old',r['accuracy'],'oracle available',max(x['accuracy'] for x in rows))
  for alpha in [0.,.25,.5,1.,2.,4.]:
   b=max(rows,key=lambda x:x['char_score']+alpha*x['word_score']);print(alpha,round(b['accuracy'],3),b['segmentation'])
  b=max(rows,key=lambda x:x['word_score']);print('wordonly',b['accuracy'],b['segmentation'])
 p=ROOT/'results/v3';p.mkdir(exist_ok=True)
 (p/'word_development.json').write_text(json.dumps({'metadata':scorer.metadata,'cases':out},indent=2))
