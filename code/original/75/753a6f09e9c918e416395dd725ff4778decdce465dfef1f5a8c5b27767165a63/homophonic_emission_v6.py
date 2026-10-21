"""Deterministic many-to-one glyph->letter search with homophone emission penalty.
For each letter, empirical probabilities of its cipher homophones sum to one.
The maximized mean log emission is H(plaintext)-H(ciphertext), non-positive.
The whole objective remains a heuristic because the word term is not a calibrated likelihood.
No symbol insertion/deletion/transposition, but multiple glyphs may map to same letter.
Every proposal respects all occurrences of each glyph. Word-aware heuristic search.
Not all homophonic keys are exhausted; scored controls run identical protocol.
"""
import json,hashlib,time,argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from model_v5 import ROOT
from automata import canonical
from language import stable_seed
from fastsolve import solve_fast
from wordsearch_v4 import WordSearch,equality_pattern
from wordpolish_v3 import char_score,fast_word
OUT=ROOT/'results/v6/homophonic_emission';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'family':'many-glyphs-one-letter-emission-v6','emission_penalty':'empirical H(plaintext)-H(ciphertext); iid homophone probabilities at MLE','restarts':128,'iterations':16000,
 'temperature':[.06,.002],'wordprob':.4,'score':'unmerged26 C+0.5W + H(plaintext)-H(ciphertext)',
 'initial_mono':[128,20000],'null_pairs':19,'null_seed':20260926069,'positive_seed':20260926070,
 'n_positive':8,'positive_status':'old first8 historical texts; 3 letters receive 2 possible glyphs',
 'arbitrary_nulls':False,'state':False,'reading':'unchanged'}

def prepare(seq,scorer):
    bylen=defaultdict(list)
    for w,lp in sorted(scorer.words.items()):
        if 3<=len(w)<=12:bylen[len(w)].append((w,lp))
    bank={};starts=[];lengths=[];ids=[]
    for start in range(len(seq)):
        for L in range(3,min(12,len(seq)-start)+1):
            pat=equality_pattern(seq[start:start+L])
            if pat not in bank:
                pos={};pairs=[]
                for j,k in enumerate(pat):
                    if k in pos:pairs.append((pos[k],j))
                    else:pos[k]=j
                rows=[(w,lp) for w,lp in bylen[L] if all(w[a]==w[b] for a,b in pairs)]
                bank[pat]=(len(bank),rows)
            gid,rows=bank[pat]
            if rows:starts.append(start);lengths.append(L);ids.append(gid)
    offsets=[0];words=[];cdf=[]
    for gid,rows in bank.values():
        if rows:
            wts=np.exp(.5*np.array([lp for _,lp in rows]));cum=np.cumsum(wts)/wts.sum();cum[-1]=1.
            for (w,_),v in zip(rows,cum):words.append([ord(c)-97 for c in w]+[-1]*(12-len(w)));cdf.append(v)
        offsets.append(len(words))
    return tuple(np.asarray(x,dtype=(np.float64 if i==5 else np.int64)) for i,x in enumerate([starts,lengths,ids,offsets,words,cdf]))

@njit(cache=True)
def entropy(a):
    counts=np.zeros(26,np.int64)
    for v in a:counts[v]+=1
    result=0.
    for n in counts:
        if n>0:
            p=n/len(a);result-=p*np.log(p)
    return result

@njit(cache=True)
def objective(text,lp,children,vals,h_cipher):
    return char_score(text,lp)+.5*fast_word(text,children,vals)+entropy(text)-h_cipher

@njit(cache=True,nogil=True)
def solve(seq,initial,lp,children,vals,p1,starts,lengths,gids,offsets,words,cdf,restarts,iterations,seed):
    np.random.seed(seed);h_cipher=entropy(seq);K=int(seq.max())+1;key=initial[:K].copy();bestkey=key.copy()
    text=key[seq];best=objective(text,lp,children,vals,h_cipher)
    trace=np.empty(restarts+1,np.float64);trace[0]=best
    pc=np.cumsum(p1);pc/=pc[-1]
    schedule=.06*np.exp(np.log(.002/.06)*np.arange(iterations)/max(1,iterations-1))
    for r in range(restarts):
        if r==0:key=initial[:K].copy()
        elif r%4==3:key=np.random.randint(0,26,K)
        else:
            key=bestkey.copy()
            for _ in range(2+r%7):key[np.random.randint(K)]=np.random.randint(26)
        text=key[seq];value=objective(text,lp,children,vals,h_cipher)
        for step in range(iterations):
            trial=key.copy();u=np.random.random()
            if u<.4 and len(starts):
                w=np.random.randint(len(starts));g=gids[w];lo=offsets[g];hi=offsets[g+1];v=np.random.random()
                while lo<hi:
                    mid=(lo+hi)//2
                    if cdf[mid]<v:lo=mid+1
                    else:hi=mid
                for j in range(lengths[w]):trial[seq[starts[w]+j]]=words[lo,j]
            elif u<.6:
                a=np.random.randint(K);b=np.random.randint(K);trial[a],trial[b]=trial[b],trial[a]
            else:
                a=np.random.randint(K);v=np.random.random();b=0
                while b<25 and pc[b]<v:b+=1
                trial[a]=b
            text=trial[seq];s=objective(text,lp,children,vals,h_cipher);delta=s-value
            if delta>=0 or np.random.random()<np.exp(delta/schedule[step]):
                key=trial;value=s
                if s>best+1e-12:best=s;bestkey=key.copy()
        trace[r+1]=best
    # Exhaust all one-glyph reassignments to a local optimum, not a global proof.
    for _ in range(30):
        improved=False;nextkey=bestkey.copy();nextscore=best
        for k in range(K):
            for a in range(26):
                q=bestkey.copy();q[k]=a;txt=q[seq];s=objective(txt,lp,children,vals,h_cipher)
                if s>nextscore+1e-12:nextscore=s;nextkey=q;improved=True
        if not improved:break
        best=nextscore;bestkey=nextkey
    return best,bestkey,trace

def make_cases():
    old=json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'];real=[]
    for c in old:
        if c['kind']=='real':real.append(dict(id=c['id'],kind='real',glyph=(3*np.array(c['orientation'])+c['arcs']).tolist()))
    out=real.copy();rng=np.random.default_rng(PROTOCOL['null_seed'])
    for j in range(PROTOCOL['null_pairs']):
        p=rng.permutation(87)
        for r in real:out.append(dict(id=r['id'].replace('_real',f'_null_{j:02d}'),kind='null',pair=j,glyph=np.array(r['glyph'])[p].tolist(),permutation=p.tolist()))
    rng=np.random.default_rng(PROTOCOL['positive_seed'])
    for j,c in enumerate([c for c in old if c['kind']=='positive'][:8]):
        truth=c['original_plaintext'].lower();letters=sorted(set(truth));assert len(letters)<=21
        freq={a:truth.count(a) for a in letters};chosen=rng.choice([a for a in letters if freq[a]>=2],3,replace=False).tolist()
        pool=rng.permutation(24).tolist();mapping={a:[pool.pop()] for a in letters}
        for a in chosen:mapping[a].append(pool.pop())
        glyph=[int(rng.choice(mapping[a])) for a in truth]
        out.append(dict(id=f'positive_{j:02d}',kind='positive',glyph=glyph,plaintext=truth,generating=mapping,source=c['id']))
    data=dict(protocol=PROTOCOL,cases=out);p=OUT/'inputs.json'
    if p.exists():assert json.loads(p.read_text())==data
    else:p.write_text(json.dumps(data,indent=2))
    return out

def run(c,engine):
    p=OUT/(c['id']+'.json')
    if p.exists():return json.loads(p.read_text())
    t=time.monotonic();seq=canonical(np.array(c['glyph']));args=prepare(seq,engine.scorer)
    _,initial=solve_fast(seq,engine.lp,engine.p1,*PROTOCOL['initial_mono'],stable_seed(seq,'homophone_emission_v6_initial'))
    seed=stable_seed(seq,'homophone_emission_v6_main');score,key,trace=solve(seq,initial,engine.lp,engine.children,engine.vals,engine.p1,*args,PROTOCOL['restarts'],PROTOCOL['iterations'],seed)
    text=''.join(chr(int(a)+97) for a in key[seq]);ws,seg=engine.scorer.score(text,True)
    record=dict(id=c['id'],kind=c['kind'],best_score=float(score),best_text=text,key=key.tolist(),segmentation=seg,
        emission_penalty=float(entropy(key[seq])-entropy(seq)),unpenalized_score=float(char_score(key[seq],engine.lp)+.5*ws),n_plain_letters=len(set(key.tolist())),n_glyphs=int(seq.max())+1,trace=trace.tolist(),seed=seed,seconds=time.monotonic()-t)
    if c['kind']=='positive':record['accuracy']=sum(a==b for a,b in zip(text,c['plaintext']))/87
    p.write_text(json.dumps(record,indent=2));print(c['id'],round(score,6),record.get('accuracy',''),text,round(record['seconds'],2),flush=True);return record

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['all','real','positive','null'],default='real');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    engine=WordSearch();cs=make_cases();data=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['homophonic_emission_v6.py','wordpolish_v3.py','fastsolve.py','wordscore_v3.py','data/english_model.npz','results/v6/homophonic/inputs.json']},dictionary=engine.scorer.metadata)
    p=OUT/'frozen.json'
    if p.exists():assert json.loads(p.read_text())==data
    else:p.write_text(json.dumps(data,indent=2))
    todo=[c for c in cs if (a.mode=='all' or a.mode==c['kind']) and not (OUT/(c['id']+'.json')).exists()]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(lambda c:run(c,engine),todo))
if __name__=='__main__':main()
