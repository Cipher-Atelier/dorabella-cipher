"""Read saved receipts/records only. Never import or invoke ch1_runner."""
import hashlib
import json
import pathlib
import datetime

BASE = pathlib.Path(__file__).resolve().parent
A = BASE / 'attempt'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

receipt = read(BASE / 'raw_execution_receipt.json')
raw = receipt['raw_tool_response']
assert raw['exit_code'] == 0 and not raw.get('session_id')
assert receipt['invocation_count'] == 1 and receipt['retry'] is False
assert receipt['outer_observed_seconds'] <= 10
stdout = json.loads(raw['output'])
terminal = read(A / 'terminal.json')
assert digest(A / 'terminal.json') == stdout['terminal_sha256']
assert stdout['status'] == terminal['status'] == 'COMPLETED_STRUCTURAL_DIAGNOSTIC'
assert stdout['elapsed_after_terminal_write_seconds'] <= 10
assert terminal['elapsed_before_terminal_write_seconds'] <= stdout['elapsed_after_terminal_write_seconds']
assert not list(A.glob('*ABORT*'))
manifest = read(BASE / 'freeze_manifest.json')
assert digest(BASE / 'freeze_manifest.json') == terminal['manifest_sha256']
for name, expected in manifest['files_sha256'].items():
    assert digest(BASE / name) == expected
assert digest(A / 'START.json') == terminal['start_record_sha256']
assert digest(A / 'input_identity.json') == terminal['input_identity_sha256']
assert digest(A / 'summary.json') == terminal['summary_sha256']
summary = read(A / 'summary.json')
identity = read(A / 'input_identity.json')
order = ['P2', 'P3', 'N2', 'hauer_real', 'hart_real']
assert summary['case_order'] == terminal['case_order'] == order
assert list(terminal['case_sha256']) == [x + '.json' for x in order]
cases = {}
details = []
for case_id in order:
    name = case_id + '.json'
    assert digest(A / name) == terminal['case_sha256'][name]
    c = read(A / name)
    cases[case_id] = c
    assert c['id'] == case_id and len(c['glyph']) == 87
    types = c['observed_types']
    assert len(types) <= 24 and types == sorted(set(types))
    pairs = c['pairs']
    keys = [tuple(p['pair']) for p in pairs]
    expected_keys = [(u, v) for i, u in enumerate(types) for v in types[i + 1:]]
    assert keys == expected_keys
    assert c['pair_count'] == len(pairs) <= 276
    assert c['compatible_count'] + c['incompatible_count'] == len(pairs)
    assert c['compatible_pairs'] == [p['pair'] for p in pairs if p['status'] == 'PAIR_NOT_REJECTED']
    assert c['automatic_compatible_pairs'] == [p['pair'] for p in pairs if p['automatic_both_singletons']]
    position_cells = 0
    for p in pairs:
        u, v = p['pair']
        pos, projection = p['original_positions_1based'], p['projection']
        assert pos == sorted(set(pos)) and len(pos) == len(projection) == sum(p['counts'])
        assert p['counts'] == [c['counts_by_type'][str(u)], c['counts_by_type'][str(v)]]
        assert all(1 <= i <= 87 and c['glyph'][i - 1] == g and g in (u, v) for i, g in zip(pos, projection))
        position_cells += len(pos)
        cert = p['first_violation']
        if cert is None:
            assert p['status'] == 'PAIR_NOT_REJECTED'
        else:
            assert p['status'] == 'PAIR_INCOMPATIBLE'
            j, k = cert['projection_positions_1based']
            assert k == j + 1
            assert cert['original_positions_1based'] == [pos[j - 1], pos[k - 1]]
            assert cert['glyphs'] == [projection[j - 1], projection[k - 1]]
            assert cert['glyphs'][0] == cert['glyphs'][1]
            assert cert['no_u_or_v_strictly_between'] is True
    if case_id in ('P2', 'P3'):
        rt = c['roundtrip']
        assert c['control_pass'] and c['control_graph_matches']
        assert c['compatible_pairs'] == c['expected_compatible_pairs']
        assert rt['decode_match_count'] == rt['encode_match_count'] == 87
        assert [r['position_1based'] for r in rt['records']] == list(range(1, 88))
        for r in rt['records']:
            i = r['position_1based'] - 1
            assert r['truth'] == rt['truth'][i] == r['decoded_letter']
            assert r['input_glyph'] == c['glyph'][i] == r['reencoded_glyph']
            assert r['decode_matches'] is True and r['encode_matches'] is True
    elif case_id == 'N2':
        assert c['control_pass'] and c['control_graph_matches']
        assert c['compatible_pairs'] == c['expected_compatible_pairs'] == []
        assert c['swap']['positions_1based'] == [3, 5]
        assert c['swap']['positions_0based'] == [2, 4]
        assert c['swap']['length_and_counts_preserved']
    else:
        record = next(r for r in identity['records'] if r['id'] == case_id)
        assert c['glyph'] == record['glyph']
        assert identity['glyph_strings'][case_id] == ','.join(map(str, c['glyph']))
        assert identity['positions_17_to_22_1based'][case_id] == c['glyph'][16:22] == [16, 16, 7, 14, 14, 16]
    details.append({'id': case_id, 'pair_records_read': len(pairs), 'projection_position_records_read': position_cells, 'sha256': digest(A / name)})

h, m = cases['hauer_real'], cases['hart_real']
differences = [{'position_1based': i, 'hauer': a, 'hart': b} for i, (a, b) in enumerate(zip(h['glyph'], m['glyph']), 1) if a != b]
stored_projection_differences = [a['pair'] for a, b in zip(h['pairs'], m['pairs']) if (a['projection'], a['original_positions_1based']) != (b['projection'], b['original_positions_1based'])]
stored_status_differences = [a['pair'] for a, b in zip(h['pairs'], m['pairs']) if a['status'] != b['status']]
report = {
    'status': 'READBACK_VERIFIED_COMPLETED_STRUCTURAL_DIAGNOSTIC',
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method': 'Read-only hash/schema/cross-reference verification of saved data; no import of runner, diagnostic, encoder, scorer or target procedure.',
    'scope_limit': 'First-violation selection/alternation rule verified in static code and fixed controls; readback does not rerun classification on ciphertext.',
    'observed_exit_code': raw['exit_code'], 'session_id_returned': False,
    'abort_absent': True, 'outer_observed_seconds': receipt['outer_observed_seconds'],
    'runner_elapsed_after_terminal_write_seconds': stdout['elapsed_after_terminal_write_seconds'],
    'terminal_sha256': stdout['terminal_sha256'], 'manifest_sha256': terminal['manifest_sha256'],
    'case_order': order, 'case_readback': details,
    'primary_symbol_inspections_saved': summary['primary_symbol_inspections'],
    'real_input_differences': differences,
    'saved_projection_difference_count': len(stored_projection_differences),
    'saved_projection_difference_pairs': stored_projection_differences,
    'saved_status_difference_pairs': stored_status_differences,
    'repeated_evidence_compatible_pair_records': {case_id: [p for p in cases[case_id]['pairs'] if p['status'] == 'PAIR_NOT_REJECTED' and not p['automatic_both_singletons']] for case_id in ('hauer_real', 'hart_real')},
}
with (BASE / 'readback.json').open('x') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2))
