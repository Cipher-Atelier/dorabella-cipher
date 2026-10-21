"""Exploratory route-search extension: every route receives word-aware search
before any shortlist. Evaluated only on2 real transcriptions and1 old failed
regression case; the previous branch's null results MUST NOT be reused for this
stronger algorithm. Local key optimization remains heuristic, not exhaustive.
"""
import json,time,hashlib,argparse
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from model_v5 import ROOT
from automata import canonical
from language import stable_seed
from fastsolve import solve_fast
from wordsearch_v4 import WordSearch
import routes_v6 as routes
OUT=ROOT/'results/v6/routes_wordall';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'id':'every-route-word-search-v6','first_character':[32,20000],
 'first_word':{'restarts':8,'iterations':6000,'final_greedy_sweeps':12},
 'middle_keep':32,'middle_character':[128,20000],'middle_word':{'restarts':32,'iterations':8000},
 'final_keep':16,'final_word':{'restarts':128,'iterations':16000},
 'routes':'unchanged1665 from routes_v6','null_calibration':False,
 'cases':['hauer_real','hart_real','positive_00'],
 'regression_status':'positive00 deliberately selected after previous route search failed; not a holdout'}

def first_task(task,eng):
    case,rid,p,name=task;directory=OUT/'first'/case['id'];directory.mkdir(parents=True,exist_ok=True)
    path=directory/(f'{rid:04d}.json')
    if path.exists():return json.loads(path.read_text())
    g=np.array(case['glyph']);seq=canonical(g[p]);_,key=solve_fast(seq,eng.lp,eng.p1,*PROTOCOL['first_character'],stable_seed(seq,'routes_wordall_first_char'))
    record=eng.run(seq,key[seq],PROTOCOL['first_word'],tag='routes_wordall_first_word');record.update(route=rid,name=name)
    path.write_text(json.dumps(record));return record

def refine_task(task,eng,stage):
    case,r,p,previous=task;directory=OUT/stage/case['id'];directory.mkdir(parents=True,exist_ok=True);path=directory/(f'{r:04d}.json')
    if path.exists():return json.loads(path.read_text())
    seq=canonical(np.array(case['glyph'])[p]);initial=np.array(previous['decoded'])
    if stage=='middle':
        _,key=solve_fast(seq,eng.lp,eng.p1,*PROTOCOL['middle_character'],stable_seed(seq,'routes_wordall_middle_char'))
        # Both starting points receive the same new budget; old best is retained.
        pool=[previous]
        for j,txt in enumerate((initial,key[seq])):pool.append(eng.run(seq,txt,PROTOCOL['middle_word'],tag='routes_wordall_middle_word'+str(j)))
        record=max(pool,key=lambda x:x['score']).copy()
    else:
        record=eng.run(seq,initial,PROTOCOL['final_word'],tag='routes_wordall_final_word')
        if record['score']<previous['score']:record=previous.copy()
    record.update(route=r);path.write_text(json.dumps(record));return record

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);a=ap.parse_args();eng=WordSearch();rr=routes.routes()
    allcases=json.loads((ROOT/'results/v6/routes/inputs.json').read_text())['cases'];cs=[x for x in allcases if x['id'] in PROTOCOL['cases']]
    f=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['routes_wordall_v6.py','routes_v6.py','wordsearch_v4.py','fastsolve.py','data/english_model.npz']},dictionary=eng.scorer.metadata)
    path=OUT/'frozen.json'
    if path.exists():assert json.loads(path.read_text())==f
    else:path.write_text(json.dumps(f,indent=2))
    (OUT/'inputs.json').write_text(json.dumps(cs,indent=2))
    for case in cs:
        dest=OUT/(case['id']+'.json')
        if dest.exists():continue
        t=time.monotonic();print('begin',case['id'],flush=True)
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            first=list(pool.map(lambda task:first_task(task,eng),[(case,i,p,n) for i,(p,n) in enumerate(rr)]))
        print('first complete',case['id'],max(x['score'] for x in first),flush=True)
        ids=sorted(set(sorted(range(len(first)),key=lambda i:(-first[i]['score'],i))[:PROTOCOL['middle_keep']]+[0]))
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            middle=list(pool.map(lambda task:refine_task(task,eng,'middle'),[(case,i,rr[i][0],first[i]) for i in ids]))
        ranked=sorted(middle,key=lambda x:(-x['score'],x['route']));chosen=ranked[:PROTOCOL['final_keep']]
        if not any(x['route']==0 for x in chosen):chosen.append(next(x for x in ranked if x['route']==0))
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            final=list(pool.map(lambda task:refine_task(task,eng,'final'),[(case,x['route'],rr[x['route']][0],x) for x in chosen]))
        final.sort(key=lambda x:(-x['score'],x['route']));b=final[0]
        rec=dict(id=case['id'],kind=case['kind'],best_score=b['score'],best_text=''.join(chr(v+97) for v in b['decoded']),
                 first_count=len(first),first_top_routes=ids,finalists=final,seconds=time.monotonic()-t)
        if case['kind']=='positive':
            rec['accuracy']=sum(a==b for a,b in zip(rec['best_text'],case['plaintext']))/87
            true=case['generating_route'];rec['true_route_first_rank']=1+sum(x['score']>first[true]['score']+1e-10 for x in first)
        dest.write_text(json.dumps(rec,indent=2));print('done',case['id'],rec['best_score'],rec.get('accuracy',''),rec['best_text'],rec['seconds'],flush=True)
if __name__=='__main__':main()
