"""Read already saved files/tool outputs; do not import or repeat writer smoke."""
import datetime,hashlib,json,pathlib,zipfile,ast
R=pathlib.Path(__file__).resolve().parent;A=R/'smoke_attempt'
def h(b):return hashlib.sha256(b).hexdigest()
def filehash(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):d.update(b)
 return d.hexdigest()
def put(p,x):
 with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n')
raw=json.loads((R/'raw_tool_receipt.json').read_text());calls=raw['calls'];assert len(calls)==1
tool=calls[0]['result'];assert tool['exit_code']==0 and not tool.get('session_id')
lines=[json.loads(x) for x in tool['output'].splitlines()]
starts=[x['SMOKE_START'] for x in lines if 'SMOKE_START' in x];ends=[x for x in lines if 'SMOKE_TERMINAL' in x]
fixtures=[x['FIXTURE_COMPLETE'] for x in lines if 'FIXTURE_COMPLETE' in x]
assert len(starts)==len(ends)==1 and len(fixtures)==15
end=ends[0];result=json.loads((A/'result.json').read_text());closed=json.loads((A/'closed_files.json').read_text())
assert filehash(A/'result.json')==end['result_sha256'] and filehash(A/'closed_files.json')==end['closed_files_sha256']
assert end['SMOKE_TERMINAL']=={k:v for k,v in result.items() if k!='cases'}
assert fixtures==[{k:v for k,v in x.items() if k!='trace'} for x in result['cases']]
assert result['status']=='PASS_SMOKE_ONLY' and result['cleanup'] and result['exit_code']==0 and result['elapsed']<30
assert result['fd_before']==result['fd_after']
dt=lambda x:datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
observation_seconds=(dt(calls[0]['observed_end_utc'])-dt(calls[0]['observed_begin_utc'])).total_seconds()
assert 0<=observation_seconds<30
for row in closed['files']:
 p=A/row['path'];assert p.stat().st_size==row['bytes'] and filehash(p)==row['sha256']
freeze=json.loads((R/'SMOKE_FREEZE.json').read_text())
for row in freeze['files']:
 p=R/row['path'];assert p.stat().st_size==row['bytes'] and filehash(p)==row['sha256']
unchanged=json.loads((R/'UNCHANGED_IDENTITIES.json').read_text())
for row in unchanged['all_original_members_unchanged']:
 p=R.parent/'BE_W16_v1'/row['path'];assert p.stat().st_size==row['bytes'] and filehash(p)==row['sha256']
assert filehash(R.parent/'BE_W16_v1/attempt/case_01/seal.json')=='349f2e676d24fe630f6ed8c749bccd582ef0af6076833aa058c7e366b4e62962'
assert filehash(R.parent/'BE_W16_v1/attempt/seal.json')=='3098182951c6c10ec8e05c47c84bf50ad6e0a7fbc8b284fd91510de0c6909c49'
summary={'status':'DATA_ONLY_READBACK_PASS_SMOKE_ONLY','positive_cases':2,'negative_expected_rejections':13,
 'exit':0,'runner_elapsed_before_final_sealing':result['elapsed'],'tool_observed_call_seconds':observation_seconds,
 'tool_wall_time_seconds':tool['wall_time_seconds'],'maxrss_KiB':result['maxrss_KiB'],'own_fds_closed':True,
 'closed_files_checked':len(closed['files']),'all_old_source_members_unchanged':True,'old_STOP_seals_unchanged':True,
 'result_sha256':end['result_sha256'],'closed_files_sha256':end['closed_files_sha256'],
 'native_payload_limit':'elapsed excludes final seal hashing; external tool-call observation bounds include the full command',
 'library_delivery':'PENDING_EXACT_READBACK'}
put(R/'DATA_ONLY_READBACK.json',summary)
frozen=R.parent/'Dorabella_BE_W16_writer_repair_v1_frozen.zip'
assert filehash(frozen)=='9bd7ff3c61acdb69cc96c6e94de6ed52a243c29a434ef2e5d17efbd4040311b2'
selected=[p for p in sorted(R.rglob('*')) if p.is_file() and p.name!='EVIDENCE_MANIFEST.json']
rows=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':filehash(p)} for p in selected]
put(R/'EVIDENCE_MANIFEST.json',{'scope':'writer repair + own smoke; no pilot execution','files':rows,'nested_frozen_zip_sha256':filehash(frozen)})
out=R.parent/'Dorabella_BE_W16_writer_repair_v1_evidence.zip'
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in selected+[R/'EVIDENCE_MANIFEST.json']:z.write(p,str(p.relative_to(R)))
 z.write(frozen,'Dorabella_BE_W16_writer_repair_v1_frozen.zip')
with zipfile.ZipFile(out) as z:
 for row in rows:assert h(z.read(row['path']))==row['sha256']
print('READBACK_COMPUTED '+json.dumps(summary,sort_keys=True),flush=True)
print('EVIDENCE_ZIP_COMPUTED '+json.dumps({'path':str(out),'bytes':out.stat().st_size,'sha256':filehash(out),'members':len(rows)+2},sort_keys=True),flush=True)
print('RUNTIME_HASHES '+json.dumps({p.name:filehash(p) for p in sorted((R/'runtime').iterdir())},sort_keys=True),flush=True)
