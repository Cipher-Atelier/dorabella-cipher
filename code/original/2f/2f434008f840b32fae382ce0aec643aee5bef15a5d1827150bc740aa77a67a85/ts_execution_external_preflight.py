import pathlib,json,hashlib,os,datetime,time
B=pathlib.Path('/workspace/scratch/f24f8fae4976'); R=B/'TS_RECOVERED_SEARCH_v2'
E=B/'TS_RECOVERED_SEARCH_v2_execution_evidence';E.mkdir(exist_ok=False)
t=time.monotonic()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
expected={
'Dorabella_TS_RECOVERED_SEARCH_v2_frozen_20261018.zip':'5b97698dd667a290a0cb62844a790376d839b19c47f673d9ec1cb5facd527817',
'TS_RECOVERED_SEARCH_v2/FREEZE.json':'c12035b1494d3c2acc8a3b17abcd1208c30c2758d8481013cc3c4eff445d07b5',
'TS_RECOVERED_SEARCH_v2/MANIFEST.json':'4df5dbe4883ca4c8ee36513058472955f6d0b340874093b920afcf515b6f595e'}
out={'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'prior_attempt_exists':(R/'attempt').exists(),'prior_launch_exists':(R/'launch_evidence.json').exists(),'expected_checks':[]}
for p,h in expected.items():out['expected_checks'].append({'path':p,'observed':sha(B/p),'expected':h})
F=json.loads((R/'FREEZE.json').read_text());M=json.loads((R/'MANIFEST.json').read_text())
checks={}
for row in F['identities']+M['files']:
 p=pathlib.Path(row['path']) if row.get('external') else R/row['path']
 if str(p) in checks:continue
 checks[str(p)]={'bytes':p.stat().st_size,'sha256':sha(p),'expected_bytes':row['bytes'],'expected_sha256':row['sha256']}
out['identity_checks']=checks
matches=[];unreadable=[];scripts=set(F['guard_script_paths'])
for d in pathlib.Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  raw=(d/'cmdline').read_bytes();args=[x.decode(errors='replace') for x in raw.rstrip(b'\0').split(b'\0')] if raw else []
  direct=[x for x in args if x in scripts]
  embedded=[i for i,x in enumerate(args) if any(s in x for s in scripts)]
  exe0=pathlib.Path(args[0]).name if args else ''
  suspicious=exe0.startswith('perl') or any(pathlib.Path(x).name in ('broker.py','profile.pl','run_profile.py','launch.py') for x in args)
  if direct or embedded or suspicious:
   stat=(d/'stat').read_text();rest=stat[stat.rfind(')')+2:].split()
   ns=[x for x in (d/'status').read_text().splitlines() if x.startswith(('Name:','State:','NSpid:','NSpgid:'))]
   matches.append({'visible_pid':int(d.name),'starttime':rest[19],'namespace':os.readlink(d/'ns/pid'),'status':ns,'exe0':exe0,'direct':direct,'embedded_argument_indices':embedded,'suspicious':suspicious})
 except (FileNotFoundError,ProcessLookupError):continue
 except PermissionError:unreadable.append(int(d.name))
out['process_matches']=matches;out['unreadable_proc']=unreadable
out['memory']={k:(pathlib.Path('/sys/fs/cgroup')/k).read_text() for k in ['memory.current','memory.max','memory.events','memory.stat']}
out['memory_gate']=out['memory']['memory.max'].strip()=='8589934592' and int(out['memory']['memory.current'])<5468942336
out['all_identities_match']=all(x['bytes']==x['expected_bytes'] and x['sha256']==x['expected_sha256'] for x in checks.values()) and all(x['observed']==x['expected'] for x in out['expected_checks'])
out['go']=out['all_identities_match'] and out['memory_gate'] and not matches and not unreadable and not out['prior_attempt_exists'] and not out['prior_launch_exists']
out['elapsed']=time.monotonic()-t;out['utc_end']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(E/'external_preflight.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('identity_checks','memory')},indent=2))
print('IDENTITY_FILES',len(checks),'MEMORY_CURRENT',out['memory']['memory.current'].strip())
print('PREFLIGHT_SHA256',sha(E/'external_preflight.json'))

