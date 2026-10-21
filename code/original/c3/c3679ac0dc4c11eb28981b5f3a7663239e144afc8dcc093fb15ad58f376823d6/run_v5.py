"""Freeze and run affine orientation test on two transcriptions and matched nulls.
Past historical plaintexts are reused as a sensitivity check, not new holdout data.
"""
from pathlib import Path
import argparse, json, time, hashlib, platform
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from model_v5 import ROOT,OUT,ALPHABET,LETTER,normalise,sha,load_model
from affine_v5 import rules,encode,decode,evaluate,rule_dict
from audit import load_cipher,tail
from wordpolish_v3 import char_score,fast_word
HART_ROWS=['BPECAHTCKYFRQDRIRRHPPRDXYXGFS','TRTHTCKLCERREHGQTRFRHUSQDXKKXFS','ESHUSEDUWGSERHUQSDCPGSHCDXC']
PROTOCOL=dict(n_null=99,n_positive=32,seed_null=2026092605,seed_positive=2026092615,
    n_rules=32768,alphabet=ALPHABET,score='merged C + 0.5 merged W; no learned substitution',
    rows='concatenated; no dot/line resets',transcriptions=['Hauer SMP2021 Fig2','Hartmeier literal transcription'],
    positive_status='32 already-used historical excerpts; all re-encrypted; sensitivity only',
    comparison='same permutation for both transcriptions; individual and max-across-two null maxima')
SOURCES={
 'hauer':'https://aclanthology.org/2021.smp-1.5.pdf',
 'hartmeier':'https://www.benzedrine.ch/dorabella.html',
 'notebook_facsimile':'https://ericsams.org/images/ciphertable3.jpg',
 'notebook_context':'https://ericsams.org/index.php/on-music/essays/on-elgar/111-elgar-s-cipher-table'}

def create_inputs():
    tok,rows,o,c=load_cipher();hart=np.array([ALPHABET.index(x) for x in ''.join(HART_ROWS)])
    assert len(hart)==87
    data=[dict(id='hauer_real',kind='real',transcription='hauer',orientation=o.tolist(),arcs=c.tolist()),
          dict(id='hart_real',kind='real',transcription='hart',orientation=(hart//3).tolist(),arcs=(hart%3).tolist())]
    rng=np.random.default_rng(PROTOCOL['seed_null'])
    for i in range(PROTOCOL['n_null']):
        perm=rng.permutation(87)
        for name,oo,cc in [('hauer',o,c),('hart',hart//3,hart%3)]:
            data.append(dict(id=f'{name}_null_{i:03d}',kind='null',transcription=name,permutation_id=i,
                             permutation=perm.tolist(),orientation=oo[perm].tolist(),arcs=cc[perm].tolist()))
    past=json.loads((ROOT/'results/v4/inputs.json').read_text())['cases'];rs=rules()
    rng=np.random.default_rng(PROTOCOL['seed_positive'])
    for x in past:
        if 'plaintext' not in x:continue
        plain=normalise(x['plaintext']);z=np.array([ALPHABET.index(ch.upper()) for ch in plain])
        for _ in range(1000):
            rule=rs[int(rng.integers(len(rs)))];enc=encode(z,rule)
            # Require genuinely history-dependent rule, not b=0, and a changed axis.
            if rule[2]!=0 and np.any((enc//3)%4!=(z//3)%4):break
        else:raise RuntimeError('No nontrivial rule')
        assert np.array_equal(decode(enc//3,enc%3,rule),z)
        data.append(dict(id='positive_'+x['id'],kind='positive',orientation=(enc//3).tolist(),arcs=(enc%3).tolist(),
             plaintext=plain,original_plaintext=x['plaintext'],generating_rule=rule.tolist()))
    assert sum(x['kind']=='positive' for x in data)==32
    target=OUT/'inputs.json';blob=dict(protocol=PROTOCOL,sources=SOURCES,hart_rows=HART_ROWS,cases=data)
    if target.exists():assert json.loads(target.read_text())==blob
    else:target.write_text(json.dumps(blob,indent=2))
    return data

def freeze(lp,scorer):
    paths=['model_v5.py','affine_v5.py','run_v5.py','data/english_merged24_v5.npz','data/dorabella_smp2021.txt','results/v5/inputs.json',
           'wordscore_v3.py','wordpolish_v3.py','language.py']
    record=dict(protocol=PROTOCOL,hashes={p:sha(ROOT/p) for p in paths},lexicon=scorer.metadata,
                note='Frozen before this affine search; all Dorabella work remains exploratory. Historical plaintexts already known.')
    target=OUT/'frozen_protocol.json'
    if target.exists():assert json.loads(target.read_text())==record
    else:target.write_text(json.dumps(record,indent=2))

def run_case(x,model):
    target=OUT/'records'/f"{x['id']}.json"
    if target.exists():return json.loads(target.read_text())
    lp,scorer,children,vals=model;rs=rules();o=np.array(x['orientation']);c=np.array(x['arcs']);t=time.monotonic()
    scores=evaluate(o,c,rs,lp,children,vals)
    # Score all 32768. Keep best distinct plaintexts, not aliases of the same output.
    order=np.argsort(-scores,kind='stable');candidates=[];seen=set()
    for i in order:
        z=decode(o,c,rs[i]);text=LETTER[z];s=''.join(chr(int(v)+97) for v in text)
        if s in seen:continue
        seen.add(s);ws,seg=scorer.score(s,True);cs=char_score(text,lp)
        assert abs(scores[i]-cs-.5*ws)<1e-9
        assert np.array_equal(encode(z,rs[i]),3*o+c)
        candidates.append(dict(rule_index=int(i),rule=rule_dict(rs[i]),score=float(scores[i]),plaintext=s,
                               char_score=float(cs),word_score=float(ws),segmentation=seg))
        if len(candidates)==8:break
    best=candidates[0];static=[]
    for a in (1,3,5,7):
        for h in range(8):
            r=np.array([0,a,0,0,h,0]);txt=LETTER[decode(o,c,r)]
            static.append(float(char_score(txt,lp)+.5*fast_word(txt,children,vals)))
    raw=LETTER[3*o+c];rawscore=float(char_score(raw,lp)+.5*fast_word(raw,children,vals))
    record=dict(id=x['id'],kind=x['kind'],best_score=best['score'],best_text=best['plaintext'],
                top_candidates=candidates,best_static_score=max(static),raw_notebook_score=rawscore,
                improvement=best['score']-max(static),rules_evaluated=len(rs),seconds=time.monotonic()-t)
    if 'transcription' in x:record['transcription']=x['transcription']
    if 'permutation_id' in x:record['permutation_id']=x['permutation_id']
    if x['kind']=='positive':
        truth=x['plaintext'];trutharr=np.array([ord(c)-97 for c in truth]);gr=np.array(x['generating_rule'])
        true_idx=next(i for i,r in enumerate(rs) if np.array_equal(r,gr))
        record.update(accuracy=sum(a==b for a,b in zip(truth,best['plaintext']))/87,
            truth_score=float(char_score(trutharr,lp)+.5*fast_word(trutharr,children,vals)),
            exact_recovery=truth==best['plaintext'],generating_rule_rank=1+int(np.sum(scores>scores[true_idx]+1e-10)))
    if x['kind']=='real':np.savez_compressed(OUT/f"{x['id']}_all_scores.npz",scores=scores,rules=rs)
    target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(record,indent=2))
    print(x['id'],round(best['score'],4),record.get('accuracy',''),round(record['seconds'],2),flush=True)
    return record

def summary(cases):
    records=[json.loads((OUT/'records'/f"{x['id']}.json").read_text()) for x in cases]
    r={x['id']:x for x in records};out=dict(protocol=PROTOCOL,n_completed=len(records),comparisons={})
    for name in ('hauer','hart'):
        real=r[name+'_real'];null=[r[f'{name}_null_{i:03d}'] for i in range(PROTOCOL['n_null'])]
        out['comparisons'][name]=dict(real={k:real[k] for k in ('best_score','best_static_score','improvement','raw_notebook_score')},
             best=tail(np.array([x['best_score'] for x in null]),real['best_score']),
             gain=tail(np.array([x['improvement'] for x in null]),real['improvement']))
    bothreal=max(r['hauer_real']['best_score'],r['hart_real']['best_score'])
    both=np.array([max(r[f'hauer_null_{i:03d}']['best_score'],r[f'hart_null_{i:03d}']['best_score']) for i in range(PROTOCOL['n_null'])])
    out['max_over_both_transcriptions']=tail(both,bothreal)
    pos=[x for x in records if x['kind']=='positive'];acc=np.array([x['accuracy'] for x in pos])
    out['sensitivity']=dict(n=len(acc),mean_accuracy=float(acc.mean()),minimum_accuracy=float(acc.min()),
              exact=sum(x['exact_recovery'] for x in pos),at_least90=int(np.sum(acc>=.9)),
              correct_rules_top_tied=sum(x['generating_rule_rank']==1 for x in pos))
    (OUT/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--max-new',type=int);a=ap.parse_args()
    model=load_model();cases=create_inputs();freeze(model[0],model[1]);rs=rules()
    evaluate(np.zeros(87,dtype=np.int64),np.zeros(87,dtype=np.int64),rs[:1],model[0],model[2],model[3])
    pending=[x for x in cases if not (OUT/'records'/f"{x['id']}.json").exists()]
    if a.max_new is not None:pending=pending[:a.max_new]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(lambda x:run_case(x,model),pending))
    if all((OUT/'records'/f"{x['id']}.json").exists() for x in cases):summary(cases)
