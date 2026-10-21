"""Own data-only delivery gate. Does NOT run broker, Perl, segmentation or scoring.
Arguments: downloaded ZIP, expected ZIP hash from primary tool output,
raw primary tool stdout text, separate new output JSON. Never rewrites attempt.
"""
import sys,pathlib,hashlib,zipfile,json
def h(b):return hashlib.sha256(b).hexdigest()
def main():
 zpath,expected,rawpath,out=sys.argv[1:];p=pathlib.Path(zpath);d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 if d.hexdigest()!=expected:raise ValueError('STOP_DELIVERY_ZIP_HASH')
 raw=pathlib.Path(rawpath).read_text();claimed=[line.split('SEAL_COMPUTED_SHA256 ',1)[1].strip() for line in raw.splitlines() if line.startswith('SEAL_COMPUTED_SHA256 ')]
 if len(claimed)!=1:raise ValueError('STOP_PRIMARY_STDOUT_SEAL')
 with zipfile.ZipFile(p) as z:
  names=z.namelist()
  if len(names)!=len(set(names)) or any(n.startswith('/') or '..' in pathlib.PurePosixPath(n).parts for n in names):raise ValueError('STOP_ZIP_NAMES')
  roots=[n for n in names if n.endswith('/attempt/seal.json') or n=='attempt/seal.json']
  if len(roots)!=1:raise ValueError('STOP_ROOT_SEAL')
  root=roots[0][:-len('seal.json')];sb=z.read(roots[0])
  if h(sb)!=claimed[0]:raise ValueError('STOP_PRIMARY_VS_SAVED_SEAL')
  seal=json.loads(sb);rows=seal['files'];expected_members={root+x['path'] for x in rows}|{roots[0]}
  actual={n for n in names if n.startswith(root) and not n.endswith('/')}
  if actual!=expected_members:raise ValueError('STOP_MEMBER_SET')
  for row in rows:
   b=z.read(root+row['path'])
   if len(b)!=row['bytes'] or h(b)!=row['sha256']:raise ValueError('STOP_CLOSED_FILE_HASH:'+row['path'])
  result=json.loads(z.read(root+'result.json'))
  for kind in ('integration','cases'):
   for case in result[kind]:
    rel=case['name']+'/seal.json';cs=json.loads(z.read(root+rel))
    if h(z.read(root+rel))!=case['seal_receipt']['seal_sha256']:raise ValueError('STOP_CASE_SEAL_HASH')
    for row in cs['files']:
     b=z.read(root+case['name']+'/'+row['path'])
     if len(b)!=row['bytes'] or h(b)!=row['sha256']:raise ValueError('STOP_CASE_MEMBER')
    if not case.get('verified_termination'):raise ValueError('STOP_UNVERIFIED_TERMINATION')
    if case['status'] in ('PASS_FINITE_INTEGRATION','CASE_COMPLETE_CANDIDATE'):
     if len(case['terminal'])!=2 or any(t['exit']!=0 or t['group'] for t in case['terminal']):raise ValueError('STOP_TERMINAL')
     r=json.loads(z.read(root+case['name']+'/independent_readback.json'))
     if r!=case['readback']:raise ValueError('STOP_READBACK_SERIALIZATION')
  decision=result.get('evaluation',{}).get('decision','NO_GO')
  status='DELIVERY_VERIFIED_GO_FOR_REVIEW' if result['status']=='COMPLETED_PILOT_CANDIDATE' and result['exit_code']==0 and decision=='GO_CANDIDATE_PENDING_DELIVERY' else 'DELIVERY_VERIFIED_NO_GO'
  receipt={'status':status,'zip_sha256':expected,'seal_sha256':claimed[0],'files_verified':len(rows),'primary_stdout_sha256':h(pathlib.Path(rawpath).read_bytes()),'target_authorization':False,'historical_STOP_unchanged':True}
  with pathlib.Path(out).open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2);f.write('\n')
  print(json.dumps(receipt,sort_keys=True));print('DELIVERY_RECEIPT_COMPUTED_SHA256 '+h(pathlib.Path(out).read_bytes()))
if __name__=='__main__':main()
