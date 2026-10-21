"""Resumeable complete runs under a hash-frozen search protocol.
Cached old finalist banks can be reused only if the old search is unchanged.
Fresh heldouts/nulls run old selection, v3 and v4 in full. No threshold stopping.
"""
import argparse,json,time,hashlib,concurrent.futures
import numpy as np
from wordscore_v3 import ROOT
from wordsearch_v4 import key_from_text
from scan_v4 import Pipeline
from scan_v3 import Pipeline as V3
from scan_v2 import scan_one
from automata import variants,canonical,transform

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--group',choices=['all','regression','heldout','real','null'],default='all');ap.add_argument('--workers',type=int,default=4);ap.add_argument('--max-new',type=int,default=0);args=ap.parse_args()
    out=ROOT/'results/v4';frozen=json.loads((out/'frozen_protocol.json').read_text())
    for f,h in frozen['sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,f
    p=Pipeline();p3=V3()
    assert p.engine.scorer.metadata['sha256']==frozen['lexicon']['sha256']
    rows=json.loads((out/'inputs.json').read_text())['cases']
    if args.group!='all':rows=[r for r in rows if r['group']==args.group]
    dest=out/'cases';dest.mkdir(exist_ok=True);banks=out/'banks';banks.mkdir(exist_ok=True)
    def work(case):
        path=dest/f"{case['id']}.json"
        if path.exists():return json.loads(path.read_text())
        t=time.monotonic();o=np.array(case['orientation'],np.int64);c=np.array(case['arcs_zero_based'],np.int64)
        b3path=banks/f"{case['id']}_v3.json"
        if 'cached_v3' in case:b3=json.loads((ROOT/case['cached_v3']).read_text())
        elif b3path.exists():b3=json.loads(b3path.read_text())
        else:
            b2path=banks/f"{case['id']}_v2.json"
            if b2path.exists():b2=json.loads(b2path.read_text())
            else:
                b2,_=scan_one(o,c,p.engine.lp,p.engine.p1);b2['id']=case['id']
                b2path.write_text(json.dumps(b2,indent=2))
            b3=p3.run(o,c,b2);b3path.write_text(json.dumps(b3,indent=2))
        r=p.run(o,c,b3,frozen['config'],tag=frozen['seed_namespace'])
        r.update(id=case['id'],group=case['group'],baseline_score=b3['best_score'],baseline_decoded=b3['decoded'],
                 baseline_identity_score=b3['identity_score'],full_seconds=time.monotonic()-t,
                 input_sha256=hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest(),
                 protocol_sha256=hashlib.sha256((out/'frozen_protocol.json').read_bytes()).hexdigest())
        if 'plaintext' in case:
            # Oracle enters here only: after final choice is irrevocably made.
            truth=np.frombuffer(case['plaintext'].encode(),np.uint8).astype(np.int64)-97
            r['accuracy']=float(np.mean(np.array(r['decoded'])==truth));r['baseline_accuracy']=float(np.mean(np.array(b3['decoded'])==truth))
            vv=variants(o,c);target=canonical(transform(o,c,case['generating_rule']))
            ti=next(j for j,(seq,_) in enumerate(vv) if np.array_equal(seq,target))
            r['true_pattern_index']=ti;r['true_pattern_won']=(ti==r['best_index'])
            for x in r['candidates']:x['accuracy_diagnostic']=float(np.mean(np.array(x['decoded'])==truth))
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(r,indent=2));tmp.replace(path)
        print(r['id'],'accuracy',r.get('accuracy','-'),'old',r.get('baseline_accuracy','-'),'score',round(r['best_score'],6),'seconds',round(r['full_seconds'],1),flush=True)
        return r
    todo=[r for r in rows if not (dest/f"{r['id']}.json").exists()]
    if args.max_new:todo=todo[:args.max_new]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:list(pool.map(work,todo))
    print('GROUP COMPLETE',args.group,len(rows),'requested',len(todo),'newly computed',flush=True)
if __name__=='__main__':main()
