"""Own data-only readback. No execution of repair/search functions."""
import pathlib,json,hashlib,zipfile,datetime
D=pathlib.Path('/workspace/scratch/f24f8fae4976/TS_RLIMIT_ORDER_REPAIR_v1');A=D/'smoke_attempt'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt=json.loads((D/'evidence/raw_smoke_receipt.json').read_text());r=json.loads((A/'result.json').read_text());closed=json.loads((A/'closed_files.json').read_text())
assert receipt['observed_exit']==0 and ''.join(x['output'] for x in receipt['tool_response_raw'])==receipt['observed_stdout']
raw=receipt['observed_stdout'].splitlines();lists=[json.loads(x.split(' ',1)[1]) for x in raw if x.startswith('SMOKE_CLOSED_FILES_COMPUTED ')]
heads=[json.loads(x.split(' ',1)[1]) for x in raw if x.startswith('SMOKE_RESULT_COMPUTED ')]
assert lists==[closed] and len(heads)==1
assert heads[0]['result_sha256']==sha(A/'result.json') and heads[0]['closed_files_sha256']==sha(A/'closed_files.json')
for x in closed:
 p=A/x['path'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
old=json.loads((D/'evidence/preparation_baseline.json').read_text())['baseline_records']
for x in old:
 p=pathlib.Path(x['path']);assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
freeze=json.loads((D/'SMOKE_FREEZE.json').read_text())
for x in freeze['files']:
 p=D/x['path'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
assert r['status']=='PASS_WRAPPER_LIMITS_ONLY' and r['exit_code']==0 and r['elapsed']<=15 and r['verified_cleanup']
assert [(x['exit'],x['group']) for x in r['terminal']]==[(0,[]),(-15,[])]
assert len(r['pure_negative_fixtures'])==5
events=r['events'];assert [x['kind'] for x in events]==['SUPERVISOR_STAGED','CHILD_READY_BLOCKED','CHILD_READY_BLOCKED','SUPERVISOR_FINAL_BEFORE_RELEASE','RELEASE','RELEASE']
roles=json.loads((D/'smoke/role_limits.json').read_text());assert r['final_limits']==roles['supervisor']
for x in r['children_ready']:
 assert {k:x['record']['after'][k] for k in roles[x['role']]}==roles[x['role']]
value={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'READBACK_CONFIRMED_WRAPPER_SMOKE_ONLY','raw_stdout_bound':True,'closed_files_verified':len(closed),'old_records_unchanged':len(old),'freeze_files_unchanged':len(freeze['files']),'no_reexecution':True,'smoke_result_sha256':sha(A/'result.json'),'raw_receipt_sha256':sha(D/'evidence/raw_smoke_receipt.json'),'diff_sha256':sha(D/'diffs/limit_order.patch'),'main_search_rerun':False,'scientific_status':'UNCHANGED_STOP_CORRECTNESS'}
(D/'evidence/data_only_readback.json').write_text(json.dumps(value,indent=2)+'\n')
rows=[]
for p in sorted(D.rglob('*')):
 if p.is_file():rows.append({'path':str(p.relative_to(D)),'bytes':p.stat().st_size,'sha256':sha(p)})
(D/'RESULTS_MANIFEST.json').write_text(json.dumps({'version':'TS-RLIMIT-ORDER-REPAIR-v1-results','files':rows},indent=2)+'\n')
Z=D.parent/'Dorabella_TS_RLIMIT_ORDER_REPAIR_v1_complete_20261018.zip'
with zipfile.ZipFile(Z,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(D.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(D)))
print('DATA_ONLY_READBACK_COMPUTED',json.dumps(value))
print('COMPLETE_ZIP_COMPUTED_SHA256',sha(Z))
print('COMPLETE_ZIP_BYTES',Z.stat().st_size)
print('RESULTS_MANIFEST_COMPUTED_SHA256',sha(D/'RESULTS_MANIFEST.json'))

