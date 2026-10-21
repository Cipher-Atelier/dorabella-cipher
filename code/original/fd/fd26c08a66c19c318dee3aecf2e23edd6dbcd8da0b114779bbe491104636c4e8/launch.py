"""Journal-diagnostic approval entrypoint, PREPARED ONLY. One attempt; exec retains one supervisor PID."""
from pathlib import Path
import os,sys,json,time,hashlib,datetime
B=Path(__file__).resolve().parent
if (B/'attempt').exists() or (B/'launch_evidence.json').exists():raise SystemExit('REFUSE_PRIOR_ATTEMPT')
start=time.monotonic();f=B/'FREEZE.json';freeze=json.loads(f.read_text())
if sys.executable!=freeze['python']:raise SystemExit('PYTHON_PATH')
ticks=os.sysconf('SC_CLK_TCK');stat=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
record={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'shell_command':freeze['launch_shell_command'],'freeze_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
 'clock_ticks_per_second':ticks,'launch_floor_ticks':int(stat[19])-10*ticks,
 'monotonic':start,'global_deadline':start+180,'launch_pid_local':os.getpid()}
with (B/'launch_evidence.json').open('x') as q:json.dump(record,q,indent=2);q.flush();os.fsync(q.fileno())
os.execve(sys.executable,[sys.executable,'-B','-I','-S',str(B/'run.py')],freeze['environment'])
