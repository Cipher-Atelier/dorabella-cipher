"""Unknown substitution key with I/J and U/V merged in both score and dictionary.
Search values are the24 allowed ASCII letters; J,V pinned to unused key entries24,25.
This is heuristic optimization, no exclusion claim and no null calibration.
"""
import json,time,hashlib
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from model_v5 import ROOT,LETTER,load_model
from automata import canonical
from wordsearch_v4 import ProposalDictionary,force_word
from wordpolish_v3 import char_score,fast_word,polish
from language import stable_seed,build_model
OUT=ROOT/'results/v6/merged_masc';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'id':'unknown-substitution-merged-IJ-UV-v6','restarts':256,'iterations':32000,'alpha':.5,'reading':'unchanged','null_calibration':False}

@njit(cache=True,nogil=True)
def merged_search(seq, initial, lp, children, vals, starts, lengths, gids, offsets, words, cdf,
           restarts, iterations, seed, alpha, tstart, tend, wordprob):
    np.random.seed(seed)
    K=int(seq.max())+1
    bestkey=initial.copy();besttext=initial[seq]
    best=char_score(besttext,lp)+alpha*fast_word(besttext,children,vals)
    trace=np.zeros((restarts+1,3));trace[0]=np.array([best,0.,0.])
    accepted_word=0;proposed_word=0
    schedule=tstart*np.exp(np.log(tend/tstart)*np.arange(iterations)/max(1,iterations-1))
    for r in range(restarts):
        if r==0:key=initial.copy()
        elif r%4==3:key=np.concatenate((np.random.permutation(LETTER),np.array([9,21],np.int64)))
        else:
            key=bestkey.copy() if r%2 else initial.copy()
            for _ in range(2+r%7):
                i=np.random.randint(K);j=np.random.randint(24)
                key[i],key[j]=key[j],key[i]
        text=key[seq];value=char_score(text,lp)+alpha*fast_word(text,children,vals)
        for step in range(iterations):
            isword=(len(starts)>0 and np.random.random()<wordprob)
            if isword:
                proposed_word+=1
                w=np.random.randint(len(starts));g=gids[w];lo=offsets[g];hi=offsets[g+1]
                u=np.random.random()
                # Binary search within this group's cumulative probability.
                while lo<hi:
                    mid=(lo+hi)//2
                    if cdf[mid]<u:lo=mid+1
                    else:hi=mid
                trial=force_word(key,seq,starts[w],lengths[w],words[lo])
            else:
                trial=key.copy();i=np.random.randint(K);j=np.random.randint(24)
                trial[i],trial[j]=trial[j],trial[i]
            txt=trial[seq]
            s=char_score(txt,lp)+alpha*fast_word(txt,children,vals)
            d=s-value
            if d>=0 or np.random.random()<np.exp(d/schedule[step]):
                key=trial;value=s
                if isword:accepted_word+=1
                if s>best+1e-12:
                    best=s;bestkey=key.copy()
        trace[r+1]=np.array([best,float(accepted_word),float(proposed_word)])
    return best,bestkey,trace


def run(case,model,p1):
    dest=OUT/(case['id']+'.json')
    if dest.exists():return
    t=time.monotonic();g=3*np.array(case['orientation'])+case['arcs'];seq=canonical(g);lp,scorer,ch,vals=model
    counts=np.bincount(seq,minlength=24);order=np.argsort(-counts);letters=LETTER[np.argsort(-p1[LETTER])]
    key=np.empty(26,np.int64);key[order]=letters;key[24]=9;key[25]=21
    args=ProposalDictionary(scorer).prepare(seq);seed=stable_seed(seq,'merged_masc_v6')
    ss,best,tr=merged_search(seq,key,lp,ch,vals,*args,256,32000,seed,.5,.06,.001,.25)
    ss,text,mapping,trace=polish(best[seq],lp,ch,vals,.5,30);best=mapping[best]
    assert np.all(np.isin(text,LETTER));assert np.array_equal(best[seq],text)
    string=''.join(chr(x+97) for x in text);_,seg=scorer.score(string,True)
    rec=dict(id=case['id'],score=float(ss),text=string,key=best.tolist(),segmentation=seg,restart_trace=tr.tolist(),polish_trace=trace.tolist(),seed=seed,seconds=time.monotonic()-t)
    dest.write_text(json.dumps(rec,indent=2));print(case['id'],ss,string,rec['seconds'],flush=True)

def main():
    model=load_model();_,p1=build_model();p1=p1.copy();p1[8]+=p1[9];p1[9]=0;p1[20]+=p1[21];p1[21]=0
    cs=[c for c in json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'] if c['kind']=='real']
    f=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['merged_masc_v6.py','model_v5.py','wordsearch_v4.py','wordpolish_v3.py','data/english_merged24_v5.npz']},dictionary=model[1].metadata)
    path=OUT/'frozen.json'
    if path.exists():assert json.loads(path.read_text())==f
    else:path.write_text(json.dumps(f,indent=2))
    (OUT/'inputs.json').write_text(json.dumps(cs,indent=2))
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda c:run(c,model,p1),cs))
if __name__=='__main__':main()
