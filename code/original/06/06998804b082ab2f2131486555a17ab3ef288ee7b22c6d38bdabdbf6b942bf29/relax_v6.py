"""Exploratory bounded relaxation of one-glyph/one-distinct-letter:
identity; remove every occurrence of up to two types (global nulls);
or merge exactly one pair of glyph types as homophones. Never position edits.
This changes the ciphertext model. It is NOT a strict bijective substitution.
"""
import itertools,json,time,hashlib,argparse
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from model_v5 import ROOT
from automata import canonical
from language import build_model,stable_seed
from fastsolve import solve_fast
from wordsearch_v4 import WordSearch
OUT=ROOT/'results/v6/relax';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'id':'bounded-null-or-one-homophone-pair-v6','screen':[8,16000,24],'middle':[32,20000,8],
 'final':[128,20000],'word':{'restarts':64,'iterations':16000},'null_types':'0,1 or2 present glyph types, globally removed',
 'merge':'exactly one pair of present types; no simultaneous null+merge','normalization':'mean scores by decoded length',
 'null_controls':19,'null_seed':20260926067,'positive_status':'not benchmarked; exploratory search; no exclusion claim'}

def variants(glyph):
    types=sorted(set(glyph.tolist()));raw=[]
    for n in (0,1,2):
        for combo in itertools.combinations(types,n):
            keep=np.flatnonzero(~np.isin(glyph,combo));seq=canonical(glyph[keep])
            raw.append((seq,dict(kind='null',types=list(map(int,combo))),keep))
    for a,b in itertools.combinations(types,2):
        g=glyph.copy();g[g==b]=a;raw.append((canonical(g),dict(kind='merge',types=[int(a),int(b)]),np.arange(87)))
    bank={}
    for s,r,keep in raw:
        key=s.tobytes()
        if key not in bank:bank[key]=(s,r,keep)
    return list(bank.values()),len(raw)

def make_cases():
    old=json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'];out=[]
    for z in old:
        if z['kind']=='real':out.append(dict(id=z['id'],kind='real',glyph=(3*np.array(z['orientation'])+z['arcs']).tolist()))
    rng=np.random.default_rng(PROTOCOL['null_seed']);real=out.copy()
    for j in range(PROTOCOL['null_controls']):
        idx=rng.permutation(87)
        for r in real:out.append(dict(id=r['id'].replace('_real',f'_null_{j:02d}'),kind='null',pair=j,glyph=np.array(r['glyph'])[idx].tolist(),permutation=idx.tolist()))
    data=dict(protocol=PROTOCOL,cases=out);p=OUT/'inputs.json'
    if p.exists():assert json.loads(p.read_text())==data
    else:p.write_text(json.dumps(data,indent=2))
    return out

def run_case(x,model,engine):
    dest=OUT/(x['id']+'.json')
    if dest.exists():return json.loads(dest.read_text())
    t=time.monotonic();g=np.array(x['glyph']);v,n=variants(g);lp,p1=model;K=len(v);scores=np.full(K,-1e100);keys=[None]*K
    selected=list(range(K));snaps=[]
    for stage in ('screen','middle','final'):
        conf=PROTOCOL[stage]
        for j in selected:
            seq=v[j][0];sc,key=solve_fast(seq,lp,p1,conf[0],conf[1],stable_seed(seq,'relax_v6_'+stage));sc/=len(seq)-3
            if sc>scores[j]:scores[j]=sc;keys[j]=key
        snaps.append(dict(stage=stage,selected=selected.copy(),scores=scores.tolist()))
        if len(conf)==3:selected=sorted(set(sorted(selected,key=lambda j:(-scores[j],v[j][0].tobytes()))[:conf[2]]+[0]))
    finals=[]
    for j in selected:
        seq,r,keep=v[j];z=engine.run(seq,keys[j][seq],PROTOCOL['word'],tag='relax_v6_word')
        z.update(index=j,rule=r,keep_indices=keep.tolist(),output_length=len(seq));finals.append(z)
    finals.sort(key=lambda r:(-r['score'],r['decoded']));best=finals[0];ii=next(r for r in finals if r['index']==0)
    rec=dict(id=x['id'],kind=x['kind'],best_score=best['score'],identity_score=ii['score'],gain=best['score']-ii['score'],
        best_text=''.join(chr(v+97) for v in best['decoded']),n_definitions=n,distinct_patterns=K,finalists=finals,stages=snaps,seconds=time.monotonic()-t)
    dest.write_text(json.dumps(rec,indent=2));print(x['id'],round(rec['best_score'],5),rec['best_text'],best['rule'],round(rec['seconds'],2),flush=True)
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['real','null','all'],default='real');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    cs=make_cases();model=build_model();engine=WordSearch()
    files=['relax_v6.py','wordsearch_v4.py','fastsolve.py','data/english_model.npz','results/v6/relax/inputs.json']
    freeze=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},dictionary=engine.scorer.metadata)
    p=OUT/'frozen.json'
    if p.exists():assert json.loads(p.read_text())==freeze
    else:p.write_text(json.dumps(freeze,indent=2))
    solve_fast(np.zeros(87,np.int64),*model,1,1,1)
    todo=[z for z in cs if (a.mode=='all' or z['kind']==a.mode) and not (OUT/(z['id']+'.json')).exists()]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(lambda z:run_case(z,model,engine),todo))
if __name__=='__main__':main()
