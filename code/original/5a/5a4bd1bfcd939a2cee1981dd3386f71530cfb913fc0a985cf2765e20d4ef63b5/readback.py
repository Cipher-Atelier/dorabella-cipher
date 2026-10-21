"""Data-only readback: no scorer, no RNG replay, no search; truth only after terminal checks."""
from pathlib import Path
import json,hashlib,gzip,math
R=Path(__file__).resolve().parent;A=R/'attempt'
H=lambda b:hashlib.sha256(b).hexdigest()
def pack(x):return(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
def read(p):return json.loads(p.read_bytes())
def gz(p):return json.loads(gzip.decompress(p.read_bytes()))
def rank(c):return(-c['score'],c['plaintext87'],c['key26'])
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')

def main():
 terminal=read(A/'terminal.json');receipt=read(R/'raw_execution_receipt.json')
 assert terminal['status']=='COMPLETED_DEVELOPMENT' and terminal['intended_exit_code']==receipt['observed_exit_code']==0
 assert not receipt['session_still_running'] and terminal['budget']['elapsed_seconds']<=60
 assert 'ABORT' not in ''.join(x['output'] for x in receipt['observations'])
 events=[json.loads(line) for x in receipt['observations'] for line in x['output'].splitlines() if line.strip()]
 assert sum(e['event']=='START' for e in events)==1 and sum(e['event']=='TERMINAL' for e in events)==1
 assert events[-1]['terminal_sha256']==H((A/'terminal.json').read_bytes())
 for n,h in terminal['files_sha256'].items():assert H((A/n).read_bytes())==h,n
 frozen=read(R/'FREEZE_MANIFEST.json')
 for n,d in frozen['files'].items():assert H((R/n).read_bytes())==d['sha256'],n
 rows=read(R/'frozen/initial_states.json');states=read(A/'states.json');seeds=read(R/'frozen/seeds.json')
 assert len(states)==40 and [s['state_id'] for s in states]==[s['state_id'] for s in rows]
 controls={x['id']:x['glyph'] for x in read(R/'frozen/decoder_controls.json')}
 index=read(A/'inverse_index.json');verified={};proposal_count=accepted=worse=equal=better=unchanged=0
 stage_trace=[];roundtrip_checks=0
 def verify_new_inverses(invs,location):
  nonlocal roundtrip_checks
  for ident,d in invs.items():
   inv=d['inverse'];text=d['plaintext87'];g=controls[d['case_id']]
   assert H(pack(inv))==d['sha256']==index[ident]['sha256']
   assert index[ident]['file']==location and ident==d['case_id']+'_'+H(text.encode('ascii'))
   assert inv['matched']==87 and inv['recovered_plaintext87']==text and inv['reencoded_glyphs87']==g and len(inv['positions'])==87
   for i,p in enumerate(inv['positions']):
    assert p['position1']==i+1 and p['match'] is True and p['letter']==p['decoded_letter']==text[i]
    assert p['glyph']==p['reencoded_glyph']==g[i]
    assert p['cycle'][p['visit0']%len(p['cycle'])]==g[i]
   assert ident not in verified
   verified[ident]={'case_id':d['case_id'],'text':text,'sha256':d['sha256']}
   roundtrip_checks+=1
 def check_candidate(c,cid):
  assert len(c['key26'])==26 and sorted(c['key26'])==list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') and len(c['plaintext87'])==87
  ref=c['inverse_ref'];assert ref==index[ref['id']]
  v=verified[ref['id']];assert v['case_id']==cid and v['text']==c['plaintext87'] and v['sha256']==ref['sha256']
 verify_new_inverses(gz(A/'initial_inverses.json.gz')['inverses'],'initial_inverses.json.gz')
 trackers={}
 for s,old,seed in zip(states,rows,seeds):
  assert all(s['initial'][k]==old['initial_candidate'][k] for k in ('key26','plaintext87','score'))
  assert s['seed_text']==seed['seed_text'] and s['seed_integer']==seed['seed_integer']
  assert len(s['checkpoints'])==20 and s['proposed']==6500
  check_candidate(s['initial'],s['case_id'])
  trackers[s['state_id']]={'current':s['initial'],'best':s['initial'],'tied':{s['initial']['plaintext87']},
   'seen':{s['initial']['plaintext87']},'visited':{s['initial']['plaintext87']},'scores':{s['initial']['plaintext87']:s['initial']['score']},'accepted':0,'proposed':0,'first_reached':{}}
 pairs=[(i,j) for i in range(26) for j in range(i+1,26)]
 for l in range(20):
  for s in states:
   qref=s['checkpoints'][l];location=qref['file'];assert qref['stage0']==l and qref['complete'] is True
   assert H((A/location).read_bytes())==qref['sha256']
   q=gz(A/location);T=10.0*math.exp(math.log(0.01)*l/19)
   assert q['temperature']==T and q['complete'] is True and len(q['records'])==325
   verify_new_inverses(q['inverses'],location)
   tr=trackers[s['state_id']];assert q['current_initial']==tr['current'] and q['best_initial']==tr['best']
   for n,p in enumerate(q['records']):
    assert p['state_id']==s['state_id'] and p['stage0']==l and p['proposal_in_stage0']==n and p['proposal_in_state1']==l*325+n+1
    assert p['temperature']==T and 0<=p['u']<1 and p['current_before']==tr['current']
    i,j=pairs[p['pair_index0']];assert p['swap0']==[i,j]
    key=list(tr['current']['key26']);key[i],key[j]=key[j],key[i]
    child=p['child'];assert child['key26']==''.join(key) and len(child['plaintext87'])==87
    d=child['score']-tr['current']['score'];assert p['delta']==d
    prob=1.0 if d>=0 else math.exp(d/T)
    accept=d>=0 or p['u']<prob
    assert p['acceptance_probability']==prob and p['accepted']==accept
    same=child['plaintext87']==tr['current']['plaintext87'];assert p['unchanged_plaintext']==same
    unchanged+=same;proposal_count+=1;tr['proposed']+=1
    text=child['plaintext87'];tr['seen'].add(text)
    if text in tr['scores']:assert tr['scores'][text]==child['score']
    else:tr['scores'][text]=child['score']
    if accept:
     cur=p['current_after'];assert all(cur[k]==child[k] for k in ('key26','plaintext87','score'))
     check_candidate(cur,s['case_id']);tr['current']=cur;tr['visited'].add(text);tr['accepted']+=1
     accepted+=1;worse+=d<0;equal+=d==0;better+=d>0
     if text not in tr['first_reached']:tr['first_reached'][text]={'stage0':l,'proposal_in_state1':p['proposal_in_state1']}
    else:assert p['current_after']==tr['current']
    if child['score']>tr['best']['score']:tr['tied']={text}
    elif child['score']==tr['best']['score']:tr['tied'].add(text)
    if rank(child)<rank(tr['best']):
     assert accept;tr['best']=tr['current']
    assert p['best_after']==tr['best']
   assert q['current_final']==tr['current'] and q['best_final']==tr['best'] and q['best_tied_texts']==sorted(tr['tied'])
   stage_trace.append({'stage0':l,'state_id':s['state_id'],'current_score':tr['current']['score'],'best_score':tr['best']['score']})
 assert len(verified)==len(index)
 for s in states:
  tr=trackers[s['state_id']]
  assert tr['current']==s['current'] and tr['best']==s['best'] and sorted(tr['tied'])==s['best_tied_texts']
  assert tr['accepted']==s['accepted'] and tr['proposed']==6500
 b=terminal['budget']
 assert (proposal_count,accepted,worse,equal,better,unchanged)==tuple(b[k] for k in ('proposals','accepted','accepted_worse','accepted_equal','accepted_better','unchanged_proposals'))
 assert b['evaluations']==proposal_count==260000 and b['completed_state_stages']==800
 # No truth file parsed until every search record is terminal and checked.
 truths=read(R/'private/control_truth.json');old={x['id']:x for x in read(R/'private/old_assessment_controls.json')['positive']}
 first={x['state_id']:x['profile'] for x in read(R/'evidence/first_neighborhoods.json')}
 def group(cid):return [(s,trackers[s['state_id']]) for s in states if s['case_id']==cid]
 def top(cid):
  sr=group(cid);maximum=max(tr['best']['score'] for s,tr in sr)
  texts=sorted({p for s,tr in sr if tr['best']['score']==maximum for p in tr['tied']})
  return maximum,texts
 assessment=[]
 for truthrow in truths:
  cid=truthrow['id'];truth=truthrow['plaintext87'];ts=old[cid]['truth_score'];maximum,texts=top(cid)
  neg='N'+cid[1:];nm,nt=top(neg)
  exact_unique=texts==[truth]
  origins=[{'state_id':s['state_id'],'initial_strict_local_max':first[s['state_id']]['better']==0 and first[s['state_id']]['equal']==0,
   'first_accepted':tr['first_reached'].get(truth)} for s,tr in group(cid) if truth in tr['seen']]
  assessment.append({'positive':cid,'truth_score_saved':ts,'before_best_score':max(s['initial']['score'] for s,tr in group(cid)),
   'after_best_score':maximum,'after_top_strings':texts,'top_tie_count':len(texts),
   'before_exact_top':False,'exact_unique_top':exact_unique,'exact_top_including_tie':truth in texts,
   'exact_any_scored':bool(origins),'exact_any_visited':any(truth in tr['visited'] for s,tr in group(cid)),
   'truth_origins':origins,'qualifying_local_max_recovery':exact_unique and any(x['initial_strict_local_max'] for x in origins),
   'truth_minus_best':ts-maximum,'negative':neg,'negative_before_best':max(s['initial']['score'] for s,tr in group(neg)),
   'negative_best':nm,'negative_top_strings':nt,'negative_top_tie_count':len(nt),
   'negative_reached_paired_truth_score':nm>=ts,'positive_minus_negative':maximum-nm})
 a=sum(x['exact_unique_top'] for x in assessment);c=sum(x['negative_reached_paired_truth_score'] for x in assessment)
 escaped=any(x['qualifying_local_max_recovery'] for x in assessment)
 passed=a>=2 and escaped and c==0
 result={'status':'READBACK_VERIFIED','decision':'DEVELOPMENT_GATE_PASSED_HOLDOUT_PREPARATION_ONLY' if passed else 'DEVELOPMENT_GATE_FAILED_VERSION_CLOSED',
  'exact_unique_recovery':a,'exact_any_scored':sum(x['exact_any_scored'] for x in assessment),
  'positive_tied_maxima':sum(x['top_tie_count']>1 for x in assessment),'qualifying_local_max_recovery':escaped,
  'negative_reached_paired_truth_score':c,'budget':b,'unique_inverse_records_verified':roundtrip_checks,
  'terminal_sha256':H((A/'terminal.json').read_bytes()),'assessment':assessment,
  'scope':'40 fixed initial states, assigned branches, regression/development only; no target, p-value, RNG replay or rescoring'}
 write(R/'readback_assessment.json',result);write(R/'stage_score_trace.json',stage_trace)
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
