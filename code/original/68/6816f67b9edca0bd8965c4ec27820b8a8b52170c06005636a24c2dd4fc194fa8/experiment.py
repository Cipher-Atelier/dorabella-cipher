"""Frozen, finite geometric next-symbol prediction diagnostic. No language model.
Euler sampler follows conditional_v7.py; count formula follows count_bigrams_v7.py.
"""
from pathlib import Path
from collections import Counter
import argparse, datetime, hashlib, itertools, json, math, platform, time
import numpy as np
import sympy as sp

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'dorabella_round13/data/cases.json'
SEED=202610021401
SPEC={
 'id':'geometric-second-order-heldout-20261002', 'seed':SEED,
 'train_length':43, 'test_length':44, 'real_controls':9999,
 'geometric_relabels':9999, 'synthetic_each_kind':100, 'synthetic_controls':199,
 'factorizations':[['axis_mod4','polarity','arcs_mod3'],['orientation_mod8','arcs_mod3']],
 'model':'Equal-weight sequence mixture of the two factorizations. Each factor has first-order KT smoothing (0.5/cell). Second-order rows shrink to the fitted first-order row with concentration 2.0. Prefix-only parameter fitting; no suffix updating.',
 'primary':'Heldout bits = log2(P_second_order(suffix|prefix)/P_first_order(suffix|prefix)).',
 'conditional_null':'Keep positions 1..43 fixed. Uniform Euler shuffle of positions 43..87, preserving its first/last signs and all directed bigram counts. Thus all global directed bigrams and symbol counts are unchanged.',
 'relabel_null':'Uniform permutation of all 24 glyph identities onto the 24 geometric forms; refit prefix and score suffix with identical models.',
 'decision':'Investigate only if gain>0 and upper-tail plus-one fraction<=0.01 for BOTH conditional and geometric-relabel controls on BOTH transcriptions, synthetic second-order detection>=80/100, and first-order false positives<=5/100. Otherwise close this model without retuning. Both transcriptions are dependent, not independent replications.',
 'synthetic':'Independent uniform initial feature pairs. Each axis(4), polarity(2), arc(3) has a random deterministic table. At each later step use table with probability 0.90, else uniform. Negative table has one lag; positive table has two lags. Same lengths, fitting and conditional test; no real-derived parameters.',
 'calibration_scope':'Synthetic detectability checks for deliberately strong local dependence only, not historical or language validation. Previously seen 14 letters are descriptive challenge cases, not new positives for geometric generation.',
 'limits':'Adaptive research on an already studied document. Split is computational only, not new unseen historical evidence. A pass would not establish no-language, hoax, original intent, a cipher key or decipherment. A fail only stops this specific predictive model.'}

def dump(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def bigrams(s):return Counter(zip(map(int,s[:-1]),map(int,s[1:])))

def euler_shuffle(seq,rng):
    seq=np.asarray(seq,np.int64);K=int(seq.max())+1
    edges=[[] for _ in range(K)]
    for i in range(len(seq)-1):edges[int(seq[i])].append(i)
    root=int(seq[-1]);tree=np.zeros(K,bool);tree[root]=True;last=np.full(K,-1,np.int64)
    for v in sorted(set(map(int,seq))):
        u=v
        while not tree[u]:
            e=edges[u][int(rng.integers(len(edges[u])))];last[u]=e;u=int(seq[e+1])
        u=v
        while not tree[u]:tree[u]=True;u=int(seq[last[u]+1])
    queues=[]
    for v in range(K):
        ee=edges[v].copy()
        if v!=root and ee:
            e=int(last[v]);ee.remove(e);rng.shuffle(ee);ee.append(e)
        else:rng.shuffle(ee)
        queues.append(ee)
    ptr=np.zeros(K,int);out=np.empty_like(seq);out[0]=seq[0]
    for i in range(1,len(seq)):
        v=int(out[i-1]);e=queues[v][ptr[v]];ptr[v]+=1;out[i]=seq[e+1]
    assert out[-1]==seq[-1] and all(ptr[v]==len(queues[v]) for v in range(K))
    return out

def cardinality(s):
    vocab=sorted(set(map(int,s)));lookup={x:i for i,x in enumerate(vocab)};K=len(vocab)
    a=[[0]*K for _ in range(K)]
    for u,v in zip(s,s[1:]):a[lookup[int(u)]][lookup[int(v)]]+=1
    out=[sum(r) for r in a];root=lookup[int(s[-1])]
    lap=sp.Matrix(K,K,lambda i,j:(out[i] if i==j else 0)-a[i][j])
    trees=int(lap.minor_submatrix(root,root).det()) if K>1 else 1
    top=trees*math.prod(math.factorial(d-1+(i==root)) for i,d in enumerate(out))
    bottom=math.prod(math.factorial(v) for row in a for v in row)
    assert top%bottom==0
    return top//bottom

def features(g):
    o=g//3;c=g%3
    return [[(o%4,4),(o//4,2),(c,3)],[(o,8),(c,3)]]

def fit(prefix):
    models=[]
    for f in features(np.asarray(prefix)):
        factors=[]
        for x,k in f:
            c1=np.zeros((k,k),float);np.add.at(c1,(x[:-1],x[1:]),1)
            q1=(c1+0.5)/(c1.sum(axis=-1,keepdims=True)+k*0.5)
            c2=np.zeros((k,k,k),float);np.add.at(c2,(x[:-2],x[1:-1],x[2:]),1)
            q2=(c2+2*q1[None,:,:])/(c2.sum(axis=-1,keepdims=True)+2)
            assert np.allclose(q1.sum(-1),1) and np.allclose(q2.sum(-1),1)
            factors.append((np.log2(q1),np.log2(q2)))
        models.append(factors)
    return models

def score_many(glyph,models):
    g=np.asarray(glyph)
    if g.ndim==1:g=g[None,:]
    fs=features(g);logs=np.zeros((2,2,len(g)))
    for j,fac in enumerate(fs):
        for (x,k),(l1,l2) in zip(fac,models[j]):
            logs[j,0]+=l1[x[:,42:-1],x[:,43:]].sum(axis=-1)
            logs[j,1]+=l2[x[:,41:-2],x[:,42:-1],x[:,43:]].sum(axis=-1)
    mixture=np.logaddexp2(logs[0],logs[1])-1
    return (mixture[1]-mixture[0]),mixture.T,logs.transpose(2,0,1)

def independent_score(g):
    # Separate, slow direct counting implementation without fit/score_many.
    scores=[]
    for fac in features(np.asarray(g)):
        v=[0.,0.]
        for x,k in fac:
            tr=list(map(int,x[:43]));n1=Counter(zip(tr,tr[1:]));n2=Counter(zip(tr,tr[1:],tr[2:]))
            denomin1=Counter(tr[:-1]);denomin2=Counter(zip(tr[:-2],tr[1:-1]))
            for t in range(43,len(x)):
                a,b,c=map(int,x[t-2:t+1]);p1=(n1[b,c]+.5)/(denomin1[b]+k*.5)
                p2=(n2[a,b,c]+2*p1)/(denomin2[a,b]+2)
                v[0]+=math.log2(p1);v[1]+=math.log2(p2)
        scores.append(v)
    out=[]
    for i in range(2):
        m=max(scores[0][i],scores[1][i]);out.append(m+math.log2(sum(2**(s[i]-m) for s in scores))-1)
    return out[1]-out[0]

def synthetic(rng,kind):
    xs=[]
    for k in [4,2,3]:
        table=rng.integers(k,size=(k,k) if kind=='second_order' else k)
        x=list(map(int,rng.integers(k,size=2)))
        for t in range(2,87):
            y=table[x[-2],x[-1]] if kind=='second_order' else table[x[-1]]
            x.append(int(y) if rng.random()<.9 else int(rng.integers(k)))
        xs.append(np.array(x))
    return (3*(xs[0]+4*xs[1])+xs[2]).tolist()

def prepare():
    assert not (ROOT/'frozen_protocol.json').exists(),'Frozen protocol already exists; do not overwrite.'
    old=json.loads(SOURCE.read_text());cases=[dict(id=x['id'],kind=x['kind'],glyph=x['glyph']) for x in old if x['kind'] in ['real','positive','regression']]
    rng=np.random.default_rng(SEED)
    for kind in ['second_order','first_order']:
        for i in range(SPEC['synthetic_each_kind']):cases.append(dict(id=f'{kind}_{i:03d}',kind=kind,glyph=synthetic(rng,kind)))
    for x in cases:x['control_seed']=int(rng.integers(0,2**63));x['relabel_seed']=int(rng.integers(0,2**63))
    dump(ROOT/'data/cases.json',cases)
    prior=ROOT.parent/'dorabella_audit/round10/dorabella_lab'
    frozen=dict(spec=SPEC,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),environment=dict(python=platform.python_version(),numpy=np.__version__,sympy=sp.__version__),hashes={str(p.relative_to(ROOT.parent)):sha(p) for p in [Path(__file__),ROOT/'data/cases.json',SOURCE,prior/'conditional_v7.py',prior/'count_bigrams_v7.py']})
    dump(ROOT/'frozen_protocol.json',frozen);print('FROZEN',sha(ROOT/'frozen_protocol.json'),flush=True)

def verify_protocol():
    frozen=json.loads((ROOT/'frozen_protocol.json').read_text());assert frozen['spec']==SPEC
    for name,h in frozen['hashes'].items():assert sha(ROOT.parent/name)==h,name

def checks():
    rng=np.random.default_rng(SEED+1);toy=[]
    for s in [(0,1,0,2,0,1,2,0),(0,0,1,2,1,0,1,2),(0,1,0,1,2,1,2,0),(0,0,0),(0,1,2)]:
        support={p for p in itertools.permutations(s) if p[0]==s[0] and p[-1]==s[-1] and bigrams(p)==bigrams(s)}
        assert len(support)==cardinality(s)
        counts=Counter(tuple(euler_shuffle(s,rng)) for _ in range(12000));assert set(counts)==support
        toy.append(dict(sequence=s,support_size=len(support),counts=[dict(sequence=x,n=counts[x]) for x in sorted(support)]))
    errors=[]
    for _ in range(100):
        g=rng.integers(0,24,87);v=score_many(g,fit(g[:43]))[0][0];errors.append(abs(v-independent_score(g)))
    assert max(errors)<1e-10
    dump(ROOT/'results/implementation_checks.json',dict(toy_checks=toy,independent_scorer_checks=len(errors),max_absolute_error=max(errors)))

def run_case(c):
    path=ROOT/'results'/f"{c['id']}.json"
    if path.exists():return json.loads(path.read_text())
    t0=time.monotonic();g=np.array(c['glyph']);model=fit(g[:43]);real,logs,parts=score_many(g,model)
    out=dict(id=c['id'],kind=c['kind'],gain_bits=float(real[0]),mixture_log2_probabilities=logs[0].tolist(),factorization_log2_probabilities=parts[0].tolist())
    n=SPEC['real_controls'] if c['kind']=='real' else SPEC['synthetic_controls'] if c['kind'] in ['first_order','second_order'] else 0
    if n:
        rng=np.random.default_rng(c['control_seed']);controls=np.empty((n,87),np.uint8);basepairs=bigrams(g)
        for i in range(n):
            z=np.r_[g[:42],euler_shuffle(g[42:],rng)];assert np.array_equal(z[:43],g[:43]) and z[-1]==g[-1] and bigrams(z)==basepairs and Counter(z)==Counter(g)
            controls[i]=z
        vals,clogs,cparts=score_many(controls,model);assert np.max(abs(clogs[:,0]-logs[0,0]))<1e-10
        k=int(np.sum(vals>=real[0]-1e-10));out['conditional']=dict(n=n,ge=k,p_plus_one=(k+1)/(n+1),unique=int(len(np.unique(controls,axis=0))),first_order_log2_range=float(np.ptp(clogs[:,0])),mean_gain_bits=float(vals.mean()),std_gain_bits=float(vals.std()))
        if c['kind']=='real':out['conditional']['exact_support_size']=str(cardinality(g[42:]))
        np.savez_compressed(ROOT/'results'/f"{c['id']}_controls.npz",glyph=controls,gain_bits=vals,mixture_log2=clogs,factorization_log2=cparts)
    if c['kind']=='real':
        rng=np.random.default_rng(c['relabel_seed']);perms=np.array([rng.permutation(24) for _ in range(SPEC['geometric_relabels'])],np.uint8)
        vals=[]
        for p in perms:
            z=p[g];vals.append(float(score_many(z,fit(z[:43]))[0][0]))
        vals=np.array(vals);k=int(np.sum(vals>=real[0]-1e-10));out['relabel']=dict(n=len(vals),ge=k,p_plus_one=(k+1)/(len(vals)+1),mean_gain_bits=float(vals.mean()),std_gain_bits=float(vals.std()))
        np.savez_compressed(ROOT/'results'/f"{c['id']}_relabels.npz",permutations=perms,gain_bits=vals)
    out['seconds']=time.monotonic()-t0;dump(path,out);print(c['id'],round(out['gain_bits'],4),out.get('conditional',{}).get('p_plus_one'),round(out['seconds'],3),flush=True)
    return out

def summarize(records):
    kinds={k:[r for r in records if r['kind']==k] for k in ['real','first_order','second_order','positive','regression']}
    detect=lambda r:r['gain_bits']>0 and r['conditional']['p_plus_one']<=.01
    positive=sum(map(detect,kinds['second_order']));false=sum(map(detect,kinds['first_order']))
    realpass=all(r['gain_bits']>0 and r['conditional']['p_plus_one']<=.01 and r['relabel']['p_plus_one']<=.01 for r in kinds['real'])
    summary=dict(frozen_protocol_sha256=sha(ROOT/'frozen_protocol.json'),records=len(records),real=kinds['real'],synthetic=dict(n_each=100,second_order_detected=positive,first_order_false_positives=false),real_gate_passed=realpass,calibration_gate_passed=positive>=80 and false<=5,decision='pursue' if realpass and positive>=80 and false<=5 else 'stop_this_model',historical_challenges=kinds['positive']+kinds['regression'])
    dump(ROOT/'results/summary.json',summary)
    manifest={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'results').glob('*')) if p.is_file() and p.name!='manifest.json'};dump(ROOT/'results/manifest.json',manifest)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['historical_challenges','real']},indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','check','run','verify']);a=ap.parse_args()
    if a.mode=='prepare':prepare()
    else:
        verify_protocol()
        if a.mode=='check':checks()
        elif a.mode=='run':summarize([run_case(c) for c in json.loads((ROOT/'data/cases.json').read_text())])
        else:
            manifest=json.loads((ROOT/'results/manifest.json').read_text())
            for name,h in manifest.items():assert sha(ROOT/name)==h,name
            print('Protocol and all result hashes verified')
