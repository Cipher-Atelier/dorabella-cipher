"""Own two-string exact mathematical diagnostic. No external code execution."""
from pathlib import Path
import json, hashlib, time, datetime, resource, sys, re, os
from fractions import Fraction as F
from decimal import Decimal, localcontext

BASE=Path(__file__).resolve().parent
ROOT=BASE.parent
START=time.monotonic()
RESULT={'status':'INCOMPLETE','start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scans':[]}
ROWS=0
BYTES=0
MEM=Path('/sys/fs/cgroup/memory.current')
TAB=re.compile(rb'\t+')
def tick():
    if time.monotonic()-START>=45:raise RuntimeError('STOP_WALL')
    if int(MEM.read_text())>=7*1024**3:raise RuntimeError('STOP_SHARED_MEMORY')
def sha(b):return hashlib.sha256(b).hexdigest()
def checked(path,expected):
    b=Path(path).read_bytes()
    if sha(b)!=expected:raise RuntimeError('STOP_IDENTITY:'+str(path))
    return b
def scan(entry,visit):
    global ROWS,BYTES
    tick();h=hashlib.sha256();n=0;total=0
    p=Path(entry['path']);s0=p.stat();t=time.monotonic()
    if s0.st_size!=entry['bytes']:raise RuntimeError('STOP_SIZE')
    with p.open('rb',buffering=1048576) as f:
        while True:
            raw=f.readline(131073)
            if not raw:break
            if len(raw)>131072:raise RuntimeError('STOP_ROW_BOUND')
            n+=1;ROWS+=1;total+=len(raw);BYTES+=len(raw);h.update(raw)
            if ROWS>20000000 or BYTES>703617043:raise RuntimeError('STOP_WORK_BOUND')
            if n%8192==0:tick()
            visit(raw,n,total-len(raw))
    s1=p.stat();tick()
    if (s0.st_dev,s0.st_ino,s0.st_size,s0.st_mtime_ns)!=(s1.st_dev,s1.st_ino,s1.st_size,s1.st_mtime_ns):raise RuntimeError('STOP_INPUT_CHANGED')
    if total!=entry['bytes'] or h.hexdigest()!=entry['sha256']:raise RuntimeError('STOP_HASH')
    RESULT['scans'].append({'path':str(p),'sha256':h.hexdigest(),'bytes':total,'rows':n,'elapsed':time.monotonic()-t})
def read_lm(entry,wanted,n):
    data={};matches=[]
    def visit(raw,row,offset):
        fields=TAB.split(raw.rstrip(b'\n'))
        if len(fields)!=n+1:raise RuntimeError('STOP_LM_ROW_DOMAIN')
        key=tuple(x.decode('ascii') for x in fields[:n])
        if key in wanted:
            p=fields[n].decode('ascii');v=F(p)
            if not 0<v<=1:raise RuntimeError('STOP_LM_PROB_DOMAIN')
            matches.append({'key':list(key),'probability_decimal':p,'row':row,'offset':offset,'raw_ascii':raw.decode('ascii')})
            data[key]=p
    scan(entry,visit)
    RESULT.setdefault('model_lookups',[]).append({'file':entry['path'],'wanted':[list(k) for k in sorted(wanted)],'matches_in_source_order':matches,'missing':[list(k) for k in sorted(wanted-set(data))]})
    return data
def grams(seq,n):return {tuple(seq[i-n+1:i+1]) for i in range(n-1,len(seq))}
def segment(s,words,trace):
    tick()
    if len(trace)>=174:raise RuntimeError('STOP_RECURSION_BOUND')
    rec={'input':s};trace.append(rec)
    if not s or s in words or not s.strip():rec['return']=s;return s
    for length in range(46,0,-1):
        for offset in range(len(s)-length+1):
            w=s[offset:offset+length]
            if w not in words:continue
            rec.update(word=w,offset_0based=offset,length=length)
            if offset==0:r=w+' '+segment(s[length:],words,trace)
            elif offset+length==len(s):r=segment(s[:offset],words,trace)+' '+w
            else:r=segment(s[:offset],words,trace)+' '+w+' '+segment(s[offset+length:],words,trace)
            r=re.sub(r'\s+',' ',r);rec['return']=r;return r
    rec['return']=s;return s
def exact_terms(seq,lms,lambdas):
    terms=[];product=F(1)
    for i,token in enumerate(seq):
        vals=[F(lms[n-1].get(tuple(seq[i-n+1:i+1]),'0')) if i>=n-1 else F(0) for n in (1,2,3)]
        p=sum((l*v for l,v in zip(lambdas,vals)),F(0))
        if p<=0:raise RuntimeError('STOP_LOG_DOMAIN')
        product*=p
        terms.append({'position_1based':i+1,'token':token,'probabilities':[str(v) for v in vals],'mixture':str(p)})
    return terms,product
def log_product(terms):
    with localcontext() as ctx:
        ctx.prec=60
        return sum(((Decimal(F(t['mixture']).numerator)/Decimal(F(t['mixture']).denominator)).ln() for t in terms),Decimal(0))
def main():
    if (BASE/'result.json').exists():raise RuntimeError('REFUSE_EXISTING_RESULT')
    resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(45,50))
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024**2,8*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    inp=json.loads((BASE/'INPUTS.json').read_text())
    f=json.loads(checked(ROOT/inp['source_freeze'],inp['source_freeze_sha256']))
    for name,h in inp['original_sha256'].items():checked(ROOT/'TS_TRANSPORT_PROFILE_v2/original'/name,h)
    source=(ROOT/inp['source_handoff']).read_text()
    texts=[x['letters'].lower() for x in inp['strings']]
    if any(len(t)!=87 or not re.fullmatch('[a-z]{87}',t) for t in texts):raise RuntimeError('STOP_INPUT_DOMAIN')
    if any(x['letters'] not in source for x in inp['strings']):raise RuntimeError('STOP_PROVENANCE')
    if [(i+1,a,b) for i,(a,b) in enumerate(zip(*texts)) if a!=b]!=[(83,'k','b')]:raise RuntimeError('STOP_PAIR_IDENTITY')
    files=f['six_lm']+[f['patlst']];page=os.sysconf('SC_PAGE_SIZE')
    b=sum(((e['bytes']+page-1)//page)*page for e in files)
    current=int(MEM.read_text());limit=int(Path('/sys/fs/cgroup/memory.max').read_text())
    RESULT.update(current_before=current,memory_max=limit,input_page_bytes=b,projected_reader_sum=current+b+80*1024**2,events_before=Path('/sys/fs/cgroup/memory.events').read_text())
    if limit!=8*1024**3 or current+b+80*1024**2>=7*1024**3:raise RuntimeError('STOP_READER_ADMISSION')
    assert F(1)*F(1)**19==1 and F(2)*F(1)**19>1 and F(1)*F(1,2)**19<1
    assert F(1,10)*F(1,2)+F(9,10)*F(1,4)==F(11,40)
    RESULT['arithmetic_fixtures']='4/4'
    wanted={t[i:j] for t in texts for i in range(87) for j in range(i+1,88)}
    if len(wanted)>7656:raise RuntimeError('STOP_SUBSTRING_BOUND')
    words=set();lexical_rows=[]
    def pat_visit(raw,row,offset):
        if not raw.startswith(b'1\t'):return
        fields=TAB.split(raw.rstrip(b' \t\n\r\v\f').replace(b' ',b''))
        matched=[v.decode('ascii') for v in fields[2:] if v.decode('ascii') in wanted]
        if matched:
            words.update(matched);lexical_rows.append({'row':row,'offset':offset,'matched':matched,'raw_sha256':sha(raw)})
    scan(f['patlst'],pat_visit)
    RESULT.update(substrings_requested=len(wanted),lexicon_membership={w:w in words for w in sorted(wanted)},lexical_rows=lexical_rows)
    records=[]
    for item,t in zip(inp['strings'],texts):
        trace=[];s=segment(t,words,trace)
        if s.replace(' ','')!=t:raise RuntimeError('STOP_LETTER_PRESERVATION')
        records.append({'id':item['id'],'original87':t,'segmented':s,'trace':trace,'letters_preserved_87_of_87':True,'word_tokens':s.split(),'char_tokens':list(s.replace(' ','_'))})
    wl1=read_lm(f['six_lm'][3],{(w,) for r in records for w in r['word_tokens']}|{('<u>',)},1)
    cl1=read_lm(f['six_lm'][0],{(w,) for r in records for w in r['char_tokens']}|{('<u>',)},1)
    for r in records:
        for kind,lm in [('word',wl1),('char',cl1)]:
            r[kind+'_model_tokens']=[t if lm.get((t,)) else '<u>' for t in r[kind+'_tokens']]
    cl=[cl1];wl=[wl1]
    for n in (2,3):
        cl.append(read_lm(f['six_lm'][n-1],set().union(*(grams(r['char_model_tokens'],n) for r in records)),n))
        wl.append(read_lm(f['six_lm'][n+2],set().union(*(grams(r['word_model_tokens'],n) for r in records)),n))
    products=[]
    for r in records:
        ct,cp=exact_terms(r['char_model_tokens'],cl,list(map(F,inp['char_lambda'])))
        wt,wp=exact_terms(r['word_model_tokens'],wl,list(map(F,inp['word_lambda'])))
        r.update(character_terms=ct,word_terms=wt,char_log_display=str(log_product(ct)),word_log_display=str(log_product(wt)))
        products.append((cp,wp))
    R=(products[1][0]/products[0][0])*(products[1][1]/products[0][1])**19
    sign=(R>1)-(R<1)
    with localcontext() as ctx:
        ctx.prec=50
        delta=(log_product(records[1]['character_terms'])-log_product(records[0]['character_terms']))/20+(log_product(records[1]['word_terms'])-log_product(records[0]['word_terms']))*Decimal(19)/20
    RESULT.update(records=records,exact_comparison='FALSE_HIGHER' if sign>0 else 'TRUTH_HIGHER' if sign<0 else 'EXACT_MATHEMATICAL_TIE',false_minus_truth_log_score_display=str(delta),ratio_numerator_bits=R.numerator.bit_length(),ratio_denominator_bits=R.denominator.bit_length(),ratio_numerator_sha256=sha(R.numerator.to_bytes((R.numerator.bit_length()+7)//8,'big')),ratio_denominator_sha256=sha(R.denominator.to_bytes((R.denominator.bit_length()+7)//8,'big')))
    tick()
    if BYTES!=703617043 or len(RESULT['scans'])!=7:raise RuntimeError('STOP_INCOMPLETE_INPUT_ACCOUNTING')
    RESULT.update(status='COMPLETED_FIXED_PAIR_MATHEMATICAL_DIAGNOSTIC',events_after=Path('/sys/fs/cgroup/memory.events').read_text())
    if RESULT['events_before']!=RESULT['events_after']:raise RuntimeError('STOP_MEMORY_EVENTS_CHANGED')
if __name__=='__main__':
    code=0
    try:main()
    except BaseException as e:RESULT.update(status='STOP',error=repr(e));code=2
    RESULT.update(elapsed=time.monotonic()-START,rows=ROWS,source_bytes=BYTES,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),self_peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,current_after=int(MEM.read_text()))
    if not (BASE/'result.json').exists():
        with (BASE/'result.json').open('x') as f:json.dump(RESULT,f,indent=2);f.write('\n')
    print(json.dumps({k:RESULT.get(k) for k in ('status','error','exact_comparison','false_minus_truth_log_score_display','elapsed','rows','source_bytes','self_peak_rss_KiB')}))
    raise SystemExit(code)
