"""Fixed 24-letter notebook-key scorer. Never used to overwrite v1-v4 models.
Normalization I/J -> I, U/V -> U is applied to both training text and lexicon.
Uses the same character backoff and word weights as v3/v4.
"""
from pathlib import Path
from collections import Counter
import re, math, json, hashlib
import numpy as np
from language import corpus_path, documents
from wordscore_v3 import WordScorer, CONFIG
from wordpolish_v3 import build_trie
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/v5'; OUT.mkdir(parents=True,exist_ok=True)
ALPHABET='ABCDEFGHIKLMNOPQRSTUWXYZ'
LETTER=np.array([ord(c)-65 for c in ALPHABET],dtype=np.int64)

def normalise(text):
    return re.sub('[^a-z]','',text.lower()).replace('j','i').replace('v','u')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class MergedWordScorer(WordScorer):
    def __init__(self):
        import textblob
        path=Path(textblob.__file__).parent/'en/en-spelling.txt';counts=Counter()
        for line in path.read_text().splitlines():
            if not line or line.startswith(';'):continue
            w,n=line.split()
            if re.fullmatch('[a-z]+',w) and (len(w)>1 or w in ('a','i')):
                counts[normalise(w)]+=int(n)
        total=sum(counts.values());self.words={w:math.log(n/total) for w,n in counts.items()}
        pre=Counter();suf=Counter()
        for w,n in counts.items():
            for k in range(1,min(len(w),CONFIG['max_word']+1)):
                pre[w[:k]]+=n;suf[w[-k:]]+=n
        self.pre={w:math.log(n/total)-2 for w,n in pre.items()}
        self.suf={w:math.log(n/total)-2 for w,n in suf.items()}
        self.metadata=dict(dictionary_sha256=sha(path),words=len(counts),tokens=total,
             normalisation='ASCII lower; j->i and v->u; merge counts; unchanged segmentation penalties')

def make_model():
    path=ROOT/'data/english_merged24_v5.npz'
    if path.exists():return np.load(path)['logp4']
    raw=corpus_path('lee_background.cor');docs=[normalise(x) for x in documents(raw)]
    counts=[np.zeros(26**n,np.float64) for n in range(1,5)]
    for text in docs:
        a=np.frombuffer(text.encode(),np.uint8).astype(np.int64)-97
        for n in range(1,5):
            codes=np.zeros(len(a)-n+1,np.int64)
            for j in range(n):codes=26*codes+a[j:j+len(codes)]
            counts[n-1]+=np.bincount(codes,minlength=26**n)
    prior=np.zeros(26);prior[LETTER]=.1
    p1=(counts[0]+prior)/(counts[0].sum()+prior.sum())
    b=counts[1].reshape(26,26);p2=(b+3*p1)/(b.sum(-1,keepdims=True)+3)
    b=counts[2].reshape(26,26,26);p3=(b+5*p2[None,:,:])/(b.sum(-1,keepdims=True)+5)
    b=counts[3].reshape(26,26,26,26);p4=(b+10*p3[None,:,:,:])/(b.sum(-1,keepdims=True)+10)
    assert np.allclose(p4.sum(-1),1.)
    logp=np.full(p4.shape,-1e100);np.log(p4,out=logp,where=p4>0)
    np.savez_compressed(path,logp4=logp.ravel())
    (OUT/'model_metadata.json').write_text(json.dumps(dict(training_file=str(raw),sha256=sha(raw),
        documents=len(docs),letters=sum(map(len,docs)),normalisation='j->i,v->u',
        backoff=[3,5,10],probability_row_sum_max_error=float(abs(p4.sum(-1)-1).max())),indent=2))
    return logp.ravel()

def load_model():
    lp=make_model();scorer=MergedWordScorer();children,vals=build_trie(scorer)
    return lp,scorer,children,vals
