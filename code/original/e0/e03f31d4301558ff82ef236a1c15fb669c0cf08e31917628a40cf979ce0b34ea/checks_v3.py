"""Implementation, provenance and reproducibility checks for round 3."""
import json,hashlib,itertools,math
import numpy as np
from scan_v3 import Pipeline
from scan_v2 import scan_one
from wordpolish_v3 import fast_word,polish
from wordscore_v3 import ROOT
from automata import canonical,transform,inverse

def main():
 p=Pipeline();rng=np.random.default_rng(2026092505);maxerr=0.
 for i in range(200):
  text=rng.integers(0,26,size=int(rng.integers(4,100)))
  a=p.scorer.score(text);b=fast_word(text,p.ch,p.v);maxerr=max(maxerr,abs(a-b));assert abs(a-b)<1e-10
 # Identity/remapping invariants and monotonicity.
 for i in range(30):
  text=rng.integers(0,26,size=87,dtype=np.int64)
  score,out,m,tr=polish(text,p.lp,p.ch,p.v,.5,30)
  assert sorted(m.tolist())==list(range(26));assert np.array_equal(out,m[text]);assert np.all(np.diff(tr)>=0)
  assert np.array_equal(canonical(text),canonical(out))
 # The input list has 12 unique unseen plaintexts; selection happened after
 # independent parameter freeze. Dictionary historical source overlap is
 # not asserted: its upstream corpus is only broadly documented.
 manifest=json.loads((ROOT/'results/v3/heldout/inputs.json').read_text())
 assert len(manifest['cases'])==12 and len({c['plaintext_sha256'] for c in manifest['cases']})==12
 for case in manifest['cases']:
  o=np.array(case['orientation']);c=np.array(case['arcs_zero_based']);z=transform(o,c,case['generating_rule'])
  oo,cc=inverse(z,case['generating_rule']);assert np.array_equal(o,oo) and np.array_equal(c,cc)
 # Check the exact submitted decoder inputs and each final answer against the
 # ciphertext's equality constraints. A solved-looking string is not enough.
 checks=0
 sets=[(ROOT/'results/v3/heldout/inputs.json',ROOT/'results/v3/heldout')]
 if (ROOT/'results/v3/fresh_null/summary.json').exists():sets.append((ROOT/'results/v3/fresh_null/inputs.json',ROOT/'results/v3/fresh_null'))
 for inp,outdir in sets:
  for case in json.loads(inp.read_text())['cases']:
   r=json.loads((outdir/f"{case['id']}.json").read_text());o=np.array(case['orientation']);c=np.array(case['arcs_zero_based'])
   for row in r['candidates']:
    z=transform(o,c,row['rule']);txt=np.array(row['decoded']);letter_to_glyph={}
    for letter,glyph in zip(txt,z):
     if int(letter) in letter_to_glyph:assert letter_to_glyph[int(letter)]==int(glyph)
     letter_to_glyph[int(letter)]=int(glyph)
    zz=np.array([letter_to_glyph[int(x)] for x in txt]);oo,cc=inverse(zz,row['rule'])
    assert np.array_equal(o,oo) and np.array_equal(c,cc);checks+=1
 # Recompute the unchanged v2 proposal search on actual Dorabella, not merely
 # reload a cached result; test deterministic parity of proposal and rerank.
 case=json.loads((ROOT/'results/v2/dorabella_inputs.json').read_text())[0]
 o=np.array(case['orientation']);c=np.array(case['arcs_zero_based'])
 bank,_=scan_one(o,c,p.lp,p.p1);stored=json.loads((ROOT/'results/v2/dorabella.json').read_text())
 assert abs(bank['best_score']-stored['best_score'])<1e-10
 assert bank['decoded']==stored['decoded']
 new=p.run(o,c,bank);old=json.loads((ROOT/'results/v3/cached/dorabella.json').read_text())
 assert new['decoded']==old['decoded'] and abs(new['best_score']-old['best_score'])<1e-10
 frozen=json.loads((ROOT/'results/v3/frozen_protocol.json').read_text())
 for f,h in frozen['sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
 assert p.scorer.metadata['sha256']==frozen['lexicon']['sha256']
 result={'python_vs_numba_word_score_cases':200,'max_error':maxerr,'polish_invariant_cases':30,
  'candidate_reencryptions_checked':checks,'true_encryption_roundtrips':12,
  'full_dorabella_v2_proposal_recomputed_matches':True,'full_dorabella_v3_repeated_matches':True,
  'frozen_source_and_model_hashes_match':True,'dictionary_hash_matches':True}
 (ROOT/'results/v3/implementation_checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
