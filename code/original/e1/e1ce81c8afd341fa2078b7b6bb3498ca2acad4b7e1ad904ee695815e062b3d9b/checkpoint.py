"""Data-only closed checkpoint packaging; never touches original attempt bytes."""
import pathlib,json,hashlib,zipfile,sys,datetime
B=pathlib.Path('/workspace/scratch/f24f8fae4976');E=B/'BE_W16_v2_execution_20261018';A=B/'BE_W16_v2/attempt'
def h(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 return d.hexdigest()
def rawreceipts():
 return ''.join(json.loads(p.read_text())['response']['output'] for p in sorted(E.glob('tool_receipt_*.json')))
raw=rawreceipts();seals={}
for line in raw.splitlines():
 if line.startswith('CLOSED_FILES_COMPUTED '):
  r=json.loads(line.split(' ',1)[1]);seals[r['folder']]=r
for name in sys.argv[1:]:
 assert name in seals and name!='.'
 folder=A/name;sb=folder/'seal.json';native=seals[name];assert h(sb)==native['seal_sha256']
 s=json.loads(sb.read_text());expected={r['path'] for r in s['files']}|{'seal.json'}
 assert expected=={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}
 for r in s['files']:
  p=folder/r['path'];assert p.stat().st_size==r['bytes'] and h(p)==r['sha256'],r['path']
 out=E/('Dorabella_BE_W16_v2_'+name+'_checkpoint.zip');assert not out.exists()
 with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
  for p in sorted(folder.rglob('*')):
   if p.is_file():z.write(p,str(p.relative_to(B)))
 result=json.loads((folder/'result.json').read_text());rec={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checkpoint':name,'zip':str(out),'zip_sha256':h(out),'zip_bytes':out.stat().st_size,'files_verified':len(s['files']),'native_closed_receipt':native,'status':result['status'],'verified_termination':result['verified_termination'],'terminal':result['terminal'],'readback':result.get('readback'),'partial_observations':result.get('partial_observations'),'pilot_still_pending':True}
 with (E/(name+'_checkpoint_receipt.json')).open('x') as f:json.dump(rec,f,indent=2,sort_keys=True);f.write('\n')
 print('CHECKPOINT_COMPUTED '+json.dumps({k:v for k,v in rec.items() if k not in ('readback','partial_observations','terminal')},sort_keys=True),flush=True)
 if 'readback' in result:print('CASE_READBACK '+json.dumps(result['readback'],sort_keys=True),flush=True)
