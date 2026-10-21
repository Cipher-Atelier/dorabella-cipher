"""Independent own saved-data readback only; never imports or re-executes runner."""
from pathlib import Path
import json,hashlib,zipfile,time,resource
resource.setrlimit(resource.RLIMIT_AS,(67108864,67108864));resource.setrlimit(resource.RLIMIT_CPU,(5,6))
S=time.monotonic();P=Path(__file__).resolve().parent;A=P.parent/'ARTIFACT_INTEGRITY_PROBE_v1'
def H(b):return hashlib.sha256(b).hexdigest()
def need(x,s):
 if not x:raise RuntimeError(s)
 if time.monotonic()-S>10:raise RuntimeError('READBACK_DEADLINE')
def R(p):need(p.stat().st_size<=65536,'FILE_BOUND');return p.read_bytes()
try:
 freeze=json.loads(R(P/'FREEZE.json'));raw=json.loads(R(P/'RAW_TOOL_RECEIPT.json'));obs=raw['observations']
 need(raw['attempt_launches']==1 and obs[-1]['response'].get('exit_code')==0,'ONE_CALL_EXIT0')
 ids={x['response'].get('session_id',x.get('session_id')) for x in obs};ids.discard(None);need(len(ids)<=1,'SAME_SESSION')
 stdout=''.join(x['response']['output'] for x in obs).encode('utf8');rows=stdout.splitlines(keepends=True);need(len(rows)==2,'TWO_PRIMARY_OUTPUT_RECORDS')
 receipt,terminal=[json.loads(x) for x in rows];need(receipt['event']=='HASH_RECEIPT' and terminal['event']=='TERMINAL','RAW_RECORD_ORDER')
 need(terminal['status']=='PASS_CANDIDATE_LOCAL_ARTIFACT_ONLY' and terminal['child_exit']==0 and terminal['child_reaped'] and 0<=terminal['elapsed']<10,'TERMINAL')
 need(rows[0]==R(A/'result.json') and rows[1]==R(A/'terminal.json'),'RAW_STDOUT_EXACT_RESULT_BYTES')
 expected=bytes.fromhex(freeze['payload_hex']);altered=bytes.fromhex(freeze['altered_hex'])
 good=R(A/'payload.jsonl');bad=R(A/'altered.jsonl');need(good==expected and bad==altered and len(good)==len(bad)==48,'EXACT_FIXTURES')
 need([i for i in range(48) if good[i]!=bad[i]]==[12] and good[12]==65 and bad[12]==68,'ONE_FIXED_MUTATION')
 need(receipt['expected_hex']==freeze['payload_hex'] and receipt['altered_hex']==freeze['altered_hex'],'RAW_BYTES_BINDING')
 need(receipt['positive_exact_bytes'] and receipt['negative_rejected'] and receipt['negative_difference_offsets_0based']==[12] and H(good)!=H(bad),'NEGATIVE_REJECTED')
 need(receipt['freeze_sha256']==H(R(P/'FREEZE.json')),'FREEZE')
 gnu=receipt['gnu'];need(gnu['exit_code']==0 and gnu['terminal_reaped'] and gnu['invocations']==1 and gnu['stderr']=='' and 0<=gnu['end_monotonic']-gnu['start_monotonic']<=2,'GNU_TERMINAL')
 expected_stdout=(H(good)+'  payload.jsonl\n'+H(bad)+'  altered.jsonl\n').encode('ascii')
 need(gnu['stdout'].encode()==R(A/'gnu_stdout.txt')==expected_stdout and R(A/'gnu_stderr.txt')==b'','GNU_HASHES')
 for w,b in zip(receipt['writers'],(good,bad)):
  need(w['intent_sha256']==w['closed_reader_sha256']==H(b) and w['EOF'] and w['bytes']==48,'WRITER_HASHES')
  need(w['reader_before']==w['reader_after']==w['path_after'] and w['reader_after']['st_size']==48,'FILE_IDENTITIES')
  need(w['closed_monotonic']<=w['read_finished_monotonic']<=gnu['start_monotonic']<=gnu['end_monotonic']<=receipt['receipt_emit_monotonic'],'WRITE_CLOSE_HASH_STDOUT_ORDER')
  need(sum(x['write_return'] for x in w['writes'])==48 and all(x['bytes']==x['write_return'] for x in w['writes']),'WRITE_COUNTS')
 need(len(receipt['writers'][0]['writes'])==3,'THREE_WRITES')
 for name,h in terminal['file_hashes'].items():need(H(R(A/name))==h,'ARTIFACT_HASH:'+name)
 with zipfile.ZipFile(A/'artifact.zip') as z:
  need(z.namelist()==['payload.jsonl','altered.jsonl','result.json'] and z.testzip() is None,'ZIP')
  for n in z.namelist():need(z.read(n)==R(A/n),'ZIP_BYTES:'+n)
 need(not (A/'STOP.json').exists(),'NO_STOP')
 for e in freeze['identities']:
  if e['role']=='own_code':need(H(R(Path(e['path'])))==e['sha256'],'OWN_CODE_UNCHANGED')
 out={'status':'PASS_LOCAL_ARTIFACT_ONLY','attempts':1,'exact_payload_bytes':48,'negative_rejected':True,'gnu_exit':0,'runner_exit':0,'attempt_elapsed':terminal['elapsed'],'payload_sha256':H(good),'altered_sha256':H(bad),'result_sha256':H(R(A/'result.json')),'artifact_zip_sha256':H(R(A/'artifact.zip')),'primary_stdout_sha256':H(stdout),'raw_stdout_result_exact':True,'historical_7523_not_explained':True,'old_STOPs_unchanged':True}
except BaseException as e:out={'status':'STOP_INDEPENDENT_READBACK','error':repr(e),'no_retry':True}
out['readback_elapsed']=time.monotonic()-S
with (P/'READBACK.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out));raise SystemExit(0 if out['status']=='PASS_LOCAL_ARTIFACT_ONLY' else 2)
