"""One own wrapper smoke: harmless stubs only. Never imports or executes search."""
import os,sys,json,pathlib,time,datetime,hashlib,resource,subprocess,signal,traceback
sys.dont_write_bytecode=True
B=pathlib.Path(__file__).resolve().parent;R=B.parent
sys.path.insert(0,str(R/'candidate/runtime'));sys.path.insert(0,str(B))
from limit_order import plan_limits,prepare_supervisor_limits,seal_supervisor_limits,LimitOrderError
from namespace_view import NamespaceView
A=R/'smoke_attempt'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def all_limits():return {k:list(resource.getrlimit(getattr(resource,k))) for k in dir(resource) if k.startswith('RLIMIT_')}
PROC_NAMES={'RLIMIT_AS':'Max address space','RLIMIT_CPU':'Max cpu time','RLIMIT_FSIZE':'Max file size','RLIMIT_NOFILE':'Max open files','RLIMIT_CORE':'Max core file size'}
def proc_values(raw):
 out={}
 for k,label in PROC_NAMES.items():
  row=next(x for x in raw.splitlines() if x.startswith(label+' '))
  a=row[len(label):].split();out[k]=[int(a[0]),int(a[1])]
 return out
def dump(n,x):
 with (A/n).open('x') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
 if A.exists():print('REFUSED_PREVIOUS_SMOKE');return 3
 A.mkdir();t=time.monotonic();end=t+15;work=t+10
 result={'version':'TS-RLIMIT-ORDER-REPAIR-v1-smoke','status':'INCOMPLETE','utc_start':utc(),'scientific_runs':0,'foreign_exec':False,'events':[]}
 children=[];handles=[];fdset=set();ns=None;prepared=False;sealed=False;ok=False
 def tick():
  if time.monotonic()>=work:raise RuntimeError('STOP_SMOKE_DEADLINE')
 def publish_event(kind,**kw):result['events'].append({'kind':kind,'elapsed':time.monotonic()-t,**kw})
 def await_file(p):
  while not p.exists():
   tick()
   if any(c['p'].poll() not in (None,0) for c in children):raise RuntimeError('STOP_STUB_EARLY_EXIT')
   time.sleep(.01)
  return json.loads(p.read_text())
 def close(fd):
  if fd in fdset:os.close(fd);fdset.remove(fd)
 def verified_signal(c,sig):
  a=c['anchor']
  if a is None:
   a=ns.by_local(c['p'].pid)
   if a is None:return
   if a['visible_ppid']!=ns.visible_self or (a['pid'],a['pgid'],a['session'])!=(c['p'].pid,)*3:raise RuntimeError('STOP_SIGNAL_IDENTITY')
   c['anchor']=a;c['known'].add((a['visible_pid'],a['starttime']))
  group=ns.group(a,c['known'])
  if group:
   if a['pid']==os.getpgrp():raise RuntimeError('STOP_SELF_GROUP')
   os.killpg(a['pid'],sig)
  result.setdefault('signals',[]).append({'role':c['role'],'signal':int(sig),'group':group})
 try:
  freeze=json.loads((R/'SMOKE_FREEZE.json').read_text())
  for row in freeze['files']:
   p=R/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
  assert sha(pathlib.Path(sys.executable))==freeze['python_sha256']
  F=json.loads((B/'role_limits.json').read_text())
  ns=NamespaceView();result['self_identity']=ns.self_record
  original=json.loads((R/'baseline/FREEZE.json').read_text())
  scripts=set(original['guard_script_paths'])|{str(B/'child_stub.py')}
  prior=[r for r in ns.snapshot() if any(arg in scripts for arg in r['cmdline'])]
  result['prior_exact_processes']=prior;assert not prior
  memory={k:(pathlib.Path('/sys/fs/cgroup')/k).read_text().strip() for k in ('memory.current','memory.max','memory.events')}
  result['memory_before']=memory
  assert memory['memory.max']=='8589934592' and int(memory['memory.current'])<5468942336
  before=all_limits();result['all_before']=before
  # Pure finite negative fixtures do not alter kernel limits.
  expected={k:list(v) for k,v in F['supervisor'].items()};expected['RLIMIT_AS'][1]=268435456
  assert plan_limits(F,{k:[-1,-1] for k in expected})==expected
  cases=[]
  for key,hard in [('RLIMIT_AS',134217728),('RLIMIT_CPU',174),('RLIMIT_FSIZE',8388607),('RLIMIT_NOFILE',63)]:
   inherited={k:[-1,-1] for k in expected};inherited[key]=[0,hard]
   try:plan_limits(F,inherited);raise AssertionError('NEGATIVE_ACCEPTED')
   except LimitOrderError as e:assert str(e)=='STOP_INHERITED_HARD:'+key;cases.append({'case':key,'rejected':str(e)})
  malformed=json.loads(json.dumps(F));malformed['broker']['RLIMIT_CORE']=[1,0]
  try:plan_limits(malformed,{k:[-1,-1] for k in expected});raise AssertionError('NEGATIVE_ACCEPTED')
  except LimitOrderError as e:assert str(e)=='STOP_LIMIT_PAIR:broker:RLIMIT_CORE';cases.append({'case':'invalid_pair','rejected':str(e)})
  assert all_limits()==before
  result['pure_negative_fixtures']=cases
  result['prepared']=prepare_supervisor_limits(F);prepared=True
  result['all_prepared']=all_limits();assert result['prepared']['actual']==expected
  result['prepared_proc_limits']=pathlib.Path('/proc/self/limits').read_text();assert proc_values(result['prepared_proc_limits'])==expected
  changed_ids={getattr(resource,k) for k in F['supervisor']}
  def untouched(snapshot):return {k:v for k,v in snapshot.items() if getattr(resource,k) not in changed_ids}
  assert untouched(result['all_prepared'])==untouched(before)
  publish_event('SUPERVISOR_STAGED',limits=result['prepared']['actual'])
  for role in ('broker','perl'):
   tick();rd,wr=os.pipe();fdset.update((rd,wr))
   outs=[]
   for suffix in ('stdout','stderr'):
    f=(A/(role+'_'+suffix+'.txt')).open('xb');handles.append(f);outs.append(f)
   cmd=[sys.executable,'-B','-I','-S',str(B/'child_stub.py'),role,str(rd),str(A)]
   p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=outs[0],stderr=outs[1],pass_fds=(rd,),start_new_session=True,env={'PATH':'/usr/bin:/bin','LC_ALL':'C','TZ':'UTC'})
   c={'p':p,'role':role,'gate':wr,'anchor':None,'known':set()};children.append(c);close(rd)
   q=await_file(A/(role+'_ready.json'));a=ns.by_local(p.pid)
   assert a and a['visible_ppid']==ns.visible_self and (a['pid'],a['pgid'],a['session'])==(p.pid,)*3
   assert (q['identity']['visible_pid'],q['identity']['starttime'],q['identity']['namespace'])==(a['visible_pid'],a['starttime'],ns.ns)
   c['anchor']=a;c['known'].add((a['visible_pid'],a['starttime']))
   assert len(ns.group(a,c['known']))==1
   assert {k:q['before'][k] for k in expected}==expected
   assert {k:q['after'][k] for k in expected}==F[role]
   assert untouched(q['after'])==untouched(before)
   raw=(pathlib.Path('/proc')/str(a['visible_pid'])/'limits').read_text()
   assert proc_values(raw)==F[role] and proc_values(q['proc_limits'])==F[role]
   result.setdefault('children_ready',[]).append({'role':role,'argv':cmd,'anchor':a,'record':q,'independent_proc_limits':raw})
   assert not (A/(role+'_released.json')).exists()
   publish_event('CHILD_READY_BLOCKED',role=role,limits=F[role])
  result['final_limits']=seal_supervisor_limits(F);sealed=True
  result['all_final']=all_limits();assert untouched(result['all_final'])==untouched(before)
  result['final_proc_limits']=pathlib.Path('/proc/self/limits').read_text();assert proc_values(result['final_proc_limits'])==F['supervisor']
  publish_event('SUPERVISOR_FINAL_BEFORE_RELEASE',limits=result['final_limits'])
  for c in children:os.write(c['gate'],b'G');close(c['gate']);publish_event('RELEASE',role=c['role'])
  for c in children:
   q=await_file(A/(c['role']+'_released.json'))
   assert {k:q['after'][k] for k in expected}==F[c['role']]
  children[0]['p'].wait(timeout=max(.1,work-time.monotonic()));assert children[0]['p'].returncode==0
  assert children[1]['p'].poll() is None
  ok=True
 except BaseException as e:result['error']=repr(e);result['traceback']=traceback.format_exc()
 finally:
  if prepared and not sealed:
   try:result['final_limits_on_error']=seal_supervisor_limits(F)
   except BaseException as e:result['seal_error']=repr(e);ok=False
  for fd in list(fdset):close(fd)
  try:
   for c in children:
    if c['p'].poll() is None:verified_signal(c,signal.SIGTERM)
   grace=min(end-2,time.monotonic()+1)
   while any(c['p'].poll() is None for c in children) and time.monotonic()<grace:time.sleep(.01)
   for c in children:
    if c['p'].poll() is None:verified_signal(c,signal.SIGKILL)
   for c in children:
    c['p'].wait(timeout=max(.1,min(1,end-time.monotonic())))
    g=ns.group(c['anchor'],c['known']) if c['anchor'] else []
    result.setdefault('terminal',[]).append({'role':c['role'],'exit':c['p'].returncode,'group':g})
    if g:raise RuntimeError('STOP_GROUP_REMAINS')
   result['verified_cleanup']=True
  except BaseException as e:result['cleanup_error']=repr(e);result['verified_cleanup']=False;ok=False
  for f in handles:f.flush();f.close()
  if ok:
   ok=(len(children)==2 and [c['p'].returncode for c in children]==[0,-15] and all((A/(c['role']+'_stderr.txt')).stat().st_size==0 for c in children))
  result['elapsed']=time.monotonic()-t;result['maxrss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;result['utc_end']=utc()
  result['status']='PASS_WRAPPER_LIMITS_ONLY' if ok and result['elapsed']<=15 else 'STOP_SMOKE'
  result['exit_code']=0 if result['status']=='PASS_WRAPPER_LIMITS_ONLY' else 2
  dump('result.json',result)
  closed=[{'path':str(p.relative_to(A)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(A.iterdir()) if p.is_file()]
  dump('closed_files.json',closed)
  print('SMOKE_CLOSED_FILES_COMPUTED '+json.dumps(closed,sort_keys=True),flush=True)
  print('SMOKE_RESULT_COMPUTED '+json.dumps({'status':result['status'],'exit_code':result['exit_code'],'elapsed':result['elapsed'],'result_sha256':sha(A/'result.json'),'closed_files_sha256':sha(A/'closed_files.json'),'terminal':result.get('terminal',[])}),flush=True)
 return result['exit_code']
if __name__=='__main__':raise SystemExit(main())

