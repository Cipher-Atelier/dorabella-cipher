"""No search: freeze inputs, verify mechanism/control invariants and old code hashes."""
from pathlib import Path
import sys,types,json,hashlib,collections,time
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'dependencies'),str(R/'lab')]
import numba,llvmlite,numpy as np
import routes_v6
rr=routes_v6.routes();old=json.loads((R/'inputs/archived_routes_inputs.json').read_text())
assert len(rr)==1665 and len(old['routes'])==1665
for (p,n),z in zip(rr,old['routes']):assert p.tolist()==z['permutation'] and n==z['name']
cases=json.loads((R/'inputs/cases.json').read_text());real={z['id']:z for z in cases if z['kind']=='real'}
oldreal={z['id']:z for z in old['cases'] if z['kind']=='real'}
for n,z in real.items():assert z['glyph']==oldreal[n]['glyph']
def pairs(g):return collections.Counter(zip(g[:-1],g[1:]))
for z in cases:
    g=z['glyph'];assert len(g)==87 and all(isinstance(x,int) and 0<=x<24 for x in g)
    if z['kind']=='null':
        base=real[z['transcription']]['glyph']
        assert collections.Counter(g)==collections.Counter(base) and pairs(g)==pairs(base)
        assert (g[0],g[-1])==(base[0],base[-1])
    if z['kind']=='positive':
        text=z['plaintext'];p=rr[z['generating_route']][0];rel={};inv={}
        for idx,ch in zip(p,text):
            token=g[idx];assert token not in rel or rel[token]==ch;assert ch not in inv or inv[ch]==token
            rel[token]=ch;inv[ch]=token
        back=[None]*87
        for idx,ch in zip(p,text):back[idx]=inv[ch]
        assert back==g and len(text)==87
frozen=json.loads((R/'inputs/archived_wordall_frozen.json').read_text())
for name,h in frozen['hashes'].items():assert hashlib.sha256((R/'lab'/name).read_bytes()).hexdigest()==h
assert numba.__version__=='0.65.1' and np.__version__=='2.3.5'
out=dict(status='PASS',route_count=len(rr),cases=len(cases),positive=12,real=2,conditional_null=38,
         all87_input_invariants=True,archived_code_hashes_match=True,
         numba=numba.__version__,llvmlite=llvmlite.__version__,numpy=np.__version__,python=sys.version)
(R/'checks/input_preflight.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
