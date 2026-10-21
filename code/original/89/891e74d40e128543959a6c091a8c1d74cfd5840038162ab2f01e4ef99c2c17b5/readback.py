"""Own data-only readback, no solver/adapter imports; used only after staged approval."""
from pathlib import Path
import json,hashlib
BASE=Path(__file__).resolve().parent
ATT=BASE/'attempt'
def require(value,why):
    if not value:raise RuntimeError('READBACK_'+why)
def events(role):return [json.loads(s) for s in (ATT/(role+'.jsonl')).read_bytes().splitlines()]
def compare_large(role):
    rows=events(role);saved=json.loads((BASE/'evidence/real_lists.json').read_text())
    selected=[e for e in rows if e[0]=='list']
    require([e[1] for e in selected]==['a','aa','ab','aba','abc','abcdefgh','!','abcdefgh'],'QUERY_ORDER')
    for e in selected:require(e[2]==saved[e[1]],'ALL_LIST_VALUES_ORDER_DUPLICATES')
    return {'full_list_queries':len(selected),'candidate_occurrences':sum(len(e[2]) for e in selected if e[2]),
            'max_list_count':max(len(e[2]) for e in selected if e[2])}
def broker(role):
    end=json.loads((ATT/(role+'_terminal.json')).read_text())
    require(end['closed'] is True and end['max_frame_bytes']<=65536,'BROKER_TERMINAL')
    seq=0;response_frames=0;last=None
    with (ATT/(role+'_ipc.jsonl')).open() as f:
        for line in f:
            item=json.loads(line)
            if 'request' in item:
                seq+=1;require(item['request'][0]==seq,'IPC_SEQ')
            else:
                require(item['response'][0]==seq,'IPC_RESPONSE_SEQ');response_frames+=1;last=item['response']
    require(seq==end['requests'] and response_frames==end['response_frames'],'IPC_ACCOUNTING')
    require(last==[seq,'value','closed'],'CLOSE_ACK')
    return end
def stage_a():
    actual=(ATT/'fixture_perl.jsonl').read_bytes();prior=(BASE/'evidence/prior_reference.jsonl').read_bytes()
    require(actual==prior,'FIXTURE_COMPLETE_TRACE_BYTES')
    rows=[json.loads(s) for s in actual.splitlines()]
    require(len(rows)==300 and rows[-1]==['terminal','complete',{'cases':3,'score_calls':64}],'FIXTURE_ACCOUNTING')
    for e in rows:
        if e[1] in ('root','winner','candidate','child'):
            key,plain,positions=e[-1]
            require(len(positions)==6 and [x[0] for x in positions]==[1,2,3,4,5,6] and all(x[1]==x[3] for x in positions),'INVERSE_RECORD')
    large=compare_large('large_perl');lr=events('large_perl')
    negatives=json.loads((BASE/'negative/index.json').read_text())
    require([e[1:] for e in lr if e[0]=='negative']==[[x['name'],x['error_prefix']] for x in negatives],'TEN_NEGATIVES')
    require([e[1] for e in lr if e[0]=='positive_chunks']==[['aa','aa','bb']],'POSITIVE_CHUNKS')
    require(lr[-1]==['complete',{'list_fetches':8,'negative':10,'positive_chunks':1}],'TRANSPORT_TERMINAL')
    return {'status':'PASS_A_TRANSPORT_ONLY','fixture_trace_sha256':hashlib.sha256(actual).hexdigest(),
            'fixture_events':300,'large':large,'negative_count':10,
            'brokers':{role:broker(role) for role in ('fixture_broker','large_broker')}}
def stage_p():
    rows=events('profile_perl');loads=[e for e in rows if e[0]=='load_begin']
    require([e[1] for e in loads]==[1,2,3,4,5,6],'SIX_LOADS')
    freeze=json.loads((BASE/'FREEZE.json').read_text())
    require([e[2] for e in loads]==[x['path'] for x in freeze['six_lm']],'LM_PATHS')
    require(rows[-1]==['complete',{'lm_loads':6,'list_fetches':8,'segmentations':6,'search_calls':0,'score_calls':0,'input_bytes':0}],'PROFILE_TERMINAL')
    expected=json.loads((BASE/'evidence/real_segmentation.json').read_text())
    require([e[1:] for e in rows if e[0]=='segment']==[[x['input'],x['output']] for x in expected],'SEGMENTATION')
    ipc=[json.loads(line) for line in (ATT/'profile_broker_ipc.jsonl').read_text().splitlines()]
    word_trace=[]
    for index,item in enumerate(ipc):
        if 'request' in item and item['request'][1]=='word':
            seq,_,word=item['request'];reply=ipc[index+1].get('response')
            require(reply is not None and reply[:2]==[seq,'value'] and reply[2] in (0,1),'WORD_REPLY')
            word_trace.append([word,bool(reply[2])])
    require(word_trace==[t for e in expected for t in e['membership_trace']],'SEGMENTATION_ORDERED_WORD_TRACE')
    large=compare_large('profile_perl')
    return {'status':'PASS_P_LOAD_PROFILE_ONLY','large':large,'profile_snapshots':[e for e in rows if e[0]=='profile'],
            'broker':broker('profile_broker'),'search_bound_established':False,'control_87_authorized':False}
