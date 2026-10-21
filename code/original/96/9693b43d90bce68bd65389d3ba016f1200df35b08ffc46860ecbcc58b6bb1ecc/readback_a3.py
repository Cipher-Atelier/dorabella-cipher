"""Future saved-record readback only. No A3 module import or mathematical replay.

External receipt uses the A2 schema: raw_response, observer_start_utc,
observer_end_utc, observer_call_elapsed_seconds, command_request.
Do not execute during prospective preparation.
"""
import argparse
import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def raw(path, limit):
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, 'FILE_CAP:' + str(path))
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(root, receipt_path, manifest_pin):
    manifest_raw = raw(root / 'manifest.json', 65536)
    require(digest(manifest_raw) == manifest_pin, 'MANIFEST_HASH')
    manifest = json.loads(manifest_raw)
    require(manifest['version'] == 'A3-v1' and len(manifest['files']) <= 32, 'MANIFEST_VERSION_OR_COUNT')
    for name, pin in manifest['files'].items():
        path = root / name
        require(not path.is_symlink() and path.resolve().is_relative_to(root), 'UNSAFE_PATH')
        data = raw(path, 262144)
        require(len(data) == pin['bytes'] and digest(data) == pin['sha256'], 'SOURCE_HASH:' + name)
    receipt = json.loads(raw(receipt_path, 65536))
    response = receipt['raw_response']
    require(response.get('exit_code') == 0 and response.get('session_id') is None, 'OBSERVED_EXIT0_REQUIRED')
    stdout = json.loads(response['output'])
    require(stdout['status'] == 'COMPLETED_DIAGNOSTIC' and stdout['completed_cases'] == 18, 'STDOUT')
    require(0 <= receipt['observer_call_elapsed_seconds'] <= 30, 'EXTERNAL_TIME')
    require(0 <= response['wall_time_seconds'] <= 30 and 0 <= stdout['elapsed_seconds'] <= 30, 'EXECUTION_TIME')
    attempt = root / 'attempt_A3_v1'
    ids = ['fresh_' + str(i).zfill(2) for i in range(16)] + ['reg_march', 'reg_caractacus']
    require({p.name for p in attempt.iterdir()} ==
            {'STARTED.json', 'TERMINAL.json'} | {i + '.json' for i in ids}, 'ATTEMPT_FILE_SET_OR_ABORT')
    require(all(p.is_file() and not p.is_symlink() for p in attempt.iterdir()), 'ATTEMPT_FILE_TYPE')
    terminal_raw = raw(attempt / 'TERMINAL.json', 131072)
    tp = stdout['terminal']
    require(tp['file'] == 'TERMINAL.json' and len(terminal_raw) == tp['bytes'] and
            digest(terminal_raw) == tp['sha256'], 'TERMINAL_HASH')
    terminal = json.loads(terminal_raw)
    started = json.loads(raw(attempt / 'STARTED.json', 131072))
    require(started['attempt_id'] == terminal['attempt_id'] == 'A3-v1-once', 'ATTEMPT_ID')
    require(started['manifest_sha256'] == terminal['manifest_sha256'] == manifest_pin, 'MANIFEST_IDENTITY')
    require(started['review_v1_T0'] is None and terminal['review_v1_T0'] is None, 'OLD_T0')
    require(terminal['status'] == 'COMPLETED_DIAGNOSTIC' and terminal['completed_cases'] == 18, 'TERMINAL_STATUS')
    require([r['id'] for r in terminal['cases']] == ids, 'CASE_ID_ORDER')
    require(0 <= terminal['elapsed_seconds'] <= stdout['elapsed_seconds'] <= 30, 'TERMINAL_TIME')
    fresh_data = json.loads(raw(root / 'data/positive_source_prefixes.json', 65536))['new_candidates']
    old_data = json.loads(raw(root / 'data/regression_inputs_original.json', 262144))['sources']
    observed = []
    previous_elapsed = 0
    for index, pin in enumerate(terminal['cases']):
        case_id = ids[index]
        require(pin['file'] == case_id + '.json', 'CASE_FILENAME')
        data = raw(attempt / pin['file'], 131072)
        require(len(data) == pin['bytes'] and digest(data) == pin['sha256'], 'CASE_HASH:' + case_id)
        rec = json.loads(data)
        require(rec['id'] == case_id and rec['status'] == pin['status'], 'CASE_STATUS:' + case_id)
        require(previous_elapsed <= rec['elapsed_seconds'] <= terminal['elapsed_seconds'], 'CASE_TIME')
        previous_elapsed = rec['elapsed_seconds']
        expected_source = fresh_data[index] if index < 16 else old_data[index - 16]
        require(rec['source_record'] == expected_source and rec['plaintext'] == expected_source['plaintext'], 'FROZEN_TEXT')
        require(rec['regression'] == (index >= 16), 'REGRESSION_LABEL')
        require(rec['plaintext_sha256'] == digest(rec['plaintext'].encode('utf-8')), 'TEXT_HASH')
        require(rec['stratum'] == [rec['route'][f] for f in ('reset', 'inverse', 'reverse')], 'STRATUM')
        require(rec['q'] == rec['q_reference'] == rec['q_block'] and len(rec['q']) == 174, 'RECORDED_Q_COMPARATORS')
        order, dispositions = rec['missing_order'], rec['missing_dispositions']
        require(sorted(order) == list(range(25)) and [r['missing'] for r in dispositions] == order, 'MISSING_ORDER')
        require([r['missing'] for r in rec['assignment_hashes']['missing_order']] == order, 'HASH_ORDER_RECEIPT')
        if rec['status'] == 'ALPHABET_OUTSIDE':
            require(rec['domain']['status'] == 'ALPHABET_OUTSIDE' and rec['domain']['invalid'], 'ALPHABET_REASON')
            require(rec['M'] is None and rec['z'] is None and rec['Z'] is None and
                    rec['missing_fraction'] is None and rec['selected_missing'] is None, 'ALPHABET_NOT_EMPTY_M')
            require(all(d['representable_fixed_m'] is False and d['coordinate_condition'] is None and
                        d['reason'] == 'not_evaluated_invalid_alphabet' for d in dispositions), 'ALPHABET_DISPOSITIONS')
            require('glyphs' not in rec, 'NO_ENCODING_ON_ALPHABET_REFUSAL')
        else:
            require(rec['status'] in ('REPRESENTABLE', 'ROUTE_DOMAIN_OUTSIDE'), 'UNKNOWN_STATUS')
            require(rec['z'] == rec['domain']['z'] and len(rec['z']) == 87 and
                    rec['block_undo_digits'] == rec['domain']['d'], 'RECORDED_DOMAIN')
            require(rec['M'] == rec['domain']['available_missing'], 'RECORDED_M')
            require(rec['missing_fraction']['numerator'] == len(rec['M']) and
                    rec['missing_fraction']['denominator'] == 25, 'M_SHARE')
            eligible = [m for m in order if m in rec['M']]
            chosen = eligible[0] if eligible else None
            require(rec['selected_missing'] == chosen, 'CONDITIONAL_CHOICE')
            for d in dispositions:
                m = d['missing']
                require(d['positions'] == [i for i, cell in enumerate(rec['z']) if cell == m], 'OCCUPIED_POSITIONS')
                require(d['representable_fixed_m'] == d['coordinate_condition'] == (m in rec['M']) == (not d['positions']), 'FIXED_M_CONDITION')
            if rec['status'] == 'ROUTE_DOMAIN_OUTSIDE':
                require(rec['M'] == [] and chosen is None and 'glyphs' not in rec, 'EMPTY_M_REFUSAL')
            else:
                require(chosen is not None and rec['key']['missing'] == chosen, 'REPRESENTABLE_KEY')
                text, glyphs, inv = rec['plaintext'], rec['glyphs'], rec['inverse']
                require(len(text) == len(glyphs) == 87 and len(inv['positions']) == inv['verified_positions'] == 87, 'ALL87')
                require(rec['encoded']['status'] == rec['lookup_encoded']['status'] == 'ENCODED', 'ENCODER_STATUS')
                require(glyphs == rec['encoded']['glyphs'] == rec['lookup_encoded']['glyphs'] == inv['reencoded_glyphs'], 'GLYPH_IDENTITIES')
                require(rec['glyph_sha256'] == digest(bytes(glyphs)), 'GLYPH_HASH')
                require(text == rec['source_port_text'] == rec['reference_text'] == rec['block_oracle_text'], 'TEXT_IDENTITIES')
                require(rec['tables'][0] == rec['tables'][1] == rec['tables'][2], 'TABLE_IDENTITIES')
                for i, row in enumerate(inv['positions']):
                    require(row['position'] == i and row['ok'] is True, 'POSITION_OK')
                    require(row['plaintext'] == row['decoded'] == row['archived_decoded'] == text[i], 'POSITION_TEXT')
                    require(row['glyph'] == row['encoded_glyph'] == row['reencoded_glyph'] == glyphs[i], 'POSITION_GLYPH')
        observed.append({'id': case_id, 'status': rec['status'], 'regression': rec['regression'],
                         'stratum': rec['stratum'], 'file_sha256': digest(data)})
    summary = terminal['summary']
    require(summary['fresh_denominator'] == 16 and summary['regression_denominator'] == 2, 'DENOMINATORS')
    for status, count in summary['fresh_counts'].items():
        require(count == sum(r['status'] == status for r in observed[:16]), 'DESCRIPTIVE_COUNTS')
    require(sum(summary['fresh_counts'].values()) == 16, 'FULL_FRESH_ACCOUNTING')
    require(summary['regressions'] == [{'id': r['id'], 'status': r['status']} for r in observed[16:]], 'REGRESSION_ACCOUNTING')
    require(len(summary['strata']) == 8, 'STRATA_COUNT')
    for s in summary['strata']:
        group = [{'id': r['id'], 'status': r['status']} for r in observed[:16] if r['stratum'] == s['stratum']]
        require(s['denominator'] == len(group) == 2 and s['cases'] == group, 'STRATA_ACCOUNTING')
    return {'status': 'COMPLETED_DIAGNOSTIC', 'accepted_after_readback': True, 'cases': observed,
            'summary': summary, 'manifest_sha256': manifest_pin, 'terminal_sha256': digest(terminal_raw),
            'observed_exit_code': 0, 'abort_present': False, 'repeat_allowed': False,
            'meaning': '18-case domain accounting only; no sensitivity gate or next-stage authorization'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True)
    ap.add_argument('--receipt', required=True)
    ap.add_argument('--manifest-sha256', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    try:
        result = inspect(Path(args.root).resolve(), Path(args.receipt), args.manifest_sha256)
    except Exception as error:
        result = {'status': 'READBACK_INCOMPLETE_OR_UNKNOWN', 'error': str(error), 'repeat_allowed': False}
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
