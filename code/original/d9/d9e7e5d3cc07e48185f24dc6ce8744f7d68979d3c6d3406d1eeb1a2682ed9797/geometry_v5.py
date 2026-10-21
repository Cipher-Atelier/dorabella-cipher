"""Sensitivity of geometry to two published transcriptions and fixed alphabetic keys.
No new blind annotation. Runs all four combinations of the two differing positions.
Monte Carlo corrects only an explicitly defined pairing search, not research history.
"""
import json, itertools
import numpy as np
from model_v5 import ROOT,OUT,ALPHABET,normalise,sha
from run_v5 import HART_ROWS
from audit import load_cipher,pairings,mi,shuffle_tests,tail
from language import documents,corpus_path


def stats(o,c,pairs):
    axis=o%4
    mask=np.ones(86,dtype=bool);mask[[28,59]]=False
    tab=np.bincount(3*axis+c,minlength=12).reshape(4,3)
    T=np.bincount(4*axis[:-1]+axis[1:],minlength=16).reshape(4,4)
    sa=int(np.sum(axis[:-1]==axis[1:]));ms=mi(tab);pr=[]
    for pairs_i in pairs:
        mapping=np.empty(8,int)
        for a,(u,v) in enumerate(pairs_i):mapping[u]=mapping[v]=a
        z=mapping[o];table=np.bincount(3*z+c,minlength=12).reshape(4,3)
        pr.append(dict(pairs=pairs_i.tolist(),same_axis=int(np.sum(z[:-1]==z[1:])),mi_axis_arcs=mi(table)))
    return dict(same_axis=sa,opposite=int(np.sum((o[1:]-o[:-1])%8==4)),
          exact_mirrors=int(np.sum(((o[1:]-o[:-1])%8==4)&(c[1:]==c[:-1]))),
          same_axis_without_line_edges=int(np.sum((axis[1:]==axis[:-1])[mask])),
          mi_axis_arcs=ms,axis_arc_table=tab.tolist(),axis_transition_table=T.tolist(),
          same_axis_pairing_rank=1+sum(x['same_axis']>sa for x in pr),
          same_axis_pairings_tied=sum(x['same_axis']==sa for x in pr),
          mi_pairing_rank=1+sum(x['mi_axis_arcs']>ms+1e-12 for x in pr),
          mi_pairings_tied=sum(abs(x['mi_axis_arcs']-ms)<1e-12 for x in pr),all_pairings=pr)


def main():
    tok,rows,o,c=load_cipher();hz=np.array([ALPHABET.index(x) for x in ''.join(HART_ROWS)])
    ho,hc=hz//3,hz%3;assert np.array_equal(c,hc)
    differences=np.flatnonzero(o!=ho);assert differences.tolist()==[33,77]
    diffs=[dict(position=int(i+1),hauer=tok[i],hart=chr(int(ho[i])+65)+str(int(c[i])+1)) for i in differences]
    pair=np.array(list(pairings(list(range(8)))));N=200000;seed=2026092606;variants={};arrays={}
    for bits in itertools.product((0,1),repeat=2):
        name=''.join(map(str,bits));oo=o.copy()
        for bit,i in zip(bits,differences):
            if bit:oo[i]=ho[i]
        observed=stats(oo,c,pair)
        arr=shuffle_tests(oo,c,pair,N,seed)
        arrays['variant_'+name]=arr
        variants[name]=dict(bits_take_hart_at_34_78=list(bits),orientation=oo.tolist(),arcs=c.tolist(),observed=observed,
             tests=dict(fixed_axes=tail(arr[:,0],observed['same_axis']),
                        best_of105_pairings=tail(arr[:,1],observed['same_axis']),
                        fixed_axes_no_line_edges=tail(arr[:,2],observed['same_axis_without_line_edges'])))
        print(name,{k:observed[k] for k in ('same_axis','opposite','exact_mirrors','same_axis_pairing_rank','mi_pairing_rank')},
              variants[name]['tests'],flush=True)
    historical=[]
    cases=json.loads((ROOT/'results/v4/inputs.json').read_text())['cases']
    for x in cases:
        if 'plaintext' not in x:continue
        plain=normalise(x['plaintext']);z=np.array([ALPHABET.index(ch.upper()) for ch in plain]);oo=z//3;cc=z%3
        s=stats(oo,cc,pair)
        historical.append(dict(id=x['id'],length=len(z),same_axis=s['same_axis'],
                 best_pairing_same_axis=max(a['same_axis'] for a in s['all_pairings'])))
    testpath=corpus_path('lee.cor');news=[]
    for docid,doc in enumerate(documents(testpath)):
        plain=normalise(doc)
        for start in range(0,len(plain)-86,87):
            z=np.array([ALPHABET.index(ch.upper()) for ch in plain[start:start+87]])
            axis=(z//3)%4
            news.append(dict(document=docid,start=start,same_axis=int(np.sum(axis[:-1]==axis[1:]))))
    def summarize(xs,key='same_axis'):
        a=np.array([x[key] for x in xs]);return dict(n=len(a),mean=float(a.mean()),minimum=int(a.min()),maximum=int(a.max()),
                                                      at_least41=int(np.sum(a>=41)))
    out=dict(source_differences=diffs,variant_meaning='0=Hauer; 1=Hartmeier; positions 34,78; 01/10 are synthetic mixtures, not publications',
       variants=variants,permutation_n=N,permutation_seed=seed,
       static_key=dict(alphabet=ALPHABET,orientation='alphabetic triples around 8 directions; reversal/global rotation do not affect same-axis statistic',
              historical=dict(summary=summarize(historical),records=historical,status='32 previously used excerpts; convenient regression sample'),
              historical_best_pairing=dict(summary=summarize(historical,'best_pairing_same_axis'),status='exploratory maximization over105 for each excerpt'),
              news=dict(summary=summarize(news),records=news,source_file=str(testpath),sha256=sha(testpath),
                        status='206 non-overlapping 87-letter windows from 50 documents; windows not independent')),
       caveats=['Two published readings are not independent blind reannotations; Hartmeier was among sources of Hauer consensus.',
                'Mixed variants do not adjudicate which glyph was actually drawn.',
                'No p-value below accounts for all historical researcher choices.',
                'Static tests do not exclude arbitrary monoalphabetic keys, atypical English, or other languages.'])
    np.savez_compressed(OUT/'geometry_nulls.npz',**arrays)
    (OUT/'geometry.json').write_text(json.dumps(out,indent=2))
    print(json.dumps({k:v['summary'] for k,v in out['static_key'].items() if isinstance(v,dict) and 'summary' in v},indent=2),flush=True)

if __name__=='__main__':main()
