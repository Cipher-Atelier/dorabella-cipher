"""Prepared gated exec for the six named roles only; no new execution during preparation."""
from pathlib import Path
import os,sys,json,resource
BASE=Path(__file__).resolve().parent
role,gate,*ipc=sys.argv[1:]
freeze=json.loads((BASE/'FREEZE.json').read_text())
if role not in freeze['roles']:raise SystemExit('ROLE')
spec=freeze['roles'][role]
limits=freeze['limits'][spec['limit_class']]
for key,pair in limits.items():resource.setrlimit(getattr(resource,key),tuple(pair))
ready={'pid_local':os.getpid(),'pgid_local':os.getpgrp(),'sid_local':os.getsid(0),
 'visible_self':int(os.readlink('/proc/self')),'pid_namespace':os.readlink('/proc/self/ns/pid'),
 'proc_status':Path('/proc/self/status').read_text(),'proc_stat':Path('/proc/self/stat').read_text(),
 'proc_limits':Path('/proc/self/limits').read_text(),
 'limits':{k:resource.getrlimit(getattr(resource,k)) for k in limits}}
p=BASE/'attempt'/f'{role}_ready.json';tmp=p.with_suffix('.tmp')
tmp.write_text(json.dumps(ready,indent=2)+'\n');os.replace(tmp,p)
token=os.read(int(gate),1);os.close(int(gate))
if token!=b'G':raise SystemExit(3)
if role.endswith('_broker'):
 if ipc:raise SystemExit('IPC_ARGS')
 argv=[freeze['python'],'-I','-S',str(BASE/'broker.py'),role]
else:
 if len(ipc)!=2:raise SystemExit('IPC_ARGS')
 args={'fixture_perl':['adapted',str(BASE/'fixtures')],
       'large_perl':[str(BASE)],'profile_perl':[str(BASE)]}[role]
 argv=[freeze['perl'],'-I',str(BASE/'original'),'-I',str(BASE),str(BASE/spec['program']),*args,*ipc]
os.chdir(BASE/'attempt/work')
os.execve(argv[0],argv,freeze['environment'])
