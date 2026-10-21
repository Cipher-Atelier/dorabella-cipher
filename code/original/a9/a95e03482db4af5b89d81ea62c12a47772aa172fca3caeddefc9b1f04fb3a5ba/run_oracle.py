"""One 30s fixture differential; no solver, numeric model, retry or target."""
from pathlib import Path
import os,sys,json,time,datetime,hashlib,resource,subprocess,signal,traceback
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from namespace_view import NamespaceView,Stop
ATTEMPT=BASE/'attempt'

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(name,value):
    p=ATTEMPT/name;q=p.with_suffix(p.suffix+'.tmp')
    with q.open('w') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(q,p)
def memory():
    return {k:(Path('/sys/fs/cgroup')/k).read_text().strip() for k in
            ['memory.max','memory.current','memory.events']}
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for buf in iter(lambda:f.read(1048576),b''):h.update(buf)
    return h.hexdigest()

def main():
    if ATTEMPT.exists():print('REFUSED_EXISTING_ORACLE_ATTEMPT');return 3
    ATTEMPT.mkdir();(ATTEMPT/'work').mkdir()
    start=time.monotonic();deadline=start+30
    result={'version':'TS-ORIGINAL-ORACLE-v1','status':'INCOMPLETE','start_utc':utc(),
            'author_invocations':0,'solver_calls':0,'score_calls':0,'target_inputs':0,'signals':[]}
    dump('T0.json',{'utc':result['start_utc'],'monotonic':start,'deadline':deadline})
    p=None;anchor=None;known=set();ns=None;gate_read=gate_write=None;logs=[]
    def tick():
        if time.monotonic()>=deadline:raise Stop('STOP_WALL_DEADLINE')
        if int(memory()['memory.current'])>=15*1024**3//2:raise Stop('STOP_SHARED_MEMORY')
        for name in ['stdout.jsonl','stderr.txt']:
            path=ATTEMPT/name
            if path.exists() and path.stat().st_size>16777216:raise Stop('STOP_OUTPUT_BOUND')
    def signal_owned(sig):
        # Only the gated, directly owned group identified before any author exec.
        members=ns.group(anchor,known)
        current=ns.read_visible(anchor['visible_pid'])
        if current and current['starttime']!=anchor['starttime']:raise Stop('STOP_PID_REUSED')
        if anchor['pid']==os.getpgrp():raise Stop('STOP_SELF_GROUP')
        if members:
            try:os.killpg(anchor['pid'],sig)
            except ProcessLookupError:pass
        result['signals'].append({'utc':utc(),'signal':int(sig),'local_pgid':anchor['pid'],'members':members})
    try:
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        freeze=json.loads((BASE/'FREEZE.json').read_text())
        result['before']=memory()
        if result['before']['memory.max']!='8589934592' or int(result['before']['memory.current'])>7*1024**3:
            raise Stop('STOP_RESOURCE_GATE')
        for it in freeze['identities']:
            q=Path(it['path'])
            if q.stat().st_size!=it['bytes'] or digest(q)!=it['sha256']:raise Stop('STOP_HASH:'+q.name)
            tick()
        ns=NamespaceView();result['namespace_self']=ns.self_record
        prior=[]
        for row in ns.snapshot():
            args=row['cmdline']
            if any(x==str(BASE/'original_module_oracle.pl') or x==str(BASE/'child_gate.py') for x in args[1:]):prior.append(row)
        if prior:raise Stop('STOP_PREVIOUS_LIVE_ATTEMPT')
        result['previous_live_matches']=prior
        result['hashes_verified']=True
        gate_read,gate_write=os.pipe()
        stdout=(ATTEMPT/'stdout.jsonl').open('wb');stderr=(ATTEMPT/'stderr.txt').open('wb');logs=[stdout,stderr]
        p=subprocess.Popen([freeze['python'],'-I','-S',str(BASE/'child_gate.py'),str(gate_read)],
                           pass_fds=(gate_read,),start_new_session=True,stdin=subprocess.DEVNULL,
                           stdout=stdout,stderr=stderr,env=freeze['environment'],cwd=ATTEMPT/'work')
        os.close(gate_read);gate_read=None
        while not (ATTEMPT/'ready.json').exists():
            tick()
            if p.poll() is not None:raise Stop('STOP_LAUNCHER_BEFORE_READY')
            time.sleep(.02)
        ready=json.loads((ATTEMPT/'ready.json').read_text())
        anchor=ns.by_local(p.pid)
        if not anchor or anchor['visible_ppid']!=ns.visible_self or anchor['pid_namespace']!=ns.ns:
            raise Stop('STOP_DIRECT_CHILD_IDENTITY')
        if (anchor['pid'],anchor['pgid'],anchor['session'])!=(p.pid,p.pid,p.pid):raise Stop('STOP_OWN_GROUP_IDENTITY')
        if os.getpgid(p.pid)!=p.pid or p.pid==os.getpgrp():raise Stop('STOP_GROUP_ADDRESSING')
        if (ready['pid_local'],ready['pgid_local'],ready['sid_local'],ready['visible_self'],ready['pid_namespace']) != (
                p.pid,p.pid,p.pid,anchor['visible_pid'],ns.ns):raise Stop('STOP_READY_MAPPING')
        expected={'RLIMIT_AS':[536870912,536870912],'RLIMIT_CPU':[25,28],
                  'RLIMIT_FSIZE':[16777216,16777216],'RLIMIT_CORE':[0,0],'RLIMIT_NOFILE':[64,64]}
        if ready['limits']!=expected:raise Stop('STOP_LIMITS')
        known.add((anchor['visible_pid'],anchor['starttime']))
        result['anchor_before_exec']=anchor;result['applied_limits']=ready['limits']
        result['group_before_exec']=ns.group(anchor,known)
        result['author_exec_release_utc']=utc();result['release_elapsed']=time.monotonic()-start
        result['author_invocations']=1
        os.write(gate_write,b'G');os.close(gate_write);gate_write=None
        while p.poll() is None:
            tick();group=ns.group(anchor,known)
            with (ATTEMPT/'observations.jsonl').open('a') as obs:
                obs.write(json.dumps({'utc':utc(),'elapsed':time.monotonic()-start,'group':group,'memory':memory()})+'\n')
            time.sleep(.05)
        result['observed_exit']=p.returncode
        for f in logs:f.close()
        logs=[]
        result['terminal_group']=ns.group(anchor,known)
        if result['terminal_group']:raise Stop('STOP_NONEMPTY_TERMINAL_GROUP')
        result['terminal_confirmed']=True
        if p.returncode!=0:raise Stop('STOP_AUTHOR_EXIT')
        if (ATTEMPT/'stderr.txt').stat().st_size:raise Stop('STOP_STDERR')
        lines=(ATTEMPT/'stdout.jsonl').read_bytes().splitlines()
        if len(lines)!=2:raise Stop('STOP_RESULT_COUNT')
        comparisons=[]
        for i,(line,expected_path) in enumerate(zip(lines,freeze['expected_jsons'])):
            actual=json.loads(line);expected=json.loads(Path(expected_path).read_text())
            if actual!=expected:raise Stop('STOP_EXACT_DIFFERENCE')
            # Full structures, no sample, no tolerance, no string coercion.
            comparisons.append({'case':i+1,'groups':len(actual['groups']),
                                'candidates':sum(len(v) for v in actual['groups'].values() if v is not None),
                                'words':len(actual['words']),'maxlen':actual['maxlen'],
                                'segmentations':len(actual['segmentation']),'exact':True})
        tick()
        result['comparisons']=comparisons
        result['status']='PASS_ORIGINAL_MODULE_FIXTURES_ONLY'
        code=0
    except BaseException as e:
        result['status']='STOP';result['error']=repr(e);result['traceback']=traceback.format_exc();code=2
        # A closed gate means no author exec. Never substitute unproven host PIDs.
        if gate_write is not None:os.close(gate_write);gate_write=None
        if p is not None and p.poll() is None:
            try:
                if anchor is not None:
                    signal_owned(signal.SIGTERM)
                    try:p.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        signal_owned(signal.SIGKILL);p.wait(timeout=2)
                else:
                    # Child gate has EOF and exits itself; no unverified signals.
                    p.wait(timeout=2)
            except BaseException as stop_error:
                result['termination_error']=repr(stop_error);result['status']='UNKNOWN'
        if p is not None:
            result['observed_exit']=p.poll()
            try:
                result['terminal_group']=ns.group(anchor,known) if anchor else None
                result['terminal_confirmed']=p.returncode is not None and (not result['terminal_group'])
            except BaseException as error:result['terminal_read_error']=repr(error)
    finally:
        for fd in [gate_read,gate_write]:
            if fd is not None:os.close(fd)
        for f in logs:f.close()
    result['elapsed']=time.monotonic()-start;result['end_utc']=utc()
    result['children_ru_maxrss_KiB']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    result['after']=memory()
    result['file_hashes']={q.name:digest(q) for q in ATTEMPT.iterdir() if q.is_file() and q.name!='result.json'}
    dump('result.json',result)
    print(json.dumps({k:result.get(k) for k in ['status','elapsed','observed_exit','children_ru_maxrss_KiB','comparisons','error','terminal_confirmed']}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
