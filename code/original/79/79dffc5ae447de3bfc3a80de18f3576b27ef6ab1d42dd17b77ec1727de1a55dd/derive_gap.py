"""Own data-only derivation from preserved segment text/presence; NOT recovered primary bytes.
No scoring, dictionary lookup, solver functions, or imports from the package.
Finite scope: one segment, 30 <=128-element batches, 35 missing packets;
<=80 MiB reads, AS 256 MiB, CPU 20 s, cooperative 30 s.
"""
import pathlib,json,hashlib,struct,time,resource
resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(20,20))
T=time.monotonic();ROOT=pathlib.Path('/workspace/scratch/f24f8fae4976');O=ROOT/'BE_W16_RESPONSE_SEQ_audit_20261018';A=ROOT/'BE_W16_v1/attempt/case_01'
summary=json.loads((O/'summary.json').read_text());catalog=[json.loads(l) for l in (O/'frame_catalogue.jsonl').read_text().splitlines()]
segs=[]
with (A/'events.000.jsonl').open('rb') as f:
 for line in f:
  e=json.loads(line)
  if e['kind']=='segment_begin':segs.append(e['value'])
assert len(segs)==110 and all(len(x['text'])==87 and len(bytes.fromhex(x['presence_hex']))==3828 for x in segs)
before=[r for r in catalog if r['direction']==1 and r.get('op')=='words' and r['seq']<3284]
assert len(before)%30==0
segment=segs[len(before)//30];assert segment['id']==len(before)//30
text=segment['text'];ordered=[text[s:s+n] for s in range(87) for n in range(1,88-s)]
presence=bytes.fromhex(segment['presence_hex']);assert len(ordered)==len(presence)==3828 and set(presence)<={0,1}
def payload(x):return (json.dumps(x,ensure_ascii=True,separators=(',',':'),sort_keys=True,allow_nan=False)+'\n').encode('ascii')
def packet(d,x):
 b=payload(x);return struct.pack('>BI',d,len(b))+b
expected={}
for j in range(30):
 seq=3284+j;start=128*j
 expected[(1,seq)]=packet(1,[seq,'words',[w.encode('ascii').hex() for w in ordered[start:start+128]]])
 expected[(2,seq)]=packet(2,[seq,0,[bool(v) for v in presence[start:start+128]],True])
assert len(expected)==60
checked=[]
for r in catalog:
 k=(r['direction'],r['seq'])
 if k in expected:
  with (A/r['file']).open('rb') as f:f.seek(r['local_start']);b=f.read(r['local_end']-r['local_start'])
  assert b==expected[k],('PRESERVED_NEIGHBOR_DIFFERENCE',k)
  checked.append(list(k))
gap=b'';gaprows=[]
for seq in range(3285,3303):
 for d in (1,2):
  if d==2 and seq==3302:continue
  b=expected[(d,seq)];off=len(gap);gap+=b
  gaprows.append({'direction':d,'seq':seq,'derived_gap_start':off,'derived_gap_end':len(gap),'payload_bytes':len(b)-5,'sha256':hashlib.sha256(b).hexdigest()})
assert len(gaprows)==35 and len(gap)==187188
with (O/'DERIVED_NOT_PRIMARY_gap.bin').open('xb') as f:f.write(gap)
native=summary['native'];h=hashlib.sha256();orig=hashlib.sha256()
for j,p in enumerate(sorted(A.glob('frames.*.bin'))):
 with p.open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b);orig.update(b);assert time.monotonic()-T<30
 if j==0:h.update(gap)
match=h.hexdigest()==native['sha256'];assert match,'DERIVED_CHAIN_MISMATCH'
out={'kind':'DERIVED_NOT_PRIMARY; old files and STOP unchanged','source_event':segment,
 'first_missing_request':3285,'last_missing_request':3302,'first_missing_response':3285,'last_missing_response':3301,
 'observed_prior_word_requests':len(before),'segment_id_zero_based':segment['id'],'segment_batches':30,
 'missing_batch_indices_zero_based':[1,18],'neighbor_packets_exactly_compared':checked,
 'derived_gap':{'frames':len(gaprows),'container_bytes':len(gap),'payload_bytes':sum(r['payload_bytes'] for r in gaprows),'sha256':hashlib.sha256(gap).hexdigest(),'rows':gaprows},
 'actual_chain_sha256':orig.hexdigest(),'derived_completed_chain_sha256':h.hexdigest(),'native_chain_sha256':native['sha256'],'matches_native':match,
 'rotation':{'stored_shard0_bytes':8200753,'derived_complete_shard0_bytes':8200753+len(gap),'shard_cap':8388608,'remaining_room':8388608-8200753-len(gap),'first_packet_shard1_bytes':783,'would_exceed_cap_if_appended':8200753+len(gap)+783>8388608},
 'elapsed':time.monotonic()-T,'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
with (O/'derived_gap_evidence.json').open('x') as f:json.dump(out,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('source_event','derived_gap')},sort_keys=True),flush=True)
print('DERIVED_GAP_COMPUTED '+json.dumps({k:v for k,v in out['derived_gap'].items() if k!='rows'},sort_keys=True),flush=True)
