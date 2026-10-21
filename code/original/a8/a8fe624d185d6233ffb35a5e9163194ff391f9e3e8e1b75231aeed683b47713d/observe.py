"""Finite own stdlib reader; no solver/module import, subprocess, network or OS writes."""
from pathlib import Path
import json, hashlib, os, time, datetime, resource, sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parent
START=time.monotonic()
TOTAL=0
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def tick():
    if time.monotonic()-START>10: raise RuntimeError('INCOMPLETE_COOPERATIVE_TIME')
def read(path):
    global TOTAL
    tick()
    with Path(path).open('rb') as f: b=f.read(131073)
    if len(b)>131072: raise RuntimeError('READ_BOUND')
    TOTAL+=len(b)
    if TOTAL>2097152: raise RuntimeError('TOTAL_READ_BOUND')
    return b
def maybe(path):
    try: return {'text':read(path).decode('utf-8')}
    except (OSError,UnicodeError) as e: return {'error':repr(e)}
def kv(text): return {k:int(v) for k,v in (s.split() for s in text.splitlines())}
def snapshot():
    names=['memory.current','memory.max','memory.peak','memory.stat','memory.events','memory.events.local','memory.high','memory.low','memory.min','memory.swap.current','memory.swap.max','memory.pressure','cgroup.type','cgroup.events']
    return {'utc':utc(),'monotonic':time.monotonic(),'cgroup':{n:maybe(Path('/sys/fs/cgroup')/n) for n in names},'self_cgroup':maybe('/proc/self/cgroup'),'self_status':maybe('/proc/self/status'),'meminfo':maybe('/proc/meminfo')}
def main():
    if (BASE/'result.json').exists(): raise RuntimeError('REFUSE_EXISTING_RESULT')
    plan=read(BASE/'PLAN.json');p=json.loads(plan)
    fbytes=read(ROOT/p['input_freeze'])
    if hashlib.sha256(fbytes).hexdigest()!=p['input_freeze_sha256']:raise RuntimeError('INPUT_FREEZE_HASH')
    f=json.loads(fbytes);r=f['resource'];page=os.sysconf('SC_PAGE_SIZE')
    out={'status':'INCOMPLETE','start_utc':utc(),'plan_sha256':hashlib.sha256(plan).hexdigest(),'script_sha256':hashlib.sha256(read(__file__)).hexdigest(),'python':sys.version,'page_size':page,'snapshots':[snapshot()],'inputs':[]}
    for entry in f['six_lm']+[f['patlst'],f['full_index']]:
        tick();s=Path(entry['path']).stat()
        if s.st_size!=entry['bytes']:raise RuntimeError('METADATA_SIZE_MISMATCH')
        out['inputs'].append({'path':entry['path'],'saved_sha256_not_rehashed':entry['sha256'],'bytes':s.st_size,'page_rounded_bytes':((s.st_size+page-1)//page)*page,'device':s.st_dev,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'blocks_512':s.st_blocks})
    out['snapshots'].append(snapshot())
    out['snapshots'].append(snapshot())
    out['resource_constants_unchanged']=r
    identities={(x['device'],x['inode']) for x in out['inputs']}
    out['distinct_input_inodes']=len(identities)
    unique={ (x['device'],x['inode']):x for x in out['inputs']}
    B=sum(x['page_rounded_bytes'] for x in unique.values())
    out['page_rounded_unique_input_bytes']=B
    out['arithmetic']=[]
    for s in out['snapshots']:
        c=int(s['cgroup']['memory.current']['text']);m=int(s['cgroup']['memory.max']['text']);st=kv(s['cgroup']['memory.stat']['text'])
        required=c+r['P_sum_process_AS_caps']+r['IO_kernel_output_allowance']+r['nominal_shared_reserve']
        out['arithmetic'].append({'utc':s['utc'],'current':c,'max':m,'instant_max_minus_current':m-c,'anon':st['anon'],'file_total_including_shmem':st['file'],'shmem_subset_of_file':st['shmem'],'file_minus_shmem':st['file']-st['shmem'],'kernel':st['kernel'],'dirty_subset':st['file_dirty'],'writeback_subset':st['file_writeback'],'slab_reclaimable_subset_of_kernel':st['slab_reclaimable'],'stat_anon_file_kernel_sum_minus_current':st['anon']+st['file']+st['kernel']-c,'zero_extra_input_policy_sum':required,'zero_extra_input_policy_excess_over_max':required-m,'full_extra_input_policy_sum':required+B,'old_pre_hash_gate_passes':c<=r['P_pre_hash_current_max'],'old_post_hash_gate_passes':c<=r['P_post_hash_current_max']})
    out.update(status='COMPLETED_READONLY_OBSERVATION',end_utc=utc(),elapsed_seconds=time.monotonic()-START,total_read_bytes=TOTAL,self_peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    tick();encoded=(json.dumps(out,indent=2)+'\n').encode()
    if len(encoded)>1048576:raise RuntimeError('OUTPUT_BOUND')
    with (BASE/'result.json').open('xb') as h:h.write(encoded)
    print(json.dumps({k:out[k] for k in ('status','elapsed_seconds','total_read_bytes','self_peak_rss_KiB','arithmetic')}))
if __name__=='__main__':main()
