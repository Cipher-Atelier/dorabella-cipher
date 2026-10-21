"""Saved-data checks only; no original code, scoring or adapter execution."""
from pathlib import Path
import json,hashlib
B=Path(__file__).resolve().parent;A=B/'attempt'
def need(x,m):
 if not x:raise RuntimeError('READBACK_'+m)
def rows(p):return [json.loads(x) for x in p.read_bytes().splitlines()]
def broker(role,requests):
 t=json.loads((A/(role+'_terminal.json')).read_text());need(t['closed'] is True and t['requests']==requests,'BROKER_TERMINAL')
 log=rows(A/(role+'_ipc.jsonl'));seq=0;frames=0;pending=None;offset=0;done=True
 for e in log:
  if 'request' in e:
   need(done,'MISSING_FINAL');seq+=1;pending=e['request'];need(pending[0]==seq,'SEQ');offset=0;done=False
  else:
   x=e['response'];need(not done and x[0]==seq and x[1]==offset,'RESPONSE_ORDER');offset+=len(x[2]);done=x[3];frames+=1
   need(offset<=len(pending[2]),'COUNT');need(not done or offset==len(pending[2]),'FINAL_COUNT')
 need(done and pending[1:] == ['close',[]] and seq==requests and frames==t['response_frames'],'CLOSE_ACCOUNTING')
 need(t['max_frame']<=65536 and t['lookups']<=20000,'BOUNDS');return t
def fixture():
 ref=(A/'reference_perl.jsonl').read_bytes();adapt=(A/'adapted_perl.jsonl').read_bytes();need(ref==adapt,'FULL_TRACE_BYTES')
 events=[json.loads(s) for s in ref.splitlines()];need(len(events)==320,'EVENT_COUNT')
 prior=(B/'evidence/prior_reference.jsonl').read_bytes();need(b'\n'.join(ref.splitlines()[:300])+b'\n'==prior,'UNCHANGED_BASE_REFERENCE')
 need(events[299]==['terminal','complete',{'cases':3,'score_calls':64}],'BASE_ACCOUNTING')
 need(events[-1]==['edge','complete',{'raw':5,'unknown':1,'score_probes':11,'expected_log_zero':2,'missing':2,'ties':1}],'EDGE_ACCOUNTING')
 roots=[];wins=[]
 for e in events[:300]:
  if e[1] in ('root','winner','candidate','child'):
   key,plain,pos=e[-1];need(len(pos)==6 and [p[0] for p in pos]==list(range(1,7)) and all(p[1]==p[3] for p in pos),'ROUNDTRIP')
   if e[1]=='root':roots.append(e[0])
   if e[1]=='winner':wins.append(e[0])
 need(roots==wins==['C1','C2','C3'],'THREE_CASES')
 edge=json.loads((B/'fixtures/edge/cases.json').read_text());probes=[e for e in events if e[0]=='edge' and e[1]=='probe']
 need([e[2] for e in probes if e[4] is None]==edge['expected_error_indices'],'EXACT_ERRORS')
 need(all(not e[-1] for e in probes),'UNEXPECTED_WARNINGS')
 neg=json.loads((A/'perl_negatives.json').read_text());spec=json.loads((B/'negative_responses.json').read_text())
 need(neg==[[x['id'],x['error']] for x in spec],'PERL_NEGATIVES')
 return {'status':'PASS_FINITE_DIFFERENTIAL_ONLY','events':320,'base_score_calls':64,'edge_combined_scores':11,'tie_scores':2,'expected_log_errors':2,'perl_negative_cases':len(neg),'trace_sha256':hashlib.sha256(ref).hexdigest(),'broker':broker('adapted_broker',158)}
def real():
 es=rows(A/'real_perl.jsonl');qs=json.loads((B/'real_queries.json').read_text());need(len(es)==10,'REAL_EVENTS')
 for i,e in enumerate(es[:9]):
  n=36 if i==0 else 776;expect=[]
  for j in range(n):
   r=qs[j%36]['result'];expect.append([r['found'],r['value_hex'],r['last_row_1based']])
  need(e['batch']==i and e['lookups']==n and e['results']==expect and e['ipc_seconds']>=0,'REAL_VALUES')
 end=es[-1];need(end['terminal']=='COMPLETE_BYTE_IPC' and end['lookups']==6244 and end['requests']==10 and end['score_calls']==end['search_calls']==0 and 0<=end['seconds']<=10,'REAL_TERMINAL')
 return {'status':'PASS_FINITE_REAL_BYTE_IPC','lookups':6244,'distinct_keys':35,'batches':9,'seconds':end['seconds'],'broker':broker('real_broker',10),'scope':'Initial application-cache misses plus repeated hot queries, not cold filesystem or full-search speed.'}
