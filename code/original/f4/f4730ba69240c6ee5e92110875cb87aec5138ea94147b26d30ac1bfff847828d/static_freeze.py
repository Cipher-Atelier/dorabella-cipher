"""Static comparison and freeze; never imports/executes search functions."""
from pathlib import Path
import ast,hashlib,json,sys,datetime,gzip,random
R=Path(__file__).resolve().parent;H=lambda b:hashlib.sha256(b).hexdigest()
assert not (R/'attempt').exists()
old=(R/'frozen/original_run_ch3.py.txt').read_text();new=(R/'runner.py').read_text()
a={x.name:x for x in ast.parse(old).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
b={x.name:x for x in ast.parse(new).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
keep=['sha','utc','save','LyonsModel','groups_for','check_glyphs','structural','encode','inverse_record','decode','candidate_record']
checks=[]
for n in keep:
 assert ast.get_source_segment(old,a[n])==ast.get_source_segment(new,b[n])
 assert ast.dump(a[n],include_attributes=False)==ast.dump(b[n],include_attributes=False)
 checks.append({'definition':n,'byte_identical':True,'original_lines':[a[n].lineno,a[n].end_lineno],'runner_lines':[b[n].lineno,b[n].end_lineno]})
for token in ['subprocess','os.system','os.fork','threading','multiprocessing','Popen','shuffle(', 'private/control_truth','hauer_real','hart_real','polish(', 'reheat','setstate(']:assert token not in new,token
stage=ast.get_source_segment(new,b['run_stage'])
assert stage.index("randrange(325)")<stage.index("state['rng'].random()")<stage.index('budget.evaluate(')
assert 'T = 10.0 * math.exp(math.log(0.01) * l / 19)' in stage
assert 'accept = delta >= 0 or u < probability' in stage
assert 'probability = 1.0 if delta >= 0 else math.exp(delta / T)' in stage
assert 'for n in range(325):' in stage
main=ast.get_source_segment(new,b['main']);assert main.index('for l in range(20):')<main.index('for state in states:')<main.index('run_stage(state, l, model, budget, store)')
readback=(R/'readback.py').read_text();ast.parse(readback)
assert 'LyonsModel' not in readback and '.score(' not in readback and 'random' not in readback
runtime=json.loads((R/'preflight.json').read_text())['runtime']
assert sys.version==runtime['version'] and sys.executable==runtime['executable']
for m in (gzip,json,random):
 p=Path(m.__file__);runtime['dependency_files'][str(p)]=H(p.read_bytes())
review={'status':'STATIC_REVIEW_COMPLETE_BEFORE_FIRST_ATTEMPT','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'copied_definitions':checks,
'manual_checks':[
'40 states fixed by input order/assigned branch/r; same input/model hashes; no search result dependent selection.',
'Exactly pair selection then unconditional uniform draw. Score called once for each proposal including repeats/unchanged plaintext.',
'Full26 key and 325 unordered swaps; same glyph decoder, same inverse; sign Δ=child-current; exp only for negative Δ.',
'20 stages x40states x325proposals; independent per-state seeded RNG; no restart, polish, tabu or transmission between states.',
'All accepted candidates execute original candidate_record/inverse. Identical inverse records are content-addressed by case/plaintext and hash; references resolve to retained compressed stage records. No inverse silently omitted.',
'Best distinct from current; same-score different full strings retained as ties. Truth read only in separate postterminal data-only readback.',
'Checkpoint gzip uses standard library, level1, mtime0; no process spawn. Partial stage retained on error/time; attempt directory exclusive.',
'Runtime binary and relevant dependency sources pinned; not a claim to pin entire host image. 60s cooperative not hard-kill.',
'No numerical test/search executed during preparation. AST/static checks do not themselves establish dynamic correctness.'
]}
(R/'STATIC_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
files={str(p.relative_to(R)):{'sha256':H(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(R.rglob('*')) if p.is_file()}
manifest={'version':'CH3-SA-dev-v1','status':'FROZEN_BEFORE_FIRST_ATTEMPT','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime':runtime,'files':files,'command':[sys.executable,'-I','-S',str(R/'runner.py')],'proposals':260000,'cooperative_seconds':60.0}
with (R/'FREEZE_MANIFEST.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
print(json.dumps({'static_pass':True,'manifest_sha256':H((R/'FREEZE_MANIFEST.json').read_bytes()),'runner_sha256':H((R/'runner.py').read_bytes()),'files':len(files),'prior_attempt_absent':not(R/'attempt').exists()}))
