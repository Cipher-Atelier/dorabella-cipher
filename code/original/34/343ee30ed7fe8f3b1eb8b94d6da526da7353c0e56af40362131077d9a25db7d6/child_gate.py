"""Own gated launcher; no import of author/glue code until approved execution."""
from pathlib import Path
import os, sys, json, resource
base=Path(__file__).resolve().parent
role,gate,*ipc=sys.argv[1:]
if role not in ('reference','adapted','broker'): raise SystemExit('ROLE')
freeze=json.loads((base/'FREEZE.json').read_text())
limits=freeze['limits']['child']
for key,pair in limits.items(): resource.setrlimit(getattr(resource,key),tuple(pair))
ready={'pid_local':os.getpid(),'pgid_local':os.getpgrp(),'sid_local':os.getsid(0),
       'visible_self':int(os.readlink('/proc/self')),'pid_namespace':os.readlink('/proc/self/ns/pid'),
       'proc_status':Path('/proc/self/status').read_text(),'proc_stat':Path('/proc/self/stat').read_text(),
       'proc_limits':Path('/proc/self/limits').read_text(),
       'limits':{k:resource.getrlimit(getattr(resource,k)) for k in limits}}
p=base/'attempt'/f'{role}_ready.json'
tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(ready,indent=2)+'\n');os.replace(tmp,p)
token=os.read(int(gate),1);os.close(int(gate))
if token!=b'G': raise SystemExit(3)
if role=='broker':
    argv=[freeze['python'],'-I','-S',str(base/'broker.py')]
else:
    argv=[freeze['perl'],'-I',str(base/'original'),'-I',str(base),
          str(base/'differential.pl'),role,str(base/'fixtures'),*ipc]
os.chdir(base/'attempt/work')
os.execve(argv[0],argv,freeze['environment'])
