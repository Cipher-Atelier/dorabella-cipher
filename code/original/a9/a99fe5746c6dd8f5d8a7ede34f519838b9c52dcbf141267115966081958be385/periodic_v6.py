"""Exact dictionary-key periodic mod24 attacks with fixed alphabet.
Every keyword supplies a periodic shift sequence; includes Vigenere/Beaufort signs,
all24 global offsets, two geometric linearizations and both whole reading directions.
No arbitrary post-substitution; no null/sign edits. Exploratory, no shuffle calibration.
"""
import json,hashlib,time,argparse
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from model_v5 import ROOT,ALPHABET,LETTER,normalise,load_model
from wordpolish_v3 import char_score,fast_word
OUT=ROOT/'results/v6/periodic';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'id':'dictionary-periodic-mod24-v6','layouts':['3*orientation+arcs','8*arcs+orientation'],
 'reading':['forward','reverse'],'cipher_sign':[1,-1],'key_sign':[1,-1],'global_offsets':24,
 'formula':'p[t]=(a*x[t]+b*key[t mod len(key)]+h) mod24',
 'dictionary':'same external merged24 word list, all words <=32 chars',
 'explicit_context_key_hypotheses':['DORA','DORABELLA','ELGAR','EDWARD','PENNY','ALICE','ENIGMA','FORLI','MALVERN','FORLIMALVERN','DORAPENNY','EDWARDELGAR'],
 'plaintext_scoring':'unchanged merged24 C+0.5W; these additional keys are NOT added to scorer',
 'key_phase':0,'row_reset':False,'arbitrary_substitution':False,'null_calibration':False,
 'sensitivity':'6 old texts, new random dictionary key and signs','positive_seed':20260926071}

def keywords(model):
    words=set(w for w in model[1].words if 1<=len(w)<=32)
    words.update(normalise(w) for w in PROTOCOL['explicit_context_key_hypotheses'])
    unique={}
    for w in sorted(words):
        s=np.array([ALPHABET.index(c.upper()) for c in w],np.int64);expanded=s[np.arange(87)%len(s)]
        if expanded.tobytes() not in unique:unique[expanded.tobytes()]=(w,expanded)
    return list(unique.values()),len(words)

@njit(cache=True,nogil=True)
def evaluate(x,keys,a,b,lp,children,vals):
    scores=np.empty((len(keys),24),np.float64)
    text=np.empty(87,np.int64)
    for i in range(len(keys)):
        for h in range(24):
            for t in range(87):text[t]=LETTER[(a*x[t]+b*keys[i,t]+h)%24]
            scores[i,h]=char_score(text,lp)+.5*fast_word(text,children,vals)
    return scores

def make_cases(kk):
    old=json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'];cs=[]
    for x in old:
        if x['kind']=='real':cs.append(dict(id=x['id'],kind='real',orientation=x['orientation'],arcs=x['arcs']))
    rng=np.random.default_rng(PROTOCOL['positive_seed'])
    for j,x in enumerate([x for x in old if x['kind']=='positive'][16:22]):
        p=np.array([ALPHABET.index(c.upper()) for c in x['plaintext']]);layout=j%2;reverse=(j//2)%2;a=(-1)**j;b=(-1)**(j//2);h=int(rng.integers(24));ki=int(rng.integers(len(kk)))
        z=(a*(p-b*kk[ki][1]-h))%24
        if reverse:z=z[::-1]
        o,c=(z//3,z%3) if layout==0 else (z%8,z//8)
        cs.append(dict(id=f'positive_{j:02d}',kind='positive',orientation=o.tolist(),arcs=c.tolist(),plaintext=x['plaintext'],source=x['id'],generating=dict(layout=layout,reverse=reverse,a=a,b=b,h=h,keyword=kk[ki][0])))
    data=dict(protocol=PROTOCOL,cases=cs,keywords=[w for w,_ in kk]);p=OUT/'inputs.json'
    if p.exists():assert json.loads(p.read_text())==data
    else:p.write_text(json.dumps(data,indent=2))
    return cs

def run(z,kk,model):
    path=OUT/(z['id']+'.json')
    if path.exists():return json.loads(path.read_text())
    start=time.monotonic();o=np.array(z['orientation']);c=np.array(z['arcs']);keys=np.stack([k for _,k in kk]);pool=[];groups=[]
    for layout in range(2):
        raw=3*o+c if layout==0 else 8*c+o
        for reverse in range(2):
            x=raw[::-1].copy() if reverse else raw.copy()
            for a in (1,-1):
                for b in (1,-1):
                    scores=evaluate(x,keys,a,b,model[0],model[2],model[3]);f=scores.ravel();ids=np.argpartition(f,-8)[-8:]
                    groups.append(dict(layout=layout,reverse=reverse,a=a,b=b,best=float(f.max()),sha256=hashlib.sha256(scores.tobytes()).hexdigest()))
                    for idx in ids:
                        ki,h=np.unravel_index(idx,scores.shape);p=(a*x+b*keys[ki]+h)%24;text=''.join(ALPHABET[v].lower() for v in p)
                        pool.append(dict(score=float(scores[ki,h]),text=text,keyword=kk[ki][0],key_index=int(ki),layout=layout,reverse=reverse,a=a,b=b,h=int(h)))
    pool.sort(key=lambda r:(-r['score'],r['text']));seen=set();top=[]
    for r in pool:
        if r['text'] in seen:continue
        seen.add(r['text']);_,seg=model[1].score(r['text'],True);r['segmentation']=seg;top.append(r)
        if len(top)==32:break
    rec=dict(id=z['id'],kind=z['kind'],best_score=top[0]['score'],best_text=top[0]['text'],top=top,groups=groups,n_evaluations=len(kk)*24*16,seconds=time.monotonic()-start)
    if z['kind']=='positive':rec['accuracy']=sum(a==b for a,b in zip(z['plaintext'],rec['best_text']))/87
    path.write_text(json.dumps(rec,indent=2));print(z['id'],rec['best_score'],rec.get('accuracy',''),rec['best_text'],rec['n_evaluations'],rec['seconds'],flush=True);return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['real','positive','all'],default='all');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args();model=load_model();kk,nraw=keywords(model);cs=make_cases(kk)
    f=dict(protocol=PROTOCOL,n_original_keywords=nraw,n_distinct_expanded_keys=len(kk),hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['periodic_v6.py','data/english_merged24_v5.npz','model_v5.py','results/v6/periodic/inputs.json']},dictionary=model[1].metadata)
    path=OUT/'frozen.json'
    if path.exists():assert json.loads(path.read_text())==f
    else:path.write_text(json.dumps(f,indent=2))
    todo=[c for c in cs if (a.mode=='all' or a.mode==c['kind']) and not (OUT/(c['id']+'.json')).exists()]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(lambda c:run(c,kk,model),todo))
if __name__=='__main__':main()
