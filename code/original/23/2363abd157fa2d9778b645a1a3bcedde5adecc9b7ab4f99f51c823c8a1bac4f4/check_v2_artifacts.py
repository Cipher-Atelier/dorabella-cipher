"""Post-run integrity checks plus deterministic rerun of Dorabella."""
from pathlib import Path
import json,hashlib
import numpy as np
from automata import canonical,definitions,transform,inverse
from audit import load_cipher
from language import build_model,score_key
from scan_v2 import scan_one
root=Path(__file__).resolve().parent;lp,p1=build_model();_,_,o,c=load_cipher()
for rule in definitions():
 z=transform(o,c,rule);oo,cc=inverse(z,rule)
 assert np.array_equal(o,oo) and np.array_equal(c,cc)
 assert np.array_equal(z//3%4,o%4)
 assert np.array_equal(z%3,c)
old=json.loads((root/'results/v2/dorabella.json').read_text())
new,_=scan_one(o,c,lp,p1)
checks={}
for field in ('best_score','identity_score','improvement','best_rule','decoded','best_key','stages'):
 checks[field]=new[field]==old[field];assert checks[field],field
frozen=json.loads((root/'results/v2_frozen_protocol.json').read_text())
for name,sha in frozen['sha256'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha
z=canonical(transform(o,c,old['best_rule']))
assert abs(score_key(z,np.array(old['best_key']),lp)/84-old['best_score'])<1e-10
res={'all_672_roundtrips_pass':True,'all_672_axis_and_arc_invariants_pass':True,
 'dorabella_repeat_equal':checks,'frozen_hashes_unchanged':True,'best_key_score_recomputed':True}
(root/'results/v2_integrity.json').write_text(json.dumps(res,indent=2));print(res,flush=True)
