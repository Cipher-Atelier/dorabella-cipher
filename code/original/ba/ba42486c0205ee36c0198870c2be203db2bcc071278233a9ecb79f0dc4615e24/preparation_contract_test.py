"""ONLY own byte/AST checks; no broker, Perl, score, original modules or real LM reads."""
from pathlib import Path
import sys,json,hashlib,ast,time,resource,struct
B=Path(__file__).resolve().parent;sys.path.insert(0,str(B));sys.dont_write_bytecode=True
resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2));START=time.monotonic()
from disk_contract import DiskLM
from wire import request,packet,encode,decode
OUT=B/'PREPARATION_TEST_RESULT.json'
if OUT.exists():raise SystemExit('REFUSE_PREPARATION_REPEAT')
f=json.loads((B/'PREPARATION_TEST_FREEZE.json').read_text())
for n,h in f['hashes'].items():assert hashlib.sha256((B/n).read_bytes()).hexdigest()==h
def tick():
 if time.monotonic()-START>=5:raise RuntimeError('PREPARATION_TIMEOUT')
for p in B.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
ds=json.loads((B/'datasets.json').read_text());lookups=rows=0;d=None
for name in ['base','edge']:
 entries=[];references={};order=[]
 for e in ds[name]:
  e=dict(e,path=str(B/e['path']),index_path=str(B/e['index_path']));entries.append(e)
  raw=Path(e['path']).read_bytes();ix=Path(e['index_path']).read_bytes();off=0;ref={}
  for j,line in enumerate(raw.splitlines(keepends=True),1):
   fs=line[:-1].split(b'\t');key=tuple(fs[:-1]);val=fs[-1]
   assert int.from_bytes(ix[(j-1)*8:j*8],'little')==off;off+=len(line)
   ref[key]={'found':True,'value_hex':val.hex(),'last_row_1based':j};order.append((e['id'],key));rows+=1
  assert ix[-8:]==off.to_bytes(8,'little') and len(ix)==8*(e['rows']+1)
  references[e['id']]=ref
 d=DiskLM(entries,tick,3)
 try:
  for t,k in order:
   got=d.lookup(t,k);assert got==references[t][k];lookups+=1
   if name=='edge' and t==1 and k==(b'h',):assert got['value_hex']==b'0.25'.hex()
  for e in entries:
   got=d.lookup(e['id'],(b'~NO_SUCH_KEY~',)*e['order']);assert got=={'found':False,'value_hex':None,'last_row_1based':None};lookups+=1
 finally:d.close()
valid=[1,'edge',[[1,['30']],[2,['61','62']],[3,['61','62','63']]]]
assert request(encode(valid),1,['edge'])==('edge',[(1,(b'0',)),(2,(b'a',b'b')),(3,(b'a',b'b',b'c'))])
neg=[b'{}\n',b'x'*65537,encode([2,'edge',[]]),encode([True,'edge',[]]),encode([1,'other',[]]),encode([1,'edge',[[0,['61']]]]),encode([1,'edge',[[2,['61']]]]),encode([1,'edge',[[1,['6']]]]),encode([1,'edge',[[1,['ff']]]]),encode([1,'edge',[[1,['61']]]*777]),b'[1,"edge",[]]']
for raw in neg:
 try:request(raw,1,['edge'])
 except (ValueError,TypeError):pass
 else:raise AssertionError('NEGATIVE_REQUEST_ACCEPTED')
values=[[True,'31'*96,10000000]]*128
wire=packet(1,0,values,True);assert decode(wire)==[1,0,values,True] and len(wire)<32768
try:packet(1,0,[[True,0.5,1]],True)
except ValueError:pass
else:raise AssertionError('NUMERIC_COERCION_ACCEPTED')
assert rows==84 and lookups==96;tick()
out={'status':'PASS_OWN_PREPARATION_CONTRACT_ONLY','fixture_rows':rows,'lookup_intents':lookups,'negative_requests':len(neg),'negative_numeric_value':1,'max_synthetic_packet_bytes':len(wire),'python_AST_parsed':len(list(B.glob('*.py'))),'Perl_or_glue_or_broker_executed':False,'real_tables_read':False,'elapsed':time.monotonic()-START,'peak_rss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
OUT.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
