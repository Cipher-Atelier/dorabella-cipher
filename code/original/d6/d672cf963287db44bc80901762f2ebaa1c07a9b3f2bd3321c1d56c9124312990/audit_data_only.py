import pathlib,json,hashlib,zipfile,collections,resource,time,struct,os,sys,datetime
B=pathlib.Path(__file__).parent;P=json.loads((B/'PLAN.json').read_text());T=time.monotonic()
resource.setrlimit(resource.RLIMIT_AS,(268435456,268435456));resource.setrlimit(resource.RLIMIT_CPU,(55,60));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def tick():
 if time.monotonic()-T>60:raise RuntimeError('STOP_AUDIT_WALL')
def hashfile(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b);tick()
 return h.hexdigest()
def dump(n,x):
 with (B/n).open('x') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
start=datetime.datetime.now(datetime.timezone.utc).isoformat();zpath=pathlib.Path(P['source_zip']);assert hashfile(zpath)==P['source_zip_sha256']
with zipfile.ZipFile(zpath) as z:
 assert sum(x.file_size for x in z.infolist())<=P['limits']['input_uncompressed_bytes']
 seal=json.loads(z.read('attempt/seal.json'));assert hashlib.sha256(z.read('attempt/seal.json')).hexdigest()==P['source_seal_sha256']
 assert hashlib.sha256(z.read('FREEZE.json')).hexdigest()==P['source_freeze_sha256']
 for row in seal['files']:
  h=hashlib.sha256();size=0
  with z.open('attempt/'+row['path']) as f:
   for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk);size+=len(chunk);tick()
  assert (size,h.hexdigest())==(row['bytes'],row['sha256'])
 manifest=json.loads(z.read('MANIFEST.json'));verified_sources=[]
 selected=['runtime/adapter.py','runtime/CompactPatList.pm','runtime/Observe.pm','runtime/broker.py','runtime/profile.pl','runtime/StreamAudit.pm','runtime/original/NoSpace.pm','runtime/original/Utils.pm']
 with (B/'source_excerpt_lines.txt').open('x') as out:
  for n in selected:
   b=z.read(n);row=next(x for x in manifest['files'] if x['path']==n);assert hashlib.sha256(b).hexdigest()==row['sha256'];verified_sources.append(row)
   out.write('\nFILE '+n+' SHA256 '+row['sha256']+'\n')
   for i,line in enumerate(b.decode().splitlines(),1):out.write(str(i)+'\t'+line+'\n')
 d={};lru=collections.OrderedDict();n=0;ordinal=0;truth=collections.Counter();hits=collections.Counter();lengths=collections.Counter();sections=[];other=[]
 request_bytes=response_bytes=hits_wire_bytes=0;max_cache_payload=0;cache_payload=0;evictions=0;hit_repeats=0;compulsory=capacity=0
 data_chain=hashlib.sha256();journal_bytes=0
 names=sorted(n for n in z.namelist() if n.startswith('attempt/pat_refs.') and n.endswith('.jsonl'))
 with (B/'ordered_logical_refs.bin').open('xb') as refs:
  for name in names:
   offset=0
   with z.open(name) as f:
    for raw in f:
     tick();assert raw.endswith(b'\n');journal_bytes+=len(raw);x=json.loads(raw);ordinal+=1;assert ordinal<=200003 and x['ordinal']==ordinal
     req=json.loads(x['request']);assert req[0]==ordinal and len(req)==3
     if req[1]!='word':other.append({'ordinal':ordinal,'request':req,'file':name,'offset':offset});offset+=len(raw);continue
     key=req[2];kb=key.encode('ascii');val=x['found'];assert type(val) is bool and 0<len(kb)<=87 and key.isalpha() and key.islower()
     n+=1;assert n<=200000;lengths[len(kb)]+=1;truth[str(val)]+=1
     if len(kb)==87:
      if sections:sections[-1].update(last_word_index=n-1,last_ordinal=ordinal-1,completed_by_next_entry=True)
      sections.append({'top':len(sections)+1,'text':key,'sha256':hashlib.sha256(kb).hexdigest(),'first_word_index':n,'first_ordinal':ordinal,'file':name,'offset':offset,'true':0,'false':0,'lru_hits':0})
     assert sections;sections[-1]['true' if val else 'false']+=1
     first=key not in d
     if first:d[key]={'id':len(d)+1,'key':key,'found':val,'count':0,'first_word_index':n,'first_ordinal':ordinal,'first_file':name,'first_offset':offset,'last_word_index':n,'lru_hits':0}
     entry=d[key];assert entry['found'] is val;entry['count']+=1;entry['last_word_index']=n
     hit=key in lru
     rb=x['request'].encode('ascii');sb=('['+str(ordinal)+',"value",'+str(int(val))+']\n').encode();request_bytes+=len(rb);response_bytes+=len(sb)
     if hit:
      assert lru[key] is val;lru.move_to_end(key);hits[str(val)]+=1;entry['lru_hits']+=1;sections[-1]['lru_hits']+=1;hits_wire_bytes+=len(rb)+len(sb)
     else:
      compulsory+=int(first);capacity+=int(not first)
      if len(lru)==1024:
       old,_=lru.popitem(last=False);cache_payload-=len(old);evictions+=1
      lru[key]=val;cache_payload+=len(kb);max_cache_payload=max(max_cache_payload,cache_payload)
     refs.write(struct.pack('>IBB',entry['id'],int(val),int(hit)))
     data_chain.update(struct.pack('>IB',len(kb),int(val)));data_chain.update(kb)
     offset+=len(raw)
  refs.flush();os.fsync(refs.fileno())
 assert n==200000 and ordinal==200003
 sections[-1].update(last_word_index=n,last_ordinal=ordinal,completed_by_next_entry=False)
 for s in sections:s['membership_records']=s['last_word_index']-s['first_word_index']+1
 bt=json.loads(z.read('attempt/broker_terminal.json'));assert sum(hits.values())==bt['pat']['word_hits'] and compulsory+capacity==bt['pat']['word_queries'] and n==bt['membership']
 assert max(lengths)<=87 and lengths[87]==len(sections)
 # Independent reductions of saved frequency ledger; no dictionary/model queries.
 freq=collections.Counter(e['count'] for e in d.values());assert sum(k*v for k,v in freq.items())==n and sum(freq.values())==len(d)
 distinct_truth=collections.Counter(str(e['found']) for e in d.values());assert sum(e['count'] for e in d.values() if e['found'])==truth['True']
 with (B/'distinct_keys.jsonl').open('x') as f:
  for e in d.values():f.write(json.dumps(e,sort_keys=True,separators=(',',':'))+'\n')
 # Independent exact reconstruction of logical key/value order from ledger+fixed-width refs.
 ids=[None]+[(e['key'].encode('ascii'),e['found']) for e in d.values()];check=hashlib.sha256();nn=hh=0
 with (B/'ordered_logical_refs.bin').open('rb') as f:
  while True:
   b=f.read(6)
   if not b:break
   assert len(b)==6;di,v,h=struct.unpack('>IBB',b);k,truthv=ids[di];assert v==int(truthv) and h in (0,1);check.update(struct.pack('>IB',len(k),v));check.update(k);nn+=1;hh+=h
 assert nn==n and hh==sum(hits.values()) and check.hexdigest()==data_chain.hexdigest()
 profile=[json.loads(x) for x in z.read('attempt/profile.jsonl').splitlines()]
 cat=json.loads(z.read('catalogue/catalogue.json'));row=next(x for x in cat if x['id']==134);assert row['pattern']=='ab'
 # Only read the already saved first candidate list; no Assume/Decipher/FindWords calls.
 values=[]
 with z.open('catalogue/catalogue.bin') as f:
  f.seek(row['offset'])
  for _ in range(row['count']):
   l=f.read(1);assert len(l)==1;b=f.read(l[0]);assert len(b)==l[0];values.append(b.decode('ascii'))
 assert len(values)==925
 for s in sections:s['matching_first50_list_positions_1based']=[i for i,v in enumerate(values[:50],1) if v==s['text'][:2]]
 dump('top_level_boundaries.json',{'basis':'source-backed length87 membership entry; exact raw offsets; no segmentation replay','sections':sections,'first50_list_values':values[:50],'catalogue_descriptor':row,'remaining_uncertainty':'last top incomplete; intermediate segmented output strings/recursive call count not logged after top4'})
 unique_bytes=sum(len(k) for k in d);maxkey=max(map(len,d));upper_slots=1024*(87+1)
 result={'status':'DATA_AUDIT_COMPLETE','utc_start':start,'utc_end':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_zip_sha256':P['source_zip_sha256'],'source_seal_sha256':P['source_seal_sha256'],'verified_sources':verified_sources,'membership':n,'distinct_keys':len(d),'repeat_calls':n-len(d),'distinct_true_false':dict(distinct_truth),'calls_true_false':dict(truth),'frequency_histogram':dict(sorted(freq.items())),'length_histogram':dict(sorted(lengths.items())),'unique_key_bytes':unique_bytes,'max_key_bytes':maxkey,'cache1024':{'hits':sum(hits.values()),'hits_true_false':dict(hits),'misses':compulsory+capacity,'compulsory_misses':compulsory,'capacity_repeat_misses':capacity,'evictions':evictions,'max_key_payload_bytes':max_cache_payload,'fixed_slot_key_payload_bound':upper_slots,'server_terminal_exact_match':True},'top_started':len(sections),'top_distinct_inputs':len({s['text'] for s in sections}),'top_completed_inferred':len(sections)-1,'last_top_partial':len(sections),'other_requests':other,'request_bytes_original_seq':request_bytes,'response_bytes_from_recorded_values_original_seq':response_bytes,'lru_hit_pair_bytes_original_seq':hits_wire_bytes,'lru_hit_pair_frames':2*sum(hits.values()),'journal_bytes':journal_bytes,'ledger_bytes':(B/'distinct_keys.jsonl').stat().st_size,'ordered_ref_bytes':(B/'ordered_logical_refs.bin').stat().st_size,'ordered_logical_sha256':data_chain.hexdigest(),'ordered_reference_readback_match':True,'profile_events':profile,'elapsed_seconds':time.monotonic()-T,'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scientific_execution':False,'truth_lookup_revalidated':False}
 dump('counts.json',result)
 assert sum(p.stat().st_size for p in B.iterdir() if p.is_file())<=67108864
 print(json.dumps({k:v for k,v in result.items() if k not in ('verified_sources','frequency_histogram','length_histogram','profile_events','other_requests')},sort_keys=True))
 print('COUNTS_COMPUTED_SHA256',hashfile(B/'counts.json'))
 print('AUDIT_CODE_COMPUTED_SHA256',hashfile(pathlib.Path(__file__)))
