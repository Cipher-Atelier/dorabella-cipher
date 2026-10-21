"""Own saved-data verifier. Never imports model lookup, broker, Perl or scorer."""
import pathlib,json,hashlib,struct,sqlite3,time
from audit_io import records,Chain,raw
def verify(R,A,deadline):
 def tick():
  if time.monotonic()>=deadline:raise RuntimeError('INCOMPLETE_BUDGET_READBACK')
 cat=json.loads((R/'catalogue/catalogue.json').read_text());cf=(R/'catalogue/catalogue.bin').open('rb')
 inputs=json.loads((R/'model_inputs.json').read_text());ip=next(x['path'] for x in inputs if x['path'].endswith('.sqlite'))
 db=sqlite3.connect(pathlib.Path(ip).as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-2048');db.execute('PRAGMA mmap_size=0');db.set_progress_handler(lambda:(tick() or 0),10000)
 broker=json.loads((A/'broker_terminal.json').read_text());consumer=json.loads((A/'consumer_terminal.json').read_text())
 chain=Chain();tx=0;checked_lists=0;words=0;lm_lookups=0;seqs={'pat':0,'lm':0};closed={'pat':False,'lm':False}
 refs=iter(records(A,'pat_refs'));lms=iter(records(A,'lm_raw'));p=next(refs,None);l=next(lms,None)
 receipts=(json.loads(x) for x in (A/'consumer.jsonl').read_text().splitlines());cr=next(receipts,None)
 try:
  while p is not None or l is not None:
   tick();ch='pat' if p is not None and (l is None or p['ordinal']<l['ordinal']) else 'lm';x=p if ch=='pat' else l
   tx+=1;assert x['ordinal']==tx
   h=hashlib.sha256();frames=0;nb=0
   def add(d,b):
    nonlocal frames,nb
    chain.add(ch,d,b);h.update(struct.pack('>BI',d,len(b))+b);frames+=1;nb+=len(b)
   if ch=='pat':
    req=x['request'].encode('ascii');v=json.loads(req);s,op,arg=v;seqs[ch]+=1;assert s==seqs[ch] and req==raw(v) and not closed[ch];add(1,req)
    if op=='list':
     d=cat[x['catalogue_id']];assert d['id']==x['catalogue_id'] and d['pattern']==arg;checked_lists+=1
     if d['count']==0:add(2,raw([s,'value',None]))
     else:
      cf.seek(d['offset']);blob=cf.read(d['bytes']);assert len(blob)==d['bytes'] and hashlib.sha256(blob).hexdigest()==d['sha256'];pos=0;payload=0;add(2,raw([s,'begin',d['count']]))
      for off in range(0,d['count'],64):
       vs=[]
       for _ in range(min(64,d['count']-off)):
        n=blob[pos];pos+=1;w=blob[pos:pos+n];pos+=n;assert len(w)==n;vs.append(w.decode('ascii'));payload+=n
       add(2,raw([s,'chunk',off,vs]))
      assert pos==len(blob) and payload==d['payload'];add(2,raw([s,'end',d['count'],payload]))
    elif op=='word':
     words+=1;found=db.execute('SELECT 1 FROM words WHERE word=?',(arg.encode('ascii'),)).fetchone() is not None
     assert type(x['found']) is bool and x['found']==found;add(2,raw([s,'value',int(found)]))
    elif op=='meta':assert arg=='';add(2,raw([s,'value',{'maxlen':46}]))
    elif op=='close':assert arg=='';add(2,raw([s,'value','closed']));closed[ch]=True
    else:raise AssertionError('PAT_OP')
    p=next(refs,None)
   else:
    assert x['direction']==1;req=x['raw'].encode('ascii');v=json.loads(req);s,op,items=v;seqs[ch]+=1;assert s==seqs[ch] and not closed[ch];add(1,req);lm_lookups+=len(items);offset=0;done=False;l=next(lms,None)
    while l is not None and l['ordinal']==tx:
     assert l['direction']==2 and not done;b=l['raw'].encode('ascii');z=json.loads(b);assert z[0]==s and z[1]==offset and len(z[2])<=128;offset+=len(z[2]);done=z[3];add(2,b);l=next(lms,None)
    assert done is True and offset==len(items)
    if op=='close':assert not items;closed[ch]=True
   if not(ch=='pat' and op=='word'):
    assert cr is not None and cr['ordinal']==tx and cr['channel']==ch and cr['seq']==s
    assert (cr['frames'],cr['bytes'],cr['sha256'])==(frames,nb,h.hexdigest())
    assert cr['exact_pat_list']==(ch=='pat' and op=='list');cr=next(receipts,None)
  assert cr is None and all(closed.values()) and all(broker['closed'].values()) and consumer['closed']
  assert chain.result()==broker['chain']
  assert all(consumer[k]==v for k,v in chain.result().items()) and consumer['transactions']==tx==broker['transactions']
  assert lm_lookups==broker['lookups'] and words==broker['membership']
  ps=broker['pat'];ls=broker['lm'];assert ps['list_calls']==ps['list_hits']+ps['list_misses']==checked_lists
  assert ps['word_calls']==ps['word_hits']+ps['word_queries']==words
  assert ls['calls']==ls['hits']+ls['misses']==lm_lookups
  profile=[json.loads(x) for x in (A/'profile.jsonl').read_text().splitlines()]
  ini=[x['value'] for x in profile if x['type']=='initialization'];completed=[x['value'] for x in profile if x['type']=='completed_iteration'];final=[x['value'] for x in profile if x['type']=='native_final'];scores=[x['value'] for x in profile if x['type']=='scored'];fin=[x['value'] for x in profile if x['type']=='observer_complete']
  assert len(ini)==1 and [x['iteration'] for x in completed]==[1,2] and len(final)==1 and len(fin)==1
  assert fin[0]['scores']==len(scores)<=1024 and [x['ordinal'] for x in scores]==list(range(1,len(scores)+1))
  assert final[0]['key']==completed[-1]['key'] and final[0]['plaintext']==completed[-1]['plaintext']
  c=(R/'ciphertext.txt').read_text().strip();f=final[0];plain=f['plaintext'];alphabet=f['alphabet'];key=f['key'];pattern=ini[0]['pattern']
  assert len(c)==len(plain)==len(pattern)==87 and len(alphabet)==len(key)==len(set(key))==16
  dec=dict(zip(alphabet,key));assert ''.join(dec[x] for x in pattern)==plain
  glyph_to_letter={};letter_to_glyph={};positions=[]
  for i,(g,z) in enumerate(zip(c,plain),1):
   assert glyph_to_letter.setdefault(g,z)==z and letter_to_glyph.setdefault(z,g)==g;positions.append([i,g,z,letter_to_glyph[z]])
  assert ''.join(letter_to_glyph[x] for x in plain)==c
  # Truth enters only after foreign processes terminated and all search output fixed.
  truth=json.loads((R/'truth/truth.json').read_text());exact=plain==truth['plaintext87']
  return {'status':'CONTROL_RECOVERED' if exact else 'CONTROL_NOT_RECOVERED','scope':'one bounded technical pilot, not sensitivity','inverse87':True,'exact_recovery':exact,'matching_positions':sum(a==b for a,b in zip(plain,truth['plaintext87'])),'positions':positions,'native_final':f,'completed_iterations':completed,'scored_strings':len(scores),'distinct_scored_strings':len({x['text'] for x in scores}),'chain':chain.result(),'transactions':tx,'checked_list_fetches':checked_lists,'membership':words,'LM_lookups':lm_lookups,'elapsed_readback_complete':True}
 finally:cf.close();db.close()
