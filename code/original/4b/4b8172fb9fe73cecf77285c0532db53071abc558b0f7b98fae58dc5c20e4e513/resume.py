"""Technical recovery after host process loss; original algorithm/budgets untouched.
Only current-run completed checkpoints are reused. Original absolute wall cap
and cumulative per-case wall limits are retained, including interruption time.
"""
from pathlib import Path
import subprocess,sys,json,time,datetime,os,concurrent.futures,threading,hashlib
R=Path(__file__).resolve().parents[1]
events=[json.loads(s) for s in (R/'logs/events.jsonl').read_text().splitlines()]
start=next(datetime.datetime.fromisoformat(e['utc']) for e in events if e['event']=='calibration_started')
deadline=start+datetime.timedelta(seconds=10800)
done={e['case'] for e in events if e['event']=='complete'}
began={e['case']:datetime.datetime.fromisoformat(e['utc']) for e in events if e['event']=='begin'}
cases=json.loads((R/'inputs/cases.json').read_text());remaining=[c for c in cases if c['id'] not in done]
STOP=threading.Event();LOCK=threading.Lock();ACTIVE={}
def now():return datetime.datetime.now(datetime.timezone.utc)
def event(obj):
    obj={'utc':now().isoformat(),**obj}
    with LOCK:
        with (R/'logs/events.jsonl').open('a') as f:f.write(json.dumps(obj)+'\n')
        print(json.dumps(obj),flush=True)
def run_case(c):
    if STOP.is_set():raise RuntimeError('Aborted after technical failure')
    name=c['id'];is_resume=name in began;case_elapsed=(now()-began[name]).total_seconds() if is_resume else 0.
    allowed=min(900-case_elapsed,(deadline-now()).total_seconds())
    if allowed<=0:raise TimeoutError('Original cumulative resource cap exhausted')
    event({'event':'resume' if is_resume else 'begin','case':name,'timeout_remaining':allowed})
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_NUM_THREADS='4')
    t=time.monotonic()
    with (R/'logs'/f'{name}.log').open('a') as f:
        p=subprocess.Popen([sys.executable,str(R/'code/worker.py'),name],stdout=f,stderr=subprocess.STDOUT,env=env)
        with LOCK:ACTIVE[name]=p
        try:
            code=p.wait(timeout=allowed)
            if code:raise RuntimeError(f'{name}: exit{code}')
        except BaseException:
            STOP.set()
            with LOCK:
                for q in ACTIVE.values():
                    if q.poll() is None:q.kill()
            raise
        finally:
            with LOCK:ACTIVE.pop(name,None)
    rec=json.loads((R/'runs'/name/(name+'.json')).read_text());assert rec['first_count']==1665
    event({'event':'complete','case':name,'seconds':case_elapsed+time.monotonic()-t,'score':rec['best_score'],'accuracy':rec.get('accuracy'),'resumed':is_resume})
if __name__=='__main__':
    f=json.loads((R/'freeze.json').read_text())
    for n,h in f['hashes'].items():assert hashlib.sha256((R/n).read_bytes()).hexdigest()==h
    subprocess.run([sys.executable,str(R/'code/preflight.py')],check=True)
    assert json.loads((R/'checks/runtime_equivalence.json').read_text())['status']=='PASS'
    event({'event':'technical_recovery','already_complete':len(done),'remaining':len(remaining),'absolute_deadline':deadline.isoformat()})
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(run_case,z) for z in remaining]
            for job in concurrent.futures.as_completed(jobs):job.result()
        status={'status':'completed','cases':52,'wall_seconds':(now()-start).total_seconds(),'technical_interruption_recovered':True}
    except BaseException as e:
        status={'status':'incomplete','error':repr(e),'wall_seconds':(now()-start).total_seconds(),'technical_interruption_recovered':False}
        (R/'STATUS.json').write_text(json.dumps(status,indent=2));event(status);raise
    (R/'STATUS.json').write_text(json.dumps(status,indent=2));event(status)
