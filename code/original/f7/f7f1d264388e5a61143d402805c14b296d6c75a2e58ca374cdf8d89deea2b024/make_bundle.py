"""Durable checkpoints: package ONLY completed runs, label incomplete snapshots."""
from pathlib import Path
import json,hashlib,zipfile,datetime
R=Path(__file__).resolve().parents[1]
events=[]
for line in (R/'logs/events.jsonl').read_text().splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
done={x['case'] for x in events if x.get('event')=='complete'}
status=json.loads((R/'STATUS.json').read_text()) if (R/'STATUS.json').exists() else {'status':'running'}
verified=json.loads((R/'checks/results_verified.json').read_text()) if (R/'checks/results_verified.json').exists() else None
snapshot={'snapshot_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed_cases':len(done),'target_cases':52,
          'status':'complete_and_verified' if len(done)==52 and status['status']=='completed' and verified and verified['status']=='PASS' else 'INCOMPLETE_checkpoint_not_a_calibration_result',
          'driver_status':status,'completed_ids':sorted(done)}
files=[]
for p in sorted(R.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(R)
    if rel.parts[0]=='dependencies' or '__pycache__' in rel.parts:continue
    if rel.parts[0]=='runs' and rel.parts[1] not in done:continue
    if p.suffix in ['.pyc','.nbc','.nbi']:continue
    files.append(p)
dest=R.parent/'Dorabella_R6_wordall_calibration_20261015.zip';manifest={}
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:
        data=p.read_bytes();name=str(p.relative_to(R));manifest[name]=hashlib.sha256(data).hexdigest();z.writestr(R.name+'/'+name,data)
    z.writestr(R.name+'/SNAPSHOT_STATUS.json',json.dumps(snapshot,indent=2)+'\n')
    z.writestr(R.name+'/BUNDLE_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(dest) as z:assert z.testzip() is None
print(json.dumps({'bundle':str(dest),'bytes':dest.stat().st_size,'files':len(files),'snapshot':snapshot}))
