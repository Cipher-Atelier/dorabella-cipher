"""Finite mixed-radix coordinate-lag experiment; standalone, no source writes."""
from pathlib import Path
import os, sys, json, itertools, hashlib, time, datetime, argparse
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'dorabella_round13/deps'))
os.environ.setdefault('NUMBA_CACHE_DIR',str(ROOT/'cache'))
os.environ.setdefault('NUMBA_NUM_THREADS','1')
from numba import njit
ALPHA='abcdefghiklmnopqrstuwxyz'
LETTER=np.array([ord(c)-97 for c in ALPHA],np.int64)
Q=np.array(list(itertools.permutations(range(3))),np.int64)
P=np.array([[(s*o+h)%8 for o in range(8)] for s in (1,-1) for h in range(8)],np.int64)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,x): Path(path).write_text(json.dumps(x,indent=2)+'\n')
def banks():
    maps=[];tables=[]
    for layout,pi,qi in itertools.product(range(2),range(16),range(6)):
        oo=P[pi,:,None]; cc=Q[qi,None,:]
        maps.append(LETTER[3*oo+cc if layout==0 else 8*cc+oo]);tables.append([layout,pi,qi])
    oi=[];ci=[];routes=[]
    for rev,reset,anchor,k in itertools.product(range(2),range(2),range(2),range(-43,44)):
        base=np.arange(87)[::-1] if rev else np.arange(87)
        shifted=np.empty(87,np.int64)
        cuts=[0,87] if not reset else ([0,27,58,87] if rev else [0,29,60,87])
        for st,en in zip(cuts[:-1],cuts[1:]):shifted[st:en]=base[st+(np.arange(en-st)+k)%(en-st)]
        oi.append(base if anchor==0 else shifted);ci.append(shifted if anchor==0 else base)
        routes.append([rev,reset,anchor,k])
    return np.array(maps),np.array(oi),np.array(ci),tables,routes

@njit(cache=True)
def word(t,children,vals):
    n=len(t); dp=np.full(n+1,-1e100);dp[0]=0.
    for st in range(n):
        v=dp[st]-8.
        if v>dp[st+1]:dp[st+1]=v
        node=0
        for en in range(st,min(n,st+24)):
            node=children[node,t[en]]
            if node<0:break
            v=vals[node,0]
            if st==0 and en+1<n:v=max(v,vals[node,2])
            if en+1==n and st>0:v=max(v,vals[node,1])
            if dp[st]+v>dp[en+1]:dp[en+1]=dp[st]+v
    return dp[n]/n

@njit(cache=True)
def scan(g,maps,oi,ci,lp,children,vals,unpruned=False):
    best=-1e100;bid=-1;ties=[np.int64(0) for _ in range(0)];nw=0
    baseline=-1e100;baselineid=-1
    t=np.empty(87,np.int64)
    for mi in range(len(maps)):
        for ri in range(len(oi)):
            C=0.
            for j in range(87):t[j]=maps[mi,g[oi[ri,j]]//3,g[ci[ri,j]]%3]
            for j in range(84):C+=lp[((t[j]*26+t[j+1])*26+t[j+2])*26+t[j+3]]
            C/=84
            # Route IDs have k=-43..43 last, so offset43 is k=0.
            isbase=ri%87==43
            if unpruned or C>=best-1e-12 or (isbase and C>=baseline-1e-12):
                W=word(t,children,vals);nw+=1;S=C+.5*W
                idx=mi*len(oi)+ri
                if S>best:best=S;bid=idx;ties=[idx]
                elif S==best:ties.append(idx)
                if isbase and S>baseline:baseline=S;baselineid=idx
    return best,bid,ties,nw,baseline,baselineid

def decode(g,maps,oi,ci,key):
    mi,ri=divmod(key,len(oi));g=np.asarray(g)
    return maps[mi,g[oi[ri]]//3,g[ci[ri]]%3]

def encrypt(text,maps,oi,ci,key):
    mi,ri=divmod(key,len(oi));inv={int(maps[mi,o,c]):(o,c) for o in range(8) for c in range(3)}
    o=np.empty(87,np.int64);c=np.empty(87,np.int64)
    for j,a in enumerate(text):o[oi[ri,j]],c[ci[ri,j]]=inv[int(a)]
    return 3*o+c

def word_py(t,ch,va):
    dp=[float('-inf')]*88;dp[0]=0.
    for st in range(87):
        dp[st+1]=max(dp[st+1],dp[st]-8.);node=0
        for en in range(st,min(87,st+24)):
            node=int(ch[node,int(t[en])])
            if node<0:break
            v=float(va[node,0])
            if st==0 and en<86:v=max(v,float(va[node,2]))
            if en==86 and st>0:v=max(v,float(va[node,1]))
            dp[en+1]=max(dp[en+1],dp[st]+v)
    return dp[-1]/87

def score_py(t,lp,ch,va):
    C=float(np.mean([lp[26**3*int(t[i])+26**2*int(t[i+1])+26*int(t[i+2])+int(t[i+3])] for i in range(84)]));W=word_py(t,ch,va)
    return C+.5*W,C,W

def paircounts(x):return Counter(zip(map(int,x[:-1]),map(int,x[1:])))
def euler_shuffle(seq,rng):
    # Directed Wilson last-exit-tree shuffle; adapted from frozen round7.
    seq=np.asarray(seq,np.int64);K=int(seq.max())+1;edges=[[] for _ in range(K)]
    for i in range(len(seq)-1):edges[int(seq[i])].append(i)
    root=int(seq[-1]);tree=np.zeros(K,bool);tree[root]=True;last=np.full(K,-1,np.int64)
    for v in sorted(set(map(int,seq))):
        u=v
        while not tree[u]:
            e=edges[u][int(rng.integers(len(edges[u])))];last[u]=e;u=int(seq[e+1])
        u=v
        while not tree[u]:tree[u]=True;u=int(seq[last[u]+1])
    qs=[]
    for v in range(K):
        ee=edges[v].copy()
        if v!=root and ee:
            ee.remove(int(last[v]));rng.shuffle(ee);ee.append(int(last[v]))
        else:rng.shuffle(ee)
        qs.append(ee)
    ptr=np.zeros(K,int);out=np.empty_like(seq);out[0]=seq[0]
    for i in range(1,len(seq)):
        v=int(out[i-1]);e=qs[v][ptr[v]];ptr[v]+=1;out[i]=seq[e+1]
    assert out[-1]==seq[-1] and all(ptr[v]==len(qs[v]) for v in range(K))
    return out

def model():
    z=np.load(ROOT/'data/scoring.npz');return z['lp'],z['children'],z['vals']

def prepare():
    maps,oi,ci,tables,routes=banks();lp,ch,va=model()
    assert np.max(va)<=0 and np.max(lp)<=0
    assert all(len(set(x))==87 for x in oi) and all(len(set(x))==87 for x in ci)
    rng=np.random.default_rng(202610091117);err=0
    for _ in range(96):
        p=LETTER[rng.integers(24,size=87)];k=int(rng.integers(len(maps)*len(oi)))
        g=encrypt(p,maps,oi,ci,k);assert np.array_equal(p,decode(g,maps,oi,ci,k))
        W=word(p,ch,va);Wp=word_py(p,ch,va);err=max(err,abs(W-Wp));assert err<1e-12
    # Explicit wrapped shifts and reverse-row boundaries.
    for i,(rev,reset,anchor,k) in enumerate(routes):
        base=list(range(86,-1,-1)) if rev else list(range(87))
        sizes=[27,31,29] if rev else [29,31,27]
        blocks=[base] if not reset else [base[:sizes[0]],base[sizes[0]:sum(sizes[:2])],base[sum(sizes[:2]):]]
        shift=sum([[b[(j+k)%len(b)] for j in range(len(b))] for b in blocks],[])
        assert oi[i].tolist()==(shift if anchor else base)
        assert ci[i].tolist()==(base if anchor else shift)
    old=json.loads((ROOT/'data/old_positive_truth.json').read_text());cases=[];truth=[]
    for i,x in enumerate(old):
        # Balance traversal/reset/anchor/layout; nonzero lag; remaining parameters randomized.
        rev=i%2;reset=(i//2)%2;anchor=(i//4)%2;layout=(i//8)%2
        kval=int(rng.choice(np.r_[np.arange(-43,0),np.arange(1,44)]))
        ri=routes.index([rev,reset,anchor,kval]);mi=tables.index([layout,int(rng.integers(16)),int(rng.integers(6))]);key=mi*len(oi)+ri
        p=np.array([ord(c)-97 for c in x['plaintext']],np.int64);g=encrypt(p,maps,oi,ci,key)
        assert np.array_equal(p,decode(g,maps,oi,ci,key))
        cases.append(dict(id=x['id'],kind='positive',glyph=g.tolist()))
        truth.append(dict(id=x['id'],plaintext=x['plaintext'],key_id=key,table=tables[mi],route=routes[ri]))
    oldinputs=json.loads((ROOT/'data/old_search_inputs.json').read_text());real=[x for x in oldinputs if x['kind']=='real']
    nullmeta={}
    for x in real:
        cases.append(dict(id=x['id'],kind='real',glyph=x['glyph']));g=np.array(x['glyph']);controls=[]
        for j in range(199):
            z=euler_shuffle(g,rng)
            assert paircounts(z)==paircounts(g) and Counter(z)==Counter(g) and z[0]==g[0] and z[-1]==g[-1]
            controls.append(z.tobytes());cases.append(dict(id=f'{x["id"]}_fresh_{j:03d}',kind='null',source=x['id'],glyph=z.tolist()))
        nullmeta[x['id']]={'n':199,'unique':len(set(controls)),'all_pairs_counts_endpoints_verified':True}
    # Small exact supports, independent enumeration, then histogram check.
    small=[]
    for ss in [(0,1,0,2,0,1,2,0),(0,0,1,2,1,0,1,2)]:
        support=sorted({p for p in itertools.permutations(ss) if p[0]==ss[0] and p[-1]==ss[-1] and paircounts(p)==paircounts(ss)})
        cnt=Counter(tuple(euler_shuffle(ss,rng)) for _ in range(24000));assert set(cnt)==set(support)
        expected=24000/len(support);chi=sum((cnt[p]-expected)**2/expected for p in support)
        small.append({'support_size':len(support),'draws':24000,'counts':[cnt[p] for p in support],'pearson_chi2':chi})
    pre=dict(roundtrip_trials=96,score_max_error=err,route_independent_checks=len(routes),nulls=nullmeta,shuffle_small_checks=small)
    # Exhaustive score check on tiny key-bank slices before any actual Dorabella scores.
    g=np.array(cases[0]['glyph']);a=scan(g,maps[:4],oi[:32],ci[:32],lp,ch,va,False);b=scan(g,maps[:4],oi[:32],ci[:32],lp,ch,va,True)
    assert a[:3]==b[:3];pre['small_pruned_unpruned_equal']=True
    save(ROOT/'checks/preflight.json',pre);save(ROOT/'data/search_inputs.json',cases);save(ROOT/'data/positive_truth.json',truth)
    proto={
      'id':'coordinate-lag-mixed-radix-v1','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'hypothesis':'The orientation and arc-count components encode different positions; a fixed cyclic displacement re-pairs the two streams.',
      'motivation':'Natural 8-direction by3-arc geometry; new transform absent from inspected frozen round1-14 code. Not an authenticated historical key or a claim of world-first novelty.',
      'alphabet':ALPHA,'map':'P(o)=(s*o+h) mod8, s in [1,-1], h=0..7; Q any of six permutations of0..2. Letter index3P(o)+Q(c) OR8Q(c)+P(o).',
      'routes':'k=-43..43, shifting arcs OR orientation; global cyclic OR separately within rows29/31/27; forward OR reversed input. Reversed row lengths27/31/29. Each stream retains all87symbols.',
      'table_count':len(maps),'route_count':len(oi),'parameter_definitions':len(maps)*len(oi),
      'key_id':'table_id*696+route_id; tables lexicographic layout,pi,qi; routes lexicographic reversal,reset,anchor,k. Duplicates retained with exact ties; smallest ID is canonical.',
      'score':'Archived S=C+.5W unchanged; all84character4grams, same dictionary segmentation. W<=0 hence C<best-1e-12 safely skips W. No score retraining or crib.',
      'baseline':'Best k=0 rule over same maps and remaining route definitions; report total gain as descriptive secondary outcome. Nulls receive identical full search.',
      'positives':'14 previously inspected87letter historical texts freshly encrypted with balanced route factors and nonzero lag. Regression sensitivity, not blind validation.',
      'gate':'Before any real/null search: >=12/14exact87/87 and >=1194/1218letters. Failure stops real scoring without retuning.',
      'nulls':'199fresh directed-bigram/endpoints/count-preserving sequences per transcription using directed Wilson last-exit tree sampler. Separate real ranks and plus-one tails; no pooling/cherry-pick. Exploratory reused real data, not confirmatory significance.',
      'stop':'Only these414cases after gate; stop on audit failure. No parameter expansion or manuscript correction. No solving claim without coherent complete plaintext and independent corroboration.',
      'seed':202610091117,'audits':'96 roundtrips,696independent route constructions,small exact shuffle supports,independent every final score+inverse; full unpruned reruns for first positive and2real.',
      'source_preservation':'Read-only copies from prior round14. Prior corpus unchanged; all new files in separate directory.',
      'hashes':{p:sha(ROOT/p) for p in ['code/experiment.py','data/scoring.npz','data/search_inputs.json','data/positive_truth.json','checks/preflight.json']}}
    save(ROOT/'protocol.json',proto);(ROOT/'protocol.sha256').write_text(sha(ROOT/'protocol.json')+'\n');print(json.dumps(pre));print('FROZEN',sha(ROOT/'protocol.json'),len(cases),flush=True)

def run_case(c,maps,oi,ci,tables,routes,lp,ch,va,unpruned=False):
    t0=time.monotonic();g=np.array(c['glyph'],np.int64);out=scan(g,maps,oi,ci,lp,ch,va,unpruned)
    S,key,ties,nw,baseline,bkey=out;text=decode(g,maps,oi,ci,key);s2,C,W=score_py(text,lp,ch,va)
    assert abs(s2-S)<1e-11;assert np.array_equal(encrypt(text,maps,oi,ci,key),g)
    mi,ri=divmod(key,len(oi));rec=dict(id=c['id'],kind=c['kind'],source=c.get('source'),S=S,C=C,W=W,key_id=key,tie_count=len(ties),all_ties=ties,table=tables[mi],route=routes[ri],plaintext=''.join(chr(x+97) for x in text),baseline_S=baseline,baseline_key_id=bkey,gain=S-baseline,char_evaluations=len(maps)*len(oi),word_evaluations=nw,seconds=time.monotonic()-t0,independent_score_error=abs(s2-S),reencryption_exact=True)
    return rec

def run():
    proto=json.loads((ROOT/'protocol.json').read_text());assert (ROOT/'protocol.sha256').read_text().strip()==sha(ROOT/'protocol.json')
    for p,h in proto['hashes'].items():assert sha(ROOT/p)==h,p
    cases=json.loads((ROOT/'data/search_inputs.json').read_text());truth={x['id']:x for x in json.loads((ROOT/'data/positive_truth.json').read_text())}
    maps,oi,ci,tables,routes=banks();lp,ch,va=model();records=[]
    for c in cases:
        if c['kind']!='positive':continue
        rec=run_case(c,maps,oi,ci,tables,routes,lp,ch,va);rec['correct_letters']=sum(a==b for a,b in zip(rec['plaintext'],truth[c['id']]['plaintext']));rec['true_key_among_ties']=truth[c['id']]['key_id'] in rec['all_ties'];records.append(rec);save(ROOT/'results'/f'{c["id"]}.json',rec);print(c['id'],rec['correct_letters'],rec['seconds'],flush=True)
    gate=dict(exact=sum(x['correct_letters']==87 for x in records),correct_letters=sum(x['correct_letters'] for x in records));gate['passed']=gate['exact']>=12 and gate['correct_letters']>=1194;save(ROOT/'checks/sensitivity.json',gate);print('GATE',gate,flush=True)
    if not gate['passed']:return
    for c in cases:
        if c['kind']=='positive':continue
        rec=run_case(c,maps,oi,ci,tables,routes,lp,ch,va);records.append(rec);save(ROOT/'results'/f'{c["id"]}.json',rec)
        if c['kind']=='real' or len(records)%20==0:print(c['id'],rec['S'],rec['seconds'],flush=True)
    summary={'cases':len(records),'sensitivity':gate,'versions':{}}
    for x in [r for r in records if r['kind']=='real']:
        ns=[r for r in records if r['kind']=='null' and r['source']==x['id']];k=sum(n['S']>=x['S']-1e-11 for n in ns);kg=sum(n['gain']>=x['gain']-1e-11 for n in ns)
        summary['versions'][x['id']]={**x,'n_null':len(ns),'null_ge_S':k,'plus_one_tail_S':(k+1)/200,'null_ge_gain':kg,'plus_one_tail_gain':(kg+1)/200,'null_score_min':min(r['S'] for r in ns),'null_score_max':max(r['S'] for r in ns)}
    save(ROOT/'results/summary.json',summary);print('SUMMARY',json.dumps(summary),flush=True)
    audits=[]
    for name in [cases[0]['id'],'hauer_real','hart_real']:
        c=next(x for x in cases if x['id']==name);u=run_case(c,maps,oi,ci,tables,routes,lp,ch,va,True);r=next(x for x in records if x['id']==name)
        assert all(u[k]==r[k] for k in ['S','key_id','all_ties','baseline_S','baseline_key_id','plaintext']);audits.append({'id':name,'all_maxima_and_baseline_equal':True,'unpruned_word_evaluations':u['word_evaluations'],'seconds':u['seconds']})
    save(ROOT/'checks/full_unpruned.json',audits);print('UNPRUNED PASSED',flush=True)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='prepare':prepare()
    elif mode=='run':run()
