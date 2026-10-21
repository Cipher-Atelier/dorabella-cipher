"""Wider multistage selection. Development is run BEFORE real/negative inputs.
Oracle metadata never enters candidate selection. All stages retain the best
score/key so far. Same fixed procedure for every input sequence.
"""
from pathlib import Path
import argparse, concurrent.futures, hashlib, json, time
import numpy as np
from audit import load_cipher
from automata import canonical, variants, transform, definitions, inverse
from language import build_model, stable_seed, documents, corpus_path, score_key
from fastsolve import solve_fast
from scan import create_positives
ROOT=Path(__file__).resolve().parent
PROTOCOL={
 'id':'wide_selection_v2','family_definitions':672,
 'screen':{'restarts':8,'iterations':16000,'keep':32},
 'middle':{'restarts':32,'iterations':20000,'keep':8},
 'final':{'restarts':128,'iterations':20000},
 'identity_always_included':True,'keep_max_across_stages':True,
 'stages_have_independent_deterministic_seeds':True,
 'seed_rule':'SHA256(canonical equality pattern + stage name), first 4 bytes little-endian',
 'development_cases':'same 8 cases as round 1, NOT independent validation',
 'new_positive_cases':'lee.cor documents 28..43, 16 disjoint documents; seed 729031',
 'null_cases':'99 full-glyph permutations, fresh seed 729032; rerun the entire pipeline on each',
 'limitations':['same two-state polarity-XOR family only','modern news language model',
   'search not globally exhaustive','all transformations leave axis and arcs unchanged',
   'historically exploratory family; this is NOT a preregistered claim about Dorabella']}

def scan_one(o,c,lp,p1):
    candidates=variants(o,c);raw=canonical(3*o+c)
    identity=next(i for i,(seq,_) in enumerate(candidates) if np.array_equal(seq,raw))
    scores=np.full(len(candidates),-1.e100);keys=[None]*len(candidates)
    snapshots=[];selected=list(range(len(candidates)))
    for stage in ('screen','middle','final'):
        conf=PROTOCOL[stage]
        for j in selected:
            seq,_=candidates[j]
            sc,key=solve_fast(seq,lp,p1,conf['restarts'],conf['iterations'],stable_seed(seq,'v2_'+stage))
            if sc>scores[j]:scores[j]=float(sc);keys[j]=key
        snapshots.append({'stage':stage,'searched_indices':selected.copy(),'all_best_scores':(scores/84).tolist()})
        if 'keep' in conf:
            # Tie break by the canonical bytes, independent of enumeration order.
            ranked=sorted(selected,key=lambda j:(-scores[j],candidates[j][0].tobytes()))
            selected=sorted(set(ranked[:conf['keep']]+[identity]))
    best=int(np.argmax(scores));seq,rule=candidates[best]
    assert abs(score_key(seq,keys[best],lp)-scores[best])<1e-7
    result={'best_score':float(scores[best]/84),'identity_score':float(scores[identity]/84),
      'improvement':float((scores[best]-scores[identity])/84),
      'distinct_patterns':len(candidates),'best_rule':rule,'best_index':best,'identity_index':identity,
      'identity_won':best==identity,'decoded':keys[best][seq].tolist(),
      'identity_decoded':keys[identity][raw].tolist(),
      'best_key':keys[best].tolist(),'stages':snapshots,
      'top_candidates':[{'index':j,'score':float(scores[j]/84),'rule':candidates[j][1],
         'decoded':keys[j][candidates[j][0]].tolist()} for j in np.argsort(scores)[-8:][::-1].tolist()]}
    return result,candidates

def new_positives(n=16):
    rng=np.random.default_rng(729031)
    train=documents(corpus_path('lee_background.cor'));test=documents(corpus_path('lee.cor'))
    rules=list(definitions());out=[]
    for i in range(n):
        text=test[28+i]
        for attempt in range(1000):
            off=int(rng.integers(0,len(text)-87+1));plain=text[off:off+87]
            a=np.frombuffer(plain.encode(),np.uint8).astype(np.int64)-97;seq=canonical(a)
            if seq.max()<24 and not any(plain in t for t in train):break
        else:raise RuntimeError('No held-out plaintext')
        z=rng.permutation(24)[seq]
        for attempt in range(1000):
            rule=rules[int(rng.integers(len(rules)))];o,c=inverse(z,rule)
            if not np.array_equal(canonical(3*o+c),seq):break
        else:raise RuntimeError('No nontrivial rule')
        assert np.array_equal(transform(o,c,rule),z)
        info={'document':28+i,'offset':off,'plaintext_sha256':hashlib.sha256(plain.encode()).hexdigest(),
              'generating_rule':rule}
        out.append((f'heldout_{i:02d}',o,c,a,info))
    return out

def make_cases(mode):
    if mode=='development':return create_positives(8,np.random.default_rng(20260928))
    if mode=='heldout':return new_positives()
    _,_,o,c=load_cipher()
    if mode=='dorabella':return [('dorabella',o,c,None,{})]
    if mode=='null':
        rng=np.random.default_rng(729032);out=[]
        for i in range(99):
            idx=rng.permutation(len(o));out.append((f'null2_{i:03d}',o[idx],c[idx],None,{}))
        return out
    raise ValueError(mode)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['development','heldout','dorabella','null']);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--max-new',type=int,default=0);args=ap.parse_args()
    pp=ROOT/'results/v2_protocol.json'
    if pp.exists():assert json.loads(pp.read_text())==PROTOCOL,'Protocol changed: use a new experiment directory'
    else:pp.write_text(json.dumps(PROTOCOL,indent=2))
    lp,p1=build_model();cases=make_cases(args.mode)
    outdir=ROOT/'results/v2';outdir.mkdir(exist_ok=True)
    manifest=[]
    for label,o,c,truth,info in cases:
        manifest.append({'id':label,'orientation':o.tolist(),'arcs_zero_based':c.tolist(),'info':info})
    (outdir/f'{args.mode}_inputs.json').write_text(json.dumps(manifest,indent=2))
    # All candidate choices take place before oracle diagnostic fields are computed.
    def work(case):
        label,o,c,truth,info=case;t=time.monotonic();r,candidates=scan_one(o,c,lp,p1)
        r.update({'id':label,'seconds':time.monotonic()-t,'source_info':info})
        if truth is not None:
            r['accuracy']=float(np.mean(np.array(r['decoded'])==truth))
            r['true_score']=float(score_key(truth,np.arange(26),lp))/84
            correct=canonical(transform(o,c,info['generating_rule']))
            j=next(j for j,(s,_) in enumerate(candidates) if np.array_equal(s,correct))
            r['true_pattern_index']=j
            r['true_pattern_stages']=[]
            for stage in r['stages']:
                scores=np.array(stage['all_best_scores'])
                r['true_pattern_stages'].append({'stage':stage['stage'],'searched':j in stage['searched_indices'],
                    'rank':int(1+np.sum(scores>scores[j]+1e-10)),'score':float(scores[j])})
        else:
            r['candidate_text']=''.join(chr(x+65) for x in r['decoded'])
        (outdir/f'{label}.json').write_text(json.dumps(r,indent=2))
        return r
    solve_fast(canonical(3*cases[0][1]+cases[0][2]),lp,p1,1,1,1)
    todo=[case for case in cases if not (outdir/f'{case[0]}.json').exists()]
    if args.max_new:todo=todo[:args.max_new]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for f in concurrent.futures.as_completed([pool.submit(work,c) for c in todo]):
            r=f.result();print(r['id'],'score',round(r['best_score'],6),'identity',round(r['identity_score'],6),
               'accuracy',r.get('accuracy','-'),'seconds',round(r['seconds'],1),flush=True)
    if all((outdir/f'{c[0]}.json').exists() for c in cases):
        rows=[json.loads((outdir/f'{c[0]}.json').read_text()) for c in cases]
        summ={'mode':args.mode,'cases':len(rows),'mean_best_score':float(np.mean([r['best_score'] for r in rows]))}
        if 'accuracy' in rows[0]:summ.update({'mean_accuracy':float(np.mean([r['accuracy'] for r in rows])),
              'at_least_90_percent':sum(r['accuracy']>=.9 for r in rows),
              'at_least_95_percent':sum(r['accuracy']>=.95 for r in rows)})
        (outdir/f'{args.mode}_summary.json').write_text(json.dumps(summ,indent=2));print(summ,flush=True)
if __name__=='__main__':main()
