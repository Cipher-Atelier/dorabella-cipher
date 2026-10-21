"""Exact search of a notebook-inspired, block-preserving key family.
NOT an exhaustive search of all monoalphabetic keys. All candidates retain
alphabetical triples; only the eight direction assignments and a COMMON
three-position arc permutation are free. No guessed words or cipher edits.
"""
from pathlib import Path
import sys,itertools,hashlib,json,time,argparse,os
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from model_v5 import load_model,LETTER,ALPHABET
from wordpolish_v3 import char_score,fast_word
from conditional_v7 import euler_shuffle,bigrams
from collections import Counter
P8=np.array(list(itertools.permutations(range(8))),dtype=np.int64)
P3=np.array(list(itertools.permutations(range(3))),dtype=np.int64)
NK=len(P8)*len(P3)
PROTOCOL=dict(id='round10-notebook-block-exact-v1',
 formula='key[3*o+c] = ALPHABET[3*perm8[o]+perm3[c]]; SAME perm3 for every direction',
 alphabet=ALPHABET,definitions=NK,unique_full_keys=NK,
 reading='87 unchanged glyphs, left to right; ignore dots/row breaks as commands',
 character_model='archived english_merged24_v5.npz, unchanged',
 score='S = mean conditional log 4gram + 0.5 * Viterbi word segmentation / length; unchanged v5 score',
 search='Exhaustive: compute full char and word scores for EVERY key, no early rejection',
 secondary='Choose key using first 43 glyphs only by same S; evaluate suffix 44 with that key, no suffix refinement; fixed before scores',
 tie='First key in lexicographic perm8, then perm3 order selected by numpy.argmax; comparisons allow 1e-10',
 controls='39 independently generated global directed-bigram-preserving controls for each published transcription, with fixed first/last glyph; each gets full search. Do not select best transcription.',
 null_count_each=39,null_seed=202610011010,
 positives='12 new published Elgar letter openings, known random keys; first87 ASCII letters after salutation, j->i,v->u; two old regression texts separate',
 interpretation='Language score is heuristic, no probability of plaintext. Exploratory family chosen after nine rounds; no global multiple-search correction.')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def text(a):return ''.join(chr(97+int(v)) for v in a)
def key_at(i):
    a,b=divmod(int(i),6)
    return LETTER[(3*P8[a,:,None]+P3[b,None,:]).reshape(-1)]
@njit(cache=True,nogil=True)
def all_scores(g,lp,children,vals,p8,p3,letter):
    n=len(g);buf=np.empty(n,np.int64);out=np.empty((len(p8)*len(p3),4),np.float64)
    q=0
    for a in range(len(p8)):
        for b in range(len(p3)):
            for j in range(n):buf[j]=letter[3*p8[a,g[j]//3]+p3[b,g[j]%3]]
            out[q,0]=char_score(buf,lp)
            out[q,1]=fast_word(buf,children,vals)
            out[q,2]=char_score(buf[:43],lp)
            out[q,3]=fast_word(buf[:43],children,vals)
            q+=1
    return out

def setup():
    lp,sc,ch,v=load_model()
    cases=json.loads((HERE/'data/inputs_base.json').read_text())
    rng=np.random.default_rng(PROTOCOL['null_seed'])
    for r in [x for x in cases if x['kind']=='real']:
        g=np.array(r['glyph'],np.int64)
        for i in range(PROTOCOL['null_count_each']):
            z=euler_shuffle(g,rng)
            assert Counter(z)==Counter(g) and bigrams(z)==bigrams(g) and z[0]==g[0] and z[-1]==g[-1]
            cases.append(dict(id=f'{r["id"]}_pair_{i:02d}',kind='null',source=r['id'],glyph=z.tolist()))
    raw=json.dumps(cases,indent=2)
    dest=HERE/'data/inputs.json'
    if dest.exists():assert dest.read_text()==raw
    else:dest.write_text(raw)
    deps=[HERE/'prepare.py',HERE/'table_search.py',HERE/'data/elgar_letters.json',dest,
          ROOT/'model_v5.py',ROOT/'wordpolish_v3.py',ROOT/'conditional_v7.py',ROOT/'data/english_merged24_v5.npz']
    frozen=dict(protocol=PROTOCOL,hashes={str(p.relative_to(ROOT)):sha(p) for p in deps},dictionary=sc.metadata)
    p=HERE/'frozen_protocol.json'
    if p.exists():assert json.loads(p.read_text())==frozen,'Frozen protocol changed'
    else:p.write_text(json.dumps(frozen,ensure_ascii=False,indent=2))
    return cases,lp,sc,ch,v

def run_one(case,lp,sc,ch,v):
    folder=HERE/'results/records';folder.mkdir(exist_ok=True)
    out=folder/(case['id']+'.json');arrfile=folder/(case['id']+'_scores.npz')
    if out.exists():return json.loads(out.read_text())
    t=time.time();g=np.array(case['glyph'],np.int64)
    scores=all_scores(g,lp,ch,v,P8,P3,LETTER)
    ss=scores[:,0]+.5*scores[:,1];hs=scores[:,2]+.5*scores[:,3]
    best=int(np.argmax(ss));head=int(np.argmax(hs));char=int(np.argmax(scores[:,0]))
    d=key_at(best)[g];h=key_at(head)[g]
    inds=sorted(range(NK),key=lambda i:(-ss[i],i))[:8]
    tops=[]
    for i in inds:
        decoded=key_at(i)[g];a,b=divmod(i,6)
        tops.append(dict(key_index=i,perm8=P8[a].tolist(),perm3=P3[b].tolist(),glyph_to_ascii_letter=key_at(i).tolist(),
           plaintext=text(decoded),segmentation=sc.score(decoded,True)[1],score=float(ss[i])))
    r=dict(id=case['id'],kind=case['kind'],source=case.get('source'),key_count=NK,
      best_key=best,score=float(ss[best]),char=float(scores[best,0]),word=float(scores[best,1]),decoded=text(d),
      char_winner_key=char,char_winner_decoded=text(key_at(char)[g]),char_best=float(scores[char,0]),
      prefix_key=head,prefix_score=float(hs[head]),prefix_decoded=text(h),
      suffix_score=float(char_score(h[43:],lp)+.5*fast_word(h[43:],ch,v)),
      near_best_key_count=int(np.sum(ss>=ss[best]-1e-10)),top=tops,
      scores_sha256=hashlib.sha256(scores.tobytes()).hexdigest(),seconds=time.time()-t)
    if 'plaintext' in case:
        true=np.array([ord(c)-97 for c in case['plaintext']],np.int64)
        pi=np.flatnonzero(np.all(P8==case['true_perm8'],axis=1))[0]*6+np.flatnonzero(np.all(P3==case['true_perm3'],axis=1))[0]
        assert np.array_equal(key_at(pi)[g],true)
        r.update(correct=int(np.sum(d==true)),char_correct=int(np.sum(key_at(char)[g]==true)),
          head_fit_correct=int(np.sum(h[:43]==true[:43])),suffix_correct=int(np.sum(h[43:]==true[43:])),
          true_score=float(ss[pi]),true_rank_strict=1+int(np.sum(ss>ss[pi]+1e-10)),
          true_key_index=int(pi),prefix_true_key_score=float(hs[pi]),true_plaintext=case['plaintext'])
    np.savez_compressed(arrfile,scores=scores)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print(case['id'],'S',round(r['score'],6),'correct',r.get('correct'),'/87','suffix',r.get('suffix_correct'),'/44','sec',round(r['seconds'],2),flush=True)
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',default='all');p.add_argument('--max-new',type=int,default=999);p.add_argument('--workers',type=int,default=2)
    args=p.parse_args();cases,lp,sc,ch,v=setup();print('Frozen',len(cases),'inputs;',NK,'keys each',flush=True)
    todo=[x for x in cases if (args.kind=='all' or x['kind']==args.kind) and not (HERE/'results/records'/(x['id']+'.json')).exists()][:args.max_new]
    # Compilation does not inspect an unknown answer or change protocol.
    all_scores(np.arange(87,dtype=np.int64)%24,lp,ch,v,P8[:1],P3,LETTER)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=args.workers) as ex:list(ex.map(lambda c:run_one(c,lp,sc,ch,v),todo))
if __name__=='__main__':main()
