import engine as e
import json,numpy as np,hashlib,datetime
src=e.H/'source/dorabella_round13'
old=json.loads((src/'data/cases.json').read_text());cases=[];truth=[]
rng=np.random.default_rng(202610051340)
for x in old:
 c={k:x[k] for k in ('id','kind','source','replicate','glyph') if k in x}
 if x['kind'] in ('positive','regression'):
  keyid=int(rng.integers(e.NK));key=e.key_at(keyid);inv={int(a):i for i,a in enumerate(key)}
  c['glyph']=[inv[ord(t)-97] for t in x['plaintext']]
  truth.append(dict(id=x['id'],plaintext=x['plaintext'],true_key_id=keyid,source=x.get('source'),status='previously_seen_regression; fresh encryption; not independent validation'))
 cases.append(c)
(e.H/'data/search_inputs.json').write_text(json.dumps(cases,indent=2));(e.H/'data/positive_truth.json').write_text(json.dumps(truth,indent=2))
print('prepared',len(cases),'truths',len(truth))
