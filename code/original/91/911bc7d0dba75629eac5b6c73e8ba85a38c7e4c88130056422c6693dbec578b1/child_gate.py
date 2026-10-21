"""Prepared exec gate; resource limits set before foreign import or exec."""
import os,sys,json,resource,pathlib
B=pathlib.Path(__file__).resolve().parent;R=B.parent;F=json.loads((R/'FREEZE.json').read_text())
role,gate,*ipc=sys.argv[1:];assert role in ('broker','perl') and len(ipc)==4
for name,value in F['role_limits'][role].items():resource.setrlimit(getattr(resource,name),tuple(value))
A=pathlib.Path(os.environ['TS_ATTEMPT']);ready={'local_pid':os.getpid(),'local_pgid':os.getpgrp(),'local_sid':os.getsid(0),'visible_pid':int(os.readlink('/proc/self')),'namespace':os.readlink('/proc/self/ns/pid'),'status':pathlib.Path('/proc/self/status').read_text(),'stat':pathlib.Path('/proc/self/stat').read_text(),'limits':{k:list(resource.getrlimit(getattr(resource,k))) for k in F['role_limits'][role]}}
with (A/(role+'_ready.json')).open('x') as f:json.dump(ready,f,sort_keys=True);f.write('\n')
token=os.read(int(gate),1);os.close(int(gate))
if token!=b'G':raise SystemExit(3)
env=dict(F['environment']);env.update({k:v for k,v in os.environ.items() if k.startswith('TS_')})
if role=='broker':cmd=[F['python'],'-B','-I','-S',str(B/'broker.py'),*ipc]
else:
 env.update(dict(zip(['TS_LM_R','TS_LM_W','TS_PAT_R','TS_PAT_W'],ipc)))
 cmd=[F['perl'],'-I',str(B/'original'),'-I',str(B),str(B/'profile.pl'),*F['solver_argv'],str(R/'ciphertext.txt')]
os.chdir(A/'work');os.execve(cmd[0],cmd,env)
