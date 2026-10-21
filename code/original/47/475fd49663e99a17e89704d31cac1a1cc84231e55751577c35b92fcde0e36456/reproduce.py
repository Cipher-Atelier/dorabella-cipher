"""Replay frozen inputs in a fresh directory and compare deterministic outcomes."""
from pathlib import Path
import shutil,sys,subprocess,json,argparse,hashlib
H=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();T=Path(a.output).resolve()
assert not T.exists() and H not in T.parents and T not in H.parents,'Use an absent directory outside the original bundle.'
proto=json.loads((H/'protocol.json').read_text())
for rel,h in proto['hashes'].items():assert hashlib.sha256((H/rel).read_bytes()).hexdigest()==h,rel
T.mkdir(parents=True)
for d in ['code','data','checks','results','logs']:(T/d).mkdir()
for rel in ['code/experiment.py','data/scoring.npz','data/search_inputs.json','data/positive_truth.json','checks/preflight.json','protocol.json','protocol.sha256']:
    shutil.copy2(H/rel,T/rel)
subprocess.run([sys.executable,str(T/'code/experiment.py'),'run'],check=True)
expected=json.loads((H/'data/search_inputs.json').read_text());fields=['S','key_id','all_ties','plaintext','baseline_S','baseline_key_id','char_evaluations','word_evaluations']
for x in expected:
    e=json.loads((H/'results'/f'{x["id"]}.json').read_text());r=json.loads((T/'results'/f'{x["id"]}.json').read_text())
    for f in fields:assert e[f]==r[f],(x['id'],f,e[f],r[f])
(T/'reproduction_verified.json').write_text(json.dumps({'status':'passed','cases':len(expected),'compared_fields':fields},indent=2)+'\n')
print('Fresh replay verified',len(expected))
