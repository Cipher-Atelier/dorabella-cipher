"""Own gate stub. Sets frozen limits before exec; no imports of author code."""
import os,sys,pathlib,json,resource,time,select
B=pathlib.Path(__file__).resolve().parent;R=B.parent
sys.path[:0]=[str(B),str(B/'reused')]
from common import put
from namespace_view import NamespaceView
role,gate,*ipc=sys.argv[1:];gate=int(gate);ipc=list(map(int,ipc));A=pathlib.Path(os.environ['BE_ATTEMPT']);end=float(os.environ['BE_DEADLINE']);F=json.loads((R/'FREEZE.json').read_text())
if role not in ('broker','perl') or len(ipc)!=2:raise SystemExit('CHILD_ARGUMENTS')
for name,pair in F['role_limits'][role].items():
 old=resource.getrlimit(getattr(resource,name))
 if old[1]!=resource.RLIM_INFINITY and pair[1]>old[1]:raise SystemExit('CHILD_INHERITED_HARD')
for name,pair in F['role_limits'][role].items():resource.setrlimit(getattr(resource,name),tuple(pair))
limits={n:list(resource.getrlimit(getattr(resource,n))) for n in F['role_limits'][role]}
ns=NamespaceView();me=ns.self_record
put(A/(role+'_ready.json'),{'record':me,'limits':limits,'role':role,'closed_before_release':True})
while True:
 if time.monotonic()>=end:raise SystemExit('INCOMPLETE_BUDGET_GATE')
 if select.select([gate],[],[],.05)[0]:
  if os.read(gate,2)!=b'G':raise SystemExit('RELEASE_REJECTED')
  os.close(gate);break
for fd in ipc:os.set_inheritable(fd,True)
if role=='broker':cmd=[F['python'],'-B','-I','-S',str(B/'broker.py'),*map(str,ipc)]
else:
 os.environ['BE_READ'],os.environ['BE_WRITE']=map(str,ipc)
 cmd=[F['perl'],'-I'+str(B/'original'),'-I'+str(B),str(B/'driver.pl')]
 if os.environ['BE_MODE']=='search':cmd.append(str(A/'decoder_input.json'))
os.execve(cmd[0],cmd,dict(os.environ))
