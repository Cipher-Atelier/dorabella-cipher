"""Fixed complete calibration with unchanged per-case search, bounded resources."""
from pathlib import Path
import subprocess,sys,json,time,datetime,os,concurrent.futures,hashlib
R=Path(__file__).resolve().parents[1]
CASES=json.loads((R/'inputs/cases.json').read_text())
def event(obj):
    obj={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**obj}
    with (R/'logs/events.jsonl').open('a') as f:f.write(json.dumps(obj)+'\n')
    print(json.dumps(obj),flush=True)
def run_case(c):
    remaining=DEADLINE-time.monotonic()
    if remaining<=0:raise TimeoutError('Total10800s budget exhausted; no next case started')
    name=c['id'];log=R/'logs'/f'{name}.log';event({'event':'begin','case':name})
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_NUM_THREADS='4')
    start=time.monotonic()
    with log.open('w') as f:
        try:r=subprocess.run([sys.executable,str(R/'code/worker.py'),name],stdout=f,stderr=subprocess.STDOUT,env=env,timeout=min(900,remaining))
        except subprocess.TimeoutExpired:
            event({'event':'timeout','case':name,'seconds':time.monotonic()-start});raise
    if r.returncode:raise RuntimeError(f'{name}: exit{r.returncode}; see log')
    dest=R/'runs'/name/(name+'.json');assert dest.exists()
    d=json.loads(dest.read_text());assert d['first_count']==1665
    event({'event':'complete','case':name,'seconds':time.monotonic()-start,'score':d['best_score'],'accuracy':d.get('accuracy')})
    return d
def compare_regression():
    # Exhaustive comparison of all saved first/middle/final candidates for positive00.
    now=R/'runs/positive_00';old=R/'archived_wordall';count=0;maxerr=0.
    for stage in ['first','middle','final']:
        ns=now/stage/'positive_00';osrc=old/stage/'positive_00'
        assert sorted(p.name for p in ns.glob('*.json'))==sorted(p.name for p in osrc.glob('*.json'))
        for p in ns.glob('*.json'):
            a=json.loads(p.read_text());b=json.loads((osrc/p.name).read_text())
            assert a['decoded']==b['decoded'] and a['key']==b['key'] and a['seed']==b['seed']
            err=abs(a['score']-b['score']);maxerr=max(maxerr,err);assert err<1e-9;count+=1
    a=json.loads((now/'positive_00.json').read_text());b=json.loads((old/'positive_00.json').read_text())
    assert a['best_text']==b['best_text'] and a['first_top_routes']==b['first_top_routes'] and a['accuracy']==b['accuracy']
    out=dict(status='PASS',candidate_records=count,max_score_error=maxerr,accuracy=a['accuracy'],source='archived full wordall positive00')
    (R/'checks/runtime_equivalence.json').write_text(json.dumps(out,indent=2)+'\n');event({'event':'runtime_equivalence',**out})
if __name__=='__main__':
    freeze=json.loads((R/'freeze.json').read_text())
    for name,h in freeze['hashes'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h
    subprocess.run([sys.executable,str(R/'code/preflight.py')],check=True)
    start=time.monotonic();DEADLINE=start+10800;event({'event':'calibration_started','case_count':52,'deadline_seconds':10800})
    try:
        run_case(next(z for z in CASES if z['id']=='positive_00'));compare_regression()
        rest=[z for z in CASES if z['id']!='positive_00']
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            # At most two case processes (4 route workers each). No discarded runs.
            futures=[pool.submit(run_case,z) for z in rest]
            for f in concurrent.futures.as_completed(futures,timeout=max(1,10800-(time.monotonic()-start))):f.result()
        status=dict(status='completed',cases=52,wall_seconds=time.monotonic()-start)
    except Exception as e:
        status=dict(status='incomplete',error=repr(e),wall_seconds=time.monotonic()-start)
        (R/'STATUS.json').write_text(json.dumps(status,indent=2));event(status);raise
    (R/'STATUS.json').write_text(json.dumps(status,indent=2));event(status)
