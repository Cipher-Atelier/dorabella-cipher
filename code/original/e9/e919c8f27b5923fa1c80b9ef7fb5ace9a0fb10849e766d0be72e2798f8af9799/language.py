"""Small, fixed, character 4-gram model and deterministic seeded MASC search.
A screening instrument, not a claim to match a published state-of-the-art solver.
English training data: Gensim's lee_background.cor (300 news documents).
No supposed Dorabella plaintext, name crib, or date is used.
"""
from pathlib import Path
import re, json, hashlib, importlib.util
import numpy as np
from numba import njit
ROOT=Path(__file__).resolve().parent

def corpus_path(name):
    spec=importlib.util.find_spec('gensim')
    if spec is None:raise RuntimeError('Install gensim to rebuild the model / run corpus validation.')
    return Path(spec.submodule_search_locations[0])/'test/test_data'/name

def documents(path):
    return [re.sub('[^a-z]','',line.lower()) for line in path.read_text(encoding='latin-1').splitlines() if line.strip()]

def build_model(force=False):
    target=ROOT/'data/english_model.npz'
    if target.exists() and not force:
        v=np.load(target);return v['logp4'],v['p1']
    path=corpus_path('lee_background.cor');docs=documents(path)
    counts=[np.zeros(26**n,dtype=np.float64) for n in range(1,5)]
    for text in docs:
        a=np.frombuffer(text.encode('ascii'),dtype=np.uint8).astype(np.int64)-97
        for n in range(1,5):
            codes=np.zeros(len(a)-n+1,np.int64)
            for j in range(n):codes=26*codes+a[j:j+len(codes)]
            counts[n-1]+=np.bincount(codes,minlength=26**n)
    p1=(counts[0]+.1)/(counts[0].sum()+2.6)
    b=counts[1].reshape(26,26);p2=(b+3*p1)/(b.sum(axis=-1,keepdims=True)+3)
    b=counts[2].reshape(26,26,26);p3=(b+5*p2[None,:,:])/(b.sum(axis=-1,keepdims=True)+5)
    b=counts[3].reshape(26,26,26,26);p4=(b+10*p3[None,:,:,:])/(b.sum(axis=-1,keepdims=True)+10)
    assert np.allclose(p4.sum(-1),1.)
    logp4=np.log(p4).ravel()
    np.savez_compressed(target,logp4=logp4,p1=p1)
    meta={'training_file':'gensim/test/test_data/lee_background.cor',
          'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'documents':len(docs),
          'letters':sum(map(len,docs)),
          'preprocessing':'lowercase, retain ASCII a-z only, remove spaces; do not join documents',
          'model':'interpolated conditional character 4-gram; Dirichlet backoff strengths 3,5,10',
          'scoring':'sum ln P(character t | previous 3 characters), t=3..86; divide by 84 for reporting',
          'source_url':'https://radimrehurek.com/gensim/auto_examples/tutorials/run_doc2vec_lee.html',
          'limitations':['Small modern-news corpus; not Elgar-era correspondence.',
                         'The corpus raw text is not redistributed in this bundle.']}
    (ROOT/'data/model_metadata.json').write_text(json.dumps(meta,indent=2))
    return logp4,p1

@njit(cache=True)
def score_key(seq,key,logp):
    score=0.
    for t in range(len(seq)-3):
        idx=((key[seq[t]]*26+key[seq[t+1]])*26+key[seq[t+2]])*26+key[seq[t+3]]
        score+=logp[idx]
    return score

@njit(cache=True)
def affected_windows(seq,K):
    L=len(seq)-3;where=np.zeros((26,26,L),np.int16);lens=np.zeros((26,26),np.int16)
    for i in range(K):
        for j in range(26):
            if i==j:continue
            n=0
            for t in range(L):
                hit=False
                for k in range(4):
                    if seq[t+k]==i or seq[t+k]==j:hit=True
                if hit:where[i,j,n]=t;n+=1
            lens[i,j]=n
    return where,lens

@njit(cache=True)
def delta_swap(seq,key,logp,where,lens,i,j):
    # Read the two hypothetical values without mutating key.
    vi=key[i];vj=key[j];delta=0.
    for q in range(lens[i,j]):
        t=where[i,j,q];old=0;new=0
        for k in range(4):
            sym=seq[t+k];v=key[sym];old=old*26+v
            if sym==i:v=vj
            elif sym==j:v=vi
            new=new*26+v
        delta+=logp[new]-logp[old]
    return delta

@njit(cache=True,nogil=True)
def solve(seq,logp,p1,restarts,iterations,seed):
    np.random.seed(seed);K=int(seq.max())+1;where,lens=affected_windows(seq,K)
    counts=np.bincount(seq,minlength=26);rankc=np.argsort(counts)[::-1];rankp=np.argsort(p1)[::-1]
    freqkey=np.zeros(26,np.int64)
    for i in range(26):freqkey[rankc[i]]=rankp[i]
    best=-1.e100;bestkey=freqkey.copy()
    for r in range(restarts):
        if r==0:key=freqkey.copy()
        else:key=np.random.permutation(26)
        value=score_key(seq,key,logp)
        if value>best:best=value;bestkey=key.copy()
        for it in range(iterations):
            i=np.random.randint(K);j=np.random.randint(26)
            if i==j:continue
            d=delta_swap(seq,key,logp,where,lens,i,j)
            temperature=4.*np.exp(-4.382026634673881*it/max(1,iterations-1))
            if d>=0 or np.random.random()<np.exp(d/temperature):
                key[i],key[j]=key[j],key[i];value+=d
                if value>best:best=value;bestkey=key.copy()
        # Deterministic greedy polishing at the end of each restart.
        for sweep in range(15):
            improved=False
            for i in range(K):
                for j in range(i+1,26):
                    d=delta_swap(seq,key,logp,where,lens,i,j)
                    if d>1.e-10:
                        key[i],key[j]=key[j],key[i];value+=d;improved=True
                        if value>best:best=value;bestkey=key.copy()
            if not improved:break
    exact=score_key(seq,bestkey,logp)
    return exact,bestkey

def stable_seed(seq,stage):
    digest=hashlib.sha256(np.asarray(seq,dtype='<i8').tobytes()+stage.encode()).digest()
    return int.from_bytes(digest[:4],'little')

if __name__=='__main__':
    import time
    from automata import canonical
    logp,p1=build_model();rng=np.random.default_rng(1234)
    train=documents(corpus_path('lee_background.cor'));test=documents(corpus_path('lee.cor'))
    rows=[];start=time.time()
    for i,text in enumerate(test[:20]):
        off=int(rng.integers(0,len(text)-87));plain=text[off:off+87]
        assert not any(plain in t for t in train)
        a=np.frombuffer(plain.encode(),dtype=np.uint8).astype(np.int64)-97
        c=canonical(a)
        sc,key=solve(c,logp,p1,128,20000,stable_seed(c,'validation'))
        decoded=key[c];acc=float(np.mean(decoded==a))
        row={'case':i,'offset':off,'accuracy':acc,'score':sc/84,
             'true_score':float(score_key(a,np.arange(26),logp))/84,
             'plaintext_sha256':hashlib.sha256(plain.encode()).hexdigest()}
        rows.append(row);print(row,flush=True)
    out={'budget':{'restarts':128,'iterations':20000},'cases':rows,
         'mean_accuracy':float(np.mean([r['accuracy'] for r in rows])),
         'at_least_90_percent':sum(r['accuracy']>=.9 for r in rows),
         'heldout_source':'gensim/test/test_data/lee.cor',
         'heldout_sha256':hashlib.sha256(corpus_path('lee.cor').read_bytes()).hexdigest()}
    (ROOT/'results/decoder_validation.json').write_text(json.dumps(out,indent=2))
    print('RESULT',out['mean_accuracy'],out['at_least_90_percent'],'time',time.time()-start,flush=True)
