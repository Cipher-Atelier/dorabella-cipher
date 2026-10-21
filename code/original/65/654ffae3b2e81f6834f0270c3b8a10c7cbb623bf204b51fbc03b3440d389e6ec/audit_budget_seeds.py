"""Additional mechanical audit after host interruption; no selection or search."""
from pathlib import Path
import json,hashlib,datetime
import numpy as np
R=Path(__file__).resolve().parents[1]
cases=json.loads((R/'inputs/cases.json').read_text());arch=json.loads((R/'inputs/archived_wordall_frozen.json').read_text())
route=json.loads((R/'inputs/archived_routes_inputs.json').read_text())['routes']
drop={'cases','null_calibration','regression_status'}
expected={k:v for k,v in arch['protocol'].items() if k not in drop}
tags={8:['routes_wordall_first_word'],32:['routes_wordall_middle_word0','routes_wordall_middle_word1'],128:['routes_wordall_final_word']}
configs={}
for p in (R/'archived_wordall').rglob('*.json'):
    z=json.loads(p.read_text())
    if isinstance(z,dict) and 'config' in z and 'seed' in z:configs[json.dumps(z['config'],sort_keys=True)]=z['config']
assert {c['restarts'] for c in configs.values()}=={8,32,128}
n=0
for c in cases:
    name=c['id'];d=R/'runs'/name;f=json.loads((d/'frozen.json').read_text())
    assert {k:v for k,v in f['protocol'].items() if k not in drop}==expected
    assert f['hashes']==arch['hashes'] and f['dictionary']['sha256']==arch['dictionary']['sha256']
    for stage in ['first','middle','final']:
        for p in (d/stage/name).glob('*.json'):
            z=json.loads(p.read_text());conf=json.dumps(z['config'],sort_keys=True);assert conf in configs
            bank={};a=[]
            for pos in route[int(p.stem)]['permutation']:
                v=c['glyph'][pos]
                if v not in bank:bank[v]=len(bank)
                a.append(bank[v])
            b=np.asarray(a,dtype='<i8').tobytes()
            allowed=[int.from_bytes(hashlib.sha256(b+(tag+conf).encode()).digest()[:4],'little') for tag in tags[z['config']['restarts']]]
            assert z['seed'] in allowed
            assert len(z['trace'])==z['config']['restarts']+1
            n+=1
events=[json.loads(s) for s in (R/'logs/events.jsonl').read_text().splitlines()]
start=next(datetime.datetime.fromisoformat(e['utc']) for e in events if e.get('event')=='calibration_started')
begin={e['case']:datetime.datetime.fromisoformat(e['utc']) for e in events if e.get('event')=='begin'}
complete=[e for e in events if e.get('event')=='complete'];assert len(complete)==len({e['case'] for e in complete})==52
elapsed={e['case']:(datetime.datetime.fromisoformat(e['utc'])-begin[e['case']]).total_seconds() for e in complete}
assert max(elapsed.values())<=901
status=json.loads((R/'STATUS.json').read_text());assert status['status']=='completed' and status['wall_seconds']<=10801
out={'status':'PASS','records_with_valid_original_seed_and_budget_config':n,'all52metadata_equal_archived_search_parameters':True,
     'max_case_elapsed_seconds_including_interruption':max(elapsed.values()),'original_total_wall_seconds':status['wall_seconds'],
     'allowance_note':'1s tolerance for log/postprocessing overhead only; all substantive search limits remain900/10800s',
     'physical_replay_note':'See recovery_accounting_note.json for bounded duplicated prefixes, no additional search trajectories'}
(R/'checks/budget_seed_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
