"""Own data-only one-pass catalogue, not a solver or its function port."""
import json,pathlib,time,resource,hashlib,datetime,sys
R=pathlib.Path(__file__).resolve().parent
T=time.monotonic();resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2);resource.setrlimit(resource.RLIMIT_CPU,(85,90))
out=R/'catalogue';out.mkdir(exist_ok=False)
parent=json.loads((R/'provenance/BOUND_RESULT.json').read_text())['patterns']
meta={x['pattern'].encode():x for x in parent};bins={p:bytearray() for p in meta};counts={p:0 for p in meta};segments={p:0 for p in meta}
source=pathlib.Path(next(x['path'] for x in json.loads((R/'model_inputs.json').read_text()) if x['path'].endswith('.patlst')))
h=hashlib.sha256();rows=0;total=0
try:
 with source.open('rb') as f:
  while raw:=f.readline(118054):
   rows+=1;total+=len(raw);h.update(raw)
   assert rows<=7548932 and total<=340083717 and len(raw)<=118052
   if rows%8192==0:assert time.monotonic()-T<90
   fields=[x for x in raw.rstrip(b' \t\r\n\v\f').replace(b' ',b'').split(b'\t') if x]
   assert len(fields)>=3 and fields[0] in (b'1',b'2',b'3')
   p=fields[1]
   if p not in bins:continue
   segments[p]+=1
   for word in fields[2:]:
    assert 1<=len(word)<=46 and all(97<=x<=122 for x in word)
    bins[p].append(len(word));bins[p].extend(word);counts[p]+=1
 assert rows==7548932 and total==340083717 and h.hexdigest()=='2849bc03f85c59a422f1945960ce04a4b6e66cc02c61a6484de0283c30c724fd'
 descriptors=[];offset=0
 with (out/'catalogue.bin').open('xb') as f:
  for id,m in enumerate(parent):
   p=m['pattern'].encode();v=bins[p];assert counts[p]==m['candidate_count'] and segments[p]==m['segments']
   # Decode our own output, only bytes/order/length checks; no key or score.
   pos=0;words=[]
   while pos<len(v):
    n=v[pos];pos+=1;w=bytes(v[pos:pos+n]);pos+=n;words.append(w)
   assert pos==len(v) and len(words)==counts[p] and max(map(len,words),default=0)==m['longest']
   d=dict(id=id,pattern=m['pattern'],offset=offset,bytes=len(v),count=counts[p],segments=segments[p],payload=sum(map(len,words)),sha256=hashlib.sha256(v).hexdigest(),unique=len(set(words)),prefix50_unique=len(set(words[:50])),longest=m['longest'])
   descriptors.append(d);f.write(v);offset+=len(v)
 catsha=hashlib.sha256((out/'catalogue.bin').read_bytes()).hexdigest()
 assert sum(counts.values())==682961 and offset==6221764
 assert catsha=='8e29af726d88e0c2e711e03ab4019a3b0666fb0d4184302080edd6733013e76e'
 (out/'catalogue.json').write_text(json.dumps(descriptors,separators=(',',':'))+'\n')
 result={'status':'CATALOGUE_RECONSTRUCTED_EXACT','new_version':True,'source_rows':rows,'source_bytes':total,'source_sha256':h.hexdigest(),'selected_entries':sum(counts.values()),'catalogue_bytes':offset,'catalogue_sha256':catsha,'matches_previous_visible_hash':True,'elapsed':time.monotonic()-T,'ru_maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'exit':0,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'foreign_execution':False}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
except BaseException as e:
 (out/'STOP.json').write_text(json.dumps({'error':repr(e),'rows':rows,'bytes':total,'elapsed':time.monotonic()-T})+'\n');raise
