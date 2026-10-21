"""Implementation checks for word-guided permutation updates and scoring.
No accuracy thresholds here. No input mutation is allowed.
"""
import json,hashlib,time
import numpy as np
from wordsearch_v4 import WordSearch,force_word,key_from_text,equality_pattern,ROOT
from wordpolish_v3 import fast_word,char_score
from automata import variants,transform,inverse
from audit import load_cipher

def main():
 t=time.monotonic();p=WordSearch();rng=np.random.default_rng(2026092605)
 _,_,o,c=load_cipher();vv=variants(o,c);n=0;maxerr=0.
 for seq,rule in vv[::17]:
  starts,lengths,gids,off,words,cdf=p.proposals.prepare(seq)
  for _ in range(50):
   key=rng.permutation(26);k=int(rng.integers(len(starts)));g=gids[k]
   j=int(rng.integers(off[g],off[g+1]));start=starts[k];L=lengths[k]
   old=key.copy();trial=force_word(key,seq,start,L,words[j]);assert np.array_equal(key,old)
   assert sorted(trial)==list(range(26));txt=trial[seq]
   assert np.array_equal(txt[start:start+L],words[j,:L])
   assert equality_pattern(txt)==equality_pattern(seq)
   err=abs(p.scorer.score(txt)-fast_word(txt,p.children,p.vals));maxerr=max(maxerr,err);assert err<1e-10
   # Every deciphered sequence can be encoded back through this key/rule.
   geom=transform(o,c,rule);lookup={}
   for x,y in zip(txt,geom):
    if int(x) in lookup:assert lookup[int(x)]==int(y)
    lookup[int(x)]=int(y)
   reconstructed=np.array([lookup[int(x)] for x in txt]);oo,cc=inverse(reconstructed,rule)
   assert np.array_equal(oo,o) and np.array_equal(cc,c);n+=1
 # Small deterministic repeated runs, independent of the long data trials.
 seq=vv[57][0];initial=rng.permutation(26)[seq]
 conf={'restarts':3,'iterations':2000}
 a=p.run(seq,initial,conf,tag='implementation_check_v4');b=p.run(seq,initial,conf,tag='implementation_check_v4')
 assert a['key']==b['key'] and a['score']==b['score'] and a['trace']==b['trace']
 assert a['score']>=char_score(initial,p.lp)+.5*p.scorer.score(initial)-1e-10
 # Initial candidates must be valid; malformed ones are rejected.
 try:key_from_text(np.array([0,0]),np.array([0,1]));raise AssertionError('Should reject')
 except ValueError:pass
 f=json.loads((ROOT/'results/v4/frozen_protocol.json').read_text())
 for path,h in f['sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h
 out={'word_forcing_and_inverse_checks':n,'max_fast_word_vs_python_error':maxerr,
      'deterministic_repeat_same_key_score_trace':True,'input_arrays_not_modified':True,
      'injective_mapping_and_pattern_preserved':True,'invalid_initial_mapping_rejected':True,
      'frozen_hashes_intact':True,'seconds':time.monotonic()-t}
 (ROOT/'results/v4/implementation_checks.json').write_text(json.dumps(out,indent=2));print(out)
if __name__=='__main__':main()
