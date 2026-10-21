"""NEW recovered supervisor. Only blind Lincoln search; never target, retry or resume."""
import os,sys,json,time,datetime,pathlib,hashlib,resource,subprocess,signal,traceback
sys.dont_write_bytecode=True;B=pathlib.Path(__file__).resolve().parent;R=B.parent;sys.path.insert(0,str(B))
from namespace_view import NamespaceView,Stop
from audit_io import sha_file
from process_guard import regression,inspect_prior
A=R/'attempt'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(n,x):
 with (A/n).open('x') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def memory():return {k:(pathlib.Path('/sys/fs/cgroup')/k).read_text().strip() for k in ['memory.max','memory.current','memory.events','memory.stat']}
def main():
 if A.exists():print('REFUSED_EXISTING_ATTEMPT');return 3
 A.mkdir();(A/'work').mkdir();launch=json.loads((R/'launch_evidence.json').read_text());start=launch['monotonic'];end=start+180;work=start+130
 result={'version':'TS-RECOVERED-SEARCH-v2','status':'INCOMPLETE','start_utc':launch['utc'],'commands':[],'signals':[],'foreign_released':False,'target_inputs':0,'control_inputs':1,'stages':[]}
 dump('T0.json',launch);children=[];handles=[];fds=set();ns=None;F=None;observations=None
 def tick(stop=work):
  if time.monotonic()>=stop:raise Stop('INCOMPLETE_BUDGET_DEADLINE')
  if int((pathlib.Path('/sys/fs/cgroup')/'memory.current').read_text())>=7*1024**3:raise Stop('STOP_SHARED_MEMORY')
  files=[p for p in A.iterdir() if p.is_file()]
  if any(p.stat().st_size>8388608 for p in files) or sum(p.stat().st_size for p in files)>96*1024**2:raise Stop('INCOMPLETE_BUDGET_OUTPUT')
  for c in children:
   if c['anchor'] is not None and not c.get('retired'):
    if len(ns.group(c['anchor'],c['known']))>1:raise Stop('STOP_UNEXPECTED_DESCENDANT')
 def hash_checked(p):
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):tick();h.update(b)
  return h.hexdigest()
 def full_gate():
  m=memory();return m,(m['memory.max']=='8589934592' and int(m['memory.current'])+F['resource']['input_pages']+512*1024**2+128*1024**2<7*1024**3)
 def close(fd):
  if fd in fds:os.close(fd);fds.remove(fd)
 def pipe():
  pair=os.pipe();fds.update(pair);return pair
 def handle(n):
  f=(A/n).open('xb');handles.append(f);return f
 def spawn(role,ipc):
  tick();gr,gw=pipe();env=dict(F['environment']);env.update({'TS_PACKAGE':str(R),'TS_ATTEMPT':str(A),'TS_DEADLINE':str(work),'TS_START_UTC':launch['utc']})
  cmd=[F['python'],'-B','-I','-S',str(B/'child_gate.py'),role,str(gr),*map(str,ipc)]
  p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=handle(role+'_stdout.txt'),stderr=handle(role+'_stderr.txt'),pass_fds=(gr,*ipc),start_new_session=True,cwd=A/'work',env=env)
  c={'p':p,'role':role,'anchor':None,'known':set(),'gate':gw};children.append(c);close(gr)
  result['commands'].append({'role':role,'argv':cmd,'local_pid':p.pid,'observed_utc':utc()})
  ready=A/(role+'_ready.json')
  while not ready.exists():
   tick()
   if p.poll() is not None:raise Stop('STOP_BEFORE_READY:'+role)
   time.sleep(.02)
  # gate file was closed before waiting for release; retry reads only incomplete JSON race.
  while True:
   try:q=json.loads(ready.read_text());break
   except json.JSONDecodeError:tick();time.sleep(.01)
  a=ns.by_local(p.pid)
  if not a or a['visible_ppid']!=ns.visible_self or a['pid_namespace']!=ns.ns:raise Stop('STOP_CHILD_IDENTITY')
  if (a['pid'],a['pgid'],a['session'])!=(p.pid,p.pid,p.pid) or os.getpgid(p.pid)!=p.pid or p.pid==os.getpgrp():raise Stop('STOP_GROUP_IDENTITY')
  if (q['local_pid'],q['local_pgid'],q['local_sid'],q['visible_pid'],q['namespace'])!=(p.pid,p.pid,p.pid,a['visible_pid'],ns.ns):raise Stop('STOP_NAMESPACE_MAPPING')
  if q['limits']!=F['role_limits'][role]:raise Stop('STOP_CHILD_LIMITS')
  c['anchor']=a;c['known'].add((a['visible_pid'],a['starttime']));ns.group(a,c['known']);result['commands'][-1]['anchor']=a
  return c
 def signal_owned(c,sig):
  if c['anchor'] is None:
   a=ns.by_local(c['p'].pid)
   if a is None:return
   if a['visible_ppid']!=ns.visible_self or (a['pid'],a['pgid'],a['session'])!=(c['p'].pid,)*3:raise Stop('UNKNOWN_UNRELEASED_CHILD_IDENTITY')
   c['anchor']=a;c['known'].add((a['visible_pid'],a['starttime']))
  a=c['anchor'];group=ns.group(a,c['known'])
  if group:
   if a['pid']==os.getpgrp():raise Stop('STOP_SELF_GROUP')
   try:os.killpg(a['pid'],sig)
   except ProcessLookupError:pass
  result['signals'].append({'role':c['role'],'signal':int(sig),'group':group,'utc':utc()})
 code=2
 try:
  F=json.loads((R/'FREEZE.json').read_text());F['_observed_sha256']=sha_file(R/'FREEZE.json')
  assert F['_observed_sha256']==launch['freeze_sha256']
  for k,v in F['role_limits']['supervisor'].items():resource.setrlimit(getattr(resource,k),tuple(v))
  if sys.version_info[:3]!=(3,12,14):raise Stop('STOP_PYTHON_VERSION')
  result['before'],go=full_gate()
  if not go:raise Stop('STOP_RESOURCE_ADMISSION')
  ns=NamespaceView();result['namespace_self']=ns.self_record
  result['guard_cases']=regression(B);guard=inspect_prior(ns,B,F,tick);dump('process_guard.json',guard)
  if guard['blockers']:raise Stop('STOP_PRIOR_LIVE_PROCESS')
  for row in F['identities']:
   p=pathlib.Path(row['path']) if row['external'] else R/row['path']
   if p.stat().st_size!=row['bytes'] or hash_checked(p)!=row['sha256']:raise Stop('STOP_IDENTITY:'+str(p))
  prior=json.loads((R/'prior_evidence/stage_fixture.json').read_text());assert prior['status']=='PASS_FINITE_COMBINED_DIFFERENTIAL' and prior['events']==320 and prior['inverse_records']==118
  assert (R/'prior_evidence/reference_perl.jsonl').read_bytes()==(R/'prior_evidence/adapted_perl.jsonl').read_bytes()
  result['prior_fixture']='REUSED_FINITE_BYTES_ONLY';result['after_hashes'],go=full_gate()
  if not go:raise Stop('STOP_RESOURCE_POST_HASH')
  if work-time.monotonic()<60:raise Stop('INCOMPLETE_BUDGET_PREFLIGHT')
  if (A/'Modules').exists():raise Stop('STOP_UNEXPECTED_MODULES')
  lr,lw=pipe();rr,rw=pipe();pr,pw=pipe();qr,qw=pipe()
  bc=spawn('broker',(lr,rw,pr,qw));pc=spawn('perl',(rr,lw,qr,pw))
  for fd in [lr,lw,rr,rw,pr,pw,qr,qw]:close(fd)
  result['release_resource'],go=full_gate()
  if not go:raise Stop('STOP_RESOURCE_RELEASE')
  for c in [bc,pc]:tick();os.write(c['gate'],b'G');close(c['gate']);c['gate']=None
  result['foreign_released']=True;result['release_elapsed']=time.monotonic()-start;print('SEARCH_RELEASED '+utc(),flush=True)
  observations=(A/'process_observations.jsonl').open('xb')
  while any(c['p'].poll() is None for c in children):
   tick();rec={'utc':utc(),'elapsed':time.monotonic()-start,'current':int((pathlib.Path('/sys/fs/cgroup')/'memory.current').read_text()),'groups':{c['role']:ns.group(c['anchor'],c['known']) for c in children}}
   observations.write((json.dumps(rec,separators=(',',':'))+'\n').encode());observations.flush();time.sleep(.1)
  observations.flush();observations.close();observations=None
  for c in children:
   c['p'].wait();g=ns.group(c['anchor'],c['known']);result['stages'].append({'role':c['role'],'exit':c['p'].returncode,'terminal_group':g,'elapsed':time.monotonic()-start})
   if g:raise Stop('UNKNOWN_GROUP_REMAINS')
   c['retired']=True
   if c['p'].returncode!=0:raise Stop('INCOMPLETE_OR_ERROR_CHILD_EXIT')
  for f in handles:f.flush();f.close()
  handles=[]
  if any((A/(c['role']+'_stderr.txt')).stat().st_size for c in children):raise Stop('STOP_STDERR')
  from readback import verify
  result['readback']=verify(R,A,min(end-8,time.monotonic()+42));dump('independent_readback.json',result['readback']);result['status']=result['readback']['status'];code=0
 except BaseException as e:
  result['error']=repr(e);result['traceback']=traceback.format_exc();s=str(e)
  result['status']='INCOMPLETE_BUDGET' if s.startswith('INCOMPLETE_BUDGET') else ('STOP_RESOURCE' if s.startswith(('STOP_RESOURCE','STOP_SHARED_MEMORY')) else 'STOP_CORRECTNESS')
 finally:
  for fd in list(fds):close(fd)
  try:
   for c in children:
    if not c.get('retired'):signal_owned(c,signal.SIGTERM)
   grace=min(end-5,time.monotonic()+2)
   while any(c['p'].poll() is None for c in children) and time.monotonic()<grace:time.sleep(.02)
   for c in children:
    if c['p'].poll() is None:signal_owned(c,signal.SIGKILL)
   for c in children:
    c['p'].wait(timeout=max(.1,min(3,end-time.monotonic()-2)))
    g=ns.group(c['anchor'],c['known']) if c['anchor'] else []
    result.setdefault('terminal',[]).append({'role':c['role'],'exit':c['p'].returncode,'group':g,'utc':utc()})
    if g:raise Stop('UNKNOWN_NONEMPTY_GROUP')
   result['verified_termination']=True
  except BaseException as e:result['status']='UNKNOWN_TERMINATION';result['cleanup_error']=repr(e);result['verified_termination']=False;code=4
  if observations:observations.flush();observations.close()
  for f in handles:
   if not f.closed:f.flush();f.close()
  result['after']=memory();result['elapsed_total']=time.monotonic()-start;result['supervisor_CPU']=time.process_time();result['children_usage']=list(resource.getrusage(resource.RUSAGE_CHILDREN));result['supervisor_maxrss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;result['end_utc']=utc()
  if result['elapsed_total']>180:result['status']='INCOMPLETE_BUDGET';code=2
  # Classify cap/error stderr only after close; never manufacture a completed Expansion.
  if result['status']=='STOP_CORRECTNESS' and result.get('error', '').find('CHILD_EXIT')>=0:
   stderr=b''.join((A/(c['role']+'_stderr.txt')).read_bytes() for c in children)
   if b'INCOMPLETE_BUDGET' in stderr:result['status']='INCOMPLETE_BUDGET'
  if result['status'] not in ('CONTROL_RECOVERED','CONTROL_NOT_RECOVERED'):code=4 if result['status']=='UNKNOWN_TERMINATION' else 2
  result['exit_code']=code;result['delivery']='PENDING_EXACT_LIBRARY_READBACK';dump('result.json',result)
  # No writer remains. The seal is not a member of itself; no append after hashing.
  files=[]
  for p in sorted(A.rglob('*')):
   if p.is_file():
    before=p.stat();h=sha_file(p);after=p.stat();assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
    files.append({'path':str(p.relative_to(A)),'dev':after.st_dev,'ino':after.st_ino,'bytes':after.st_size,'sha256':h,'mtime_ns':after.st_mtime_ns})
  seal={'files':files,'freeze_sha256':launch['freeze_sha256'],'end_utc':utc(),'elapsed_to_seal':time.monotonic()-start,'status':result['status'],'exit_code':code,'observation_stream_closed':True}
  dump('seal.json',seal);print('CLOSED_FILES_COMPUTED '+json.dumps(seal,sort_keys=True,separators=(',',':')),flush=True);print('SEAL_COMPUTED_SHA256 '+sha_file(A/'seal.json'),flush=True)
 return code
if __name__=='__main__':raise SystemExit(main())
