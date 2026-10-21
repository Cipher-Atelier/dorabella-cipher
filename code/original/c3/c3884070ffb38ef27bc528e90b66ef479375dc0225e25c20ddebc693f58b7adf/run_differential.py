"""PREPARED ONLY. One fixed differential attempt; requires separate user approval."""
from pathlib import Path
import os, sys, json, time, datetime, hashlib, resource, subprocess, signal, traceback
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from namespace_view import NamespaceView, Stop
ATTEMPT=BASE/'attempt'

def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()
def memory():
    return {k:(Path('/sys/fs/cgroup')/k).read_text().strip()
            for k in ('memory.max','memory.current','memory.events')}
def dump(name,value):
    p=ATTEMPT/name;tmp=p.with_suffix(p.suffix+'.tmp')
    with tmp.open('w') as f:
        json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def main():
    if ATTEMPT.exists(): print('REFUSED_EXISTING_ATTEMPT');return 3
    ATTEMPT.mkdir();(ATTEMPT/'work').mkdir()
    start=time.monotonic();deadline=start+60
    result={'version':'TS-DIFF-BRIDGE-v1','status':'INCOMPLETE','start_utc':utc(),
            'commands':[],'signals':[],'phases':[],'target_inputs':0,'full_model_loads':0}
    dump('T0.json',{'utc':result['start_utc'],'monotonic':start,'deadline':deadline})
    children=[];handles=[];parent_fds=set();ns=None
    def tick():
        if time.monotonic()>=deadline: raise Stop('STOP_WALL_DEADLINE')
        if int(memory()['memory.current'])>=15*1024**3//2: raise Stop('STOP_SHARED_MEMORY')
        for p in ATTEMPT.iterdir():
            if p.is_file() and p.stat().st_size>8388608: raise Stop('STOP_OUTPUT_BOUND')
        active=0
        for child in children:
            p=child['p']
            if p.poll() is None: active+=1
            if child['anchor'] is not None:
                group=ns.group(child['anchor'],child['known'])
                if len(group)>1: raise Stop('STOP_UNEXPECTED_DESCENDANT')
        if active>2: raise Stop('STOP_PROCESS_COUNT')
    def log_handle(name):
        f=(ATTEMPT/name).open('xb');handles.append(f);return f
    def close_fd(fd):
        if fd in parent_fds: os.close(fd);parent_fds.remove(fd)
    def pipe():
        pair=os.pipe();parent_fds.update(pair);return pair
    def launch(role,stdin,stdout,ipc=()):
        tick()
        gr,gw=pipe()
        argv=[freeze['python'],'-I','-S',str(BASE/'child_gate.py'),role,str(gr),*map(str,ipc)]
        stderr=log_handle(role+'_stderr.txt')
        p=subprocess.Popen(argv,stdin=stdin,stdout=stdout,stderr=stderr,
            pass_fds=(gr,*ipc),start_new_session=True,cwd=ATTEMPT/'work',env=freeze['environment'])
        child={'p':p,'role':role,'anchor':None,'known':set(),'gate':gw}
        children.append(child);close_fd(gr)
        result['commands'].append({'role':role,'launcher_argv':argv,'pid_local':p.pid,
                                   'start_observed_utc':utc()})
        ready_path=ATTEMPT/(role+'_ready.json')
        while not ready_path.exists():
            tick()
            if p.poll() is not None: raise Stop('STOP_BEFORE_READY:'+role)
            time.sleep(.02)
        ready=json.loads(ready_path.read_text());a=ns.by_local(p.pid)
        if not a or a['visible_ppid']!=ns.visible_self or a['pid_namespace']!=ns.ns:
            raise Stop('STOP_CHILD_IDENTITY:'+role)
        if (a['pid'],a['pgid'],a['session'])!=(p.pid,p.pid,p.pid): raise Stop('STOP_GROUP_IDENTITY')
        if os.getpgid(p.pid)!=p.pid or p.pid==os.getpgrp(): raise Stop('STOP_ADDRESSING')
        if (ready['pid_local'],ready['pgid_local'],ready['sid_local'],ready['visible_self'],ready['pid_namespace']) != (
                p.pid,p.pid,p.pid,a['visible_pid'],ns.ns): raise Stop('STOP_NAMESPACE_MAPPING')
        if ready['limits']!=freeze['limits']['child']: raise Stop('STOP_LIMITS')
        child['anchor']=a;child['known'].add((a['visible_pid'],a['starttime']))
        ns.group(a,child['known'])
        result['commands'][-1]['anchor']=a
        return child
    def release(child):
        tick();os.write(child['gate'],b'G');close_fd(child['gate']);child['gate']=None
        result['phases'].append({'release':child['role'],'utc':utc(),'elapsed':time.monotonic()-start})
    def observe_until_done(batch):
        while any(c['p'].poll() is None for c in batch):
            tick()
            rec={'utc':utc(),'elapsed':time.monotonic()-start,'memory':memory(),
                 'groups':{c['role']:ns.group(c['anchor'],c['known']) for c in batch}}
            with (ATTEMPT/'observations.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
            time.sleep(.05)
        tick()
        for c in batch:
            group=ns.group(c['anchor'],c['known'])
            result['phases'].append({'terminal':c['role'],'exit':c['p'].returncode,
                'group':group,'utc':utc(),'elapsed':time.monotonic()-start})
            if group or c['p'].returncode!=0: raise Stop('STOP_EXIT_OR_GROUP:'+c['role'])
            if (ATTEMPT/(c['role']+'_stderr.txt')).stat().st_size: raise Stop('STOP_STDERR:'+c['role'])
    def signal_owned(child,sig):
        a=child['anchor']
        group=ns.group(a,child['known'])
        now=ns.read_visible(a['visible_pid'])
        if now and now['starttime']!=a['starttime']: raise Stop('STOP_PID_REUSE')
        if a['pid']==os.getpgrp(): raise Stop('STOP_SELF_GROUP')
        if group:
            try:os.killpg(a['pid'],sig)
            except ProcessLookupError:pass
        result['signals'].append({'role':child['role'],'signal':int(sig),'group':group,'utc':utc()})
    try:
        freeze=json.loads((BASE/'FREEZE.json').read_text())
        result['manifest_sha256']=digest(BASE/'FREEZE.json')
        for k,v in freeze['limits']['supervisor'].items():resource.setrlimit(getattr(resource,k),tuple(v))
        if sys.version_info[:3]!=(3,12,14):raise Stop('STOP_PYTHON_VERSION')
        result['before']=memory()
        if result['before']['memory.max']!='8589934592' or int(result['before']['memory.current'])>7*1024**3:
            raise Stop('STOP_RESOURCE_GATE')
        for entry in freeze['identities']:
            p=Path(entry['path']) if entry['external'] else BASE/entry['path']
            if p.stat().st_size!=entry['bytes'] or digest(p)!=entry['sha256']:raise Stop('STOP_HASH:'+str(p))
            tick()
        ns=NamespaceView();result['namespace_self']=ns.self_record
        matches=[r for r in ns.snapshot() if any(
            str(BASE/name) in r['cmdline'] for name in ('child_gate.py','broker.py','differential.pl'))]
        result['prior_live_matches']=matches
        if matches:raise Stop('STOP_PREVIOUS_LIVE_PROCESS')
        result['hashes_verified']=True
        reference=launch('reference',subprocess.DEVNULL,log_handle('reference.jsonl'))
        release(reference);observe_until_done([reference])
        request_read,request_write=pipe();response_read,response_write=pipe()
        broker=launch('broker',request_read,response_write)
        adapted=launch('adapted',subprocess.DEVNULL,log_handle('adapted.jsonl'),(response_read,request_write))
        for fd in (request_read,request_write,response_read,response_write):close_fd(fd)
        release(broker);release(adapted);observe_until_done([broker,adapted])
        for h in handles:h.close()
        handles=[]
        reference_raw=(ATTEMPT/'reference.jsonl').read_bytes();adapted_raw=(ATTEMPT/'adapted.jsonl').read_bytes()
        if reference_raw!=adapted_raw:raise Stop('STOP_DIFFERENTIAL_EXACT_BYTES')
        events=[json.loads(line) for line in reference_raw.splitlines()]
        spec=json.loads((BASE/'fixtures/cases.json').read_text())
        by_kind=lambda kind:[e for e in events if e[1]==kind]
        lists={e[2]:e[3] for e in by_kind('list')}
        if lists!=spec['expected_groups']:raise Stop('STOP_GOLDEN_LISTS')
        if [e[3] for e in by_kind('word')]!=spec['expected_words']:raise Stop('STOP_GOLDEN_WORDS')
        if [e[3] for e in by_kind('segment')]!=spec['expected_segments']:raise Stop('STOP_GOLDEN_SEGMENTS')
        pre_scores={e[2]:e[4] for e in by_kind('score') if e[0]=='prelude'}
        if pre_scores['cat']!=pre_scores['dog']:raise Stop('STOP_TIE_FIXTURE')
        if len(by_kind('winner'))!=3 or len(by_kind('iteration'))!=6:raise Stop('STOP_TRAJECTORY_COUNT')
        if [e[0] for e in by_kind('winner')]!=[c['id'] for c in spec['cases']]:
            raise Stop('STOP_CASE_ORDER')
        for case,root_event in zip(spec['cases'],by_kind('root')):
            if root_event[0]!=case['id'] or root_event[2]!=case['alphabet'] or root_event[3][0]!=case['root']:
                raise Stop('STOP_ROOT_IDENTITY')
            if [e[2] for e in by_kind('iteration') if e[0]==case['id']]!=[1,2]:
                raise Stop('STOP_CASE_ITERATIONS')
        if {e[2] for e in by_kind('candidates')}!={1,2}:raise Stop('STOP_ORDER_PHASE_COVERAGE')
        if events[-1][0:2]!=['terminal','complete'] or events[-1][2]['cases']!=3:
            raise Stop('STOP_TERMINAL_EVENT')
        # Readback only: every emitted roundtrip was checked in Perl, require complete saved positions.
        roundtrips=[]
        for e in events:
            if e[1] in ('root','winner'):rt=e[-1]
            elif e[1] in ('candidate','child'):rt=e[-1]
            else:continue
            if len(rt[1])!=6 or len(rt[2])!=6 or [r[0] for r in rt[2]]!=[1,2,3,4,5,6]:
                raise Stop('STOP_ROUNDTRIP_ACCOUNTING')
            if any(r[1]!=r[3] for r in rt[2]):raise Stop('STOP_ROUNDTRIP_READBACK')
            roundtrips.append(rt)
        broker_end=json.loads((ATTEMPT/'broker_terminal.json').read_text())
        if broker_end['closed'] is not True or not 1<=broker_end['requests']<=80000:
            raise Stop('STOP_BROKER_TERMINAL')
        ipc_count=0
        with (ATTEMPT/'broker_ipc.jsonl').open() as f:
            for line in f:
                item=json.loads(line);ipc_count+=1
                if item['request'][0]!=ipc_count or item['response'][0]!=ipc_count:
                    raise Stop('STOP_IPC_READBACK_ORDER')
        if ipc_count!=broker_end['requests']:raise Stop('STOP_IPC_READBACK_COUNT')
        for entry in freeze['identities']:
            p=Path(entry['path']) if entry['external'] else BASE/entry['path']
            if digest(p)!=entry['sha256']:raise Stop('STOP_POST_HASH:'+str(p))
            tick()
        if digest(BASE/'FREEZE.json')!=result['manifest_sha256']:raise Stop('STOP_MANIFEST_CHANGED')
        result['comparison']={'exact_bytes':True,'events':len(events),
            'score_calls_per_arm':len(by_kind('score')),'iterations_per_arm':len(by_kind('iteration')),
            'roundtrips_per_arm':len(roundtrips),'broker':broker_end,
            'trace_sha256':hashlib.sha256(reference_raw).hexdigest()}
        result['status']='PASS_FINITE_DIFFERENTIAL_ONLY';code=0
    except BaseException as e:
        result['status']='STOP';result['error']=repr(e);result['traceback']=traceback.format_exc();code=2
    finally:
        for fd in list(parent_fds):close_fd(fd)
        # All own groups receive TERM before the shared grace; then KILL, no replacements.
        try:
            for c in children:
                if c['anchor'] is not None and ns.group(c['anchor'],c['known']):signal_owned(c,signal.SIGTERM)
            grace=time.monotonic()+2
            while any(c['p'].poll() is None for c in children) and time.monotonic()<grace:time.sleep(.02)
            for c in children:
                if c['anchor'] is not None and ns.group(c['anchor'],c['known']):signal_owned(c,signal.SIGKILL)
            grace=time.monotonic()+2
            while any(c['p'].poll() is None for c in children) and time.monotonic()<grace:time.sleep(.02)
            terminal=[]
            for c in children:
                group=ns.group(c['anchor'],c['known']) if c['anchor'] else None
                terminal.append({'role':c['role'],'exit':c['p'].poll(),'group':group})
            result['terminal']=terminal
            result['terminal_confirmed']=all(t['exit'] is not None and t['group']==[] for t in terminal)
            if children and not result['terminal_confirmed']:
                result['status']='UNKNOWN';code=2
        except BaseException as e:
            result['termination_error']=repr(e);result['status']='UNKNOWN';code=2
        for h in handles:h.close()
    result['elapsed']=time.monotonic()-start;result['end_utc']=utc();result['after']=memory()
    if result['status']=='PASS_FINITE_DIFFERENTIAL_ONLY' and result['elapsed']>=60:
        result['status']='STOP';result['error']='STOP_FINAL_WALL_ACCOUNTING';code=2
    result['children_peak_rss_KiB']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    result['file_hashes']={p.name:digest(p) for p in ATTEMPT.iterdir() if p.is_file() and p.name!='result.json'}
    dump('result.json',result)
    print(json.dumps({k:result.get(k) for k in ('status','elapsed','terminal_confirmed','comparison','error')}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
