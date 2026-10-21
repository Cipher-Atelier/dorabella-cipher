"""Own data-only terminal accounting and immutable-attempt packaging. No scoring."""
import pathlib,json,hashlib,zipfile,datetime,collections,os,sys
B=pathlib.Path('/workspace/scratch/f24f8fae4976');E=B/'BE_W16_v2_execution_20261018';R=B/'BE_W16_v2';A=R/'attempt'
sys.path[:0]=[str(R/'runtime/reused')]
from namespace_view import NamespaceView
def h(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 return d.hexdigest()
def put(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
receipts=[json.loads(p.read_text()) for p in sorted(E.glob('tool_receipt_*.json'))]
assert receipts[0]['command']=='/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -B -I -S /workspace/scratch/f24f8fae4976/BE_W16_v2/runtime/launch.py'
assert sum('exit_code' in x['response'] for x in receipts)==1 and receipts[-1]['response']['exit_code']==2
raw=''.join(x['response']['output'] for x in receipts)
with (E/'primary_tool_stdout.txt').open('x') as f:f.write(raw)
roots=[line.split(' ',1)[1] for line in raw.splitlines() if line.startswith('SEAL_COMPUTED_SHA256 ')]
assert len(roots)==1 and h(A/'seal.json')==roots[0]
seal=json.loads((A/'seal.json').read_text());assert {r['path'] for r in seal['files']}|{'seal.json'}=={str(p.relative_to(A)) for p in A.rglob('*') if p.is_file()}
for row in seal['files']:
 p=A/row['path'];assert p.stat().st_size==row['bytes'] and h(p)==row['sha256'],row['path']
for row in json.loads((R/'MANIFEST.json').read_text())['files']:
 p=R/row['path'];assert h(p)==row['sha256'] and p.stat().st_size==row['bytes']
assert h(R/'FREEZE.json')=='5ad495e82c7bdcacef9bab496512e93dbd3fa3fbd5fb6a1a69baec30212df94d'
oldseals=json.loads((R/'release/UNCHANGED_BYTE_COMPARISON.json').read_text())['old_seals_preserved']
for p,want in oldseals.items():assert h(B/p)==want
result=json.loads((A/'result.json').read_text());ns=NamespaceView();terminal=[]
for case in result['integration']+result['cases']:
 assert case['verified_termination'] and all(x['group']==[] for x in case['terminal'])
 for c in case['commands']:
  anchor=c.get('anchor')
  if anchor:
   now=ns.read_visible(anchor['visible_pid']);same=now is not None and now['starttime']==anchor['starttime'];assert not same or now['state']=='Z'
   terminal.append({'case':case['name'],'role':c['role'],'anchor_visible_pid':anchor['visible_pid'],'anchor_starttime':anchor['starttime'],'same_identity_live':False,'observed_now':now})
checks=[]
scriptset=set(json.loads((R/'FREEZE.json').read_text())['guard_script_paths'])
for r in ns.snapshot():
 if any(a in scriptset for a in r['cmdline']):checks.append(r)
assert not checks
put(E/'terminal_independent.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'observed_tool_exit':2,'terminal_checks':terminal,'exact_script_matches':checks,'old_seals_unchanged':oldseals})
cases=[];found={c['id']:c for c in result['cases']};inputs=json.loads((R/'decoder/inputs.json').read_text())['cases']
for i,row in enumerate(inputs):
 c=found.get(row['id']);info={'number':i+1,'label':['P1','N1','P2','N2','P3','N3','P4','N4'][i],'id':row['id'],'status':c['status'] if c else 'NOT_STARTED','P1_regression':i==0}
 if c:
  folder=A/c['name'];counts=collections.Counter();best_records=[];score_indices=[];segments=[];search_complete=[];raw_errors=[]
  wanted=set(c.get('readback',{}).get('best_plaintexts',[]))
  for p in sorted(folder.glob('events.*.jsonl')):
   with p.open('rb') as f:
    for lineno,b in enumerate(f,1):
     if not b.endswith(b'\n'):raw_errors.append([p.name,lineno,'NO_EOL'])
     e=json.loads(b);counts[e['kind']]+=1
     if e['kind']=='score':
      score_indices.append(e['value']['index'])
      if e['value']['plaintext'] in wanted:best_records.append(e['value'])
     if e['kind']=='segment_begin':segments.append(e['value']['id'])
     if e['kind']=='search_complete':search_complete.append(e['value'])
  consumer=json.loads((folder/'consumer_terminal.json').read_text());broker=json.loads((folder/'broker_terminal.json').read_text());peaks={};cgroup=[]
  for p in folder.glob('process_observations.*.bin'):
   for b in p.open('rb'):
    q=json.loads(b);cgroup.append(q['memory_current'])
    for role,rs in q['groups'].items():
     for rr in rs:
      for line in rr['memory_status']:
       k,v=line.split(':',1);val=int(v.strip().split()[0]);peaks.setdefault(role,{})[k+'_KiB']=max(peaks.get(role,{}).get(k+'_KiB',0),val)
  info.update(elapsed_s=c['elapsed'],readback_error=c.get('readback_error'),verified_termination=c['verified_termination'],terminal=c['terminal'],accepted_readback=c.get('readback'),native_consumer=consumer,native_broker=broker,observed_event_counts=dict(counts),score_indices=score_indices,segment_begin_ids=segments,search_complete_records=search_complete,best_records_accepted_only=best_records,event_errors=raw_errors,sampled_process_high_water=peaks,sampled_cgroup_current_max=max(cgroup,default=None))
 cases.append(info)
summary={'actual_version':'BE-W16-v2','native_legacy_label_preserved':'BE-W16-v1','status':result['status'],'exit_code':result['exit_code'],'elapsed_s':result['elapsed'],'end_utc':result['end_utc'],'start_utc':result['start']['utc'],'supervisor_maxrss_KiB':result['supervisor_maxrss_KiB'],'native_evaluation':result['evaluation'],'accepted_cases':1,'accepted_positive_recovery':'0 of 1 completed positive; P1 regression','paired_comparisons_accepted':0,'paired_comparisons_reason':'N1 correctness STOP; N2–N4 not started. Native false fields are not four measured negative comparisons.','cases':cases,'root_seal_sha256':roots[0],'raw_stdout_sha256':h(E/'primary_tool_stdout.txt'),'old_STOP_unchanged':True,'no_retry_no_target':True}
put(E/'terminal_accounting.json',summary)
put(E/'execution_receipt.json',{'command':receipts[0]['command'],'tool_receipts':receipts,'native_start_utc':summary['start_utc'],'native_end_utc':summary['end_utc'],'native_elapsed_s':result['elapsed'],'observed_exit_code':2,'observation_limit':'Tool-call boundaries bracket observations, not continuous external measurement. Native monotonic timing separately retained.','scope':'one frozen technical retry; no third attempt','root_seal_sha256':roots[0]})
out=B/'Dorabella_BE_W16_v2_full_evidence_20261018.zip';assert not out.exists()
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
 for p in sorted(R.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(B)))
 for p in sorted(E.iterdir()):
  if p.is_file() and p.suffix in ('.json','.txt','.py'):z.write(p,str(p.relative_to(B)))
 z.write(B/'Dorabella_BE_W16_v2_frozen_20261018.zip','frozen/Dorabella_BE_W16_v2_frozen_20261018.zip')
archive={'path':str(out),'sha256':h(out),'bytes':out.stat().st_size,'root_seal_sha256':roots[0],'seal_files_verified':len(seal['files']),'status':'BUNDLE_CLOSED_PENDING_LIBRARY_READBACK','actual_version':'BE-W16-v2'}
put(E/'bundle_receipt.json',archive)
print('BUNDLE_COMPUTED '+json.dumps(archive,sort_keys=True),flush=True)
print('TERMINAL_ACCOUNTING '+json.dumps({'status':result['status'],'exit':2,'elapsed':result['elapsed'],'cases':[{'label':x['label'],'status':x['status'],'events':x.get('observed_event_counts'),'native_scores':x.get('native_consumer',{}).get('scores'),'sampled_memory':x.get('sampled_process_high_water')} for x in cases]},sort_keys=True),flush=True)
