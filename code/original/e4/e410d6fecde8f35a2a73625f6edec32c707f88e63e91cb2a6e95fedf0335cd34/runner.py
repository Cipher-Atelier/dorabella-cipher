"""CH3-tabu-dev-v1. Single synchronous bounded attempt. No random/target/truth search input."""
from pathlib import Path
import datetime, hashlib, json, math, os, sys, time, traceback
AZ = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
BRANCHES = ('B0', 'B1', 'B2', 'B3')


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


class CooperativeStop(Exception):
    pass


class Budget:
    def __init__(self, t0):
        self.t0 = t0
        self.evaluations = 0
        self.raw_swaps = 0
        self.completed_sweeps = 0
        self.transitions = 0

    def elapsed(self):
        return time.monotonic() - self.t0

    def check(self):
        if self.elapsed() >= 60.0:
            raise CooperativeStop('COOPERATIVE_60S')

    def score(self, model, text):
        self.check()
        if self.evaluations >= 260000:
            raise ValueError('EVALUATION_CAP')
        self.evaluations += 1
        return model.score(text)

    def snapshot(self):
        return {'evaluations': self.evaluations, 'raw_swaps': self.raw_swaps,
                'completed_sweeps': self.completed_sweeps, 'transitions': self.transitions,
                'elapsed_seconds': self.elapsed()}


def compact_save(path, obj):
    data = (json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return sha(data)


def rank(candidate):
    return (-candidate['score'], candidate['plaintext87'], candidate['key26'])


def observed_signature(key, observed):
    return ''.join(key[i] for i in observed)


def candidate_from_small(small, state):
    return candidate_record(small['plaintext87'], small['score'], list(small['key26']),
                            state['glyphs'], state['groups'])


def small_record(candidate):
    return {k: candidate[k] for k in ('key26', 'plaintext87', 'score')}


def initialize(row, inputs):
    glyphs = inputs[row['case_id']]
    check_glyphs(glyphs)
    groups = groups_for(row['branch'])
    valid, evidence = structural(glyphs, groups)
    if not valid:
        raise ValueError('Assigned branch structural mismatch')
    initial = row['initial_candidate']
    if decode(glyphs, groups, initial['key26']) != initial['plaintext87']:
        raise ValueError('Saved key/text mismatch')
    checked = candidate_record(initial['plaintext87'], initial['score'], list(initial['key26']), glyphs, groups)
    # JSON normalizes tuples; all saved class/inverse evidence must agree exactly.
    if json.loads(json.dumps(checked)) != initial:
        raise ValueError('Saved initial candidate/inverse mismatch')
    observed = [i for i, cycle in enumerate(groups) if any(g in glyphs for g in cycle)]
    return {'state_id': row['state_id'], 'case_id': row['case_id'], 'branch': row['branch'], 'r': row['r'],
            'glyphs': glyphs, 'groups': groups, 'observed_classes': observed,
            'initial': checked, 'current': checked, 'best': checked,
            'tabu': [observed_signature(initial['key26'], observed)],
            'transitions': 0, 'sweeps': [], 'status': 'ACTIVE'}


def sweep(state, model, budget):
    budget.check()
    step = state['transitions'] + 1
    current = state['current']
    basekey = current['key26']
    rows = []
    unique = {}
    unchanged = 0
    started = budget.elapsed()
    before = budget.evaluations
    try:
        for i in range(26):
            for j in range(i + 1, 26):
                budget.check()
                key = list(basekey)
                key[i], key[j] = key[j], key[i]
                key = ''.join(key)
                text = decode(state['glyphs'], state['groups'], key)
                budget.raw_swaps += 1
                raw = {'swap0': [i, j], 'key26': key, 'plaintext87': text}
                rows.append(raw)
                if text == current['plaintext87']:
                    unchanged += 1
                    raw.update(status='UNCHANGED', score=current['score'])
                    continue
                if text not in unique:
                    score = budget.score(model, text)
                    unique[text] = {'key26': key, 'plaintext87': text, 'score': score, 'swap0': [i, j]}
                elif (key, i, j) < (unique[text]['key26'], *unique[text]['swap0']):
                    unique[text].update(key26=key, swap0=[i, j])
                raw.update(status='CHANGED', score=unique[text]['score'])
    except BaseException:
        compact_save(OUT / 'sweeps' / f"{state['state_id']}_s{step:02d}_PARTIAL.json",
                     {'state_id': state['state_id'], 'step': step, 'complete': False,
                      'rows': rows, 'budget': budget.snapshot()})
        raise
    if len(rows) != 325:
        raise ValueError('Incomplete neighborhood')
    values = list(unique.values())
    better = sum(x['score'] > current['score'] for x in values)
    equal = sum(x['score'] == current['score'] for x in values)
    worse = len(values) - better - equal
    best_delta = max(x['score'] - current['score'] for x in values) if values else None
    tabu_before = state['tabu'][:]
    admissible = [x for x in values
                  if observed_signature(x['key26'], state['observed_classes']) not in tabu_before]
    chosen = min(admissible, key=rank) if admissible else None
    allbest = min([small_record(state['best'])] + values, key=rank)
    state['best'] = candidate_from_small(allbest, state)
    for raw in rows:
        if raw['status'] == 'CHANGED':
            representative = unique[raw['plaintext87']]
            raw['representative_swap0'] = representative['swap0']
            raw['representative_key26'] = representative['key26']
            raw['tabu'] = observed_signature(raw['key26'], state['observed_classes']) in tabu_before
    if chosen is None:
        state['status'] = 'NO_ADMISSIBLE_MOVE'
    else:
        state['current'] = candidate_from_small(chosen, state)
        state['tabu'] = (tabu_before + [observed_signature(chosen['key26'], state['observed_classes'])])[-7:]
        state['transitions'] += 1
        budget.transitions += 1
        if state['transitions'] == 20:
            state['status'] = 'MAX_20_TRANSITIONS'
    budget.completed_sweeps += 1
    profile = {'raw_swaps': len(rows), 'unchanged_swaps': unchanged,
               'effective_distinct_changed_strings': len(values),
               'duplicate_changed_swaps': 325 - unchanged - len(values),
               'better': better, 'equal': equal, 'worse': worse, 'best_delta': best_delta,
               'admissible': len(admissible), 'evaluations': budget.evaluations - before}
    rec = {'state_id': state['state_id'], 'step': step, 'complete': True,
           'first_neighborhood': step == 1, 'started_elapsed': started, 'ended_elapsed': budget.elapsed(),
           'current_before': current, 'profile_before_tabu': profile, 'tabu_before': tabu_before,
           'neighbors': rows, 'chosen': chosen, 'current_after': state['current'],
           'best_seen': state['best'], 'tabu_after': state['tabu'], 'status': state['status']}
    name = f"sweeps/{state['state_id']}_s{step:02d}.json"
    digest = compact_save(OUT / name, rec)
    state['sweeps'].append({'file': name, 'sha256': digest, 'profile': profile})
    if step == 1:
        print(json.dumps({'event': 'FIRST_NEIGHBORHOOD', 'state': state['state_id'], 'profile': profile}), flush=True)


def main():
    t0 = time.monotonic()
    started = utc()
    OUT.mkdir(exist_ok=False)  # exclusive attempt guard, no resume path
    budget = Budget(t0)
    save(OUT / 'T0.json', {'utc': started, 'monotonic': t0, 'pid': os.getpid(),
                         'python': sys.version, 'executable': sys.executable,
                         'flags': {'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site},
                         'scope': 'This development attempt only; includes verification/model loading; no prior T0 changed.'})
    print(json.dumps({'event': 'START', 'utc': started, 'pid': os.getpid()}), flush=True)
    states = []
    status = 'INCOMPLETE'
    error = None
    exit_code = 2
    try:
        freeze = json.loads((ROOT / 'FREEZE_MANIFEST.json').read_text())
        runtime = freeze['runtime']
        if sys.version != runtime['version'] or sys.executable != runtime['executable']:
            raise ValueError('Runtime mismatch')
        if not (sys.flags.isolated == 1 and sys.flags.no_site == 1):
            raise ValueError('Need -I -S')
        if sha(Path(sys.executable).read_bytes()) != runtime['binary_sha256']:
            raise ValueError('Runtime binary mismatch')
        for name, digest in runtime['dependency_files'].items():
            budget.check()
            if sha(Path(name).read_bytes()) != digest:
                raise ValueError('Runtime dependency mismatch: ' + name)
        for name, info in freeze['files'].items():
            budget.check()
            if sha((ROOT / name).read_bytes()) != info['sha256']:
                raise ValueError('Freeze mismatch: ' + name)
        protocol = json.loads((ROOT / 'frozen/protocol.json').read_text())
        rows = json.loads((ROOT / 'frozen/initial_states.json').read_text())
        if [x['state_id'] for x in rows] != protocol['state_order'] or len(rows) != 40:
            raise ValueError('Frozen state order mismatch')
        controls = json.loads((ROOT / 'frozen/decoder_controls.json').read_text())
        if [x['id'] for x in controls] != protocol['case_order'] or any(x['status'] != 'READY' for x in controls):
            raise ValueError('Control inputs mismatch')
        inputs = {x['id']: x['glyph'] for x in controls}
        (OUT / 'sweeps').mkdir()
        for row in rows:
            budget.check()
            states.append(initialize(row, inputs))
        model = LyonsModel(ROOT / 'frozen/quadgrams.txt', budget)
        save(OUT / 'model_identity.json', {'N': model.N, 'floor': model.floor,
                                         'entries': len(model.ngrams), 'sha256': sha((ROOT / 'frozen/quadgrams.txt').read_bytes())})
        for state in states:
            sweep(state, model, budget)
        save(OUT / 'first_neighborhoods.json', [{'state_id': s['state_id'], **s['sweeps'][0]} for s in states])
        for state in states:
            while state['status'] == 'ACTIVE' and state['transitions'] < 20:
                sweep(state, model, budget)
            print(json.dumps({'event': 'STATE_END', 'state': state['state_id'], 'status': state['status'],
                              'transitions': state['transitions'], 'initial_score': state['initial']['score'],
                              'best_score': state['best']['score'], 'current_score': state['current']['score'],
                              'budget': budget.snapshot()}), flush=True)
        budget.check()
        if any(s['status'] not in ('MAX_20_TRANSITIONS', 'NO_ADMISSIBLE_MOVE') for s in states):
            raise ValueError('Incomplete path accounting')
        status = 'COMPLETED_DEVELOPMENT'
        exit_code = 0
    except CooperativeStop as exc:
        status = 'INCOMPLETE_TIME'
        error = repr(exc)
    except BaseException as exc:
        status = 'STOP_ERROR'
        error = {'error': repr(exc), 'traceback': traceback.format_exc()}
    save(OUT / 'states.json', states)
    files = {str(p.relative_to(OUT)): sha(p.read_bytes()) for p in sorted(OUT.rglob('*')) if p.is_file()}
    terminal = {'status': status, 'error': error, 'T0_utc': started, 'ended_utc': utc(),
                'budget': budget.snapshot(), 'intended_exit_code': exit_code, 'state_count': len(states),
                'files_sha256': files, 'limits': 'Cooperative 60 s including preparation; terminal writes may extend it. No hard kill or host-crash durability guarantee.'}
    save(OUT / 'terminal.json', terminal)
    print(json.dumps({'event': 'TERMINAL', 'status': status, 'budget': terminal['budget'],
                      'intended_exit_code': exit_code, 'terminal_sha256': sha((OUT / 'terminal.json').read_bytes())}), flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
