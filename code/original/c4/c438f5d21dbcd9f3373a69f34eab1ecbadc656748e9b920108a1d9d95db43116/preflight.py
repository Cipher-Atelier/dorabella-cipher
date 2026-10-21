"""Read-only pre-command identities/process/resource checks. No smoke or science."""
import sys,os,pathlib,json,hashlib,datetime,time,resource,zipfile
B=pathlib.Path('/workspace/scratch/f24f8fae4976');R=B/'BE_W16_v2';E=B/'BE_W16_v2_execution_20261018'
sys.path[:0]=[str(R/'runtime/reused')]
from namespace_view import NamespaceView
start=time.monotonic();out={'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':str(R/'runtime/launch.py'),'scope':'pre-command read-only; no pilot T0','identities':[]}
def h(p):
 a=p.stat();d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):
   if time.monotonic()-start>60:raise RuntimeError('PREFLIGHT_DEADLINE')
   d.update(b)
 z=p.stat();assert (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns)
 return d.hexdigest()
def memory():
 d={n:(pathlib.Path('/sys/fs/cgroup')/n).read_text().strip() for n in ('memory.current','memory.max','memory.events','memory.stat')}
 assert d['memory.max']=='8589934592' and int(d['memory.current'])<5468942336,'STOP_RESOURCE_ADMISSION'
 return d
code=2
try:
 assert not (E/'preflight.json').exists(),'PREVIOUS_PREFLIGHT'
 assert not (R/'attempt').exists() and not (R/'launch_evidence.json').exists(),'PRIOR_V2_ATTEMPT'
 assert sys.version_info[:3]==(3,12,14),'RUNTIME_VERSION'
 expected={'FREEZE.json':'5ad495e82c7bdcacef9bab496512e93dbd3fa3fbd5fb6a1a69baec30212df94d','MANIFEST.json':'62545bef8ed555dadd2cbbb1493b4c2c75948f921e0e5000022d78a2bf14c425'}
 for p,want in expected.items():assert h(R/p)==want,p
 z=B/'Dorabella_BE_W16_v2_frozen_20261018.zip';assert h(z)=='9a17caeb607eeeb9863c3e8abbc3a4a9b524bda3ec5e216f948ee65c673759ca'
 out['hashes']={**expected,'ZIP':h(z)};F=json.loads((R/'FREEZE.json').read_text())
 out['before']=memory()
 for row in F['identities']:
  p=pathlib.Path(row['path']) if row['external'] else R/row['path'];a=p.stat();got=h(p)
  assert got==row['sha256'] and a.st_size==row['bytes'],('IDENTITY',str(p))
  out['identities'].append({'path':str(p),'sha256':got,'bytes':a.st_size,'dev':a.st_dev,'ino':a.st_ino,'mtime_ns':a.st_mtime_ns})
 with zipfile.ZipFile(z) as pack:
  for name in pack.namelist():assert pack.read(name)==(B/name).read_bytes(),name
 st=os.stat(F['carrier_executable']);assert {k:getattr(st,k) for k in F['carrier_file_stat']}==F['carrier_file_stat'],'CARRIER_IDENTITY'
 ns=NamespaceView();out['namespace_self']=ns.self_record;out['namespace_ancestors']=ns.ancestors
 protected={(r['visible_pid'],r['starttime'],tuple(r['nspid']),r['pid_namespace']) for r in [ns.self_record,*ns.ancestors]};scripts=set(F['guard_script_paths']);matches=[]
 for r in ns.snapshot():
  if any(any(s in a for s in scripts) for a in r['cmdline']):
   ident=(r['visible_pid'],r['starttime'],tuple(r['nspid']),r['pid_namespace']);q={**r,'protected_self_or_ancestor':ident in protected}
   try:q['proc_exe']=os.readlink('/proc/'+str(r['visible_pid'])+'/exe')
   except (FileNotFoundError,PermissionError):q['proc_exe']=None
   matches.append(q)
 out['process_matches']=matches;assert not [r for r in matches if not r['protected_self_or_ancestor']],'PRIOR_PROCESS_OR_UNRESOLVED_CARRIER'
 old=json.loads((B/'BE_W16_v1/attempt/result.json').read_text());out['old_terminal_checks']=[]
 for case in old.get('integration',[])+old.get('cases',[]):
  assert case.get('verified_termination'),'OLD_TERMINATION_UNVERIFIED'
  for cmd in case.get('commands',[]):
   a=cmd.get('anchor')
   if a:
    now=ns.read_visible(a['visible_pid']);same=now is not None and now['starttime']==a['starttime']
    assert not same or now['state']=='Z','OLD_PROCESS_STILL_LIVE'
    out['old_terminal_checks'].append({'case':case['name'],'role':cmd['role'],'old_anchor':a,'observed_now':now,'same_identity_live':False})
 out['effective_outer_limits']={n:list(resource.getrlimit(getattr(resource,n))) for n in ('RLIMIT_AS','RLIMIT_CPU','RLIMIT_FSIZE','RLIMIT_NOFILE','RLIMIT_CORE')}
 for roles in F['role_limits'].values():
  for n,want in roles.items():
   hard=resource.getrlimit(getattr(resource,n))[1];assert hard==resource.RLIM_INFINITY or hard>=max(want),('INHERITED_HARD_LIMIT',n)
 out['after']=memory();out['status']='PASS_PRECOMMAND';code=0
except BaseException as e:out['status']='STOP_PRECOMMAND';out['error']=repr(e)
out.update(utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_s=time.monotonic()-start,exit_code=code)
with (E/'preflight.json').open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
print('PRECOMMAND_COMPUTED '+json.dumps({'status':out['status'],'error':out.get('error'),'identities':len(out['identities']),'memory_current':out.get('after',{}).get('memory.current'),'utc':out['utc_end'],'receipt_sha256':h(E/'preflight.json')},sort_keys=True),flush=True)
raise SystemExit(code)
