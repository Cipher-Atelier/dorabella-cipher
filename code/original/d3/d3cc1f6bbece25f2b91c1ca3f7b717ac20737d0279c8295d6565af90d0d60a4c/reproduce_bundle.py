"""Fresh/resumable main94 and six unpruned audits; compare saved scientific outputs.
Unpack the bundle to a new directory for an unequivocally fresh computation.
"""
from pathlib import Path
import subprocess,sys,json,hashlib
H=Path(__file__).resolve().parents[1]
def run(*args):subprocess.run([sys.executable,str(H/'code'/args[0]),*args[1:]],cwd=H,check=True)
run('run.py','--case','bailey_01','--workers','1')
run('verify.py','--case','bailey_01')
run('run.py','--kind','positive,regression','--workers','4')
run('verify.py','--kind','positive,regression')
run('run.py','--kind','real','--workers','2')
run('verify.py','--kind','real')
run('run.py','--kind','null','--workers','4')
run('verify.py','--kind','all','--sample-blocks')
run('audit_unpruned.py','--workers','4')
cases=json.loads((H/'data/cases.json').read_text());keys=['score87','key_id','exact_tie_ids','decoded','all87_reencrypted','all87_training','heldout_length']
for c in cases:
 actual=json.loads((H/'results'/(c['id']+'.json')).read_text());expected=json.loads((H/'evidence/reference_results'/(c['id']+'.json')).read_text())
 for key in keys:assert actual[key]==expected[key],(c['id'],key,actual[key],expected[key])
 if 'full_correct' in expected:assert actual['full_correct']==expected['full_correct']
r={'status':'passed','cases':len(cases),'strict_score_key_tie_and_decoded_equality':True,'unpruned_audit':json.loads((H/'audit/unpruned_summary.json').read_text())['all_agree']}
(H/'reproduction_verified.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
