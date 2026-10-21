"""Own finite supervisor. No author imports here. NO TARGET, RETRY OR RESUME."""
import os,sys,pathlib,json,time,datetime,resource,subprocess,signal,hashlib,traceback
B=pathlib.Path(__file__).resolve().parent;R=B.parent;sys.path[:0]=[str(B),str(B/'reused')]
from common import put,sha,admit,memory,Shards,raw
from namespace_view import NamespaceView,Stop
from process_guard import inspect_prior
from limit_order import prepare_supervisor_limits,seal_supervisor_limits
from readback import verify,evaluate_all,events,number
A=R/'attempt'
def interrupted(signum,frame):raise Stop('INCOMPLETE_BUDGET_SIGNAL:'+str(signum))
for _signal in (signal.SIGXCPU,signal.SIGTERM,signal.SIGINT):signal.signal(_signal,interrupted)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def seal(folder,context):
 rows=[]
 for p in sorted(folder.rglob('*')):
  if p.is_file():
   os.chmod(p,0o444);a=p.stat();h=sha(p);b=p.stat()
   if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns):raise Stop('STOP_FILE_CHANGED_DURING_SEAL')
   rows.append({'path':str(p.relative_to(folder)),'bytes':b.st_size,'sha256':h,'dev':b.st_dev,'ino':b.st_ino,'mtime_ns':b.st_mtime_ns})
 value={'files':rows,'context':context,'utc':utc(),'all_writers_closed':True};put(folder/'seal.json',value);os.chmod(folder/'seal.json',0o444)
 receipt={'folder':str(folder.relative_to(A)),'seal_sha256':sha(folder/'seal.json'),'files':len(rows),'bytes':sum(x['bytes'] for x in rows),'context':context}
 print('CLOSED_FILES_COMPUTED '+json.dumps(receipt,sort_keys=True),flush=True);return receipt
def partial(folder):
 scores=[];rounds=0;windows=0
 try:
  for e in events(folder):
   if e['kind']=='score':scores.append(e['value'])
   elif e['kind']=='expansion_complete':rounds+=1
   elif e['kind']=='window':windows+=1
 except Exception as e:return {'error':repr(e),'observed_scores':len(scores),'complete_rounds':rounds,'window_records':windows}
 best=[]
 if scores:
  m=max(number(x['score_bits']) for x in scores);best=[{'index':x['index'],'key':x['key'],'plaintext':x['plaintext'],'score_bits':x['score_bits']} for x in scores if number(x['score_bits'])==m]
 return {'scores_observed_only':len(scores),'complete_rounds_observed_only':rounds,'windows_observed_only':windows,'partial_best_unverified':best,'not_recovery':True}
def main():
 if A.exists():print('REFUSED_PREVIOUS_ATTEMPT');return 3
 A.mkdir();F=json.loads((R/'FREEZE.json').read_text());launch=json.loads((R/'launch_evidence.json').read_text());F['_observed_sha256']=sha(R/'FREEZE.json');start=launch['monotonic'];global_end=start+1500;prep_end=start+60
 result={'version':'BE-W16-v1','status':'PREPARING','start':launch,'cases':[],'integration':[],'target_authorized':False,'delivery':'PENDING_EXACT_LIBRARY_READBACK'};ns=None;prepared=False;snapshots={}
 def tick(deadline):
  if time.monotonic()>=min(deadline,global_end):raise Stop('INCOMPLETE_BUDGET_DEADLINE')
  if int(pathlib.Path('/sys/fs/cgroup/memory.current').read_text())>=7*1024**3:raise Stop('STOP_SHARED_MEMORY')
 def resource_gate(deadline):
  tick(deadline);m,go=admit()
  if not go:raise Stop('STOP_RESOURCE_ADMISSION')
  return m
 def identity_gate(deadline):
  for row in F['identities']:
   tick(deadline);p=pathlib.Path(row['path']) if row['external'] else R/row['path'];a=p.stat();h=hashlib.sha256()
   if a.st_size!=row['bytes']:raise Stop('STOP_IDENTITY_SIZE:'+str(p))
   with p.open('rb') as f:
    for b in iter(lambda:f.read(1048576),b''):tick(deadline);h.update(b)
   z=p.stat()
   if h.hexdigest()!=row['sha256'] or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns):raise Stop('STOP_IDENTITY_HASH:'+str(p))
   snapshots[str(p)]=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns)
 def unchanged(deadline):
  for p,want in snapshots.items():
   tick(deadline);s=pathlib.Path(p).stat()
   if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)!=want:raise Stop('STOP_INPUT_CHANGED:'+p)
 def one(name,mode,dataset,case_start,deadline,work,input_row=None):
  folder=A/name;folder.mkdir();rec={'name':name,'mode':mode,'dataset':dataset,'monotonic_start':case_start,'utc':utc(),'deadline':deadline,'work_deadline':work,'status':'INCOMPLETE','foreign_released':False,'commands':[],'signals':[]};children=[];handles=[];fds=set();obs=Shards(folder,'process_observations',8*1024**2)
  put(folder/'T0.json',rec)
  if input_row is not None:put(folder/'decoder_input.json',input_row)
  def close(fd):
   if fd in fds:os.close(fd);fds.remove(fd)
  def pipe():
   p=os.pipe();fds.update(p);return p
  def watch(until=work):
   tick(until);files=[p for p in folder.iterdir() if p.is_file()];sizes=[p.stat().st_size for p in files]
   if any(n>8388608 for n in sizes) or sum(sizes)>100663296:raise Stop('INCOMPLETE_BUDGET_EVIDENCE')
   for c in children:
    if c['anchor'] is not None and len(ns.group(c['anchor'],c['known']))>1:raise Stop('STOP_UNEXPECTED_DESCENDANT')
  def output(role,stream):
   f=(folder/(role+'_'+stream+'.txt')).open('xb');handles.append(f);return f
  def spawn(role,ipc):
   gr,gw=pipe();env=dict(F['environment']);env.update(BE_PACKAGE=str(R),BE_ATTEMPT=str(folder),BE_DEADLINE=str(work),BE_MODE=mode,BE_DATASET=dataset)
   cmd=[F['python'],'-B','-I','-S',str(B/'child_gate.py'),role,str(gr),*map(str,ipc)]
   p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=output(role,'stdout'),stderr=output(role,'stderr'),pass_fds=(gr,*ipc),start_new_session=True,cwd=folder,env=env)
   c={'role':role,'p':p,'gate':gw,'anchor':None,'known':set()};children.append(c);close(gr);rec['commands'].append({'role':role,'argv':cmd,'local_pid':p.pid,'time':utc()})
   ready=folder/(role+'_ready.json')
   while True:
    watch()
    if p.poll() is not None:raise Stop('STOP_CHILD_BEFORE_READY')
    if ready.exists():
     try:q=json.loads(ready.read_text());break
     except json.JSONDecodeError:pass
    time.sleep(.02)
   a=ns.by_local(p.pid);qr=q['record']
   if a is None or a['visible_ppid']!=ns.visible_self or a['pid_namespace']!=ns.ns or (a['pid'],a['pgid'],a['session'])!=(p.pid,p.pid,p.pid):raise Stop('STOP_CHILD_IDENTITY')
   for k in ('visible_pid','starttime','pid_namespace','nspid','nspgid','nssid'):
    if a[k]!=qr[k]:raise Stop('STOP_READY_IDENTITY')
   if q['limits']!=F['role_limits'][role] or os.getpgid(p.pid)!=p.pid:raise Stop('STOP_CHILD_LIMITS_GROUP')
   c['anchor']=a;c['known'].add((a['visible_pid'],a['starttime']));rec['commands'][-1]['anchor']=a;return c
  def signal_owned(c,sig):
   if c['anchor'] is None:
    a=ns.by_local(c['p'].pid)
    if a is None:return
    if a['visible_ppid']!=ns.visible_self or a['pid_namespace']!=ns.ns or (a['pid'],a['pgid'],a['session'])!=(c['p'].pid,)*3:raise Stop('UNKNOWN_UNRELEASED_CHILD')
    c['anchor']=a;c['known'].add((a['visible_pid'],a['starttime']))
   g=ns.group(c['anchor'],c['known'])
   if g:
    if c['p'].pid==os.getpgrp():raise Stop('STOP_SELF_SIGNAL')
    try:os.killpg(c['p'].pid,sig)
    except ProcessLookupError:pass
   rec['signals'].append({'role':c['role'],'signal':int(sig),'group':g,'utc':utc()})
  try:
   rec['before']=resource_gate(work);unchanged(work)
   if (folder.parent/'Modules').exists():raise Stop('STOP_UNEXPECTED_MODULES_PATH')
   # Two IPC pipes, two release pipes; supervisor plus two children only.
   r1,w1=pipe();r2,w2=pipe();bc=spawn('broker',(r1,w2));pc=spawn('perl',(r2,w1))
   for fd in (r1,w1,r2,w2):close(fd)
   rec['release_memory']=resource_gate(work)
   for c in children:os.write(c['gate'],b'G');close(c['gate'])
   rec['foreign_released']=True;rec['release_elapsed']=time.monotonic()-case_start;print('CASE_RELEASED '+json.dumps({'name':name,'utc':utc(),'elapsed':rec['release_elapsed']}),flush=True)
   while any(c['p'].poll() is None for c in children):
    watch();record={'utc':utc(),'elapsed':time.monotonic()-case_start,'memory_current':int(pathlib.Path('/sys/fs/cgroup/memory.current').read_text()),'groups':{c['role']:ns.group(c['anchor'],c['known']) for c in children}};obs.write(raw(record))
    if any(c['p'].returncode not in (None,0) for c in children):raise Stop('STOP_CHILD_EXIT')
    time.sleep(.1)
   for c in children:
    c['p'].wait()
    if c['p'].returncode!=0:raise Stop('STOP_CHILD_EXIT')
   rec['status']='WAITING_READBACK'
  except BaseException as e:rec['error']=repr(e);rec['traceback']=traceback.format_exc();rec['status']='INCOMPLETE_BUDGET' if 'INCOMPLETE_BUDGET' in str(e) else ('STOP_RESOURCE' if str(e).startswith(('STOP_RESOURCE','STOP_SHARED_MEMORY')) else 'STOP_CORRECTNESS')
  finally:
   for fd in list(fds):close(fd)
   try:
    for c in children:
     if c['p'].poll() is None:signal_owned(c,signal.SIGTERM)
    grace=min(deadline-7,time.monotonic()+2)
    while any(c['p'].poll() is None for c in children) and time.monotonic()<grace:time.sleep(.02)
    for c in children:
     if c['p'].poll() is None:signal_owned(c,signal.SIGKILL)
    rec['terminal']=[]
    for c in children:
     c['p'].wait(timeout=max(.1,min(3,deadline-time.monotonic()-4)));g=ns.group(c['anchor'],c['known']) if c['anchor'] else []
     rec['terminal'].append({'role':c['role'],'exit':c['p'].returncode,'group':g,'utc':utc()})
     if g:raise Stop('UNKNOWN_GROUP_REMAINS')
    rec['verified_termination']=True
   except BaseException as e:rec['verified_termination']=False;rec['status']='UNKNOWN_TERMINATION';rec['cleanup_error']=repr(e)
   obs.close()
   for f in handles:f.flush();f.close()
  try:
   stderr=b''.join((folder/(c['role']+'_stderr.txt')).read_bytes() for c in children)
   if rec['status']=='STOP_CORRECTNESS' and 'CHILD_EXIT' in rec.get('error',''):
    if b'INCOMPLETE_BUDGET' in stderr or any(x['exit'] in (-24,-25) for x in rec.get('terminal',[])):rec['status']='INCOMPLETE_BUDGET'
    elif b'MemoryError' in stderr or b'Out of memory' in stderr:rec['status']='STOP_RESOURCE'
   if rec['status']=='WAITING_READBACK':
    if stderr:raise Stop('STOP_STDERR')
    unchanged(deadline-6);rb=verify(R,folder,dataset,mode,deadline-6,input_row);put(folder/'independent_readback.json',rb);rec['readback']=rb;rec['status']=rb['status']
   rec['partial_observations']=partial(folder)
  except BaseException as e:rec['readback_error']=repr(e);rec['status']='INCOMPLETE_BUDGET' if 'INCOMPLETE_BUDGET' in str(e) else 'STOP_CORRECTNESS'
  rec.update(end_utc=utc(),elapsed=time.monotonic()-case_start,after=memory(),supervisor_CPU=time.process_time(),children_usage=list(resource.getrusage(resource.RUSAGE_CHILDREN)))
  if time.monotonic()>=deadline-3:rec['status']='INCOMPLETE_BUDGET'
  put(folder/'result.json',rec);receipt=seal(folder,{'status':rec['status'],'elapsed_before_seal':rec['elapsed']});rec['seal_receipt']=receipt
  if time.monotonic()>=deadline:rec['status']='INCOMPLETE_BUDGET';rec['late_seal']=True
  return rec
 code=2
 try:
  if F['_observed_sha256']!=launch['freeze_sha256']:raise Stop('STOP_FREEZE_IDENTITY')
  put(A/'T0.json',launch);result['limits_prepared']=prepare_supervisor_limits(F['role_limits']);prepared=True
  if sys.version_info[:3]!=(3,12,14):raise Stop('STOP_PYTHON_VERSION')
  result['before']=resource_gate(prep_end);ns=NamespaceView();g=inspect_prior(ns,B/'reused',F,lambda:tick(prep_end));put(A/'prior_process_gate.json',g)
  if g['blockers']:raise Stop('STOP_PRIOR_LIVE_PROCESS')
  identity_gate(prep_end);put(A/'identity_snapshot.json',snapshots);result['after_identity']=resource_gate(prep_end)
  for dataset in ('base','edge'):
   now=time.monotonic();rec=one('integration_'+dataset,'fixture',dataset,now,prep_end,min(prep_end-10,now+25));result['integration'].append(rec)
   if rec['status']!='PASS_FINITE_INTEGRATION' or not rec['verified_termination']:raise Stop('STOP_INTEGRATION')
  tick(prep_end);rows=json.loads((R/'decoder/inputs.json').read_text())['cases']
  if len(rows)!=8:raise Stop('STOP_INPUT_COUNT')
  for index,row in enumerate(rows):
   now=time.monotonic();rec=one('case_%02d'%(index+1),'search','real',now,min(now+180,global_end),min(now+130,global_end-10),row);result['cases'].append({'id':row['id'],**rec})
   if not rec['verified_termination'] or rec['status'] not in ('CASE_COMPLETE_CANDIDATE','INCOMPLETE_BUDGET'):break
  got={r['id']:r.get('readback',{}) if r['status']=='CASE_COMPLETE_CANDIDATE' else {'status':r['status']} for r in result['cases']}
  for row in rows:
   if row['id'] not in got:got[row['id']]={'status':'NOT_STARTED'}
  # The only access to evaluator truth occurs here, after all child searches ended.
  result['evaluation']=evaluate_all(R,got);result['status']='COMPLETED_PILOT_CANDIDATE' if result['evaluation']['completed']==8 else 'INCOMPLETE_PILOT';code=0 if result['evaluation']['completed']==8 else 2
 except BaseException as e:result['status']='STOP_PREPARATION' if not result['cases'] else 'STOP';result['error']=repr(e);result['traceback']=traceback.format_exc()
 finally:
  if prepared:
   try:result['final_limits']=seal_supervisor_limits(F['role_limits'])
   except BaseException as e:result['status']='STOP_LIMIT_SEAL';result['limit_error']=repr(e);code=2
  result.update(end_utc=utc(),elapsed=time.monotonic()-start,exit_code=code,supervisor_maxrss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,supervisor_CPU=time.process_time())
  if result['elapsed']>=1500:result['status']='INCOMPLETE_BUDGET';result['exit_code']=code=2
  put(A/'result.json',result);seal(A,{'version':'BE-W16-v1','freeze_sha256':F['_observed_sha256'],'status':result['status'],'exit_code':code})
  print('SEAL_COMPUTED_SHA256 '+sha(A/'seal.json'),flush=True)
 return code
if __name__=='__main__':raise SystemExit(main())
