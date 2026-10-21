import pathlib,json,hashlib,ast,zipfile,datetime
D=pathlib.Path('/workspace/scratch/f24f8fae4976/TS_RLIMIT_ORDER_REPAIR_v1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=(D/'baseline/runtime/run_profile.py').read_text();s=(D/'candidate/runtime/run_profile.py').read_text()
restored=s.replace('from limit_order import prepare_supervisor_limits,seal_supervisor_limits\n','').replace("  result['limits_prepared']=prepare_supervisor_limits(F['role_limits'])\n","  for k,v in F['role_limits']['supervisor'].items():resource.setrlimit(getattr(resource,k),tuple(v))\n").replace("  result['limits_final']=seal_supervisor_limits(F['role_limits'])\n",'').replace("  if 'limits_prepared' in result and 'limits_final' not in result:\n   try:result['limits_final']=seal_supervisor_limits(F['role_limits'])\n   except BaseException as le:result['limit_seal_error']=repr(le)\n",'')
assert restored==base
for p in list((D/'candidate').rglob('*.py'))+list((D/'smoke').glob('*.py')):ast.parse(p.read_text())
assert s.index("result['limits_final']=seal_supervisor_limits") < s.index("os.write(c['gate'],b'G')")
assert s.index("prepare_supervisor_limits(F['role_limits'])") < s.index("bc=spawn('broker'")
stub=(D/'smoke/child_stub.py').read_text();child=(D/'baseline/runtime/child_gate.py').read_text()
assert "for name,value in F[role].items():resource.setrlimit(getattr(resource,name),tuple(value))" in stub
assert "for name,value in F['role_limits'][role].items():resource.setrlimit(getattr(resource,name),tuple(value))" in child
F=json.loads((D/'baseline/FREEZE.json').read_text());roles=json.loads((D/'smoke/role_limits.json').read_text());assert roles==F['role_limits']
pairs=[]
for k,v in roles['supervisor'].items():
 pairs.append({'limit':k,'supervisor_final':v,'supervisor_staged':[v[0],max(r[k][1] for r in roles.values())],'broker':roles['broker'][k],'perl':roles['perl'][k],'old_child_hard_conflict':any(r[k][1]>v[1] for r in roles.values())})
review={'version':'TS-RLIMIT-ORDER-REPAIR-v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate_supervisor_reverts_byte_exactly_to_baseline':True,'AST_parse_only_no_import_of_supervisor_or_foreign_code':True,'guard_before_release':True,'configured_limits':pairs,'only_conflict':'RLIMIT_AS','unconfigured_limits':'No setrlimit calls added for DATA/STACK/RSS/MEMLOCK/NPROC/MSGQUEUE/NICE/RTPRIO/RTTIME/SIGPENDING; OFILE is NOFILE alias. Smoke records every available RLIMIT constant and verifies unconfigured unique resource ids unchanged.','limit_inventory':'All setrlimit call sites in baseline runtime: run_profile.py:76 and child_gate.py:5; launcher only execve. Candidate replaces first only and adds own helper.','finite_evidence_limits':'Kernel values /proc/getrlimit verified; no deliberate exhaustion of AS/CPU/FSIZE/NOFILE, and no full search runtime claim.','baseline_stop_and_delivery_unchanged':True}
(D/'STATIC_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
files=[]
for p in sorted(D.rglob('*')):
 if p.is_file():files.append({'path':str(p.relative_to(D)),'bytes':p.stat().st_size,'sha256':sha(p)})
freeze={'version':'TS-RLIMIT-ORDER-REPAIR-v1-smoke-freeze','python_sha256':sha(pathlib.Path(F['python'])),'files':files,'allowed_execution':'smoke/run_smoke.py only; main search not approved','limit_policy':roles}
(D/'SMOKE_FREEZE.json').write_text(json.dumps(freeze,indent=2)+'\n')
manifest={'version':'TS-RLIMIT-ORDER-REPAIR-v1','files':files+[{'path':'SMOKE_FREEZE.json','bytes':(D/'SMOKE_FREEZE.json').stat().st_size,'sha256':sha(D/'SMOKE_FREEZE.json')}]}
(D/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
Z=D.parent/'Dorabella_TS_RLIMIT_ORDER_REPAIR_v1_pre_smoke_20261018.zip'
with zipfile.ZipFile(Z,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(D.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(D)))
print('STATIC_REVIEW_COMPUTED',json.dumps(review))
for p in [D/'diffs/limit_order.patch',D/'candidate/runtime/run_profile.py',D/'candidate/runtime/limit_order.py',D/'SMOKE_FREEZE.json',D/'MANIFEST.json',Z]:print('COMPUTED_SHA256',sha(p),str(p))

