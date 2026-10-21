"""Independent calibration audit. Never imports optimizer, Numba, or archived scorer."""
from pathlib import Path
import json,math,re,hashlib,csv,collections,sys
import numpy as np
R=Path(__file__).resolve().parents[1]
cases=json.loads((R/'inputs/cases.json').read_text());frozen=json.loads((R/'freeze.json').read_text())
for name,h in frozen['hashes'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h
assert json.loads((R/'STATUS.json').read_text())['status']=='completed'
routes=json.loads((R/'inputs/archived_routes_inputs.json').read_text())['routes']
for i,z in enumerate(routes):assert z['id']==i and sorted(z['permutation'])==list(range(87))
lp=np.load(R/'lab/data/english_model.npz')['logp4'].reshape(26,26,26,26)
counts={}
for line in (R/'dictionary/textblob/en/en-spelling.txt').read_text().splitlines():
    if not line or line.startswith(';'):continue
    w,n=line.split()
    if re.fullmatch('[a-z]+',w) and (len(w)>1 or w in ('a','i')):counts[w]=int(n)
total=sum(counts.values());assert len(counts)==29133 and total==1096363
pre={};suf={}
for w,n in counts.items():
    for k in range(1,min(24,len(w)-1)+1):
        pre[w[:k]]=pre.get(w[:k],0)+n;suf[w[-k:]]=suf.get(w[-k:],0)+n
words={w:math.log(n/total) for w,n in counts.items()}
pref={w:math.log(n/total)-2 for w,n in pre.items()};suff={w:math.log(n/total)-2 for w,n in suf.items()}
memo={}
def reference_score(t):
    if t in memo:return memo[t]
    a=[ord(c)-97 for c in t];assert len(a)==87 and all(0<=x<26 for x in a)
    C=sum(float(lp[tuple(a[k:k+4])]) for k in range(84))/84
    dp=[0.]+[-math.inf]*87
    for start in range(87):
        dp[start+1]=max(dp[start+1],dp[start]-8.)
        for end in range(start+1,min(87,start+24)+1):
            w=t[start:end];v=words.get(w,-math.inf)
            if start==0 and end<87:v=max(v,suff.get(w,-math.inf))
            if end==87 and start>0:v=max(v,pref.get(w,-math.inf))
            dp[end]=max(dp[end],dp[start]+v)
    W=dp[-1]/87;memo[t]=(C+.5*W,C,W);return memo[t]
def check_inverse(g,f,rid):
    p=routes[rid]['permutation'];key=f['key'];assert sorted(key)==list(range(26))
    bank={};canon=[]
    for idx in p:
        v=g[idx]
        if v not in bank:bank[v]=len(bank)
        canon.append(bank[v])
    decoded=[key[k] for k in canon];assert decoded==f['decoded']
    mapping={v:key[k] for v,k in bank.items()};inv={ch:tok for tok,ch in mapping.items()}
    assert len(inv)==len(mapping)
    back=[None]*87
    for idx,ch in zip(p,decoded):back[idx]=inv[ch]
    assert back==g
    return ''.join(chr(c+97) for c in decoded),p,mapping
out=[];rows=[];maxerr=0.;nrecords=0;nscored=0;checkpoint_counts={};archived_real=[]
for case in cases:
    name=case['id'];base=R/'runs'/name;g=case['glyph'];rec=json.loads((base/(name+'.json')).read_text())
    firstfiles=sorted((base/'first'/name).glob('*.json'));assert len(firstfiles)==1665
    first={};middle={};final={}
    for stage,files,bank in [('first',firstfiles,first),('middle',sorted((base/'middle'/name).glob('*.json')),middle),('final',sorted((base/'final'/name).glob('*.json')),final)]:
        for path in files:
            rid=int(path.stem);f=json.loads(path.read_text());assert f['route']==rid
            text,p,mapping=check_inverse(g,f,rid);bank[rid]=f;nrecords+=1
            # Prespecified main audit covers ALL final candidates. Extra checks
            # cover all middle and every101st first route, without changing search.
            if stage!='first' or rid%101==0:
                S,C,W=reference_score(text);err=max(abs(S-f['score']),abs(C-f['char_score']),abs(W-f['word_score']))
                maxerr=max(maxerr,err);assert err<1e-9;nscored+=1
    assert sorted(first)==list(range(1665))
    chosen=sorted(set(sorted(first,key=lambda j:(-first[j]['score'],j))[:32]+[0]));assert sorted(middle)==chosen==rec['first_top_routes']
    mids=sorted(middle,key=lambda j:(-middle[j]['score'],j));expect=mids[:16]
    if 0 not in expect:expect.append(0)
    assert sorted(final)==sorted(expect)
    ranked=sorted(final,key=lambda j:(-final[j]['score'],j));rid=ranked[0];best=final[rid]
    text,p,mapping=check_inverse(g,best,rid);assert text==rec['best_text'] and best['score']==rec['best_score']
    assert [f['route'] for f in rec['finalists']]==ranked
    S,C,W=reference_score(text);item=dict(id=name,kind=case['kind'],S=S,C=C,W=W,route=rid,route_name=routes[rid]['name'],text=text,
                                         mapping={str(k):chr(v+97) for k,v in mapping.items()},inverse87=True)
    if case['kind']=='positive':
        correct=sum(a==b for a,b in zip(text,case['plaintext']));assert abs(correct/87-rec['accuracy'])<1e-15
        item.update(correct=correct,accuracy=correct/87,exact=correct==87,truth=case['plaintext'],true_route_first_rank=rec['true_route_first_rank'])
    if case['kind']=='null':item.update(pair=case['pair'],transcription=case['transcription'])
    if case['kind']=='real':
        old=json.loads((R/'archived_wordall'/(name+'.json')).read_text())
        archived_real.append(dict(id=name,same_text=text==old['best_text'],score_error=abs(S-old['best_score']),same_first_shortlist=rec['first_top_routes']==old['first_top_routes']))
    for t,idx in enumerate(p):rows.append([name,t+1,idx+1,g[idx],g[idx]//3,g[idx]%3+1,text[t],mapping[g[idx]]])
    out.append(item);checkpoint_counts[name]={'first':len(first),'middle':len(middle),'final':len(final)}
    print('verified',name,flush=True)
lookup={z['id']:z for z in out};tails={};eps=1e-10
for name in ['hauer_real','hart_real']:
    S=lookup[name]['S'];ns=[lookup[f'{name}_fresh_{i:03d}']['S'] for i in range(19)];k=sum(x>=S-eps for x in ns)
    tails[name]={'real_S':S,'controls_not_lower':k,'n':19,'descriptive_plus_one_tail':(k+1)/20,'null_S':ns}
T=max(lookup[x]['S'] for x in ['hauer_real','hart_real']);nts=[max(lookup[f'{x}_fresh_{i:03d}']['S'] for x in ['hauer_real','hart_real']) for i in range(19)];k=sum(x>=T-eps for x in nts)
tails['paired_max']={'real_T':T,'controls_not_lower':k,'n_pairs':19,'descriptive_plus_one_tail':(k+1)/20,'null_T':nts,'screening_flag':(k+1)/20<=.05}
pos=[x for x in out if x['kind']=='positive'];sensitivity=dict(n=12,exact=sum(x['exact'] for x in pos),at_least90pct=sum(x['accuracy']>=.9 for x in pos),correct_letters=sum(x['correct'] for x in pos),total_letters=1044,
status='previously_seen_regressions_not_blind',no12of12_gate=True)
result=dict(status='PASS',completed_cases=len(out),checkpoint_records=nrecords,independent_score_checks=nscored,max_score_error=maxerr,
            inverse87_winner_count=len(out),all_checkpoints_inverse87=True,checkpoint_counts=checkpoint_counts,
            sensitivity=sensitivity,tails=tails,archived_real_comparisons=archived_real,cases=out,
            limitations='Fixed heuristic procedure calibration; not exhaustive letter search, not independent transcriptions or blind validation; tail is exploratory')
(R/'checks/results_verified.json').write_text(json.dumps(result,indent=2)+'\n')
with (R/'checks/winners87.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['case','reading_position','original_position','original_glyph_id','orientation_code','arc_count','decoded_letter','mapped_letter_code']);w.writerows(rows)
print(json.dumps({'sensitivity':sensitivity,'tails':{n:{k:v for k,v in x.items() if not k.startswith('null_')} for n,x in tails.items()}},indent=2))
