"""Prepared combined LM differential and optional real-byte IPC; no production solver."""
from pathlib import Path
import os, sys, json, time, datetime, hashlib, resource, subprocess, signal, traceback
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from namespace_view import NamespaceView, Stop
from verifier_binding import observed_real,final_binding,check_publication
ATTEMPT=BASE/'attempt'

def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(path,check=None):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):
            h.update(block)
            if check:check()
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
    launch=json.loads((BASE/'launch_evidence.json').read_text());start=launch['monotonic'];global_deadline=launch['global_deadline'];deadline=min(start+90,global_deadline)
    result={'version':'TS-JOURNAL-DIAGNOSTIC-v1','status':'INCOMPLETE','start_utc':launch['utc'],
            'commands':[],'signals':[],'phases':[],'target_inputs':0,'control_87_inputs':0,'full_model_loads':0,'stages':{}}
    dump('T0.json',{'utc':result['start_utc'],'monotonic':start,'global_deadline':global_deadline})
    children=[];handles=[];parent_fds=set();ns=None
    def tick():
        if time.monotonic()>=min(deadline,global_deadline)-4: raise Stop('STOP_WALL_DEADLINE')
        if int(memory()['memory.current'])>=7*1024**3: raise Stop('STOP_SHARED_MEMORY')
        for p in ATTEMPT.iterdir():
            if p.is_file() and p.stat().st_size>8388608: raise Stop('STOP_OUTPUT_BOUND')
        if sum(p.stat().st_size for p in ATTEMPT.iterdir() if p.is_file())>32*1024**2:
            raise Stop('STOP_TOTAL_OUTPUT_BOUND')
        active=0
        for child in children:
            p=child['p']
            if p.poll() is None: active+=1
            if child['anchor'] is not None and not child.get('retired',False):
                group=ns.group(child['anchor'],child['known'])
                if len(group)>1: raise Stop('STOP_UNEXPECTED_DESCENDANT')
        if active>2: raise Stop('STOP_PROCESS_COUNT')
    def log_handle(name):
        f=(ATTEMPT/name).open('xb');handles.append(f);return f
    def close_fd(fd):
        if fd in parent_fds: os.close(fd);parent_fds.remove(fd)
    def pipe():
        pair=os.pipe();parent_fds.update(pair);return pair
    def launch_child(role,stdin,stdout,ipc=()):
        tick()
        gr,gw=pipe()
        argv=[freeze['python'],'-B','-I','-S',str(BASE/'child_gate.py'),role,str(gr),*map(str,ipc)]
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
        if ready['limits']!=freeze['limits'][freeze['roles'][role]['limit_class']]: raise Stop('STOP_LIMITS')
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
            c['retired']=True
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
    def verify(entries):
        for entry in entries:
            p=Path(entry['path']) if entry.get('external',True) else BASE/entry['path']
            if p.stat().st_size!=entry['bytes'] or digest(p,tick)!=entry['sha256']:
                raise Stop('STOP_HASH:'+str(p))
    def pair(prefix):
        lreqr,lreqw=pipe();lrespr,lrespw=pipe();preqr,preqw=pipe();prespr,prespw=pipe()
        broker=launch_child(prefix+'_broker',subprocess.DEVNULL,log_handle(prefix+'_broker_stdout.txt'),(lreqr,lrespw,preqr,prespw))
        perl=launch_child(prefix+'_perl',subprocess.DEVNULL,log_handle(prefix+'_perl.jsonl'),(lrespr,lreqw,prespr,preqw))
        for fd in (lreqr,lreqw,lrespr,lrespw,preqr,preqw,prespr,prespw):close_fd(fd)
        release(broker);release(perl);observe_until_done([broker,perl])
    try:
        freeze=json.loads((BASE/'FREEZE.json').read_text())
        result['manifest_sha256']=digest(BASE/'FREEZE.json')
        for k,v in freeze['limits']['supervisor'].items():resource.setrlimit(getattr(resource,k),tuple(v))
        if sys.version_info[:3]!=(3,12,14):raise Stop('STOP_PYTHON_VERSION')
        result['before']=memory()
        result['memory_stat_before']=Path('/sys/fs/cgroup/memory.stat').read_text()
        if result['before']['memory.max']!='8589934592' or int(result['before']['memory.current'])+freeze['resource']['all_input_page_bytes']+freeze['resource']['process_AS_sum']+freeze['resource']['allowance']>=7*1024**3:
            raise Stop('NO_GO_INITIAL_RESOURCE')
        if (ATTEMPT/'Modules').exists():raise Stop('STOP_UNEXPECTED_PERL_INCLUDE_PATH')
        verify(freeze['identities'])
        ns=NamespaceView();result['namespace_self']=ns.self_record
        from process_guard import regression,inspect_prior
        result['process_guard_cases']=regression(BASE)
        freeze['_observed_sha256']=result['manifest_sha256']
        guard=inspect_prior(ns,BASE,freeze,tick)
        result['process_guard']=guard
        result['prior_live_matches']=guard['blockers']
        dump('process_guard.json',guard)
        if guard['blockers']:raise Stop('STOP_PREVIOUS_LIVE_PROCESS')
        verify(freeze['real_inputs'])
        result['post_hash_resource']=memory()
        if int(result['post_hash_resource']['memory.current'])+freeze['resource']['process_AS_sum']+freeze['resource']['allowance']>=7*1024**3:raise Stop('NO_GO_POST_HASH_RESOURCE')
        result['hashes_verified']=True
        dump('phase_deadline.json',{'deadline':deadline-4,'global_deadline':global_deadline})
        # Existing synthetic evidence is authenticated data, not a new search or re-execution.
        prior=json.loads((BASE/'prior_evidence/stage_fixture.json').read_text())
        if prior['status']!='PASS_FINITE_COMBINED_DIFFERENTIAL' or prior['events']!=320 or prior['inverse_records']!=118:
            raise Stop('STOP_PRIOR_FIXTURE_STATUS')
        if (BASE/'prior_evidence/reference_perl.jsonl').read_bytes()!=(BASE/'prior_evidence/adapted_perl.jsonl').read_bytes():
            raise Stop('STOP_PRIOR_FIXTURE_BYTES')
        result['stages']['prior_synthetic']={'status':'REUSED_HASH_PINNED_EVIDENCE_ONLY','value':prior}
        dump('prior_synthetic_admission.json',result['stages']['prior_synthetic'])
        # Combined real-table transport, only after all-input admission and fixture PASS.
        deadline=min(global_deadline,time.monotonic()+60)
        dump('phase_deadline.json',{'deadline':deadline-4,'global_deadline':global_deadline})
        pre=memory();result['real_post_hash_resource']=pre
        if int(pre['memory.current'])+freeze['resource']['process_AS_sum']+freeze['resource']['allowance']>=7*1024**3:
            result['stages']['real']={'status':'SKIPPED_RESOURCE','phase':'POST_FIXTURE','observed':pre}
            result['status']='SKIPPED_RESOURCE';code=0
        else:
            pair('real');tick()
            dump('wait_before_verifier.json',{'monotonic':time.monotonic(),
                'terminal_phases':[p for p in result['phases'] if p.get('terminal') in ('real_broker','real_perl')]})
            result['stages']['real']=observed_real(BASE,tick);tick();verify(freeze['real_inputs'])
            result['status']='PASS_DIAGNOSTIC_PENDING_BINDING';code=0
        dump('stage_real.json',result['stages']['real'])
        verify(freeze['identities'])
        if digest(BASE/'FREEZE.json',tick)!=result['manifest_sha256']:raise Stop('STOP_MANIFEST_CHANGED')
    except BaseException as e:
        result['status']='NO_GO_BEFORE_FOREIGN' if str(e).startswith('NO_GO_') and not children else 'STOP';result['error']=repr(e);result['traceback']=traceback.format_exc();code=3 if result['status']=='NO_GO_BEFORE_FOREIGN' else 2
    finally:
        for fd in list(parent_fds):close_fd(fd)
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
            if children and not result['terminal_confirmed']:result['status']='UNKNOWN';code=2
        except BaseException as e:
            result['termination_error']=repr(e);result['status']='UNKNOWN';code=2
        for h in handles:h.close()
    result['elapsed']=time.monotonic()-start;result['end_utc']=utc();result['after']=memory()
    result['memory_stat_after']=Path('/sys/fs/cgroup/memory.stat').read_text()
    if result['status'].startswith('PASS') and (result['elapsed']>=180 or time.monotonic()>=deadline):
        result['status']='STOP';result['error']='STOP_FINAL_WALL_ACCOUNTING';code=2
    before_events=dict(line.split() for line in result.get('before',{}).get('memory.events','').splitlines())
    after_events=dict(line.split() for line in result['after']['memory.events'].splitlines())
    if any(int(after_events.get(k,0))>int(before_events.get(k,0)) for k in ('oom','oom_kill','oom_group_kill')):
        result['status']='STOP';result['error']='STOP_SHARED_OOM_EVENT';code=2
    result['children_peak_rss_KiB']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    result['self_peak_rss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if result['status']=='PASS_DIAGNOSTIC_PENDING_BINDING':
        try:
            result['binding']=final_binding(BASE,result['terminal'],tick)['status']
            result['status']='PASS_DIAGNOSTIC_THIS_ATTEMPT_ONLY'
        except BaseException as e:
            result['status']='STOP';result['error']=repr(e);result['traceback']=traceback.format_exc();code=2
    result['file_hashes']={p.name:digest(p) for p in ATTEMPT.iterdir() if p.is_file() and p.name!='result.json'}
    if result['status']=='PASS_DIAGNOSTIC_THIS_ATTEMPT_ONLY':
        try:check_publication(BASE,result['file_hashes'],tick)
        except BaseException as e:
            result['status']='STOP';result['error']=repr(e);result['traceback']=traceback.format_exc();code=2
    result['elapsed']=time.monotonic()-start;result['end_utc']=utc()
    if result['status'].startswith('PASS') and (result['elapsed']>=180 or time.monotonic()>=deadline):
        result['status']='STOP';result['error']='STOP_SEAL_WALL_ACCOUNTING';code=2
    dump('result.json',result)
    print(json.dumps({k:result.get(k) for k in ('status','elapsed','terminal_confirmed','stages','error')}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
