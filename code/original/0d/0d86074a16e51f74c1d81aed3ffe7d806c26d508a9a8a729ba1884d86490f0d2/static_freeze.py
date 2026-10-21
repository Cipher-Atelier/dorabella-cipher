"""Static only: parse/compare sources and hash files; never import runner."""
from pathlib import Path
import ast,hashlib,json,sys,datetime
R=Path(__file__).resolve().parent
H=lambda b:hashlib.sha256(b).hexdigest()
assert not (R/'attempt').exists()
source=(R/'frozen/original_run_ch3.py.txt').read_text();new=(R/'runner.py').read_text()
oldtree=ast.parse(source);newtree=ast.parse(new)
old={n.name:n for n in oldtree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
now={n.name:n for n in newtree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
keep=['sha','utc','save','LyonsModel','groups_for','check_glyphs','structural','encode','inverse_record','decode','candidate_record']
checks=[]
for n in keep:
 assert ast.dump(old[n],include_attributes=False)==ast.dump(now[n],include_attributes=False),n
 assert ast.get_source_segment(source,old[n])==ast.get_source_segment(new,now[n]),n
 checks.append({'name':n,'byte_identical_definition':True,'source_lines':[old[n].lineno,old[n].end_lineno],'new_lines':[now[n].lineno,now[n].end_lineno]})
imports=[n for n in ast.walk(newtree) if isinstance(n,(ast.Import,ast.ImportFrom))]
modules=[a.name for n in imports if isinstance(n,ast.Import) for a in n.names]
assert set(modules)<={'datetime','hashlib','json','math','os','sys','time','traceback'}
assert all(n.module=='pathlib' for n in imports if isinstance(n,ast.ImportFrom))
for token in ['random.', 'subprocess', 'os.system', 'os.fork', 'Popen', 'threading', 'multiprocessing', 'private/control_truth', 'hauer_real', 'hart_real', 'prepare_controls(', 'postsearch(']:
 assert token not in new,token
for call in ast.walk(newtree):
 if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='score':
  checks.append({'score_call_line':call.lineno,'source':ast.get_source_segment(new,call)})
ast.parse((R/'readback_assess.py').read_text())
assert 'LyonsModel' not in (R/'readback_assess.py').read_text()
pre=json.loads((R/'preflight.json').read_text())
runtime=pre['runtime'];assert sys.version==runtime['version'] and sys.executable==runtime['executable']
assert H(Path(sys.executable).read_bytes())==runtime['binary_sha256']
review={'status':'STATIC_REVIEW_COMPLETE','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'manual_review':[
 '40 selection fixed by case/assigned branch/r before new scores; all selected receipts byte-equal original ZIP.',
 '325 complete i<j transpositions; changed text dedup with lexical key representative; unchanged excluded.',
 'Best includes all scored neighbors and is distinct from current. Tabu is observed-class projection, last7 including current; no aspiration.',
 'First40 neighborhoods have scheduling priority. All loops bounded by40x20x325; truth read only by separate postterminal assessment.',
 'Exactly one attempt-directory mkdir guard; no child jobs/network/RNG; cooperative time checks per raw swap and score.',
 'Original mathematical definitions byte-identical. Static checks are not empirical validation of new search.',
 'Data-only readback rechecks every stored neighborhood choice/score comparison/inverse field without scorer or RNG.'
]}
(R/'STATIC_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
files={str(p.relative_to(R)):{'sha256':H(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(R.rglob('*')) if p.is_file()}
manifest={'version':'CH3-tabu-dev-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'FROZEN_BEFORE_FIRST_ATTEMPT','runtime':runtime,'files':files,'command':[sys.executable,'-I','-S',str(R/'runner.py')],'limit_seconds':60.0,'max_evaluations':260000}
with (R/'FREEZE_MANIFEST.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
print(json.dumps({'static_pass':True,'manifest_sha256':H((R/'FREEZE_MANIFEST.json').read_bytes()),'runner_sha256':H((R/'runner.py').read_bytes()),'files':len(files),'prior_attempt_absent':not(R/'attempt').exists()}))
