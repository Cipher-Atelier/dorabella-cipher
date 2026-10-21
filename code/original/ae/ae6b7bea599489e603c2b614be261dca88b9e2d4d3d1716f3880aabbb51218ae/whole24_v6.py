"""Exhaustive full-glyph affine transforms mod 24. No arbitrary per-letter key.
The optional input layout is x=3*orientation+arcs, or x=8*arcs+orientation.
mode0: p[t] = a*x[t] + b*x[t-1] + k*t + h (mod24)
mode1: p[t] = a*x[t] + b*p[t-1] + k*t + h (mod24)
All units a, b/k/h=0..23, and all distinct effects of the initial value.
Full 24-state family includes arc-changing transforms, unlike round5.
"""
from pathlib import Path
import math,json,time,hashlib,argparse
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from model_v5 import load_model,LETTER,ROOT,ALPHABET
from wordpolish_v3 import char_score,fast_word
OUT=ROOT/'results/v6/whole24';OUT.mkdir(parents=True,exist_ok=True)
UNITS=np.array([1,5,7,11,13,17,19,23],np.int64)
PROTOCOL={'family':'full-glyph-affine-mod24-v6','layouts':['3*orientation+arcs','8*arcs+orientation'],
 'modes':['previous-cipher','previous-plaintext'],'a':UNITS.tolist(),'bkh':'all residues mod24',
 'initial':'all 24 states, deduplicate identical b*initial mod24 effects',
 'reading':'left-to-right concatenation only','arbitrary_substitution':False,
 'score':'round5 merged24 C+0.5W unchanged','null_pairs':19,'null_seed':20260926061,
 'positives':'first 12 of previously used historical plaintexts, re-encrypted; sensitivity, not holdout',
 'positive_seed':20260926062,'keep_best':32}

def param_array():
    # For fixed b, initial values 0..(24/gcd(b,24)-1) cover all b*initial effects.
    return np.array([(a,b,k,h,s) for a in UNITS for b in range(24)
        for k in range(24) for h in range(24) for s in range(24//math.gcd(b,24))],np.int64)

@njit(cache=True)
def decode(x,r,mode):
    a,b,k,h,previous=r;p=np.empty(len(x),np.int64)
    for t in range(len(x)):
        p[t]=(a*x[t]+b*previous+k*t+h)%24
        previous=x[t] if mode==0 else p[t]
    return p

@njit(cache=True)
def encode(p,r,mode):
    a,b,k,h,previous=r;x=np.empty(len(p),np.int64)
    # Each unit mod24 is its own inverse.
    for t in range(len(p)):
        x[t]=(a*(p[t]-b*previous-k*t-h))%24
        previous=x[t] if mode==0 else p[t]
    return x

@njit(cache=True,nogil=True)
def evaluate(x,rs,mode,lp,children,vals):
    ss=np.empty(len(rs),np.float64)
    for j in range(len(rs)):
        p=decode(x,rs[j],mode);txt=LETTER[p]
        ss[j]=char_score(txt,lp)+.5*fast_word(txt,children,vals)
    return ss

def layout_to_geom(x,layout):
    return (x//3,x%3) if layout==0 else (x%8,x//8)

def inputs():
    old=json.loads((ROOT/'results/v5/inputs.json').read_text())['cases']
    real=[dict(id=z['id'],kind='real',orientation=z['orientation'],arcs=z['arcs']) for z in old if z['kind']=='real']
    out=real.copy();rng=np.random.default_rng(PROTOCOL['null_seed'])
    for j in range(PROTOCOL['null_pairs']):
        idx=rng.permutation(87)
        for z in real:
            out.append(dict(id=z['id'].replace('_real',f'_null_{j:02d}'),kind='null',pair=j,
                orientation=np.array(z['orientation'])[idx].tolist(),arcs=np.array(z['arcs'])[idx].tolist(),permutation=idx.tolist()))
    rng=np.random.default_rng(PROTOCOL['positive_seed']);pos=[z for z in old if z['kind']=='positive'][:12]
    for j,z in enumerate(pos):
        truth=z['plaintext'];p=np.array([ALPHABET.index(ch.upper()) for ch in truth]);mode=j%2;layout=(j//2)%2
        while True:
            b=int(rng.integers(1,24));r=np.array([int(rng.choice(UNITS)),b,int(rng.integers(24)),int(rng.integers(24)),int(rng.integers(24//math.gcd(b,24)))])
            x=encode(p,r,mode);o,c=layout_to_geom(x,layout)
            if np.any(c!=p%3):break
        out.append(dict(id=f'positive_{j:02d}',kind='positive',plaintext=truth,
            orientation=o.tolist(),arcs=c.tolist(),generating=dict(rule=r.tolist(),mode=mode,layout=layout),source=z['id']))
    dest=OUT/'inputs.json';data=dict(protocol=PROTOCOL,cases=out)
    if dest.exists():assert json.loads(dest.read_text())==data
    else:dest.write_text(json.dumps(data,indent=2))
    return out

def freeze(rs,model):
    files=['whole24_v6.py','model_v5.py','wordpolish_v3.py','wordscore_v3.py','data/english_merged24_v5.npz','results/v6/whole24/inputs.json']
    data=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
              dictionary=model[1].metadata,n_unique_effect_rules_per_mode_layout=len(rs),total_per_case=4*len(rs),
              all_parameter_definitions_including_aliases=4*8*24**4)
    path=OUT/'frozen.json'
    if path.exists():assert json.loads(path.read_text())==data,'Do not mix protocols'
    else:path.write_text(json.dumps(data,indent=2))

def run_case(z,rs,model):
    dest=OUT/(z['id']+'.json')
    if dest.exists():return json.loads(dest.read_text())
    lp,scorer,ch,val=model;start=time.monotonic();o=np.array(z['orientation']);c=np.array(z['arcs'])
    pool=[];details=[];static=-1e100;score_hashes=[]
    for layout in range(2):
        x=3*o+c if layout==0 else 8*c+o
        for mode in range(2):
            scores=evaluate(x,rs,mode,lp,ch,val)
            ids=np.argpartition(scores,-PROTOCOL['keep_best'])[-PROTOCOL['keep_best']:]
            ids=sorted(ids,key=lambda i:(-float(scores[i]),int(i)))
            for j in ids:
                txt=LETTER[decode(x,rs[j],mode)]
                pool.append(dict(layout=layout,mode=mode,rule=rs[j].tolist(),rule_index=int(j),score=float(scores[j]),
                    plaintext=''.join(chr(int(v)+97) for v in txt)))
            mask=(rs[:,1]==0)&(rs[:,2]==0)
            static=max(static,float(np.max(scores[mask])))
            details.append(dict(layout=layout,mode=mode,max_score=float(scores.max()),mean=float(scores.mean()),
                                quantiles=np.quantile(scores,[0,.25,.5,.75,.9,.99,1]).tolist(),n=len(scores)))
            score_hashes.append(hashlib.sha256(scores.tobytes()).hexdigest())
    seen=set();top=[]
    for p in sorted(pool,key=lambda y:(-y['score'],y['layout'],y['mode'],y['rule_index'])):
        if p['plaintext'] in seen:continue
        seen.add(p['plaintext']);ws,seg=scorer.score(p['plaintext'],True)
        a=np.array([ord(v)-97 for v in p['plaintext']]);cs=char_score(a,lp)
        assert abs(p['score']-cs-.5*ws)<1e-10
        p.update(char_score=float(cs),word_score=float(ws),segmentation=seg);top.append(p)
        if len(top)==PROTOCOL['keep_best']:break
    rec=dict(id=z['id'],kind=z['kind'],best_score=top[0]['score'],best_text=top[0]['plaintext'],static_score=static,
             gain=top[0]['score']-static,top=top,group_stats=details,score_sha256=score_hashes,seconds=time.monotonic()-start,
             n_rule_evaluations=4*len(rs))
    if z['kind']=='positive':
        rec['accuracy']=sum(a==b for a,b in zip(z['plaintext'],rec['best_text']))/87
        rec['truth_score']=float(char_score(np.array([ord(a)-97 for a in z['plaintext']]),lp)+.5*scorer.score(z['plaintext']))
    dest.write_text(json.dumps(rec,indent=2));print(z['id'],round(rec['best_score'],5),rec.get('accuracy',''),round(rec['seconds'],2),flush=True)
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['real','positive','null','all'],default='real');ap.add_argument('--workers',type=int,default=4);ap.add_argument('--max-new',type=int);args=ap.parse_args()
    model=load_model();rs=param_array();cases=inputs();freeze(rs,model)
    evaluate(np.zeros(87,np.int64),rs[:1],0,model[0],model[2],model[3])
    todo=[x for x in cases if (args.mode=='all' or x['kind']==args.mode) and not (OUT/(x['id']+'.json')).exists()]
    if args.max_new is not None:todo=todo[:args.max_new]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:list(pool.map(lambda z:run_case(z,rs,model),todo))

if __name__=='__main__':main()
