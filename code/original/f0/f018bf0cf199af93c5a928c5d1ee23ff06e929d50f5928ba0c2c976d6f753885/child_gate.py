"""Prepared bounded exec. No release token means exit, no author execution."""
from pathlib import Path
import os,sys,json,resource
B=Path(__file__).resolve().parent
role,gate,*ipc=sys.argv[1:];f=json.loads((B/'FREEZE.json').read_text());spec=f['roles'][role]
for k,v in f['limits'][spec['limit_class']].items():resource.setrlimit(getattr(resource,k),tuple(v))
ready={'pid_local':os.getpid(),'pgid_local':os.getpgrp(),'sid_local':os.getsid(0),
 'visible_self':int(os.readlink('/proc/self')),'pid_namespace':os.readlink('/proc/self/ns/pid'),
 'proc_status':Path('/proc/self/status').read_text(),'proc_stat':Path('/proc/self/stat').read_text(),
 'proc_limits':Path('/proc/self/limits').read_text(),
 'limits':{k:resource.getrlimit(getattr(resource,k)) for k in f['limits'][spec['limit_class']]}}
p=B/'attempt'/f'{role}_ready.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(ready));os.replace(tmp,p)
token=os.read(int(gate),1);os.close(int(gate))
if token!=b'G':raise SystemExit(3)
if role.endswith('_broker'):
 if ipc:raise SystemExit('IPC_ARGS')
 argv=[f['python'],'-B','-I','-S',str(B/'broker.py'),role]
else:
 args={'reference_perl':['reference',str(B/'fixtures/base')],
       'adapted_perl':['adapted',str(B/'fixtures/base')],
       'real_perl':[str(B)]}[role]
 if len(ipc)!=(0 if role=='reference_perl' else 2):raise SystemExit('IPC_ARGS')
 argv=[f['perl'],'-I',str(B/'original'),'-I',str(B),str(B/spec['program']),*args,*ipc]
os.chdir(B/'attempt/work');os.execve(argv[0],argv,f['environment'])
