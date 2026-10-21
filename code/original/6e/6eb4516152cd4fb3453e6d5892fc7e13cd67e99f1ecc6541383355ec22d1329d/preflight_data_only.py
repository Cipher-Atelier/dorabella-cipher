import os,sys,json,hashlib,pathlib,datetime,resource,zipfile,time
R=pathlib.Path('/workspace/scratch/f24f8fae4976/TS_RECOVERED_SEARCH_v3')
E=pathlib.Path(__file__).parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
o={'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'errors':[],'files':[]}
pins={'FREEZE.json':'84146a52c5f0e2e53974c0220eb3cb63f698fd81c6250a522083099447050874','MANIFEST.json':'06414f0381afd15d6cf0ddae768323575836e1f98010fb061ce3c5d07d1523db'}
for n,h in pins.items():
 actual=sha(R/n);o[n]=actual
 if actual!=h:o['errors'].append('PIN:'+n)
z=R.parent/'Dorabella_TS_RECOVERED_SEARCH_v3_frozen_20261018.zip'
o['zip_sha256']=sha(z)
if o['zip_sha256']!='7ad43c0ae2e3129f914bc090b7a521ddd24351b6dacd1b85361e757e24f53968':o['errors'].append('ZIP')
F=json.loads((R/'FREEZE.json').read_text());M=json.loads((R/'MANIFEST.json').read_text())
seen={}
for row in F['identities']+M['files']:
 p=pathlib.Path(row['path']) if row.get('external') else R/row['path']
 if str(p) in seen:
  if seen[str(p)]!=(row['bytes'],row['sha256']):o['errors'].append('CONFLICT:'+str(p))
  continue
 seen[str(p)]=(row['bytes'],row['sha256'])
 try:
  st=p.stat();h=sha(p);ok=(st.st_size,h)==seen[str(p)]
  o['files'].append({'path':str(p),'bytes':st.st_size,'sha256':h,'ok':ok})
  if not ok:o['errors'].append('IDENTITY:'+str(p))
 except OSError as e:o['errors'].append('FILE:'+str(p)+':'+repr(e))
with zipfile.ZipFile(z) as q:
 o['zip_members']=len(q.infolist())
 for n in q.namelist():
  if n.endswith('/'):continue
  p=R/n
  if not p.is_file() or hashlib.sha256(q.read(n)).hexdigest()!=sha(p):o['errors'].append('ZIP_MEMBER:'+n)
o['prior_attempt_exists']=(R/'attempt').exists();o['prior_launch_exists']=(R/'launch_evidence.json').exists()
if o['prior_attempt_exists'] or o['prior_launch_exists']:o['errors'].append('PRIOR_V3_ATTEMPT')
st=pathlib.Path(F['carrier_executable']).stat();o['carrier_stat']={k:getattr(st,k) for k in F['carrier_file_stat']}
if o['carrier_stat']!=F['carrier_file_stat']:o['errors'].append('CARRIER_STAT')
o['live_matches']=[];o['proc_unreadable']=[];o['processes_inspected']=0
guard=set(F['guard_script_paths'])
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  args=p.joinpath('cmdline').read_bytes().split(b'\0');args=[a.decode(errors='replace') for a in args if a]
  status=p.joinpath('status').read_text();stat=p.joinpath('stat').read_text();tail=stat[stat.rfind(')')+2:].split()
  o['processes_inspected']+=1
  matched=[a for a in args if a in guard]
  names=[pathlib.Path(a).name for a in args[:2]]
  suspicious=any(n in ('broker.py','profile.pl','masc_solver_mcts.pl','perl') for n in names)
  if matched or suspicious:
   rec={'visible_pid':int(p.name),'argv':args,'state':tail[0],'starttime':tail[19],'NSpid':[l for l in status.splitlines() if l.startswith('NSpid:')],'exact_matches':matched}
   o['live_matches'].append(rec)
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:o['proc_unreadable'].append(int(p.name))
if o['live_matches']:o['errors'].append('LIVE_PROCESS_OR_AMBIGUITY')
o['inherited_limits']={k:list(resource.getrlimit(getattr(resource,k))) for k in F['role_limits']['supervisor']}
for k,lim in o['inherited_limits'].items():
 need=max(v[k][1] for v in F['role_limits'].values())
 if lim[1]!=resource.RLIM_INFINITY and lim[1]<need:o['errors'].append('INHERITED_LIMIT:'+k)
C=pathlib.Path('/sys/fs/cgroup');o['memory']={k:(C/k).read_text().strip() for k in ('memory.max','memory.current','memory.stat','memory.events')}
o['memory_formula_total']=int(o['memory']['memory.current'])+F['resource']['input_pages']+F['resource']['AS_sum']+F['resource']['allowance']
o['memory_pass']=o['memory']['memory.max']=='8589934592' and int(o['memory']['memory.current'])<5468942336 and o['memory_formula_total']<7516192768
if not o['memory_pass']:o['errors'].append('RESOURCE_GATE')
o['utc_end']=datetime.datetime.now(datetime.timezone.utc).isoformat();o['status']='PASS_EXTERNAL_PREFLIGHT' if not o['errors'] else 'STOP_EXTERNAL_PREFLIGHT'
with (E/'preflight.json').open('x') as f:json.dump(o,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps({k:v for k,v in o.items() if k not in ('files','memory')},sort_keys=True))
print('MEMORY_CURRENT',o['memory']['memory.current'])
print('PREFLIGHT_COMPUTED_SHA256',sha(E/'preflight.json'))
sys.exit(0 if not o['errors'] else 2)
