"""Own gated exec launcher. One exec of unchanged original modules via fixture harness."""
from pathlib import Path
import os,sys,json,resource

base=Path(__file__).resolve().parent
freeze=json.loads((base/'FREEZE.json').read_text())
attempt=base/'attempt'
for key,pair in [('RLIMIT_AS',(536870912,536870912)),('RLIMIT_CPU',(25,28)),
                 ('RLIMIT_FSIZE',(16777216,16777216)),('RLIMIT_CORE',(0,0)),('RLIMIT_NOFILE',(64,64))]:
    resource.setrlimit(getattr(resource,key),pair)
ready={'pid_local':os.getpid(),'pgid_local':os.getpgrp(),'sid_local':os.getsid(0),
       'visible_self':int(os.readlink('/proc/self')),'pid_namespace':os.readlink('/proc/self/ns/pid'),
       'proc_status':Path('/proc/self/status').read_text(),'proc_stat':Path('/proc/self/stat').read_text(),
       'proc_limits':Path('/proc/self/limits').read_text(),
       'limits':{k:resource.getrlimit(getattr(resource,k)) for k in
                 ['RLIMIT_AS','RLIMIT_CPU','RLIMIT_FSIZE','RLIMIT_CORE','RLIMIT_NOFILE']}}
tmp=attempt/'ready.tmp';tmp.write_text(json.dumps(ready,indent=2)+'\n');os.replace(tmp,attempt/'ready.json')
gate=int(sys.argv[1])
token=os.read(gate,1);os.close(gate)
if token!=b'G':raise SystemExit(3)
os.chdir(attempt/'work')
os.execve(freeze['author_argv'][0],freeze['author_argv'],freeze['environment'])
