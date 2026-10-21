"""Exact maximum in a bounded keyword-generated substitution-table family.
The language criterion is unchanged. A candidate can be safely rejected when
its C score is below the current best C+0.5W, because W<=0. This only prunes
score computation; it does not claim all cryptographic keys were enumerated.
Two real transcriptions only, no shuffle test and no independent benchmark.
"""
import json,time,hashlib,itertools
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from model_v5 import ROOT,ALPHABET,LETTER,normalise,load_model
from wordpolish_v3 import char_score,fast_word
OUT=ROOT/'results/v6/keyword_tables';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'id':'keyword-generated-tables-v6','alphabet':'24 I/J U/V merged',
 'key':'unique letters of keyword then unused alphabet letters in order; also inverse permutation',
 'keywords':'all model dictionary words plus explicit context words and name phrases',
 'extra_keywords':['DORA','DORABELLA','EDWARDELGAR','EDWARDWILLIAMELGAR','FORLIMALVERN','DORAPENNY','ALICEELGAR','ENIGMA'],
 'glyph_layouts':'sign+/- and8orientation rotations and6arc orders and2linearizations',
 'reading':['forward','reverse'],'no_plaintext_crib':True,'null_calibration':False,
 'max_score_pruning':'only skip W if C<=best; W is non-positive; same exact maximum'}

def key_tables(model):
    words=set(model[1].words);words.update(normalise(w) for w in PROTOCOL['extra_keywords']);bank={}
    for word in sorted(words):
        order=[]
        for c in (word+ALPHABET.lower()):
            v=ALPHABET.index(c.upper())
            if v not in order:order.append(v)
        pp=np.array(order,np.int64)
        for inverse in range(2):
            p=np.argsort(pp) if inverse else pp
            if p.tobytes() not in bank:bank[p.tobytes()]=(p,dict(keyword=word,inverse=inverse))
    return list(bank.values()),2*len(words)

def glyph_tables():
    bank={}
    for sign,rot,arcs,layout in itertools.product((1,-1),range(8),itertools.permutations(range(3)),range(2)):
        o=(sign*(np.arange(24)//3)+rot)%8;c=np.array(arcs)[np.arange(24)%3];p=3*o+c if layout==0 else 8*c+o
        if p.tobytes() not in bank:bank[p.tobytes()]=(p,dict(sign=sign,rot=rot,arcs=arcs,layout=layout))
    return list(bank.values())

@njit(cache=True,nogil=True)
def scan(glyph,tables,geometries,lp,children,vals):
    best=-1e100;win=np.zeros(3,np.int64);full=0;visited=0;txt=np.empty(87,np.int64)
    for j in range(len(geometries)):
        x=geometries[j,glyph]
        for i in range(len(tables)):
            for reverse in range(2):
                for t in range(87):txt[t]=LETTER[tables[i,x[86-t if reverse else t]]]
                cs=char_score(txt,lp);visited+=1
                if cs<=best:continue
                ws=fast_word(txt,children,vals);full+=1
                if ws>1e-12:raise ValueError('Unsafe word bound')
                ss=cs+.5*ws
                if ss>best:best=ss;win[0]=i;win[1]=j;win[2]=reverse
    return best,win,visited,full

def run(c,model,tt,gg):
    path=OUT/(c['id']+'.json')
    if path.exists():return
    t=time.monotonic();g=3*np.array(c['orientation'])+c['arcs'];ta=np.stack([p for p,_ in tt]);ga=np.stack([p for p,_ in gg])
    ss,w,v,f=scan(g,ta,ga,model[0],model[2],model[3]);i,j,reverse=map(int,w);x=ga[j,g]
    if reverse:x=x[::-1]
    out=ta[i,x];text=''.join(ALPHABET[k].lower() for k in out);_,seg=model[1].score(text,True)
    rec=dict(id=c['id'],best_score=float(ss),best_text=text,key_index=i,geometry_index=j,reverse=reverse,key=tt[i][1],geometry=gg[j][1],table=ta[i].tolist(),glyph_table=ga[j].tolist(),segmentation=seg,definitions_char_scored=int(v),definitions_fully_scored=int(f),seconds=time.monotonic()-t)
    path.write_text(json.dumps(rec,indent=2));print(c['id'],ss,text,v,f,rec['seconds'],flush=True)

def main():
    model=load_model();tt,n=key_tables(model);gg=glyph_tables();cs=[c for c in json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'] if c['kind']=='real']
    f=dict(protocol=PROTOCOL,original_keyword_table_definitions=n,unique_tables=len(tt),unique_geometries=len(gg),hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['keyword_tables_v6.py','model_v5.py','wordpolish_v3.py','data/english_merged24_v5.npz']},dictionary=model[1].metadata)
    path=OUT/'frozen.json'
    if path.exists():assert json.loads(path.read_text())==f
    else:path.write_text(json.dumps(f,indent=2))
    (OUT/'inputs.json').write_text(json.dumps(cs,indent=2))
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda c:run(c,model,tt,gg),cs))
if __name__=='__main__':main()
