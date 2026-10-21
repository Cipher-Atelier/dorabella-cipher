"""Saved traces only. No solver, scorer, transport or model imports."""
from pathlib import Path
import json,hashlib
B=Path(__file__).resolve().parent;A=B/'attempt'
def need(x,m):
    if not x:raise RuntimeError('READBACK_'+m)
def load(p):return json.loads(p.read_text())
def rows(p):return [json.loads(s) for s in p.read_bytes().splitlines()]
def iter_rows(p):
    with p.open('rb') as handle:
        for raw in handle:
            need(len(raw)<=8388608,'ROW_BYTES');yield json.loads(raw)
def ipc(role,expected_lm,expected_pat):
    terminal=load(A/(role+'_terminal.json'));need(terminal['both_closed'],'BOTH_CLOSE')
    state={c:{'seq':0,'req':None,'done':True,'offset':0,'payload':0,'frames':0,'count':None} for c in ('lm','pat')}
    order=[];word_trace=[]
    for event in iter_rows(A/(role+'_ipc.jsonl')):
        channel=event['channel'];need(channel in state,'CHANNEL');v=state[channel]
        if 'request' in event:
            need(v['done'] and (v['req'] is None or v['req'][1]!='close'),'REQUEST_AFTER_PENDING_OR_CLOSE')
            req=event['request'];v['seq']+=1;need(req[0]==v['seq'],'SEQ')
            v.update(req=req,done=False,offset=0,payload=0,count=None);order.append(channel)
        else:
            x=event['response'];need(not v['done'] and x[0]==v['seq'],'RESPONSE_ID');v['frames']+=1
            if channel=='lm':
                need(x[1]==v['offset'] and len(x[2])<=128,'LM_FRAME');v['offset']+=len(x[2])
                need(v['offset']<=len(v['req'][2]),'LM_COUNT');v['done']=x[3]
                need(not v['done'] or v['offset']==len(v['req'][2]),'LM_FINAL')
            elif x[1]=='value':
                need(len(x)==3 and v['count'] is None,'PAT_VALUE');v['done']=True
                if v['req'][1]=='word':word_trace.append([v['req'][2],bool(x[2])])
            elif x[1]=='begin':
                need(v['req'][1]=='list' and v['count'] is None and 0<=x[2]<=63911,'PAT_BEGIN');v['count']=x[2]
            elif x[1]=='chunk':
                need(v['count'] is not None and x[2]==v['offset'] and 0<len(x[3])<=64,'PAT_CHUNK')
                v['offset']+=len(x[3]);v['payload']+=sum(len(y.encode('ascii')) for y in x[3]);need(v['offset']<=v['count'],'PAT_OVERFLOW')
            else:
                need(x[1]=='end' and v['count'] is not None and x[2:]==[v['count'],v['payload']] and v['offset']==v['count'],'PAT_END');v['done']=True
    counts={}
    for channel,expected in [('lm',expected_lm),('pat',expected_pat)]:
        v=state[channel];t=terminal[channel]
        need(v['seq']==expected and v['done'] and v['req'][1]=='close','FINAL_CLOSE')
        need(t['requests']==expected and t['response_frames']==v['frames'] and t['closed'] and t['max_frame']<=65536,'CHANNEL_TERMINAL')
        counts[channel]={'requests':expected,'response_frames':v['frames']}
    need(order[0]=='pat' and 'lm' in order and sum(a!=b for a,b in zip(order,order[1:]))>=4,'INTERLEAVING')
    return terminal,word_trace,counts
def fixture():
    ref=(A/'reference_perl.jsonl').read_bytes();alt=(A/'adapted_perl.jsonl').read_bytes();need(ref==alt,'EXACT_TRACE')
    es=[json.loads(s) for s in ref.splitlines()];need(len(es)==320,'EVENTS')
    need(b'\n'.join(ref.splitlines()[:300])+b'\n'==(B/'evidence/prior_reference.jsonl').read_bytes(),'PRIOR_BASE')
    # Only relocation of the error's absolute source pathname is allowed in saved oracle.
    prior=(B/'evidence/lm_fixture_reference.jsonl').read_bytes()
    old=b'/workspace/scratch/f24f8fae4976/TS_LM_PREFETCH_DIFF_v1/original/JMSmoothing.pm'
    need(prior.count(old)==2,'EXACT_TWO_ERROR_LOCATORS')
    need(prior.replace(old,str(B/'original/JMSmoothing.pm').encode())==ref,'PRIOR_FULL_RELOCATED')
    spec=load(B/'fixtures/base/cases.json');cases={x['id']:x for x in spec['cases']};n=0
    for event in es[:300]:
        if event[1] in ('root','candidate','child','winner'):
            key,plain,pos=event[-1];c=cases[event[0]];alpha=c['alphabet'];cipher=c['cipher'];n+=1
            need(len(pos)==len(plain)==6 and len(key)==len(alpha)==len(set(key)),'INVERSE_SHAPE')
            for i,p in enumerate(pos):
                need(p==[i+1,cipher[i],plain[i],cipher[i]] and key[alpha.index(cipher[i])]==plain[i] and alpha[key.index(plain[i])]==cipher[i],'INVERSE_POSITION')
    need(n==118 and es[299]==['terminal','complete',{'cases':3,'score_calls':64}],'ACCOUNTING')
    neg=load(A/'perl_negatives.json');need(neg==[[x['id'],x['error']] for x in load(B/'negative_responses.json')],'NEGATIVES')
    terminal,words,counts=ipc('adapted_broker',158,1495)
    need(terminal['lm']['lookups']==2098 and terminal['lm']['response_frames']==158,'LM_FIXTURE')
    need(terminal['pat']['response_frames']==1925 and len(words)==1211,'PAT_FIXTURE')
    return {'status':'PASS_FINITE_COMBINED_DIFFERENTIAL','events':320,'inverse_records':n,'positions_each':6,'score_bits_tolerance':0,'trace_sha256':hashlib.sha256(ref).hexdigest(),'ipc':counts}
def real():
    spec=load(B/'real_spec.json');qs=load(B/'real_queries.json');lists=load(B/'evidence/real_lists.json');segments=load(B/'evidence/real_segmentation.json')
    nl=nm=ns=total=0;last=None
    for e in iter_rows(A/'real_perl.jsonl'):
        total+=1;kind=e.get('type')
        if kind=='pat_list':
            need(nl<8 and e['batch']==nl and e['pattern']==spec['patterns'][nl] and e['values']==lists[e['pattern']],'REAL_LIST_BYTES_ORDER_DUPLICATES');nl+=1
        elif kind=='lm_batch':
            need(nm<9,'LM_BATCH_BOUND');n=spec['lm_batches'][nm];expect=[]
            for j in range(n):
                x=qs[j%36]['result'];expect.append([x['found'],x['value_hex'],x['last_row_1based']])
            need(e['batch']==nm and e['lookups']==n and e['results']==expect,'REAL_LM_BYTES');nm+=1
        elif kind=='segmentation':
            need(ns<6 and e=={'type':'segmentation','input':segments[ns]['input'],'output':segments[ns]['output']},'REAL_SEGMENTATION');ns+=1
        else:need(last is None,'SECOND_TERMINAL');last=e
    need((total,nl,nm,ns)==(24,8,9,6),'REAL_EVENT_COUNTS');lists=None
    expected_words=[item for s in segments for item in s['membership_trace']]
    terminal,words,counts=ipc('real_broker',10,10+len(expected_words))
    need(words==expected_words,'REAL_MEMBERSHIP_ORDER')
    need(terminal['lm']['lookups']==6244 and terminal['lm']['response_frames']==58,'REAL_LM_ACCOUNTING')
    need(terminal['pat']['candidate_occurrences']==132856 and terminal['pat']['max_list_count']==63911,'REAL_PAT_ACCOUNTING')
    need(last['terminal']=='COMPLETE_COMBINED_TRANSPORT' and last['lookups']==6244 and last['list_fetches']==8 and last['segmentations']==6 and last['lm_requests']==10,'REAL_TERMINAL')
    need(last['score_calls']==last['search_calls']==0 and 0<=last['lm_seconds']<=10 and 0<=last['seconds']<=30,'REAL_LIMITS')
    return {'status':'PASS_FINITE_COMBINED_TRANSPORT','lm_lookups':6244,'list_fetches':8,'candidates':132856,'segmentations':6,'lm_seconds':last['lm_seconds'],'seconds':last['seconds'],'ipc':counts,'scope':'No real scoring/search/87-control. Finite repeated-key transport; not full-search speed.'}
