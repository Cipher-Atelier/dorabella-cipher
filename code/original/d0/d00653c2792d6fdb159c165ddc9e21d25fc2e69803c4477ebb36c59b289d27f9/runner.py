"""CH3-SA-dev-v1: sole synchronous attempt, standard library, no target/truth in search."""
from pathlib import Path
import datetime, hashlib, json, math, os, sys, time, traceback, random, gzip
AZ = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
BRANCHES = ('B0','B1','B2','B3')


def sha(data):
    return hashlib.sha256(data).hexdigest()

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def save(path, obj):
    data = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return sha(data)

class LyonsModel:
    def __init__(self, path, budget):
        counts = {}
        with path.open('r', encoding='ascii') as f:
            for line_number, line in enumerate(f, 1):
                key, count = line.split()
                if len(key) != 4 or any(c not in AZ for c in key) or key in counts or int(count) <= 0:
                    raise ValueError('Malformed/duplicate model row')
                counts[key] = int(count)
                if line_number % 4096 == 0:
                    budget.check()
        self.N = sum(counts.values())
        self.ngrams = {}
        for i, (key, count) in enumerate(counts.items()):
            self.ngrams[key] = math.log10(float(count) / self.N)
            if i % 4096 == 0:
                budget.check()
        self.floor = math.log10(0.01 / self.N)
        budget.check()

    def score(self, text):
        if len(text) != 87:
            raise ValueError('Score length != 87')
        score = 0
        get = self.ngrams.get
        floor = self.floor
        for i in range(84):
            score += get(text[i:i + 4], floor)
        return score

def groups_for(branch):
    if branch not in BRANCHES:
        raise ValueError('Unknown branch')
    pairs = []
    if branch in ('B1', 'B3'):
        pairs.append((5, 15))
    if branch in ('B2', 'B3'):
        pairs.append((22, 8))
    reserved = {g for cycle in pairs for g in cycle}
    return sorted(pairs + [(g,) for g in range(24) if g not in reserved], key=min)

def check_glyphs(glyphs):
    if len(glyphs) != 87 or any(type(x) is not int or not 0 <= x < 24 for x in glyphs):
        raise ValueError('Invalid 87-glyph input')

def structural(glyphs, groups):
    evidence = []
    for cycle in groups:
        positions = [i for i, g in enumerate(glyphs) if g in cycle]
        projection = [glyphs[i] for i in positions]
        violations = [{'position1': i + 1, 'seen': glyphs[i], 'expected': cycle[j % len(cycle)]}
                      for j, i in enumerate(positions) if glyphs[i] != cycle[j % len(cycle)]]
        evidence.append({'cycle': cycle, 'positions1': [i + 1 for i in positions],
                         'projection': projection, 'violations': violations})
    return not any(x['violations'] for x in evidence), evidence

def encode(text, key):
    visits = {letter: 0 for letter in key}
    glyphs = []
    for letter in text:
        cycle = key[letter]
        glyphs.append(cycle[visits[letter] % len(cycle)])
        visits[letter] += 1
    return glyphs

def inverse_record(text, glyphs, key):
    # Independent prefix-count oracle, not encode()'s mutable counters.
    check_glyphs(glyphs)
    if len(text) != 87 or any(c not in AZ for c in text):
        raise ValueError('Invalid inverse plaintext')
    owner = {}
    for letter, cycle in key.items():
        for g in cycle:
            if g in owner:
                raise ValueError('Non-disjoint key')
            owner[g] = letter
    recovered = ''.join(owner[g] for g in glyphs)
    positions = []
    for i, (letter, g) in enumerate(zip(text, glyphs)):
        cycle = key[letter]
        visit = text[:i].count(letter)
        expected = cycle[visit % len(cycle)]
        positions.append({'position1': i + 1, 'letter': letter, 'visit0': visit,
                          'cycle': list(cycle), 'glyph': g, 'reencoded_glyph': expected,
                          'decoded_letter': owner[g], 'match': expected == g and owner[g] == letter})
    if recovered != text or not all(x['match'] for x in positions):
        raise ValueError('CORRECTNESS_INVERSE_MISMATCH')
    return {'matched': 87, 'recovered_plaintext87': recovered,
            'reencoded_glyphs87': [x['reencoded_glyph'] for x in positions], 'positions': positions}

def decode(glyphs, groups, key):
    table = {g: key[i] for i, cycle in enumerate(groups) for g in cycle}
    return ''.join(table[g] for g in glyphs)

def candidate_record(text, score, key, glyphs, groups):
    if len(key) != 26 or sorted(key) != list(AZ):
        raise ValueError('Non-permutation key')
    encoder = {key[i]: cycle for i, cycle in enumerate(groups)}
    return {'plaintext87': text, 'score': score, 'key26': ''.join(key),
            'class_table': [{'class_index0': i, 'cycle': cycle, 'letter': key[i],
                             'observed': any(g in glyphs for g in cycle)} for i, cycle in enumerate(groups)],
            'unused_letters': ''.join(key[len(groups):]),
            'inverse': inverse_record(text, glyphs, encoder)}

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'attempt'
PAIRS = [(i, j) for i in range(26) for j in range(i + 1, 26)]


class CooperativeStop(Exception):
    pass


class Budget:
    def __init__(self, t0):
        self.t0 = t0
        self.proposals = 0
        self.evaluations = 0
        self.accepted = 0
        self.accepted_worse = 0
        self.accepted_equal = 0
        self.accepted_better = 0
        self.unchanged_proposals = 0
        self.completed_state_stages = 0

    def elapsed(self):
        return time.monotonic() - self.t0

    def check(self):
        if self.elapsed() >= 60.0:
            raise CooperativeStop('COOPERATIVE_60S')

    def evaluate(self, model, text):
        if self.proposals >= 260000 or self.evaluations >= 260000:
            raise ValueError('WORK_CAP')
        self.proposals += 1
        self.evaluations += 1
        return model.score(text)

    def snapshot(self):
        return {k: v for k, v in vars(self).items() if k != 't0'} | {'elapsed_seconds': self.elapsed()}


def pack(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()


def save_gzip(path, obj):
    data = gzip.compress(pack(obj), compresslevel=1, mtime=0)
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return sha(data)


def rank(c):
    return (-c['score'], c['plaintext87'], c['key26'])


def keep_candidate(key, text, score, state, store, pending, location):
    # Every accepted/best candidate executes the unchanged full inverse.
    full = candidate_record(text, score, list(key), state['glyphs'], state['groups'])
    inv = full['inverse']
    ident = state['case_id'] + '_' + sha(text.encode('ascii'))
    digest = sha(pack(inv))
    if ident in store:
        ref = store[ident]
        if ref['sha256'] != digest:
            raise ValueError('Inverse dedup identity mismatch')
    else:
        ref = {'file': location, 'id': ident, 'sha256': digest}
        store[ident] = ref
        pending[ident] = {'case_id': state['case_id'], 'branch': state['branch'],
                          'plaintext87': text, 'inverse': inv, 'sha256': digest}
    return {'key26': key, 'plaintext87': text, 'score': score, 'inverse_ref': ref}


def initialize(rows, inputs, seeds, store):
    states, pending = [], {}
    for row, seedrow in zip(rows, seeds):
        if row['state_id'] != seedrow['state_id']:
            raise ValueError('Seed order mismatch')
        seed_text = 'CH3-SA-dev-v1|2026101704|' + row['state_id']
        seed = int.from_bytes(hashlib.sha256(seed_text.encode('utf-8')).digest(), 'big')
        if seedrow['seed_text'] != seed_text or seedrow['seed_integer'] != seed:
            raise ValueError('Seed identity mismatch')
        g = inputs[row['case_id']]
        check_glyphs(g)
        groups = groups_for(row['branch'])
        if not structural(g, groups)[0]:
            raise ValueError('Assigned branch structural mismatch')
        initial = row['initial_candidate']
        if decode(g, groups, initial['key26']) != initial['plaintext87']:
            raise ValueError('Saved key/text mismatch')
        checked = candidate_record(initial['plaintext87'], initial['score'], list(initial['key26']), g, groups)
        if json.loads(json.dumps(checked)) != initial:
            raise ValueError('Saved initial/inverse mismatch')
        state = {k: row[k] for k in ('state_id', 'case_id', 'branch', 'r')}
        state.update(glyphs=g, groups=groups, seed_text=seed_text, seed_integer=seed,
                     rng=random.Random(seed), proposed=0, accepted=0, checkpoints=[], best_tied_texts=[initial['plaintext87']])
        cur = keep_candidate(initial['key26'], initial['plaintext87'], initial['score'], state,
                             store, pending, 'initial_inverses.json.gz')
        state.update(initial=cur, current=cur, best=cur)
        states.append(state)
    save_gzip(OUT / 'initial_inverses.json.gz', {'inverses': pending})
    return states


def run_stage(state, l, model, budget, store):
    budget.check()
    T = 10.0 * math.exp(math.log(0.01) * l / 19)
    location = f"stages/{state['state_id']}_l{l:02d}.json.gz"
    records, pending = [], {}
    started = budget.elapsed()
    stage_initial = state['current']
    best_initial = state['best']
    error = None
    complete = False
    try:
        for n in range(325):
            budget.check()
            # Mandatory primitive order: pair selection, then unconditional u.
            k = state['rng'].randrange(325)
            u = state['rng'].random()
            i, j = PAIRS[k]
            before = state['current']
            key = list(before['key26'])
            key[i], key[j] = key[j], key[i]
            key = ''.join(key)
            text = decode(state['glyphs'], state['groups'], key)
            row = {'state_id': state['state_id'], 'stage0': l, 'proposal_in_stage0': n,
                   'proposal_in_state1': state['proposed'] + 1, 'pair_index0': k, 'swap0': [i, j],
                   'u': u, 'temperature': T, 'child': {'key26': key, 'plaintext87': text},
                   'current_before': before}
            records.append(row)
            score = budget.evaluate(model, text)
            state['proposed'] += 1
            row['child']['score'] = score
            delta = score - before['score']
            probability = 1.0 if delta >= 0 else math.exp(delta / T)
            accept = delta >= 0 or u < probability
            unchanged = text == before['plaintext87']
            row.update(delta=delta, acceptance_probability=probability, accepted=accept, unchanged_plaintext=unchanged)
            budget.unchanged_proposals += int(unchanged)
            if accept:
                current = keep_candidate(key, text, score, state, store, pending, location)
                state['current'] = current
                state['accepted'] += 1
                budget.accepted += 1
                budget.accepted_better += int(delta > 0)
                budget.accepted_equal += int(delta == 0)
                budget.accepted_worse += int(delta < 0)
            if score > state['best']['score']:
                state['best_tied_texts'] = [text]
            elif score == state['best']['score'] and text not in state['best_tied_texts']:
                state['best_tied_texts'].append(text)
                state['best_tied_texts'].sort()
            small = {'key26': key, 'plaintext87': text, 'score': score}
            if rank(small) < rank(state['best']):
                if not accept:
                    raise ValueError('Improved/tied best unexpectedly rejected')
                state['best'] = state['current']
            row.update(current_after=state['current'], best_after=state['best'], elapsed_seconds=budget.elapsed())
        complete = True
        budget.completed_state_stages += 1
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        record = {'state_id': state['state_id'], 'stage0': l, 'temperature': T,
                  'complete': complete, 'error': error, 'started_elapsed': started,
                  'ended_elapsed': budget.elapsed(), 'current_initial': stage_initial, 'best_initial': best_initial,
                  'records': records, 'inverses': pending, 'current_final': state['current'],
                  'best_final': state['best'], 'best_tied_texts': state['best_tied_texts'],
                  'rng_state_after': state['rng'].getstate(), 'budget': budget.snapshot()}
        digest = save_gzip(OUT / location, record)
        state['checkpoints'].append({'file': location, 'sha256': digest, 'complete': complete,
                                     'stage0': l, 'proposals': len(records)})


def main():
    t0 = time.monotonic()
    started = utc()
    OUT.mkdir(exist_ok=False)
    budget = Budget(t0)
    save(OUT / 'T0.json', {'utc': started, 'monotonic': t0, 'pid': os.getpid(), 'python': sys.version,
                         'executable': sys.executable, 'flags': {'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site},
                         'scope': 'This SA development attempt only; all preparation/model loading included; old T0 unchanged.'})
    print(json.dumps({'event': 'START', 'utc': started, 'pid': os.getpid()}), flush=True)
    states, store = [], {}
    status, error, exit_code = 'INCOMPLETE', None, 2
    try:
        manifest = json.loads((ROOT / 'FREEZE_MANIFEST.json').read_text())
        rt = manifest['runtime']
        if sys.version != rt['version'] or sys.executable != rt['executable'] or not(sys.flags.isolated == 1 and sys.flags.no_site == 1):
            raise ValueError('Runtime/flags mismatch')
        if sha(Path(sys.executable).read_bytes()) != rt['binary_sha256']:
            raise ValueError('Runtime binary mismatch')
        for name, digest in rt['dependency_files'].items():
            budget.check()
            if sha(Path(name).read_bytes()) != digest:
                raise ValueError('Runtime dependency mismatch')
        for name, info in manifest['files'].items():
            budget.check()
            if sha((ROOT / name).read_bytes()) != info['sha256']:
                raise ValueError('Freeze file mismatch: ' + name)
        rows = json.loads((ROOT / 'frozen/initial_states.json').read_text())
        seeds = json.loads((ROOT / 'frozen/seeds.json').read_text())
        controls = json.loads((ROOT / 'frozen/decoder_controls.json').read_text())
        order = [p + f'{i:02d}' for p in ('P', 'N') for i in range(1, 5)]
        expected = [f'{c}_B{int(c[1:])-1}_r{r}' for c in order for r in range(5)]
        if [x['state_id'] for x in rows] != expected or len(seeds) != 40:
            raise ValueError('Initial states/order mismatch')
        if [x['id'] for x in controls] != order or any(x['status'] != 'READY' for x in controls):
            raise ValueError('Control input mismatch')
        (OUT / 'stages').mkdir()
        inputs = {x['id']: x['glyph'] for x in controls}
        states = initialize(rows, inputs, seeds, store)
        model = LyonsModel(ROOT / 'frozen/quadgrams.txt', budget)
        save(OUT / 'model_identity.json', {'N': model.N, 'floor': model.floor, 'entries': len(model.ngrams),
                                         'quadgrams_sha256': sha((ROOT / 'frozen/quadgrams.txt').read_bytes())})
        for l in range(20):
            for state in states:
                run_stage(state, l, model, budget, store)
            print(json.dumps({'event': 'STAGE_END', 'stage0': l, 'budget': budget.snapshot()}), flush=True)
        budget.check()
        if budget.proposals != 260000 or budget.evaluations != 260000 or any(s['proposed'] != 6500 for s in states):
            raise ValueError('Incomplete workload')
        status, exit_code = 'COMPLETED_DEVELOPMENT', 0
    except CooperativeStop as exc:
        status, error = 'INCOMPLETE_TIME', repr(exc)
    except BaseException as exc:
        status, error = 'STOP_ERROR', {'error': repr(exc), 'traceback': traceback.format_exc()}
    save(OUT / 'states.json', [{k: v for k, v in s.items() if k != 'rng'} for s in states])
    save(OUT / 'inverse_index.json', store)
    files = {str(p.relative_to(OUT)): sha(p.read_bytes()) for p in sorted(OUT.rglob('*')) if p.is_file()}
    terminal = {'status': status, 'error': error, 'T0_utc': started, 'ended_utc': utc(),
                'budget': budget.snapshot(), 'intended_exit_code': exit_code, 'state_count': len(states),
                'files_sha256': files,
                'limits': '60s cooperative, includes preparation; terminal writes may extend observation; no hard-kill/host-crash guarantee.'}
    save(OUT / 'terminal.json', terminal)
    print(json.dumps({'event': 'TERMINAL', 'status': status, 'budget': terminal['budget'],
                      'intended_exit_code': exit_code, 'terminal_sha256': sha((OUT / 'terminal.json').read_bytes())}), flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
