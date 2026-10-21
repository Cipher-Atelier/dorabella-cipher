"""Explicit bounded reading-order family + arbitrary monoalphabetic substitution.
No symbol edits or stateful substitutions. Both permutation directions are included.
Heuristic key search, hence this does NOT exhaust all substitution keys.
"""
import json,time,hashlib,itertools,math,argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from automata import canonical
from language import build_model,stable_seed,score_key
from fastsolve import solve_fast
from wordsearch_v4 import WordSearch
from model_v5 import ROOT
OUT=ROOT/'results/v6/routes';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'family':'bounded-routes-and-substitution-v6','N':87,'widths':list(range(2,32)),
 'printed_rows':[29,31,27],'rectangular_styles':['row','row_snake','column','column_snake','diagonal','diagonal_snake','spiral'],
 'grid_reflections':4,'include_inverse_routes':True,'coprime_step_routes':'all step mod87; start fixed at zero',
 'screen':{'restarts':8,'iterations':16000,'keep':32},'middle':{'restarts':32,'iterations':20000,'keep':8},
 'final':{'restarts':128,'iterations':20000},'identity_always_included':True,
 'word':{'restarts':64,'iterations':16000},'null_pairs':19,'seed_null':20260926063,
 'n_positive':12,'seed_positive':20260926064,'positive_status':'old historical plaintexts, new random route/key; sensitivity only'}

def grid_route(M,style):
    H,W=M.shape
    if style==0:coords=[(r,c) for r in range(H) for c in range(W)]
    elif style==1:coords=[(r,c) for r in range(H) for c in (range(W) if r%2==0 else range(W-1,-1,-1))]
    elif style==2:coords=[(r,c) for c in range(W) for r in range(H)]
    elif style==3:coords=[(r,c) for c in range(W) for r in (range(H) if c%2==0 else range(H-1,-1,-1))]
    elif style in (4,5):
        coords=[]
        for s in range(H+W-1):
            part=[(r,s-r) for r in range(max(0,s-W+1),min(H,s+1))]
            if style==5 and s%2:part=part[::-1]
            coords.extend(part)
    else:
        coords=[];top,left,bottom,right=0,0,H-1,W-1
        while left<=right and top<=bottom:
            coords.extend((top,c) for c in range(left,right+1));top+=1
            coords.extend((r,right) for r in range(top,bottom+1));right-=1
            if top<=bottom:coords.extend((bottom,c) for c in range(right,left-1,-1));bottom-=1
            if left<=right:coords.extend((r,left) for r in range(bottom,top-1,-1));left+=1
    return np.array([M[r,c] for r,c in coords if M[r,c]>=0],np.int64)

def routes():
    bank={}
    def add(p,name):
        p=np.asarray(p,np.int64)
        assert np.array_equal(np.sort(p),np.arange(87)),(name,p)
        for q,n in ((p,name),(np.argsort(p),'inverse:'+name)):
            if q.tobytes() not in bank:bank[q.tobytes()]=(q,n)
    add(np.arange(87),'identity')
    rows=[np.arange(0,29),np.arange(29,60),np.arange(60,87)]
    for order in itertools.permutations(range(3)):
        for mask in range(8):
            r=[rows[j][::-1] if mask&(1<<j) else rows[j] for j in order]
            add(np.concatenate(r),f'printed-row-concat:{order}:{mask}')
            add([r[k][c] for c in range(31) for k in range(3) if c<len(r[k])],f'printed-column-weave:{order}:{mask}')
    for w in PROTOCOL['widths']:
        h=math.ceil(87/w);m=np.full(h*w,-1,np.int64);m[:87]=np.arange(87);m=m.reshape(h,w)
        for flipr,flipc in itertools.product(range(2),repeat=2):
            mm=m[::(-1 if flipr else 1),::(-1 if flipc else 1)]
            for style in range(7):add(grid_route(mm,style),f'grid:{w}:{flipr}:{flipc}:{style}')
    for k in range(1,87):
        if math.gcd(k,87)==1:add((k*np.arange(87))%87,f'step:{k}')
    return list(bank.values())

def create_cases(rr):
    old=json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'];real=[]
    for z in old:
        if z['kind']=='real':real.append(dict(id=z['id'],kind='real',glyph=(3*np.array(z['orientation'])+z['arcs']).tolist()))
    out=real.copy();rng=np.random.default_rng(PROTOCOL['seed_null'])
    for j in range(PROTOCOL['null_pairs']):
        idx=rng.permutation(87)
        for r in real:out.append(dict(id=r['id'].replace('_real',f'_null_{j:02d}'),kind='null',pair=j,glyph=np.array(r['glyph'])[idx].tolist(),permutation=idx.tolist()))
    rng=np.random.default_rng(PROTOCOL['seed_positive']);past=[z for z in old if z['kind']=='positive'][-12:]
    for j,z in enumerate(past):
        # Restore original unmerged plaintext from the previously archived input.
        plaintext=z['original_plaintext'].lower();truth=np.array([ord(a)-97 for a in plaintext]);eq=canonical(truth)
        assert eq.max()<24
        glyph=np.empty(87,np.int64);rid=int(rng.integers(1,len(rr)));p=rr[rid][0]
        glyph[p]=rng.permutation(24)[eq]
        out.append(dict(id=f'positive_{j:02d}',kind='positive',glyph=glyph.tolist(),plaintext=plaintext,
                         generating_route=rid,route_name=rr[rid][1],source=z['id']))
    data=dict(protocol=PROTOCOL,cases=out,routes=[dict(id=i,name=n,permutation=p.tolist()) for i,(p,n) in enumerate(rr)])
    dest=OUT/'inputs.json'
    if dest.exists():assert json.loads(dest.read_text())==data
    else:dest.write_text(json.dumps(data,indent=2))
    return out

def freeze(rr,engine):
    files=['routes_v6.py','fastsolve.py','wordsearch_v4.py','wordscore_v3.py','wordpolish_v3.py','language.py',
           'data/english_model.npz','results/v6/routes/inputs.json']
    data=dict(protocol=PROTOCOL,n_routes=len(rr),hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},dictionary=engine.scorer.metadata)
    dest=OUT/'frozen.json'
    if dest.exists():assert json.loads(dest.read_text())==data,'Protocol mismatch'
    else:dest.write_text(json.dumps(data,indent=2))

def run_case(case,rr,model,engine):
    dest=OUT/(case['id']+'.json')
    if dest.exists():return json.loads(dest.read_text())
    start=time.monotonic();glyph=np.array(case['glyph']);lp,p1=model;seqs=[];names=[];lookup={};route_groups=[]
    for i,(p,name) in enumerate(rr):
        seq=canonical(glyph[p]);key=seq.tobytes()
        if key not in lookup:lookup[key]=len(seqs);seqs.append(seq);names.append(i);route_groups.append([i])
        else:route_groups[lookup[key]].append(i)
    raw=canonical(glyph);ii=lookup[raw.tobytes()];K=len(seqs);scores=np.full(K,-1e100);keys=[None]*K;snapshots=[];selected=list(range(K))
    for stage in ('screen','middle','final'):
        conf=PROTOCOL[stage]
        for j in selected:
            seq=seqs[j];sc,key=solve_fast(seq,lp,p1,conf['restarts'],conf['iterations'],stable_seed(seq,'route_v6_'+stage))
            if sc>scores[j]:scores[j]=sc;keys[j]=key
        snapshots.append(dict(stage=stage,selected=selected.copy(),scores=(scores/84).tolist()))
        if 'keep' in conf:
            selected=sorted(set(sorted(selected,key=lambda j:(-scores[j],seqs[j].tobytes()))[:conf['keep']]+[ii]))
    finalists=[]
    for j in selected:
        q=engine.run(seqs[j],keys[j][seqs[j]],PROTOCOL['word'],tag='route_v6_word')
        q.update(pattern_index=j,representative_route=names[j],route_name=rr[names[j]][1],equivalent_route_indices=route_groups[j])
        finalists.append(q)
    finalists.sort(key=lambda q:(-q['score'],q['decoded']));best=finalists[0];identity=next(q for q in finalists if q['pattern_index']==ii)
    rec=dict(id=case['id'],kind=case['kind'],best_score=best['score'],identity_score=identity['score'],gain=best['score']-identity['score'],
        best_text=''.join(chr(v+97) for v in best['decoded']),n_routes=len(rr),distinct_patterns=K,finalists=finalists,stages=snapshots,seconds=time.monotonic()-start)
    if case['kind']=='positive':
        rec['accuracy']=sum(a==b for a,b in zip(rec['best_text'],case['plaintext']))/87
        true_j=lookup[canonical(glyph[rr[case['generating_route']][0]]).tobytes()]
        rec['true_pattern_index']=true_j;rec['true_pattern_finalist']=true_j in selected
        rec['true_pattern_ranks']=[1+sum(v>s['scores'][true_j]+1e-10 for v in s['scores']) for s in snapshots]
    dest.write_text(json.dumps(rec,indent=2));print(case['id'],round(rec['best_score'],6),rec.get('accuracy',''),rec['best_text'],round(rec['seconds'],2),flush=True)
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['real','positive','null','all'],default='real');ap.add_argument('--workers',type=int,default=4);ap.add_argument('--max-new',type=int);args=ap.parse_args()
    rr=routes();cases=create_cases(rr);model=build_model();engine=WordSearch();freeze(rr,engine)
    print('routes',len(rr),flush=True);solve_fast(np.zeros(87,np.int64),model[0],model[1],1,1,1)
    todo=[z for z in cases if (args.mode=='all' or args.mode==z['kind']) and not (OUT/(z['id']+'.json')).exists()]
    if args.max_new is not None:todo=todo[:args.max_new]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:list(pool.map(lambda z:run_case(z,rr,model,engine),todo))

if __name__=='__main__':main()
