"""Own copy/hash-only packaging. No package code imports or execution."""
import pathlib,json,hashlib,zipfile,io,shutil
R=pathlib.Path('/workspace/scratch/f24f8fae4976');O=R/'BE_W16_RESPONSE_SEQ_audit_20261018';A=R/'BE_W16_v1/attempt'
def h(b):return hashlib.sha256(b).hexdigest()
def put(p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
def dump(p,x):put(p,(json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode())
sourcefiles=['runtime/common.py','runtime/broker.py','runtime/driver.pl','runtime/readback.py','runtime/supervisor.py','runtime/child_gate.py','runtime/launch.py']
manifest=json.loads((R/'BE_W16_v1/MANIFEST.json').read_text());mm={x['path']:x for x in manifest['files']};sources=[]
frozen=R/'Dorabella_BE_W16_v1_frozen_20261018.zip'
assert h(frozen.read_bytes())=='3eb98372153182698b12e15ba5d8108b402f790f7f782d968ce9bc3625d411f4'
with zipfile.ZipFile(frozen) as z:
 for name in sourcefiles:
  p=R/'BE_W16_v1'/name;b=p.read_bytes();assert h(b)==mm[name]['sha256'] and len(b)==mm[name]['bytes']
  matches=[n for n in z.namelist() if n.endswith('/'+name) or n==name];assert len(matches)==1
  assert z.read(matches[0])==b
  put(O/'source'/name,b);sources.append({'path':name,'bytes':len(b),'sha256':h(b),'frozen_zip_equal':True})
  put(O/'source'/('numbered_'+p.name+'.txt'),''.join(f'{i:4d} {s}' for i,s in enumerate(b.decode().splitlines(keepends=True),1)).encode())
dump(O/'source_identity.json',sources)
for name in ['MANIFEST.json','FREEZE.json']:put(O/'source'/name,(R/'BE_W16_v1'/name).read_bytes())
primary_names=['frames.000.bin','frames.001.bin','frames.002.bin','frames.003.bin','events.000.jsonl','broker_stdout.txt','broker_stderr.txt','perl_stdout.txt','perl_stderr.txt','broker_terminal.json','consumer_terminal.json','result.json','seal.json']
for n in primary_names:put(O/'primary/case_01'/n,(A/'case_01'/n).read_bytes())
put(O/'primary/root_seal.json',(A/'seal.json').read_bytes())
for name in ['raw_tool_receipt.json','raw_tool_stdout.txt','data_only_observations.json','delivery_readback.json']:
 put(O/'primary'/name,(R/'BE_W16_v1_execution_20261018'/name).read_bytes())
zpath=R/'BE_W16_v1_execution_20261018/library_final_copy/Dorabella_BE_W16_v1_result_20261018.zip'
assert h(zpath.read_bytes())=='ac5c22a2ee5497a9ec83c2ea5749da3a88a0865feca64315054c43c4073b7415'
with zipfile.ZipFile(zpath) as z:
 names=[n for n in z.namelist() if n.endswith('BE_W16_v1_full_execution_evidence.zip')];assert len(names)==1
 nested=z.read(names[0]);assert h(nested)=='4c8fb809dc5cf62c02c83647ec84e2465029ec49bccff93ef0a9761d9e1ab155'
 with zipfile.ZipFile(io.BytesIO(nested)) as old:
  for n in primary_names:assert old.read('BE_W16_v1/attempt/case_01/'+n)==(O/'primary/case_01'/n).read_bytes()
dump(O/'archived_copy_check.json',{'status':'EXACT_PRIMARY_COPIES','primary_zip_sha256':h(nested),'final_zip_sha256':h(zpath.read_bytes()),'case_files_checked':primary_names,'historical_STOP_unchanged':True})
# First parser output was observed as chunk 1e0023. This record is explicitly
# a transcript reference, not a claim of saving that returned object at the time.
dump(O/'parser_tool_reference.json',{'chunk_id':'1e0023','observed_exit_code':0,'tool_wall_seconds':0.499762386,'summary_file':'summary.json','provenance':'Transcript reference added during packaging. The full computed JSON is summary.json; original tool output remains in conversation.'})
selected=[p for p in sorted(O.rglob('*')) if p.is_file() and 'library_helpers' not in p.parts and p.name not in ('evidence_manifest.json',) and p.suffix!='.zip']
rows=[{'path':str(p.relative_to(O)),'bytes':p.stat().st_size,'sha256':h(p.read_bytes())} for p in selected]
dump(O/'evidence_manifest.json',{'scope':'RESPONSE_SEQ audit only; STOP unchanged','files':rows})
out=R/'Dorabella_BE_W16_RESPONSE_SEQ_audit_evidence_20261018.zip'
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in selected+[O/'evidence_manifest.json']:z.write(p,str(p.relative_to(O)))
with zipfile.ZipFile(out) as z:
 for r in rows:assert h(z.read(r['path']))==r['sha256']
print('AUDIT_ZIP_COMPUTED '+json.dumps({'path':str(out),'bytes':out.stat().st_size,'sha256':h(out.read_bytes()),'members':len(rows)+1},sort_keys=True),flush=True)
print('REPORT_COMPUTED_SHA256 '+h((O/'Dorabella_BE_W16_RESPONSE_SEQ_audit_RU.md').read_bytes()),flush=True)
