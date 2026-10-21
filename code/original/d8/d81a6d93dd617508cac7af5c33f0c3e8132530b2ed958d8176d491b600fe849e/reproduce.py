"""Fresh replay. Creates a new output tree, never trusts prior cached outputs."""
from pathlib import Path
import json,sys,shutil,subprocess,datetime,argparse
H=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--case',default=None);ap.add_argument('--output',required=True);a=ap.parse_args()
T=Path(a.output).resolve();assert T!=H and H not in T.parents,'Output must be outside the source tree.'
assert not T.exists(),'Choose a new, absent output directory.'
T.mkdir(parents=True)
for rel in ('code','data'):
 shutil.copytree(H/rel,T/rel,ignore=shutil.ignore_patterns('__pycache__'))
(T/'checks').mkdir();(T/'results').mkdir();(T/'logs').mkdir()
for rel in ('protocol.json','protocol.sha256','requirements.txt','environment.json'):
 shutil.copy2(H/rel,T/rel)
for rel in ('preflight.json','benchmark.json'):
 shutil.copy2(H/'checks'/rel,T/'checks'/rel)
def run(script,*args):subprocess.run([sys.executable,str(T/'code'/script),*args],check=True)
run('audit_integrity.py')
# Frozen core files and model checked before execution; no pre-existing numerical results.
sys.path.insert(0,str(T/'code'))
from run import check_frozen
check_frozen()
# Gate is always obtained freshly, including when requesting a single real/control replay.
run('run.py')
run('verify.py')
run('audit_integrity.py')
if a.case:
 cases=json.loads((T/'data/search_inputs.json').read_text());case=next(x for x in cases if x['id']==a.case)
 if case['kind'] not in ('positive','regression'):run('run.py','--kind',case['kind'],'--case',a.case)
else:run('orchestrate.py')
run('verify.py');run('audit_integrity.py',*(['--require-complete'] if not a.case else []))
ids=[a.case] if a.case else [x['id'] for x in json.loads((T/'data/search_inputs.json').read_text())]
for cid in ids:
 expected=json.loads((H/'results'/(cid+'.json')).read_text());actual=json.loads((T/'results'/(cid+'.json')).read_text())
 for field in ('score','key_id','exact_ties','decoded','char_evaluations','word_evaluations'):
  assert actual[field]==expected[field],(cid,field)
(T/'reproduction_verified.json').write_text(json.dumps({'status':'passed','compared_cases':ids,'fresh_output_directory':str(T),'fields':['score','key_id','exact_ties','decoded','char_evaluations','word_evaluations']},indent=2))
print('REPRODUCTION VERIFIED',len(ids))
