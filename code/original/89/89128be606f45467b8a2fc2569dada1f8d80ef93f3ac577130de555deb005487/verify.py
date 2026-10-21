"""Independent full87 direct decoder/vectorized C/forward Python dictionary DP checks."""
from engine import *
from run import sha,arrsha,atomic_json,check_frozen,utc
import json,argparse,hashlib
from collections import Counter

def independent_key(i):
 p,r=divmod(i,768);m,b=divmod(r,256)
 return np.array([LETTER[3*P8[p,z//3]+Q[m,2-z%3 if b>>(z//3)&1 else z%3]] for z in range(24)],np.int64)
def ref_word(text,ch,v,segments=False):
 n=len(text);dp=[-1e100]*(n+1);dp[0]=0.;prev=[None]*(n+1)
 for end in range(1,n+1):
  dp[end]=dp[end-1]-8.;prev[end]=end-1
  for start in range(max(0,end-24),end):
   node=0
   for a in text[start:end]:
    node=ch[node,a]
    if node<0:break
   if node<0:continue
   w=v[node,0]
   if start==0 and end<n:w=max(w,v[node,2])
   if end==n and start>0:w=max(w,v[node,1])
   if dp[start]+w>dp[end]:dp[end]=dp[start]+w;prev[end]=start
 if not segments:return dp[n]/n
 words=[];end=n
 while end:
  start=prev[end];words.append(''.join(chr(int(x)+97) for x in text[start:end]));end=start
 return dp[n]/n,' '.join(reversed(words))
def ref_score(text,arrays):
 lp,ch,v,_=arrays;codes=((text[:-3]*26+text[1:-2])*26+text[2:-1])*26+text[3:]
 c=float(lp[codes].sum()/(len(text)-3));w=ref_word(text,ch,v);return c+.5*w,c,w

def verify_case(c,arrays):
 folder=H/'checkpoints'/c['id'];tr=json.loads((folder/'training_result.json').read_text());fp=sha(H/'frozen_protocol.json');g=np.array(c['glyph'],np.int64);lp,ch,v,letter=arrays
 assert tr['status']=='complete' and tr['keys']==NK and tr['train_length']==87 and tr['heldout_length']==0 and tr['protocol_sha256']==fp
 best=-1e100;bestid=-1;ties=[];wordn=0;charn=0;checks=0;maxerr=0.;sparse=0;blockrows=[]
 for bi,start in enumerate(range(0,40320,1024)):
  mp=folder/f'block_{bi:03d}.json';p=folder/f'block_{bi:03d}.npz';r=json.loads(mp.read_text())
  assert r['start']==start and r['stop']==min(start+1024,40320)
  assert r['incoming_score']==best and r['incoming_id']==bestid and r['incoming_ties']==ties
  assert r['protocol_sha256']==fp and r['input_sha256']==arrsha(g) and sha(p)==r['file_sha256']
  with np.load(p,allow_pickle=False) as z:a={n:z[n] for n in z.files}
  for n,h in r['array_sha256'].items():assert arrsha(a[n])==h
  stats=a['stats'];ids=a['scored_ids'];assert len(np.unique(ids))==len(ids) and np.all((ids>=start*768)&(ids<r['stop']*768))
  assert np.array_equal(stats[:,0],np.repeat(np.arange(start,r['stop']),3)) and np.array_equal(stats[:,1],np.tile(np.arange(3),r['stop']-start))
  assert int(stats[:,4].sum())==len(ids)==r['word_evaluations'] and int(stats[:,5].sum())==r['pruned_keys']
  assert r['pruned_keys']+len(ids)==r['char_keys'] and np.all(stats[:,4]+stats[:,5]==256)
  if len(ids):
   # Independent direct decode and C of every saved fully evaluated key, memory-bounded batches.
   for pos in range(0,len(ids),1024):
    ii=ids[pos:pos+1024];pp=ii//768;m=(ii%768)//256;b=ii%256;o=g//3;cc=g%3
    ranks=Q[m[:,None],np.where(((b[:,None]>>o)&1)!=0,2-cc,cc)]
    text=letter[3*P8[pp[:,None],o]+ranks];cod=((text[:,:-3]*26+text[:,1:-2])*26+text[:,2:-1])*26+text[:,3:]
    rec=lp[cod].sum(1)/84;err=float(np.max(np.abs(rec-a['C'][pos:pos+len(ii)])));maxerr=max(maxerr,err);assert err<1e-11
   sparse+=len(ids);ss=a['C']+.5*a['W'];mx=float(ss.max())
   assert np.all(a['W']<=stats[(ids//256)-start*3,3]+1e-9)
   if mx>best:best=mx;ties=sorted(ids[ss==mx].tolist())
   elif mx==best:ties=sorted(set(ties+ids[ss==mx].tolist()))
   bestid=min(ties)
   for j in sorted({0,len(ids)-1,int(np.argmax(ss))}):
    d=independent_key(int(ids[j]))[g];s,_,w=ref_score(d,arrays);err=abs(s-ss[j]);maxerr=max(maxerr,err);assert err<1e-11;checks+=1
  assert r['best_score']==best and r['best_id']==bestid and r['ties']==ties
  charn+=r['char_keys'];wordn+=len(ids);blockrows.append({'block':bi,'json_sha256':sha(mp),'npz_sha256':sha(p)})
 assert charn==NK and wordn==tr['word_evaluations'] and best==tr['train_score'] and bestid==tr['key_id'] and ties==tr['exact_tie_ids'] and blockrows==tr['blocks']
 key=independent_key(bestid);d=key[g];assert len(set(key))==24 and key.tolist()==tr['key_ascii_0based']
 inv={int(x):i for i,x in enumerate(key)};assert [inv[int(x)] for x in d]==g.tolist()
 s,cs,ws=ref_score(d,arrays);assert abs(s-best)<1e-11
 decoded=''.join(chr(int(x)+97) for x in d);assert decoded==tr['decoded_full87']
 r={'id':c['id'],'kind':c['kind'],'source':c.get('source'),'replicate':c.get('replicate'),'status':'verified','protocol_sha256':fp,'score87':best,'C87':cs,'W87':ws,'key_id':bestid,'key_ascii_0based':key.tolist(),'perm8':P8[bestid//768].tolist(),'middle_rank':(bestid%768)//256,'mask':bestid%256,'decoded':decoded,'segmentation':ref_word(d,ch,v,True)[1],'exact_tie_ids':ties,'exact_tie_count':len(ties),'word_evaluations':wordn,'bound_pruned_keys':NK-wordn,'independently_verified_sparse_C':sparse,'python_word_checks':checks+1,'max_independent_error':maxerr,'all87_reencrypted':True,'all87_training':True,'heldout_length':0,'training_result_sha256':sha(folder/'training_result.json')}
 for ti in ties:
  ss,_,_=ref_score(independent_key(ti)[g],arrays);assert abs(ss-best)<1e-11
 if 'plaintext' in c:
  true=np.array([ord(x)-97 for x in c['plaintext']],np.int64);assert np.array_equal(independent_key(c['true_key'])[g],true)
  r.update(full_correct=int(np.sum(d==true)),true_key=c['true_key'],true_key_is_exact_tie=c['true_key'] in ties,true_score87=ref_score(true,arrays)[0],source_status='previously_seen_regression_excerpt')
 atomic_json(H/'results'/(c['id']+'.json'),r);return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kind',default='all');ap.add_argument('--case',action='append');ap.add_argument('--sample-blocks',action='store_true');a=ap.parse_args();check_frozen()
 aa=np.load(H/'data/scoring.npz',allow_pickle=False);arrays=tuple(aa[k] for k in ['lp','children','vals','letter']);cases=json.loads((H/'data/cases.json').read_text());outs=[]
 for c in cases:
  if a.kind!='all' and c['kind'] not in a.kind.split(','):continue
  if a.case and c['id'] not in a.case:continue
  r=verify_case(c,arrays);outs.append(r);print(c['id'],'VERIFIED','full_correct',r.get('full_correct'),'score',r['score87'],flush=True)
 if len([r for r in outs if r['kind'] in ('positive','regression')])==14:
  atomic_json(H/'checks/positives_verified.json',{'protocol_sha256':sha(H/'frozen_protocol.json'),'verified':14,'positive_exact':sum(r.get('full_correct')==87 for r in outs if r['kind']=='positive'),'regression_exact':sum(r.get('full_correct')==87 for r in outs if r['kind']=='regression'),'completed_utc':utc()})
 if a.sample_blocks:
  checks=[]
  for name in ['bailey_01','bailey_08','elgar_march_1897','hauer_real','hart_real','hauer_real_pair_00','hart_real_pair_00']:
   c=next(c for c in cases if c['id']==name);tr=json.loads((H/'results'/(name+'.json')).read_text());g=np.array(c['glyph'],np.int64)
   for pi in [tr['key_id']//768,int(hashlib.sha256(name.encode()).hexdigest()[:8],16)%40320]:
    b=brute_block(g,*arrays[:3],P8,Q,arrays[3],pi,pi+1);z=scan_block(g,*arrays[:3],P8,Q,arrays[3],pi,pi+1,-1e100,-1);ss=b[:,0]+.5*b[:,1];ids=np.flatnonzero(ss==ss.max())+pi*768
    assert z[0]==ss.max() and z[1]==ids.min() and sorted(z[2])==list(ids)
    for m in range(3):assert b[m*256:(m+1)*256,1].max()<=z[3][m,3]+1e-9
    checks.append({'case':name,'pi':pi,'brute_keys':768,'ties':ids.tolist(),'passed':True})
  atomic_json(H/'checks/brute_sample_blocks.json',checks)
 atomic_json(H/'checks/latest_verification.json',{'cases_verified':len(outs),'max_independent_score_error':max(r['max_independent_error'] for r in outs),'protocol_sha256':sha(H/'frozen_protocol.json'),'status':'passed','completed_utc':utc()})
if __name__=='__main__':main()
