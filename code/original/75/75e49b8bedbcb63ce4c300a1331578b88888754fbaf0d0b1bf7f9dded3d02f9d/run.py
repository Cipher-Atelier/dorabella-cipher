"""Single own bounded full census/readback and finite byte-contract attempt."""
from pathlib import Path
import os, sys, json, time, datetime, hashlib, resource, struct, re
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(BASE))
from contract import parse,canonical,DiskLM,frame,unframe
START=time.monotonic();OUT=BASE/'attempt';R={'status':'INCOMPLETE','start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tables':[]}
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b);tick()
    return h.hexdigest()
def tick():
    if time.monotonic()-START>=180:raise RuntimeError('STOP_WALL')
    if int(Path('/sys/fs/cgroup/memory.current').read_text())>=7*1024**3:raise RuntimeError('STOP_SHARED_MEMORY')
    if OUT.exists() and sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())>128*1024**2:raise RuntimeError('STOP_OUTPUT')
def memory():return {k:(Path('/sys/fs/cgroup')/k).read_text() for k in ['memory.current','memory.max','memory.events','memory.stat']}
def dump(n,x):
    with (OUT/n).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def independent_parse(raw,n):
    # Byte scanner, independent of regex parser and canonical serializer.
    if len(raw)>512 or not raw:raise ValueError('REF_ROW')
    if raw[-1:]==b'\n':raw=raw[:-1]
    fields=[];buf=bytearray();intabs=False
    for c in raw:
        if c==9:
            if not intabs:fields.append(bytes(buf));buf.clear()
            intabs=True
        else:buf.append(c);intabs=False
    fields.append(bytes(buf))
    if len(fields)!=n+1 or any(not f for f in fields):raise ValueError('REF_FIELDS')
    for k in fields[:-1]:
        if len(k)>128 or min(k)<33 or max(k)>126:raise ValueError('REF_KEY')
    p=fields[-1]
    if len(p)>96 or any(c not in b'0123456789.eE+-' for c in p):raise ValueError('REF_VALUE')
    return tuple(fields[:-1]),p
def ref_serial(k,v):
    out=bytearray()
    for field in list(k)+[v]:out.extend(len(field).to_bytes(2,'little'));out.extend(field)
    return bytes(out)
def fixture_tests():
    positives=[(1,b'a\t0\n',(b'a',),b'0'),(1,b'a\t00\n',(b'a',),b'00'),(1,b'a\t0.00\n',(b'a',),b'0.00'),(1,b'a\t1e-03',(b'a',),b'1e-03'),(2,b'a\t\tb\t.500\n',(b'a',b'b'),b'.500')]
    for n,raw,k,v in positives:
        assert parse(raw,n)==(k,v) and independent_parse(raw,n)==(k,v)
        assert canonical(k,v)==ref_serial(k,v)
    negatives=[(1,b'a\t\n'),(1,b'\t0.1\n'),(1,b'a\tb\t0.1\n'),(1,b'a\t0.1\r\n'),(1,b'\xff\t0.1\n'),(1,b'a\tNaN\n'),(1,b'a'*129+b'\t0.1\n'),(1,b'a'*513)]
    rejected=[]
    for i,(n,raw) in enumerate(negatives):
        try:parse(raw,n)
        except ValueError:rejected.append(i)
        else:raise RuntimeError('NEGATIVE_PARSE_ACCEPTED')
    src=OUT/'fixture.lm';idx=OUT/'fixture.idx'
    lines=[b'a\t0\n',b'a\t0.00\n',b'b\t1e-03\n']
    src.write_bytes(b''.join(lines));offset=0
    with idx.open('xb') as f:
        for line in lines:f.write(struct.pack('<Q',offset));offset+=len(line)
        f.write(struct.pack('<Q',offset))
    d=DiskLM([{'id':1,'order':1,'path':str(src),'index_path':str(idx),'rows':3,'bytes':offset}],tick,2)
    try:
        assert d.lookup(1,(b'a',))=={'found':True,'value_hex':b'0.00'.hex(),'last_row_1based':2}
        assert d.lookup(1,(b'aa',))=={'found':False,'value_hex':None,'last_row_1based':None}
        for t,k in [(0,(b'a',)),(1,(b'a',b'b'))]:
            try:d.lookup(t,k)
            except ValueError:rejected.append('query')
            else:raise RuntimeError('NEGATIVE_QUERY_ACCEPTED')
    finally:d.close()
    # Corrupt only the new fixture index; never any real index/data.
    bad=OUT/'corrupt.idx';bad.write_bytes(struct.pack('<QQQQ',0,9999,9999,9999))
    d=DiskLM([{'id':1,'order':1,'path':str(src),'index_path':str(bad),'rows':3,'bytes':offset}],tick,2)
    try:
        try:d.lookup(1,(b'a',))
        except ValueError:rejected.append('offset')
        else:raise RuntimeError('NEGATIVE_OFFSET_ACCEPTED')
    finally:d.close()
    decreasing=[(b'b',),(b'a',)]
    if all(a<=b for a,b in zip(decreasing,decreasing[1:])):raise RuntimeError('NEGATIVE_ORDER_ACCEPTED')
    rejected.append('decreasing_order')
    records=[{'found':True,'value_hex':(b'1'*96).hex(),'last_row_1based':10000000}]*128
    raw=frame(0,records,True);assert unframe(raw,0)==(records,True)
    for bad,seq in [(b'x'*65537,0),(b'{}\n',0),(raw,1),(raw[:-1],0)]:
        try:unframe(bad,seq)
        except (ValueError,KeyError,TypeError):rejected.append('frame')
        else:raise RuntimeError('NEGATIVE_FRAME_ACCEPTED')
    try:frame(0,[{'found':True,'value_hex':0.5,'last_row_1based':1}],True)
    except ValueError:rejected.append('numeric_value')
    else:raise RuntimeError('NUMERIC_COERCION_ACCEPTED')
    return {'positive_parse':len(positives),'negative_checks':len(rejected),'negative_ids':rejected,'max_synthetic_response_frame_bytes':len(raw),'duplicate_last_write_and_missing':True,'raw_numeric_strings_retained':True}
def main():
    if OUT.exists():raise RuntimeError('REFUSE_EXISTING_ATTEMPT')
    OUT.mkdir();dump('T0.json',{'utc':R['start_utc'],'monotonic':START,'deadline':START+180})
    resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(160,170));resource.setrlimit(resource.RLIMIT_FSIZE,(96*1024**2,96*1024**2));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    freeze=json.loads((BASE/'FREEZE.json').read_text())
    for n,e in freeze['files'].items():
        if digest(BASE/n)!=e['sha256']:raise RuntimeError('FREEZE_HASH:'+n)
    f=ROOT/'TS_TRANSPORT_PROFILE_v2/FREEZE.json'
    if digest(f)!=freeze['source_freeze_sha256']:raise RuntimeError('SOURCE_FREEZE_HASH')
    entries=json.loads(f.read_text())['six_lm'];counts=freeze['rows'];R['before']=memory()
    page=os.sysconf('SC_PAGE_SIZE');B=sum(((e['bytes']+page-1)//page)*page for e in entries)
    projected=int(R['before']['memory.current'])+B+90592776+160*1024**2
    R['reader_admission']={'projected_bytes':projected,'threshold_exclusive':7*1024**3,'input_page_bytes':B,'index_bytes':90592776}
    st=os.statvfs(BASE)
    if int(R['before']['memory.max'])!=8*1024**3 or projected>=7*1024**3 or st.f_bavail*st.f_frsize<512*1024**2:raise RuntimeError('STOP_RESOURCE_GATE')
    R['fixtures']=fixture_tests()
    for table,(entry,N) in enumerate(zip(entries,counts),1):
        tick();t=time.monotonic();order=(table-1)%3+1
        e=dict(entry,id=table,order=order,rows=N,index_path=str((OUT/f'lm{table}.idx').resolve()))
        h=hashlib.sha256();c=hashlib.sha256();ih=hashlib.sha256();offset=0;rows=0;prev=None;dups=0;run=1;maxrun=1;maxrow=maxkey=maxval=0;zero_pv=0;numeric_forms={};selected={};positions=[1,2,1+(N-1)//2,N]
        s0=Path(e['path']).stat()
        with open(e['path'],'rb',buffering=1048576) as src,open(e['index_path'],'xb',buffering=1048576) as ix:
            while True:
                raw=src.readline(513)
                if not raw:break
                rows+=1
                if rows>N:raise RuntimeError('ROW_COUNT_OVER')
                if rows%8192==0:tick()
                k,v=parse(raw,order)
                if prev is not None and k<prev:raise RuntimeError(f'STOP_UNSORTED_TABLE_{table}_ROW_{rows}')
                if k==prev:dups+=1;run+=1;maxrun=max(maxrun,run)
                else:run=1
                prev=k
                if rows in positions:selected[rows]=k
                packed=struct.pack('<Q',offset);ix.write(packed);ih.update(packed)
                h.update(raw);c.update(canonical(k,v));offset+=len(raw)
                maxrow=max(maxrow,len(raw));maxkey=max(maxkey,*map(len,k));maxval=max(maxval,len(v));zero_pv+=v==b'0'
                form='exponent' if b'e' in v.lower() else 'decimal' if b'.' in v else 'integer';numeric_forms[form]=numeric_forms.get(form,0)+1
            last=struct.pack('<Q',offset);ix.write(last);ih.update(last)
        s1=Path(e['path']).stat()
        if (s0.st_dev,s0.st_ino,s0.st_size,s0.st_mtime_ns)!=(s1.st_dev,s1.st_ino,s1.st_size,s1.st_mtime_ns):raise RuntimeError('SOURCE_CHANGED')
        if rows!=N or offset!=e['bytes'] or h.hexdigest()!=e['sha256']:raise RuntimeError('INPUT_IDENTITY')
        e.update(index_sha256=ih.hexdigest(),index_bytes=8*(N+1),canonical_sha256=c.hexdigest(),duplicates=dups,max_duplicate_run=maxrun,max_row_bytes=maxrow,max_token_bytes=maxkey,max_value_bytes=maxval,perl_false_literal_zero_rows=zero_pv,numeric_forms=numeric_forms,queries=[list(selected[p]) for p in positions]+[[b'<u>']*order,[b'~TS-LM-MISSING~']*order],build_elapsed=time.monotonic()-t)
        R['tables'].append(e)
    # Full independent readback, not execution of the adapter's parser.
    for e in R['tables']:
        tick();t=time.monotonic();expected={tuple(q):{'found':False,'value_hex':None,'last_row_1based':None} for q in e['queries']};h=hashlib.sha256();ch=hashlib.sha256();ih=hashlib.sha256();off=0;rows=0;prev=None;dup=0
        with open(e['path'],'rb',buffering=1048576) as src,open(e['index_path'],'rb',buffering=1048576) as ix:
            while True:
                raw=src.readline(513)
                if not raw:break
                rows+=1
                if rows%8192==0:tick()
                b=ix.read(8);ih.update(b)
                if len(b)!=8 or int.from_bytes(b,'little')!=off:raise RuntimeError('READBACK_OFFSET')
                k,v=independent_parse(raw,e['order']);h.update(raw);ch.update(ref_serial(k,v));off+=len(raw)
                if prev is not None and k<prev:raise RuntimeError('READBACK_SORT')
                dup+=k==prev;prev=k
                if k in expected:expected[k]={'found':True,'value_hex':v.hex(),'last_row_1based':rows}
            b=ix.read(8);ih.update(b)
            if len(b)!=8 or int.from_bytes(b,'little')!=off or ix.read(1):raise RuntimeError('READBACK_EOF')
        if (rows,off,dup,h.hexdigest(),ch.hexdigest(),ih.hexdigest())!=(e['rows'],e['bytes'],e['duplicates'],e['sha256'],e['canonical_sha256'],e['index_sha256']):raise RuntimeError('READBACK_IDENTITY')
        e['reference']=[expected[tuple(q)] for q in e['queries']];e['readback_elapsed']=time.monotonic()-t
    d=DiskLM(R['tables'],tick,3);records=[];t=time.monotonic()
    try:
        for e in R['tables']:
            for i,q in enumerate(e['queries']):
                got=d.lookup(e['id'],tuple(q));assert got==e['reference'][i]
                records.append({'table':e['id'],'query_index':i,'key_hex':[k.hex() for k in q],'result':got})
            for i in [0,1,2,3,4,5,0,5,1]:
                got=d.lookup(e['id'],tuple(e['queries'][i]));assert got==e['reference'][i]
                got['value_hex']='caller mutation'
                assert d.lookup(e['id'],tuple(e['queries'][i]))==e['reference'][i]
        raw=frame(0,[x['result'] for x in records],True)
        assert unframe(raw,0)==([x['result'] for x in records],True)
        R['contract']={'queries':records,'cache_stats':d.stats,'elapsed':time.monotonic()-t,'response_frame_bytes':len(raw),'all36_queries_exact':True,'eviction_mutation_checks':54}
    finally:d.close()
    R['after']=memory();tick()
    if R['after']['memory.events']!=R['before']['memory.events']:raise RuntimeError('MEMORY_EVENTS_CHANGED')
    R['status']='PASS_FULL_CENSUS_INDEX_AND_FINITE_BYTE_CONTRACT'
def json_safe(x):
    if isinstance(x,bytes):return x.decode('ascii')
    if isinstance(x,dict):return {k:json_safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return list(map(json_safe,x))
    return x
if __name__=='__main__':
    code=0
    try:main()
    except BaseException as e:R.update(status='STOP',error=repr(e));code=2
    R.update(elapsed=time.monotonic()-START,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),self_peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if OUT.exists() and not (OUT/'result.json').exists():dump('result.json',json_safe(R))
    print(json.dumps({k:R.get(k) for k in ['status','error','elapsed','self_peak_rss_KiB']}));raise SystemExit(code)
