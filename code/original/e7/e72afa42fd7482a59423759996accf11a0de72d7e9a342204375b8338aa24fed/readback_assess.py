"""Post-terminal data-only hash/receipt/inverse review and truth comparison. No scorer import."""
from pathlib import Path
import hashlib,json,sys
R=Path(__file__).resolve().parent
A=R/'attempt'
H=lambda b:hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def check_candidate(c,glyphs):
 assert len(c['key26'])==26 and sorted(c['key26'])==list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
 assert len(c['plaintext87'])==87
 inv=c['inverse'];assert inv['matched']==87 and inv['recovered_plaintext87']==c['plaintext87']
 assert inv['reencoded_glyphs87']==glyphs and len(inv['positions'])==87
 for i,p in enumerate(inv['positions']):
  assert p['position1']==i+1 and p['match'] is True
  assert p['letter']==p['decoded_letter']==c['plaintext87'][i]
  assert p['glyph']==p['reencoded_glyph']==glyphs[i]
 for ctab in c['class_table']:assert ctab['letter']==c['key26'][ctab['class_index0']]

def main():
 t=read(A/'terminal.json');receipt=read(R/'raw_execution_receipt.json')
 assert t['status']=='COMPLETED_DEVELOPMENT' and t['intended_exit_code']==0
 assert receipt['observed_exit_code']==0
 assert not receipt.get('session_still_running',False)
 assert 'ABORT' not in ''.join(o['output'] for o in receipt['observations'])
 assert t['budget']['elapsed_seconds']<=60 and t['budget']['evaluations']<=260000
 for p,h in t['files_sha256'].items():assert H((A/p).read_bytes())==h,p
 manifest=read(R/'FREEZE_MANIFEST.json')
 for p,d in manifest['files'].items():assert H((R/p).read_bytes())==d['sha256'],p
 states=read(A/'states.json');initial=read(R/'frozen/initial_states.json');protocol=read(R/'frozen/protocol.json')
 assert [s['state_id'] for s in states]==protocol['state_order'] and len(states)==40
 assert [s['state_id'] for s in initial]==protocol['state_order']
 rawswaps=evals=sweeps=transitions=0
 case_data={c:{'initial':[],'best':[],'visited_texts':set(),'scored_texts':set(),'first':[],
               'downhill_moves':0,'equal_moves':0} for c in protocol['case_order']}
 first_all=[]
 for s,old in zip(states,initial):
  assert s['initial']==old['initial_candidate']
  assert s['status'] in ('MAX_20_TRANSITIONS','NO_ADMISSIBLE_MOVE')
  assert s['transitions']<=20
  transitions+=s['transitions']
  cd=case_data[s['case_id']]
  cd['initial'].append(s['initial']);cd['best'].append(s['best'])
  cd['visited_texts'].add(s['initial']['plaintext87'])
  for c in (s['initial'],s['current'],s['best']):check_candidate(c,s['glyphs'])
  prev=s['initial'];best=prev;history=[''.join(prev['key26'][i] for i in s['observed_classes'])]
  for item in s['sweeps']:
   p=A/item['file'];assert H(p.read_bytes())==item['sha256']
   q=read(p);assert q['complete'] is True and q['current_before']==prev
   assert q['tabu_before']==history and len(history)<=7
   neighbors=q['neighbors'];assert len(neighbors)==325
   assert [x['swap0'] for x in neighbors]==[[i,j] for i in range(26) for j in range(i+1,26)]
   rawswaps+=325;sweeps+=1
   vals={};unchanged=0
   for n in neighbors:
    assert len(n['plaintext87'])==87 and sorted(n['key26'])==list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    if n['plaintext87']==prev['plaintext87']:
     assert n['status']=='UNCHANGED' and n['score']==prev['score'];unchanged+=1;continue
    cd['scored_texts'].add(n['plaintext87'])
    if n['plaintext87'] not in vals or n['key26']<vals[n['plaintext87']]['key26']:
     vals[n['plaintext87']]=n
   evals+=len(vals)
   profile=q['profile_before_tabu'];assert profile==item['profile']
   assert profile['effective_distinct_changed_strings']==len(vals)
   assert profile['unchanged_swaps']==unchanged and profile['evaluations']==len(vals)
   assert profile['better']==sum(x['score']>prev['score'] for x in vals.values())
   assert profile['equal']==sum(x['score']==prev['score'] for x in vals.values())
   assert profile['worse']==sum(x['score']<prev['score'] for x in vals.values())
   assert profile['best_delta']==max(x['score']-prev['score'] for x in vals.values())
   if q['first_neighborhood']:
    f={'state_id':s['state_id'],'case_id':s['case_id'],**profile}
    first_all.append(f);cd['first'].append(f)
   possible=[n for n in vals.values() if ''.join(n['key26'][i] for i in s['observed_classes']) not in history]
   ranked=lambda n:(-n['score'],n['plaintext87'],n['key26'])
   chosen=min(possible,key=ranked) if possible else None
   if chosen:
    assert {k:chosen[k] for k in ('key26','plaintext87','score','swap0')}==q['chosen']
    after=q['current_after'];assert all(after[k]==chosen[k] for k in ('key26','plaintext87','score'))
    cd['downhill_moves']+=after['score']<prev['score'];cd['equal_moves']+=after['score']==prev['score']
    history=(history+[''.join(after['key26'][i] for i in s['observed_classes'])])[-7:]
   else:
    assert q['chosen'] is None and q['status']=='NO_ADMISSIBLE_MOVE';after=prev
   assert q['tabu_after']==history
   b=min([best]+list(vals.values()),key=ranked)
   assert all(q['best_seen'][k]==b[k] for k in ('key26','plaintext87','score'))
   for c in (q['current_before'],q['current_after'],q['best_seen']):check_candidate(c,s['glyphs'])
   cd['visited_texts'].add(after['plaintext87'])
   prev=after;best=q['best_seen']
  assert prev==s['current'] and best==s['best'] and history==s['tabu']
 assert (rawswaps,evals,sweeps,transitions)==tuple(t['budget'][k] for k in ('raw_swaps','evaluations','completed_sweeps','transitions'))
 # First access to truth values in this program occurs after every search is terminal and reviewed.
 truths=read(R/'private/control_truth.json')
 oldassessment=read(R/'private/old_assessment_controls.json')
 old_by_id={x['id']:x for x in oldassessment['positive']}
 assessment=[]
 for p in truths:
  cid=p['id']; truth=p['plaintext87'];score=old_by_id[cid]['truth_score']
  cp=case_data[cid];cn=case_data['N'+cid[1:]]
  def top(items):
   m=max(x['score'] for x in items)
   return m,sorted({x['plaintext87'] for x in items if x['score']==m})
  before,bt=top(cp['initial']);after,at=top(cp['best']);nb,nbt=top(cn['initial']);na,nat=top(cn['best'])
  assessment.append({'positive':cid,'truth_score_saved':score,'before_score':before,'after_score':after,
   'truth_minus_after':score-after,'before_exact_top':truth in bt,'before_exact_any':any(x['plaintext87']==truth for x in cp['initial']),
   'after_exact_top':truth in at,'after_exact_any_visited':truth in cp['visited_texts'],
   'after_exact_any_scored':truth in cp['scored_texts'] or truth in cp['visited_texts'],
   'after_top_strings':at,'first_improving_states':sum(x['better']>0 for x in cp['first']),
   'first_better_counts':[x['better'] for x in cp['first']],
   'first_best_deltas':[x['best_delta'] for x in cp['first']],
   'negative':'N'+cid[1:],'negative_before_score':nb,'negative_after_score':na,
   'negative_reached_paired_truth_before':nb>=score,'negative_reached_paired_truth_after':na>=score,
   'positive_minus_negative_before':before-nb,'positive_minus_negative_after':after-na,
   'negative_after_top_strings':nat,
   'negative_first_improving_states':sum(x['better']>0 for x in cn['first'])})
 summary={'status':'READBACK_VERIFIED','scope':'development, assigned branches only; no target search; no p-value',
  'terminal_sha256':H((A/'terminal.json').read_bytes()),'workload':t['budget'],
  'state_count':40,'first_improving_states':sum(x['better']>0 for x in first_all),
  'first_nonimproving_states':sum(x['better']==0 for x in first_all),
  'first_total_improving_neighbors':sum(x['better'] for x in first_all),
  'effective_counts':sorted(set(x['effective_distinct_changed_strings'] for x in first_all)),
  'positive_exact_top_before':sum(x['before_exact_top'] for x in assessment),
  'positive_exact_top_after':sum(x['after_exact_top'] for x in assessment),
  'positive_any_scored_after':sum(x['after_exact_any_scored'] for x in assessment),
  'negative_reached_paired_truth_after':sum(x['negative_reached_paired_truth_after'] for x in assessment),
  'assessment':assessment,'first_neighborhoods':first_all,
  'downhill_moves':sum(c['downhill_moves'] for c in case_data.values()),
  'equal_moves':sum(c['equal_moves'] for c in case_data.values())}
 save(R/'readback_assessment.json',summary)
 print(json.dumps({k:v for k,v in summary.items() if k not in ('first_neighborhoods',)},ensure_ascii=False))

if __name__=='__main__':main()
