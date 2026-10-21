from pathlib import Path
import shutil,hashlib,json,zipfile
H=Path(__file__).resolve().parents[1];D=H/'deliverables';D.mkdir(exist_ok=True)
S=D/'bundle_staging';R=S/'dorabella_round13';R.mkdir(parents=True,exist_ok=True)
def cp(p,rel):
 dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
for name in ['code','data','checks']:
 for p in (H/name).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.json','.npz']:cp(p,p.relative_to(H))
for name in ['frozen_protocol.json','environment.json','requirements.txt','README_REPRODUCE_RU.md','FULL_RUN_MANIFEST.sha256']:cp(H/name,name)
for name,target in [('results','reference_results'),('checkpoints','main_checkpoints'),('audit','unpruned_audit'),('logs','logs')]:
 for p in (H/name).rglob('*'):
  if p.is_file() and p.suffix in ['.json','.log']:cp(p,Path('evidence')/target/p.relative_to(H/name))
for src in ['dorabella_audit/test_lab/wordpolish_v3.py','dorabella_audit/test_lab/conditional_v7.py','dorabella_audit/round11/dorabella_lab/round11/engine.py']:
 p=S/src;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(H.parent/src,p)
# Bundle only intentional copies, not later smoke-run products in the staging tree.
include=[]
for p in S.rglob('*'):
 if not p.is_file():continue
 rel=p.relative_to(S)
 if rel.parts[0]=='dorabella_round13' and rel.parts[1] in ['cache','checkpoints','results','logs','audit']:continue
 if '__pycache__' in rel.parts or p.name in ['runner.lock','BUNDLE_MANIFEST.sha256']:continue
 include.append(p)
manifest=R/'BUNDLE_MANIFEST.sha256';manifest.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(S))+'\n' for p in sorted(include)));include.append(manifest)
out=D/'dorabella_round13_reproducible_bundle.zip'
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(include):z.write(p,str(p.relative_to(S)))
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for line in manifest.read_text().splitlines():
  h,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==h
print(json.dumps({'path':str(out),'bytes':out.stat().st_size,'files':len(include),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
