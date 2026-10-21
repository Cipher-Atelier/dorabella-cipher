"""Finite coordinate accumulation cipher. No historical key asserted."""
import json, hashlib, itertools, datetime, sys, time, platform
from pathlib import Path
import numpy as np
from archived_support import word_py, euler_shuffle, paircounts
R=Path(__file__).resolve().parents[1]
A='abcdefghiklmnopqrstuwxyz'
L=np.array([ord(c)-97 for c in A])
def save(p,x): (R/p).write_text(json.dumps(x,indent=2)+'\n')
def sha(p): return hashlib.sha256((R/p).read_bytes()).hexdigest()
def bank():
    maps=[]; params=[]
    for layout,s,h,q in itertools.product(range(2),(1,-1),range(8),itertools.permutations(range(3))):
        maps.append([[int(L[3*((s*o+h)%8)+q[c] if layout==0 else 8*q[c]+((s*o+h)%8)]) for c in range(3)] for o in range(8)])
        params.append([layout,s,h,list(q)])
    return np.array(maps),params
M,PARAM=bank()
def decode(g,key):
    mi,route=divmod(key,96);rev,reset,state=route//48,(route//24)%2,route%24
    g=np.asarray(g);x=g[::-1] if rev else g
    cuts=[0,87] if not reset else ([0,27,58,87] if rev else [0,29,60,87])
    prev=np.roll(x,1).copy()
    for st in cuts[:-1]:prev[st]=state
    return M[mi,(x//3-prev//3)%8,(x%3-prev%3)%3]
def encrypt(t,key):
    mi,route=divmod(key,96);rev,reset,state=route//48,(route//24)%2,route%24
    inv={int(M[mi,o,c]):(o,c) for o in range(8) for c in range(3)}
    cuts=[0,87] if not reset else ([0,27,58,87] if rev else [0,29,60,87])
    out=[];o,c=divmod(state,3)
    for i,a in enumerate(t):
        if i in cuts[:-1]:o,c=divmod(state,3)
        u,v=inv[int(a)];o=(o+u)%8;c=(c+v)%3;out.append(3*o+c)
    return np.array(out[::-1] if rev else out)
def texts(g):
    # key order is map then rev/reset/state; all 18,432 definitions, duplicates retained.
    variants=[]
    for rev,reset,state in itertools.product(range(2),range(2),range(24)):
        x=np.asarray(g)[::-1] if rev else np.asarray(g)
        prev=np.roll(x,1).copy()
        for st in ([0] if not reset else ([0,27,58] if rev else [0,29,60])):prev[st]=state
        variants.append(((x//3-prev//3)%8,(x%3-prev%3)%3))
    oo=np.array([v[0] for v in variants]);cc=np.array([v[1] for v in variants])
    return M[:,oo,cc].reshape(-1,87)
def model():
    z=np.load(R/'data/scoring.npz');return z['lp'],z['children'],z['vals']
def search(g,lp,ch,va):
    t=texts(g);idx=((t[:,:-3]*26+t[:,1:-2])*26+t[:,2:-1])*26+t[:,3:]
    C=lp[idx].sum(axis=1)/84
    order=np.argsort(-C,kind='stable');best=-1e100;ties=[];nw=0
    for k in order:
        if C[k]<best-1e-11:break # W<=0 gives a safe upper bound, with conservative tolerance.
        w=word_py(t[k],ch,va);s=float(C[k]+.5*w);nw+=1
        if s>best:best=s;ties=[int(k)]
        elif s==best:ties.append(int(k))
    ties.sort();k=ties[0]
    assert np.array_equal(encrypt(t[k],k),g)
    return dict(S=best,key=k,all_ties=ties,plaintext=''.join(chr(int(a)+97) for a in t[k]),char_evaluations=len(t),word_evaluations=nw,reencryption_exact=True)
def prepare():
    # No candidate score is evaluated here.
    rng=np.random.default_rng(202610151701)
    old=json.loads((R/'data/old_positive_truth.json').read_text());truth=[];cases=[]
    for i,x in enumerate(old):
        mi=int(rng.integers(192));route=(i%2)*48+((i//2)%2)*24+int(rng.integers(24));key=mi*96+route
        t=np.array([ord(a)-97 for a in x['plaintext']]);g=encrypt(t,key)
        assert np.array_equal(decode(g,key),t)
        truth.append(dict(id=x['id'],plaintext=x['plaintext'],key=key))
        cases.append(dict(id=x['id'],kind='positive',glyph=g.tolist()))
    original=json.loads((R/'data/old_search_inputs.json').read_text())
    for x in original:
        if x['kind']!='real':continue
        cases.append(x)
        for j in range(199):
            g=euler_shuffle(x['glyph'],rng)
            assert paircounts(g)==paircounts(x['glyph'])
            assert sorted(g)==sorted(x['glyph']) and g[0]==x['glyph'][0] and g[-1]==x['glyph'][-1]
            cases.append(dict(id=x['id']+'_new_'+str(j).zfill(3),kind='null',source=x['id'],glyph=g.tolist()))
    save('data/cases.json',cases);save('data/truth.json',truth)
    protocol=dict(id='dorabella-coordinate-accumulation-1',frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        model='g_i=(o_i,c_i). d_i=((o_i-o_previous) mod8,(c_i-c_previous) mod3); p_i=table(d_i). Encryption accumulates inverse table increments. Previous state at start is u in Z8 x Z3.',
        table='Alphabet abcdefghiklmnopqrstuwxyz. For s=+1,-1; h=0..7; q all6 permutations of0,1,2: table(o,c)=alphabet[3*((s*o+h)%8)+q[c]] or alphabet[8*q[c]+((s*o+h)%8)]. 192 definitions.',
        routes='Forward/reverse whole sequence; continuous accumulation or reset at printed rows29/31/27 (27/31/29 reversed). One common initial state u=0..23, reused at every reset; no independent row states.',
        ordering='map order: layout,s,h,q lexicographic with s=(1,-1). route=rev*48+reset*24+u. key=map_id*96+route. Preserve all exact float64 ties; representative smallest key.',
        budget='18432 definitions per case; 14 positives then, ONLY if gate passes, 2 real +398 null=414 cases; 7630848 C evaluations maximum. No expansion or retuning. Gate failure stops before real/null scoring.',
        score='Archived S=C+0.5W unchanged. C is mean over84 four-letter windows; W archived 87-letter segmentation, TextBlob trie. Every position used, no holdout. Sort by C; W<=0 so skip only when C<best-1e-11.',
        gate='Before any real/null search: >=12/14 exactly87/87 AND >=1194/1218 correct letters; otherwise stop and report sensitivity failure, not negative result for Dorabella.',
        controls='14 old known texts freshly encrypted; regression only, not blind. 199 fresh directed-bigram/count/endpoints preserving Wilson samples per transcription, seed202610151701; identical full key search. Negative controls conditional on ciphertext pairs, not a universal null.',
        success='Numerical lead requires separately (1+#null S>=real S-1e-11)/200<=0.01. Decipherment additionally needs coherent complete87letters without edits and independent historical corroboration. No global adaptive-search significance. No combining transcriptions, even if both pass.',
        failure='If valid search has no numerical lead, this finite test supplies no support. Gate/audit failure is an invalid or insensitive test, not evidence against the cipher. Numerical lead without coherence/corroboration is unresolved.',
        rationale='Mathematical hypothesis only: natural group Z8xZ3 supports one-memory reversible accumulated encoding. Unlike static substitution or lagged re-pairing, differences depend on previous glyph. Signs/rotations exhaust geometric dihedral symmetries; arc permutations exhaust3 labels; two natural flattenings. Common reset states avoid unconstrained row fitting. No authenticated historical evidence. Novelty limited to supplied inspected code/protocols; early full research history unavailable.',
        audits='Independent scalar transform/inverse and scorer; compare complete candidate banks, roundtrip every key with deterministic87letter message before search; verify every returned tied winner and every case, controls invariants; independent full unpruned search for first positive and both reals if gate passes.',
        scope='All87 used. Hauer and Hartmeier are alternative related readings, never independent observations. External messages/orders/publication prohibited. Computations in this chat runtime only.',
        environment=dict(python=platform.python_version(),numpy=np.__version__,numba='unavailable'),
        hashes={str(p.relative_to(R)):sha(p.relative_to(R)) for p in sorted(R.rglob('*')) if p.is_file() and p.suffix in ('.py','.json','.npz')})
    save('protocol.json',protocol);(R/'protocol.sha256').write_text(sha('protocol.json')+'\n');print('FROZEN',sha('protocol.json'),flush=True)
def run():
    p=json.loads((R/'protocol.json').read_text());assert sha('protocol.json')==(R/'protocol.sha256').read_text().strip()
    for f,h in p['hashes'].items():assert sha(f)==h,f
    lp,ch,va=model();assert va.max()<=0
    cases=json.loads((R/'data/cases.json').read_text());truth={x['id']:x for x in json.loads((R/'data/truth.json').read_text())};out=[]
    for c in cases:
        if c['kind']!='positive':continue
        start=time.monotonic();r=search(c['glyph'],lp,ch,va);r.update(id=c['id'],kind=c['kind'],seconds=time.monotonic()-start)
        r['correct_letters']=sum(a==b for a,b in zip(r['plaintext'],truth[c['id']]['plaintext']));r['true_key_among_ties']=truth[c['id']]['key'] in r['all_ties'];out.append(r);save('results/'+c['id']+'.json',r);print(c['id'],r['correct_letters'],r['seconds'],flush=True)
    gate=dict(exact=sum(r['correct_letters']==87 for r in out),letters=sum(r['correct_letters'] for r in out));gate['passed']=gate['exact']>=12 and gate['letters']>=1194;save('checks/gate.json',gate);print('GATE',gate,flush=True)
    if not gate['passed']:return
    for c in cases:
        if c['kind']=='positive':continue
        start=time.monotonic();r=search(c['glyph'],lp,ch,va);r.update(id=c['id'],kind=c['kind'],source=c.get('source'),seconds=time.monotonic()-start);out.append(r);save('results/'+c['id']+'.json',r)
        if c['kind']=='real' or len(out)%20==0:print(c['id'],r['S'],r['seconds'],flush=True)
    summary=dict(cases=len(out),gate=gate,versions={})
    for r in out:
        if r['kind']!='real':continue
        ns=[x for x in out if x.get('source')==r['id']];k=sum(x['S']>=r['S']-1e-11 for x in ns)
        summary['versions'][r['id']]={**r,'null_ge':k,'n_null':len(ns),'descriptive_tail':(k+1)/200}
    save('results/summary.json',summary);print('FINISHED',json.dumps(summary),flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
