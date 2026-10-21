"""Prefix-only exact structured key search with admissible dictionary bounds.
Family: arbitrary permutation of eight fixed letter triples; common middle
rank m, independently reversed endpoints for each orientation. No edits.
"""
from pathlib import Path
import sys,os,itertools
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
os.environ.setdefault('NUMBA_CACHE_DIR',str(HERE/'cache'))
sys.path.insert(0,str(ROOT))
import numpy as np
from numba import njit
from model_v5 import load_model,LETTER,ALPHABET
from wordpolish_v3 import char_score,fast_word
P8=np.array(list(itertools.permutations(range(8))),dtype=np.int64)
# Canonical Q: ascending endpoints, middle rank m. Reverse INPUT arcs 1<->3.
Q=np.array([[1,0,2],[0,1,2],[0,2,1]],dtype=np.int64)
NK=40320*3*256

def key_at(i):
    p,rem=divmod(int(i),768);m,b=divmod(rem,256)
    return np.array([LETTER[3*P8[p,o]+Q[m,2-c if b>>o&1 else c]] for o in range(8) for c in range(3)],dtype=np.int64)

@njit(cache=True,nogil=True)
def ambiguous_word(g,lo,hi,children,vals):
    """Upper bound on word score. Each position may choose lo OR hi freely,
    even inconsistently between occurrences. Every legal key is included.
    A binary DFS stack of depth <=24 needs <=25 pending nodes; capacity 64.
    """
    n=len(g);dp=np.full(n+1,-1e100);dp[0]=0.
    ns=np.empty(64,np.int64);es=np.empty(64,np.int64)
    for start in range(n):
        if dp[start]-8.>dp[start+1]:dp[start+1]=dp[start]-8.
        sp=1;ns[0]=0;es[0]=start
        while sp:
            sp-=1;node=ns[sp];end=es[sp]
            a=lo[g[end]];b=hi[g[end]]
            for which in range(1 if a==b else 2):
                child=children[node,a if which==0 else b]
                if child<0:continue
                v=vals[child,0]
                if start==0 and end+1<n:v=max(v,vals[child,2])
                if end+1==n and start>0:v=max(v,vals[child,1])
                value=dp[start]+v
                if value>dp[end+1]:dp[end+1]=value
                if end+1<n and end+1<start+24:
                    if sp>=64:raise RuntimeError('DFS capacity exceeded')
                    ns[sp]=child;es[sp]=end+1;sp+=1
    return dp[n]/n

@njit(cache=True,nogil=True)
def scan_block(g,lp,children,vals,p8,q,letter,pstart,pstop,incumbent,incumbent_id):
    """All 768 keys per P. C evaluated for all; W evaluated unless a safe
    block/key upper bound is below incumbent by >=1e-9. No heuristic cut.
    Outputs contain exact local maximum, tie ids and per-P checkpoint data.
    """
    n=len(g);nw=n-3
    lo=np.empty(24,np.int64);hi=np.empty(24,np.int64);buf=np.empty(n,np.int64)
    potential=np.zeros((nw,256),np.float64)
    wm=np.zeros(nw,np.int64)
    for t in range(nw):
        for j in range(4):
            if g[t+j]%3!=1:wm[t]|=1<<(g[t+j]//3)
    cs=np.empty(256,np.float64)
    best=incumbent;bestid=incumbent_id
    ties=[]
    # p,m,Cmax,Wupper,evaluated,skipped,Cmin,local Smax, local id
    stats=np.empty(((pstop-pstart)*3,9),np.float64)
    sparse_ids=[];sparse_c=[];sparse_w=[]
    for pi in range(pstart,pstop):
        for m in range(3):
            for o in range(8):
                for c in range(3):
                    lo[3*o+c]=letter[3*p8[pi,o]+q[m,c]]
                    hi[3*o+c]=letter[3*p8[pi,o]+q[m,2-c]]
            for t in range(nw):
                subset=wm[t]
                while True:
                    code=0
                    for j in range(4):
                        z=g[t+j];v=hi[z] if subset>>(z//3)&1 else lo[z]
                        code=code*26+v
                    potential[t,subset]=lp[code]
                    if subset==0:break
                    subset=(subset-1)&wm[t]
            cmax=-1e100;cmin=1e100;cbest=0
            for b in range(256):
                v=0.
                for t in range(nw):v+=potential[t,b&wm[t]]
                cs[b]=v/nw
                if cs[b]>cmax:cmax=cs[b];cbest=b
                if cs[b]<cmin:cmin=cs[b]
            upper=ambiguous_word(g,lo,hi,children,vals)
            evaluated=0;localbest=-1e100;localid=-1
            # First the character champion, then all other masks in ID order.
            for bi in range(257):
                b=cbest if bi==0 else bi-1
                if bi>0 and b==cbest:continue
                idx=pi*768+m*256+b
                if cs[b]+.5*upper < best-1e-9:continue
                for t in range(n):
                    z=g[t];buf[t]=hi[z] if b>>(z//3)&1 else lo[z]
                w=fast_word(buf,children,vals);s=cs[b]+.5*w;evaluated+=1
                sparse_ids.append(idx);sparse_c.append(cs[b]);sparse_w.append(w)
                if w>upper+1e-9:raise RuntimeError('invalid word upper bound')
                if s>localbest or (s==localbest and idx<localid):localbest=s;localid=idx
                if s>best:
                    best=s;bestid=idx;ties.clear();ties.append(idx)
                elif s==best:
                    ties.append(idx)
                    if bestid<0 or idx<bestid:bestid=idx
            row=(pi-pstart)*3+m
            stats[row,0]=pi;stats[row,1]=m;stats[row,2]=cmax;stats[row,3]=upper
            stats[row,4]=evaluated;stats[row,5]=256-evaluated;stats[row,6]=cmin
            stats[row,7]=localbest;stats[row,8]=localid
    return best,bestid,np.array(ties,np.int64),stats,np.array(sparse_ids,np.int64),np.array(sparse_c),np.array(sparse_w)

@njit(cache=True,nogil=True)
def brute_block(g,lp,ch,v,p8,q,letter,pstart,pstop):
    out=np.empty(((pstop-pstart)*768,2),np.float64);buf=np.empty(len(g),np.int64)
    for pi in range(pstart,pstop):
        for m in range(3):
            for b in range(256):
                for t in range(len(g)):
                    z=g[t];o=z//3;c=z%3
                    if b>>o&1:c=2-c
                    buf[t]=letter[3*p8[pi,o]+q[m,c]]
                idx=(pi-pstart)*768+m*256+b
                out[idx,0]=char_score(buf,lp);out[idx,1]=fast_word(buf,ch,v)
    return out
