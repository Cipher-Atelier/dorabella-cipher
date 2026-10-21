"""Own bounded DATA-ONLY materialization. No solver imports, subprocess or network."""
import ast, datetime, hashlib, json, pathlib, re, resource, string, time, zipfile
ROOT=pathlib.Path('/workspace/scratch/f24f8fae4976')
OUT=ROOT/'BE_W16_v1_preparation'/'input_checkpoint'
SPEC=ROOT/'Dorabella_BE_W16_v1_specification_20261018.md'
SPEC_SHA='03c81d1cc4529a8859f38e07bdb60591635070681edf96ae3e81c8ff275427ce'
INVENTORIES=[
 'Dorabella_R6_A3_representability_v1_20261016/data/positive_source_prefixes.json',
 'Dorabella_R6_A3_representability_v1_20261016/data/regression_inputs_original.json',
 'Dorabella_R6_section7_implementation_review_20261016/original/inputs_v7.py',
 'Dorabella_R6_section7_implementation_review_20261016/original/results/v6/fraction/inputs.json',
 'Dorabella_R6_section7_implementation_review_20261016/original/round8/results/elgar/inputs.json',
 'CH2_v1_prepare/control_selection.json',
 'CH2_v1_prepare/preflight_output/private_control_truth.json',
 'Dorabella_CH3_v1_execution_20261017/frozen/controls.json',
 'Dorabella_CH3_v1_execution_20261017/attempt/private_control_truth.json',
 'CH3_tabu_dev_v1_20261017/private/control_truth.json',
 'CH3_SA_dev_v1_execution_20261017/private/control_truth.json',
 'TS_RECOVERED_SEARCH_v3/truth/truth.json',
]
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):
 b=(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();p.write_bytes(b);return sha(b)
def norm(s):return re.sub('[^A-Za-z]','',s).lower()
def strings(x,p='$'):
 if isinstance(x,str):yield p,x
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from strings(v,p+'['+str(i)+']')
 elif isinstance(x,dict):
  for k,v in x.items():yield from strings(v,p+'.'+k)
def pattern(s):return [s.index(c) for c in s]
def main():
 t=time.monotonic();start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(25,30))
 if OUT.exists():raise RuntimeError('REFUSED_EXISTING_INPUT_CHECKPOINT')
 OUT.mkdir();(OUT/'decoder').mkdir();(OUT/'evaluator').mkdir();(OUT/'evidence').mkdir()
 def tick():
  if time.monotonic()-t>30:raise RuntimeError('DATA_ONLY_DEADLINE')
 b=SPEC.read_bytes();assert sha(b)==SPEC_SHA; (OUT/'protocol.md').write_bytes(b)
 captures=[]
 for line in b.decode().splitlines():
  if re.match(r'^\| P[1-4] \| ',line):
   cells=line.split(' | ');captures.append({'id':cells[0][2:],'locator':cells[1],'capture':cells[2].removesuffix(' |')})
 assert [x['id'] for x in captures]==['P1','P2','P3','P4']
 # This plan is closed before normalization, generation and freshness comparisons.
 inv=[];total=0
 for name in INVENTORIES:
  p=ROOT/name;data=p.read_bytes();total+=len(data);assert total<=16*1024**2 and len(data)<=4*1024**2
  inv.append({'path':name,'bytes':len(data),'sha256':sha(data)});tick()
 plan={'version':'BE-W16-v1-input-data-only','protocol_sha256':SPEC_SHA,'inventories':inv,'limits':{'wall_seconds':30,'AS_bytes':268435456,'input_bytes':16777216},'executable':'prepare_inputs.py','no_solver_import_or_subprocess':True,'comparisons':'Exact 87 ASCII plaintext as substring of each normalized stored string; source literal constants via AST, never execution.'}
 dump(OUT/'evidence/PLAN.json',plan)
 alphabet=string.ascii_lowercase;truth=[];decoder=[];evidence=[];collisions=[]
 for i,row in enumerate(captures,1):
  text=norm(row['capture'])[:87]
  independent=''.join(chr(ord(c)+32) if 'A'<=c<='Z' else c for c in row['capture'] if 'A'<=c<='Z' or 'a'<=c<='z')[:87]
  assert text==independent and len(text)==87
  pi='P'+str(i);ni='N'+str(i)
  key=''.join(sorted(alphabet,key=lambda c:(sha(('BE-W16-v1|key|'+pi+'|'+c).encode('ascii')),c)))
  assert len(key)==26 and len(set(key))==26
  cipher=''.join(key[alphabet.index(c)] for c in text)
  order=sorted(range(1,88),key=lambda j:(sha(('BE-W16-v1|negative|'+ni+'|'+str(j)).encode('ascii')),j))
  neg=''.join(cipher[j-1] for j in order);negtruth=''.join(text[j-1] for j in order)
  assert sorted(order)==list(range(1,88)) and sorted(neg)==sorted(cipher)
  equivalent=pattern(cipher)==pattern(neg)
  # Independent equality-relation check, not imported Pattern.
  pair_equal=all((cipher[a]==cipher[z])==(neg[a]==neg[z]) for a in range(87) for z in range(87))
  assert pair_equal==equivalent
  if equivalent:raise RuntimeError('INVALID_CONTROL_DESIGN:'+ni)
  inverse=[];negative_inverse=[]
  for pos in range(87):
   decoded=alphabet[key.index(cipher[pos])];assert decoded==text[pos]
   assert key[ord(decoded)-97]==cipher[pos]
   inverse.append([pos+1,text[pos],cipher[pos],decoded])
   j=order[pos]-1;decoded_n=alphabet[key.index(neg[pos])]
   assert decoded_n==negtruth[pos] and neg[pos]==cipher[j]
   negative_inverse.append([pos+1,order[pos],negtruth[pos],neg[pos],decoded_n])
  for tag,ct in [(pi,cipher),(ni,neg)]:
   opaque=sha(('BE-W16-v1|opaque|'+tag).encode())[:24]
   decoder.append({'id':opaque,'ciphertext':ct})
   evidence.append({'case':tag,'opaque_id':opaque,'ciphertext_sha256':sha(ct.encode()),'length':len(ct),'alphabet_types':len(set(ct))})
  truth.append(dict(row,plaintext87=text,plaintext_sha256=sha(text.encode()),capture_sha256=sha(row['capture'].encode()),encryption_alphabet=key,ciphertext87=cipher,inverse87=inverse,negative={'id':ni,'positions_1based':order,'ciphertext87':neg,'generating_plaintext87':negtruth,'inverse87':negative_inverse,'same_equality_pattern':False},decoder_ids=[decoder[-2]['id'],decoder[-1]['id']]))
  tick()
 for item in inv:
  p=ROOT/item['path'];data=p.read_bytes();assert sha(data)==item['sha256']
  if p.suffix=='.json':values=list(strings(json.loads(data)))
  else:values=[('AST:'+str(n.lineno),n.value) for n in ast.walk(ast.parse(data.decode())) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
  examined=0
  for location,value in values:
   if len(value)<87:continue
   normalized=norm(value);examined+=1
   for row in truth:
    if row['plaintext87'] in normalized:collisions.append({'new_case':row['id'],'inventory':item['path'],'location':location})
   tick()
  item['strings_examined']=examined
 if len({row['plaintext87'] for row in truth})!=4:raise RuntimeError('NEW_TEXT_DUPLICATE')
 status='PASS_INPUT_DATA_ONLY' if not collisions else 'BLOCKED_REUSED_CONTROL'
 dump(OUT/'decoder/inputs.json',{'version':'BE-W16-v1','cases':decoder})
 dump(OUT/'evaluator/truth.json',{'version':'BE-W16-v1','protocol_sha256':SPEC_SHA,'truth_not_decoder_input':True,'cases':truth})
 dump(OUT/'evaluator/source_capture.json',{'protocol_sha256':SPEC_SHA,'capture_kind':'Exact saved protocol text, not downloaded HTML bytes; source locators retained, no live substitutions','captures':captures})
 result={'status':status,'started_utc':start,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed':time.monotonic()-t,'maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'inventories':inv,'collisions':collisions,'cases':evidence,'positive_inverses':4,'negative_generation_inverses':4,'positions_per_case':87,'negative_inverse_is_not_recovery':True,'freshness_scope':'Compared exactly the 12 preserved inventories listed; not training-corpus disjointness, not global historical absence. No model/table/score read.'}
 dump(OUT/'evidence/result.json',result)
 files=[]
 for p in sorted(OUT.rglob('*')):
  if p.is_file():files.append({'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
 dump(OUT/'INPUT_MANIFEST.json',{'files':files,'code_sha256':sha(pathlib.Path(__file__).read_bytes())})
 print('INPUT_DATA_ONLY_RESULT '+json.dumps(result,sort_keys=True),flush=True)
 print('INPUT_MANIFEST_COMPUTED_SHA256 '+sha((OUT/'INPUT_MANIFEST.json').read_bytes()),flush=True)
 return 0 if status=='PASS_INPUT_DATA_ONLY' else 2
if __name__=='__main__':raise SystemExit(main())
