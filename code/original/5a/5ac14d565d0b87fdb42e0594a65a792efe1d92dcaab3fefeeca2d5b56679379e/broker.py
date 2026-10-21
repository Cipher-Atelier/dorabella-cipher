"""PREPARED ONLY: chunked transport; readonly adapter unchanged; no scoring."""
from pathlib import Path
import sys,json,time,sqlite3
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from adapter import CompactPatList

def main():
    role=sys.argv[1]
    if role not in ('fixture_broker','large_broker','profile_broker'):raise RuntimeError('ROLE')
    if sys.version_info[:3]!=(3,12,14) or sqlite3.sqlite_version!='3.53.1':raise RuntimeError('RUNTIME')
    freeze=json.loads((BASE/'FREEZE.json').read_text())
    stage='P' if role=='profile_broker' else 'A'
    deadline=json.loads((BASE/'attempt'/f'{stage}_deadline.json').read_text())['deadline']
    def tick():
        if time.monotonic()>=deadline:raise RuntimeError('DEADLINE')
    store=None;saved=None
    if role=='fixture_broker':
        store=CompactPatList(BASE/'fixtures/fixture.sqlite',BASE/'fixtures/fixture.patlst',tick)
    elif role=='profile_broker':
        store=CompactPatList(freeze['full_index']['path'],freeze['patlst']['path'],tick)
    else:saved=json.loads((BASE/'evidence/real_lists.json').read_text())
    maxlen=store.maxlen if store else 46
    stats={'requests':0,'response_frames':0,'response_bytes':0,'max_frame_bytes':0,
           'max_list_count':0,'closed':False}
    log=(BASE/'attempt'/f'{role}_ipc.jsonl').open('x',encoding='ascii')
    def send(seq,value):
        tick();raw=json.dumps([seq,*value],ensure_ascii=True,separators=(',',':')).encode()+b'\n'
        if len(raw)>65536:raise RuntimeError('FRAME_BOUND')
        stats['response_frames']+=1;stats['response_bytes']+=len(raw)
        stats['max_frame_bytes']=max(stats['max_frame_bytes'],len(raw))
        log.write(json.dumps({'response':[seq,*value]},separators=(',',':'))+'\n');log.flush()
        sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
    try:
        for seq in range(1,80001):
            tick();raw=sys.stdin.buffer.readline(65537)
            if not raw or len(raw)>65536 or not raw.endswith(b'\n'):raise RuntimeError('REQUEST_FRAME_OR_EOF')
            request=json.loads(raw)
            if not isinstance(request,list) or len(request)!=3:raise RuntimeError('REQUEST_SHAPE')
            number,op,value=request
            if type(number) is not int or number!=seq or not isinstance(value,str):raise RuntimeError('REQUEST_ID')
            arg=value.encode('ascii');CompactPatList._bytes(arg,87)
            stats['requests']=seq;log.write(json.dumps({'request':request},separators=(',',':'))+'\n')
            if op=='meta' and not value:send(seq,['value',{'maxlen':maxlen}])
            elif op=='word' and store:send(seq,['value',1 if store.is_word(arg) else 0])
            elif op=='list':
                CompactPatList._bytes(arg,46)
                if store:values=store.candidates(arg)
                else:
                    if value not in saved:raise RuntimeError('UNFROZEN_SAVED_QUERY')
                    values=saved[value]
                if values is None:send(seq,['value',None]);continue
                count=len(values)
                if count>63911:raise RuntimeError('LIST_BOUND')
                stats['max_list_count']=max(stats['max_list_count'],count)
                send(seq,['begin',count]);payload=0
                # No whole-list conversion to str/JSON: at most 64 decoded candidates per frame.
                for offset in range(0,count,64):
                    tick();part=[]
                    for item in values[offset:offset+64]:
                        v=item.decode('ascii') if isinstance(item,bytes) else item
                        encoded=v.encode('ascii');CompactPatList._bytes(encoded,46)
                        if not encoded:raise RuntimeError('EMPTY_CANDIDATE')
                        payload+=len(encoded);part.append(v)
                    if payload>2939906:raise RuntimeError('PAYLOAD_BOUND')
                    send(seq,['chunk',offset,part])
                send(seq,['end',count,payload])
                values=None # avoid retaining the previous caller copy during the next FETCH
            elif op=='close' and not value:
                send(seq,['value','closed']);stats['closed']=True;break
            else:raise RuntimeError('OP_DOMAIN')
        if not stats['closed']:raise RuntimeError('REQUEST_BOUND')
    finally:
        if store:stats['adapter']=store.stats.copy();store.close()
        log.close()
    (BASE/'attempt'/f'{role}_terminal.json').write_text(json.dumps(stats,indent=2)+'\n')

if __name__=='__main__':main()
