"""One saved-data audit. Does not import/execute experiment code or recompute scores."""
from pathlib import Path
import json, hashlib, datetime, os, collections
B=Path('/workspace/scratch/f24f8fae4976/TS_LM_PREFETCH_DIFF_v1')
A=B/'attempt'; E=B.parent/'TS_LM_PREFETCH_DIFF_v1_execution_evidence'
def j(p): return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for q in iter(lambda:f.read(1048576),b''): h.update(q)
    return h.hexdigest()
checks={}
def check(label, value): checks[label]=bool(value)
r=j(A/'result.json'); f=j(B/'FREEZE.json'); receipt=j(E/'raw_execution_receipt.json')
check('tool_exit0_no_session', receipt['result']['exit_code']==0 and 'session_id' not in receipt['result'])
check('tool_stdout_status',j(E/'raw_execution_receipt.json')['result']['output']==json.dumps({k:r.get(k) for k in ('status','elapsed','terminal_confirmed','stages','error')})+'\n')
check('all_recorded_attempt_hashes',all(sha(A/n)==h for n,h in r['file_hashes'].items()))
check('frozen_code_runtime_identities',all(sha(Path(e['path']) if e['external'] else B/e['path'])==e['sha256'] for e in f['identities']))
check('freeze_unchanged',sha(B/'FREEZE.json')=='7009da08780275e7a917e6712098294f87035a40cceeb65fe2a388fb20ec6d86')
check('zip_unchanged',sha(B.parent/'Dorabella_TS_LM_PREFETCH_DIFF_v1_20261018_package.zip')=='5a7fbbc2465a7e6d4433fd3ea2a44eb8545f871b4e3c07807d26af7c4cabd81e')
ref=(A/'reference_perl.jsonl').read_bytes(); alt=(A/'adapted_perl.jsonl').read_bytes()
ev=[json.loads(s) for s in ref.splitlines()]
check('full_320_events_byte_equal',len(ev)==320 and ref==alt)
check('prior_300_events_byte_equal',b'\n'.join(ref.splitlines()[:300])+b'\n'==(B/'evidence/prior_reference.jsonl').read_bytes())
base=j(B/'fixtures/base/cases.json'); edge=j(B/'fixtures/edge/cases.json')
case={c['id']:c for c in base['cases']}; inv=[]
for n,e in enumerate(ev[:300],1):
    if e[1] not in ('root','winner','candidate','child'):continue
    key,plain,pos=e[-1]; c=case[e[0]]; alpha=c['alphabet']; cipher=c['cipher']
    good=len(pos)==len(plain)==6 and len(key)==len(alpha) and len(set(key))==len(key)
    for i,p in enumerate(pos):
        good=good and p[0]==i+1 and p[1]==cipher[i] and p[2]==plain[i] and p[3]==cipher[i] and key[alpha.index(cipher[i])]==plain[i] and alpha[key.index(plain[i])]==cipher[i]
    inv.append({'event_1based':n,'case':e[0],'kind':e[1],'ok':good})
check('every_saved_inverse_key_and_all_positions',bool(inv) and all(x['ok'] for x in inv))
check('roots_and_winners',all([e[0] for e in ev if e[1]==kind]==['C1','C2','C3'] for kind in ('root','winner')))
check('base_accounting',ev[299]==['terminal','complete',{'cases':3,'score_calls':64}])
check('candidate_lists_order_duplicates',[(e[2],e[3]) for e in ev if e[:2]==['prelude','list']]==list(base['expected_groups'].items()))
raw=[e for e in ev if e[:2]==['edge','raw']]
check('raw_values_and_truth', [e[2] for e in raw]==edge['raw_keys'] and [e[4] for e in raw]==edge['expected_raw'] and [e[5] for e in raw]==edge['expected_truth'])
check('zero_bits',all(e[6]=='0000000000000000' for e in raw[:3]))
check('unknown_replacement',['edge','unknown',edge['expected_unknown']] in ev)
probes=[e for e in ev if e[:2]==['edge','probe']]
check('exact_error_cases_no_warnings',len(probes)==11 and [e[3] for e in probes]==edge['score_probes'] and [e[2] for e in probes if e[4] is None]==[3,4] and all(not e[-1] for e in probes))
check('ties_preserve_input_order',[e[3:] for e in ev if e[:2]==['edge','tie']]==[[['first','second'],['second','first']]])
negative=j(A/'perl_negatives.json'); spec=j(B/'negative_responses.json')
check('all_11_negative_rejections',negative==[[x['id'],x['error']] for x in spec] and len(negative)==11)
logs=[json.loads(s) for s in (A/'adapted_broker_ipc.jsonl').read_bytes().splitlines()]
request=None; seq=0; frames=0; lookups=0; offset=0; done=True; wire_ok=True
for e in logs:
    if 'request' in e:
        wire_ok=wire_ok and done; request=e['request'];seq+=1;offset=0;done=False
        wire_ok=wire_ok and request[0]==seq and len(request[2])<=776;lookups+=len(request[2])
    else:
        x=e['response'];frames+=1
        wire_ok=wire_ok and not done and x[0]==seq and x[1]==offset and len(x[2])<=128
        offset+=len(x[2]);done=x[3]
        wire_ok=wire_ok and offset<=len(request[2]) and (not done or offset==len(request[2]))
check('full_ipc_accounting',wire_ok and done and request[1:]==['close',[]] and (seq,frames,lookups)==(158,158,2098))
check('broker_explicit_close',j(A/'adapted_broker_terminal.json')['closed'] is True)
roles=['reference_perl','adapted_broker','adapted_perl']
check('only_three_authorized_child_invocations',[c['role'] for c in r['commands']]==roles)
check('limits_ready_evidence',all(j(A/(role+'_ready.json'))['limits']==f['limits']['small'] for role in roles))
check('exit_and_groups',r['terminal_confirmed'] and r['terminal']==[{'role':role,'exit':0,'group':[]} for role in roles] and r['signals']==[])
check('empty_stderr',all((A/(role+'_stderr.txt')).read_bytes()==b'' for role in roles))
check('wall_inside_plan',0<=r['elapsed']<180)
check('no_oom_delta',r['before']['memory.events']==r['after']['memory.events'] and 'oom 0' in r['after']['memory.events'])
rc=f['resource']; cur=int(r['stages']['real']['observed']['memory.current']); projected=cur+rc['all_input_page_bytes']+rc['process_AS_sum']+rc['allowance']
check('skip_exact_frozen_formula',r['stages']['real']['status']=='SKIPPED_RESOURCE' and r['stages']['real']['phase']=='PRE_HASH' and projected>=rc['shared_abort'])
check('no_real_artifacts_or_scope_expansion',not list(A.glob('real_*')) and r['target_inputs']==r['control_87_inputs']==r['full_model_loads']==0)
terminal=[]
for row in [r['namespace_self']]+[c['anchor'] for c in r['commands']]:
    p=Path('/proc')/str(row['visible_pid']); exists=p.exists(); current=None
    if exists:
        try:current=int((p/'stat').read_text().rsplit(')',1)[1].split()[19])
        except (FileNotFoundError,ProcessLookupError):exists=False
    terminal.append({'visible_pid':row['visible_pid'],'saved_starttime':row['starttime'],'proc_exists':exists,'current_starttime':current,'old_identity_absent':not exists or current!=row['starttime']})
check('independent_proc_identities_gone',all(x['old_identity_absent'] for x in terminal))
result={'status':'PASS_SAVED_DATA_READBACK' if all(checks.values()) else 'READBACK_DISCREPANCY','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'inverse_records_per_trace':len(inv),'inverse_positions_per_trace':6*len(inv),'inverse_details':inv,'terminal_reinspection':terminal,'real_gate':{'current':cur,'projected':projected,'threshold':rc['shared_abort'],'excess_bytes':projected-rc['shared_abort'],'strict_current_required_below':rc['shared_abort']-rc['all_input_page_bytes']-rc['process_AS_sum']-rc['allowance']},'result_sha256':sha(A/'result.json'),'raw_receipt_sha256':sha(E/'raw_execution_receipt.json'),'scope':'Saved bytes/keys/positions only; no scoring, solver, IPC, model load or rerun.'}
(E/'independent_readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='inverse_details'},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
