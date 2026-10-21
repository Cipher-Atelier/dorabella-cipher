"""Freeze full87 objective and fixed input set before any full search."""
from pathlib import Path
import json,hashlib,datetime,ast,collections
H=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=H/'frozen_protocol.json';assert not p.exists(),'Do not overwrite frozen protocol'
cases=json.loads((H/'data/cases.json').read_text());inputs=json.loads((H/'data/search_inputs.json').read_text())
assert len(cases)==94 and len({c['id'] for c in cases})==94
assert inputs==[{'id':c['id'],'kind':c['kind'],'glyph':c['glyph']} for c in cases]
assert collections.Counter(c['kind'] for c in cases)=={'positive':12,'regression':2,'real':2,'null':78}
for c in cases:assert len(c['glyph'])==87 and all(type(z)==int and 0<=z<24 for z in c['glyph'])
for c in cases:
 if c['kind']=='null':
  real=next(x for x in cases if x['id']==c['source']);g=c['glyph'];r=real['glyph']
  assert collections.Counter(g)==collections.Counter(r)
  assert collections.Counter(zip(g,g[1:]))==collections.Counter(zip(r,r[1:]))
  assert (g[0],g[-1])==(r[0],r[-1])
old=json.loads((H/'data/round11_frozen_protocol.json').read_text())
protocol=json.loads(json.dumps(old['protocol']))
protocol.update(id='round13-direction-reversal-full87-exact-v1',execution_order='First bailey_01 full87 and independent verification. Then all14 positive/regression full87 and verification. Then two real full87 and verification. Then78 null full87 and verification. No scorer retuning.',interpretation='All87 used for training/selection. NO heldout test or decryption claim. Frozen round11 model, family and94 cases reused; texts previously seen. Exact numerical maximum is not a semantic solution. Matched controls yield separate descriptive conditional tails only; no global adaptive-search correction.')
protocol['objective'].update(train='S87=C87+0.5*W87 on all87 glyphs, including all84 within-fulltext 4gram windows.',key_selection='Strict largest float64 S87; exact equality retains every tied key and selects smallest canonical ID. No tolerance in key selection.',test='None. Heldout length0.',whole87='All87 is optimization input, not heldout.')
protocol['negative_controls']['tail']='(1+count(S87_control>=S87_real-1e-10))/(39+1), separately for each transcription; descriptive conditional tail, not solution probability'
protocol['verification'].update(independent='All checkpoint chain/hash/shape/count checks; direct C for every saved fully evaluated key; independent Python W for per-block samples, winners and all ties; reencrypt87; 14 brute sampled blocks; six full unpruned audits.',development='Preexisting synthetic checks at lengths43 and87: seeds1301..1304, 768keys each; zero actual full-search outputs existed before this freeze.',full_unpruned_cases=['bailey_01','elgar_caractacus_postcard','hauer_real','hart_real','hauer_real_pair_00','hart_real_pair_00'],local_stats_caveat='stats[:,7] and [:,8] contain maxima over evaluated keys only, not exact local maxima; global max and ties exact.',acceptance='Every computation must verify exactly against checkpoints and independent scoring within1e-11. Positive recovery rates are outcomes, never scorer tuning or hidden exclusion criteria. If verification fails stop dependent stages and diagnose. No full experiment result may be reported before it actually runs.')
paths=['data/cases.json','data/search_inputs.json','data/scoring.npz','data/round11_frozen_protocol.json','code/engine.py','code/run.py','code/verify.py','code/freeze.py','checks/engine_body_provenance.json']
f={'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol':protocol,'hashes':{x:sha(H/x) for x in paths}}
p.write_text(json.dumps(f,sort_keys=True,indent=2)+'\n')
root=H.parent/'dorabella_audit'
sources={str(x.relative_to(root)):sha(x) for sub in ['round10','round11','test_lab'] for x in (root/sub).rglob('*') if x.is_file()}
(H/'checks/source_files_before.json').write_text(json.dumps(sources,sort_keys=True,indent=2)+'\n')
print('FROZEN',sha(p),'94 inputs; null counts, bigrams, endpoints passed; source files',len(sources))
