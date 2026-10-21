"""Own one-shot read-only sizing of pinned saved data; no solver or adapter import."""
from pathlib import Path
import json, hashlib, time, resource, datetime
BASE=Path(__file__).resolve().parent
def main():
    output=BASE/'SIZING_RESULT.json'
    if output.exists():raise RuntimeError('NO_REPEAT')
    start=time.monotonic();deadline=start+10
    resource.setrlimit(resource.RLIMIT_AS,(134217728,134217728))
    resource.setrlimit(resource.RLIMIT_CPU,(8,10))
    plan=json.loads((BASE/'SIZING_PLAN.json').read_text())
    def tick():
        if time.monotonic()>=deadline:raise RuntimeError('DEADLINE')
    r={'scope':'saved-data sizing only','start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        data=[]
        for item in plan['inputs']:
            tick();p=Path(item['path']);raw=p.read_bytes()
            if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:raise RuntimeError('HASH')
            data.append(json.loads(raw))
        phase,lists,store,t0=data
        r['lists']=[]
        for pattern,values in lists.items():
            tick()
            frame=json.dumps([1,values],ensure_ascii=True,separators=(',',':')).encode()+b'\n'
            r['lists'].append({'pattern':pattern,'count':0 if values is None else len(values),
                'old_single_frame_bytes':len(frame),
                'sum_value_bytes':0 if values is None else sum(len(x.encode('ascii')) for x in values),
                'max_value_bytes':0 if not values else max(len(x.encode('ascii')) for x in values)})
        offset=phase['start_monotonic']-t0['monotonic']
        selected=None
        for snap in phase['process_samples']:
            tick()
            if snap['elapsed']<offset+13:continue
            perl=[m for m in snap['members'] if m['cmdline'] and m['cmdline'][0]=='/usr/bin/perl']
            if perl:
                selected={'relative_to_author_start_seconds':snap['elapsed']-offset,'snapshot':snap};break
        r['first_process_sample_after_13s']=selected
        r['saved_global_candidate_bound']=store['groups']['max_candidates_in_one_pattern']
        r['saved_global_max_candidate_bytes']=store['build']['max_candidate_bytes']
        r['chunk_size']=64
        r['conservative_ASCII_JSON_chunk_bound_bytes']=64*(46*6+3)+128
        r['max_chunks']=(63911+63)//64
        r['max_candidate_payload_bytes']=63911*46
        r['status']='SIZING_COMPLETE'
    except BaseException as exc:r['status']='STOP';r['error']=repr(exc)
    r['elapsed']=time.monotonic()-start;r['maxrss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
    return 0 if r['status']=='SIZING_COMPLETE' else 2
if __name__=='__main__':raise SystemExit(main())
