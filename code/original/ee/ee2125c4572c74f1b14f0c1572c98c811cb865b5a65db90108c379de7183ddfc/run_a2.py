"""Synchronous, one-attempt A2 only. Never run as part of static review.

No child processes, threads, signals, networking, install, resume or search.
30s cooperative deadline; no guarantee against a blocked syscall/host pause.
PASS_CANDIDATE needs observed exit0 and readback of all22 case hashes.
"""
import argparse
import hashlib
import importlib.util
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
        raise Deadline('A2_COOPERATIVE_30S_EXCEEDED')


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
    """Only three explicit new, hash-checked modules; never sources/fraction."""
    if name not in ('source_port', 'block_oracle', 'reference_frozen'):
        raise RuntimeError('MODULE_NOT_ALLOWED')
    spec = importlib.util.spec_from_file_location(name, root / 'code' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def glyph_vector(recipe):
    if recipe == 'cycle24':
        return [i % 24 for i in range(87)]
    if recipe == 'affine7_11':
        return [(7 * i + 11) % 24 for i in range(87)]
    if recipe == 'zeros':
        return [0] * 87
    raise RuntimeError('UNKNOWN_VECTOR_RECIPE')


def golden_text(name):
    if name == 'identity_first24':
        return ('abcdefghiklmnopqrstuvwxy' * 4)[:87]
    if name == 'reverse_shift1':
        return (('bcdefghiklmnopqrstuvwxyz' * 4)[:87])[::-1]
    if name == 'z87':
        return 'z' * 87
    if name is not None:
        raise RuntimeError('UNKNOWN_GOLDEN')
    return None


def positive_case(vector, port, ref, oracle, start):
    record = {'id': vector['id'], 'type': 'positive_synthetic', 'fixture': vector}
    key, route = vector['key'], vector['route']
    glyphs = glyph_vector(vector['glyph_recipe'])
    t1, t2, t3 = port.table_one(key), ref.table(key), oracle.coordinate_rows(key)
    q1, q2 = port.route_one(**route), ref.route(**route)
    q3 = oracle.forward_digits(list(range(174)), route)
    record.update(glyphs=glyphs, tables=[t1, t2, t3], routes=[q1, q2, q3])
    check(t1 == t2 == t3, 'TABLE_MISMATCH', record)
    check(q1 == q2 == q3 and sorted(q1) == list(range(174)), 'ROUTE_MISMATCH', record)
    check(sorted(5 * p[0] + p[1] for p in t1) ==
          [x for x in range(25) if x != key['missing']], 'TABLE_DOMAIN', record)
    tick(start)
    numeric = port.output_numeric(glyphs, t1, q1, 5)
    text1 = ''.join(ref.A25[x] for x in numeric)
    text2, text3 = ref.decode(glyphs, key, q2), oracle.decode(glyphs, key, route)
    record.update(source_port_text=text1, reference_text=text2, block_oracle_text=text3)
    check(len(text1) == 87 and text1 == text2 == text3, 'DECODE_MISMATCH', record)
    expected = golden_text(vector['golden'])
    record['golden_expected'] = expected
    check(expected is None or text1 == expected, 'GOLDEN_MISMATCH', record)
    encoded, lookup = ref.encode(text1, key, q1), oracle.encode(text1, key, route)
    record.update(reference_encoded=encoded, lookup_encoded=lookup)
    check(encoded['status'] == lookup['status'] == 'ENCODED', 'ENCODE_REFUSAL', record)
    check(encoded['glyphs'] == lookup['glyphs'] == glyphs, 'GLYPH_INVERSE_MISMATCH', record)
    tick(start)
    # Old verifier's archived_* field names are retained without pretending that
    # the supplied text was produced by the original NumPy/Numba runtime.
    record['verifier_comparator_kind'] = 'source_port_integer_only_NOT_archived_runtime'
    record['reference_verifier'] = ref.verify(text1, glyphs, key, q1, text1)
    check(record['reference_verifier']['verified_positions'] == 87 and
          all(z['ok'] for z in record['reference_verifier']['positions']), 'VERIFIER_MISMATCH', record)
    record['status'] = 'PASS'
    return record


def missing_case(vector, route, port, ref, oracle, start):
    key = dict(sign=1, rot=0, arcs=[0, 1, 2], layout=0, missing=vector['missing'])
    z = [vector['background_cell']] * 87
    z[vector['bad_position']] = vector['missing']
    digits = [v for cell in z for v in divmod(cell, 5)]
    q = port.route_one(**route)
    output = [digits[j] for j in q]
    other_output = oracle.forward_digits(digits, route)
    text = ''.join(ref.A25[5 * output[2 * i] + output[2 * i + 1]] for i in range(87))
    record = {'id': vector['id'], 'type': 'outside_domain_synthetic', 'fixture': vector,
              'key': key, 'route': route, 'q': q, 'z': z, 'digits': digits,
              'output_digits': output, 'block_output_digits': other_output, 'plaintext': text}
    check(output == other_output, 'INVALID_FIXTURE_ROUTE_MISMATCH', record)
    tick(start)
    result, other = ref.encode(text, key, q), oracle.encode(text, key, route)
    record.update(reference=result, block_oracle=other)
    check(result['status'] == other['status'] == 'OUTSIDE_DOMAIN', 'MISSING_NOT_REJECTED', record)
    check(result['missing_positions'] == other['missing_positions'] == [42],
          'MISSING_POSITIONS_MISMATCH', record)
    check(result['z'] == z, 'UNDO_ROUTE_MISMATCH', record)
    record['status'] = 'PASS'
    return record


def invalid_case(name, ref):
    """Validation contract of reference_frozen only; not original invalid behavior."""
    key = dict(sign=1, rot=0, arcs=[0, 1, 2], layout=0, missing=24)
    q, glyphs = list(range(174)), [0] * 87
    record = {'id': name, 'type': 'reference_invalid_input', 'key': key, 'q': q}
    if name in ('text86', 'text88', 'text_j87'):
        text = {'text86': 'a' * 86, 'text88': 'a' * 88, 'text_j87': 'j' + 'a' * 86}[name]
        result = ref.encode(text, key, q)
        expected = 'ALPHABET_OUTSIDE' if name == 'text_j87' else 'LENGTH_OUTSIDE'
        record.update(plaintext=text, result=result, expected_status=expected)
        check(result['status'] == expected, 'INVALID_TEXT_STATUS', record)
        if name == 'text_j87':
            check(result['invalid'] == [{'position': 0, 'character': 'j'}], 'INVALID_J_POSITION', record)
    else:
        if name == 'glyph86':
            glyphs = [0] * 86
        elif name == 'glyph88':
            glyphs = [0] * 88
        elif name == 'glyph24':
            glyphs[42] = 24
        elif name == 'route_duplicate':
            q[173] = q[0]
        elif name == 'arcs_duplicate':
            key['arcs'] = [0, 0, 2]
        else:
            raise RuntimeError('UNKNOWN_INVALID_FIXTURE')
        expected = {'route_duplicate': 'NOT_A_PERMUTATION', 'arcs_duplicate': 'ARCS'}.get(name, 'GLYPHS')
        record.update(glyphs=glyphs, expected_error=expected)
        try:
            returned = ref.decode(glyphs, key, q)
        except ValueError as error:
            record['error'] = str(error)
            check(str(error) == expected, 'WRONG_INVALID_EXCEPTION', record)
        else:
            record['unexpected_return'] = returned
            raise Mismatch('INVALID_INPUT_ACCEPTED', record)
    record['status'] = 'PASS'
    return record


def main():
    start = time.monotonic()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-A2-v1', action='store_true')
    ap.add_argument('--manifest-sha256', required=True)
    args = ap.parse_args()
    if not args.execute_A2_v1:
        print('NOT_STARTED: explicit readback authorization and execute flag required')
        return 2
    root = Path(__file__).resolve().parents[1]
    attempt = root / 'attempt_A2_v1'
    # Fixed single-attempt location. Existing directory means refusal, never resume.
    try:
        attempt.mkdir(exist_ok=False)
    except FileExistsError:
        print('REFUSE_REPEAT_OR_RESUME: attempt_A2_v1 exists')
        return 2
    records = []
    current_id = None
    try:
        sys.dont_write_bytecode = True
        write_new(attempt / 'STARTED.json', {'status': 'RUNNING', 'attempt_id': 'A2-v1-once',
                  'A2_start_monotonic': start, 'A2_start_utc_unix': time.time(), 'pid': os.getpid(),
                  'manifest_sha256': args.manifest_sha256, 'review_v1_T0': None,
                  'cooperative_seconds': 30, 'python': sys.version, 'executable': sys.executable})
        raw = limited_read(root / 'manifest.json', 65536)
        if digest(raw) != args.manifest_sha256:
            raise RuntimeError('MANIFEST_HASH_MISMATCH')
        manifest = json.loads(raw)
        if manifest['version'] != 'A2-v1' or not sys.flags.isolated or not sys.flags.no_site:
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
        vectors = json.loads(limited_read(root / 'vectors.json', 65536))
        if (len(vectors['positive']), len(vectors['missing']), len(vectors['invalid'])) != (11, 3, 8):
            raise RuntimeError('FIXTURE_COUNT_MISMATCH')
        port = frozen_module(root, 'source_port')
        ref = frozen_module(root, 'reference_frozen')
        oracle = frozen_module(root, 'block_oracle')
        tasks = ([('positive', v) for v in vectors['positive']] +
                 [('missing', v) for v in vectors['missing']] +
                 [('invalid', v) for v in vectors['invalid']])
        for kind, vector in tasks:
            tick(start)
            current_id = vector if kind == 'invalid' else vector['id']
            if kind == 'positive':
                record = positive_case(vector, port, ref, oracle, start)
            elif kind == 'missing':
                record = missing_case(vector, vectors['missing_route'], port, ref, oracle, start)
            else:
                record = invalid_case(vector, ref)
            tick(start)
            record['elapsed_seconds'] = time.monotonic() - start
            pin = write_new(attempt / (current_id + '.json'), record)
            records.append({'id': current_id, 'status': record['status'], **pin})
            tick(start)
        if len(records) != 22 or any(r['status'] != 'PASS' for r in records):
            raise RuntimeError('INCOMPLETE_CASE_SET')
        terminal = {'status': 'PASS_CANDIDATE', 'attempt_id': 'A2-v1-once',
                    'manifest_sha256': args.manifest_sha256, 'cases': records,
                    'completed_cases': 22, 'elapsed_seconds': time.monotonic() - start,
                    'review_v1_T0': None, 'scope': 'A2 integer vectors only; not G0/G1/scorer sensitivity',
                    'requires': 'observed exit0 + complete hash readback + no ABORT + elapsed within30s'}
        tick(start)
        receipt = write_new(attempt / 'TERMINAL.json', terminal)
        tick(start)
        print(json.dumps({'status': 'PASS_CANDIDATE', 'terminal': receipt,
                          'completed_cases': 22, 'elapsed_seconds': time.monotonic() - start}), flush=True)
        tick(start)
        return 0
    except BaseException as error:
        status = 'FAIL' if isinstance(error, Mismatch) else 'INCOMPLETE'
        abort = {'status': status, 'current_id': current_id, 'completed_cases': records,
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
