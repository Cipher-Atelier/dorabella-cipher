"""Own data-only readback. No imports from the study, no model lookup/solver/process launch.
Failure accounting after the strict readback STOP. All criteria retained; no acceptance retry.
Single pass over saved JSONL and fixed reference bytes; no regenerated transport.
Bounds: 128 MiB AS, 20/25 s CPU, cooperative 30 s, 8 MiB/file.
"""
from pathlib import Path
import json, hashlib, time, datetime, resource, traceback, os
B=Path('/workspace/scratch/f24f8fae4976/TS_JOURNAL_DIAGNOSTIC_v1')
A=B/'attempt'; E=Path(__file__).resolve().parent
resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(20,25))
start=time.monotonic(); checks=0; details={}; failures=[]
def need(ok,label):
 global checks
 checks+=1
 if time.monotonic()-start>30: raise RuntimeError('READBACK_TIME')
 if not ok: failures.append(label)
def raw(p):
 need(p.stat().st_size<=8*1024**2,'READ_BOUND:'+str(p)); return p.read_bytes()
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(raw(p))
def lines(p):
 b=raw(p);need(b.endswith(b'\n'),'FINAL_NEWLINE:'+str(p));return b.splitlines(keepends=True)
def stat(p):
 s=p.stat();return {k:getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}
def encoded(x):return (json.dumps(x,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
try:
 r=load(A/'result.json'); v=load(A/'verifier_call_receipt.json'); w=load(A/'real_broker_ipc_writer_completion.json'); bind=load(A/'seal_binding.json'); wait=load(A/'wait_before_verifier.json'); term=load(A/'real_broker_terminal.json'); f=load(B/'FREEZE.json'); receipt=load(E/'RAW_EXECUTION_RECEIPT.json')
 need(receipt['attempt_launches']==1 and len(receipt['observations'])==2,'ONE_LAUNCH')
 need(receipt['observations'][0]['response']['session_id']==receipt['observations'][1]['session_id']==50250 and receipt['observations'][1]['response']['exit_code']==0,'SAME_SESSION_EXIT0')
 out=json.loads(receipt['observations'][1]['response']['output']);need(out['status']==r['status']=='PASS_DIAGNOSTIC_THIS_ATTEMPT_ONLY','NATIVE_STATUS')
 need(r['terminal_confirmed'] and len(r['terminal'])==2 and all(t['exit']==0 and t['group']==[] for t in r['terminal']),'TERMINAL')
 need(len(r['commands'])==2 and {c['role'] for c in r['commands']}=={'real_perl','real_broker'} and not r['signals'],'SCOPE_CHILDREN')
 need(r['target_inputs']==r['control_87_inputs']==r['full_model_loads']==0,'NO_SEARCH_SCOPE')
 need(0<r['elapsed']<180 and 0<=r['stages']['real']['seconds']<=30 and 0<=r['stages']['real']['lm_seconds']<=10,'TIMES')
 need(r['before']['memory.max']=='8589934592' and int(r['before']['memory.current'])<5877698560,'INITIAL_RESOURCE')
 need(all(int(r[k]['memory.current'])+201326592+67108864<7516192768 for k in ('post_hash_resource','real_post_hash_resource')),'POST_HASH_RESOURCE')
 need(r['before']['memory.events']==r['after']['memory.events'],'NO_NEW_CGROUP_EVENTS')
 for name,h in r['file_hashes'].items():need(sha(raw(A/name))==h,'SEALED_FILE:'+name)
 for c in r['commands']:
  ready=load(A/(c['role']+'_ready.json'));need(ready['limits']==f['limits']['small'],'CHILD_LIMITS')
  need(raw(A/(c['role']+'_stderr.txt'))==b'','STDERR')
 # Actual source bytes only: do not compile or invoke the verifier again.
 need(sha(raw(B/'readback.py'))==v['source_sha256']=='3c5e1917172c84ef61d56e947d6f283d3dde2096542703ab1ada563d1a722296','VERIFIER_SOURCE')
 need(v['outcome']=='RETURNED' and 'exception' not in v and v['return_value']==r['stages']['real']==load(A/'stage_real.json'),'OBSERVED_RETURN')
 for e in v['reads']:
  p=Path(e['path']);b=raw(p);need(e['EOF'] and e['error'] is None and len(b)==e['bytes'] and sha(b)==e['sha256'],'CONSUMED_BYTES:'+p.name)
  need(e['before']==e['after']==e['path_after']==stat(p),'CONSUMED_IDENTITY:'+p.name)
 need(w['close_completed_monotonic']<=w['completion_monotonic']<=wait['monotonic']<=v['call_start_monotonic']<=v['return_monotonic']<=v['finish_monotonic']<=bind['monotonic'],'CLOSE_WAIT_VERIFY_SEAL_ORDER')
 need(wait['terminal_phases']==[p for p in r['phases'] if 'terminal' in p],'WAIT_PHASES')
 need(bind['status']=='BOUND_COMPLETE' and load(A/'seal_observations.json')['error'] is None,'BINDING')
 for e in bind['bound_reads']+bind['receipt_snapshots']:
  p=Path(e['path']);b=raw(p);need(sha(b)==e['sha256'] and len(b)==e['bytes'] and stat(p)==e['before']==e['after'],'FINAL_SNAPSHOT:'+p.name)
 jraw=raw(A/'real_broker_ipc.jsonl'); jl=jraw.splitlines(keepends=True); evlines=lines(A/'real_broker_ipc_writer_events.jsonl')
 need(len(jl)==w['records']==2244 and len(jraw)==w['bytes']==1966951,'JOURNAL_COMPLETE')
 need(sha(jraw)==w['intended_sha256']==w['physical_incremental_sha256']==w['closed_fd_sha256']==bind['journal']['sha256']==r['file_hashes']['real_broker_ipc.jsonl'],'HASH_CHAIN')
 need(w['status']=='WRITER_CLOSED_CONSISTENT' and stat(A/'real_broker_ipc.jsonl')==w['final'],'WRITER_FINAL')
 need(sha(b''.join(evlines))==w['audit_sha256'] and sum(map(len,evlines))==w['audit_bytes'] and len(evlines)==6734,'AUDIT_COMPLETE')
 op=json.loads(evlines[0]);cl=json.loads(evlines[-1]);need(op['event']=='OPEN' and cl['event']=='CLOSE' and op['identity']==w['initial'] and cl['identity']==w['final'],'OPEN_CLOSE')
 offset=0; last_mono=op['monotonic']; offsets=[]
 for i,line in enumerate(jl,1):
  e=json.loads(line);intent,flushed,read=[json.loads(x) for x in evlines[1+3*(i-1):1+3*i]];end=offset+len(line);h=sha(line)
  need([x['event'] for x in (intent,flushed,read)]==['INTENT','AFTER_FLUSH','WRITE_FLUSH_READ'] and all(x['record']==i for x in (intent,flushed,read)),'AUDIT_SEQUENCE')
  need(intent['start']==read['start']==offset and intent['bytes']==flushed['write_return']==read['write_return']==len(line) and flushed['expected_end']==read['end']==end,'OFFSETS')
  need(intent['sha256']==read['intended_sha256']==read['physical_sha256']==h,'RECORD_HASH')
  need(flushed['writer']==flushed['reader']==flushed['path']==read['stat'] and read['stat']['st_size']==end,'FLUSH_IDENTITY')
  need(all(read['stat'][k]==w['initial'][k] for k in ('st_dev','st_ino','st_mode','st_nlink')),'SAME_INODE')
  kind='request' if 'request' in e else 'response';need(read['channel']==e['channel'] and read['kind']==kind and read['seq']==e[kind][0],'AUDIT_RECORD_LINK')
  need(last_mono<=intent['monotonic']<=flushed['monotonic']<=read['monotonic'],'AUDIT_TIME_ORDER');last_mono=read['monotonic'];offsets.append({'record':i,'start':offset,'end':end,'sha256':h,'channel':e['channel'],'kind':kind,'seq':e[kind][0]});offset=end
 need(last_mono<=cl['closed_at']<=cl['monotonic']<=w['completion_monotonic'] and cl['bytes']==offset and cl['sha256']==sha(jraw),'FINAL_CLOSE_RECORD')
 # Independently group each channel into a request and ordered response frames.
 tx={c:[] for c in ('lm','pat')};framebytes={c:0 for c in tx};framecounts={c:0 for c in tx};maxframe={c:0 for c in tx}
 for line in jl:
  e=json.loads(line);c=e['channel'];need(c in tx,'CHANNEL')
  if 'request' in e:
   req=e['request'];need(req[0]==len(tx[c])+1,'REQUEST_ID');tx[c].append({'request':req,'responses':[]})
  else:
   resp=e['response'];need(tx[c] and resp[0]==tx[c][-1]['request'][0],'RESPONSE_ID');tx[c][-1]['responses'].append(resp);n=len(encoded(resp));need(n<=65536,'FRAME_CAP');framebytes[c]+=n;framecounts[c]+=1;maxframe[c]=max(n,maxframe[c])
 need((len(tx['lm']),len(tx['pat']),framecounts['lm'],framecounts['pat'])==(10,45,58,2131),'IPC_COUNTS')
 for c in tx:
  need(tx[c][-1]['request'][1]=='close' and term[c]['closed'] and term[c]['requests']==len(tx[c]) and term[c]['response_frames']==framecounts[c] and term[c]['response_bytes']==framebytes[c] and term[c]['max_frame']==maxframe[c],'TERMINAL_COUNTERS:'+c)
 spec=load(B/'real_spec.json');qs=load(B/'real_queries.json');lists=load(B/'evidence/real_lists.json');segments=load(B/'evidence/real_segmentation.json');perls=[json.loads(x) for x in lines(A/'real_perl.jsonl')]
 need(len(perls)==24,'PERL_ROWS');lmper=[x for x in perls if x.get('type')=='lm_batch'];lp=[x for x in perls if x.get('type')=='pat_list'];sp=[x for x in perls if x.get('type')=='segmentation']
 need((len(lmper),len(lp),len(sp))==(9,8,6),'PERL_ACCOUNTING')
 for i,n in enumerate(spec['lm_batches']):
  t=tx['lm'][i];reqitems=[[qs[k%36]['table'],qs[k%36]['key_hex']] for k in range(n)];expected=[[qs[k%36]['result'][key] for key in ('found','value_hex','last_row_1based')] for k in range(n)]
  need(t['request']==[i+1,'real',reqitems],'LM_REQUEST_ITEMS');values=[]
  for j,x in enumerate(t['responses']):need(x[1]==len(values) and len(x[2])<=128 and x[3]==(j==len(t['responses'])-1),'LM_FRAMES');values.extend(x[2])
  need(values==expected==lmper[i]['results'] and lmper[i]['batch']==i and lmper[i]['lookups']==n,'LM_FULL_BYTES')
 need(tx['lm'][-1]=={'request':[10,'close',[]],'responses':[[10,0,[],True]]},'LM_CLOSE')
 ltx=[x for x in tx['pat'] if x['request'][1]=='list'];wt=[x for x in tx['pat'] if x['request'][1]=='word'];total=0
 need(len(ltx)==8 and len(wt)==35,'PAT_OPERATIONS')
 for i,t in enumerate(ltx):
  pat=spec['patterns'][i];seq=t['request'][0];need(t['request']==[seq,'list',pat],'LIST_REQUEST');rs=t['responses'];expected=lists[pat]
  if expected is None:need(rs==[[seq,'value',None]],'MISSING_LIST');values=None
  else:
   need(rs[0]==[seq,'begin',len(expected)],'LIST_BEGIN');values=[]
   for x in rs[1:-1]:need(x[1]=='chunk' and x[2]==len(values) and 0<len(x[3])<=64,'CHUNK');values.extend(x[3])
   need(rs[-1]==[seq,'end',len(expected),sum(len(y.encode('ascii')) for y in expected)],'LIST_END');total+=len(values)
  need(values==expected==lp[i]['values'] and lp[i]['batch']==i and lp[i]['pattern']==pat,'LIST_BYTES_ORDER_DUPLICATES')
 expectedwords=[t for s in segments for t in s['membership_trace']]
 need([[x['request'][2],bool(x['responses'][0][2])] for x in wt]==expectedwords and all(len(x['responses'])==1 and x['responses'][0][1]=='value' for x in wt),'WORD_ORDER_VALUES')
 need(sp==[{'type':'segmentation','input':s['input'],'output':s['output']} for s in segments],'SEGMENTATION_SAVED_REFERENCE')
 need(tx['pat'][0]=={'request':[1,'meta',''],'responses':[[1,'value',{'maxlen':46}]]} and tx['pat'][-1]=={'request':[45,'close',''],'responses':[[45,'value','closed']]},'META_PAT_CLOSE')
 pt=perls[-1];need(pt['terminal']=='COMPLETE_COMBINED_TRANSPORT' and pt['score_calls']==pt['search_calls']==0 and total==132856 and pt['lookups']==6244 and pt['segmentations']==6 and pt['list_fetches']==8,'WORKLOAD')
 observations=[json.loads(x) for x in lines(A/'observations.jsonl')];peak={};samplepeak=0
 for ob in observations:
  samplepeak=max(samplepeak,int(ob['memory']['memory.current']));need(int(ob['memory']['memory.current'])<7516192768,'SHARED_SAMPLE')
  need(sum(len(g) for g in ob['groups'].values())<=2,'PROCESS_SAMPLE')
  for role,group in ob['groups'].items():
   for proc in group:
    for s in proc['memory_status']:
     k,val=s.split(':');peak.setdefault(role,{})[k]=max(peak.get(role,{}).get(k,0),int(val.split()[0]))
 need(all(d.get('VmPeak',0)<=65536 for d in peak.values()),'AS_OBSERVED')
 terminal_now=[]
 for c in r['commands']:
  p=Path('/proc')/str(c['anchor']['visible_pid']);entry={'role':c['role'],'visible_pid':c['anchor']['visible_pid'],'recorded_starttime':c['anchor']['starttime'],'path_exists':p.exists()}
  if p.exists():
   st=p.joinpath('stat').read_text().rsplit(')',1)[1].split();entry['now_starttime']=int(st[19]);entry['same_process']=entry['now_starttime']==entry['recorded_starttime'];need(not entry['same_process'],'STILL_LIVE')
  terminal_now.append(entry)
 # Recheck only package small bytes; historical artifacts unchanged, without re-running them.
 for e in f['identities']:
  if not e.get('external',True):need(sha(raw(B/e['path']))==e['sha256'],'FROZEN_SOURCE_UNCHANGED')
 for p,h in [(Path('/workspace/scratch/f24f8fae4976/TS_COMBINED_STORAGE_v1_execution_evidence_20261018/Dorabella_TS_COMBINED_STORAGE_v1_20261018_result.zip'),'7fe8e92e44ef249ac525186518ac0bb5784f4b252f09fc10c5fa0f635aeb4b22'),(Path('/workspace/scratch/f24f8fae4976/TS_COMBINED_STORAGE_v1_static_journal_audit_20261018/Dorabella_TS_COMBINED_STORAGE_v1_journal_audit_20261018.zip'),'bc3b10d2fabcb90c137e6115fb6629fcb0c6084db58372158d8c7f1844e4532b')]:need(sha(p.read_bytes())==h,'HISTORY_UNCHANGED')
 details={'journal_records':2244,'journal_bytes':len(jraw),'journal_sha256':sha(jraw),'audit_records':len(evlines),'writer_inode':w['final'],'verifier_outcome':v['outcome'],'consumed_files':len(v['reads']),'ipc_requests':{c:len(tx[c]) for c in tx},'ipc_frames':framecounts,'lm_lookups':6244,'candidate_occurrences':total,'segmentations':6,'sampled_process_peak_KiB':peak,'sampled_cgroup_peak_bytes':samplepeak,'observation_samples':len(observations),'terminal_direct_read':terminal_now,'elapsed_attempt':r['elapsed'],'historical_STOP_unchanged':True,'scope':'Saved byte comparison only. No numerical/model/search procedure executed.'}
 (E/'JOURNAL_OFFSETS.json').write_text(json.dumps(offsets,separators=(',',':'))+'\n')
 result={'status':'AUDIT_COMPLETE_WITH_FAILURES' if failures else 'AUDIT_COMPLETE_NO_ADDITIONAL_FAILURES','checks':checks,'failures':failures,'details':details,'acceptance':'Historical strict readback STOP remains; this audit does not replace it.'}
except BaseException as exc:
 result={'status':'STOP_INDEPENDENT_READBACK','checks':checks,'error':repr(exc),'traceback':traceback.format_exc(),'partial_details':details,'failures':failures}
result['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();result['readback_elapsed']=time.monotonic()-start
(E/'SAVED_DATA_FAILURE_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));raise SystemExit(0 if result['status'].startswith('AUDIT_COMPLETE') else 2)
