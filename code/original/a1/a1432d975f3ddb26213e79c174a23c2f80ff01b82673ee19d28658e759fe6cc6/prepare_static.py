"""Own one-time data-only preparation; no candidate module imported/executed."""
import ast,difflib,hashlib,json,pathlib,sys,zipfile
R=pathlib.Path(__file__).resolve().parent;OLD=R.parent/'BE_W16_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def put(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(b)
def dump(p,x):put(p,(json.dumps(x,sort_keys=True,indent=2)+'\n').encode())
m=json.loads((OLD/'MANIFEST.json').read_text());rows=[]
for row in m['files']:
 if row['external']:continue
 b=(OLD/row['path']).read_bytes();assert len(b)==row['bytes'] and sha(b)==row['sha256']
 rows.append({'path':row['path'],'bytes':len(b),'sha256':sha(b)})
old=(OLD/'runtime/broker.py').read_text();new=old
changes=[('from common import raw,Shards,Chain,put','from common import raw,Chain,put\nfrom verified_shards import VerifiedShards'),
 ('def send(seq,off,part,done):','def send(seq,off,part,done,final=False):'),
 ('  view=memoryview(b)','  if final:log.close()  # Verified final chunk BEFORE emitting closed ACK.\n  view=memoryview(b)'),
 ("log=Shards(A,'frames')","log=VerifiedShards(A,'frames',tick)"),
 ("send(seq,0,['closed'],True);status=","send(seq,0,['closed'],True,final=True);status=")]
for a,b in changes:assert new.count(a)==1;new=new.replace(a,b)
put(R/'runtime/broker.py',new.encode());put(R/'baseline/broker.py',old.encode())
put(R/'baseline/common.py',(OLD/'runtime/common.py').read_bytes())
put(R/'baseline/MANIFEST.json',(OLD/'MANIFEST.json').read_bytes())
put(R/'baseline/FREEZE.json',(OLD/'FREEZE.json').read_bytes())
diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='BE_W16_v1/runtime/broker.py',tofile='PROSPECTIVE/runtime/broker.py'))
put(R/'broker.diff',diff.encode())
reverse=new
for a,b in reversed(changes):assert reverse.count(b)==1;reverse=reverse.replace(b,a)
assert reverse==old
for p in [R/'runtime/verified_shards.py',R/'runtime/broker.py',R/'smoke.py']:
 tree=ast.parse(p.read_text());assert tree
 if p.name!='broker.py':
  forbidden={'subprocess','threading','multiprocessing','socket','requests','urllib'}
  names={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}
  assert not names&forbidden
  assert all(not isinstance(n,ast.ImportFrom) or n.module in ('verified_shards',) for n in ast.walk(tree))
block=bytes(range(256))*256;h=hashlib.sha256()
for b in [block]*127+[block[:65535],b'Q',b'R',block]:h.update(b)
small=b'0123456789abcdefghijklmnopqrstuv';assert len(small)==32
fixtures=['POS_ROTATION','POS_SHORT_RETURN','NEG_RETURN_NONE','NEG_RETURN_ZERO','NEG_RETURN_NEGATIVE','NEG_RETURN_EXCESS','NEG_FLUSH','NEG_FSYNC','NEG_CLOSE','NEG_ROTATION_TRUNCATE','NEG_HASH','NEG_REPLACE','NEG_APPEND','NEG_RECEIPT','NEG_DEADLINE']
dump(R/'UNCHANGED_IDENTITIES.json',{'old_manifest_sha256':sha((OLD/'MANIFEST.json').read_bytes()),'all_original_members_unchanged':rows,'changed_existing_copy':['runtime/broker.py'],'added_runtime':['runtime/verified_shards.py'],'foreign_bytes_unchanged':True,'scientific_bytes_unchanged':True})
selection=[p for p in sorted(R.rglob('*')) if p.is_file()]
files=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in selection]
freeze={'version':'BE-W16-WRITER-REPAIR-v1','scope':'ONE OWN SMOKE ONLY; no broker imports or pilot',
 'files':files,'python':sys.executable,'python_version':list(sys.version_info[:3]),'python_sha256':sha(pathlib.Path(sys.executable).read_bytes()),
 'command':sys.executable+' -B -I -S '+str(R/'smoke.py'),'fixtures':fixtures,
 'positive_rotation_bytes':{'bytes':8454145,'sha256':h.hexdigest()},
 'positive_short_bytes':{'bytes':32,'sha256':sha(small)},
 'limits':{'AS':67108864,'CPU_s':10,'cooperative_s':30,'processes':1,'FSIZE':8388608,'NOFILE':64,'CORE':0,'disk_output':20971520},
 'criterion':'2 positives exact;13 expected negatives;no ACK on failure;no next shard after failed rotation;no fd leak;exit0;elapsed<30;no retry'}
dump(R/'SMOKE_FREEZE.json',freeze)
z=R.parent/'Dorabella_BE_W16_writer_repair_v1_frozen.zip'
with zipfile.ZipFile(z,'x',zipfile.ZIP_DEFLATED) as out:
 for p in selection+[R/'SMOKE_FREEZE.json']:out.write(p,str(p.relative_to(R)))
print(json.dumps({'FROZEN_ZIP':str(z),'ZIP_SHA256':sha(z.read_bytes()),'SMOKE_FREEZE_SHA256':sha((R/'SMOKE_FREEZE.json').read_bytes()),'command':freeze['command'],'diff':diff,'verified_original_members':len(rows)},sort_keys=True),flush=True)
