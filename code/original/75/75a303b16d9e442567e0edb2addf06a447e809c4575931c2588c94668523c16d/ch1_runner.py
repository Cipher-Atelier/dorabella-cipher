import time
START = time.monotonic()
import datetime
import hashlib
import itertools
import json
import pathlib
import sys
from collections import Counter

BASE = pathlib.Path(__file__).resolve().parent.parent
ATTEMPT = BASE / 'attempt'
LIMIT = 10.0
INSPECTIONS = 0
CASE_HASHES = {}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def deadline():
    if time.monotonic() - START > LIMIT:
        raise TimeoutError('10-second cooperative attempt limit exceeded')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def save(name, data):
    deadline()
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    path = ATTEMPT / name
    with path.open('xb') as f:
        f.write(raw)
    deadline()
    return sha(raw)


def validate_sequence(seq):
    require(len(seq) == 87, 'length is not 87')
    require(all(type(x) is int and 0 <= x < 24 for x in seq), 'invalid glyph')
    types = sorted(set(seq))
    require(len(types) <= 24, 'more than 24 observed types')
    require(len(types) * (len(types) - 1) // 2 <= 276, 'pair budget exceeded')
    deadline()
    return types


def diagnose(case_id, seq):
    global INSPECTIONS
    types = validate_sequence(seq)
    counts = Counter(seq)
    pairs = []
    for u, v in itertools.combinations(types, 2):
        deadline()
        positions, projection = [], []
        for pos, glyph in enumerate(seq, 1):
            INSPECTIONS += 1
            require(INSPECTIONS <= 120060, 'primary inspection budget exceeded')
            if glyph == u or glyph == v:
                positions.append(pos)
                projection.append(glyph)
        violation = None
        for j in range(1, len(projection)):
            if projection[j - 1] == projection[j]:
                violation = {
                    'projection_positions_1based': [j, j + 1],
                    'original_positions_1based': [positions[j - 1], positions[j]],
                    'glyphs': [projection[j - 1], projection[j]],
                    'no_u_or_v_strictly_between': True,
                }
                break
        pairs.append({
            'pair': [u, v], 'counts': [counts[u], counts[v]],
            'original_positions_1based': positions, 'projection': projection,
            'first_violation': violation,
            'status': 'PAIR_INCOMPATIBLE' if violation else 'PAIR_NOT_REJECTED',
            'automatic_both_singletons': counts[u] == counts[v] == 1,
        })
    compatible = [p['pair'] for p in pairs if p['status'] == 'PAIR_NOT_REJECTED']
    return {
        'id': case_id, 'glyph': seq, 'observed_types': types,
        'counts_by_type': {str(g): counts[g] for g in types},
        'pair_count': len(pairs), 'compatible_count': len(compatible),
        'incompatible_count': len(pairs) - len(compatible),
        'compatible_pairs': compatible,
        'automatic_compatible_pairs': [p['pair'] for p in pairs if p['automatic_both_singletons']],
        'pairs': pairs,
    }


def roundtrip(seq, cycles):
    # Truth uses position parity, independently of the diagnostic and period formula.
    truth = ['X' if pos % 2 else 'Y' for pos in range(1, 88)]
    inverse = {glyph: letter for letter, cycle in cycles.items() for glyph in cycle}
    require(len(inverse) == sum(len(c) for c in cycles.values()), 'overlapping cycles')
    counters = {letter: 0 for letter in cycles}
    records = []
    for pos, (letter, glyph) in enumerate(zip(truth, seq), 1):
        deadline()
        decoded = inverse[glyph]
        cycle = cycles[letter]
        phase = counters[letter] % len(cycle)
        encoded = cycle[phase]
        counters[letter] += 1
        records.append({
            'position_1based': pos, 'truth': letter, 'input_glyph': glyph,
            'decoded_letter': decoded, 'reencoded_glyph': encoded,
            'phase_before': phase, 'decode_matches': decoded == letter,
            'encode_matches': encoded == glyph,
        })
    return {
        'cycles': cycles, 'initial_phases': {k: 0 for k in cycles},
        'truth': truth, 'records': records,
        'decode_match_count': sum(r['decode_matches'] for r in records),
        'encode_match_count': sum(r['encode_matches'] for r in records),
    }


def main():
    deadline()
    require(len(sys.argv) == 2, 'exact manifest hash argument required')
    manifest_raw = (BASE / 'freeze_manifest.json').read_bytes()
    require(sha(manifest_raw) == sys.argv[1], 'manifest hash mismatch')
    manifest = json.loads(manifest_raw)
    require(sys.version == manifest['runtime']['version'], 'runtime version mismatch')
    require(str(pathlib.Path(sys.executable).resolve()) == manifest['runtime']['executable_resolved'], 'executable mismatch')
    require(sha(pathlib.Path(sys.executable).read_bytes()) == manifest['runtime']['executable_sha256'], 'executable hash mismatch')
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1, '-I -S missing')
    for name, expected in manifest['files_sha256'].items():
        require(sha((BASE / name).read_bytes()) == expected, 'frozen file hash mismatch: ' + name)
        deadline()
    source_raw = (BASE / 'inputs/search_inputs.json').read_bytes()
    require(sha(source_raw) == '20213ef608d401bd393ff545ba4c854cfc2cd1ddc546f55a96db4917c6f68894', 'source hash mismatch')
    reals = [r for r in json.loads(source_raw) if r.get('kind') == 'real']
    require([r['id'] for r in reals] == ['hauer_real', 'hart_real'], 'real IDs/order mismatch')
    require(reals == json.loads((BASE / 'inputs/real_inputs.json').read_bytes()), 'extracted inputs mismatch')
    for record in reals:
        validate_sequence(record['glyph'])
    identity = {
        'source_library_id': manifest['source']['library_id'],
        'source_member': manifest['source']['member'], 'source_sha256': sha(source_raw),
        'records': reals,
        'glyph_strings': {r['id']: ','.join(map(str, r['glyph'])) for r in reals},
        'positions_17_to_22_1based': {r['id']: r['glyph'][16:22] for r in reals},
        'manifest_sha256': sha(manifest_raw),
    }
    identity_hash = save('input_identity.json', identity)

    p2 = [[0, 2, 1, 2][i % 4] for i in range(87)]
    p3 = [[0, 3, 1, 3, 2, 3][i % 6] for i in range(87)]
    n2 = p2.copy()
    n2[2], n2[4] = n2[4], n2[2]  # Exactly 1-based positions 3 and 5.
    controls = [
        ('P2', p2, [[0, 1]], {'X': [0, 1], 'Y': [2]}),
        ('P3', p3, [[0, 1], [0, 2], [1, 2]], {'X': [0, 1, 2], 'Y': [3]}),
        ('N2', n2, [], None),
    ]
    summaries = []
    for case_id, seq, expected, cycles in controls:
        result = diagnose(case_id, seq)
        result['expected_compatible_pairs'] = expected
        graph_ok = result['compatible_pairs'] == expected
        result['control_graph_matches'] = graph_ok
        rt_ok = True
        if cycles is not None:
            result['roundtrip'] = roundtrip(seq, cycles)
            rt_ok = result['roundtrip']['decode_match_count'] == 87 and result['roundtrip']['encode_match_count'] == 87
        else:
            result['swap'] = {
                'positions_1based': [3, 5], 'positions_0based': [2, 4],
                'before': [p2[2], p2[4]], 'after': [n2[2], n2[4]],
                'length_and_counts_preserved': len(n2) == len(p2) and Counter(n2) == Counter(p2),
            }
            rt_ok = result['swap']['length_and_counts_preserved']
        result['control_pass'] = graph_ok and rt_ok
        CASE_HASHES[case_id + '.json'] = save(case_id + '.json', result)
        require(result['control_pass'], 'CONTROL_MISMATCH: ' + case_id)
        summaries.append({k: result[k] for k in ('id', 'pair_count', 'compatible_count', 'incompatible_count', 'compatible_pairs')})

    real_results = []
    for record in reals:
        result = diagnose(record['id'], record['glyph'])
        result['source_identity'] = {'kind': record['kind'], 'source_sha256': sha(source_raw)}
        CASE_HASHES[record['id'] + '.json'] = save(record['id'] + '.json', result)
        real_results.append(result)
        summaries.append({k: result[k] for k in ('id', 'pair_count', 'compatible_count', 'incompatible_count', 'compatible_pairs', 'automatic_compatible_pairs')})
    h_pairs = {tuple(p['pair']): p['status'] for p in real_results[0]['pairs']}
    m_pairs = {tuple(p['pair']): p['status'] for p in real_results[1]['pairs']}
    comparison = {'both_incompatible': [], 'hauer_only_incompatible': [], 'hart_only_incompatible': [], 'neither_rejected': []}
    for pair in sorted(h_pairs.keys() & m_pairs.keys()):
        h_bad = h_pairs[pair] == 'PAIR_INCOMPATIBLE'
        m_bad = m_pairs[pair] == 'PAIR_INCOMPATIBLE'
        key = 'both_incompatible' if h_bad and m_bad else 'hauer_only_incompatible' if h_bad else 'hart_only_incompatible' if m_bad else 'neither_rejected'
        comparison[key].append(list(pair))
    summary = {
        'status': 'COMPLETED_STRUCTURAL_DIAGNOSTIC',
        'case_order': [s['id'] for s in summaries], 'cases': summaries,
        'comparison': comparison,
        'comparison_counts': {k: len(v) for k, v in comparison.items()},
        'only_hauer_observed_pairs': [list(p) for p in sorted(h_pairs.keys() - m_pairs.keys())],
        'only_hart_observed_pairs': [list(p) for p in sorted(m_pairs.keys() - h_pairs.keys())],
        'primary_symbol_inspections': INSPECTIONS, 'primary_symbol_inspection_limit': 120060,
        'cooperative_limit_seconds': LIMIT,
    }
    summary_hash = save('summary.json', summary)
    terminal = {
        'status': summary['status'], 'case_order': summary['case_order'],
        'case_sha256': CASE_HASHES, 'input_identity_sha256': identity_hash,
        'summary_sha256': summary_hash, 'manifest_sha256': sha(manifest_raw),
        'start_record_sha256': sha((ATTEMPT / 'START.json').read_bytes()),
        'utc_before_terminal_write': utc(), 'elapsed_before_terminal_write_seconds': time.monotonic() - START,
        'cooperative_limit_seconds': LIMIT,
        'completion_requires_external_normal_exit0_and_postwrite_elapsed': True,
    }
    terminal_hash = save('terminal.json', terminal)
    deadline()
    print(json.dumps({
        'status': summary['status'], 'terminal_sha256': terminal_hash,
        'elapsed_after_terminal_write_seconds': time.monotonic() - START,
        'utc_after_terminal_write': utc(), 'cases': summaries,
        'comparison_counts': summary['comparison_counts'],
        'primary_symbol_inspections': INSPECTIONS,
    }, ensure_ascii=False), flush=True)
    deadline()


if __name__ == '__main__':
    # Exclusive directory is the single-attempt guard, never resumed or replaced.
    try:
        ATTEMPT.mkdir(exist_ok=False)
    except FileExistsError:
        print(json.dumps({'status': 'STOP_EXISTING_ATTEMPT', 'attempt': str(ATTEMPT)}), flush=True)
        raise SystemExit(3)
    try:
        save('START.json', {
            'utc_after_imports': utc(), 'elapsed_since_first_import_seconds': time.monotonic() - START,
            'command_argv': sys.argv, 'python': sys.version, 'executable': sys.executable,
            'limit_seconds': LIMIT, 'timer_scope': 'first import time through terminal write and stdout; cooperative, not hard kill',
        })
        main()
    except BaseException as exc:
        abort = {
            'status': 'INCOMPLETE', 'exception_type': type(exc).__name__, 'message': str(exc),
            'utc': utc(), 'elapsed_seconds': time.monotonic() - START,
            'completed_case_sha256': CASE_HASHES, 'primary_symbol_inspections': INSPECTIONS,
            'retry_forbidden': True,
        }
        # Best-effort failure evidence; no durability guarantee and no automatic retry.
        try:
            with (ATTEMPT / 'ABORT.json').open('x') as f:
                json.dump(abort, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        print(json.dumps(abort, ensure_ascii=False), flush=True)
        raise SystemExit(2)
