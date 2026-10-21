"""Own bounded saved-byte analysis. Does not import or execute any study file."""
from pathlib import Path
import json,hashlib,zipfile,csv,resource,time,datetime
ROOT=Path('/workspace/scratch/f24f8fae4976')
B=ROOT/'TS_COMBINED_STORAGE_v1';A=B/'attempt'
OUT=ROOT/'TS_COMBINED_STORAGE_v1_static_journal_audit_20261018'
start=time.monotonic()
resource.setrlimit(resource.RLIMIT_AS,(134217728,134217728))
resource.setrlimit(resource.RLIMIT_CPU,(20,25))
def tick():
    if time.monotonic()-start>60:raise RuntimeError('AUDIT_DEADLINE')
def sha(x):return hashlib.sha256(x).hexdigest()
def obj(p):return json.loads(p.read_bytes())
scope=obj(OUT/'AUDIT_SCOPE.json');archive=Path(scope['input_result_zip'])
assert sha(archive.read_bytes())==scope['input_zip_sha256']
archive_matches=[]
with zipfile.ZipFile(archive) as z:
    assert sum(i.file_size for i in z.infolist())<=104857600
    manifest=json.loads(z.read('RESULT_MANIFEST.json'))
    for name,expected in manifest['files'].items():
        tick();data=z.read(name)
        assert len(data)==expected['bytes'] and sha(data)==expected['sha256'],name
        if name.startswith('frozen_package_and_attempt/'):
            p=B/name.removeprefix('frozen_package_and_attempt/')
            assert data==p.read_bytes(),str(p)
            archive_matches.append({'path':str(p),'bytes':len(data),'sha256':sha(data)})
result=obj(A/'result.json');terminal=obj(A/'real_broker_terminal.json')
def rows(p):
    data=p.read_bytes();assert data.endswith(b'\n')
    out=[];pos=0
    for i,line in enumerate(data.splitlines(keepends=True),1):
        tick();event=json.loads(line)
        out.append({'line_1based':i,'start_0based':pos,'end_exclusive':pos+len(line),
                    'bytes':len(line),'sha256':sha(line),'event':event})
        pos+=len(line)
    assert pos==len(data)
    return data,out
ipc_data,ir=rows(A/'real_broker_ipc.jsonl');perl_data,pr=rows(A/'real_perl.jsonl')
states={c:{'requests':0,'frames':0,'response_bytes':0,'closed':False,'request':None,'responses':[]} for c in ('lm','pat')}
mapping=[];index=[];requests=[]
for row in ir:
    event=row['event'];c=event['channel'];s=states[c]
    kind='request' if 'request' in event else 'response';v=event[kind]
    entry={k:row[k] for k in ('line_1based','start_0based','end_exclusive','bytes','sha256')}
    entry.update(channel=c,kind=kind,seq=v[0])
    if kind=='request':
        assert s['request'] is None
        s['requests']+=1;assert v[0]==s['requests'];s['request']=v;s['responses']=[]
        entry.update(operation=v[1],item_count=len(v[2]) if c=='lm' else None,argument=v[2] if c=='pat' else None)
        requests.append(entry)
    else:
        assert s['request'] is not None and s['request'][0]==v[0]
        s['frames']+=1;s['response_bytes']+=len((json.dumps(v,ensure_ascii=True,separators=(',',':'))+'\n').encode('ascii'))
        s['responses'].append(v)
        entry.update(operation=s['request'][1],offset=v[1] if c=='lm' else (v[2] if v[1]=='chunk' else None),
                     value_count=len(v[2]) if c=='lm' else (len(v[3]) if v[1]=='chunk' else None),
                     final=v[3] if c=='lm' else (v[1] in ('value','end')))
        done=v[3] if c=='lm' else v[1] in ('value','end')
        if done:
            q=s['request'];mapped=None
            if c=='lm' and q[1]!='close':
                candidates=[r for r in pr if r['event'].get('type')=='lm_batch' and r['event']['batch']==q[0]-1]
                assert len(candidates)==1;mapped=candidates[0]
                values=[value for response in s['responses'] for value in response[2]]
                assert values==mapped['event']['results'] and len(values)==len(q[2])
            elif c=='pat' and q[1]=='list':
                candidates=[r for r in pr if r['event'].get('type')=='pat_list' and r['event']['batch']==q[0]-2]
                assert len(candidates)==1;mapped=candidates[0]
                values=None if v[1]=='value' else [value for response in s['responses'] if response[1]=='chunk' for value in response[3]]
                assert mapped['event']['pattern']==q[2] and mapped['event']['values']==values
            if mapped:
                mapping.append({'channel':c,'request_seq':q[0],'operation':q[1],
                                'ipc_complete_line':row['line_1based'],'ipc_complete_end':row['end_exclusive'],
                                'perl_line':mapped['line_1based'],'perl_start':mapped['start_0based'],
                                'perl_end':mapped['end_exclusive'],'byte_values_match':True})
            if q[1]=='close':s['closed']=True
            s['request']=None;s['responses']=[]
    index.append(entry)
fields=['line_1based','start_0based','end_exclusive','bytes','channel','kind','seq','operation','argument','offset','item_count','value_count','final','sha256']
with (OUT/'real_IPC_record_offsets.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(index)
perl_index=[]
for row in pr:
    e=row['event'];v={k:row[k] for k in ('line_1based','start_0based','end_exclusive','bytes','sha256')}
    v.update(type=e.get('type',e.get('terminal')),batch=e.get('batch'),pattern=e.get('pattern'),input=e.get('input'))
    perl_index.append(v)
with (OUT/'real_Perl_record_offsets.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(perl_index[0]));w.writeheader();w.writerows(perl_index)
(OUT/'last_5_complete_IPC_records.jsonl').write_bytes(b''.join(ipc_data[r['start_0based']:r['end_exclusive']] for r in ir[-5:]))
# Save original native and independent verdicts separately, byte-for-byte, without changing them.
orig=OUT/'original_verdicts';orig.mkdir()
for label,p in [('native_runner_PASS_result.json',A/'result.json'),
                ('independent_readback_STOP.json',ROOT/'TS_COMBINED_STORAGE_v1_execution_evidence_20261018/SAVED_EVIDENCE_AUDIT.json')]:
    (orig/label).write_bytes(p.read_bytes())
fd=[]
for cmd in result['commands']:
    if cmd['role'].startswith('real_'):
        argv=cmd['launcher_argv'];fd.append({'role':cmd['role'],'launcher_argv':argv,
         'child_gate_fd':int(argv[-5]),'ipc_fds':list(map(int,argv[-4:])),
         'pid_local':cmd['pid_local'],'anchor':cmd['anchor']})
phases=result['phases']
native_assertions={c:{'seq':states[c]['requests'],'expected':10 if c=='lm' else 45,
 'done':states[c]['request'] is None,'last_request_op':next(r['operation'] for r in reversed(requests) if r['channel']==c),
 'readback_py_line42_FINAL_CLOSE_condition':False} for c in ('lm','pat')}
stats={}
for n in ['real_broker_ipc.jsonl','real_perl.jsonl','real_broker_terminal.json','stage_real.json','result.json']:
    p=A/n;st=p.stat();stats[n]={'bytes':st.st_size,'sha256':sha(p.read_bytes()),'st_dev_now':st.st_dev,'st_ino_now':st.st_ino,'st_mtime_ns_now':st.st_mtime_ns,'current_metadata_not_execution_observation':True}
proof={
 'scope':scope,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'archive_to_current_matches':archive_matches,'input_archive_sha256':scope['input_zip_sha256'],
 'all_native_sealed_hashes_match':all(sha((A/n).read_bytes())==h for n,h in result['file_hashes'].items()),
 'file_stats':stats,'IPC_final_newline':ipc_data.endswith(b'\n'),'IPC_lines':len(ir),'IPC_bytes':len(ipc_data),
 'last_IPC_records':index[-5:],'all_IPC_requests':requests,
 'last_LM_response':next(r for r in reversed(index) if r['channel']=='lm' and r['kind']=='response'),
 'states':states,'terminal_claims':terminal,'matching_Perl_records':mapping,
 'unmatched_Perl_records':[r for r in perl_index if r['line_1based'] not in {m['perl_line'] for m in mapping}],
 'required_remaining_records_from_counts':sum(terminal[c]['requests']-states[c]['requests']+terminal[c]['response_frames']-states[c]['frames'] for c in states),
 'first_native_rejection_for_current_bytes':'readback.py:42 READBACK_FINAL_CLOSE, channel lm: 7 != 10; last op real != close',
 'native_assertion_conditions':native_assertions,'saved_role_fd_assignments':fd,'saved_phases':phases,
 'output_caps':{'per_file':8388608,'total':33554432,'observed_attempt_file_bytes':sum(p.stat().st_size for p in A.iterdir() if p.is_file())},
 'elapsed_own_analysis_seconds':time.monotonic()-start,
 'not_recorded_in_original_attempt':['broker log fileno/dev/inode/offset at each write/flush/close',
 'hash and size of exact bytes consumed by internal readback',
 'runtime resolved readback module origin/loaded code digest',
 'filesystem or system-call trace establishing later write/truncation'],
 'no_experiment_execution':True}
(OUT/'OFFSET_AND_IDENTITY_EVIDENCE.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:proof[k] for k in ['IPC_lines','IPC_bytes','last_IPC_records','last_LM_response','required_remaining_records_from_counts','first_native_rejection_for_current_bytes','output_caps','elapsed_own_analysis_seconds']},ensure_ascii=False,indent=2))
print('UNMATCHED_PERL',json.dumps(proof['unmatched_Perl_records'],ensure_ascii=False))
print('FDS',[(x['role'],x['child_gate_fd'],x['ipc_fds']) for x in fd])
