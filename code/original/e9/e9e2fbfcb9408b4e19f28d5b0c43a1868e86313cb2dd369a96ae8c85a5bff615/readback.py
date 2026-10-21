"""Read-only verification of saved CH3 data. Never imports runner or model."""
from pathlib import Path
import collections
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'attempt'


def load(p):
    return json.loads(p.read_text())


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_inverse(record, text, glyphs, key):
    assert record['matched'] == 87
    assert record['recovered_plaintext87'] == text
    assert record['reencoded_glyphs87'] == glyphs
    positions = record['positions']
    assert len(positions) == len(text) == len(glyphs) == 87
    # Validate the saved positional witness, without calling an encoder/scorer.
    visits = collections.Counter()
    for i, row in enumerate(positions):
        letter = text[i]
        assert row['position1'] == i + 1
        assert row['letter'] == row['decoded_letter'] == letter
        assert row['glyph'] == row['reencoded_glyph'] == glyphs[i]
        assert row['match'] is True
        assert row['cycle'] == key[letter]
        assert row['visit0'] == visits[letter]
        assert row['cycle'][row['visit0'] % len(row['cycle'])] == glyphs[i]
        visits[letter] += 1


def main():
    freeze = load(ROOT / 'FREEZE_MANIFEST.json')
    for name, info in freeze['files'].items():
        assert digest(ROOT / name) == info['sha256']
    terminal = load(OUT / 'terminal.json')
    for name, sha in terminal['files_sha256'].items():
        assert digest(OUT / name) == sha
    raw = load(ROOT / 'raw_execution_receipt.json')
    assert raw['observed_exit_code'] == 0
    assert len(raw['observations']) == 2
    assert raw['observations'][0]['tool'] == 'exec_command'
    session = raw['observations'][0]['result']['session_id']
    assert raw['observations'][1]['session_id'] == session
    assert raw['observations'][1]['result']['exit_code'] == 0
    events = [json.loads(line) for obs in raw['observations'] for line in obs['result']['output'].splitlines() if line]
    assert sum(e['event'] == 'START' for e in events) == 1
    assert sum(e['event'] == 'TERMINAL' for e in events) == 1
    assert not any('ABORT' in e['event'] for e in events)
    assert events[-1]['terminal_sha256'] == digest(OUT / 'terminal.json')
    assert terminal['status'] == 'COMPLETED_EXPLORATORY' and terminal['intended_exit_code'] == 0
    assert terminal['budget']['elapsed_seconds'] < 180
    inputs = load(OUT / 'decoder_inputs.json')
    expected_ids = ['P01','P02','P03','P04','N01','N02','N03','N04','hauer_real','hart_real']
    assert [r['id'] for r in inputs] == expected_ids
    glyph_by_id = {r['id']:r['glyph'] for r in inputs}
    source = load(ROOT / 'frozen/search_inputs.json')
    for case_id in expected_ids[-2:]:
        assert glyph_by_id[case_id] == next(r['glyph'] for r in source if r['id'] == case_id)
    private = load(OUT / 'private_control_truth.json')
    for r in private:
        assert r['status'] == 'REPRESENTABLE'
        assert hashlib.sha256(r['plaintext87'].encode('ascii')).hexdigest() == r['plaintext_sha256']
        check_inverse(r['positive_inverse'],r['plaintext87'],r['positive_glyphs87'],r['key'])
        check_inverse(r['negative_inverse'],r['negative_plaintext87'],r['negative_glyphs87'],r['key'])
    branches=[];restarts=[];case_rows=[]
    for case_id in expected_ids:
        for branch in ['B0','B1','B2','B3']:
            b = load(OUT / 'branches' / (case_id+'_'+branch+'.json'))
            branches.append(b)
            assert b['elapsed_seconds'] < 4
            if b['status'] == 'STRUCTURAL_REJECT':
                assert any(x['violations'] for x in b['structural'])
                assert not b['restarts']
                continue
            assert b['status'] == 'COMPLETE' and [x['r'] for x in b['restarts']] == list(range(5))
            assert not any(x['violations'] for x in b['structural'])
            for item in b['restarts']:
                f=OUT/item['file'];assert digest(f)==item['sha256']
                r=load(f);restarts.append(r);c=r['candidate']
                assert sorted(c['key26'])==list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                assert len(c['plaintext87'])==87
                assert r['proposals']<=5000
                assert r['reason'] in ['COUNT_1000','PROPOSAL_CAP']
                if r['reason']=='COUNT_1000':assert r['count']==1000
                else:assert r['proposals']==5000
                key={x['letter']:x['cycle'] for x in c['class_table']}
                assert len(key)==len(c['class_table'])
                assert sorted(g for cycle in key.values() for g in cycle)==list(range(24))
                assert ''.join(x['letter'] for x in c['class_table'])==c['key26'][:len(key)]
                check_inverse(c['inverse'],c['plaintext87'],glyph_by_id[case_id],key)
        aggregate=load(OUT/'cases'/(case_id+'.json'))
        assert aggregate['distinct_count']==len({r['plaintext87'] for r in aggregate['ranked']})
        assert aggregate['ranked']==sorted(aggregate['ranked'],key=lambda r:(-r['score'],r['plaintext87']))
        for row in aggregate['ranked']:
            for origin in row['origins']:
                c=load(OUT/origin['file'])['candidate']
                assert row['plaintext87']==c['plaintext87'] and row['score']==c['score']
        case_rows.append({'id':case_id,'distinct':aggregate['distinct_count'],'best':aggregate['ranked'][0]})
    assert len(branches)==40 and len(events)==43
    proposals=sum(r['proposals'] for r in restarts)
    assert proposals==terminal['budget']['proposals']<=1000000
    assert len(restarts)==terminal['budget']['initial_scores']<=200
    assert terminal['budget']['truth_scores']==4
    assessment=load(OUT/'postsearch_assessment.json')
    for row in assessment['positive']:
        p=next(x['plaintext87'] for x in private if x['id']==row['id'])
        a=load(OUT/'cases'/(row['id']+'.json'))
        assert row['exact_top']==(p in a['top_tied_strings'])
        assert row['exact_any_retained']==any(p==x['plaintext87'] for x in a['ranked'])
    for row in assessment['negative']:
        assert row['reached_paired_truth_score']==(row['best_score']>=row['paired_truth_score'])
    result={'status':'READBACK_VERIFIED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'runner_or_score_imported':False,'search_repeated':False,'score_recomputed':False,
            'observed_exit':0,'session_id':session,'raw_start_utc':raw['observation_start_utc'],
            'raw_end_utc':raw['observation_end_utc'],'T0_utc':terminal['T0_utc'],'terminal_end_utc':terminal['ended_utc'],
            'terminal_sha256':digest(OUT/'terminal.json'),'hash_checked_attempt_files':len(terminal['files_sha256']),
            'branch_status_counts':dict(collections.Counter(b['status'] for b in branches)),
            'restart_stop_counts':dict(collections.Counter(r['reason'] for r in restarts)),
            'completed_starts':len(restarts),'proposals':proposals,'max_branch_seconds':max(b['elapsed_seconds'] for b in branches),
            'elapsed_seconds':terminal['budget']['elapsed_seconds'],'candidate_inverse_records':len(restarts),
            'control_inverse_records':len(private)*2,'case_summaries':case_rows,
            'assessment':assessment}
    with (ROOT/'readback_result.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['case_summaries','assessment']},indent=2))


if __name__=='__main__':main()
