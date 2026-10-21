"""Summarize completed results and perform packaging/identity diagnostics.
No key selection or fitting is performed here.
"""
from pathlib import Path
import sys,os,json,hashlib,datetime,importlib.metadata,itertools
sys.dont_write_bytecode=True
from engine import *
from run import sha,arrsha,atomic_json,check_frozen
H=Path(__file__).parent

def main():
 frozen=check_frozen();fp=sha(H/'frozen_protocol.json')
 cases=json.loads((H/'data/cases.json').read_text());res={c['id']:json.loads((H/'results'/(c['id']+'.json')).read_text()) for c in cases}
 count=0
 for c in cases:
  f=H/'checkpoints'/c['id'];t=json.loads((f/'training_result.json').read_text())
  assert sha(f/'training_result.json')==res[c['id']]['training_result_sha256']
  for b in t['blocks']:
   n=b['block'];assert sha(f/f'block_{n:03d}.json')==b['json_sha256'];assert sha(f/f'block_{n:03d}.npz')==b['npz_sha256'];count+=1
 # Combinatorial identity proof checks, not random inference.
 perms3=list(itertools.permutations(range(3))); embeddings=[]
 for q in perms3:
  m=q[1];mask=0 if q[0]<q[2] else 255
  assert [int(Q[m,2-c if mask else c]) for c in range(3)]==list(q)
  embeddings.append({'round10_P3':q,'middle':m,'mask':mask})
 # Same P8: exhaustively verify all 768 internal tables unique and bijective.
 tables=np.array([key_at(i) for i in range(768)],np.int64)
 assert len(np.unique(tables,axis=0))==768
 assert np.all(np.sort(tables,axis=1)==np.sort(LETTER))
 # Any table reveals P8 by integer division of alphabet rank by3, m by c=1,
 # and its independent reversal bits by endpoint order. Verify all40320 P8
 # across the six embedded global orders (241920 keys) vectorized.
 invletter={int(v):i for i,v in enumerate(LETTER)}
 for m in range(3):
  for b in [0,255]:
   ranks=3*P8[:,:,None]+Q[m,np.array([2,1,0]) if b else np.arange(3)][None,None,:]
   assert np.all(ranks[:,:,1]//3==P8)
   assert np.all(ranks[:,:,1]%3==m)
 fam={'full_keys':NK,'canonical_Q_count':3,'masks':256,'P8_count':40320,
  'proof':'Each full key uniquely reveals P8 (alphabet rank //3), common middle m (rank%3 at c=1), and each reversal bit (endpoint rank order). Thus 40320*3*256 distinct bijections.',
  'all768_internal_keys_explicitly_unique':True,'all241920_round10_embeddings_checked':True,'round10_embeddings':embeddings}
 atomic_json(H/'audit/family_identity.json',fam)
 summary={'status':'completed_and_verified_no_solution','protocol_sha256':fp,'case_count':94,'keys_per_input':NK,
  'main_character_key_input_evaluations':94*NK,'main_fully_evaluated_word_scores':sum(v['word_evaluations'] for v in res.values()),
  'main_safe_bound_pruned_word_scores':94*NK-sum(v['word_evaluations'] for v in res.values()),
  'main_checkpoint_blocks_verified':count,'max_independent_score_error':max(v['max_independent_error'] for v in res.values()),
  'all_stored_complete_key_char_scores_independently_verified':sum(v['independently_verified_sparse_C'] for v in res.values()),
  'python_word_score_checks':sum(v['python_word_checks'] for v in res.values()),
  'positives':{},'real':{}}
 for kind in ['positive','regression']:
  a=[res[c['id']] for c in cases if c['kind']==kind]
  summary['positives'][kind]={'n':len(a),'train43_exact':sum(v['train_correct']==43 for v in a),
   'test44_exact':sum(v['test_correct']==44 for v in a),'train_correct_letters':sum(v['train_correct'] for v in a),
   'test_correct_letters':sum(v['test_correct'] for v in a),'unique_training_key':sum(v['exact_tie_count']==1 for v in a),
   'unambiguous_correct_suffix_across_all_maximum_training_keys':sum(v['test_correct']==44 and v['distinct_suffixes_among_exact_training_ties']==1 for v in a),
   'per_case':[{k:v[k] for k in ['id','train_correct','test_correct','full_correct','exact_tie_count','distinct_suffixes_among_exact_training_ties','train_score','true_prefix_score']} for v in a]}
 for n in ['hauer_real','hart_real']:
  r=res[n];nulls=[res[c['id']] for c in cases if c['kind']=='null' and c['source']==n]
  kt=sum(x['test_score']>=r['test_score']-1e-10 for x in nulls);kh=sum(x['train_score']>=r['train_score']-1e-10 for x in nulls)
  summary['real'][n]={'train_S43':r['train_score'],'test_S44':r['test_score'],'null_count':len(nulls),'test_controls_ge':kt,
   'descriptive_test_tail_plus1':(kt+1)/40,'train_controls_ge':kh,'key_id':r['key_id'],
   'perm8':r['perm8'],'middle_rank':r['middle_rank'],'mask':r['mask'],'exact_training_ties':r['exact_tie_count'],
   'full_readout_NOT_solution':r['decoded'],'suffix_null_range':[min(x['test_score'] for x in nulls),max(x['test_score'] for x in nulls)]}
 summary['bounded_full_repeats']=json.loads((H/'audit/full_repeats_verified.json').read_text())
 summary['unpruned_verification']={k:v for k,v in json.loads((H/'audit/unpruned_summary.json').read_text()).items() if k!='results'}
 summary['round10_recomputed']=json.loads((H/'audit/round10_recomputed.json').read_text())
 summary['old_files']=json.loads((H/'audit/old_files_verified.json').read_text())
 atomic_json(H/'results/summary.json',summary)
 # Explain only post-selection ambiguity. Do not choose a different tie using truth.
 diagnostics=[]
 for name in ['bailey_05','bailey_06','bailey_07','elgar_march_1897','elgar_caractacus_postcard']:
  c=next(c for c in cases if c['id']==name);r=res[name];g=np.array(c['glyph'],np.int64)
  entries=[]
  for kid in r['exact_tie_ids']:
   s=''.join(chr(int(x)+97) for x in key_at(kid)[g]);entries.append({'id':kid,'suffix':s[43:],'test_correct_after_selection_only':sum(a==b for a,b in zip(s[43:],c['plaintext'][43:]))})
  absent_flip_directions=[o for o in range(8) if not any(z//3==o and z%3!=1 for z in g[:43])]
  diagnostics.append({'case':name,'selected_key':r['key_id'],'unchanged_selected_test_correct':r['test_correct'],'true_key':c['true_key'],
   'prefix_unobserved_reversal_bits':absent_flip_directions,'equal_training_maxima':entries,
   'training_score_gap_selected_minus_truth':r['train_score']-r['true_prefix_score'],'posthoc_only':True})
 atomic_json(H/'audit/ambiguity_diagnostic.json',diagnostics)
 versions={n:importlib.metadata.version(n) for n in ['numpy','numba','scipy','textblob','gensim']}
 (H/'requirements_round11.txt').write_text('\n'.join(f'{n}=={v}' for n,v in versions.items())+'\n')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
