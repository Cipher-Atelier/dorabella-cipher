"""Reproducible geometric audit; not a Dorabella decipherment.
Python >=3.10, numpy, scipy, numba. All reported Monte Carlo samples are run.
"""
from pathlib import Path
import argparse, json, hashlib
import numpy as np
from numba import njit
from scipy.stats import beta
ROOT = Path(__file__).resolve().parent

def load_cipher():
    rows=[line.split() for line in (ROOT/'data/dorabella_smp2021.txt').read_text().splitlines() if line.strip()]
    tok=sum(rows,[])
    assert len(tok)==87 and all(len(t)==2 and t[0] in 'ABCDEFGH' and t[1] in '123' for t in tok)
    ori=np.array([ord(t[0])-65 for t in tok],dtype=np.int64)
    arcs=np.array([int(t[1])-1 for t in tok],dtype=np.int64)
    return tok,rows,ori,arcs

def pairings(items):
    if not items:
        yield []; return
    first=items[0]
    for i in range(1,len(items)):
        for rest in pairings(items[1:i]+items[i+1:]):
            yield [(first,items[i])]+rest

def mi(table):
    t=np.asarray(table,dtype=float);n=t.sum(); expected=t.sum(1)[:,None]*t.sum(0)[None,:]
    nz=t>0
    return float(np.sum(t[nz]/n*np.log2(t[nz]*n/expected[nz])))

@njit(cache=True)
def mi_numba(tab):
    n=tab.sum();nr,nc=tab.shape; val=0.
    for i in range(nr):
        for j in range(nc):
            v=tab[i,j]
            if v>0: val+=v/n*np.log2(v*n/(tab[i,:].sum()*tab[:,j].sum()))
    return val

@njit(cache=True)
def shuffle_tests(ori,arcs,pairs,N,seed):
    np.random.seed(seed);n=len(ori)
    scores=np.zeros((N,3),np.int16) # same axis; max over pairings; within-row edges
    line_mask=np.ones(n-1,np.bool_);line_mask[28]=False;line_mask[59]=False
    for k in range(N):
        z=np.random.permutation(ori)
        T=np.zeros((8,8),np.int16)
        sa=0;sa_line=0
        for i in range(n-1):
            T[z[i],z[i+1]]+=1
            if z[i]%4==z[i+1]%4:
                sa+=1
                if line_mask[i]:sa_line+=1
        diag=0
        for i in range(8):diag+=T[i,i]
        best=0
        for p in range(len(pairs)):
            s=diag
            for j in range(4):
                u,v=pairs[p,j];s+=T[u,v]+T[v,u]
            if s>best:best=s
        scores[k,0]=sa;scores[k,1]=best;scores[k,2]=sa_line
    return scores

@njit(cache=True)
def conditional_tests(ori,arcs,N,seed):
    np.random.seed(seed);n=len(ori);axis=ori%4;base=3*axis+arcs;pol=ori//4
    scores=np.zeros((N,4),np.int16)
    for k in range(N):
        q=pol.copy()
        # Permute polarity only among the occurrences of the same base glyph.
        # This preserves the entire base sequence AND exact full-glyph frequencies.
        for b in range(12):
            idx=np.where(base==b)[0]
            q[idx]=np.random.permutation(q[idx])
        op=0;mir=0;flips=0
        for i in range(n-1):
            if q[i]!=q[i+1]:
                flips+=1
                if axis[i]==axis[i+1]:
                    op+=1
                    if arcs[i]==arcs[i+1]:mir+=1
        # Permute orientation only within each arc-count stratum.
        # Preserves arc sequence, glyph frequencies, and axis/arc contingency table.
        a=axis.copy()
        for c in range(3):
            idx=np.where(arcs==c)[0]
            a[idx]=np.random.permutation(a[idx])
        sa=0
        for i in range(n-1):
            if a[i]==a[i+1]:sa+=1
        scores[k,0]=op;scores[k,1]=mir;scores[k,2]=flips;scores[k,3]=sa
    return scores

@njit(cache=True)
def relabel_tests(ori,arcs,N,seed):
    np.random.seed(seed);types=3*ori+arcs;n=len(ori)
    out=np.empty((N,2),np.float64)
    for k in range(N):
        key=np.random.permutation(24)
        z=key[types];ax=(z//3)%4;arc=z%3
        s=0;tab=np.zeros((4,3),np.int64)
        for i in range(n):
            tab[ax[i],arc[i]]+=1
            if i>0 and ax[i]==ax[i-1]:s+=1
        out[k,0]=s;out[k,1]=mi_numba(tab)
    return out

def tail(arr,threshold):
    N=len(arr);hits=int(np.sum(arr>=threshold-1e-12))
    lo=0. if hits==0 else float(beta.ppf(.025,hits,N-hits+1))
    hi=1. if hits==N else float(beta.ppf(.975,hits+1,N-hits))
    return dict(n=N,hits=hits,threshold=float(threshold),p_plus_one=(hits+1)/(N+1),
                mc_probability_interval95=[lo,hi],null_mean=float(np.mean(arr)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--n',type=int,default=200000)
    ap.add_argument('--relabel-n',type=int,default=1000000);args=ap.parse_args()
    tok,rows,o,c=load_cipher();a=o%4;p=o//4;base=3*a+c
    pair=np.array(list(pairings(list(range(8)))),dtype=np.int64)
    pair_results=[]
    for pr in pair:
        mapping=np.empty(8,int)
        for idx,(u,v) in enumerate(pr):mapping[u]=mapping[v]=idx
        z=mapping[o];s=int(np.sum(z[1:]==z[:-1]));tab=np.bincount(z*3+c,minlength=12).reshape(4,3)
        pair_results.append({'pairs':pr.tolist(),'same_axis':s,'mi_axis_arcs_bits':mi(tab)})
    tab=np.bincount(a*3+c,minlength=12).reshape(4,3)
    T=np.bincount(4*a[:-1]+a[1:],minlength=16).reshape(4,4)
    obs={'n':len(o),'line_lengths_in_printed_transcription':list(map(len,rows)),
         'distinct_glyphs':len(set(tok)),'same_axis':int(np.sum(a[1:]==a[:-1])),
         'opposite':int(np.sum((o[1:]-o[:-1])%8==4)),
         'exact_mirror':int(np.sum(((o[1:]-o[:-1])%8==4)&(c[1:]==c[:-1]))),
         'polarity_changes':int(np.sum(p[1:]!=p[:-1])),
         'polarity_counts':np.bincount(p).tolist(),'axis_arc_table':tab.tolist(),
         'axis_transition_table':T.tolist(),'mi_axis_arcs_bits':mi(tab),
         'mi_axis_next_bits':mi(T),'distinct_bases':len(set(base)),
         'same_axis_excluding_printed_line_edges':int(np.sum((a[1:]==a[:-1])[np.array([i not in (28,59) for i in range(86)])]))}
    print('OBSERVED',json.dumps(obs),flush=True)
    scores=shuffle_tests(o,c,pair,args.n,20260925)
    cond=conditional_tests(o,c,args.n,20260926)
    relab=relabel_tests(o,c,args.relabel_n,20260927)
    tests={'shuffle_fixed_axis':tail(scores[:,0],obs['same_axis']),
           'shuffle_best_of_105_pairings':tail(scores[:,1],obs['same_axis']),
           'shuffle_no_line_edges':tail(scores[:,2],obs['same_axis_excluding_printed_line_edges']),
           'polarity_within_base_opposites':tail(cond[:,0],obs['opposite']),
           'polarity_within_base_exact_mirrors':tail(cond[:,1],obs['exact_mirror']),
           'polarity_within_base_all_flips':tail(cond[:,2],obs['polarity_changes']),
           'axis_shuffled_within_arcs':tail(cond[:,3],obs['same_axis']),
           'relabel_24_glyphs_same_axis':tail(relab[:,0],obs['same_axis']),
           'relabel_24_glyphs_mi':tail(relab[:,1],obs['mi_axis_arcs_bits']),
           'relabel_joint_descriptive_only':tail(((relab[:,0]>=obs['same_axis'])&(relab[:,1]>=obs['mi_axis_arcs_bits']-1e-12)).astype(int),1)}
    res={'source':'Hauer et al., Dorabella Cipher as Musical Inspiration (SMP 2021), Figure 2',
         'source_url':'https://aclanthology.org/2021.smp-1.5.pdf',
         'text_sha256':hashlib.sha256((ROOT/'data/dorabella_smp2021.txt').read_bytes()).hexdigest(),
         'observed':obs,'tests':tests,'all_105_pairings':pair_results,
         'limitations':['All Dorabella analysis is exploratory; max-over-105 corrects only the stated pairing search, not the full research history.',
                       'Permutation tails are probabilities under specific reference models, not posterior probabilities of hypotheses.',
                       'A fixed alphabet geometry does not by itself imply a stateful cipher.',
                       'Line splits are those printed in Figure 2; no dot-driven reset is assumed.']}
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'results/audit.json').write_text(json.dumps(res,indent=2))
    np.savez_compressed(ROOT/'results/audit_null_arrays.npz',shuffle=scores,conditional=cond,relabel=relab)
    print(json.dumps(tests,indent=2),flush=True)
if __name__=='__main__':main()
