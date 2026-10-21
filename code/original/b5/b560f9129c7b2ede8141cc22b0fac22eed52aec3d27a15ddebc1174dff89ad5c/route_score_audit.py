"""Score an immutable archive. Does not import/run any solver or numba code."""
from pathlib import Path
import json,hashlib,csv,sys,types,importlib.util,shutil,datetime
import numpy as np
R=Path(__file__).resolve().parents[1];D=R/'route_data';O=R/'route_audit_results';O.mkdir(exist_ok=True)
freeze=json.loads((R/'route_audit_freeze.json').read_text())
for name,sha in freeze['hashes'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==sha
# Run the archived WordScorer unchanged, supplying the exact dictionary through
# its expected TextBlob data path. No TextBlob inference code is involved.
q=D/'textblob/en';q.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/'source/en-spelling.txt',q/'en-spelling.txt')
stub=types.ModuleType('textblob');stub.__file__=str(D/'textblob/__init__.py');sys.modules['textblob']=stub
spec=importlib.util.spec_from_file_location('archived_wordscore',R/'prior_code/wordscore_v3.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);ws=mod.WordScorer()
assert ws.metadata['sha256']=='eade91558167fe09a481abf59e176af8643ad78678cc53dd5aeaf2a8b30fa332'
lp=np.load(D/'english_model.npz')['logp4']
data=json.loads((D/'inputs.json').read_text());routes=data['routes']
truths=[z for z in data['cases'] if z['kind']=='positive'];assert len(truths)==12
def score(text):
    a=[ord(c)-97 for c in text];v=0.
    for j in range(84):v+=float(lp[((a[j]*26+a[j+1])*26+a[j+2])*26+a[j+3]])
    C=v/84;W=ws.score(text);return C+.5*W,C,W
def canonical(a):
    bank={};return [bank.setdefault(int(x),len(bank)) for x in a]
def inversion(g,route,text):
    assert len(g)==len(route)==len(text)==87 and sorted(route)==list(range(87))
    mapping={};inv={}
    for idx,ch in zip(route,text):
        glyph=g[idx]
        assert glyph not in mapping or mapping[glyph]==ch
        assert ch not in inv or inv[ch]==glyph
        mapping[glyph]=ch;inv[ch]=glyph
    returned=[None]*87
    for idx,ch in zip(route,text):returned[idx]=inv[ch]
    assert returned==g
    return mapping,returned
rows=[];position_rows=[];checks=[];maxerr=0.;controls=0
for z in truths:
    name=z['id'];g=z['glyph'];plain=z['plaintext'];ts=score(plain);p=routes[z['generating_route']]['permutation']
    assert ts==score(plain);controls+=1
    mapping,_=inversion(g,p,plain);controls+=1
    for t,idx in enumerate(p):position_rows.append([name,'truth',t+1,idx+1,g[idx],plain[t],z['generating_route']])
    # A bijective letter swap remains lawful but is known wrong, independently
    # of whether its score happens to rise or fall.
    chars=sorted(set(plain));x,y=chars[:2];swapped=plain.translate(str.maketrans({x:y,y:x}));assert swapped!=plain
    inversion(g,p,swapped);controls+=1
    try:inversion(g[:-1],p,plain)
    except AssertionError:controls+=1
    else:raise AssertionError('Negative length control failed')
    records=[('routes',json.loads((D/(name+'.json')).read_text()))]
    if name=='positive_00':records.append(('wordall',json.loads((D/'wordall_positive_00.json').read_text())))
    candidates=[]
    for branch,rec in records:
        for j,f in enumerate(rec['finalists']):
            rid=f['representative_route'] if branch=='routes' else f['route'];route=routes[rid]['permutation']
            text=''.join(chr(x+97) for x in f['decoded'])
            assert [f['key'][a] for a in canonical([g[t] for t in route])]==f['decoded']
            inversion(g,route,text)
            S,C,W=score(text);err=max(abs(S-f['score']),abs(C-f['char_score']),abs(W-f['word_score']));maxerr=max(maxerr,err);assert err<1e-9
            wrong=text!=plain;delta=S-ts[0];witness=wrong and delta>1e-9
            checks.append(dict(id=name,branch=branch,finalist=j,route=rid,S=S,C=C,W=W,wrong=wrong,delta_vs_truth=delta,strict_witness=witness,re_encryption_87=True))
            if witness:
                for t,idx in enumerate(route):position_rows.append([name,f'{branch}_wrong_{j}',t+1,idx+1,g[idx],text[t],rid])
            candidates.append((S,text,rid,branch,j,witness))
    wrongs=[x for x in candidates if x[1]!=plain]
    bestwrong=max(wrongs,key=lambda x:x[0]) if wrongs else None
    row=dict(id=name,truth=plain,truth_S=ts[0],truth_C=ts[1],truth_W=ts[2],generating_route=z['generating_route'],
             candidates_checked=len(candidates),strict_witnesses=sum(x[-1] for x in candidates),
             objective_obstruction=any(x[-1] for x in candidates),
             old_reported_accuracy=records[0][1]['accuracy'],true_pattern_finalist=records[0][1]['true_pattern_finalist'],
             true_pattern_ranks=records[0][1]['true_pattern_ranks'])
    if bestwrong:
        row['best_saved_wrong']=dict(S=bestwrong[0],text=bestwrong[1],route=bestwrong[2],branch=bestwrong[3],finalist=bestwrong[4],delta_vs_truth=bestwrong[0]-ts[0])
    rows.append(row)
with (O/'all87_inverse_checks.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['case','candidate','read_position','original_position','original_glyph_id','letter','route']);w.writerows(position_rows)
out=dict(scope='Necessary score audit only, no solver or real/null search',cases=rows,candidate_checks=checks,
         cases_with_strict_obstruction=sum(x['objective_obstruction'] for x in rows),
         max_archived_score_error=maxerr,implementation_controls_passed=controls,
         inverse_position_checks_published=len(position_rows),real_cipher_search_performed=False,null_search_performed=False)
(O/'audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['cases_with_strict_obstruction','max_archived_score_error','implementation_controls_passed','inverse_position_checks_published']}))
print(json.dumps([{k:x[k] for k in ['id','objective_obstruction','old_reported_accuracy','true_pattern_finalist']} for x in rows]))
