"""Own harmless child stub. Sets frozen role limits, reports, waits. No foreign code."""
import os, sys, json, pathlib, resource, signal
B=pathlib.Path(__file__).resolve().parent
role, gate, out = sys.argv[1:]
assert role in ('broker','perl')
F=json.loads((B/'role_limits.json').read_text())
all_limits=lambda:{k:list(resource.getrlimit(getattr(resource,k))) for k in dir(resource) if k.startswith('RLIMIT_')}
before=all_limits()
for name,value in F[role].items():resource.setrlimit(getattr(resource,name),tuple(value))
def identity():
 s=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
 status=pathlib.Path('/proc/self/status').read_text()
 return {'visible_pid':int(os.readlink('/proc/self')),'local_pid':os.getpid(),'local_pgid':os.getpgrp(),'local_sid':os.getsid(0),'starttime':int(s[19]),'namespace':os.readlink('/proc/self/ns/pid'),'status':status}
def publish(name, value):
 p=pathlib.Path(out)/(role+'_'+name+'.json')
 with p.with_suffix('.tmp').open('x') as f:
  json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 os.rename(p.with_suffix('.tmp'),p)
ready={'identity':identity(),'before':before,'after':all_limits(),'proc_limits':pathlib.Path('/proc/self/limits').read_text(),'mode':'NO_FOREIGN_EXEC'}
publish('ready',ready)
token=os.read(int(gate),1);os.close(int(gate))
if token != b'G':raise SystemExit(3)
publish('released',{'identity':identity(),'after':all_limits(),'proc_limits':pathlib.Path('/proc/self/limits').read_text()})
if role=='broker':
 print('STUB_NORMAL_EXIT',flush=True)
 raise SystemExit(0)
# Exercises supervisor cleanup; no work or child creation.
while True:signal.pause()

