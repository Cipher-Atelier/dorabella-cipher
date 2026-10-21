"""Independent reference scoring and inverse checks, no imported research code."""
import json,math,re,hashlib,csv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];D=R/'route_data';O=R/'route_audit_results'
f=json.loads((R/'route_audit_freeze.json').read_text())
for n,h in f['hashes'].items():assert hashlib.sha256((R/n).read_bytes()).hexdigest()==h
cf=json.loads((R/'route_code_freeze.json').read_text());assert hashlib.sha256((R/cf['path']).read_bytes()).hexdigest()==cf['sha256']
freq={}
for line in (R/'source/en-spelling.txt').read_text().splitlines():
    if not line or line.startswith(';'):continue
    w,n=line.split()
    if re.fullmatch('[a-z]+',w) and (len(w)>1 or w in ['a','i']):freq[w]=int(n)
total=sum(freq.values());assert len(freq)==29133 and total==1096363
pre={};suf={}
for w,n in freq.items():
    for k in range(1,min(24,len(w)-1)+1):pre[w[:k]]=pre.get(w[:k],0)+n;suf[w[-k:]]=suf.get(w[-k:],0)+n
lp=np.load(D/'english_model.npz')['logp4'].reshape(26,26,26,26)
def score(t):
    a=[ord(c)-ord('a') for c in t];C=sum(float(lp[tuple(a[k:k+4])]) for k in range(84))/84
    dp=[0.]+[-math.inf]*len(t)
    for start in range(len(t)):
        dp[start+1]=max(dp[start+1],dp[start]-8.)
        for end in range(start+1,min(len(t),start+24)+1):
            w=t[start:end];terms=[]
            if w in freq:terms.append(math.log(freq[w]/total))
            if start==0 and end<len(t) and w in suf:terms.append(math.log(suf[w]/total)-2.)
            if end==len(t) and start>0 and w in pre:terms.append(math.log(pre[w]/total)-2.)
            if terms:dp[end]=max(dp[end],dp[start]+max(terms))
    return C+.5*dp[-1]/len(t)
a=json.loads((O/'audit.json').read_text());data=json.loads((D/'inputs.json').read_text());cases={z['id']:z for z in data['cases'] if z['kind']=='positive'}
errors=[]
for x in a['cases']:errors.append(abs(score(x['truth'])-x['truth_S']))
for ck in a['candidate_checks']:
    rec=json.loads((D/(ck['id']+'.json' if ck['branch']=='routes' else 'wordall_positive_00.json')).read_text())
    text=''.join(chr(v+97) for v in rec['finalists'][ck['finalist']]['decoded'])
    errors.append(abs(score(text)-ck['S']))
    assert ck['strict_witness']==(text!=cases[ck['id']]['plaintext'] and score(text)-score(cases[ck['id']]['plaintext'])>1e-9)
assert max(errors)<1e-9
groups={}
with (O/'all87_inverse_checks.csv').open() as fh:
    for z in csv.DictReader(fh):groups.setdefault((z['case'],z['candidate']),[]).append(z)
for (name,tag),rows in groups.items():
    assert len(rows)==87 and sorted(int(z['original_position']) for z in rows)==list(range(1,88))
    rel={};inverse={};back=[None]*87
    for z in rows:
        g=int(z['original_glyph_id']);ch=z['letter'];pos=int(z['original_position'])-1
        assert cases[name]['glyph'][pos]==g
        assert g not in rel or rel[g]==ch
        assert ch not in inverse or inverse[ch]==g
        rel[g]=ch;inverse[ch]=g;back[pos]=inverse[ch]
    assert back==cases[name]['glyph']
out=dict(status='PASS',score_checks=len(errors),max_score_error=max(errors),inverse_encodings_87=len(groups),
         objective_obstructions=sum(x['objective_obstruction'] for x in a['cases']),
         scope='Independent score/inverse audit only, not heuristic calibration or decipherment')
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
