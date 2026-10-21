"""Own preparation only: finite ciphertext/metadata accounting. No scorer/search imports."""
import time
T=time.monotonic()
import resource
resource.setrlimit(resource.RLIMIT_AS,(134217728,134217728))
resource.setrlimit(resource.RLIMIT_CPU,(25,28))
from pathlib import Path
import json,hashlib,sqlite3,collections
B=Path(__file__).resolve().parent
def need(ok,msg):
 if not ok:raise RuntimeError(msg)
 if time.monotonic()-T>30:raise RuntimeError('PREP_WALL_BOUND')
def H(d):return hashlib.sha256(d).hexdigest()
def save(n,v):
 data=(json.dumps(v,indent=2,ensure_ascii=False)+'\n').encode()
 need(len(data)<2000000,'OUTPUT_BOUND')
 with (B/n).open('xb') as f:f.write(data)
def fullhash(e):
 p=Path(e['path']);need(p.stat().st_size==e['bytes'],'SIZE')
 before=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  while True:
   chunk=f.read(1048576)
   if not chunk:break
   h.update(chunk);need(True,'TIME')
 after=p.stat();need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'INPUT_CHANGED')
 need(h.hexdigest()==e['sha256'],'HASH')
 return {'path':str(p),'bytes':before.st_size,'sha256':h.hexdigest(),'dev':before.st_dev,'ino':before.st_ino}
try:
 need(not (B/'BOUND_RESULT.json').exists() and not (B/'truth.json').exists(),'EXISTING_PREP')
 f=json.loads((B/'SELECTION_FREEZE.json').read_text())
 plain=''.join(c.lower() for c in f['source_paragraph'] if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')[:87]
 need(len(plain)==87,'LENGTH')
 alpha='abcdefghijklmnopqrstuvwxyz'
 key=''.join(sorted(alpha,key=lambda c:(H(('TS-INTEGRATION87-v1|20261018|permutation|'+c).encode()),c)))
 need(len(set(key))==26,'PERMUTATION')
 cipher=plain.translate(str.maketrans(alpha,key))
 positions=[]
 for i,(p,c) in enumerate(zip(plain,cipher),1):
  need(c==key[ord(p)-97] and alpha[key.index(c)]==p,'INVERSE')
  positions.append([i,p,c,alpha[key.index(c)]])
 # Inventory comparison uses only pre-existing control data, never evaluates them.
 oldpaths=['CH2_v1_prepare/preflight_output/preflight_report.json','Dorabella_CH3_v1_execution_20261017/frozen/controls.json','r6_fraction_audit/positive_source_prefixes.json','r6_fraction_audit/read/dorabella_lab/results/v6/fraction/inputs.json']
 old=[];matches=[]
 for name in oldpaths:
  p=B.parent/name;need(p.stat().st_size<2000000,'PRIOR_BOUND');raw=p.read_bytes();old.append({'path':name,'sha256':H(raw)})
  obj=json.loads(raw)
  stack=[obj]
  while stack:
   item=stack.pop()
   if isinstance(item,dict):stack.extend(item.values())
   elif isinstance(item,list):stack.extend(item)
   elif isinstance(item,str):
    s=''.join(c.lower() for c in item if c in alpha+alpha.upper())
    if plain in s:matches.append(name)
 need(not matches,'PREVIOUS_CONTROL_MATCH')
 save('truth.json',{'source':f['source'],'plaintext87':plain,'plaintext_sha256':H(plain.encode()),'alphabet':alpha,'cipher_alphabet':key,'ciphertext_sha256':H(cipher.encode()),'positions_inverse':positions,'checked_prior':old,'matches':matches,'scope':'New selected control, not validated or proven training-disjoint'})
 save('decoder_input.json',{'case_id':'LINCOLN_BEDELL_18601019_P2_87','ciphertext':cipher,'ciphertext_sha256':H(cipher.encode()),'normalization':'already lowercase 87 letters; no further transformation'})
 def pat(s):
  order=list(dict.fromkeys(s))
  x=''.join(alpha[order.index(c)] for c in s)
  ref={};y=''
  for c in s:
   if c not in ref:ref[c]=chr(97+len(ref))
   y+=ref[c]
  need(x==y,'PATTERN_REFERENCE')
  return x
 identities=[fullhash(f['index']),fullhash(f['patlst'])]
 db=sqlite3.connect(Path(f['index']['path']).as_uri()+'?mode=ro',uri=True,timeout=0)
 db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-2048');db.execute('PRAGMA mmap_size=0')
 db.set_progress_handler(lambda:0 if time.monotonic()-T<30 else 1,1000)
 maxlen=int(db.execute("SELECT value FROM metadata WHERE key='maxlen'").fetchone()[0]);need(maxlen==46,'MAXLEN')
 windows=collections.Counter(pat(cipher[s:s+l]) for s in range(86) for l in range(2,47))
 need(sum(windows.values())==3870,'WINDOWS')
 records=[];HITS=0;S=0;LCOUNT=0;FRAME=0;BYTES=0
 for pattern,multiplicity in sorted(windows.items()):
  need(len(records)<3870,'QUERY_CAP')
  r=db.execute('SELECT COALESCE(SUM(count),0),COUNT(*),COALESCE(MAX(longest),0) FROM segments WHERE pattern=?',(pattern.encode(),)).fetchone()
  count,segs,longest=map(int,r);need(0<=count<=63911 and 0<=segs<=7548932 and 0<=longest<=46,'INDEX_DOMAIN')
  hit=segs>0;need(not hit or count>0,'NONEMPTY')
  if hit:
   HITS+=multiplicity;S+=multiplicity*min(50,count);LCOUNT+=multiplicity*count
   FRAME+=multiplicity*(2+(count+63)//64);BYTES+=multiplicity*3*count
  else:FRAME+=multiplicity
  records.append({'pattern':pattern,'windows':multiplicity,'candidate_count':count,'segments':segs,'longest':longest})
 db.close()
 W=3870
 # Separate unconditional full-loop costs from only upper bounds on key-dependent work.
 # 1st iteration: hit twice, miss once; 2nd: hit three times, miss once.
 pat_req_1=W+HITS;pat_req_2=W+2*HITS
 hit_frames=sum(r['windows']*(2+(r['candidate_count']+63)//64) for r in records if r['segments'])
 miss_windows=W-HITS
 full_frames=5*hit_frames+2*miss_windows
 string_octets_lower=15*LCOUNT # 5 deliveries * at least 3 JSON bytes/string
 # Bound one NoSpace recursion using monotonic upper cost increments.
 def local(n):return 1+sum(n-l+1 for l in range(1,min(n,46)+1))
 seg_bound=sum(local(n) for n in range(1,88))
 P=2*S
 bounds={'windows_each_iteration':W,'windows_with_lists':HITS,'distinct_patterns':len(records),'sum_min_50_counts_per_iteration':S,
 'attempted_Assume_upper_two_iterations':P,'distinct_score_calls_upper':P,
 'pat_list_requests_if_two_iterations_complete':pat_req_1+pat_req_2,
 'pat_list_response_frames_if_two_iterations_complete':full_frames,
 'candidate_occurrences_transferred_if_two_iterations_complete':5*LCOUNT,
 'pat_response_min_string_bytes_if_two_iterations_complete':string_octets_lower,
 'pat_first_iteration_min_string_bytes':6*LCOUNT,
 'pat_first_iteration_list_requests':pat_req_1,
 'LM_requests_upper_with_close':2*P+1,'LM_lookups_upper':776*P,'LM_response_frames_upper_with_close':8*P+1,
 'NoSpace_membership_upper_per_candidate':seg_bound,'NoSpace_membership_upper_total':P*seg_bound,
 'meaning':'Pat counts and minimum bytes conditional on completing full loops; score/segmentation bounds are upper bounds, not actual workload or necessary minima.'}
 out={'status':'PREPARATION_COUNTS_ONLY','selection_sha256':H((B/'SELECTION_FREEZE.json').read_bytes()),'source_identities':identities,'control_plaintext':plain,'ciphertext':cipher,'key':key,'distinct_cipher_types':len(set(cipher)),'inverse_positions':87,'bounds':bounds,'patterns':records,'elapsed':time.monotonic()-T,'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'foreign_execution':False,'model_values_read':False,'candidate_strings_read':False}
 save('BOUND_RESULT.json',out)
 print(json.dumps({k:v for k,v in out.items() if k!='patterns'},ensure_ascii=False))
except BaseException as e:
 out={'status':'STOP_PREPARATION','error':repr(e),'elapsed':time.monotonic()-T,'retry':False}
 with (B/'STOP.json').open('x') as f:json.dump(out,f)
 print(json.dumps(out));raise SystemExit(2)

