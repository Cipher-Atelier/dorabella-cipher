"""Independent record checks. Writes only round8/results/final_checks.json."""
from pathlib import Path
import sys,json,hashlib,itertools,math
from collections import Counter
from fractions import Fraction
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from automata import canonical
from wordscore_v3 import WordScorer
from wordpolish_v3 import char_score
from wordsearch_v4 import WordSearch
from geometry_sensitivity import condition_masks

def grams(s,k):return Counter(tuple(s[i:i+k]) for i in range(len(s)-k+1))
def hash_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def general_pattern_formula(s,pattern):
 hist=list(Counter(s).values());one=sum(v==1 for v in Counter(pattern).values());assert sum(v==2 for v in Counter(pattern).values())==2
 def w(d,r):
  dp={(0,0):1}
  for c in hist:
   new=dp.copy()
   for (i,j),v in dp.items():
    if i<d:new[i+1,j]=new.get((i+1,j),0)+v*c*(c-1)
    if j<r:new[i,j+1]=new.get((i,j+1),0)+v*c
   dp=new
  return dp.get((d,r),0)*math.factorial(d)*math.factorial(r)
 top=w(2,one)+2*w(1,one+2)+(math.comb(one,2)*w(3,one-2) if one>=2 else 0)
 return Fraction(top,math.factorial(len(s))//math.factorial(len(s)-len(pattern)))

def main():
 originals=json.loads((HERE/'results/original_archive_sha256.json').read_text())
 assert all(hash_file(ROOT/k)==v for k,v in originals.items())
 frozen=[]
 for p in HERE.glob('frozen_*_protocol.json'):
  f=json.loads(p.read_text());assert all(hash_file(ROOT/k)==v for k,v in f['sha256'].items());frozen.append(p.name)
 # Test exact crib event probability against independent brute-force on small multisets.
 toy=[];pattern='ABACBD'
 for s in [(0,0,1,1,2,3),(0,0,1,1,2,3,4,5),(0,0,0,1,1,2,2,3)]:
  perms=set(itertools.permutations(s));good=0
  for p in perms:
   d=sum(((p[i]==p[j])!=(pattern[i]==pattern[j])) for i in range(6) for j in range(i+1,6))
   good+=d<=1
  exact=general_pattern_formula(s,pattern);assert exact==Fraction(good,len(perms))
  toy.append({'input':s,'prefix_pattern':pattern,'fraction':str(exact),'permutations':len(perms)})
 eng=WordSearch();inputs=json.loads((HERE/'results/elgar/inputs.json').read_text())
 positive={c['id']:c for c in inputs['cases'] if c['kind']=='known_positive'}
 maxerr=0.;n=0
 for c in inputs['cases']:
  d=json.loads((HERE/'results/elgar/records'/(c['id']+'.json')).read_text());assert d['glyph']==c['glyph']
  seq=canonical(np.array(c['glyph']));key=np.array(d['character']['key']);assert sorted(key.tolist())==list(range(26))
  arr=key[seq];assert ''.join(chr(i+97) for i in arr)==d['character']['text']
  err=abs(float(char_score(arr,eng.lp))-d['character']['score']);maxerr=max(maxerr,err)
  key=np.array(d['word']['key']);assert sorted(key.tolist())==list(range(26));arr=key[seq]
  assert arr.tolist()==d['word']['decoded'];cs=float(char_score(arr,eng.lp));ws=float(eng.scorer.score(arr))
  for x,y in [(cs,d['word']['char_score']),(ws,d['word']['word_score']),(cs+.5*ws,d['word']['score'])]:maxerr=max(maxerr,abs(x-y))
  if c['kind']=='trigram_null':
   orig=positive[c['source_id']]['glyph'];assert grams(c['glyph'],3)==grams(orig,3)
   assert c['glyph'][:2]==orig[:2] and c['glyph'][-2:]==orig[-2:]
  else:
   true=np.array([ord(x)-97 for x in c['plaintext']]);assert d['accuracy_word']==float(np.mean(arr==true))
  n+=1
 assert maxerr<1e-10
 # Diagnose the small conditional support rather than treating 29 strings as powerful evidence.
 support={}
 for c in [x for x in json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'] if x['kind']=='real']:
  a=np.load(HERE/'results'/f'{c["id"]}_trigrams.npz')['sequences'];s=c['glyph'];mask=condition_masks(a,s)['same_row_arcs_and_polarity'];sub=a[mask]
  hist=np.array([[np.bincount(row[start:end],minlength=24) for start,end in [(0,29),(29,60),(60,87)]] for row in sub])
  oh=np.array([np.bincount(s[start:end],minlength=24) for start,end in [(0,29),(29,60),(60,87)]])
  support[c['id']]={'support':len(sub),'distinct_row_full_glyph_histograms':len(np.unique(hist.reshape(len(sub),-1),axis=0)),'same_full_glyph_row_histograms_as_original':int(np.sum(np.all(hist==oh,axis=(1,2))))}
 result={'original_round7_files_checked_unchanged':len(originals),'frozen_protocols_verified':frozen,'exact_crib_formula_small_checks':toy,'new_solver_records_checked':n,'maximum_score_error':maxerr,'conditional_support_diagnostic':support,'no_claim':'No plaintext or glyph corrections established.'}
 (HERE/'results/final_checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
