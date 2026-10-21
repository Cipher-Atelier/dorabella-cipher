"""Authorized v2 supervisor identification fix; unchanged transport, A/P and limits."""
from pathlib import Path
import os, sys, json, time, datetime, hashlib, resource, subprocess, signal, traceback
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from namespace_view import NamespaceView, Stop
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
    start=time.monotonic();global_deadline=start+180;deadline=start+60
    result={'version':'TS-TRANSPORT-PROFILE-v2','status':'INCOMPLETE','start_utc':utc(),
            'commands':[],'signals':[],'phases':[],'target_inputs':0,'control_87_inputs':0,'full_model_loads':0,'stages':{}}
    dump('T0.json',{'utc':result['start_utc'],'monotonic':start,'global_deadline':global_deadline})
    children=[];handles=[];parent_fds=set();ns=None
    def tick():
        if time.monotonic()>=min(deadline,global_deadline)-4: raise Stop('STOP_WALL_DEADLINE')
        if int(memory()['memory.current'])>=7*1024**3: raise Stop('STOP_SHARED_MEMORY')
        for p in ATTEMPT.iterdir():
            if p.is_file() and p.stat().st_size>8388608: raise Stop('STOP_OUTPUT_BOUND')
        if sum(p.stat().st_size for p in ATTEMPT.iterdir() if p.is_file())>64*1024**2:
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
        request_read,request_write=pipe();response_read,response_write=pipe()
        broker=launch(prefix+'_broker',request_read,response_write)
        perl=launch(prefix+'_perl',subprocess.DEVNULL,log_handle(prefix+'_perl.jsonl'),(response_read,request_write))
        for fd in (request_read,request_write,response_read,response_write):close_fd(fd)
        release(broker);release(perl);observe_until_done([broker,perl])
    try:
        freeze=json.loads((BASE/'FREEZE.json').read_text())
        result['manifest_sha256']=digest(BASE/'FREEZE.json')
        for k,v in freeze['limits']['supervisor'].items():resource.setrlimit(getattr(resource,k),tuple(v))
        if sys.version_info[:3]!=(3,12,14):raise Stop('STOP_PYTHON_VERSION')
        result['before']=memory()
        result['memory_stat_before']=Path('/sys/fs/cgroup/memory.stat').read_text()
        if result['before']['memory.max']!='8589934592' or int(result['before']['memory.current'])>freeze['resource']['A_enter_current_max']:
            raise Stop('STOP_A_RESOURCE_GATE')
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
        result['hashes_verified']=True
        dump('A_deadline.json',{'deadline':deadline-4,'wall_deadline':deadline,'global_deadline':global_deadline})
        pair('fixture');pair('large')
        from readback import stage_a,stage_p
        tick();result['stages']['A']=stage_a();tick()
        result['stages']['A']['elapsed_including_initial_checks']=time.monotonic()-start
        dump('stage_A.json',result['stages']['A'])
        # Conditional load-only profile. No memory reclamation, waiting for resources, or retries.
        pstart=time.monotonic();deadline=min(global_deadline,pstart+60)
        dump('P_deadline.json',{'deadline':deadline-4,'wall_deadline':deadline,'global_deadline':global_deadline})
        pgate=memory();result['P_pre_hash_resource']=pgate
        if int(pgate['memory.current'])>freeze['resource']['P_pre_hash_current_max']:
            result['stages']['P']={'status':'SKIPPED_RESOURCE','reason':'PRE_HASH_CURRENT','observed':pgate}
            result['status']='PASS_A_PROFILE_SKIPPED_RESOURCE';code=0
        else:
            verify(freeze['six_lm']+[freeze['patlst'],freeze['full_index']])
            pgate=memory();result['P_post_hash_resource']=pgate
            if int(pgate['memory.current'])>freeze['resource']['P_post_hash_current_max']:
                result['stages']['P']={'status':'SKIPPED_RESOURCE','reason':'POST_HASH_CURRENT','observed':pgate}
                result['status']='PASS_A_PROFILE_SKIPPED_RESOURCE';code=0
            else:
                result['profile_launch_requested']=True
                pair('profile');result['full_model_loads']=1
                tick();result['stages']['P']=stage_p();tick()
                verify(freeze['six_lm']+[freeze['patlst'],freeze['full_index']])
                result['stages']['P']['elapsed_including_identity_checks']=time.monotonic()-pstart
                result['status']='PASS_TRANSPORT_AND_LOAD_PROFILE_ONLY';code=0
        dump('stage_P.json',result['stages']['P'])
        verify(freeze['identities'])
        if digest(BASE/'FREEZE.json',tick)!=result['manifest_sha256']:raise Stop('STOP_MANIFEST_CHANGED')
    except BaseException as e:
        result['status']='STOP';result['error']=repr(e);result['traceback']=traceback.format_exc();code=2
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
    result['file_hashes']={p.name:digest(p) for p in ATTEMPT.iterdir() if p.is_file() and p.name!='result.json'}
    result['elapsed']=time.monotonic()-start;result['end_utc']=utc()
    if result['status'].startswith('PASS') and (result['elapsed']>=180 or time.monotonic()>=deadline):
        result['status']='STOP';result['error']='STOP_SEAL_WALL_ACCOUNTING';code=2
    dump('result.json',result)
    print(json.dumps({k:result.get(k) for k in ('status','elapsed','terminal_confirmed','stages','error')}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
