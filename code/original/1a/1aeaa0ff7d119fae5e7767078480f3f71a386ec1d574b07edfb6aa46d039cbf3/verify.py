"""Independent score checks, seed regeneration, checkpoints, full repeats.
Test readout happens only after immutable prefix training results exist.
"""
from pathlib import Path
import json,sys,os,argparse,hashlib,time
sys.dont_write_bytecode=True
from engine import *
from run import sha,arrsha,atomic_json,check_frozen,run_case
from conditional_v7 import euler_shuffle,bigrams
from collections import Counter
H=Path(__file__).parent

def independently_score(t,lp,sc):
 a=np.array([ord(c)-97 for c in t],np.int64) if isinstance(t,str) else np.asarray(t,np.int64)
 codes=((a[:-3]*26+a[1:-2])*26+a[2:-1])*26+a[3:]
 c=float(np.sum(lp[codes])/(len(a)-3));w=sc.score(a)
 return c+.5*w,c,w

def verify_case(c,arrays,sc):
 lp,ch,v,letter=arrays;folder=H/'checkpoints'/c['id']
 fp=sha(H/'frozen_protocol.json');train=json.loads((folder/'training_result.json').read_text())
 assert train['status']=='complete' and train['keys']==NK and train['protocol_sha256']==fp
 best=-1e100;bestid=-1;ties=[];wordn=0;charn=0;checks=0;maxerr=0.;sparse_chars=0
 g=np.array(c['glyph'][:43],np.int64)
 for bi,start in enumerate(range(0,40320,1024)):
  r=json.loads((folder/f'block_{bi:03d}.json').read_text());p=folder/f'block_{bi:03d}.npz'
  assert r['start']==start and r['stop']==min(start+1024,40320)
  assert r['incoming_score']==best and r['incoming_id']==bestid and r['incoming_ties']==ties
  assert r['protocol_sha256']==fp and r['input_sha256']==arrsha(g) and sha(p)==r['file_sha256']
  with np.load(p) as z:
   a={n:z[n] for n in z.files}
  for n,h in r['array_sha256'].items():assert arrsha(a[n])==h
  ids=a['scored_ids'];assert len(np.unique(ids))==len(ids)
  assert np.all((ids>=start*768)&(ids<r['stop']*768))
  assert int(a['word_evaluated'].sum())==len(ids)==r['word_evaluations']
  assert r['pruned_keys']+len(ids)==r['char_keys']
  if len(ids):
   # Direct independent vectorized character evaluation for EVERY stored fully scored key.
   pi=ids//768;m=(ids%768)//256;b=ids%256
   o=g//3;cc=g%3
   rank=Q[m[:,None],np.where(((b[:,None]>>o)&1)!=0,2-cc,cc)]
   text=letter[3*P8[pi[:,None],o]+rank]
   cod=((text[:,:-3]*26+text[:,1:-2])*26+text[:,2:-1])*26+text[:,3:]
   resc=lp[cod].sum(1)/40
   err=float(np.max(np.abs(resc-a['C'])));maxerr=max(maxerr,err);assert err<1e-11
   sparse_chars+=len(ids)
   vals=a['C']+.5*a['W']
   mx=float(vals.max())
   if mx>best:best=mx;ties=sorted(ids[vals==mx].tolist())
   elif mx==best:ties=sorted(set(ties+ids[vals==mx].tolist()))
   bestid=min(ties)
   # Python dictionary DP independently checks deterministic samples in every block.
   for j in sorted({0,len(ids)-1,int(np.argmax(vals))}):
    ss,ccc,www=independently_score(text[j],lp,sc)
    err=abs(ss-vals[j]);maxerr=max(maxerr,err);assert err<1e-11
    assert www<=a['word_upper'][(ids[j]//256)-start*3]+1e-10
    checks+=1
  assert r['best_score']==best and r['best_id']==bestid and r['ties']==ties
  charn+=r['char_keys'];wordn+=len(ids)
 assert charn==NK and wordn==train['word_evaluations'] and best==train['train_score']
 assert bestid==train['key_id'] and ties==train['exact_tie_ids']
 key=key_at(bestid);g87=np.array(c['glyph'],np.int64);d=key[g87]
 assert len(set(key))==24 and np.array_equal(key,train['key_ascii_0based'])
 inverse={int(x):i for i,x in enumerate(key)}
 assert [inverse[int(x)] for x in d]==g87.tolist()
 ss,cs,ws=independently_score(d[:43],lp,sc);assert abs(ss-best)<1e-11
 test,tc,tw=independently_score(d[43:],lp,sc)
 decoded=''.join(chr(int(x)+97) for x in d)
 out={'id':c['id'],'kind':c['kind'],'source':c.get('source'),'replicate':c.get('replicate'),
  'training_result_sha256':sha(folder/'training_result.json'),'protocol_sha256':fp,
  'train_score':best,'key_id':bestid,'key_ascii_0based':key.tolist(),
  'perm8':P8[bestid//768].tolist(),'middle_rank':(bestid%768)//256,'mask':bestid%256,
  'test_score':test,'test_C':tc,'test_W':tw,'decoded':decoded,'test_decoded':decoded[43:],
  'segmentation':sc.score(d,True)[1],'exact_tie_count':len(ties),'exact_tie_ids':ties,
  'distinct_suffixes_among_exact_training_ties':len({tuple(key_at(i)[g87[43:]]) for i in ties}),
  'word_evaluations':wordn,'bound_pruned_keys':NK-wordn,
  'independently_verified_sparse_C':sparse_chars,'python_word_checks':checks+2,'max_independent_error':maxerr,
  'all87_reencrypted':True,'status':'verified','test_ever_used_for_key_choice':False}
 if 'plaintext' in c:
  true=np.array([ord(x)-97 for x in c['plaintext']],np.int64)
  assert np.array_equal(key_at(c['true_key'])[g87],true)
  out.update(train_correct=int(np.sum(d[:43]==true[:43])),test_correct=int(np.sum(d[43:]==true[43:])),
    full_correct=int(np.sum(d==true)),true_key=c['true_key'],true_key_is_exact_training_tie=c['true_key'] in ties,
    true_prefix_score=independently_score(true[:43],lp,sc)[0],source_status='old regression excerpt, fresh encryption')
 atomic_json(H/'results'/(c['id']+'.json'),out)
 return out

def input_checks(cases):
 seed=202610011101;rng=np.random.default_rng(seed)
 for c in [x for x in cases if x['kind'] in ('positive','regression')]:
  p=rng.permutation(8);m=int(rng.integers(3));b=int(rng.integers(1,255))
  assert c['true_perm8']==p.tolist() and c['true_middle']==m and c['true_mask']==b
 reals={c['id']:c for c in cases if c['kind']=='real'}
 for c in [x for x in cases if x['kind']=='null']:
  base=np.array(reals[c['source']]['glyph'],np.int64);z=euler_shuffle(base,np.random.default_rng(c['seed']))
  assert z.tolist()==c['glyph'] and Counter(z)==Counter(base) and bigrams(z)==bigrams(base)
  assert z[0]==base[0] and z[-1]==base[-1]
 return {'fresh_positive_seeds_regenerated':14,'nulls_regenerated':78,'all_invariants':True,
  'null_unique':{k:len({tuple(c['glyph']) for c in cases if c.get('source')==k and c['kind']=='null'}) for k in reals}}

def round10_check():
 sys.path.insert(0,str(ROOT/'round10'))
 from table_search import all_scores,P3
 lp,sc,ch,v=load_model();out=[]
 cases=json.loads((ROOT/'round10/data/inputs.json').read_text())
 for name in ['bailey_01','hauer_real']:
  c=next(c for c in cases if c['id']==name);t=time.time()
  a=all_scores(np.array(c['glyph'],np.int64),lp,ch,v,P8,P3,LETTER)
  r=json.loads((ROOT/'round10/results/records'/(name+'.json')).read_text())
  assert arrsha(a)==r['scores_sha256']
  out.append({'id':name,'keys':241920,'scores_sha256':arrsha(a),'seconds':time.time()-t})
 atomic_json(H/'audit/round10_recomputed.json',out);print('round10 verified',out,flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kind',default='all');ap.add_argument('--repeat',action='store_true');ap.add_argument('--sample-blocks',action='store_true');ap.add_argument('--round10',action='store_true');ap.add_argument('--old-files',action='store_true')
 a=ap.parse_args()
 if a.round10:round10_check();return
 check_frozen();fph=sha(H/'frozen_protocol.json')
 cases=json.loads((H/'data/cases.json').read_text());data=np.load(H/'data/scoring.npz')
 arrays=(data['lp'],data['children'],data['vals'],data['letter']);lp,sc,ch,v=load_model()
 assert np.array_equal(lp,arrays[0]) and np.array_equal(ch,arrays[1]) and np.array_equal(v,arrays[2])
 atomic_json(H/'audit/input_checks.json',input_checks(cases))
 selected=[c for c in cases if a.kind=='all' or c['kind'] in a.kind.split(',')]
 outs=[]
 for c in selected:
  r=verify_case(c,arrays,sc);outs.append(r)
  print(c['id'],'VERIFIED','train_correct',r.get('train_correct'),'test_correct',r.get('test_correct'),'ties',r['exact_tie_count'],flush=True)
 if {c['id'] for c in selected if c['kind'] in ('positive','regression')}=={c['id'] for c in cases if c['kind'] in ('positive','regression')}:
  atomic_json(H/'audit/positives_verified.json',{'protocol_sha256':fph,'verified':14,'cases':[r['id'] for r in outs if r['kind'] in ('positive','regression')],
   'test_44_exact':sum(r.get('test_correct',-1)==44 for r in outs if r['kind']=='positive'),
   'regression_test_44_exact':sum(r.get('test_correct',-1)==44 for r in outs if r['kind']=='regression')})
 if a.sample_blocks:
  checks=[]
  for name in ['bailey_01','hauer_real','hart_real','hauer_real_pair_00','hart_real_pair_00']:
   c=next(c for c in cases if c['id']==name)
   if not (H/'results'/(name+'.json')).exists():continue
   tr=json.loads((H/'results'/(name+'.json')).read_text());prefix=np.array(c['glyph'][:43],np.int64)
   # Around actual selected permutation, plus deterministic unrelated permutation.
   ps=[tr['key_id']//768,int(hashlib.sha256(name.encode()).hexdigest()[:8],16)%40320]
   for pi in ps:
    b=brute_block(prefix,*arrays[:3],P8,Q,arrays[3],pi,pi+1)
    z=scan_block(prefix,*arrays[:3],P8,Q,arrays[3],pi,pi+1,-1e100,-1)
    ss=b[:,0]+.5*b[:,1];ix=pi*768+int(np.argmax(ss))
    assert z[1]==ix and z[0]==ss.max()
    for m in range(3):assert b[m*256:(m+1)*256,1].max()<=z[3][m,3]+1e-10
    checks.append({'case':name,'pi':pi,'keys_bruteforce':768,'score':float(ss.max()),'winner':ix,'passed':True})
  atomic_json(H/'audit/brute_sample_blocks.json',checks)
 if a.repeat:
  names=check_frozen()['protocol']['verification']['repeat_cases'];search=json.loads((H/'data/search_inputs.json').read_text());reps=[]
  for name in names:
   if not (H/'checkpoints'/name/'training_result.json').exists():continue
   c=next(c for c in search if c['id']==name)
   original=json.loads((H/'checkpoints'/name/'training_result.json').read_text())
   repeat=run_case(c,arrays,H/'audit/full_repeats')
   for k in ['key_id','train_score','exact_tie_ids','word_evaluations','decoded_prefix']:assert original[k]==repeat[k]
   for i in range(40):
    aa=json.loads((H/'checkpoints'/name/f'block_{i:03d}.json').read_text())
    bb=json.loads((H/'audit/full_repeats'/name/f'block_{i:03d}.json').read_text())
    assert aa['array_sha256']==bb['array_sha256']
   reps.append({'case':name,'all30965760_keys_repeated':True,'all40checkpoint_arrays_identical':True})
  atomic_json(H/'audit/full_repeats_verified.json',reps)
 if a.old_files:
  hashes=json.loads((H/'audit/round10_file_hashes.json').read_text());changed=[]
  for n,h in hashes.items():
   if sha(ROOT.parent/n)!=h:changed.append(n)
  assert not changed
  atomic_json(H/'audit/old_files_verified.json',{'verified':len(hashes),'changed':changed})
 atomic_json(H/'audit/latest_verification.json',{'protocol_sha256':fph,'cases_verified':len(outs),
  'max_independent_score_error':max(r['max_independent_error'] for r in outs),'status':'passed'})

if __name__=='__main__':main()
