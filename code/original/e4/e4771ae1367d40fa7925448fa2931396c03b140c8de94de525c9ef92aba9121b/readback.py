"""Own DATA-ONLY verifier. No Perl imports, scores, key search or solver functions."""
import hashlib,json,pathlib,sqlite3,struct,time,math
from common import Chain
def events(A):
 for p in sorted(A.glob('events.*.jsonl')):
  with p.open('rb') as f:
   for b in f:
    if not b.endswith(b'\n'):raise ValueError('INCOMPLETE_EVENT_RECORD')
    yield json.loads(b)
def frames(A):
 buf=b''
 for p in sorted(A.glob('frames.*.bin')):
  with p.open('rb') as f:
   for b in iter(lambda:f.read(65536),b''):
    buf+=b
    while len(buf)>=5:
     d,n=struct.unpack('>BI',buf[:5])
     if d not in (1,2) or not 0<n<=65536:raise ValueError('FRAME_HEADER')
     if len(buf)<5+n:break
     yield d,buf[5:5+n];buf=buf[5+n:]
 if buf:raise ValueError('INCOMPLETE_RAW_FRAME')
def reference_prefix(db,source,pattern,tick):
 out=[];refs=[]
 for seq,off,n in db.execute('SELECT seq,offset,raw_bytes FROM segments WHERE pattern=? ORDER BY seq',(pattern.encode(),)):
  tick();source.seek(off);b=source.read(n)
  if len(b)!=n or n>118052:raise ValueError('REF_PREFIX_ROW')
  fields=[x for x in b.rstrip(b' \t\r\n\v\f').replace(b' ',b'').split(b'\t') if x]
  values=fields[2:];take=min(50-len(out),len(values));out+=values[:take];refs.append([seq,off,n,take])
  if len(out)==50:break
 L=len(out);return {'length':L,'picks':[out[((2*r+1)*L)//16].decode('ascii') for r in range(8)] if L else [],'segments':refs}
def reference_lm(entry,key,handles,tick):
 # Separate implementation: bisect raw key rows with rightmost-equal semantics.
 if entry['id'] not in handles:handles[entry['id']]=(open(entry['path'],'rb'),open(entry['index_path'],'rb'))
 data,idx=handles[entry['id']]
 def row(i):
  tick();idx.seek(i*8);b=idx.read(16)
  if len(b)!=16:raise ValueError('REF_LM_INDEX')
  x,y=struct.unpack('<QQ',b)
  if not 0<y-x<=512 or y>entry['bytes']:raise ValueError('REF_LM_RANGE')
  data.seek(x);b=data.read(y-x);fields=[z for z in b.removesuffix(b'\n').split(b'\t') if z]
  if len(fields)!=entry['order']+1:raise ValueError('REF_LM_FIELDS')
  return tuple(fields[:-1]),fields[-1]
 lo=0;hi=entry['rows']
 while lo<hi:
  mid=(lo+hi)//2;k,_=row(mid)
  if key<k:hi=mid
  else:lo=mid+1
 if not lo:return [False,None,None]
 k,v=row(lo-1);return [True,v.hex(),lo] if k==key else [False,None,None]
def verify(R,A,dataset,mode,deadline,input_row=None):
 def tick():
  if time.monotonic()>=deadline:raise RuntimeError('INCOMPLETE_BUDGET_READBACK')
 tick();segments=[];ends={}
 for e in events(A):
  tick()
  if e['kind']=='segment_begin':segments.append(e['value'])
  if e['kind']=='segment_end':ends[e['value']['id']]=e['value']
 if len(segments)>129:raise ValueError('SEGMENT_CAP')
 nonempty=[s for s in segments if s['text']];seg_cursor=0;word_cursor=0
 ds=json.loads((R/'datasets_all.json').read_text())[dataset];db=sqlite3.connect(pathlib.Path(ds['index']).resolve().as_uri()+'?mode=ro',uri=True,timeout=0);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-2048');db.execute('PRAGMA mmap_size=0')
 source=open(ds['source'],'rb');handles={};lm={x['id']:x for x in ds['lm']};seq=0;pending=None;received=[];chain=Chain();prefixes={};lm_lookups=0;physical_words=0;closed=False;counts={'prefix':0,'words':0,'lm':0,'close':0}
 try:
  for d,b in frames(A):
   tick();chain.add(d,b)
   if not b.endswith(b'\n'):raise ValueError('FRAME_EOL')
   x=json.loads(b)
   if d==1:
    if pending is not None or closed:raise ValueError('PIPELINING_AFTER_CLOSE')
    seq+=1
    if len(x)!=3 or x[0]!=seq:raise ValueError('REQUEST_SEQ')
    pending=x;received=[]
   else:
    if pending is None or len(x)!=4 or x[0]!=seq or x[1]!=len(received) or type(x[3]) is not bool or len(x[2])>128:raise ValueError('RESPONSE_SEQ')
    received.extend(x[2])
    if not x[3]:continue
    _,op,arg=pending
    if op not in counts:raise ValueError('OP_ACCOUNTING')
    counts[op]+=1
    if op=='prefix':
     expected=reference_prefix(db,source,arg,tick)
     if received!=[expected] or arg in prefixes:raise ValueError('PREFIX_EXACT_REFERENCE')
     prefixes[arg]=expected
    elif op=='words':
     keys=[bytes.fromhex(h) for h in arg];expected=[bool(db.execute('SELECT 1 FROM words WHERE word=?',(k,)).fetchone()) for k in keys]
     if received!=expected or any(type(x) is not bool for x in received):raise ValueError('MEMBERSHIP_REFERENCE')
     if seg_cursor>=len(nonempty):raise ValueError('EXTRA_MEMBERSHIP_BATCH')
     sg=nonempty[seg_cursor];text=sg['text'];ordered=[text[s:s+l].encode() for s in range(len(text)) for l in range(1,len(text)-s+1)];presence=bytes.fromhex(sg['presence_hex'])
     want=ordered[word_cursor:word_cursor+128]
     if keys!=want or received!=[bool(v) for v in presence[word_cursor:word_cursor+len(want)]]:raise ValueError('PREFETCH_EVENT_ORDER')
     word_cursor+=len(keys);physical_words+=len(keys)
     if word_cursor==len(ordered):seg_cursor+=1;word_cursor=0
    elif op=='lm':
     expected=[reference_lm(lm[table],tuple(bytes.fromhex(k) for k in key),handles,tick) for table,key in arg];lm_lookups+=len(arg)
     if received!=expected:raise ValueError('LM_EXACT_RAW_REFERENCE')
    elif op=='close':
     if received!=['closed']:raise ValueError('CLOSE_REFERENCE')
     closed=True
    else:raise ValueError('UNKNOWN_OP')
    pending=None
  if pending or not closed or word_cursor or seg_cursor!=len(nonempty):raise ValueError('INCOMPLETE_TRANSPORT')
 finally:
  source.close();db.close()
  for a,b in handles.values():a.close();b.close()
 broker=json.loads((A/'broker_terminal.json').read_text());consumer=json.loads((A/'consumer_terminal.json').read_text())
 if broker['status']!='BROKER_COMPLETE' or not consumer['closed'] or broker['chain']!=chain.result() or consumer['chain']!=chain.result() or consumer['transactions']!=seq:raise ValueError('TERMINAL_CHAIN_MISMATCH')
 if broker['counts']['lm_lookups']!=lm_lookups or broker['physical_words']!=physical_words:raise ValueError('TERMINAL_COUNTS')
 if any(broker['counts'][k]!=v for k,v in counts.items()) or counts['prefix']>3870 or counts['words']>3870 or counts['lm']>258 or counts['close']!=1 or lm_lookups>100104 or physical_words>493812:raise ValueError('REQUEST_CAPS')
 logical=0
 for s in segments:
  tick();text=s['text'];ordered=[text[i:i+l] for i in range(len(text)) for l in range(1,len(text)-i+1)];pv=bytes.fromhex(s['presence_hex']);ids={}
  if len(pv)!=len(ordered) or any(v not in (0,1) for v in pv):raise ValueError('PRESENCE_BYTES')
  for i,k in enumerate(ordered):ids.setdefault(k,i)
  b=(A/s['member_file']).read_bytes()
  if len(b)%2 or len(b)>202620:raise ValueError('LOGICAL_TRACE_LENGTH')
  trace=[x[0] for x in struct.iter_unpack('<H',b)];cursor=0
  def fetch(k):
   nonlocal cursor
   if cursor%1024==0:tick()
   if k not in ids or cursor>=len(trace) or trace[cursor]!=ids[k]:raise ValueError('LOGICAL_ORDER_REFERENCE')
   cursor+=1;return bool(pv[ids[k]])
  # Own exact trace validator: no language scores, proposals or foreign function calls.
  def check(t):
   if not t or t=='0':return t
   if fetch(t) or not t.strip():return t
   for length in range(s['maxlen'],0,-1):
    for offset in range(len(t)-length+1):
     w=t[offset:offset+length]
     if fetch(w):
      import re
      if offset==0:return re.sub(r'\s+',' ',w+' '+check(t[length:]))
      if offset+length==len(t):return re.sub(r'\s+',' ',check(t[:offset])+' '+w)
      return re.sub(r'\s+',' ',check(t[:offset])+' '+w+' '+check(t[offset+length:]))
   return t
  result=check(text);end=ends.get(s['id'])
  if cursor!=len(trace) or end is None or end['segmented']!=result or s['logical_before']!=logical or end['logical_count']!=cursor:raise ValueError('SEGMENT_REFERENCE')
  logical+=cursor
  if end['logical_after']!=logical:raise ValueError('LOGICAL_ACCOUNTING')
 if consumer['logical_membership']!=logical or logical>13068990:raise ValueError('LOGICAL_CAP')
 if consumer['segments']!=len(segments):raise ValueError('SEGMENT_TERMINAL')
 result={'status':'PASS_FINITE_INTEGRATION' if mode=='fixture' else 'CASE_COMPLETE_CANDIDATE','chain':chain.result(),'transactions':seq,'lm_lookups':lm_lookups,'physical_words':physical_words,'logical_membership':logical,'segments':len(segments)}
 if mode=='search':
  result.update(check_search(A,input_row,prefixes,tick))
  if consumer['scores']!=result['scores']:raise ValueError('SCORE_TERMINAL')
 else:
  done=[e for e in events(A) if e['kind']=='fixture_complete']
  if len(done)!=1 or done[0]['value']['dataset']!=dataset:raise ValueError('FIXTURE_COMPLETION')
  cfg=json.loads((R/'fixtures'/dataset/'cases.json').read_text());probes=[e['value'] for e in events(A) if e['kind']=='fixture_score']
  if [x['text'] for x in probes]!=cfg['score_probes']:raise ValueError('FIXTURE_PROBES')
  for i,p in enumerate(probes):
   err=bool(p['original_error'])
   if err!=bool(p['adapted_error']) or (not err and p['original_bits']!=p['adapted_bits']):raise ValueError('FIXTURE_BITS')
   if dataset=='edge' and err!=(i in cfg['expected_error_indices']):raise ValueError('FIXTURE_EXPECTED_ERROR')
  if dataset=='edge':
   raws=[e['value'] for e in events(A) if e['kind']=='fixture_raw']
   if raws!=[{'key':k,'raw':v,'truth':t} for k,v,t in zip(cfg['raw_keys'],cfg['expected_raw'],cfg['expected_truth'])]:raise ValueError('FIXTURE_RAW_EVIDENCE')
   unknown=[e['value'] for e in events(A) if e['kind']=='fixture_unknown']
   if unknown!=[{'input':cfg['unknown_input'],'result':cfg['expected_unknown']}]:raise ValueError('FIXTURE_UNKNOWN_EVIDENCE')
 return result

def number(bits):
 if len(bits)!=16:raise ValueError('SCORE_BITS')
 v=struct.unpack('<d',bytes.fromhex(bits))[0]
 if not math.isfinite(v):raise ValueError('NONFINITE_SCORE')
 return v
def canonical(text):
 d={}
 for c in text:
  if c not in d:d[c]=chr(97+len(d))
 return ''.join(d[c] for c in text)
def verify_proposal(alphabet,current,cw,match,claimed):
 # Independent mapping witness for the unchanged sequence of transpositions/replacements.
 mapping=dict(zip(alphabet,current));owners={v:k for k,v in mapping.items()}
 for symbol,letter in zip(cw,match):
  if symbol.isspace() or letter.isspace():continue
  old=mapping[symbol]
  if old==letter:continue
  other=owners.get(letter)
  if other is not None:mapping[other]=old;owners[old]=other
  else:del owners[old]
  mapping[symbol]=letter;owners[letter]=symbol
 if len(cw)!=len(match) or ''.join(mapping[c] for c in alphabet)!=claimed:raise ValueError('ASSUME_WITNESS')
def check_search(A,input_row,prefixes,tick):
 scored={};by_index=[];r=-1;window_index=0;bins={};selected=[];children=[];current=None;init=None;complete=None;completed=0
 for e in events(A):
  tick();k=e['kind'];v=e['value']
  if k=='initialization':
   if init is not None or v['ciphertext']!=input_row['ciphertext'] or v['id']!=input_row['id']:raise ValueError('INITIAL_INPUT')
   init=v;current=v['key'];p=v['pattern'];mapping={};next_letter=97
   for c in input_row['ciphertext']:
    if c not in mapping:mapping[c]=chr(next_letter);next_letter+=1
   if ''.join(mapping[c] for c in input_row['ciphertext'])!=p:raise ValueError('CANONICAL_MAP')
   if len(set(v['alphabet']))!=len(v['alphabet']) or set(v['alphabet'])!=set(p):raise ValueError('INITIAL_ALPHABET')
   f=[p.count(c) for c in v['alphabet']]
   if f!=sorted(f,reverse=True) or current!='etaoinsrhldcpumfgywbvkxjzq'[:len(f)]:raise ValueError('INITIAL_FREQUENCY')
  elif k=='expansion_begin':
   if v['round']!=completed or v['key']!=current:raise ValueError('STATE_BEGIN')
   r=v['round'];window_index=0;bins={};selected=[];children=[]
  elif k=='window':
   if r<0 or (v['round'],v['start'],v['length'])!=(r,window_index//45,2+window_index%45):raise ValueError('WINDOW_ORDER')
   window_index+=1
   cell=(4*v['start']//86)*4+sum(v['length']>q for q in [4,8,16])
   if v['cell']!=cell or v['pattern'] not in prefixes:raise ValueError('WINDOW_METADATA')
   cw=init['pattern'][v['start']:v['start']+v['length']]
   if v['pattern']!=canonical(cw):raise ValueError('WINDOW_PATTERN')
   L=prefixes[v['pattern']]['length']
   if not L:
    if v['status']!='empty':raise ValueError('EMPTY_STATUS')
    continue
   if v['j']!=(2*r+1)*L//16:raise ValueError('QUANTILE')
   verify_proposal(init['alphabet'],current,cw,prefixes[v['pattern']]['picks'][r],v['key'])
   key=v['key'];status='identity' if key==current else 'scored' if key in scored else 'eligible'
   if v['status']!=status:raise ValueError('PROPOSAL_STATUS')
   if status=='eligible':
    h=hashlib.sha256(f"BE-W16-v1|window|{r}|{v['start']}|{v['length']}|{v['j']}".encode()).hexdigest()
    if v['priority']!=h:raise ValueError('PRIORITY')
    order=(h,v['start'],v['length'],v['j'])
    if cell not in bins or order<bins[cell][0]:bins[cell]=(order,key)
  elif k=='selected':
   if window_index!=3870 or v['round']!=r:raise ValueError('SELECTION_BEFORE_FULL_SCAN')
   want=[];seen=set()
   for c,(_,key) in sorted(bins.items()):
    if key not in seen:want.append((c,key));seen.add(key)
   n=len(selected)
   if n>=len(want) or (v['cell'],v['key'])!=want[n]:raise ValueError('SELECTED_ORDER')
   selected.append(want[n])
  elif k=='score':
   key=v['key'];text=v['plaintext'];enc=v['encryption_alphabet'];s=number(v['score_bits'])
   if v['index']!=len(by_index) or key in scored or len(text)!=87 or len(set(enc))!=26 or set(enc)!=set('abcdefghijklmnopqrstuvwxyz'):raise ValueError('SCORE_IDENTITY')
   expected=''.join(enc[ord(c)-97] for c in text)
   if expected!=input_row['ciphertext']:raise ValueError('INVERSE87')
   inverse=[[i+1,text[i],expected[i],text[i]] for i in range(87)]
   if v['inverse']!=inverse or v['segmented'].replace(' ','')!=text:raise ValueError('POSITIONAL_INVERSE')
   if ''.join(dict(zip(init['alphabet'],key))[c] for c in init['pattern'])!=text:raise ValueError('KEY_ORIENTATION')
   if r<0:
    if key!=current or by_index:raise ValueError('ROOT_SCORE')
   else:
    if len(children)>=len(selected) or key!=selected[len(children)][1]:raise ValueError('SCORED_SELECTION')
    children.append(v)
   scored[key]=v;by_index.append(v)
  elif k=='expansion_complete':
   wantkeys=[]
   for cell,(_,key) in sorted(bins.items()):
    if key not in wantkeys:wantkeys.append(key)
   if v['round']!=r or v['previous']!=current or window_index!=3870 or [x['key'] for x in children]!=wantkeys or v['scored_children']!=len(children):raise ValueError('EXPANSION_ACCOUNTING')
   if children:current=min(children,key=lambda x:(-number(x['score_bits']),x['plaintext'],x['key']))['key']
   if v['next']!=current:raise ValueError('STATE_TRANSITION')
   completed+=1
  elif k=='search_complete':complete=v
 if completed!=8 or complete is None or len(by_index)>129:raise ValueError('INCOMPLETE_SEARCH')
 best=max(number(x['score_bits']) for x in by_index);co={x['plaintext']:x for x in by_index if number(x['score_bits'])==best};ordered=sorted(co.values(),key=lambda x:(x['plaintext'],x['key']))
 if complete['scores']!=len(by_index) or complete['expansions']!=8 or complete['best_indices']!=[x['index'] for x in ordered] or complete['best_plaintexts']!=[x['plaintext'] for x in ordered] or number(complete['best_score_bits'])!=best:raise ValueError('BEST_ACCOUNTING')
 return {'scores':len(by_index),'expansions':8,'best_plaintexts':[x['plaintext'] for x in ordered],'best_score_bits':ordered[0]['score_bits'],'unique_best':len(ordered)==1,'inverse_all_scores':True}

def evaluate_all(R,case_results):
 # Called only after every scheduled search has terminated or been recorded unstarted.
 truth=json.loads((R/'evaluator/truth.json').read_text());positives=[];pairs=[]
 for t in truth['cases']:
  p=case_results.get(t['decoder_ids'][0],{});n=case_results.get(t['decoder_ids'][1],{})
  good=p.get('status')=='CASE_COMPLETE_CANDIDATE';ngood=n.get('status')=='CASE_COMPLETE_CANDIDATE'
  positives.append({'id':t['id'],'exact_unique_recovery':good and p.get('best_plaintexts')==[t['plaintext87']],'truth_in_tied_best':good and t['plaintext87'] in p.get('best_plaintexts',[]) and not p.get('unique_best',False)})
  pairs.append({'id':t['id'],'positive_strictly_above_negative':good and ngood and number(p['best_score_bits'])>number(n['best_score_bits'])})
 completed=sum(x.get('status')=='CASE_COMPLETE_CANDIDATE' for x in case_results.values());recoveries=sum(x['exact_unique_recovery'] for x in positives);ordered=sum(x['positive_strictly_above_negative'] for x in pairs)
 return {'decision':'GO_CANDIDATE_PENDING_DELIVERY' if completed==8 and recoveries>=3 and ordered==4 else 'NO_GO','completed':completed,'exact_unique_recovery':recoveries,'paired_strict_scores':ordered,'positives':positives,'pairs':pairs,'no_p_value':True,'no_target_authorization':True}
