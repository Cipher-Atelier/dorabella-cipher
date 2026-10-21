"""Create immutable protocol and fresh synthetic/control inputs, no scoring."""
from pathlib import Path
import sys,os,json,hashlib,platform,datetime,subprocess
sys.dont_write_bytecode=True
from engine import *
from conditional_v7 import euler_shuffle,bigrams
from collections import Counter
H=Path(__file__).parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(path,obj):
 s=json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
 if path.exists():assert path.read_text()==s,f'refuse to change {path}'
 else:path.write_text(s)

PROTOCOL={
 'id':'round11-direction-reversal-prefix-exact-v1',
 'family':{'alphabet':ALPHABET,'triples':['ABC','DEF','GHI','KLM','NOP','QRS','TUW','XYZ'],
  'formula':'key[3*o+c] = ASCII_index(A24[3*P8[o] + Q_m[2-c if bit(mask,o) else c]])',
  'P8':'all 40320 lexicographic permutations of 0..7',
  'Q_m':Q.tolist(),'mask':'all integers 0..255; bit o reverses input arcs 1<->3 for orientation o',
  'canonical_id':'768*lex_rank(P8) + 256*m + mask',
  'unique_full_keys':NK,'duplicates_removed':'6 common P3 * 256 masks has a global-reversal redundancy of 2; canonical Q endpoints ascending removes it',
  'round10_included':'all Q with mask=0 or mask=255; 241920 distinct keys',
  'scope':'No glyph corrections, no position reordering, no state/dot commands. Same fixed triples, common middle rank; not all substitutions, not all 6^8 internal permutations.'},
 'objective':{'train':'S43 = C43 + 0.5*W43 only on first 43 glyphs',
  'test':'Last44 decrypted once with selected key, scored with same C44+0.5*W44 using within-suffix windows only. No cross-boundary 4grams, no suffix-based key choice, stopping, tuning or tie breaking.',
  'whole87':'Only readout with training-selected key; no full-text fit in this round',
  'character':'unchanged archived data/english_merged24_v5.npz, mean natural log conditional 4gram in original window order',
  'word':'unchanged merged24 TextBlob unigram Viterbi; max word24, unknown-8/letter, partial endpoints -2; no added words',
  'key_selection':'Strict largest float64 S43; if EXACT equal, smallest canonical key ID. All exact ties retained. 1e-10 is reporting comparison tolerance for tail counts only, not key selection.',
  'not_probability':True},
 'search':{'method':'Exact enumeration of all 30965760 character scores per input; evaluate W unless admissible ambiguity-word upper bound proves S cannot match incumbent. Bound allows independent lo/hi choices at every position, a superset of all 256 masks for fixed P8,m.',
  'prune':'C+.5*W_upper < incumbent - 1e-9; conservative float safety margin',
  'budget':'All 40320 P8 * 3 canonical Q * 256 masks. No top-K cut, stochastic search, or data-dependent early stopping.',
  'block_P8':1024,'checkpoint':'atomic NPZ+JSON after each P8 block, before next block; cumulative score, exact-tie keys, bounds, sparse complete scores, hashes',
  'sequential_order':'P8 lexicographic, m0..2. Within group character champion first then remaining mask IDs ascending; ties resolved by canonical ID regardless of order'},
 'positive_controls':{'n_main':12,'n_regression':2,'source':'unchanged archived round10 letter excerpts; 12 Bailey/Brewer plus 2 round8 regressions',
  'status':'All 14 texts were already seen in prior rounds. Regression/sensitivity tests, NOT independent new historical holdouts. Fresh nonuniform direction masks, unknown to solver.',
  'seed':202610011101,'key_generation':'uniform P8 permutation, uniform m in0..2, uniform mask in1..254 (exclude old common-order subfamily); independent by excerpt order',
  'normalization':'reuse exactly the existing 87 normalized ASCII letters; j->i and v->u; no modernizing spelling',
  'limitations':'convenience linked letter openings, repeated recipients, merged letters; no guarantee external dictionary lacks author'},
 'negative_controls':{'n_pairs':39,'seed_root':202610011102,
  'method':'archived directed-bigram Euler shuffle with fixed endpoints, independently uniform for each transcription; paired by replicate using same reset RNG seed per replicate for both versions',
  'coupling':'Same RNG initial state, different graphs consume it differently. NOT identical positional permutations and not a validated joint null for max across versions.',
  'selection':'Each version analyzed separately. No choosing better version or multiplying p-values. Controls preserve full glyph counts, directed bigrams, endpoints, not necessarily prefix counts.',
  'tail':'(1+count(test_control>=test_real-1e-10))/(39+1); descriptive conditional tail, not probability true/false plaintext; no global adaptive-search correction'},
 'execution_order':'all14 positive/regression prefixes finalized and independently checked before real transcriptions; then two real, then78 negatives, same search',
 'verification':{'initial':'existing process/files inventory and archive SHA256; no prior round11 found in accessible runtime/archives; withdrawn12/12 not evidence',
  'development':'5 complete two-P8 synthetic toy exhaustive comparisons, before freeze; no actual case scores used',
  'repeat_cases':['bailey_01','bailey_08','elgar_march_1897','hauer_real','hart_real','hauer_real_pair_00','hart_real_pair_00'],
  'repeat_rule':'missing case name substituted ONLY by actual first old-regression case name before freeze',
  'independent':'Python word scorer and direct C evaluation of selected keys; brute full masks on deterministic sampled blocks; checkpoint chaining, admissible bound checks; reencrypt all87; regenerate seeds; verify7500oldfiles'},
 'interpretation':'Exploratory family selected after ten rounds. Exact numerical max does not mean semantic solution or exclusion of every English reading; no new original manuscript evidence.'}

lp,sc,ch,v=load_model()
base=json.loads((ROOT/'round10/data/inputs_base.json').read_text())
rng=np.random.default_rng(PROTOCOL['positive_controls']['seed']);cases=[]
for e in base:
 if e['kind'] not in ('positive','regression'):continue
 p=rng.permutation(8);m=int(rng.integers(3));b=int(rng.integers(1,255))
 pi=int(np.flatnonzero(np.all(P8==p,axis=1))[0]);ki=pi*768+m*256+b;k=key_at(ki)
 true=np.array([ord(c)-97 for c in e['plaintext']],np.int64)
 inv={int(letter):i for i,letter in enumerate(k)};g=np.array([inv[int(x)] for x in true],np.int64)
 assert np.array_equal(k[g],true)
 cases.append({'id':e['id'],'kind':e['kind'],'glyph':g.tolist(),'plaintext':e['plaintext'],'true_key':ki,'true_perm8':p.tolist(),'true_middle':m,'true_mask':b,'source':e['source'],'historical_test_status':'previously_seen_regression'})
reals=[{'id':e['id'],'kind':'real','glyph':e['glyph']} for e in base if e['kind']=='real'];cases+=reals
for j in range(PROTOCOL['negative_controls']['n_pairs']):
 seed=int(np.random.SeedSequence([PROTOCOL['negative_controls']['seed_root'],j]).generate_state(1,dtype=np.uint64)[0])
 for r in reals:
  g=np.array(r['glyph'],np.int64);z=euler_shuffle(g,np.random.default_rng(seed))
  assert Counter(z)==Counter(g) and bigrams(z)==bigrams(g) and z[0]==g[0] and z[-1]==g[-1]
  cases.append({'id':f'{r["id"]}_pair_{j:02d}','kind':'null','source':r['id'],'replicate':j,'seed':seed,'glyph':z.tolist()})
assert len(cases)==94
reg=[c['id'] for c in cases if c['kind']=='regression']
PROTOCOL['verification']['repeat_cases'][2]=reg[0]
put(H/'data/cases.json',cases)
# Separate solver input has NO plaintext or true key and only prefix 43.
put(H/'data/search_inputs.json',[{'id':c['id'],'kind':c['kind'],'prefix':c['glyph'][:43]} for c in cases])
put(H/'data/protocol.json',PROTOCOL)
# Save scoring arrays verbatim for self-contained exact checks.
arrpath=H/'data/scoring.npz'
if not arrpath.exists():np.savez_compressed(arrpath,lp=lp,children=ch,vals=v,letter=LETTER)
else:
 a=np.load(arrpath);assert np.array_equal(a['lp'],lp) and np.array_equal(a['children'],ch) and np.array_equal(a['vals'],v)
put(H/'data/model_metadata.json',sc.metadata)
sourcepaths=['engine.py','prepare.py','run.py','verify.py']
for name in sourcepaths:
 assert (H/name).exists(),name
files=[H/p for p in sourcepaths]+[H/'data/cases.json',H/'data/search_inputs.json',H/'data/protocol.json',H/'data/scoring.npz',H/'data/model_metadata.json',ROOT/'model_v5.py',ROOT/'wordpolish_v3.py',ROOT/'wordscore_v3.py',ROOT/'conditional_v7.py',ROOT/'data/english_merged24_v5.npz',ROOT/'round10/data/inputs_base.json',ROOT/'round10/data/elgar_letters.json']
put(H/'frozen_protocol.json',{'protocol':PROTOCOL,'hashes':{str(p.relative_to(ROOT)):sha(p) for p in files}})
env={'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'numba':__import__('numba').__version__,'dictionary':sc.metadata,'keys':NK}
put(H/'environment.json',env)
print('FROZEN',sha(H/'frozen_protocol.json'),len(cases),'cases',NK,'keys each; regressions',reg,flush=True)
