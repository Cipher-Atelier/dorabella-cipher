from pathlib import Path
import json,hashlib,shutil,datetime,importlib.metadata,subprocess
R=Path('/mnt/data/dorabella_audit_20261002'); src=R/'restored'; dst=R/'work'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((src/'dorabella_lab/round11/delivery_manifest.json').read_text())
checks=[]
for n,expected in manifest['included_files_sha256'].items():
 p=src/n
 assert p.is_file(),n
 assert h(p)==expected,n
 checks.append(n)
archive=json.loads((R/'archive_manifest.json').read_text())
assert archive['dorabella_lab_round10.zip']['sha256']==manifest['base_archive_sha256']
old=json.loads((src/'dorabella_lab/round11/audit/round10_file_hashes.json').read_text())
assert len(old)==7500
for n,expected in old.items():assert h(src/n)==expected,n
cases=json.loads((src/'dorabella_lab/round11/data/cases.json').read_text())
complete=[];blocks=0
for c in cases:
 folder=src/'dorabella_lab/round11/checkpoints'/c['id']
 t=json.loads((folder/'training_result.json').read_text())
 assert t['status']=='complete' and len(t['blocks'])==40
 result=json.loads((src/'dorabella_lab/round11/results'/f"{c['id']}.json").read_text())
 assert result['status']=='verified'
 complete.append(c['id']);blocks+=len(t['blocks'])
versions={n:importlib.metadata.version(n) for n in ['numpy','numba','scipy','textblob','gensim']}
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base_files_sha256_verified':len(old),
'round11_manifest_entries_sha256_verified':len(checks),'main_case_files_with_complete_status':len(complete),'main_blocks_declared_complete':blocks,
'case_ids':complete,'current_versions':versions,'protocol_sha256':h(src/'dorabella_lab/round11/frozen_protocol.json'),
'interpretation':'File integrity and stored completion flags only here; numerical repeats are separate.'}
(R/'integrity_audit.json').write_text(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='case_ids'},indent=2),flush=True)
if dst.exists():raise RuntimeError('Work copy exists; refusing overwrite')
shutil.copytree(src,dst)
print('Independent work copy created',flush=True)
