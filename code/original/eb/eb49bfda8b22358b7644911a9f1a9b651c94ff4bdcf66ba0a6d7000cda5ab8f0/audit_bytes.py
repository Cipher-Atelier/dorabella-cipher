"""Own data-only parser; no frozen module/function execution."""
import pathlib, hashlib, json, struct, time, resource, zipfile, datetime
resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(30,30))
T=time.monotonic(); read_total=0
ROOT=pathlib.Path('/workspace/scratch/f24f8fae4976')
OUT=ROOT/'BE_W16_RESPONSE_SEQ_audit_20261018'
A=ROOT/'BE_W16_v1/attempt/case_01'
def tick():
    assert time.monotonic()-T < 45,'TIME_BOUND'
def rd(p):
    global read_total
    tick(); assert p.stat().st_size <= 32*1024**2,'FILE_BOUND'
    b=p.read_bytes();read_total+=len(b);assert read_total<=300*1024**2,'READ_BOUND';return b
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(name,x):
    with (OUT/name).open('x') as f:json.dump(x,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
case_seal=json.loads(rd(A/'seal.json'));root_seal=json.loads(rd(A.parent/'seal.json'))
cs={r['path']:r for r in case_seal['files']};rs={r['path']:r for r in root_seal['files']}
zip_path=ROOT/'BE_W16_v1_execution_20261018/library_exact_copy/BE_W16_v1_full_execution_evidence.zip'
zbytes=rd(zip_path);assert sha(zbytes)=='4c8fb809dc5cf62c02c83647ec84e2465029ec49bccff93ef0a9761d9e1ab155'
ident=[];records=[];global_off=0;chain=hashlib.sha256();payload_total=0;shard_sizes=[]
with zipfile.ZipFile(zip_path) as z:
    for p in sorted(A.glob('frames.*.bin')):
        b=rd(p);assert len(b)<=8388608
        archived=z.read('BE_W16_v1/attempt/case_01/'+p.name);assert archived==b
        read_total+=len(archived);assert read_total<=300*1024**2
        row=cs[p.name];assert row['bytes']==len(b) and row['sha256']==sha(b)
        assert rs['case_01/'+p.name]['sha256']==sha(b)
        s=p.stat();ident.append({'path':p.name,'bytes':len(b),'sha256':sha(b),'case_seal':row,
          'current_stat':{'dev':s.st_dev,'ino':s.st_ino,'mtime_ns':s.st_mtime_ns,'mode':oct(s.st_mode&0o777)},'archive_equal':True})
        shard_sizes.append({'path':p.name,'start':global_off,'end':global_off+len(b)})
        off=0
        while off<len(b):
            tick();assert off+5<=len(b),'HEADER_CROSSES_SHARD'
            d,n=struct.unpack('>BI',b[off:off+5]);assert d in (1,2) and 0<n<=65536
            assert off+5+n<=len(b),'PAYLOAD_CROSSES_SHARD'
            payload=b[off+5:off+5+n];assert payload.endswith(b'\n');x=json.loads(payload)
            packet=b[off:off+5+n];chain.update(packet);payload_total+=n
            r={'frame_1based':len(records)+1,'file':p.name,'local_start':off,'local_end':off+5+n,
               'global_start':global_off+off,'global_end':global_off+off+5+n,
               'direction':d,'payload_bytes':n,'packet_sha256':sha(packet),'seq':x[0]}
            if d==1:r.update(op=x[1],arg_count=len(x[2]) if isinstance(x[2],list) else None)
            else:r.update(offset=x[1],value_count=len(x[2]),done=x[3])
            records.append(r);assert len(records)<=20000;off+=5+n
        global_off+=len(b)
    for name in ['events.000.jsonl','broker_terminal.json','consumer_terminal.json','broker_stdout.txt','perl_stdout.txt','result.json','seal.json']:
        b=rd(A/name);assert z.read('BE_W16_v1/attempt/case_01/'+name)==b
        if name!='seal.json':assert cs[name]['sha256']==sha(b)
        else:assert rs['case_01/seal.json']['sha256']==sha(b)
        ident.append({'path':name,'bytes':len(b),'sha256':sha(b),'archive_equal':True})
with (OUT/'frame_catalogue.jsonl').open('x') as f:
    for r in records:f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
requests=[r for r in records if r['direction']==1];responses=[r for r in records if r['direction']==2]
by_req={r['seq']:r for r in requests};by_resp={}
for r in responses:by_resp.setdefault(r['seq'],[]).append(r)
broker=json.loads(rd(A/'broker_terminal.json'));consumer=json.loads(rd(A/'consumer_terminal.json'))
assert broker['chain']==consumer['chain']
native=broker['chain'];last=consumer['transactions']
missq=[i for i in range(1,last+1) if i not in by_req];missr=[i for i in range(1,last+1) if i not in by_resp]
assert len(by_req)==len(requests),'DUP_REQUEST'
first=None;seq=0;pending=None;received=0;completed=0
for r in records:
    if r['direction']==1:
        if pending is not None or r['seq']!=seq+1:
            first={'kind':'REQUEST_SEQ','row':r,'prior_seq':seq,'expected_request_id':seq+1,'pending':pending};break
        seq+=1;pending=seq;received=0
    else:
        if pending is None or r['seq']!=seq or r['offset']!=received:
            first={'kind':'RESPONSE_SEQ','row':r,'prior_seq':seq,'pending':pending,'received_variable':received,
                   'next_expected':'request','next_expected_request_id':seq+1,'completed_transactions':completed};break
        received+=r['value_count']
        if r['done']:pending=None;completed+=1
boundary=[]
if first:
    i=first['row']['frame_1based']-1;boundary=records[max(0,i-4):i+5]
    with (OUT/'boundary_primary_packets.bin').open('xb') as f:
        for r in boundary:
            with (A/r['file']).open('rb') as q:q.seek(r['local_start']);f.write(q.read(r['local_end']-r['local_start']))
        # Exact concatenation of catalogued neighboring packets, not reconstructed data.
rawtool=rd(ROOT/'BE_W16_v1_execution_20261018/raw_tool_stdout.txt')
provenance={}
for name,prefix,expected in [('broker_stdout.txt',b'BROKER_COMPUTED ',broker),('perl_stdout.txt',b'CONSUMER_COMPUTED ',consumer)]:
    lines=rd(A/name).splitlines();matches=[x[len(prefix):] for x in lines if x.startswith(prefix)]
    assert len(matches)==1 and json.loads(matches[0])==expected
    provenance[name]={'parsed_exactly_equals_terminal':True,'native_hash_present':native['sha256'].encode() in b'\n'.join(lines)}
provenance['native_hash_in_original_parent_tool_stdout']=native['sha256'].encode() in rawtool
provenance['root_seal_in_original_parent_tool_stdout']=sha(rd(A.parent/'seal.json')).encode() in rawtool
provenance['case_seal_in_original_parent_tool_stdout']=sha(rd(A/'seal.json')).encode() in rawtool
summary={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'data-only; preserved case_01',
 'actual':{'frames':len(records),'requests':len(requests),'responses':len(responses),'payload_bytes':payload_total,'container_bytes':global_off,'sha256':chain.hexdigest()},
 'native':native,'difference':{'frames':native['frames']-len(records),'payload_bytes':native['bytes']-payload_total,'container_bytes':native['bytes']+5*native['frames']-global_off},
 'missing_request_ids':missq,'missing_response_ids':missr,'first_violation':first,'boundary':boundary,'shards':shard_sizes,
 'request_counts':{op:sum(r.get('op')==op for r in requests) for op in ['prefix','words','lm','close']},
 'native_counts':broker['counts'],'native_hash_provenance':provenance,
 'elapsed':time.monotonic()-T,'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'input_bytes_read':read_total}
dump('file_identity.json',ident);dump('summary.json',summary)
print(json.dumps(summary,sort_keys=True),flush=True)
