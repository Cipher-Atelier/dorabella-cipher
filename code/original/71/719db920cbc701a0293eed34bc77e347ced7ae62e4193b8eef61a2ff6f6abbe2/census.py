from pathlib import Path
import hashlib, json, time, datetime, resource, sys, os, traceback

BASE=Path(__file__).resolve().parent
SOURCE=Path('/workspace/scratch/f24f8fae4976/TREESEARCH_first_control_v1/model/lmtrain_nyt_word.patlst')
EXPECTED_BYTES=340083717
EXPECTED_HASH='2849bc03f85c59a422f1945960ce04a4b6e66cc02c61a6484de0283c30c724fd'

def main():
    a=BASE/'attempt'
    if a.exists(): print('REFUSED_EXISTING_ATTEMPT');return 3
    a.mkdir();start=time.monotonic(); deadline=start+60
    r={'version':'TS-PATLST-CENSUS-v1','status':'INCOMPLETE','start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deadline_seconds':60,'AS_bytes':268435456,'source':str(SOURCE),'expected_bytes':EXPECTED_BYTES,'expected_sha256':EXPECTED_HASH,'passes':1,'index_built':False}
    (a/'T0.json').write_text(json.dumps(r,indent=2)+'\n')
    resource.setrlimit(resource.RLIMIT_AS,(268435456,268435456))
    resource.setrlimit(resource.RLIMIT_CPU,(55,60))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    h=hashlib.sha256(); n=total=maxline=pattern_sum=maxpattern=tabs=0; orders={}
    try:
        if SOURCE.stat().st_size!=EXPECTED_BYTES:raise RuntimeError('SIZE_MISMATCH')
        before=SOURCE.stat()
        with SOURCE.open('rb') as f:
            while True:
                raw=f.readline(8*1024**2+1)
                if not raw:break
                if len(raw)>8*1024**2:raise RuntimeError('LINE_BOUND')
                n+=1;total+=len(raw);maxline=max(maxline,len(raw));h.update(raw)
                first=raw.find(b'\t');second=raw.find(b'\t',first+1)
                if first<0 or second<0:raise RuntimeError('MISSING_TAB_HEADER')
                order=raw[:first].decode('ascii');orders[order]=orders.get(order,0)+1
                size=second-first-1;pattern_sum+=size;maxpattern=max(maxpattern,size)
                tabs+=raw.count(b'\t')
                if n%8192==0 and time.monotonic()>=deadline:raise RuntimeError('DEADLINE')
                if total>EXPECTED_BYTES:raise RuntimeError('BYTE_BOUND')
        after=SOURCE.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('INPUT_CHANGED')
        if total!=EXPECTED_BYTES or h.hexdigest()!=EXPECTED_HASH:raise RuntimeError('INPUT_HASH')
        if time.monotonic()>deadline:raise RuntimeError('DEADLINE')
        r['status']='COMPLETED_CENSUS';code=0
    except BaseException as e:
        r.update(status='STOP',error=repr(e),traceback=traceback.format_exc());code=2
    r.update(lines=n,bytes=total,sha256=h.hexdigest(),max_raw_line_bytes=maxline,raw_pattern_bytes_sum=pattern_sum,max_raw_pattern_bytes=maxpattern,tab_bytes=tabs,physical_orders=orders,elapsed=time.monotonic()-start,maxrss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with (a/'result.json').open('w') as f:json.dump(r,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps(r),flush=True);return code
if __name__=='__main__':sys.exit(main())
