"""Describe all fixed94 full87 outcomes without retuning or heldout claims."""
from engine import *
from run import sha,atomic_json,check_frozen,utc
import json,collections,platform

def main():
 f=check_frozen();cases=json.loads((H/'data/cases.json').read_text());rows=[json.loads((H/'results'/(c['id']+'.json')).read_text()) for c in cases]
 assert len(rows)==94 and all(r['status']=='verified' for r in rows)
 positives=[r for r in rows if r['kind'] in ('positive','regression')];reals=[r for r in rows if r['kind']=='real'];null=[r for r in rows if r['kind']=='null']
 out={'protocol_sha256':sha(H/'frozen_protocol.json'),'all87_training':True,'heldout_length':0,'cases_verified':len(rows),'character_keys_per_case':NK,'main_character_keys_total':NK*len(rows),'main_word_evaluations_total':sum(r['word_evaluations'] for r in rows),'main_bound_pruned_keys_total':sum(r['bound_pruned_keys'] for r in rows),'exact_plaintext_recovery':{'positive':sum(r['full_correct']==87 for r in positives if r['kind']=='positive'),'positive_n':12,'regression':sum(r['full_correct']==87 for r in positives if r['kind']=='regression'),'regression_n':2},'all_known_true_keys_retained':all(r['true_key_is_exact_tie'] for r in positives),'all87_reencrypted':all(r['all87_reencrypted'] for r in rows),'max_independent_score_error':max(r['max_independent_error'] for r in rows),'positive_ties':[{'id':r['id'],'ties':r['exact_tie_ids'],'key_id':r['key_id'],'true_key':r['true_key']} for r in positives if r['exact_tie_count']>1],'real_results':[],'completed_utc':utc()}
 for r in reals:
  controls=[x for x in null if x['source']==r['id']];assert len(controls)==39
  above=sum(c['score87']>=r['score87']-1e-10 for c in controls);strict=sum(c['score87']>r['score87'] for c in controls)
  out['real_results'].append({**{k:r[k] for k in ['id','score87','C87','W87','key_id','exact_tie_ids','decoded','segmentation','perm8','middle_rank','mask']},'control_count':39,'controls_at_least_real_tolerance1e10':above,'controls_strictly_above':strict,'descriptive_conditional_tail':(1+above)/40,'descending_rank_of40':1+strict,'controls_min':min(c['score87'] for c in controls),'controls_max':max(c['score87'] for c in controls),'controls_median':float(np.median([c['score87'] for c in controls]))})
 states=[json.loads(p.read_text()) for p in sorted((H/'logs').glob('run_state_*.json'))]
 assert all(x['status']=='completed' for x in states)
 out['main_run_states']=states
 out['main_block_elapsed_wall_seconds_sum']=sum(json.loads((H/'checkpoints'/c['id']/'training_result.json').read_text())['block_elapsed_wall_seconds_sum'] for c in cases)
 out['checkpoint_count']=sum(len(list((H/'checkpoints'/c['id']).glob('block_*.json'))) for c in cases);assert out['checkpoint_count']==3760
 audit=H/'audit/unpruned_summary.json'
 out['unpruned_audit']=json.loads(audit.read_text()) if audit.exists() else {'status':'pending'}
 before=json.loads((H/'checks/source_files_before.json').read_text());root=H.parent/'dorabella_audit';changed=[p for p,h in before.items() if sha(root/p)!=h];assert not changed
 atomic_json(H/'checks/source_files_unchanged.json',{'files':len(before),'all_unchanged':True,'manifest_sha256':sha(H/'checks/source_files_before.json'),'checked_utc':utc()})
 atomic_json(H/'results/summary.json',out)
 atomic_json(H/'environment.json',{'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'numba':__import__('numba').__version__,'llvmlite':__import__('llvmlite').__version__,'cpu_count':os.cpu_count(),'affinity':sorted(os.sched_getaffinity(0)),'computation_machine':'dot cloud filesystem, not user computer','thread_workers':4,'numba_threads':os.environ.get('NUMBA_NUM_THREADS'),'openblas_threads':os.environ.get('OPENBLAS_NUM_THREADS')})
 print(json.dumps(out,indent=2))
if __name__=='__main__':main()
