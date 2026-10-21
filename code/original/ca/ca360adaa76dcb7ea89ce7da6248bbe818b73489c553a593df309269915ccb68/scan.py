"""Equal-procedure scan of 672 two-state definitions and shuffled controls.
Every negative control repeats the complete family search and refinement.
"""
from pathlib import Path
import argparse, concurrent.futures, hashlib, json, time
import numpy as np
from audit import load_cipher
from automata import canonical, variants, definitions, inverse, transform
from language import build_model, solve, stable_seed, documents, corpus_path, score_key
ROOT=Path(__file__).resolve().parent
PROTOCOL={'definitions':672,'states':2,'inputs':['cipher polarity','arc count','axis'],
          'output':'same axis and arc count, polarity XOR current state',
          'state_initial_values':[0,1], 'read_order':'left to right, no line/dot resets',
          'screen_restarts':2,'screen_iterations':4000,'shortlist_size':3,
          'refine_restarts':128,'refine_iterations':20000,
          'identity_always_refined':True,'canonicalize_symbol_names':True,
          'deduplicate_equivalent_equality_patterns_per_input':True,
          'seed':'SHA256(canonical cipher bytes + stage label), first 32 bits little-endian',
          'primary_statistic':'maximum score over all screened/refined candidates',
          'secondary_statistic':'maximum score minus identity score',
          'negative_reference':'permute complete input glyphs, preserve their exact frequencies',
          'selection_correction':'repeat entire family search, ranking and refinement on every control',
          'limitations':['Not an exhaustive search over all finite-state ciphers.',
                         'The definitions were selected using prior exploratory analysis of Dorabella.',
                         'All transformations preserve the entire axis/arc sequence.',
                         'Modern English news model, not Elgar-era personal correspondence.',
                         'Heuristic search, not a proof of a global optimum.']}

def scan_one(o,c,logp,p1):
    cand=variants(o,c);raw=canonical(3*o+c)
    identity=next(i for i,(s,_) in enumerate(cand) if np.array_equal(s,raw))
    scores=[];keys=[]
    for seq,rule in cand:
        sc,key=solve(seq,logp,p1,PROTOCOL['screen_restarts'],PROTOCOL['screen_iterations'],stable_seed(seq,'screen_v1'))
        scores.append(float(sc));keys.append(key)
    selected=sorted(set(np.argsort(scores)[-PROTOCOL['shortlist_size']:].tolist()+[identity]))
    for j in selected:
        seq,_=cand[j]
        sc,key=solve(seq,logp,p1,PROTOCOL['refine_restarts'],PROTOCOL['refine_iterations'],stable_seed(seq,'refine_v1'))
        if sc>scores[j]:scores[j]=float(sc);keys[j]=key
    best=int(np.argmax(scores));seq,rule=cand[best];norm=len(o)-3
    assert abs(score_key(seq,keys[best],logp)-scores[best])<1.e-7
    return {'best_score':scores[best]/norm,'identity_score':scores[identity]/norm,
            'improvement':(scores[best]-scores[identity])/norm,'distinct_patterns':len(cand),
            'best_rule':rule,'decoded':keys[best][seq].tolist(),
            'top_candidates':[{'score':scores[j]/norm,'rule':cand[j][1]} for j in np.argsort(scores)[-6:][::-1]],
            'identity_won':best==identity}

def create_positives(n,rng):
    train=documents(corpus_path('lee_background.cor'));test=documents(corpus_path('lee.cor'))
    allrules=list(definitions());out=[]
    for i in range(n):
        text=test[20+i]
        for attempt in range(100):
            off=int(rng.integers(0,len(text)-87));plain=text[off:off+87]
            a=np.frombuffer(plain.encode(),dtype=np.uint8).astype(np.int64)-97;seq=canonical(a)
            if seq.max()<24 and not any(plain in t for t in train):break
        else:raise RuntimeError('No valid held-out sample')
        z=rng.permutation(24)[seq]
        for attempt in range(1000):
            rule=allrules[int(rng.integers(len(allrules)))];o,c=inverse(z,rule)
            if not np.array_equal(canonical(3*o+c),seq):break
        else:raise RuntimeError('No nontrivial state machine')
        assert np.array_equal(transform(o,c,rule),z)
        info={'document':20+i,'offset':off,'plaintext_sha256':hashlib.sha256(plain.encode()).hexdigest(),
              'generating_rule':rule}
        out.append((f'positive_{i:02d}',o,c,a,info))
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--controls',type=int,default=99)
    ap.add_argument('--positives',type=int,default=8);ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--max-new',type=int,default=0,help='Optional resumable batch size; 0 means all remaining cases')
    args=ap.parse_args();logp,p1=build_model();_,_,o,c=load_cipher()
    PROTOCOL['negative_controls']=args.controls;PROTOCOL['end_to_end_positives']=args.positives
    protocol_path=ROOT/'results/scan_protocol.json'
    if protocol_path.exists():assert json.loads(protocol_path.read_text())==PROTOCOL,'Protocol mismatch'
    else:protocol_path.write_text(json.dumps(PROTOCOL,indent=2))
    cases=create_positives(args.positives,np.random.default_rng(20260928))
    cases.append(('dorabella',o,c,None,{}));rng=np.random.default_rng(20260929)
    for i in range(args.controls):
        idx=rng.permutation(len(o));cases.append((f'shuffle_{i:03d}',o[idx],c[idx],None,{}))
    path=ROOT/'results/scan_records.jsonl';done={}
    if path.exists():
        for line in path.read_text().splitlines():
            row=json.loads(line);done[row['id']]=row
    def work(case):
        label,oi,ci,truth,info=case;t=time.monotonic();r=scan_one(oi,ci,logp,p1)
        decoded=np.array(r.pop('decoded'),int)
        r.update({'id':label,'seconds':time.monotonic()-t,'source_info':info})
        if truth is not None:
            r['decipherment_accuracy']=float(np.mean(decoded==truth))
            r['true_plaintext_score']=float(score_key(truth,np.arange(26),logp))/84
        if label=='dorabella':r['candidate_text']=''.join(chr(v+65) for v in decoded)
        return r
    dummy=canonical(3*o+c);solve(dummy,logp,p1,1,1,123)
    todo=[case for case in cases if case[0] not in done]
    if args.max_new:todo=todo[:args.max_new]
    start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(work,case) for case in todo]
        for f in concurrent.futures.as_completed(futures):
            r=f.result();done[r['id']]=r
            with path.open('a') as fp:fp.write(json.dumps(r)+'\n')
            print(r['id'],'max',round(r['best_score'],5),'identity',round(r['identity_score'],5),
                  'accuracy',r.get('decipherment_accuracy','-'),'time',round(r['seconds'],1),flush=True)
    missing=[case[0] for case in cases if case[0] not in done]
    if missing:
        print('CHECKPOINT:',len(done),'completed;',len(missing),'remaining. Batch seconds:',time.monotonic()-start,flush=True)
        return
    obs=done['dorabella'];null=[done[f'shuffle_{i:03d}'] for i in range(args.controls)]
    ps=[done[f'positive_{i:02d}'] for i in range(args.positives)]
    summ={'protocol':PROTOCOL,'observed':obs,'negative_comparison':{},
          'end_to_end_positive_accuracy_mean':float(np.mean([r['decipherment_accuracy'] for r in ps])),
          'end_to_end_positives_above_90_percent':sum(r['decipherment_accuracy']>=.9 for r in ps),
          'positive_cases':ps}
    for metric in ['best_score','improvement','identity_score']:
        vals=np.array([r[metric] for r in null]);hit=int(np.sum(vals>=obs[metric]-1.e-12))
        summ['negative_comparison'][metric]={'observed':obs[metric],'null_mean':float(vals.mean()),
             'null_sd':float(vals.std(ddof=1)),'exceedances':hit,'controls':len(vals),
             'p_plus_one':(hit+1)/(len(vals)+1),'null_min':float(vals.min()),'null_max':float(vals.max())}
    (ROOT/'results/scan_summary.json').write_text(json.dumps(summ,indent=2))
    print('SUMMARY',json.dumps(summ['negative_comparison']),flush=True)
    print('POSITIVE ACCURACY',summ['end_to_end_positive_accuracy_mean'],summ['end_to_end_positives_above_90_percent'],flush=True)
if __name__=='__main__':main()
