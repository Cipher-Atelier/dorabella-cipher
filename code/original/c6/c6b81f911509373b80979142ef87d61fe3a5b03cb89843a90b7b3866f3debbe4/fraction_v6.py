"""Fixed-table coordinate fractionation. Exploratory, not an exhaustive cipher claim.
Square 5x5: every choice of missing cell and geometric layouts of 24 symbols.
Cube 3x3x3: 8 compass neighbours of each layer centre, three arc-count layers;
all coordinate permutations. Fixed alphabet output, no arbitrary keyed square/cube.
Periods 1..87; forward/inverse coordinate mixing; reverse whole input or not;
reset blocks at printed rows or concatenate. Equivalent maps/routes deduplicated.
Cube extra symbol is a space; scoring ignores these generated spaces (explicit limitation).
"""
import itertools,json,time,hashlib,argparse
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from numba import njit
from model_v5 import ROOT
from language import build_model
from wordsearch_v4 import WordSearch
from wordpolish_v3 import char_score,fast_word
OUT=ROOT/'results/v6/fraction';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'family':'fixed-table-coordinate-fractionation-v6','periods':[1,87],
 'geometric_orientation':'sign +/-1 and all8 rotations','arc_orders':'all6','square':'5x5, every omitted cell, 2 layouts',
 'cube':'3x3x3, three arc layers of8 compass neighbours, all6 coordinate permutations',
 'digit_routes':'both directions, whole input reversal, reset by printed row or not',
 'square_alphabet':'abcdefghiklmnopqrstuvwxyz','cube_alphabet':'abcdefghijklmnopqrstuvwxyz ',
 'scoring':'unmerged26 C+0.5W; cube spaces stripped ONLY for scoring, preserved in result',
 'arbitrary_key':False,'null_calibration':False,'sensitivity_benchmark':False,'status':'exploratory exact bounded search'}

def tables(kind):
    bank={};count=0
    for sign,rot,arcs in itertools.product((1,-1),range(8),itertools.permutations(range(3))):
        o=(sign*np.arange(24)//3) # overwritten explicitly to avoid precedence ambiguity
        oo=(sign*(np.arange(24)//3)+rot)%8;cc=np.array(arcs)[np.arange(24)%3]
        if kind=='square':
            for layout,missing in itertools.product(range(2),range(25)):
                x=3*oo+cc if layout==0 else 8*cc+oo
                x=x+(x>=missing)
                coords=np.column_stack((x//5,x%5)).astype(np.int64)
                name=dict(sign=sign,rot=rot,arcs=arcs,layout=layout,missing=missing)
                count+=1
                if coords.tobytes() not in bank:bank[coords.tobytes()]=(coords,name)
        else:
            # A opens east, B southeast, C south, etc.
            ring=np.array([[1,2],[2,2],[2,1],[2,0],[1,0],[0,0],[0,1],[0,2]])
            coords0=np.column_stack((cc,ring[oo,0],ring[oo,1]))
            for order in itertools.permutations(range(3)):
                coords=coords0[:,order].astype(np.int64)
                name=dict(sign=sign,rot=rot,arcs=arcs,coordinate_order=order)
                count+=1
                if coords.tobytes() not in bank:bank[coords.tobytes()]=(coords,name)
    return list(bank.values()),count

def digit_routes(dim):
    bank={};count=0
    for period,reset in itertools.product(range(1,88),range(2)):
        bounds=[0,29,60,87] if reset else [0,87]
        p=np.arange(87*dim)
        for lo,hi in zip(bounds[:-1],bounds[1:]):
            for first in range(lo,hi,period):
                m=min(period,hi-first)
                for i in range(m):
                    for j in range(dim):p[(first+i)*dim+j]=first*dim+j*m+i
        for inverse,rev in itertools.product(range(2),range(2)):
            q=np.argsort(p) if inverse else p.copy()
            if rev:q=(86-q//dim)*dim+q%dim
            count+=1;assert np.array_equal(np.sort(q),np.arange(dim*87))
            if q.tobytes() not in bank:bank[q.tobytes()]=(q,dict(period=period,reset=reset,inverse=inverse,reverse=rev))
    return list(bank.values()),count

@njit(cache=True)
def output_numeric(glyph,table,route,base):
    dim=table.shape[1];digit=np.empty(87*dim,np.int64)
    for i in range(87):
        for j in range(dim):digit[i*dim+j]=table[glyph[i],j]
    out=np.empty(87,np.int64)
    for i in range(87):
        v=0
        for j in range(dim):v=v*base+digit[route[i*dim+j]]
        out[i]=v
    return out

@njit(cache=True,nogil=True)
def evaluate(glyph,tablearray,routearray,base,alphabet,lp,children,vals):
    scores=np.empty((len(tablearray),len(routearray)),np.float64)
    for i in range(len(tablearray)):
        for j in range(len(routearray)):
            out=output_numeric(glyph,tablearray[i],routearray[j],base);text=np.empty(87,np.int64);n=0
            for k in range(87):
                a=alphabet[out[k]]
                if a>=0:text[n]=a;n+=1
            if n<4:scores[i,j]=-1e100
            else:scores[i,j]=char_score(text[:n],lp)+.5*fast_word(text[:n],children,vals)
    return scores

def run(kind,z,model,engine):
    path=OUT/(kind+'_'+z['id']+'.json')
    if path.exists():return json.loads(path.read_text())
    start=time.monotonic();tt,td=tables(kind);dim=2 if kind=='square' else 3;rr,rd=digit_routes(dim)
    tarray=np.stack([t[0] for t in tt]);rarray=np.stack([r[0] for r in rr]);base=5 if dim==2 else 3
    astr=PROTOCOL[kind+'_alphabet'];alphabet=np.array([ord(c)-97 if c!=' ' else -1 for c in astr],np.int64)
    glyph=3*np.array(z['orientation'])+z['arcs']
    scores=evaluate(glyph,tarray,rarray,base,alphabet,model[0],engine.children,engine.vals)
    flat=scores.ravel();ids=np.argpartition(flat,-32)[-32:];ids=sorted(ids,key=lambda j:(-float(flat[j]),int(j)));top=[];seen=set()
    for idx in ids:
        i,j=np.unravel_index(idx,scores.shape);out=output_numeric(glyph,tarray[i],rarray[j],base)
        text=''.join(astr[v] for v in out)
        if text in seen:continue
        seen.add(text);stripped=text.replace(' ','');ws,seg=engine.scorer.score(stripped,True)
        top.append(dict(score=float(scores[i,j]),text=text,table_index=int(i),route_index=int(j),table=tt[i][1],route=rr[j][1],segmentation=seg,scored_length=len(stripped)))
    record=dict(kind=kind,id=z['id'],best_score=top[0]['score'],best_text=top[0]['text'],top=top,
        n_table_definitions=td,n_unique_tables=len(tt),n_route_definitions=rd,n_unique_routes=len(rr),
        n_evaluations=int(scores.size),score_sha256=hashlib.sha256(scores.tobytes()).hexdigest(),seconds=time.monotonic()-start)
    path.write_text(json.dumps(record,indent=2));print(kind,z['id'],record['best_score'],record['best_text'],record['n_evaluations'],record['seconds'],flush=True)
    return record

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    z=[c for c in json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'] if c['kind']=='real'];engine=WordSearch();model=build_model()
    frozen=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['fraction_v6.py','data/english_model.npz','wordpolish_v3.py','wordscore_v3.py']},dictionary=engine.scorer.metadata)
    p=OUT/'frozen.json'
    if p.exists():assert json.loads(p.read_text())==frozen
    else:p.write_text(json.dumps(frozen,indent=2))
    (OUT/'inputs.json').write_text(json.dumps(z,indent=2))
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(lambda kv:run(*kv,model,engine),[(kind,c) for kind in ('square','cube') for c in z]))
if __name__=='__main__':main()
