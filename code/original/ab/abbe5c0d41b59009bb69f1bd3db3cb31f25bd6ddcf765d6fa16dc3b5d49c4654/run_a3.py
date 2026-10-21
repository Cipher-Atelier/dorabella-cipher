"""A3-v1: one synchronous representability diagnostic. Do not execute before readback.
No scoring, banks, target data, background jobs, resume or automatic retry.
"""
import argparse
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
import time


class Deadline(Exception):
    pass


class Mismatch(Exception):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def check(condition, message, record):
    if not condition:
        raise Mismatch(message, record)


def tick(start):
    if time.monotonic() - start > 30.0:
        raise Deadline('A3_COOPERATIVE_30S_EXCEEDED')


def limited_read(path, cap):
    with Path(path).open('rb') as stream:
        data = stream.read(cap + 1)
    if len(data) > cap:
        raise RuntimeError('FILE_SIZE_CAP')
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def interpreter_digest(path, start):
    """At most128MiB; finite file-read loop, no package imports."""
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for _ in range(128):
            tick(start)
            block = stream.read(1024 * 1024)
            if not block:
                return h.hexdigest()
            h.update(block)
        if stream.read(1):
            raise RuntimeError('INTERPRETER_SIZE_CAP')
    return h.hexdigest()


def write_new(path, value):
    """Best-effort local checkpoint; no host-crash durability claim."""
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False) + '\n').encode('utf-8')
    if len(raw) > 131072:
        raise RuntimeError('RECORD_SIZE_CAP')
    path = Path(path)
    if path.exists():
        raise RuntimeError('REFUSE_OVERWRITE')
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'file': path.name, 'sha256': digest(raw), 'bytes': len(raw)}


def frozen_module(root, name):
    if name not in ('source_port', 'reference_frozen', 'block_oracle', 'assignment_frozen'):
        raise RuntimeError('MODULE_NOT_ALLOWED')
    spec = importlib.util.spec_from_file_location(name, root / 'code' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidates(fresh_data, regression_data):
    """Same source order and route rule as driver_review1.py:171–187.

    Only called inside the one attempt. Normalization is checked, never substituted.
    Old regression ciphertexts/null cases are not read as scientific inputs.
    """
    fresh = fresh_data['new_candidates']
    check(len(fresh) == 16 and [z['id'] for z in fresh] ==
          ['fresh_' + str(i).zfill(2) for i in range(16)], 'FRESH_IDS', {'phase': 'inputs'})
    params = list(itertools.product((5, 17), (0, 1), (0, 1), (0, 1)))
    answer = []
    for z, values in zip(fresh, params):
        text, raw = z['plaintext'], z['raw_prefix']
        check(digest(text.encode('utf-8')) == z['plaintext_sha256'] and
              digest(raw.encode('utf-8')) == z['raw_prefix_sha256'], 'TEXT_SHA', z)
        normalized = ''.join(c for c in raw.lower() if 'a' <= c <= 'z')[:87]
        check(text == normalized and len(text) == 87, 'FROZEN_NORMALIZATION_OR_LENGTH', z)
        answer.append({'id': z['id'], 'plaintext': text, 'regression': False,
                       'route': dict(zip(('period', 'reset', 'inverse', 'reverse'), values)),
                       'source_record': z, 'source_file': 'data/positive_source_prefixes.json'})
    old = regression_data['sources']
    check(len(old) >= 2, 'REGRESSION_SOURCE_COUNT', {'phase': 'inputs'})
    for index, case_id, values in ((0, 'reg_march', (5, 0, 0, 0)),
                                   (1, 'reg_caractacus', (17, 1, 1, 1))):
        text = old[index]['plaintext']
        check(isinstance(text, str) and len(text) == 87, 'REGRESSION_LENGTH', old[index])
        answer.append({'id': case_id, 'plaintext': text, 'regression': True,
                       'route': dict(zip(('period', 'reset', 'inverse', 'reverse'), values)),
                       'source_record': old[index], 'source_index': index,
                       'source_file': 'data/regression_inputs_original.json'})
    check(len(answer) == 18, 'CASE_COUNT', {'phase': 'inputs'})
    return answer


def diagnose(candidate, assignment, port, ref, oracle, start):
    key, missing_order, assignment_audit = assignment.control_assignment(candidate['id'])
    route = candidate['route']
    q = port.route_one(**route)
    q_ref = ref.route(**route)
    q_block = oracle.forward_digits(list(range(174)), route)
    text = candidate['plaintext']
    record = {**candidate, 'plaintext_sha256': digest(text.encode('utf-8')),
              'key_without_missing': key, 'assignment_hashes': assignment_audit,
              'missing_order': missing_order, 'q': q, 'q_reference': q_ref, 'q_block': q_block,
              'stratum': [route[f] for f in ('reset', 'inverse', 'reverse')],
              'selection_rule': 'First missing in original hash-order absent from z; CONDITIONAL, not an independent key',
              'z': None, 'Z': None, 'M': None, 'missing_fraction': None, 'selected_missing': None}
    check(q == q_ref == q_block and sorted(q) == list(range(174)), 'ROUTE_COMPARATOR_MISMATCH', record)
    check(sorted(missing_order) == list(range(25)), 'MISSING_ORDER_NOT_PERMUTATION', record)
    tick(start)
    domain = ref.undo_route(text, q)
    record['domain'] = domain
    if domain['status'] == 'ALPHABET_OUTSIDE':
        record.update(status='ALPHABET_OUTSIDE', missing_dispositions=[
            {'missing': m, 'representable_fixed_m': False, 'coordinate_condition': None,
             'reason': 'not_evaluated_invalid_alphabet', 'positions': None} for m in missing_order])
        return record
    check(domain['status'] == 'VALID_COORDINATES', 'UNEXPECTED_INPUT_DOMAIN_STATUS', record)
    z = domain['z']
    block_d = oracle.backward_digits(domain['e'], route)
    record['block_undo_digits'] = block_d
    check(len(z) == 87 and block_d == domain['d'], 'UNDO_ROUTE_COMPARATOR_MISMATCH', record)
    occupied = sorted(set(z))
    available = sorted(set(range(25)) - set(z))
    check(available == domain['available_missing'], 'M_SET_MISMATCH', record)
    eligible = [m for m in missing_order if m in available]
    chosen = eligible[0] if eligible else None
    record.update(z=z, Z=occupied, M=available,
                  missing_fraction={'numerator': len(available), 'denominator': 25,
                                    'meaning': 'allowed missing share for this text/q only'},
                  selected_missing=chosen,
                  missing_dispositions=[
                      {'missing': m, 'representable_fixed_m': m in available,
                       'coordinate_condition': m not in z,
                       'reason': 'occupied' if m not in available else
                                 ('selected' if m == chosen else 'available_not_selected'),
                       'positions': [i for i, cell in enumerate(z) if cell == m]}
                      for m in missing_order])
    if chosen is None:
        record['status'] = 'ROUTE_DOMAIN_OUTSIDE'
        return record
    tick(start)
    full_key = {**key, 'missing': chosen}
    encoded = ref.encode(text, full_key, q)
    lookup = oracle.encode(text, full_key, route)
    record.update(key=full_key, encoded=encoded, lookup_encoded=lookup)
    check(encoded['status'] == lookup['status'] == 'ENCODED', 'ENCODER_DOMAIN_INCONSISTENCY', record)
    glyphs = encoded['glyphs']
    record.update(glyphs=glyphs, glyph_sha256=digest(bytes(glyphs)))
    check(len(glyphs) == 87 and glyphs == lookup['glyphs'], 'ENCODER_COMPARATOR_MISMATCH', record)
    t1, t2, t3 = port.table_one(full_key), ref.table(full_key), oracle.coordinate_rows(full_key)
    record['tables'] = [t1, t2, t3]
    check(t1 == t2 == t3, 'TABLE_COMPARATOR_MISMATCH', record)
    numeric = port.output_numeric(glyphs, t1, q, 5)
    port_text = ''.join(ref.A25[x] for x in numeric)
    ref_text, block_text = ref.decode(glyphs, full_key, q), oracle.decode(glyphs, full_key, route)
    record.update(source_port_text=port_text, reference_text=ref_text, block_oracle_text=block_text)
    check(port_text == ref_text == block_text == text, 'DECODE_COMPARATOR_MISMATCH', record)
    inverse = ref.verify(text, glyphs, full_key, q, port_text)
    record.update(inverse=inverse, verifier_comparator_kind='source_port_integer_only_NOT_archived_runtime')
    check(inverse['verified_positions'] == 87 and all(row['ok'] for row in inverse['positions']),
          'FULL_INVERSE_MISMATCH', record)
    record['status'] = 'REPRESENTABLE'
    tick(start)
    return record


def descriptive_summary(records):
    """Accounting only: no >=14 criterion, no sensitivity or model-success gate."""
    statuses = ('REPRESENTABLE', 'ALPHABET_OUTSIDE', 'ROUTE_DOMAIN_OUTSIDE')
    fresh = [r for r in records if not r['regression']]
    regressions = [r for r in records if r['regression']]
    check(len(fresh) == 16 and len(regressions) == 2, 'FINAL_ACCOUNTING', {'records': records})
    strata = []
    for s in itertools.product((0, 1), repeat=3):
        group = [r for r in fresh if r['stratum'] == list(s)]
        strata.append({'stratum': list(s), 'denominator': len(group),
                       'cases': [{'id': r['id'], 'status': r['status']} for r in group]})
    return {'fresh_denominator': 16,
            'fresh_counts': {s: sum(r['status'] == s for r in fresh) for s in statuses},
            'strata': strata, 'regression_denominator': 2,
            'regressions': [{'id': r['id'], 'status': r['status']} for r in regressions],
            'interpretation': 'Descriptive domain accounting; not G1 or14/16 sensitivity gate'}


def main():
    start = time.monotonic()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-A3-v1', action='store_true')
    ap.add_argument('--manifest-sha256', required=True)
    args = ap.parse_args()
    if not args.execute_A3_v1:
        print('NOT_STARTED: external readback and explicit authorization required')
        return 2
    root = Path(__file__).resolve().parents[1]
    attempt = root / 'attempt_A3_v1'
    try:
        attempt.mkdir(exist_ok=False)
    except FileExistsError:
        print('REFUSE_REPEAT_OR_RESUME: attempt_A3_v1 exists')
        return 2
    receipts, accounting = [], []
    current_id = None
    try:
        sys.dont_write_bytecode = True
        write_new(attempt / 'STARTED.json', {'status': 'RUNNING', 'attempt_id': 'A3-v1-once',
                  'A3_start_monotonic': start, 'A3_start_utc_unix': time.time(), 'pid': os.getpid(),
                  'manifest_sha256': args.manifest_sha256, 'review_v1_T0': None,
                  'cooperative_seconds': 30, 'python': sys.version, 'executable': sys.executable})
        raw = limited_read(root / 'manifest.json', 65536)
        if digest(raw) != args.manifest_sha256:
            raise RuntimeError('MANIFEST_HASH_MISMATCH')
        manifest = json.loads(raw)
        if manifest['version'] != 'A3-v1' or not sys.flags.isolated or not sys.flags.no_site:
            raise RuntimeError('VERSION_OR_ISOLATION_FLAGS')
        if tuple(sys.version_info[:3]) != (3, 12, 14):
            raise RuntimeError('PYTHON_VERSION_MISMATCH_NO_SUBSTITUTION')
        if interpreter_digest(sys.executable, start) != manifest['runtime']['python_binary_sha256']:
            raise RuntimeError('PYTHON_BINARY_MISMATCH')
        if len(manifest['files']) > 32:
            raise RuntimeError('FILE_COUNT_CAP')
        for name, pin in manifest['files'].items():
            tick(start)
            path = root / name
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise RuntimeError('UNSAFE_PATH')
            data = limited_read(path, 262144)
            if len(data) != pin['bytes'] or digest(data) != pin['sha256']:
                raise RuntimeError('FILE_HASH_MISMATCH:' + name)
        port, ref, oracle, assignment = [frozen_module(root, name) for name in
            ('source_port', 'reference_frozen', 'block_oracle', 'assignment_frozen')]
        fresh = json.loads(limited_read(root / 'data/positive_source_prefixes.json', 65536))
        old = json.loads(limited_read(root / 'data/regression_inputs_original.json', 262144))
        for candidate in candidates(fresh, old):
            tick(start)
            current_id = candidate['id']
            record = diagnose(candidate, assignment, port, ref, oracle, start)
            tick(start)
            check(record['status'] in ('REPRESENTABLE', 'ALPHABET_OUTSIDE', 'ROUTE_DOMAIN_OUTSIDE'),
                  'NONDIAGNOSTIC_STATUS', record)
            record['elapsed_seconds'] = time.monotonic() - start
            pin = write_new(attempt / (current_id + '.json'), record)
            receipts.append({'id': current_id, 'status': record['status'], **pin})
            accounting.append({k: record[k] for k in ('id', 'status', 'regression', 'stratum')})
            tick(start)
        check(len(receipts) == 18, 'INCOMPLETE_CASE_SET', {'receipts': receipts})
        summary = descriptive_summary(accounting)
        terminal = {'status': 'COMPLETED_DIAGNOSTIC', 'requires_external_acceptance': True,
                    'attempt_id': 'A3-v1-once', 'manifest_sha256': args.manifest_sha256,
                    'cases': receipts, 'completed_cases': 18, 'summary': summary,
                    'elapsed_seconds': time.monotonic() - start, 'review_v1_T0': None,
                    'scope': 'A3 domain diagnostic only; no sensitivity or G1 claim',
                    'requires': 'observed exit0 +18 complete hash readbacks + no ABORT + elapsed within30s'}
        tick(start)
        receipt = write_new(attempt / 'TERMINAL.json', terminal)
        tick(start)
        print(json.dumps({'status': 'COMPLETED_DIAGNOSTIC', 'requires_external_acceptance': True,
                          'terminal': receipt, 'completed_cases': 18,
                          'elapsed_seconds': time.monotonic() - start}), flush=True)
        tick(start)
        return 0
    except BaseException as error:
        status = 'STOP' if isinstance(error, Mismatch) else 'INCOMPLETE'
        abort = {'status': status, 'current_id': current_id, 'completed_cases': receipts,
                 'error_type': type(error).__name__, 'error': str(error)[:1000],
                 'elapsed_seconds': time.monotonic() - start, 'repeat_allowed': False}
        if isinstance(error, Mismatch):
            abort['failed_observation'] = error.record
        try:
            write_new(attempt / 'ABORT.json', abort)
        except BaseException:
            print('UNKNOWN: could not save ABORT; no repeat', flush=True)
            return 3
        print(json.dumps({'status': status, 'error': str(error)[:1000], 'repeat_allowed': False}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
