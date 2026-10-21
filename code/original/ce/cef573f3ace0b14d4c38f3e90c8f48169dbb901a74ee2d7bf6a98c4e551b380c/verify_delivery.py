"""Own data-only post-delivery binding. No attempt, broker, model lookup or scoring."""
import sys,json,pathlib,zipfile,hashlib
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 local,download,receipt,out=map(pathlib.Path,sys.argv[1:]);assert not out.exists()
 assert sha(local)==sha(download)
 assert local.stat().st_size<=128*1024**2 and download.stat().st_size<=128*1024**2 and receipt.stat().st_size<=8388608
 r=json.loads(receipt.read_text());assert 'tool_response_raw' in r and r['observed_exit'] is not None
 responses=r['tool_response_raw'];assert type(responses) is list and 1<=len(responses)<=1024
 assert all(type(x) is dict and type(x.get('output')) is str for x in responses)
 assert ''.join(x['output'] for x in responses)==r['observed_stdout']
 assert responses[-1].get('exit_code')==r['observed_exit'] and all(x.get('exit_code') is None for x in responses[:-1])
 sessions={x['session_id'] for x in responses if x.get('session_id') is not None};assert len(sessions)<=1
 with zipfile.ZipFile(download) as z:
  names=z.namelist();assert len(names)<=256 and len(set(names))==len(names) and all(not x.startswith('/') and '..' not in pathlib.PurePosixPath(x).parts for x in names)
  assert sum(x.file_size for x in z.infolist())<=128*1024**2 and all(x.file_size<=8388608 for x in z.infolist())
  sealbytes=z.read('attempt/seal.json');seal=json.loads(sealbytes);computed='SEAL_COMPUTED_SHA256 '+hashlib.sha256(sealbytes).hexdigest()
  freeze=z.read('FREEZE.json');assert hashlib.sha256(freeze).hexdigest()==seal['freeze_sha256']
  assert r['command']==json.loads(freeze)['launch_shell_command']
  stdout=r['observed_stdout'];assert computed in stdout.splitlines()
  lines=[x[len('CLOSED_FILES_COMPUTED '):] for x in stdout.splitlines() if x.startswith('CLOSED_FILES_COMPUTED ')];assert len(lines)==1 and json.loads(lines[0])==seal
  for x in seal['files']:
   b=z.read('attempt/'+x['path']);assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256']
  result=json.loads(z.read('attempt/result.json'));assert result['exit_code']==r['observed_exit']==seal['exit_code'] and result['status']==seal['status']
  assert result['verified_termination'] and seal['elapsed_to_seal']<=180
  status=result['status'];accepted=status in ('CONTROL_RECOVERED','CONTROL_NOT_RECOVERED')
  if accepted:
   assert r['observed_exit']==0 and result['readback']['inverse87'] and len(result['readback']['completed_iterations'])==2
   assert all(x['exit']==0 and x['group']==[] for x in result['terminal'])
  value={'status':'DELIVERY_BOUND_COMPLETE' if accepted else 'DELIVERY_BOUND_STOP_OR_INCOMPLETE','scientific_status':status,'zip_sha256':sha(download),'raw_receipt_sha256':sha(receipt),'seal_sha256':hashlib.sha256(sealbytes).hexdigest(),'tool_provenance_limit':'receipt must contain exact tool-returned JSON and observed stdout, never a model paraphrase; this checker cannot attest provenance of a fabricated receipt','no_old_STOP_reclassification':True}
 out.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
if __name__=='__main__':main()
