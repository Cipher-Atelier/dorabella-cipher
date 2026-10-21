"""Post-primary diagnostics, separately frozen and explicitly exploratory.
Sensitivity to pair selection and fixed per-row arc/polarity margins.
Also includes the two mixed readings, never treated as new historical witnesses.
"""
from pathlib import Path
import sys,json,hashlib,math
from collections import Counter
from fractions import Fraction
import numpy as np
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
sys.path.insert(0,str(HERE))
from exact_study import dump, vector_pairs, le_exact, enumerate_strings, describe, ROWS, vals

def condition_masks(a,s):
    sa=np.asarray(s)[None,:]
    out={}
    for attr,name,classes in [('arcs','same_row_arc_histograms',range(3)),('polarity','same_row_polarity_counts',range(2))]:
        x=a%3 if attr=='arcs' else a//12
        y=sa%3 if attr=='arcs' else sa//12
        ok=np.ones(len(a),bool)
        for start,end in ROWS:
            for c in classes:ok &= np.sum(x[:,start:end]==c,axis=1)==np.sum(y[:,start:end]==c)
        out[name]=ok
    out['same_row_arcs_and_polarity']=out['same_row_arc_histograms']&out['same_row_polarity_counts']
    return out

def analyze(a,s):
    p=vector_pairs(a);obs=vector_pairs(np.asarray(s)[None,:])[0]
    primary=le_exact(p[:,:2].sum(axis=1),obs[:2].sum(axis=0))
    # Best pair chosen for EACH null, not only for the real record.
    pairs=[(0,1),(0,2),(1,2)]; best=p[:,0]+p[:,1]
    for i,j in pairs[1:]:
        cand=p[:,i]+p[:,j];choose=le_exact(cand,best);best[choose]=cand[choose]
    realbest=obs[0]+obs[1]
    for i,j in pairs[1:]:
        cand=obs[i]+obs[j]
        if le_exact(cand,realbest):realbest=cand
    selected=le_exact(best,realbest)
    res={'best_pair_among_all_three':{'le':int(selected.sum()),'n':len(a),'conditional_fraction':float(selected.mean()),'real_2T_A_B':realbest.tolist()},'conditional_margins':{}}
    for name,mask in condition_masks(a,s).items():
        n=int(mask.sum());k=int(np.sum(primary&mask))
        res['conditional_margins'][name]={'support':n,'le':k,'conditional_fraction':k/n if n else None,'fraction':str(Fraction(k,n)) if n else None,'scope':'complete subset of trigram ensemble; low support is a limitation'}
    # Holding each row's full glyph multiset fixes vector sums exactly, regardless of order.
    rng=np.random.default_rng(20261001803)
    shuffled=np.tile(np.asarray(s),(1000,1))
    for row in shuffled:
        for start,end in ROWS:rng.shuffle(row[start:end])
    assert np.all(vector_pairs(shuffled)==obs)
    res['within_row_shuffles_checked_identical_sums']=1000
    # Independent floating trigonometric implementation (audit only; ranks use integers).
    o=a//3;w=a%3+1;unit=np.exp(1j*o*math.pi/4)*w
    actual=np.array([np.abs(unit[:,start:end].sum(axis=1))**2 for start,end in ROWS]).T
    res['max_squared_radius_error_against_complex_exp']=float(np.max(np.abs(actual-vals(p))))
    assert res['max_squared_radius_error_against_complex_exp']<1e-9
    return res

def main():
    frozen=json.loads((HERE/'frozen_sensitivity_protocol.json').read_text())
    for rel,sha in frozen['sha256'].items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==sha
    cs=[x for x in json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'] if x['kind']=='real']
    result={'protocol':frozen['protocol'],'cases':{}}
    for c in cs:
        a=np.load(HERE/'results'/f'{c["id"]}_trigrams.npz')['sequences']
        result['cases'][c['id']]=analyze(a,c['glyph'])
    h=cs[0]['glyph'];t=cs[1]['glyph'];assert [i for i in range(87) if h[i]!=t[i]]==[33,77]
    for pos in (33,77):
        g=h.copy();g[pos]=t[pos];name=f'hauer_plus_hart_at_{pos+1}'
        a,enumeration=enumerate_strings(g,3,name+'_trigrams')
        descript,measures=describe(a,g)
        result['cases'][name]={'status':'artificial mixed reading, NOT independent transcription','enumeration':enumeration,'analysis':descript,'sensitivity':analyze(a,g)}
        np.savez_compressed(HERE/'results'/f'{name}_trigram_measures.npz',**measures)
    dump(HERE/'results'/'sensitivity_summary.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
