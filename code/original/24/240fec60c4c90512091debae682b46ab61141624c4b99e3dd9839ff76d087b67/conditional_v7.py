"""Round 7: fixed-order monoalphabetic search under two null ensembles.
A directed Wilson last-exit tree + randomized edge lists gives uniform Euler
trails with fixed endpoints and directed adjacent-pair counts. This is a
standalone implementation of the same mathematical approach as k-let shuffling;
it is not a call to uShuffle, and does not claim a new shuffle algorithm.
"""
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, itertools, json, time
import numpy as np
from scipy.stats import chisquare
from automata import canonical
from language import stable_seed
from fastsolve import solve_fast
from wordsearch_v4 import WordSearch
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/v7/conditional';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'id':'conditional-bigram-null-v7','seed':20260926701,
 'n_null_each_transcription_each_type':99,'old_positive_texts':12,'positive_bigram_controls':9,
 'character_search':[128,20000],'word_search':{'restarts':64,'iterations':16000},
 'nulls':['unigram_permutation','fixed_endpoints_exact_directed_bigrams'],
 'scope':'fixed left-to-right order and injective substitution ONLY; not route search',
 'positive_status':'previously used historical texts, fresh random substitution, sensitivity only'}

def bigrams(seq):return Counter(zip(map(int,seq[:-1]),map(int,seq[1:])))

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

def geometry(seq):
    g=np.asarray(seq);d=g//3;c=g%3;diff=(d[1:]-d[:-1])%8
    return {'same_axis':int(np.sum(diff%4==0)),'opposite':int(np.sum(diff==4)),
      'mirrors':int(np.sum((diff==4)&(c[1:]==c[:-1])))}

def check_shuffle():
    rng=np.random.default_rng(20260926702);report={}
    for s in [(0,1,0,2,0,1,2,0),(0,0,1,2,1,0,1,2),(0,1,0,1,2,1,2,0)]:
        possible=sorted({p for p in itertools.permutations(s) if p[0]==s[0] and p[-1]==s[-1] and bigrams(p)==bigrams(s)})
        observed=Counter(tuple(euler_shuffle(s,rng)) for _ in range(24000))
        assert set(observed)==set(possible)
        chi=chisquare([observed[p] for p in possible])
        report[str(s)]={'n_possible':len(possible),'n':24000,'counts':[observed[p] for p in possible],
                         'chi2':float(chi.statistic),'p':float(chi.pvalue),'support':possible}
    raw=np.loadtxt(ROOT/'data/dorabella_smp2021.txt',dtype=str) if False else None
    old=json.loads((ROOT/'results/v6/routes/inputs.json').read_text())['cases']
    for case in [x for x in old if x['kind']=='real']:
        s=np.array(case['glyph']);zs=[euler_shuffle(s,rng) for _ in range(10000)]
        for z in zs:
            assert bigrams(s)==bigrams(z) and Counter(s)==Counter(z) and geometry(s)==geometry(z)
        report[case['id']]={'checked':len(zs),'unique':len({z.tobytes() for z in zs}),
               'mean_position_changes':float(np.mean([np.sum(z!=s) for z in zs])),'geometry':geometry(s)}
    (OUT/'shuffle_checks.json').write_text(json.dumps(report,indent=2));return report

def make_inputs():
    dest=OUT/'inputs.json'
    if dest.exists():return json.loads(dest.read_text())['cases']
    old=json.loads((ROOT/'results/v6/routes/inputs.json').read_text())['cases']
    real=[dict(x) for x in old if x['kind']=='real'];rng=np.random.default_rng(PROTOCOL['seed'])
    cases=real.copy()
    for r in real:
        g=np.array(r['glyph'])
        for style in ('unigram','bigram'):
            for j in range(PROTOCOL['n_null_each_transcription_each_type']):
                z=rng.permutation(g) if style=='unigram' else euler_shuffle(g,rng)
                cases.append(dict(id=f'{r["id"]}_{style}_{j:03d}',kind=style,source=r['id'],glyph=z.tolist(),replicate=j))
    oldpos=[x for x in json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'] if x['kind']=='positive']
    chosen=[0,1,2,3,8,9,10,11,20,21,22,23]
    for k,i in enumerate(chosen):
        p=oldpos[i]['original_plaintext'].lower();s=canonical(np.array([ord(c)-97 for c in p]));g=rng.permutation(24)[s]
        base=dict(id=f'positive_{k:02d}',kind='positive',glyph=g.tolist(),plaintext=p,source=oldpos[i]['id'])
        cases.append(base)
        for j in range(PROTOCOL['positive_bigram_controls']):
            cases.append(dict(id=f'positive_{k:02d}_bigram_{j:02d}',kind='positive_null',source=base['id'],glyph=euler_shuffle(g,rng).tolist()))
    dest.write_text(json.dumps(dict(protocol=PROTOCOL,cases=cases),indent=2));return cases

def run_one(case,engine):
    p=OUT/'records'/(case['id']+'.json');p.parent.mkdir(exist_ok=True)
    if p.exists():return json.loads(p.read_text())
    t=time.monotonic();s=canonical(np.asarray(case['glyph']));_,key=solve_fast(s,engine.lp,engine.p1,*PROTOCOL['character_search'],stable_seed(s,'v7_conditional_char'))
    rec=engine.run(s,key[s],PROTOCOL['word_search'],tag='v7_conditional_word');rec.update(id=case['id'],kind=case['kind'],source=case.get('source'),glyph=case['glyph'],seconds_total=time.monotonic()-t)
    rec['text']=''.join(chr(v+97) for v in rec['decoded'])
    if case['kind']=='positive':rec['accuracy']=float(np.mean(np.array(rec['decoded'])==np.array([ord(c)-97 for c in case['plaintext']])))
    p.write_text(json.dumps(rec,indent=2));print(case['id'],round(rec['score'],6),rec.get('accuracy',''),round(rec['seconds_total'],2),flush=True);return rec

def summarize(cases):
    records={x['id']:json.loads((OUT/'records'/(x['id']+'.json')).read_text()) for x in cases}
    r={}
    for name in ('hauer_real','hart_real'):
        sc=records[name]['score'];r[name]={'score':sc,'text':records[name]['text'],'segmentation':records[name]['segmentation']}
        for style in ('unigram','bigram'):
            vals=[records[x['id']]['score'] for x in cases if x['kind']==style and x['source']==name]
            k=sum(v>=sc-1e-12 for v in vals);r[name][style]={'n':len(vals),'ge':k,'p_plus_one':(k+1)/(len(vals)+1),'mean':float(np.mean(vals)),'range':[min(vals),max(vals)]}
    positives=[]
    for c in cases:
        if c['kind']=='positive':
            vals=[records[x['id']]['score'] for x in cases if x['kind']=='positive_null' and x['source']==c['id']]
            positives.append(dict(id=c['id'],accuracy=records[c['id']]['accuracy'],ge=sum(v>=records[c['id']]['score']-1e-12 for v in vals),n=len(vals)))
    r['positive_sensitivity']=positives;r['records']=len(records)
    (OUT/'summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--max-new',type=int);ap.add_argument('--check-shuffle',action='store_true');a=ap.parse_args()
    if a.check_shuffle:check_shuffle();return
    eng=WordSearch();cases=make_inputs()
    frozen=dict(protocol=PROTOCOL,hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),OUT/'inputs.json',ROOT/'data/english_model.npz',ROOT/'wordsearch_v4.py',ROOT/'fastsolve.py']},dictionary=eng.scorer.metadata)
    p=OUT/'frozen.json'
    if p.exists():assert json.loads(p.read_text())==frozen
    else:p.write_text(json.dumps(frozen,indent=2))
    tasks=[c for c in cases if not (OUT/'records'/(c['id']+'.json')).exists()]
    if a.max_new is not None:tasks=tasks[:a.max_new]
    # Compile serially before multithreading.
    s=canonical(np.array(cases[0]['glyph']));solve_fast(s,eng.lp,eng.p1,1,1,1);eng.run(s,np.arange(26)[s],{'restarts':1,'iterations':1,'final_greedy_sweeps':1},tag='compile')
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(lambda c:run_one(c,eng),tasks))
    if all((OUT/'records'/(c['id']+'.json')).exists() for c in cases):summarize(cases)
if __name__=='__main__':main()
