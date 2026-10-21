"""One own-stdlib adapter contract attempt. No Perl, solver, score or subprocess."""
from pathlib import Path
import sys, os, json, time, datetime, hashlib, resource, sqlite3, traceback

BASE = Path(__file__).resolve().parent
ATTEMPT = BASE / 'attempt'
START = DEADLINE = LAST = None
R = {'version':'TS-ADAPTER-CONTRACT-v1','status':'INCOMPLETE',
     'author_executions':0,'solver_calls':0,'score_calls':0,'target_inputs':0,'events':[]}

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def write(name, obj):
    p = ATTEMPT / name
    q = p.with_suffix(p.suffix + '.tmp')
    with q.open('w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(q, p)

def memory():
    return {'current':int(Path('/sys/fs/cgroup/memory.current').read_text()),
            'maximum':Path('/sys/fs/cgroup/memory.max').read_text().strip(),
            'events':Path('/sys/fs/cgroup/memory.events').read_text(),
            'proc':[x for x in Path('/proc/self/status').read_text().splitlines()
                    if x.startswith(('VmPeak:','VmSize:','VmHWM:','VmRSS:'))]}

def tick():
    global LAST
    now = time.monotonic()
    if now >= DEADLINE:
        raise RuntimeError('STOP_COOPERATIVE_DEADLINE')
    if LAST is None or now - LAST >= .5:
        LAST = now
        m = memory()
        with (ATTEMPT/'observations.jsonl').open('a') as f:
            f.write(json.dumps({'utc':utc(),'elapsed':now-START,'phase':R.get('phase'),'memory':m})+'\n')
        if m['current'] >= 15 * 1024**3 // 2:
            raise RuntimeError('STOP_SHARED_MEMORY')

def phase(name):
    R['phase'] = name
    event = {'phase':name,'utc':utc(),'elapsed':time.monotonic()-START}
    R['events'].append(event)
    print(json.dumps(event), flush=True)
    tick()

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        while True:
            data = f.read(1048576)
            if not data: break
            h.update(data); tick()
    return h.hexdigest()

def create_fixture(folder, fixture):
    folder.mkdir()
    source = folder/'fixture.patlst'
    source.write_bytes(''.join(fixture['raw_lines']).encode('ascii'))
    dbpath = folder/'fixture.sqlite'
    db = sqlite3.connect(dbpath)
    db.executescript('''CREATE TABLE segments(seq INTEGER PRIMARY KEY,original_order INTEGER,
      pattern BLOB,offset INTEGER,raw_bytes INTEGER,count INTEGER,longest INTEGER);
      CREATE INDEX by_pattern ON segments(pattern,seq);
      CREATE TABLE words(word BLOB PRIMARY KEY) WITHOUT ROWID;
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT) WITHOUT ROWID;''')
    offset = 0
    # Fixture-only encoder uses independent token parser; literal goldens anchor it.
    for seq, line in enumerate(fixture['raw_lines'], 1):
        raw = line.encode('ascii')
        order, pattern, values = fields_from_raw(raw)
        db.execute('INSERT INTO segments VALUES(?,?,?,?,?,?,?)',
                   (seq,order,pattern,offset,len(raw),len(values),max(map(len,values))))
        offset += len(raw)
    db.executemany('INSERT INTO words VALUES(?)', [(w.encode('ascii'),) for w in fixture['words']])
    db.execute("INSERT INTO metadata VALUES('maxlen',?)", (str(fixture['maxlen']),))
    db.commit(); db.close()
    return dbpath, source

def snapshot(adapter, f):
    return {'groups':{p: [v.decode('ascii') for v in adapter.candidates(p.encode())]
                      for p in f['groups']},
            'members':{w:adapter.is_word(w.encode()) for w in f['words']+['at','gogogo','!']},
            'maxlen':adapter.maxlen}

def run_fixtures(f):
    db, source = create_fixture(ATTEMPT/'fixture', f)
    a = CompactPatList(db, source, tick)
    expected = {'groups':f['groups'], 'members':{w: w in f['words'] for w in f['words']+['at','gogogo','!']},'maxlen':6}
    if snapshot(a,f) != expected: raise RuntimeError('FAIL_GOLDEN_API')
    segments = []
    wordset = set(w.encode() for w in f['words'])
    for text, golden in f['segmentation']:
        tr1, tr2 = [], []
        got = find_words_reference(text.encode(), a.is_word, a.maxlen, tick, tr1)
        ref = find_words_reference(text.encode(), wordset.__contains__, 6, tick, tr2)
        if got != golden.encode() or ref != got or tr1 != tr2:
            raise RuntimeError('FAIL_GOLDEN_SEGMENTATION')
        segments.append({'input':text,'expected':golden,'actual':got.decode(),'membership_trace':tr1})
    returned = a.candidates(b'ab'); returned.reverse(); returned.pop()
    if a.candidates(b'ab') != [x.encode() for x in f['groups']['ab']]:
        raise RuntimeError('FAIL_MUTATION_ISOLATION')
    if a.candidates(b'!') is not None or a.candidates(b'ab',2) is not None or a.candidates(b'ab',3) is not None:
        raise RuntimeError('FAIL_MISSING_ORDER')
    rejects = 0
    for op in [lambda:a.candidates('ab'),lambda:a.candidates(b'ab',0),
               lambda:a.candidates(b'x'*47),lambda:a.candidates(b'\xff'),
               lambda:a.is_word('to'),lambda:a.is_word(b'x'*88)]:
        try: op()
        except ValueError: rejects += 1
        else: raise RuntimeError('FAIL_NEGATIVE_DOMAIN')
    try: a.db.execute("UPDATE metadata SET value='1' WHERE key='maxlen'")
    except sqlite3.OperationalError: pass
    else: raise RuntimeError('FAIL_READ_ONLY')
    a.close()
    # Mutate only small independent fixture copies. Real store remains read-only.
    mutations = ["UPDATE segments SET count=count-1 WHERE seq=1",
                 "UPDATE segments SET offset=offset+1 WHERE seq=1",
                 "DELETE FROM segments WHERE seq=2",
                 "INSERT INTO words VALUES(x'6174')",
                 "DELETE FROM words WHERE word=x'746f'",
                 "UPDATE metadata SET value='5' WHERE key='maxlen'"]
    rejected=[]
    for i,sql in enumerate(mutations):
        bad=ATTEMPT/f'negative_{i}.sqlite'; bad.write_bytes(db.read_bytes())
        con=sqlite3.connect(bad); con.execute(sql); con.commit(); con.close()
        obj=CompactPatList(bad,source,tick)
        try:
            got=snapshot(obj,f)
            detected=(got != expected)
        except ValueError:
            detected=True
        finally: obj.close()
        if not detected: raise RuntimeError('FAIL_NEGATIVE_MUTATION')
        rejected.append({'mutation':sql,'detected':True})
    # Two byte-level mutations keep length/count: reorder and duplicate substitution.
    raw=source.read_bytes()
    for label,changed in [('reorder',raw.replace(b'to\ton\tto',b'on\tto\tto',1)),
                          ('duplicate_loss',raw.replace(b'to\ton\tto',b'to\ton\tat',1))]:
        wrong=ATTEMPT/(label+'.patlst');wrong.write_bytes(changed)
        obj=CompactPatList(db,wrong,tick)
        try: detected=snapshot(obj,f)!=expected
        finally:obj.close()
        if not detected:raise RuntimeError('FAIL_NEGATIVE_BYTES')
        rejected.append({'mutation':label,'detected':True})
    write('fixture_results.json',{'golden':expected,'segmentation':segments,
          'domain_rejections':rejects,'storage_mutations':rejected,
          'mutation_isolation':True,'read_only':True,'missing_orders':True})
    write('golden_oracle_expected.json',{k:f[k] for k in ('groups','words','maxlen','segmentation')})
    return {'golden_groups':5,'golden_segmentation':10,'negative_domain':rejects,
            'negative_storage':len(rejected),'passed':True}

def full_stream_reference(source, f):
    patterns={p.encode():[] for p in f['real_patterns']}
    words=set(); rows=bytecount=candidates=maximum=selected=0
    digest=hashlib.sha256(); seqs=[]; highest_included=False
    # A small exact subset for a FUTURE original Utils/NoSpace oracle:
    # all order-1 rows, all chosen-pattern rows, first row attaining known maxlen46.
    with Path(source).open('rb') as src, (ATTEMPT/'oracle_fixture.patlst').open('wb') as out:
        while True:
            raw=src.readline(118053)
            if not raw:break
            rows+=1;bytecount+=len(raw);digest.update(raw)
            if rows>7548932 or len(raw)>118052 or bytecount>340083717:
                raise RuntimeError('STOP_REFERENCE_BOUND')
            order,p,values=fields_from_raw(raw)
            candidates+=len(values)
            if candidates>10662322:raise RuntimeError('STOP_REFERENCE_CANDIDATES')
            longest=max(map(len,values));maximum=max(maximum,longest)
            if order==1:
                words.update(values)
                if len(words)>123619:raise RuntimeError('STOP_LEXICON_BOUND')
            if p in patterns:
                patterns[p].extend(values);selected+=len(values)
                if selected>7*63911 or len(patterns[p])>63911:
                    raise RuntimeError('STOP_SELECTED_BOUND')
            include=order==1 or p in patterns or (longest==46 and not highest_included)
            if include:
                out.write(raw);seqs.append(rows)
                if out.tell()>16*1024**2:raise RuntimeError('STOP_ORACLE_SUBSET_BOUND')
                if longest==46:highest_included=True
            if rows%2048==0:tick()
    if (rows,bytecount,candidates,len(words),maximum,digest.hexdigest()) != (
            7548932,340083717,10662322,123619,46,
            '2849bc03f85c59a422f1945960ce04a4b6e66cc02c61a6484de0283c30c724fd'):
        raise RuntimeError('FAIL_REFERENCE_ACCOUNTING')
    write('oracle_subset_provenance.json',{'selection':'all original-order1 OR frozen seven patterns OR first row reaching maxlen46',
          'source_seq_1based':seqs,'rows':len(seqs),'bytes':(ATTEMPT/'oracle_fixture.patlst').stat().st_size,
          'sha256':sha(ATTEMPT/'oracle_fixture.patlst')})
    return patterns, words, {'rows':rows,'bytes':bytecount,'candidate_occurrences':candidates,
                           'selected_candidates':selected,'words':len(words),'maxlen':maximum,
                           'source_sha256':digest.hexdigest()}

def real_tests(index,source,f,groups,words):
    a=CompactPatList(index,source,tick)
    if a.maxlen!=46:raise RuntimeError('FAIL_REAL_MAXLEN')
    receipts=[]
    def compare(p,label):
        got=a.candidates(p.encode())
        expected=groups[p.encode()] or None
        if got!=expected:raise RuntimeError('FAIL_REAL_LIST:'+p)
        encoded=None if got is None else [x.decode('ascii') for x in got]
        receipt={'phase':label,'pattern':p,'count':0 if got is None else len(got),
                 'list_sha256':hashlib.sha256(json.dumps(encoded,separators=(',',':')).encode()).hexdigest(),
                 'equal_full_reference':True}
        receipts.append(receipt)
        return got
    full={}
    for p in f['real_patterns']:
        got=compare(p,'cold')
        full[p]=None if got is None else [x.decode() for x in got]
    for p in f['cache_schedule']:compare(p,'fixed_cache_schedule')
    before=a.candidates(b'abcdefgh');before[0]=b'CHANGED';before.reverse()
    compare('abcdefgh','caller_mutation_isolation')
    probes={}
    for w in f['real_word_probes']:
        got=a.is_word(w.encode())
        if got!=(w.encode() in words):raise RuntimeError('FAIL_REAL_MEMBERSHIP')
        probes[w]=got
    seg=[]
    for text in f['real_segmentation']:
        tr1,tr2=[],[]
        result=find_words_reference(text.encode(),a.is_word,a.maxlen,tick,tr1)
        ref=find_words_reference(text.encode(),words.__contains__,46,tick,tr2)
        if result!=ref or tr1!=tr2:raise RuntimeError('FAIL_REAL_SEGMENTATION_REFERENCE')
        seg.append({'input':text,'output':result.decode(),'membership_trace':tr1,'exact_trace_equal':True})
    if a.candidates(b'ab',2) is not None or a.candidates(b'ab',3) is not None:
        raise RuntimeError('FAIL_REAL_ORDER')
    stats1=dict(a.stats);a.close()
    a=CompactPatList(index,source,tick)
    for p in f['real_patterns']:compare(p,'reopen')
    stats2=dict(a.stats);a.close()
    if not stats1['list_hits'] or not stats1['evictions']:
        raise RuntimeError('FAIL_CACHE_COVERAGE')
    write('real_lists.json',full)
    write('real_lookup_receipts.json',receipts)
    write('real_segmentation.json',seg)
    write('oracle_expected.json',{'groups':full,'words':sorted(x.decode() for x in words),
          'maxlen':46,'segmentation':[[v['input'],v['output']] for v in seg]})
    write('real_membership.json',probes)
    return {'patterns':len(full),'full_list_comparisons':len(receipts),
            'query_stats':stats1,'reopen_stats':stats2,'word_probes':len(probes),
            'segmentation_reference_cases':len(seg),'rebuilds':0,'all_equal':True,
            'counts':{k:0 if v is None else len(v) for k,v in full.items()}}

def main():
    global START,DEADLINE,CompactPatList,fields_from_raw,find_words_reference
    if ATTEMPT.exists():
        print('REFUSED_EXISTING_ATTEMPT');return 3
    ATTEMPT.mkdir();START=time.monotonic();DEADLINE=START+180
    write('T0.json',{'utc':utc(),'monotonic':START,'deadline':DEADLINE,'no_resume':True})
    R['start_utc']=utc()
    try:
        for key,pair in [('RLIMIT_AS',(256*1024**2,256*1024**2)),
                         ('RLIMIT_CPU',(170,180)),('RLIMIT_FSIZE',(32*1024**2,32*1024**2)),
                         ('RLIMIT_CORE',(0,0)),('RLIMIT_NOFILE',(64,64))]:
            resource.setrlimit(getattr(resource,key),pair)
        R['limits']={k:resource.getrlimit(getattr(resource,k)) for k in
                     ['RLIMIT_AS','RLIMIT_CPU','RLIMIT_FSIZE','RLIMIT_CORE','RLIMIT_NOFILE']}
        R['before']=memory()
        if R['before']['maximum']!='8589934592' or R['before']['current']>7*1024**3:
            raise RuntimeError('STOP_RESOURCE_GATE')
        freeze=json.loads((BASE/'FREEZE.json').read_text())
        if sys.version!=freeze['python_version'] or sqlite3.sqlite_version!=freeze['sqlite_version']:
            raise RuntimeError('STOP_RUNTIME_IDENTITY')
        phase('authenticate_frozen_inputs')
        for item in freeze['identities']:
            p=Path(item['path'])
            if p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
                raise RuntimeError('STOP_IDENTITY:'+p.name)
        R['identities_verified']=True
        sys.dont_write_bytecode=True
        sys.path.insert(0,str(BASE))
        from adapter import CompactPatList
        from reference import fields_from_raw,find_words_reference
        f=json.loads((BASE/'fixtures.json').read_text())
        phase('golden_and_negative_fixture_contracts')
        R['fixtures']=run_fixtures(f)
        phase('single_full_stream_selected_reference')
        groups,words,R['reference']=full_stream_reference(freeze['source'],f)
        phase('real_read_only_adapter_and_cache')
        R['adapter']=real_tests(freeze['index'],freeze['source'],f,groups,words)
        phase('seal_and_input_unchanged')
        if sha(freeze['index'])!=freeze['index_sha256'] or sha(freeze['source'])!=freeze['source_sha256']:
            raise RuntimeError('FAIL_INPUT_CHANGED')
        R['output_hashes']={p.name:sha(p) for p in sorted(ATTEMPT.iterdir())
                            if p.is_file() and p.name not in ('observations.jsonl','result.json')}
        R['status']='PASS_ADAPTER_CONTRACT_ONLY'
        R['not_proved']=['Perl execution equivalence','numerical LM equivalence',
                         'native Perl bridge','solver trajectory/ties','full-search RAM/time','87/87 control or target']
        exit_code=0
    except BaseException as e:
        R['status']='STOP';R['error']=repr(e);R['traceback']=traceback.format_exc();exit_code=2
    R['end_utc']=utc();R['elapsed_seconds']=time.monotonic()-START
    R['ru_maxrss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    R['after']=memory()
    if R['elapsed_seconds']>180 and exit_code==0:
        R['status']='STOP_LATE';exit_code=2
    write('result.json',R)
    print(json.dumps({'status':R['status'],'elapsed':R['elapsed_seconds'],'exit':exit_code,
                      'ru_maxrss_KiB':R['ru_maxrss_KiB'],'error':R.get('error')}),flush=True)
    return exit_code

if __name__=='__main__':
    raise SystemExit(main())
