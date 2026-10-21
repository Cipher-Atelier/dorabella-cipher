"""Static preparation: no imports of scientific code, scoring or random draws."""
from pathlib import Path
import ast,hashlib,json,sys,zipfile,datetime
R=Path(__file__).resolve().parent;O=R.parent/'CH3_tabu_dev_v1_20261017'
H=lambda b:hashlib.sha256(b).hexdigest()
def save(p,d):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
Z=R.parent/'Dorabella_CH3_tabu_dev_v1_result_20261017.zip'
assert H(Z.read_bytes())=='1486082b0d6a55294e94c9720d4e9e06a994be24a4b938a96ce46793fd9d337c'
assert not (R/'attempt').exists()
expected={'frozen/initial_states.json':'3f35f25f792829938b47148edefc4227e1e64e30e7ea60a85246431fd19cecd5','frozen/decoder_controls.json':'74c44ea9113a9bc93abdfbcec2270221b194f8a7c8007d92fa8bd7bf1ae688e8','frozen/quadgrams.txt':'b461953d6ad3b5e1f0f07c133102b7656a205529cb8697a8ecda8d45311f7a55'}
names=list(expected)+['frozen/original_run_ch3.py.txt','private/control_truth.json','private/old_assessment_controls.json','attempt/first_neighborhoods.json']
with zipfile.ZipFile(Z) as z:
 for n in names:
  b=z.read(n);assert b==(O/n).read_bytes()
  if n in expected:assert H(b)==expected[n]
  dst=R/('evidence/first_neighborhoods.json' if n.startswith('attempt/') else n)
  dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
rows=json.loads((R/'frozen/initial_states.json').read_text())
order=[p+f'{i:02d}' for p in ('P','N') for i in range(1,5)]
ids=[f'{c}_B{int(c[1:])-1}_r{r}' for c in order for r in range(5)]
assert len(rows)==40 and [r['state_id'] for r in rows]==ids
seed_rows=[{'state_id':s,'seed_text':'CH3-SA-dev-v1|2026101704|'+s,'seed_integer':int.from_bytes(hashlib.sha256(('CH3-SA-dev-v1|2026101704|'+s).encode()).digest(),'big')} for s in ids]
save(R/'frozen/seeds.json',seed_rows)
(R/'frozen/PLAN.md').write_bytes((R.parent/'Dorabella_CH3_SA_dev_v1_plan_20261017.md').read_bytes())
old=json.loads((O/'FREEZE_MANIFEST.json').read_text())['runtime']
assert sys.version==old['version'] and sys.executable==old['executable']
assert H(Path(sys.executable).read_bytes())==old['binary_sha256']
for p,h in old['dependency_files'].items():assert H(Path(p).read_bytes())==h
save(R/'preflight.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'prior_attempt_absent':True,'library_title_search':'Only accepted plan found; combined with current local state, not a universal archive absence proof.','runtime':old,'source_zip_sha256':H(Z.read_bytes()),'data_hashes':expected,'state_order':ids})
src=(R/'frozen/original_run_ch3.py.txt').read_text()
assert H(src.encode())=='37df8cd01cf5da1bc51a64ba282117fcf10afb23adfc842a33af9611c6effca8'
keep=['sha','utc','save','LyonsModel','groups_for','check_glyphs','structural','encode','inverse_record','decode','candidate_record']
blocks={n.name:ast.get_source_segment(src,n) for n in ast.parse(src).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in keep}
header='''"""CH3-SA-dev-v1: sole synchronous attempt, standard library, no target/truth in search."""\nfrom pathlib import Path\nimport datetime, hashlib, json, math, os, sys, time, traceback, random, gzip\nAZ = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'\nBRANCHES = ('B0','B1','B2','B3')\n'''
(R/'runner.py').write_text(header+'\n\n'+'\n\n'.join(blocks[n] for n in keep)+'\n\n')
print(json.dumps({'prepared':True,'states':40,'runner_not_executed':True,'runtime':sys.version}))
