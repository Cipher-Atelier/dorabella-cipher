"""Own 48-byte local integrity probe. Standard library plus one pinned GNU sha256sum.
No study code, model, network, threads, retry, resume or background work.
"""
import time
T0=time.monotonic()
import resource
resource.setrlimit(resource.RLIMIT_AS,(67108864,67108864))
resource.setrlimit(resource.RLIMIT_CPU,(5,6))
resource.setrlimit(resource.RLIMIT_FSIZE,(65536,65536))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
from pathlib import Path
import os,sys,json,hashlib,datetime,subprocess,zipfile
P=Path(__file__).resolve().parent
A=P.parent/'ARTIFACT_INTEGRITY_PROBE_v1'
EXPECTED=b'{"i":0,"v":"A"}\n{"i":1,"v":"B"}\n{"i":2,"v":"C"}\n'
ALTERED=EXPECTED[:12]+b'D'+EXPECTED[13:]
output_bytes=0
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(ok,why):
 if not ok:raise RuntimeError(why)
def tick():
 need(time.monotonic()-T0<10,'DEADLINE')
 if A.exists():
  sizes=[p.stat().st_size for p in A.iterdir() if p.is_file()]
  need(all(n<=65536 for n in sizes) and sum(sizes)+output_bytes<=262144,'OUTPUT_BOUND')
def H(b):return hashlib.sha256(b).hexdigest()
def hash_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b);tick()
 return h.hexdigest()
def enc(x):return (json.dumps(x,separators=(',',':'),sort_keys=True)+'\n').encode('ascii')
def emit(b):
 global output_bytes
 need(len(b)<=65536 and output_bytes+len(b)<=65536,'STDOUT_BOUND')
 n=sys.stdout.buffer.write(b);need(n==len(b),'STDOUT_SHORT_WRITE');sys.stdout.buffer.flush();output_bytes+=n
def write_new(name,b):
 need(len(b)<=65536,'FILE_BOUND')
 with (A/name).open('xb') as f:need(f.write(b)==len(b),'SHORT_WRITE');f.flush()
 tick()
def st(s):return {k:getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')}
def write_fixture(name,b,split):
 tick();p=A/name;events=[]
 with p.open('xb') as f:
  initial=st(os.fstat(f.fileno()))
  for chunk in (b.splitlines(keepends=True) if split else [b]):
   begin=time.monotonic();n=f.write(chunk);need(n==len(chunk),'FIXTURE_SHORT_WRITE');f.flush()
   events.append({'bytes':len(chunk),'write_return':n,'write_begin_monotonic':begin,'flushed_monotonic':time.monotonic(),'fd':st(os.fstat(f.fileno()))})
 closed=time.monotonic();before=st(p.stat());fd=os.open(p,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
 try:
  reader_before=st(os.fstat(fd));data=os.read(fd,65536);eof=os.read(fd,1)==b'';reader_after=st(os.fstat(fd))
 finally:os.close(fd)
 after=st(p.stat());need(eof and before==reader_before==reader_after==after and data==b,'CLOSED_READ_MISMATCH')
 return data,{'name':name,'path':str(p),'initial':initial,'writes':events,'closed_monotonic':closed,'read_finished_monotonic':time.monotonic(),'reader_before':reader_before,'reader_after':reader_after,'path_after':after,'EOF':eof,'bytes':len(data),'intent_sha256':H(b),'closed_reader_sha256':H(data)}
def main():
 child=None;child_exit=None;created=False;start_utc=utc()
 try:
  need(not A.exists(),'REFUSE_EXISTING_ATTEMPT');A.mkdir();created=True
  write_new('T0.json',enc({'utc':start_utc,'monotonic':T0,'deadline':T0+10}))
  fraw=(P/'FREEZE.json').read_bytes();f=json.loads(fraw);tick()
  need(sys.executable==f['python'] and list(sys.version_info[:3])==f['python_version'],'PYTHON_IDENTITY')
  need(len(EXPECTED)==len(ALTERED)==48 and EXPECTED[12:13]==b'A' and EXPECTED.hex()==f['payload_hex'] and ALTERED.hex()==f['altered_hex'],'FIXED_BYTES')
  for e in f['identities']:
   p=Path(e['path']);need(p.stat().st_size==e['bytes'] and hash_file(p)==e['sha256'],'IDENTITY:'+str(p))
  good,gr=write_fixture('payload.jsonl',EXPECTED,True)
  bad,br=write_fixture('altered.jsonl',ALTERED,False)
  argv=[f['sha256sum'],'--','payload.jsonl','altered.jsonl'];tick();child_start=time.monotonic()
  child=subprocess.Popen(argv,cwd=A,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,close_fds=True,env={'PATH':'/usr/bin:/bin','LC_ALL':'C','TZ':'UTC'})
  try:out,err=child.communicate(timeout=min(2,max(.001,10-(time.monotonic()-T0))))
  except subprocess.TimeoutExpired:
   child.kill()
   try:out,err=child.communicate(timeout=1)
   except subprocess.TimeoutExpired:raise RuntimeError('UNKNOWN_CHILD_TERMINATION')
   child_exit=child.returncode;write_new('gnu_stdout.txt',out);write_new('gnu_stderr.txt',err);raise RuntimeError('GNU_TIMEOUT')
  child_exit=child.returncode;child_end=time.monotonic();tick()
  write_new('gnu_stdout.txt',out);write_new('gnu_stderr.txt',err)
  need(child_exit==0 and not err and len(out)<=4096,'GNU_EXIT_OUTPUT')
  expected_output=(H(good)+'  payload.jsonl\n'+H(bad)+'  altered.jsonl\n').encode('ascii')
  need(out==expected_output,'INDEPENDENT_HASH_MISMATCH')
  differences=[i for i,(a,b) in enumerate(zip(good,bad)) if a!=b]
  negative_rejected=(bad!=EXPECTED and H(bad)!=H(EXPECTED) and differences==[12])
  need(good==EXPECTED and negative_rejected,'FIXTURE_VERDICT')
  receipt={'event':'HASH_RECEIPT','scope':'LOCAL_48_BYTE_ARTIFACT_ONLY','expected_hex':EXPECTED.hex(),'altered_hex':ALTERED.hex(),'freeze_sha256':H(fraw),'runtime_identities':f['identities'],'writers':[gr,br],'gnu':{'argv':argv,'pid':child.pid,'start_monotonic':child_start,'end_monotonic':child_end,'exit_code':child_exit,'terminal_reaped':child.poll() is not None,'stdout':out.decode('ascii'),'stderr':err.decode('ascii'),'invocations':1},'positive_exact_bytes':True,'negative_rejected':negative_rejected,'negative_difference_offsets_0based':differences,'limits':f['limits'],'start_utc':start_utc,'elapsed_before_receipt':time.monotonic()-T0,'receipt_emit_monotonic':time.monotonic()}
  receipt_bytes=enc(receipt);emit(receipt_bytes)  # Primary raw output BEFORE result is created.
  write_new('result.json',receipt_bytes)
  reread=(A/'result.json').read_bytes();need(reread==receipt_bytes and json.loads(reread)==receipt,'RESULT_READBACK')
  zip_path=A/'artifact.zip';names=['payload.jsonl','altered.jsonl','result.json']
  expected_members={'payload.jsonl':good,'altered.jsonl':bad,'result.json':receipt_bytes}
  with zipfile.ZipFile(zip_path,'x',zipfile.ZIP_STORED) as z:
   for name in names:z.writestr(name,expected_members[name])
  tick()
  with zipfile.ZipFile(zip_path) as z:
   need(z.namelist()==names and z.testzip() is None,'ZIP_MEMBERS')
   for name in names:need(z.read(name)==expected_members[name],'ZIP_BYTES:'+name)
  need((A/'payload.jsonl').read_bytes()==good and (A/'altered.jsonl').read_bytes()==bad,'FINAL_FIXTURE_BYTES')
  hashes={n:hash_file(A/n) for n in ['payload.jsonl','altered.jsonl','result.json','artifact.zip','gnu_stdout.txt','gnu_stderr.txt','T0.json']}
  tick();terminal={'event':'TERMINAL','status':'PASS_CANDIDATE_LOCAL_ARTIFACT_ONLY','child_exit':child_exit,'child_reaped':child.poll() is not None,'elapsed':time.monotonic()-T0,'end_utc':utc(),'file_hashes':hashes,'self_peak_rss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'child_peak_rss_KiB':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'execution_scope':'One own fixture attempt, one GNU invocation, no study code/network'}
  terminal_bytes=enc(terminal);write_new('terminal.json',terminal_bytes);need((A/'terminal.json').read_bytes()==terminal_bytes,'TERMINAL_READBACK');emit(terminal_bytes);return 0
 except BaseException as exc:
  if child is not None and child.poll() is None:
   child.kill()
   try:child.communicate(timeout=1)
   except subprocess.TimeoutExpired:pass
  status='UNKNOWN' if child is not None and child.poll() is None else 'STOP'
  failure={'event':'TERMINAL','status':status,'error':repr(exc),'elapsed':time.monotonic()-T0,'child_exit':None if child is None else child.poll(),'no_retry':True}
  b=enc(failure)
  if created:
   try:
    with (A/'STOP.json').open('xb') as q:q.write(b);q.flush()
   except OSError:pass
  emit(b);return 2
if __name__=='__main__':raise SystemExit(main())
