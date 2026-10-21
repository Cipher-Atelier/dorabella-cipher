"""Cached four-gram integer codes; same swap objective as language.py.
No change to model or candidate transformations. Tests in test_fastsolve.py.
"""
import numpy as np
from numba import njit
from language import score_key

@njit(cache=True)
def prepare(seq):
    K=int(seq.max())+1;L=len(seq)-3
    coeff=np.zeros((26,L),np.int32)
    for t in range(L):
        coeff[seq[t],t]+=17576
        coeff[seq[t+1],t]+=676
        coeff[seq[t+2],t]+=26
        coeff[seq[t+3],t]+=1
    wh=np.zeros((26,26,L),np.int16)
    dc=np.zeros((26,26,L),np.int32)
    ln=np.zeros((26,26),np.int16)
    for i in range(K):
        for j in range(26):
            n=0
            for t in range(L):
                d=coeff[i,t]-coeff[j,t]
                if d!=0:
                    wh[i,j,n]=t;dc[i,j,n]=d;n+=1
            ln[i,j]=n
    return wh,dc,ln

@njit(cache=True)
def encode_windows(seq,key):
    codes=np.empty(len(seq)-3,np.int32)
    for t in range(len(codes)):
        codes[t]=17576*key[seq[t]]+676*key[seq[t+1]]+26*key[seq[t+2]]+key[seq[t+3]]
    return codes

@njit(cache=True)
def delta_cached(codes,key,logp,wh,dc,ln,i,j):
    v=key[j]-key[i];d=0.
    for q in range(ln[i,j]):
        old=codes[wh[i,j,q]];new=old+dc[i,j,q]*v
        d+=logp[new]-logp[old]
    return d

@njit(cache=True)
def apply_swap(codes,key,wh,dc,ln,i,j):
    v=key[j]-key[i]
    for q in range(ln[i,j]):codes[wh[i,j,q]]+=dc[i,j,q]*v
    key[i],key[j]=key[j],key[i]

@njit(cache=True,nogil=True)
def solve_fast(seq,logp,p1,restarts,iterations,seed):
    np.random.seed(seed);K=int(seq.max())+1;wh,dc,ln=prepare(seq)
    counts=np.bincount(seq,minlength=26);rankc=np.argsort(counts)[::-1];rankp=np.argsort(p1)[::-1]
    freqkey=np.zeros(26,np.int64)
    for i in range(26):freqkey[rankc[i]]=rankp[i]
    # Precompute acceptance temperatures once, avoiding exp per iteration.
    invtemp=np.exp(4.382026634673881*np.arange(iterations)/max(1,iterations-1))/4.
    best=-1.e100;bestkey=freqkey.copy()
    for r in range(restarts):
        if r==0:key=freqkey.copy()
        else:key=np.random.permutation(26)
        codes=encode_windows(seq,key)
        value=score_key(seq,key,logp)
        if value>best:best=value;bestkey=key.copy()
        for it in range(iterations):
            i=np.random.randint(K);j=np.random.randint(26)
            if i==j:continue
            d=delta_cached(codes,key,logp,wh,dc,ln,i,j)
            if d>=0 or np.random.random()<np.exp(d*invtemp[it]):
                apply_swap(codes,key,wh,dc,ln,i,j);value+=d
                if value>best:best=value;bestkey=key.copy()
        for sweep in range(15):
            improved=False
            for i in range(K):
                for j in range(i+1,26):
                    d=delta_cached(codes,key,logp,wh,dc,ln,i,j)
                    if d>1.e-10:
                        apply_swap(codes,key,wh,dc,ln,i,j);value+=d;improved=True
                        if value>best:best=value;bestkey=key.copy()
            if not improved:break
    return score_key(seq,bestkey,logp),bestkey
