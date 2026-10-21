import numpy as np
from collections import Counter
def word_py(t,ch,va):
    dp=[float('-inf')]*88;dp[0]=0.
    for st in range(87):
        dp[st+1]=max(dp[st+1],dp[st]-8.);node=0
        for en in range(st,min(87,st+24)):
            node=int(ch[node,int(t[en])])
            if node<0:break
            v=float(va[node,0])
            if st==0 and en<86:v=max(v,float(va[node,2]))
            if en==86 and st>0:v=max(v,float(va[node,1]))
            dp[en+1]=max(dp[en+1],dp[st]+v)
    return dp[-1]/87

def score_py(t,lp,ch,va):
    C=float(np.mean([lp[26**3*int(t[i])+26**2*int(t[i+1])+26*int(t[i+2])+int(t[i+3])] for i in range(84)]));W=word_py(t,ch,va)
    return C+.5*W,C,W

def paircounts(x):return Counter(zip(map(int,x[:-1]),map(int,x[1:])))
def euler_shuffle(seq,rng):
    # Directed Wilson last-exit-tree shuffle; adapted from frozen round7.
    seq=np.asarray(seq,np.int64);K=int(seq.max())+1;edges=[[] for _ in range(K)]
    for i in range(len(seq)-1):edges[int(seq[i])].append(i)
    root=int(seq[-1]);tree=np.zeros(K,bool);tree[root]=True;last=np.full(K,-1,np.int64)
    for v in sorted(set(map(int,seq))):
        u=v
        while not tree[u]:
            e=edges[u][int(rng.integers(len(edges[u])))];last[u]=e;u=int(seq[e+1])
        u=v
        while not tree[u]:tree[u]=True;u=int(seq[last[u]+1])
    qs=[]
    for v in range(K):
        ee=edges[v].copy()
        if v!=root and ee:
            ee.remove(int(last[v]));rng.shuffle(ee);ee.append(int(last[v]))
        else:rng.shuffle(ee)
        qs.append(ee)
    ptr=np.zeros(K,int);out=np.empty_like(seq);out[0]=seq[0]
    for i in range(1,len(seq)):
        v=int(out[i-1]);e=qs[v][ptr[v]];ptr[v]+=1;out[i]=seq[e+1]
    assert out[-1]==seq[-1] and all(ptr[v]==len(qs[v]) for v in range(K))
    return out
