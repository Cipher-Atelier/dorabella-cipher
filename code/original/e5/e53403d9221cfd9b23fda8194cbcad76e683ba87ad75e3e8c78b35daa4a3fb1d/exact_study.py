"""Finite conditional geometry/crib audit; NOT a language-score or decipherment test.
Uses the original round7 data and exact matrix-tree cardinality routine.
Writes ONLY beneath round8; all generated null strings are retained losslessly.
"""
from pathlib import Path
import sys, json, math, subprocess, hashlib, itertools, time
from collections import Counter
from fractions import Fraction
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from count_bigrams_v7 import count_strings

CRIB='FORLIMALVERN'
ROWS=((0,29),(29,60),(60,87))
COEFF=np.array([[1,0,0,0],[0,0,1,1],[0,1,0,0],[0,0,-1,1],[-1,0,0,0],[0,0,-1,-1],[0,-1,0,0],[0,0,1,-1]],dtype=np.int64)

def dump(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def grams(s,k):return [tuple(map(int,s[i:i+k])) for i in range(len(s)-k+1)]

def enumerate_strings(s,k,stem):
    expected,trees=count_strings(grams(s,k-1))
    assert expected<=1000000, 'refuse unbounded enumeration'
    inp=HERE/'results'/f'{stem}.input.txt'; binary=HERE/'results'/f'{stem}.bin'
    inp.write_text(f'{len(s)} {k}\n'+ ' '.join(map(str,s))+'\n')
    p=subprocess.run([str(HERE/'enumerate_kgrams'),str(inp),str(binary),str(expected)],check=True,text=True,capture_output=True)
    a=np.fromfile(binary,np.uint8).reshape(-1,len(s))
    assert len(a)==expected
    assert len(np.unique(a,axis=0))==expected
    assert np.count_nonzero(np.all(a==s,axis=1))==1
    target=np.sort(np.array([sum(g*256**j for j,g in enumerate(t)) for t in grams(s,k)],np.int64))
    for batch in np.array_split(a,max(1,math.ceil(len(a)/4096))):
        code=np.zeros((len(batch),len(s)-k+1),np.int64)
        for j in range(k):code+=batch[:,j:j+len(s)-k+1].astype(np.int64)*256**j
        assert np.all(np.sort(code,axis=1)==target)
        assert np.all(batch[:,:k-1]==np.asarray(s)[:k-1])
        assert np.all(batch[:,-k+1:]==np.asarray(s)[-k+1:])
        assert np.all(np.sort(batch,axis=1)==np.sort(s))
    np.savez_compressed(HERE/'results'/f'{stem}.npz',sequences=a)
    binary.unlink()
    return a,{'count':int(expected),'trees':int(trees),'enumerator':json.loads(p.stdout),'all_gram_counts_endpoints_unigrams_verified':True,'all_unique':True,'original_occurrences':1}

def vector_pairs(a):
    # Output integer A,B with 2*radius_squared = A+B*sqrt(2), per row.
    vectors=COEFF[a//3]*(a%3+1)[:,:,None]
    pairs=[]
    for start,end in ROWS:
        p=vectors[:,start:end].sum(axis=1);x,y,dx,dy=p.T
        pairs.append(np.column_stack([2*(x*x+y*y)+dx*dx+dy*dy,2*(x*dx+y*dy)]))
    return np.stack(pairs,axis=1)

def le_exact(p,q):
    # Exact comparison in Z[sqrt(2)], no floating-point thresholding.
    a=p[...,0]-q[...,0];b=p[...,1]-q[...,1]
    return ((a<=0)&(b<=0)) | ((a>=0)&(b<0)&(a*a<=2*b*b)) | ((a<0)&(b>=0)&(a*a>=2*b*b))

def vals(p):return (p[...,0]+p[...,1]*math.sqrt(2))/2

def crib_distances(a):
    w=np.lib.stride_tricks.sliding_window_view(a,len(CRIB),axis=1)
    d=np.zeros(w.shape[:2],np.int16)
    for i in range(len(CRIB)):
        for j in range(i+1,len(CRIB)):
            d+=(w[:,:,i]==w[:,:,j]) != (CRIB[i]==CRIB[j])
    return d

def exact_unigram_crib(s):
    # Distinct glyph assignments to d labelled double blocks and r labelled singleton blocks.
    counts=list(Counter(s).values())
    def weight(d,r):
        dp={(0,0):1}
        for c in counts:
            nxt=dp.copy()
            for (i,j),w in dp.items():
                if i<d:nxt[i+1,j]=nxt.get((i+1,j),0)+w*c*(c-1)
                if j<r:nxt[i,j+1]=nxt.get((i,j+1),0)+w*c
            dp=nxt
        return dp.get((d,r),0)*math.factorial(d)*math.factorial(r)
    den=math.factorial(len(s))//math.factorial(len(s)-len(CRIB))
    parts={'exact_pattern':weight(2,8),'one_repeat_missing':2*weight(1,10),'one_extra_singleton_pair':28*weight(3,6)}
    p=Fraction(sum(parts.values()),den)
    return {'distance_le_1_exact_probability':float(p),'fraction':str(p),'favourable_ordered_draws':str(sum(parts.values())),'all_ordered_draws':str(den),'components':{k:str(v) for k,v in parts.items()},'scope':'fixed 12-position window, fixed crib, unconditioned multiset permutations; not a corrected discovery p-value'}

def describe(a,s):
    pp=vector_pairs(np.asarray(s,dtype=np.uint8)[None,:]);obs=pp[0]
    observed_d=crib_distances(np.asarray(s,dtype=np.uint8)[None,:])[0]
    # Process in batches to keep memory bounded.
    collected={k:[] for k in ['geometry_pairs','crib_prefix','crib_min']}
    for block in np.array_split(a,max(1,math.ceil(len(a)/4096))):
        pairs=vector_pairs(block);d=crib_distances(block)
        collected['geometry_pairs'].append(pairs)
        collected['crib_prefix'].append(d[:,0]);collected['crib_min'].append(d.min(axis=1))
    collected={k:np.concatenate(v) for k,v in collected.items()}
    pair=collected['geometry_pairs'];total=len(a)
    def tail(values,threshold):
        k=int(np.sum(le_exact(values,threshold)));eq=int(np.sum(np.all(values==threshold,axis=-1)))
        return {'le':k,'equal':eq,'n':total,'exact_fraction':str(Fraction(k,total)),'conditional_fraction':k/total,'less_is_more_closed':True}
    geom={
        'first_two_sum_squared_radius':tail(pair[:,:2].sum(axis=1),obs[:2].sum(axis=0)),
        'all_three_sum_squared_radius':tail(pair.sum(axis=1),obs.sum(axis=0)),
        'row1_squared_radius':tail(pair[:,0],obs[0]),
        'row2_squared_radius':tail(pair[:,1],obs[1]),
        'row3_squared_radius':tail(pair[:,2],obs[2])}
    k=int(np.sum(le_exact(pair[:,0],obs[0])&le_exact(pair[:,1],obs[1])))
    geom['first_two_joint_orthant']={'le_both':k,'n':total,'fraction':k/total,'scope':'descriptive joint lower orthant frequency, not itself a calibrated p-value'}
    prefix=collected['crib_prefix'];minim=collected['crib_min']
    changed=np.sum(a!=np.asarray(s),axis=1)
    num_per_pos=[len(np.unique(a[:,i])) for i in range(a.shape[1])]
    res={'n':total,'geometry':geom,'header':{
        'prefix_distance':int(observed_d[0]),'all_window_distances':observed_d.tolist(),
        'best_window_1_based':(np.flatnonzero(observed_d==observed_d.min())+1).tolist(),
        'prefix_le_observed':int(np.sum(prefix<=observed_d[0])),
        'any_window_le_observed':int(np.sum(minim<=observed_d[0])),
        'prefix_histogram':dict(sorted(Counter(map(int,prefix)).items())),
        'minimum_window_histogram':dict(sorted(Counter(map(int,minim)).items()))},
        'observed_row_2r2_A_B':obs.tolist(),'observed_row_radii':np.sqrt(vals(obs)).tolist(),
        'observed_primary_T12':float(vals(obs[:2].sum(axis=0))),
        'position_change_mean':float(changed.mean()),'max_positions_changed':int(changed.max()),
        'fixed_positions_1_based':[i+1 for i,n in enumerate(num_per_pos) if n==1],
        'distinct_symbols_per_position':num_per_pos,
        'different_12_symbol_prefixes':int(len(np.unique(a[:,:12],axis=0)))}
    return res,collected

def toy_checks():
    records=[]
    for i,(s,k) in enumerate([([0,1,0,2,0,1,2,0],2),([0,1,0,2,0,1,2,0],3),([0,0,1,0,0,1,0,0],3),([0,0,0],2),([0,1,2],2)]):
        brute={p for p in itertools.permutations(s) if p[:k-1]==tuple(s[:k-1]) and p[-k+1:]==tuple(s[-k+1:]) and Counter(grams(p,k))==Counter(grams(s,k))}
        a,r=enumerate_strings(s,k,f'toy_{i}');assert set(map(tuple,a))==brute
        records.append({'s':s,'k':k,'count':len(brute),'matches_bruteforce':True})
    # Comparator checked against high precision independent arithmetic.
    import decimal
    with decimal.localcontext() as ctx:
        ctx.prec=80;rt=decimal.Decimal(2).sqrt()
        for A in range(-100,101):
            for B in range(-100,101):
                got=bool(le_exact(np.array([A,B]),np.array([0,0])))
                assert got==(decimal.Decimal(A)+decimal.Decimal(B)*rt<=0)
    return {'enumeration_toys':records,'exact_comparator_cases':201**2}

def main():
    frozen=json.loads((HERE/'frozen_exact_protocol.json').read_text())
    for path,digest in frozen['sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    subprocess.run(['g++','-O3','-std=c++17',str(HERE/'enumerate_kgrams.cpp'),'-o',str(HERE/'enumerate_kgrams')],check=True)
    result={'protocol':frozen['protocol'],'toy_checks':toy_checks(),'cases':{}}
    cases=[x for x in json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'] if x['kind']=='real']
    for c in cases:
        s=c['glyph'];a,r=enumerate_strings(s,3,c['id']+'_trigrams')
        card4=count_strings(grams(s,3))[0];assert card4==1
        analysis,measures=describe(a,s)
        np.savez_compressed(HERE/'results'/f'{c["id"]}_trigram_measures.npz',**measures)
        result['cases'][c['id']]={'trigram_enumeration':r,'fourgram_cardinality':int(card4),'analysis':analysis,'fixed_window_unigram_crib':exact_unigram_crib(s)}
        dump(HERE/'results'/'exact_summary.json',result)
        print(c['id'],json.dumps(result['cases'][c['id']],ensure_ascii=False),flush=True)
    dump(HERE/'results'/'exact_summary.json',result)
if __name__=='__main__':main()
