"""Closed partial records only. Never substitutes a partial expansion winner."""
import json,pathlib
def inspect(R,A):
 out={'status':'PARTIAL_OBSERVATIONS_ONLY','not_full_acceptance':True};p=A/'profile.jsonl';events=[]
 if p.exists():
  bs=p.read_bytes();lines=bs.splitlines(keepends=True);tail=0
  for b in lines:
   if not b.endswith(b'\n'):tail+=len(b);continue
   try:events.append(json.loads(b))
   except (ValueError,UnicodeError):tail+=len(b)
  out['unparsed_tail_bytes']=tail
 scores=[x['value'] for x in events if x['type']=='scored'];completed=[x['value'] for x in events if x['type']=='completed_iteration']
 out.update(scored_records=len(scores),distinct_scored_strings=len({x['text'] for x in scores}),completed_iterations=completed,last_event=events[-1] if events else None)
 if completed:
  q=completed[-1];plain=q['plaintext'];c=(R/'ciphertext.txt').read_text().strip();dec={};enc={};positions=[];valid=len(plain)==len(c)==87
  for i,(g,l) in enumerate(zip(c,plain),1):
   valid=valid and dec.setdefault(g,l)==l and enc.setdefault(l,g)==g;positions.append([i,g,l,enc.get(l)])
  valid=valid and ''.join(enc[x] for x in plain)==c
  truth=json.loads((R/'truth/truth.json').read_text())
  out['last_fully_completed_iteration_best']={'iteration':q['iteration'],'key':q['key'],'plaintext':plain,'positions':positions,'inverse87':valid,'exact_recovery':plain==truth['plaintext87'],'scope':'native completed-iteration best only, total search still incomplete'}
 return out
