"""Own finite protocol test ONLY; never imports broker, adapter, Perl or solver."""
from pathlib import Path
import os,sys,json,time,hashlib,resource,ast
BASE=Path(__file__).resolve().parent;sys.path.insert(0,str(BASE))
plan=json.loads((BASE/'PREPARATION_FREEZE.json').read_text());start=time.monotonic()
out=BASE/'PREPARATION_RESULT.json'
if out.exists():raise SystemExit('REFUSE_PRIOR_PREPARATION_TEST')
for name,limits in plan['limits'].items():resource.setrlimit(getattr(resource,name),tuple(limits))
def tick():
    if time.monotonic()-start>15:raise RuntimeError('PREPARATION_DEADLINE')
for name,expected in plan['hashes'].items():
    tick()
    if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('HASH:'+name)
from transport_contract import Channels,pat_request,encode_pat
from wire import request,packet
checks=[]
def check(label,ok):
    tick();checks.append([label,bool(ok)])
    if not ok:raise RuntimeError(label)
def reject(label,func,error):
    try:func()
    except ValueError as exc:check(label,str(exc)==error)
    else:check(label,False)
m=Channels();check('partial',m.feed('pat',b'[1,') is None)
check('pat_seq1',m.feed('pat',b'"meta",""]\n')==(b'[1,"meta",""]\n',1))
check('lm_independent_seq1',m.feed('lm',b'[1,"base",[]]\n')==(b'[1,"base",[]]\n',1))
check('pat_seq2',m.feed('pat',b'[2,"word","cat"]\n')[1]==2)
m.close('lm');check('pat_after_lm_close',m.feed('pat',b'[3,"word","a"]\n')[1]==3)
m.close('pat');check('both_closed',all(m.closed.values()))
for label,channel,data,error in plan['feed_negative']:
    data=(b'x'*int(data[1:])) if data.startswith('@') else bytes.fromhex(data)
    reject(label,lambda channel=channel,data=data:Channels().feed(channel,data),error)
n=Channels();n.close('lm');reject('post_close',lambda:n.feed('lm',b'[]\n'),'CHANNEL_CLOSED_OR_UNKNOWN')
reject('double_close',lambda:n.close('lm'),'CLOSE_STATE')
n=Channels();n.feed('pat',b'[');reject('close_partial',lambda:n.close('pat'),'CLOSE_STATE')
for channel,cap in [('lm',512),('pat',80000)]:
    n=Channels();n.seq[channel]=cap;reject(channel+'_sequence_cap',lambda:n.feed(channel,b'[]\n'),'REQUEST_BOUND')
for label,value,expected in plan['pat_positive']:
    op,arg=pat_request((json.dumps(value)+'\n').encode(),1);check(label,(op,arg.decode())==tuple(expected))
for label,value,error in plan['pat_negative']:
    reject(label,lambda value=value:pat_request((json.dumps(value)+'\n').encode(),1),error)
reject('pat_on_lm',lambda:request(b'[1,"word","cat"]\n',1,['base']),'REQUEST_DOMAIN')
reject('lm_on_pat',lambda:pat_request(b'[1,"base",[]]\n',1),'REQUEST_SHAPE')
check('pat_exact_bytes',encode_pat(1,['chunk',0,['aa','aa','bb']])==b'[1,"chunk",0,["aa","aa","bb"]]\n')
lm=packet(1,0,[[True,'30',1],[True,'3030',2],[True,'302e3030',3],[False,None,None]],True)
check('lm_strings_exact_bytes',lm==b'[1,0,[[true,"30",1],[true,"3030",2],[true,"302e3030",3],[false,null,null]],true]\n')
pat_max=encode_pat(80000,['chunk',63847,['x'*46]*64]);lm_max=packet(512,648,[[True,'ff'*96,10000000]]*128,True)
check('two_max_legal_chunk_frames_bounded',len(pat_max)<65536 and len(lm_max)<65536)
asts=[]
for name in plan['AST_only']:
    ast.parse((BASE/name).read_text(),filename=name);asts.append(name);tick()
check('frozen_check_count',len(checks)+1==plan['expected_checks'])
result={'status':'PASS_OWN_CONTRACT_AND_AST_ONLY','checks':checks,'checks_count':len(checks),'AST_files':asts,'max_pat_frame':len(pat_max),'max_lm_frame':len(lm_max),'elapsed':time.monotonic()-start,'peak_rss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'broker_or_adapter_imported':False,'Perl_or_glue_executed':False,'IPC_or_model_reads':False,'T0_scientific_unchanged':True}
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
