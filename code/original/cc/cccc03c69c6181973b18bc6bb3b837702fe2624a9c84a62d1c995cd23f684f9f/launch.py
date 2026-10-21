"""NEW recovered one-attempt launcher. Do not execute before approval."""
import time
T0=time.monotonic()
import pathlib,os,json,datetime,hashlib,sys
B=pathlib.Path(__file__).resolve().parent;R=B.parent
if (R/'attempt').exists() or (R/'launch_evidence.json').exists():raise SystemExit('REFUSED_PREVIOUS_ATTEMPT')
F=json.loads((R/'FREEZE.json').read_text())
payload={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monotonic':T0,'global_deadline':T0+180,'work_deadline':T0+130,'clock_ticks_per_second':os.sysconf('SC_CLK_TCK'),'launch_floor_ticks':int((float(pathlib.Path('/proc/uptime').read_text().split()[0])-10)*os.sysconf('SC_CLK_TCK')),'shell_command':F['launch_shell_command'],'freeze_sha256':hashlib.sha256((R/'FREEZE.json').read_bytes()).hexdigest()}
with (R/'launch_evidence.json').open('x') as f:json.dump(payload,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
print('ATTEMPT_START '+json.dumps(payload,sort_keys=True),flush=True)
os.execve(F['python'],[F['python'],'-B','-I','-S',str(B/'run_profile.py')],F['environment'])
