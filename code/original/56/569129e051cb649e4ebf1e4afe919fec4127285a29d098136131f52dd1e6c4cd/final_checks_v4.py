"""Verify all archived final candidates and repeat the real-data search.
The repeat uses exactly the frozen seed/config; only timing fields may differ.
"""
import json,hashlib,time
import numpy as np
from wordscore_v3 import ROOT
from scan_v4 import Pipeline
from automata import variants,transform,inverse
from wordpolish_v3 import char_score,fast_word

def main():
 out=ROOT/'results/v4';m=json.loads((out/'inputs.json').read_text())['cases'];p=Pipeline();count=0;maxerr=0.
 f=json.loads((out/'frozen_protocol.json').read_text())
 for name,h in f['sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
 e=json.loads((out/'execution_manifest.json').read_text())
 for name,h in e.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
 for case in m:
  path=out/'cases'/f"{case['id']}.json";assert path.exists(),str(path)
  r=json.loads(path.read_text());o=np.array(case['orientation']);c=np.array(case['arcs_zero_based']);vv=variants(o,c)
  assert r['input_sha256']==hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()
  assert r['protocol_sha256']==hashlib.sha256((out/'frozen_protocol.json').read_bytes()).hexdigest()
  assert r['candidates'][0]['score']==r['best_score']
  for x in r['candidates']:
   seq,rule=vv[x['index']];key=np.array(x['key']);text=np.array(x['decoded']);assert np.array_equal(key[seq],text)
   assert len(set(key))==26
   score=char_score(text,p.engine.lp)+f['config']['alpha']*fast_word(text,p.engine.children,p.engine.vals)
   err=abs(score-x['score']);maxerr=max(maxerr,err);assert err<1e-9
   geom=transform(o,c,rule);table={int(a):int(b) for a,b in zip(text,geom)}
   assert all(table[int(a)]==b for a,b in zip(text,geom))
   oo,cc=inverse(np.array([table[int(a)] for a in text]),rule)
   assert np.array_equal(oo,o) and np.array_equal(cc,c)
   assert x['score']>=x['seed_combined_score']-1e-9
   assert np.all(np.diff(np.array(x['trace'])[:,0])>=-1e-10)
   count+=1
 realcase=next(c for c in m if c['id']=='dorabella');bank=json.loads((ROOT/realcase['cached_v3']).read_text())
 old=json.loads((out/'cases/dorabella.json').read_text());t=time.monotonic()
 new=p.run(np.array(realcase['orientation']),np.array(realcase['arcs_zero_based']),bank,f['config'],f['seed_namespace'])
 for k in ['best_score','identity_score','improvement','best_index','identity_index','decoded']:assert old[k]==new[k],k
 for x,y in zip(old['candidates'],new['candidates']):
  for k in ['index','key','score','trace','greedy_trace','decoded']:assert x[k]==y[k],k
 result=dict(records=len(m),candidates_roundtripped=count,max_score_recompute_error=maxerr,
             frozen_search_and_execution_hashes_intact=True,all_input_hashes_match=True,
             dorabella_full_v4_repeat_identical=True,repeat_seconds=time.monotonic()-t,
             caveat='Repeat reuses unchanged v2/v3 finalist bank; the v4 key search itself was recomputed in full.')
 (out/'final_integrity.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
if __name__=='__main__':main()
