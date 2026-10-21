"""Build a transparent audit readout. Does not perform or claim new key searches.
Run after the logged verification and reproduce.py calls, with --root if needed.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, datetime, sys
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--root',default='/mnt/data/dorabella_audit_20261002');args=ap.parse_args()
R=Path(args.root).resolve();H=R/'work/dorabella_lab/round11';S=R/'restored'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
# These three destinations were printed by the three real fresh calls in this turn.
fresh_names=['fresh-zacn0bmn','fresh-nd8byrwh','fresh-__1l3p_l']
repeats=[];repeat_records=[]
for n in fresh_names:
 folder=H/'audit/reproductions'/n
 validated=load(folder/'verified.json')
 for item in validated:
  name=item['case'];tr=load(folder/name/'training_result.json');old=load(H/'checkpoints'/name/'training_result.json')
  assert tr['status']=='complete' and tr['keys']==30965760
  for k in ['train_score','key_id','exact_tie_ids','word_evaluations']:
   assert tr[k]==old[k],(name,k)
  for i in range(40):
   x=load(folder/name/f'block_{i:03d}.json');y=load(H/'checkpoints'/name/f'block_{i:03d}.json')
   assert x['array_sha256']==y['array_sha256']
  repeats.append(name)
  repeat_records.append({'case':name,'directory':str(folder/name),'key_id':tr['key_id'],
   'train_score':tr['train_score'],'exact_tie_ids':tr['exact_tie_ids'],
   'word_evaluations':tr['word_evaluations'],'all40_arrays_identical':True,
   'key_space_searched':tr['keys'],'sum_block_elapsed_seconds':tr['cpu_work_seconds_sum'],
   'execution_start_utc':tr['execution_start_utc'],'completed_utc':tr['completed_utc']})
assert len(repeats)==len(set(repeats))==18
cases=load(H/'data/cases.json');records=[load(H/'results'/f"{c['id']}.json") for c in cases]
# Independently re-check root -> replica seed, beyond the archived verifier's per-seed replay.
for c in cases:
 if c['kind']=='null':
  expected=int(np.random.SeedSequence([202610011102,c['replicate']]).generate_state(1,dtype=np.uint64)[0])
  assert c['seed']==expected
primary=[r for r in records if r['kind']=='positive'];reg=[r for r in records if r['kind']=='regression']
comparison=[]
for name in ['hauer_real','hart_real']:
 real=next(r for r in records if r['id']==name)
 null=[r for r in records if r['kind']=='null' and r['source']==name]
 assert len(null)==39
 k=sum(r['test_score']>=real['test_score']-1e-10 for r in null)
 comparison.append({'transcription':name,'S43':real['train_score'],'S44':real['test_score'],
  'key_id':real['key_id'],'null_test_ge':k,'null_count':39,'tail_plus1':(k+1)/40,
  'null_train_ge':sum(r['train_score']>=real['train_score']-1e-10 for r in null)})
# Check original extracted source, and unchanged round1-10 files in work, after all calculations.
archives=load(R/'archive_manifest.json');untouched=0
for archive,d in archives.items():
 for n,h in d['file_hashes'].items():
  assert sha(S/n)==h,('original copy modified',n);untouched+=1
for n,h in archives['dorabella_lab_round10.zip']['file_hashes'].items():
 assert sha(R/'work'/n)==h,('old work file modified',n)
ver=load(H/'audit/latest_verification.json');assert ver['status']=='passed' and ver['cases_verified']==94
positive_summary={'texts':12,'exact_prefixes':sum(r['train_correct']==43 for r in primary),
 'exact_selected_suffixes':sum(r['test_correct']==44 for r in primary),
 'correct_suffix_letters':sum(r['test_correct'] for r in primary),'total_suffix_letters':12*44,
 'all_tied_keys_agree_on_correct_suffix':sum(r['test_correct']==44 and r['distinct_suffixes_among_exact_training_ties']==1 for r in primary),
 'status':'Previously used, related convenience sample; not fresh independent historical validation.'}
summary={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'activity':'Audit and fresh replication of existing round11, not a new hypothesis round',
 'integrity':load(R/'integrity_audit.json'),
 'current_verification':{'cases':94,'checkpoint_blocks':3760,
 'stored_C_scores_independently_recomputed':sum(r['independently_verified_sparse_C'] for r in records),
 'python_word_score_checks':sum(r['python_word_checks'] for r in records),
 'max_score_error':ver['max_independent_score_error'],
 'sample_unpruned_keys':sum(r['keys_bruteforce'] for r in load(H/'audit/brute_sample_blocks.json')),
 'root_to_replica_seeds_checked':78,'all_87_symbols_reverse_encoded_for_each_case':True},
 'fresh_repeated_searches':repeat_records,'fresh_repeated_count':18,'fresh_repeated_blocks':18*40,
 'fresh_C_key_input_evaluations':18*30965760,
 'fresh_full_W_evaluations':sum(r['word_evaluations'] for r in repeat_records),
 'full_searches_NOT_rerun_now':len(cases)-len(repeats),
 'original_extracted_files_unchanged':untouched,'old_round1_10_work_files_unchanged':7500,
 'positive_results':positive_summary,
 'regressions':[{k:r[k] for k in ['id','train_correct','test_correct','exact_tie_count','distinct_suffixes_among_exact_training_ties']} for r in reg],
 'dorabella':comparison,
 'limitations':['No confirmed plaintext or established letters.',
 'No new optimization on all 87 symbols. Keys chosen on 43; suffix44 is readout only.',
 'All94 delivered outputs checked; only18 full key searches repeated now.',
 'Full unpruned31m-key audits from old logs were NOT repeated now; 7680 unpruned sample keys were.',
 'Current environment cannot establish process history in inaccessible old containers.',
 'Bigram controls preserve whole-message counts, pairs and ends, not prefix counts; shared replica seeds do not produce identical positional permutations.',
 'No validated joint comparison selecting best of two transcriptions.',
 'This is not exclusion of all substitutions or proof of absence of a message.']}
(R/'audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
# Preserve exact current process snapshot and list only relevant Python searches.
ps=subprocess.check_output(['ps','-eo','pid,ppid,etime,args'],text=True)
(R/'processes_final.txt').write_text(ps)
active=[]
for line in ps.splitlines()[1:]:
 cols=line.strip().split(None,3)
 if len(cols)<4:continue
 cmd=cols[3]
 if (cmd.startswith('python ') or cmd.startswith('/opt/pyvenv/bin/python ')) and any(v in cmd for v in ['round11/run.py','round11/reproduce.py','round11/verify.py','round11/audit_exhaustive.py']):active.append(line)
summary['active_research_processes_at_end']=active
assert not active
(R/'audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'positive':positive_summary,'dorabella':comparison,'fresh_repeated':18,
 'independent_C':summary['current_verification']['stored_C_scores_independently_recomputed'],
 'independent_W_checks':summary['current_verification']['python_word_score_checks'],
 'fresh_full_W':summary['fresh_full_W_evaluations'], 'unchanged_original_files':untouched},ensure_ascii=False,indent=2))
