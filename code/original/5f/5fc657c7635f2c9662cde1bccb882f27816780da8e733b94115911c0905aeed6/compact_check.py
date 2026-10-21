"""Own bounded storage diagnostic. No solver, scoring, Perl or subprocess."""
from pathlib import Path
import sys, os, json, hashlib, time, datetime, resource, sqlite3, re, struct, traceback

BASE = Path(__file__).resolve().parent
ATTEMPT = BASE / 'attempt'
START = None
DEADLINE = None
R = {'schema': 'TS-COMPACT-STORE-v1', 'status': 'INCOMPLETE', 'solver_executions': 0,
     'scoring_calls': 0, 'target_inputs': 0, 'phase': 'not_started', 'events': []}
DB = None
LAST_TICK = 0.0
MAX_LINE = 8 * 1024 * 1024
MAX_ROWS = 3000000
MAX_CANDIDATES = 50000000
WS = b' \t\n\r\v\f'
BAD = re.compile(rb'[^\x09\x0a\x0b\x0c\x0d\x20-\x7e]')
TABS = re.compile(rb'\t+')

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def atomic_json(name, value):
    p = ATTEMPT / name
    temp = p.with_suffix(p.suffix + '.tmp')
    with temp.open('w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temp, p)

def memory():
    out = {}
    for name in ['memory.max', 'memory.current', 'memory.events']:
        out[name] = (Path('/sys/fs/cgroup') / name).read_text().strip()
    out['self_status'] = [s for s in Path('/proc/self/status').read_text().splitlines()
                          if s.startswith(('VmPeak:', 'VmSize:', 'VmHWM:', 'VmRSS:'))]
    return out

def tick(force=False):
    global LAST_TICK
    now = time.monotonic()
    if now >= DEADLINE:
        raise RuntimeError('STOP_COOPERATIVE_DEADLINE')
    if force or now - LAST_TICK >= .25:
        LAST_TICK = now
        m = memory()
        if int(m['memory.current']) >= 6 * 1024**3:
            raise RuntimeError('STOP_SHARED_MEMORY_THRESHOLD')
        with (ATTEMPT / 'observations.jsonl').open('a') as f:
            f.write(json.dumps({'utc': utc(), 'elapsed': now-START, 'phase': R['phase'],
                                'memory': m}) + '\n')

def phase(name):
    R['phase'] = name
    event = {'phase': name, 'utc': utc(), 'elapsed': time.monotonic()-START}
    R['events'].append(event)
    print(json.dumps(event), flush=True)
    tick(True)

def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(1048576)
            if not b: break
            h.update(b); tick()
    return h.hexdigest()

def parser_a(raw):
    if BAD.search(raw): raise ValueError('STOP_NON_ASCII_OR_CONTROL')
    if raw.endswith(b'\n'): raw = raw[:-1]
    raw = re.sub(rb'\s+$', b'', raw).replace(b' ', b'')
    fields = TABS.split(raw)
    if len(fields) < 3 or fields[0] not in (b'1', b'2', b'3') or not fields[1]:
        raise ValueError('STOP_UNSUPPORTED_ROW')
    if any(not v for v in fields[2:]): raise ValueError('STOP_EMPTY_CANDIDATE')
    return int(fields[0]), fields[1], fields[2:]

def parser_b(raw):
    # Independent tokenization: split raw tab fields first, normalize individually.
    fields = []
    for part in raw.rstrip(WS).split(b'\t'):
        value = part.translate(None, b' ')
        if value: fields.append(value)
    if len(fields) < 3 or fields[0] not in (b'1', b'2', b'3'):
        raise ValueError('STOP_ORACLE_FORMAT')
    return int(fields[0]), fields[1], fields[2:]

def framed_digest(order, pattern, candidates):
    h = hashlib.sha256(bytes([order]))
    for token in [pattern] + candidates:
        h.update(struct.pack('>Q', len(token))); h.update(token)
    return h.digest()

def sqlite_progress():
    return int(time.monotonic() >= DEADLINE)

def main():
    global START, DEADLINE, DB
    if ATTEMPT.exists():
        print('REFUSED_EXISTING_ATTEMPT', flush=True); return 3
    ATTEMPT.mkdir()
    START = time.monotonic(); DEADLINE = START + 180.0
    atomic_json('T0.json', {'utc': utc(), 'monotonic': START, 'deadline': DEADLINE,
                           'old_scientific_T0_untouched': True})
    R['start_utc'] = utc()
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (170, 180))
        resource.setrlimit(resource.RLIMIT_FSIZE, (512*1024**2, 512*1024**2))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        R['limits'] = {name: resource.getrlimit(getattr(resource, name)) for name in
                       ['RLIMIT_AS','RLIMIT_CPU','RLIMIT_FSIZE','RLIMIT_CORE','RLIMIT_NOFILE']}
        R['before'] = memory()
        if int(R['before']['memory.max']) != 8*1024**3 or int(R['before']['memory.current']) > 3*1024**3:
            raise RuntimeError('STOP_RESOURCE_PREFLIGHT')
        freeze = json.loads((BASE/'FREEZE.json').read_text())
        if sys.version != freeze['python_version'] or sqlite3.sqlite_version != freeze['sqlite_version']:
            raise RuntimeError('STOP_RUNTIME_IDENTITY')
        phase('six_frozen_parser_fixtures')
        positives = [
            (b'1\tab\tto\tto\ton\n', (1,b'ab',[b'to',b'to',b'on'])),
            (b'2\ta b\tto go\ton to\n', (2,b'ab',[b'togo',b'onto'])),
            (b'3\tab\t a b c \t d e f \r\n', (3,b'ab',[b'abc',b'def'])),
            (b'1\t\ta\t\ti\t\t a \t \n', (1,b'a',[b'i',b'a'])),
        ]
        for raw, expected in positives:
            if parser_a(raw) != expected or parser_b(raw) != expected:
                raise RuntimeError('STOP_POSITIVE_PARSER_FIXTURE')
        for raw in [b'4\tab\tto\n', b'1\tab\t\n']:
            for parser in [parser_a,parser_b]:
                try: parser(raw)
                except ValueError: pass
                else: raise RuntimeError('STOP_NEGATIVE_PARSER_FIXTURE')
        R['parser_fixtures'] = {'positive':4,'negative':2,'passed':True}
        phase('identity')
        for item in freeze['identities']:
            p = Path(item['path'])
            if p.stat().st_size != item['bytes'] or sha_file(p) != item['sha256']:
                raise RuntimeError('STOP_HASH_IDENTITY:' + p.name)
        R['all_identity_checks'] = True
        source = Path(freeze['patlst_path'])
        expected_hash = freeze['patlst_sha256']
        DB = sqlite3.connect(ATTEMPT/'patlst_index.sqlite', timeout=0)
        for sql in ['PRAGMA page_size=4096','PRAGMA cache_size=-8192','PRAGMA mmap_size=0',
                    'PRAGMA temp_store=FILE','PRAGMA journal_mode=DELETE',
                    'PRAGMA synchronous=FULL','PRAGMA max_page_count=131072']:
            DB.execute(sql).fetchall()
        DB.set_progress_handler(sqlite_progress, 10000)
        DB.executescript('''
            CREATE TABLE segments(seq INTEGER PRIMARY KEY, original_order INTEGER NOT NULL,
                pattern BLOB NOT NULL, offset INTEGER NOT NULL, raw_bytes INTEGER NOT NULL,
                count INTEGER NOT NULL, longest INTEGER NOT NULL, digest BLOB NOT NULL);
            CREATE INDEX by_pattern ON segments(pattern, seq);
            CREATE TABLE words(word BLOB PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE words_oracle(word BLOB PRIMARY KEY) WITHOUT ROWID;
        ''')
        phase('build_patlst_index')
        n = total = offset = max_line = max_len = 0
        per_order = {'1': {'rows': 0, 'candidates': 0}, '2': {'rows': 0, 'candidates': 0}, '3': {'rows': 0, 'candidates': 0}}
        h = hashlib.sha256()
        with source.open('rb') as f:
            while True:
                raw = f.readline(MAX_LINE + 1)
                if not raw: break
                if len(raw) > MAX_LINE: raise RuntimeError('STOP_LINE_BOUND')
                n += 1
                if n > MAX_ROWS: raise RuntimeError('STOP_ROW_BOUND')
                order, pattern, candidates = parser_a(raw)
                total += len(candidates)
                if total > MAX_CANDIDATES: raise RuntimeError('STOP_CANDIDATE_BOUND')
                longest = max(map(len, candidates))
                max_len = max(max_len, longest); max_line = max(max_line, len(raw))
                per_order[str(order)]['rows'] += 1
                per_order[str(order)]['candidates'] += len(candidates)
                DB.execute('INSERT INTO segments VALUES(?,?,?,?,?,?,?,?)',
                           (n,order,pattern,offset,len(raw),len(candidates),longest,framed_digest(order,pattern,candidates)))
                if order == 1:
                    DB.executemany('INSERT OR IGNORE INTO words VALUES(?)', ((x,) for x in candidates))
                h.update(raw); offset += len(raw)
                if n % 4096 == 0: DB.commit(); tick()
                if n % 65536 == 0:
                    print(json.dumps({'build_rows': n, 'source_bytes': offset}), flush=True)
                tick()
        DB.commit()
        if h.hexdigest() != expected_hash: raise RuntimeError('STOP_BUILD_INPUT_HASH')
        R['build'] = {'rows': n, 'candidates_with_duplicates': total, 'bytes': offset,
                      'per_original_order': per_order, 'max_raw_line_bytes': max_line,
                      'max_candidate_bytes': max_len, 'raw_sha256': h.hexdigest()}
        atomic_json('build_checkpoint.json', R['build'])
        phase('verify_all_rows_independent_parser')
        offset2 = count2 = total2 = maxlen2 = 0
        h2 = hashlib.sha256()
        with source.open('rb') as f:
            for seq, order, pattern, off, nr, nc, longest, digest in DB.execute('SELECT * FROM segments ORDER BY seq'):
                tick()
                raw = f.read(nr)
                if seq != count2+1 or off != offset2 or len(raw) != nr:
                    raise RuntimeError('STOP_OFFSET_ACCOUNTING')
                o2, p2, c2 = parser_b(raw)
                if (o2,p2,len(c2),max(map(len,c2)),framed_digest(o2,p2,c2)) != (order,pattern,nc,longest,digest):
                    raise RuntimeError('STOP_SEMANTIC_READBACK')
                if o2 == 1:
                    DB.executemany('INSERT OR IGNORE INTO words_oracle VALUES(?)', ((x,) for x in c2))
                h2.update(raw); count2 += 1; offset2 += nr; total2 += len(c2); maxlen2 = max(maxlen2,longest)
                if count2 % 4096 == 0: DB.commit()
            if f.read(1): raise RuntimeError('STOP_UNINDEXED_TAIL')
        DB.commit()
        if (count2,total2,maxlen2,h2.hexdigest()) != (n,total,max_len,expected_hash):
            raise RuntimeError('STOP_TOTAL_READBACK')
        for a,b in [('words','words_oracle'),('words_oracle','words')]:
            if DB.execute(f'SELECT word FROM {a} EXCEPT SELECT word FROM {b} LIMIT 1').fetchone() is not None:
                raise RuntimeError('STOP_LEXICON_MISMATCH')
        R['lexicon_count'] = DB.execute('SELECT count(*) FROM words').fetchone()[0]
        R['full_row_readback'] = {'rows':count2, 'candidates':total2, 'raw_sha256':h2.hexdigest(),
                                 'lexicon_two_way_difference':0, 'maxlen_equal':True}
        phase('verify_group_order_and_statistics')
        groups = merges = max_group = 0
        current = None; last_seq = 0; group_count = 0; mask = 0; max_pattern = None
        def finish_group():
            nonlocal groups, merges, max_group, max_pattern
            if current is None: return
            groups += 1
            if mask.bit_count() > 1: merges += 1
            if group_count > max_group:
                max_group = group_count; max_pattern = current.decode('ascii')
        for pattern, seq, order, nc in DB.execute('SELECT pattern,seq,original_order,count FROM segments ORDER BY pattern,seq'):
            tick()
            if pattern != current:
                finish_group(); current=pattern; last_seq=0; group_count=0; mask=0
            if seq <= last_seq: raise RuntimeError('STOP_GROUP_ORDER')
            last_seq=seq; group_count += nc; mask |= 1 << order
        finish_group()
        R['groups'] = {'distinct_normalized_patterns':groups, 'patterns_merging_original_orders':merges,
                       'max_candidates_in_one_pattern':max_group, 'max_pattern':max_pattern,
                       'sequence_order_verified':True, 'duplicates_not_removed':True}
        R['lookup_query_plan'] = DB.execute('EXPLAIN QUERY PLAN SELECT * FROM segments WHERE pattern=? ORDER BY seq', (b'a',)).fetchall()
        if DB.execute('PRAGMA quick_check').fetchall() != [('ok',)]: raise RuntimeError('STOP_SQLITE_QUICK_CHECK')
        DB.commit(); DB.close(); DB=None
        phase('seal')
        R['index_bytes'] = (ATTEMPT/'patlst_index.sqlite').stat().st_size
        R['index_sha256'] = sha_file(ATTEMPT/'patlst_index.sqlite')
        R['status'] = 'PASS_STORAGE_CONTRACT_ONLY'
        R['limits_of_result'] = ['Not original Perl equivalence execution', 'Not numerical score equivalence',
                                'Not search/resource viability', 'No target/control decoding',
                                'Source file plus pinned index are required together']
        tick(True)
        return 0
    except BaseException as e:
        R['status'] = 'STOP'
        R['error'] = type(e).__name__ + ': ' + str(e)
        R['traceback'] = traceback.format_exc()
        print(R['error'], flush=True)
        return 2
    finally:
        if DB is not None:
            try: DB.close()
            except Exception: pass
        R['end_utc'] = utc(); R['elapsed'] = time.monotonic()-START
        R['after'] = memory(); R['maxrss_KiB'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if R['elapsed'] > 180 and R['status'] == 'PASS_STORAGE_CONTRACT_ONLY':
            R['status'] = 'STOP'; R['error'] = 'STOP_FINAL_ELAPSED'
        atomic_json('result.json', R)
        print(json.dumps({'status':R['status'], 'elapsed':R['elapsed'], 'maxrss_KiB':R['maxrss_KiB']}), flush=True)
        if R['status'] == 'STOP': return 2

if __name__ == '__main__':
    sys.exit(main())
