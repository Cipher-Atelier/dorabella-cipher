"""Direct word-aware search of a bijective substitution, with pattern-consistent
multi-letter proposals. This is a heuristic optimizer, NOT a posterior sampler.
No plaintext, correct automaton, or position-specific crib is accepted as input.
"""
from collections import defaultdict
import hashlib, json, time
from pathlib import Path
import numpy as np
from numba import njit
from wordscore_v3 import WordScorer, ROOT
from wordpolish_v3 import build_trie, fast_word, char_score, polish
from automata import canonical
from language import stable_seed, build_model

CONFIG = dict(alpha=0.5, restarts=16, iterations=8000,
              temperature_start=0.06, temperature_end=0.001,
              word_move_probability=0.25, min_word=3, max_word=12,
              word_sampling_count_power=0.5, final_greedy_sweeps=30)

def equality_pattern(values):
    seen={}; out=[]
    for v in values:
        if v not in seen: seen[v]=len(seen)
        out.append(seen[v])
    return tuple(out)

class ProposalDictionary:
    def __init__(self, scorer):
        groups=defaultdict(list)
        for w, logp in sorted(scorer.words.items()):
            if CONFIG['min_word']<=len(w)<=CONFIG['max_word']:
                groups[equality_pattern(w)].append((w,logp))
        self.groups=groups
    def prepare(self, seq):
        # Each window has a dictionary group with exactly its repeat pattern.
        pats={}; starts=[]; lengths=[]; gids=[]
        for start in range(len(seq)):
            for L in range(CONFIG['min_word'],min(CONFIG['max_word'],len(seq)-start)+1):
                pat=equality_pattern(seq[start:start+L])
                if pat not in self.groups: continue
                if pat not in pats:pats[pat]=len(pats)
                starts.append(start); lengths.append(L); gids.append(pats[pat])
        offsets=[0]; words=[]; cdf=[]
        for pat in pats:
            rows=self.groups[pat]
            weights=np.exp(np.array([v for _,v in rows])*CONFIG['word_sampling_count_power'])
            cumulative=np.cumsum(weights)/weights.sum()
            cumulative[-1]=1.
            for (w,_),p in zip(rows,cumulative):
                codes=[ord(c)-97 for c in w]
                words.append(codes+[-1]*(CONFIG['max_word']-len(codes))); cdf.append(p)
            offsets.append(len(words))
        return (np.array(starts,np.int64),np.array(lengths,np.int64),np.array(gids,np.int64),
                np.array(offsets,np.int64),np.array(words,np.int64).reshape(-1,CONFIG['max_word']),np.array(cdf,np.float64))

def key_from_text(seq, text):
    key=np.full(26,-1,np.int64)
    for tok,val in zip(seq,text):
        if key[tok]>=0 and key[tok]!=val:raise ValueError('Inconsistent substitution')
        key[tok]=val
    used=key[key>=0]
    if len(set(used))!=len(used):raise ValueError('Non-injective substitution')
    available=[x for x in range(26) if x not in used]
    key[key<0]=available
    assert np.array_equal(key[seq],text)
    return key

@njit(cache=True)
def force_word(key,seq,start,L,word):
    trial=key.copy()
    # Word pattern was checked before invoking this routine. Each enforced
    # mapping can be satisfied by swapping with the inverse-image of a letter.
    for j in range(L):
        tok=seq[start+j]; letter=word[j]
        if trial[tok]==letter:continue
        for other in range(26):
            if trial[other]==letter:break
        trial[tok],trial[other]=trial[other],trial[tok]
    return trial

@njit(cache=True,nogil=True)
def search(seq, initial, lp, children, vals, starts, lengths, gids, offsets, words, cdf,
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
        elif r%4==3:key=np.random.permutation(26)
        else:
            key=bestkey.copy() if r%2 else initial.copy()
            for _ in range(2+r%7):
                i=np.random.randint(K);j=np.random.randint(26)
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
                trial=key.copy();i=np.random.randint(K);j=np.random.randint(26)
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

class WordSearch:
    def __init__(self):
        self.lp,self.p1=build_model(); self.scorer=WordScorer()
        self.children,self.vals=build_trie(self.scorer);self.proposals=ProposalDictionary(self.scorer)
    def run(self,seq,initial_text,config=None,tag='v4'):
        conf=dict(CONFIG);conf.update(config or {})
        seq=np.asarray(seq,dtype=np.int64);initial_text=np.asarray(initial_text,dtype=np.int64)
        key=key_from_text(seq,initial_text);args=self.proposals.prepare(seq)
        seed=stable_seed(seq,tag+json.dumps(conf,sort_keys=True))
        t=time.monotonic()
        score,bestkey,trace=search(seq,key,self.lp,self.children,self.vals,*args,
                conf['restarts'],conf['iterations'],seed,conf['alpha'],conf['temperature_start'],
                conf['temperature_end'],conf['word_move_probability'])
        score,text,mapping,greedy_trace=polish(bestkey[seq],self.lp,self.children,self.vals,conf['alpha'],conf['final_greedy_sweeps'])
        finalkey=mapping[bestkey]
        assert np.array_equal(finalkey[seq],text)
        assert len(set(finalkey.tolist()))==26
        ws,seg=self.scorer.score(text,True);cs=char_score(text,self.lp)
        assert abs(score-cs-conf['alpha']*ws)<1e-9
        return dict(score=float(score),char_score=float(cs),word_score=float(ws),decoded=text.tolist(),
                    key=finalkey.tolist(),segmentation=seg,trace=trace.tolist(),greedy_trace=greedy_trace.tolist(),
                    proposal_windows=len(args[0]),seed=seed,config=conf,seconds=time.monotonic()-t)
