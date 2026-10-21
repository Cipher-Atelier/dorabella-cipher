"""Independent inspection of saved files only; never import study modules or score text."""
from pathlib import Path
import json,hashlib,datetime,os,re,resource,time
R=Path('/workspace/scratch/f24f8fae4976');B=R/'TS_COMBINED_STORAGE_v1';A=B/'attempt';E=R/'TS_COMBINED_STORAGE_v1_execution_evidence_20261018'
resource.setrlimit(resource.RLIMIT_AS,(134217728,134217728))
resource.setrlimit(resource.RLIMIT_CPU,(15,20))
start=time.monotonic();checks=[]
def ok(value,name):
    checks.append({'check':name,'pass':bool(value)})
    if not value:raise AssertionError(name)
def obj(p):return json.loads(p.read_text())
def lines(p):
    with p.open('rb') as f:
        for line in f:
            if time.monotonic()-start>30:raise RuntimeError('READBACK_DEADLINE')
            yield json.loads(line)
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
result=obj(A/'result.json');f=obj(B/'FREEZE.json');raw=obj(E/'RAW_EXECUTION_RECEIPT.json')
ok(raw['polls'][-1]['tool_result']['exit_code']==0 and raw['initial_tool_result']['session_id']==2051,'same_tool_session_exit0')
ok(result['status']=='PASS_FINITE_COMBINED_STORAGE_ONLY' and result['error'] if 'error' in result else result['status']=='PASS_FINITE_COMBINED_STORAGE_ONLY','saved_status')
ok(result.get('error') is None and result.get('termination_error') is None,'no_error')
ok(result['terminal_confirmed'] and len(result['terminal'])==5 and all(x['exit']==0 and x['group']==[] for x in result['terminal']),'all_five_normal_empty_terminals')
ok(result['signals']==[] and result['prior_live_matches']==[],'no_signals_or_prior_live_matches')
ok(0<result['elapsed']<180 and all(result[k]==0 for k in ['target_inputs','control_87_inputs','full_model_loads']),'time_and_scope')
ok(digest(B/'FREEZE.json')=='33c953e9982803aa5fe9b6bffce9d43d8b55ac43052a73604ef9211d1adc8a0a','freeze_identity')
sealed=[]
for name,want in result['file_hashes'].items():
    got=digest(A/name);sealed.append({'name':name,'sha256':got,'pass':got==want})
ok(all(x['pass'] for x in sealed),'all_sealed_artifact_hashes')
ok(all((A/(x['role']+'_stderr.txt')).stat().st_size==0 for x in result['commands']),'all_five_child_stderr_empty')
for c in result['commands']:
    ready=obj(A/(c['role']+'_ready.json'))
    ok(ready['limits']==f['limits']['small'],'limits_'+c['role'])
    ok(ready['visible_self']==c['anchor']['visible_pid'] and ready['pid_local']==c['pid_local'] and ready['pid_namespace']==c['anchor']['pid_namespace'],'identity_'+c['role'])
ref=(A/'reference_perl.jsonl').read_bytes();alt=(A/'adapted_perl.jsonl').read_bytes()
ok(ref==alt,'reference_adapted_byte_identical')
events=[json.loads(x) for x in ref.splitlines()]
old=b'/workspace/scratch/f24f8fae4976/TS_LM_PREFETCH_DIFF_v1/original/JMSmoothing.pm'
prior=(B/'evidence/lm_fixture_reference.jsonl').read_bytes()
ok(len(events)==320 and prior.count(old)==2 and prior.replace(old,str(B/'original/JMSmoothing.pm').encode())==ref,'prior_full_oracle_exact_two_path_relocations')
ok(b'\n'.join(ref.splitlines()[:300])+b'\n'==(B/'evidence/prior_reference.jsonl').read_bytes(),'prior_base_oracle')
cases={x['id']:x for x in obj(B/'fixtures/base/cases.json')['cases']};inverse_count=0
for row in events[:300]:
    if row[1] not in ['root','candidate','child','winner']:continue
    c=cases[row[0]];key,plain,positions=row[-1];alpha=c['alphabet'];cipher=c['cipher']
    assert len(key)==len(set(key))==len(alpha)
    mapping=dict(zip(alpha,key));reverse={v:k for k,v in mapping.items()}
    assert len(positions)==len(cipher)==len(plain)==6
    assert positions==[[i+1,cipher[i],plain[i],cipher[i]] for i in range(6)]
    assert all(mapping[cipher[i]]==plain[i] and reverse[plain[i]]==cipher[i] for i in range(6))
    inverse_count+=1
ok(inverse_count==118 and events[299]==['terminal','complete',{'cases':3,'score_calls':64}],'118_full_6_position_inverse_records_per_side')
ok(obj(A/'perl_negatives.json')==[[x['id'],x['error']] for x in obj(B/'negative_responses.json')],'frozen_negative_fixture_errors')
segments=obj(B/'evidence/real_segmentation.json');lists=obj(B/'evidence/real_lists.json');spec=obj(B/'real_spec.json');queries=obj(B/'real_queries.json')
real=list(lines(A/'real_perl.jsonl'));pat=[e for e in real if e.get('type')=='pat_list'];lm=[e for e in real if e.get('type')=='lm_batch'];seg=[e for e in real if e.get('type')=='segmentation'];terms=[e for e in real if 'terminal' in e]
ok((len(real),len(pat),len(lm),len(seg),len(terms))==(24,8,9,6,1),'real_event_accounting')
ok(all(e['batch']==i and e['pattern']==spec['patterns'][i] and e['values']==lists[spec['patterns'][i]] for i,e in enumerate(pat)),'all_full_candidate_lists_order_duplicates_mutation_refetch')
ok(sum(len(e['values'] or []) for e in pat)==132856,'all_132856_candidate_occurrences')
for i,e in enumerate(lm):
    expected=[]
    for j in range(spec['lm_batches'][i]):
        q=queries[j%36]['result'];expected.append([q['found'],q['value_hex'],q['last_row_1based']])
    assert e['batch']==i and e['lookups']==len(expected) and e['results']==expected
ok(sum(e['lookups'] for e in lm)==6244,'all_6244_raw_LM_responses')
ok(seg==[{'type':'segmentation','input':s['input'],'output':s['output']} for s in segments],'six_segmentation_outputs')
rt=terms[0];ok(rt['terminal']=='COMPLETE_COMBINED_TRANSPORT' and rt['score_calls']==rt['search_calls']==0 and 0<=rt['lm_seconds']<=10 and 0<=rt['seconds']<=30,'real_terminal_no_search_time_bounds')
ipc_result={}
for role,expect in [('adapted_broker',{'lm':(158,158),'pat':(1495,1925)}),('real_broker',{'lm':(10,58),'pat':(45,2131)})]:
    channels={c:{'requests':0,'frames':0,'response_bytes':0,'max_frame':0,'pending':None,'offset':0,'list':None,'closed':False} for c in ['lm','pat']};wordtrace=[];orders=[];completed_lists=[]
    for event in lines(A/(role+'_ipc.jsonl')):
        channel=event['channel'];s=channels[channel]
        if 'request' in event:
            q=event['request'];assert s['pending'] is None and not s['closed'];s['requests']+=1;assert q[0]==s['requests'];s['pending']=q;s['offset']=0;s['list']=None;orders.append(channel)
        else:
            q=s['pending'];v=event['response'];assert q is not None and v[0]==q[0];s['frames']+=1
            size=len((json.dumps(v,separators=(',',':'),ensure_ascii=True)+'\n').encode());assert size<=65536;s['max_frame']=max(s['max_frame'],size);s['response_bytes']+=size
            done=False
            if channel=='lm':
                assert v[1]==s['offset'] and len(v[2])<=128;s['offset']+=len(v[2]);assert s['offset']<=len(q[2]);done=v[3]
                if done:assert s['offset']==len(q[2])
            elif v[1]=='value':
                assert len(v)==3;done=True
                if q[1]=='word':wordtrace.append([q[2],bool(v[2])])
                if q[1]=='list' and role=='real_broker':assert v[2]==lists[q[2]]
            elif v[1]=='begin':
                assert q[1]=='list' and s['list'] is None and 0<=v[2]<=63911;s['list']=[];s['declared']=v[2]
            elif v[1]=='chunk':
                assert s['list'] is not None and v[2]==len(s['list']) and 0<len(v[3])<=64;s['list'].extend(v[3]);assert len(s['list'])<=s['declared']
            else:
                assert v[1]=='end' and s['list'] is not None and len(s['list'])==s['declared']==v[2] and sum(len(w.encode('ascii')) for w in s['list'])==v[3]
                if role=='real_broker':assert s['list']==lists[q[2]]
                completed_lists.append((q[2],len(s['list'])));done=True
            if done:
                if q[1]=='close':s['closed']=True
                s['pending']=None
    terminal=obj(A/(role+'_terminal.json'))
    for ch,s in channels.items():
        assert (s['requests'],s['frames'])==expect[ch] and s['closed'] and s['pending'] is None
        for k in ['requests','response_frames','response_bytes','max_frame']:
            assert terminal[ch][k]==s[{'response_frames':'frames'}.get(k,k)]
    assert terminal['both_closed'] and sum(a!=b for a,b in zip(orders,orders[1:]))>=4
    if role=='real_broker':assert wordtrace==[x for s in segments for x in s['membership_trace']]
    else:assert len(wordtrace)==1211
    ipc_result[role]={'channels':{c:{k:s[k] for k in ['requests','frames','response_bytes','max_frame','closed']} for c,s in channels.items()},'word_queries':len(wordtrace),'channel_switches':sum(a!=b for a,b in zip(orders,orders[1:])),'list_completions':len(completed_lists)}
ok(True,'complete_independent_dual_channel_IPC_readback')
obs=list(lines(A/'observations.jsonl'));peaks={};cg=[];maxchildren=0
for row in obs:
    cg.append(int(row['memory']['memory.current']));maxchildren=max(maxchildren,sum(len(g) for g in row['groups'].values()))
    for role,group in row['groups'].items():
        for p in group:
            dst=peaks.setdefault(role,{})
            for line in p['memory_status']:
                k,v=line.split(':',1);dst[k]=max(dst.get(k,0),int(v.split()[0]))
ok(maxchildren<=2 and max(cg)<7516192768,'observed_process_and_shared_memory_bounds')
events_before=dict(x.split() for x in result['before']['memory.events'].splitlines());events_after=dict(x.split() for x in result['after']['memory.events'].splitlines())
ok(all(events_before[k]==events_after[k] for k in ['oom','oom_kill','oom_group_kill']),'no_recorded_OOM_growth')
# Independent live read: PID/starttime and visible process-group checks, no signals or executable imports.
anchors=[x['anchor'] for x in result['commands']];post=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:
        st=(p/'stat').read_text().rsplit(')',1)[1].split();pid=int(p.name);pgid=int(st[2]);starttime=int(st[19])
        if any(pgid==a['visible_pgid'] or (pid==a['visible_pid'] and starttime==a['starttime']) for a in anchors):
            post.append({'visible_pid':pid,'visible_pgid':pgid,'starttime':starttime,'state':st[0]})
    except (FileNotFoundError,ProcessLookupError):pass
ok(post==[],'independent_post_terminal_no_anchor_or_group')
manifest=obj(B/'PACKAGE_MANIFEST.json');ok(all(digest(B/x['path'])==x['sha256'] and (B/x['path']).stat().st_size==x['bytes'] for x in manifest['files']),'frozen_package_unchanged')
summary={'status':'PASS_INDEPENDENT_SAVED_DATA_READBACK','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'sealed_files':sealed,'fixture_events':len(events),'inverse_records_per_side':inverse_count,'positions_per_record':6,'fixture_trace_sha256':hashlib.sha256(ref).hexdigest(),'real_lookups':6244,'real_candidate_occurrences':132856,'segmentations':6,'ipc':ipc_result,'observed_peaks_KiB':peaks,'cgroup_sample_min':min(cg),'cgroup_sample_max':max(cg),'observation_samples':len(obs),'max_observed_children':maxchildren,'post_terminal_matches':post,'scope':'Saved bytes/keys/positions/receipts only; no model reread, no scoring/search, no study imports. Post /proc is independent, momentary evidence; not a host-crash guarantee.','elapsed_seconds':time.monotonic()-start}
with (E/'INDEPENDENT_READBACK.json').open('x') as h:json.dump(summary,h,indent=2);h.write('\n')
print(json.dumps({k:summary[k] for k in ['status','fixture_events','inverse_records_per_side','real_lookups','real_candidate_occurrences','segmentations','observed_peaks_KiB','cgroup_sample_max','post_terminal_matches','elapsed_seconds']},indent=2))
print('CHECKS',len(checks),'ALL_PASS',all(x['pass'] for x in checks))
