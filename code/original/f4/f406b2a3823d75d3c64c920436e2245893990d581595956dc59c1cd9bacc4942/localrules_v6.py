"""Exploratory local geometric rules followed by an unrestricted substitution.
This is a heuristic search with explicit parameters, NOT a complete exclusion.
No null test is claimed in this branch. Stop claiming success without coherence.
"""
import itertools,json,time,argparse,hashlib
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from automata import canonical
from language import build_model,stable_seed
from fastsolve import solve_fast
from wordsearch_v4 import WordSearch
from model_v5 import ROOT
OUT=ROOT/'results/v6/localrules';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'family':'local-geometric-and-substitution-v6','screen':[8,16000,32],
          'middle':[32,20000,8],'final':[128,20000],'word':{'restarts':64,'iterations':16000},
          'cumulative':'state update by each possible table of arc(3),axis(4),polarity(2); state mod8',
          'boundary_shifts':'orientation ramp 0..7, two extra shifts 0..7 at (29,60) or (41,65)',
          'two_channel_difference':'orientation mod8 and arc mod3; previous ciphertext or plaintext; all coefficients/initial states',
          'previous_arc':'arbitrary orientation/arc offsets from previous ciphertext arc, first offsets fixed zero up to global relabelling',
          'reading':'forward only; no per-symbol edits; no crib','null_calibration':'none in this exploratory branch',
          'seed_positive':20260926065,'positives':8,'positive_status':'old texts re-encrypted; sensitivity only'}

def definitions():
    # fixed width records: family,subtype,arg0..arg5
    out=[(0,0,0,0,0,0,0,0)]
    for pair in range(2):
        for k,u,v in itertools.product(range(8),repeat=3):out.append((1,pair,k,u,v,0,0,0))
    for feature,R in [(0,3),(1,4),(2,2)]:
        for tab in itertools.product(range(8),repeat=R):out.append(tuple([2,feature]+list(tab)+[0]*(6-R)))
    for mode in range(2):
        for b,l,io,ic in itertools.product(range(8),range(3),range(8),range(3)):
            out.append((3,mode,b,l,io,ic,0,0))
    for g1,g2,f1,f2 in itertools.product(range(8),range(8),range(3),range(3)):
        out.append((4,0,g1,g2,f1,f2,0,0))
    return np.array(out,np.int64)

@njit(cache=True)
def feature(o,c,kind):
    if kind==0:return c
    if kind==1:return o%4
    return o//4

@njit(cache=True)
def transform(o,c,r):
    family,sub=r[:2];n=len(o);z=np.empty(n,np.int64);state=0
    po=r[4];pc=r[5]
    for t in range(n):
        if family==0:oo=o[t];cc=c[t]
        elif family==1:
            cut1=29 if sub==0 else 41;cut2=60 if sub==0 else 65
            oo=(o[t]-r[2]*t-r[3]*(t>=cut1)-r[4]*(t>=cut2))%8;cc=c[t]
        elif family==2:
            oo=(o[t]-state)%8;cc=c[t]
            state=(state+r[2+feature(o[t],c[t],sub)])%8
        elif family==3:
            oo=(o[t]-r[2]*po)%8;cc=(c[t]-r[3]*pc)%3
            po=o[t] if sub==0 else oo;pc=c[t] if sub==0 else cc
        else:
            prev=0 if t==0 else c[t-1]
            g=0 if prev==0 else r[1+prev];f=0 if prev==0 else r[3+prev]
            oo=(o[t]-g)%8;cc=(c[t]-f)%3
        z[t]=3*oo+cc
    return z

@njit(cache=True)
def inverse(z,r):
    family,sub=r[:2];n=len(z);o=np.empty(n,np.int64);c=np.empty(n,np.int64);state=0;po=r[4];pc=r[5]
    for t in range(n):
        oo=z[t]//3;cc=z[t]%3
        if family==0:o[t]=oo;c[t]=cc
        elif family==1:
            cut1=29 if sub==0 else 41;cut2=60 if sub==0 else 65
            o[t]=(oo+r[2]*t+r[3]*(t>=cut1)+r[4]*(t>=cut2))%8;c[t]=cc
        elif family==2:
            o[t]=(oo+state)%8;c[t]=cc;state=(state+r[2+feature(o[t],c[t],sub)])%8
        elif family==3:
            o[t]=(oo+r[2]*po)%8;c[t]=(cc+r[3]*pc)%3
            po=o[t] if sub==0 else oo;pc=c[t] if sub==0 else cc
        else:
            prev=0 if t==0 else c[t-1]
            g=0 if prev==0 else r[1+prev];f=0 if prev==0 else r[3+prev]
            o[t]=(oo+g)%8;c[t]=(cc+f)%3
    return o,c

def variants(o,c,rs):
    bank={}
    for j,r in enumerate(rs):
        z=transform(o,c,r);s=canonical(z);k=s.tobytes()
        if k not in bank:bank[k]=(s,j)
    return list(bank.values())

def cases(rs):
    old=json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'];out=[]
    for z in old:
        if z['kind']=='real':out.append(dict(id=z['id'],kind='real',orientation=z['orientation'],arcs=z['arcs']))
    rng=np.random.default_rng(PROTOCOL['seed_positive']);past=[z for z in old if z['kind']=='positive'][8:16]
    for j,x in enumerate(past):
        truth=x['original_plaintext'].lower();a=np.array([ord(ch)-97 for ch in truth]);eq=canonical(a);z=rng.permutation(24)[eq]
        # Cover four new families twice, without selecting successful instances.
        fam=1+j%4;rid=int(rng.choice(np.flatnonzero(rs[:,0]==fam)));r=rs[rid];o,c=inverse(z,r)
        assert np.array_equal(transform(o,c,r),z)
        out.append(dict(id=f'positive_{j:02d}',kind='positive',plaintext=truth,orientation=o.tolist(),arcs=c.tolist(),
                        generating_index=rid,generating_rule=r.tolist(),source=x['id']))
    data=dict(protocol=PROTOCOL,cases=out,n_definitions=len(rs))
    p=OUT/'inputs.json'
    if p.exists():assert json.loads(p.read_text())==data
    else:p.write_text(json.dumps(data,indent=2))
    return out

def run_case(x,rs,model,engine):
    dest=OUT/(x['id']+'.json')
    if dest.exists():return json.loads(dest.read_text())
    start=time.monotonic();o=np.array(x['orientation']);c=np.array(x['arcs']);v=variants(o,c,rs);lp,p1=model
    raw=canonical(3*o+c);ii=next(i for i,(s,_) in enumerate(v) if np.array_equal(s,raw));scores=np.full(len(v),-1e100);keys=[None]*len(v);selected=list(range(len(v)));snaps=[]
    print('begin',x['id'],len(v),'patterns',flush=True)
    for stage in ('screen','middle','final'):
        conf=PROTOCOL[stage]
        for j in selected:
            seq=v[j][0];sc,key=solve_fast(seq,lp,p1,conf[0],conf[1],stable_seed(seq,'local_v6_'+stage))
            if sc>scores[j]:scores[j]=sc;keys[j]=key
        snaps.append(dict(stage=stage,selected=selected.copy(),scores=(scores/84).tolist()))
        if len(conf)==3:selected=sorted(set(sorted(selected,key=lambda j:(-scores[j],v[j][0].tobytes()))[:conf[2]]+[ii]))
    finals=[]
    for j in selected:
        seq,rid=v[j];r=engine.run(seq,keys[j][seq],PROTOCOL['word'],tag='local_v6_word')
        r.update(pattern_index=j,rule_index=rid,rule=rs[rid].tolist());finals.append(r)
    finals.sort(key=lambda q:(-q['score'],q['decoded']));best=finals[0];ident=next(r for r in finals if r['pattern_index']==ii)
    rec=dict(id=x['id'],kind=x['kind'],best_score=best['score'],identity_score=ident['score'],gain=best['score']-ident['score'],best_text=''.join(chr(v+97) for v in best['decoded']),
             distinct_patterns=len(v),n_definitions=len(rs),finalists=finals,stages=snaps,seconds=time.monotonic()-start)
    if x['kind']=='positive':
        rec['accuracy']=sum(a==b for a,b in zip(rec['best_text'],x['plaintext']))/87
        s=canonical(transform(o,c,rs[x['generating_index']]));j=next(j for j,(seq,_) in enumerate(v) if np.array_equal(seq,s))
        rec['true_pattern_finalist']=j in selected;rec['true_pattern_index']=j
        rec['true_pattern_ranks']=[1+sum(val>q['scores'][j]+1e-10 for val in q['scores']) for q in snaps]
    dest.write_text(json.dumps(rec,indent=2));print('done',x['id'],rec['best_score'],rec.get('accuracy',''),rec['best_text'],round(rec['seconds'],2),flush=True)
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['real','positive','all'],default='real');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    rs=definitions();cs=cases(rs);model=build_model();engine=WordSearch()
    files=['localrules_v6.py','wordsearch_v4.py','fastsolve.py','data/english_model.npz','results/v6/localrules/inputs.json']
    freeze=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},dictionary=engine.scorer.metadata)
    p=OUT/'frozen.json'
    if p.exists():assert json.loads(p.read_text())==freeze
    else:p.write_text(json.dumps(freeze,indent=2))
    todo=[z for z in cs if (a.mode=='all' or z['kind']==a.mode) and not (OUT/(z['id']+'.json')).exists()]
    solve_fast(np.zeros(87,np.int64),*model,1,1,1)
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(lambda z:run_case(z,rs,model,engine),todo))

if __name__=='__main__':main()
