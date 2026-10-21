"""Joint injective substitution + up to four adjacent-orientation transcription
errors. Exploratory sensitivity model: not an assertion that any glyph is wrong.
Only +/- one 45-degree step, never an arc-count change, insertion or deletion.
Every candidate retains an explicit correction list and a global bijective key.
"""
import argparse,json,hashlib,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from wordsearch_v4 import WordSearch,key_from_text,force_word
from wordpolish_v3 import char_score,fast_word,polish
from automata import canonical
from fastsolve import solve_fast
from language import stable_seed
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/v7/noisy';OUT.mkdir(parents=True,exist_ok=True)
CONFIG={'restarts':96,'iterations':24000,'max_edits':4,'cost_per_edit':4.0,
        'temperature_start':.06,'temperature_end':.001,'alpha':.5,
        'move_probabilities':[.45,.25,.20,.10],
        'word_length':[3,12],'word_sampling_power':.5,
        'char_baseline':[128,20000],'word_baseline':{'restarts':64,'iterations':16000}}

def dictionary_by_length(scorer):
    words=[];cdf=[];offsets=np.zeros(14,np.int64)
    for L in range(3,13):
        offsets[L]=len(words);rows=sorted((w,p) for w,p in scorer.words.items() if len(w)==L)
        weights=np.exp(np.array([p for _,p in rows])*.5);weights=np.cumsum(weights)/weights.sum();weights[-1]=1.
        for (w,_),p in zip(rows,weights):words.append([ord(c)-97 for c in w]+[-1]*(12-L));cdf.append(p)
        offsets[L+1]=len(words)
    return np.array(words,np.int64),np.array(cdf,np.float64),offsets

@njit(cache=True)
def match_pattern(seq,start,L,word):
    for i in range(L):
        for j in range(i):
            if (seq[start+i]==seq[start+j])!=(word[i]==word[j]):return False
    return True

@njit(cache=True)
def neighbour(original,delta):return 3*((original//3+delta)%8)+original%3

@njit(cache=True,nogil=True)
def joint_search(obs,initial,lp,children,vals,words,cdf,offsets,restarts,iterations,max_edits,cost,seed):
    np.random.seed(seed);n=len(obs);alpha=.5
    bestseq=obs.copy();bestkey=initial.copy();best=char_score(initial[obs],lp)+alpha*fast_word(initial[obs],children,vals)
    frontier=np.full(max_edits+1,-1e100);frontier[0]=best
    frontseq=np.empty((max_edits+1,n),np.int64);frontkey=np.empty((max_edits+1,len(initial)),np.int64)
    for i in range(max_edits+1):frontseq[i]=obs;frontkey[i]=initial
    trace=np.empty((restarts+1,2));trace[0,0]=best;trace[0,1]=0
    schedule=.06*np.exp(np.log(.001/.06)*np.arange(iterations)/max(1,iterations-1))
    for r in range(restarts):
        if r==0:key=initial.copy();seq=obs.copy()
        elif r%4==3:key=np.random.permutation(26);seq=obs.copy()
        else:
            key=bestkey.copy() if r%2 else initial.copy();seq=bestseq.copy() if r%2 else obs.copy()
            for _ in range(2+r%5):
                i=np.random.randint(24);j=np.random.randint(26);key[i],key[j]=key[j],key[i]
        edits=np.sum(seq!=obs)
        sc=char_score(key[seq],lp)+alpha*fast_word(key[seq],children,vals)-cost*edits/n
        for step in range(iterations):
            trialkey=key.copy();trialseq=seq.copy();u=np.random.random()
            if u<.45:
                i=np.random.randint(24);j=np.random.randint(26)
                trialkey[i],trialkey[j]=trialkey[j],trialkey[i]
            elif u<.70:
                L=np.random.randint(3,13);start=np.random.randint(n-L+1)
                lo=offsets[L];hi=offsets[L+1];draw=np.random.random()
                while lo<hi:
                    mid=(lo+hi)//2
                    if cdf[mid]<draw:lo=mid+1
                    else:hi=mid
                if not match_pattern(seq,start,L,words[lo]):continue
                trialkey=force_word(key,seq,start,L,words[lo])
            elif u<.90:
                i=np.random.randint(n);delta=np.random.randint(3)-1;trialseq[i]=neighbour(obs[i],delta)
            else:
                # Relocate a correction without temporarily using five edits.
                if edits>0:
                    target=np.random.randint(edits);seen=0
                    for i in range(n):
                        if seq[i]!=obs[i]:
                            if seen==target:trialseq[i]=obs[i];break
                            seen+=1
                j=np.random.randint(n);trialseq[j]=neighbour(obs[j],1 if np.random.random()<.5 else -1)
            ec=np.sum(trialseq!=obs)
            if ec>max_edits:continue
            txt=trialkey[trialseq]
            raw=char_score(txt,lp)+alpha*fast_word(txt,children,vals);value=raw-cost*ec/n
            # Keep the best actually evaluated candidate in every edit stratum.
            if raw>frontier[ec]+1e-12:
                frontier[ec]=raw;frontseq[ec]=trialseq;frontkey[ec]=trialkey
            delta=value-sc
            if delta>=0 or np.random.random()<np.exp(delta/schedule[step]):
                seq=trialseq;key=trialkey;edits=ec;sc=value
                if sc>best+1e-12:best=sc;bestseq=seq.copy();bestkey=key.copy()
        trace[r+1,0]=best;trace[r+1,1]=np.sum(bestseq!=obs)
    return best,bestseq,bestkey,trace,frontier,frontseq,frontkey

def report_candidate(obs,seq,key,eng):
    decoded=key[seq];cs=char_score(decoded,eng.lp);ws,seg=eng.scorer.score(decoded,True)
    edits=np.flatnonzero(seq!=obs);raw=cs+.5*ws
    return {'score':float(raw-CONFIG['cost_per_edit']*len(edits)/len(obs)),'unpenalized_score':float(raw),
     'edits':len(edits),'corrections':[{'position_1based':int(i+1),'from':int(obs[i]),'to':int(seq[i]),
                    'from_token':chr(65+obs[i]//3)+str(1+obs[i]%3),'to_token':chr(65+seq[i]//3)+str(1+seq[i]%3)} for i in edits],
     'corrected_glyphs':seq.tolist(),'key':key.tolist(),'decoded':decoded.tolist(),
     'text':''.join(chr(x+97) for x in decoded),'segmentation':seg,'char_score':float(cs),'word_score':float(ws)}

def run_case(case,eng,pack,config=None):
    conf=dict(CONFIG);conf.update(config or {})
    t=time.monotonic();g=np.array(case['glyph'],np.int64);s=canonical(g)
    _,k=solve_fast(s,eng.lp,eng.p1,*conf['char_baseline'],stable_seed(s,'v7_noisy_char'))
    base=eng.run(s,k[s],conf['word_baseline'],tag='v7_noisy_baseline');initial=key_from_text(g,np.array(base['decoded']))
    seed=stable_seed(g,'v7_joint_noise'+json.dumps(conf,sort_keys=True))
    res=joint_search(g,initial,eng.lp,eng.children,eng.vals,*pack,conf['restarts'],conf['iterations'],conf['max_edits'],conf['cost_per_edit'],seed)
    b,seq,key,trace,front,seqs,keys=res
    # Word-aware greedy polishing does not alter correction positions.
    candidates=[report_candidate(g,g,initial,eng)]
    for i in range(conf['max_edits']+1):
        if front[i]<-1e90:continue
        sc,txt,mapping,tr=polish(keys[i][seqs[i]],eng.lp,eng.children,eng.vals,.5,30)
        candidates.append(report_candidate(g,seqs[i],mapping[keys[i]],eng))
    best=max(candidates,key=lambda x:x['score'])
    record={'id':case['id'],'kind':case['kind'],'config':conf,'seed':seed,'best':best,'baseline':base,
        'frontier':candidates,'trace':trace.tolist(),'seconds':time.monotonic()-t,'glyph':case['glyph']}
    if case.get('plaintext'):
        truth=np.array([ord(c)-97 for c in case['plaintext']]);record['accuracy']=float(np.mean(truth==np.array(best['decoded'])))
        record['baseline_accuracy']=float(np.mean(truth==np.array(base['decoded'])))
        if 'true_glyph' in case:record['corrected_cipher_accuracy']=float(np.mean(np.array(best['corrected_glyphs'])==np.array(case['true_glyph'])))
    return record

def development_inputs():
    old=[x for x in json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'] if x['kind']=='positive']
    rng=np.random.default_rng(20260926711);out=[]
    for j,i in enumerate([0,3,14,18,22,30]):
        txt=old[i]['original_plaintext'].lower();s=canonical(np.array([ord(c)-97 for c in txt]));clean=rng.permutation(24)[s];g=clean.copy();positions=rng.choice(87,size=2 if j<3 else 4,replace=False)
        for p in positions:g[p]=neighbour(g[p],int(rng.choice([-1,1])))
        out.append(dict(id=f'dev_{j:02d}',kind='development',glyph=g.tolist(),true_glyph=clean.tolist(),plaintext=txt,corrupted_positions_1based=(positions+1).tolist(),source=old[i]['id']))
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--mode',choices=['dev','main'],default='dev');a=ap.parse_args()
    eng=WordSearch();pack=dictionary_by_length(eng.scorer)
    if a.mode=='dev':cases=development_inputs();target=OUT/'development'
    else:cases=json.loads((OUT/'inputs.json').read_text())['cases'];target=OUT/'records'
    target.mkdir(exist_ok=True)
    if a.mode=='main':
        tracked=['noisy_v7.py','inputs_v7.py','wordsearch_v4.py','wordpolish_v3.py','wordscore_v3.py','fastsolve.py','data/english_model.npz','results/v7/noisy/inputs.json']
        frozen=dict(config=CONFIG,hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in tracked},dictionary=eng.scorer.metadata)
        manifest=OUT/'frozen.json'
        if manifest.exists():assert json.loads(manifest.read_text())==frozen, 'Frozen protocol mismatch'
        else:manifest.write_text(json.dumps(frozen,indent=2))
    if a.mode=='dev':(target/'inputs.json').write_text(json.dumps(cases,indent=2))
    # Compile before parallel calls to avoid concurrent compilation.
    g=np.array(cases[0]['glyph']);joint_search(g,np.arange(26),eng.lp,eng.children,eng.vals,*pack,1,1,4,4.,1)
    def do(c):
        path=target/(c['id']+'.json')
        if path.exists():return json.loads(path.read_text())
        r=run_case(c,eng,pack);path.write_text(json.dumps(r,indent=2));print(c['id'],round(r['best']['score'],6),r.get('accuracy',''),r['best']['edits'],round(r['seconds'],1),flush=True);return r
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(do,cases))
if __name__=='__main__':main()
