"""NEW UNEXECUTED combined broker; two isolated pipe channels, one process, no scoring."""
from pathlib import Path
import os,sys,json,time,select,sqlite3
sys.dont_write_bytecode=True
B=Path(__file__).resolve().parent;sys.path.insert(0,str(B))
from disk_contract import DiskLM
from adapter import CompactPatList
from wire import request,packet
from transport_contract import Channels,pat_request,encode_pat
def main():
    role,*args=sys.argv[1:]
    if role not in ('adapted_broker','real_broker') or len(args)!=4:raise RuntimeError('ARGS')
    fds=list(map(int,args))
    if len(set(fds))!=4:raise RuntimeError('FD_ALIAS')
    if sys.version_info[:3]!=(3,12,14) or sqlite3.sqlite_version!='3.53.1':raise RuntimeError('RUNTIME')
    routes={'lm':(fds[0],fds[1]),'pat':(fds[2],fds[3])}
    deadline=json.loads((B/'attempt/phase_deadline.json').read_text())['deadline']
    def tick():
        if time.monotonic()>=deadline:raise RuntimeError('DEADLINE')
    spec=json.loads((B/'real_spec.json').read_text());ds=json.loads((B/'datasets.json').read_text())
    names=['real'] if role=='real_broker' else ['base','edge'];stores={};pat=None
    counters={'lm':{'requests':0,'lookups':0,'response_frames':0,'response_bytes':0,'max_frame':0,'closed':False},
              'pat':{'requests':0,'response_frames':0,'response_bytes':0,'max_frame':0,'max_list_count':0,'candidate_occurrences':0,'closed':False}}
    mux=Channels();log=(B/'attempt'/f'{role}_ipc.jsonl').open('xb')
    def write_record(channel,kind,raw):
        log.write(b'{"channel":'+json.dumps(channel).encode()+b',"'+kind.encode()+b'":'+raw.rstrip(b'\n')+b'}\n');log.flush()
    def send(channel,raw):
        tick();write_record(channel,'response',raw);view=memoryview(raw)
        while view:
            tick();n=os.write(routes[channel][1],view)
            if n<=0:raise RuntimeError('WRITE')
            view=view[n:]
        c=counters[channel];c['response_frames']+=1;c['response_bytes']+=len(raw);c['max_frame']=max(c['max_frame'],len(raw))
    try:
        for name in names:
            es=[]
            for entry in ds[name]:
                entry=dict(entry)
                for key in ('path','index_path'):
                    if not Path(entry[key]).is_absolute():entry[key]=str(B/entry[key])
                es.append(entry)
            stores[name]=DiskLM(es,tick,4096 if role=='real_broker' else 3)
        pat=CompactPatList(spec['full_index']['path'],spec['patlst']['path'],tick) if role=='real_broker' else CompactPatList(B/'fixtures/base/fixture.sqlite',B/'fixtures/base/fixture.patlst',tick)
        while not all(mux.closed.values()):
            tick();active={routes[c][0]:c for c in ('lm','pat') if not mux.closed[c]}
            readable,_,_=select.select(list(active),[],[],.05)
            for fd in readable:
                channel=active[fd];raw=os.read(fd,min(4096,65536-len(mux.buffers[channel])))
                ready=mux.feed(channel,raw)
                if ready is None:continue
                raw,seq=ready;write_record(channel,'request',raw);c=counters[channel];c['requests']=seq
                if channel=='lm':
                    name,items=request(raw,seq,names)
                    if c['lookups']+len(items)>20000:raise RuntimeError('LOOKUP_BOUND')
                    for offset in (range(0,len(items),128) if items else [0]):
                        values=[]
                        for table,key in items[offset:offset+128]:
                            v=stores[name].lookup(table,key);values.append([v['found'],v['value_hex'],v['last_row_1based']]);c['lookups']+=1
                        send('lm',packet(seq,offset,values,offset+len(values)==len(items)))
                    if name=='close':mux.close('lm');c['closed']=True
                else:
                    op,arg=pat_request(raw,seq)
                    if op=='meta':send('pat',encode_pat(seq,['value',{'maxlen':pat.maxlen}]))
                    elif op=='word':send('pat',encode_pat(seq,['value',1 if pat.is_word(arg) else 0]))
                    elif op=='list':
                        values=pat.candidates(arg)
                        if values is None:send('pat',encode_pat(seq,['value',None]));continue
                        count=len(values)
                        if count>63911:raise RuntimeError('LIST_BOUND')
                        c['max_list_count']=max(c['max_list_count'],count);c['candidate_occurrences']+=count
                        send('pat',encode_pat(seq,['begin',count]));payload=0
                        for offset in range(0,count,64):
                            tick();part=[]
                            for value in values[offset:offset+64]:
                                CompactPatList._bytes(value,46)
                                if not value:raise RuntimeError('EMPTY_CANDIDATE')
                                payload+=len(value);part.append(value.decode('ascii'))
                            if payload>2939906:raise RuntimeError('PAYLOAD_BOUND')
                            send('pat',encode_pat(seq,['chunk',offset,part]))
                        send('pat',encode_pat(seq,['end',count,payload]));values=None
                    elif op=='close':send('pat',encode_pat(seq,['value','closed']));mux.close('pat');c['closed']=True
        tick()
    finally:
        counters['stores']={k:v.stats for k,v in stores.items()};counters['pat_store']=pat.stats if pat else None
        for store in stores.values():store.close()
        if pat:pat.close()
        log.close()
        for fd in fds:os.close(fd)
    counters['both_closed']=all(mux.closed.values())
    (B/'attempt'/f'{role}_terminal.json').write_text(json.dumps(counters,indent=2)+'\n')
if __name__=='__main__':main()
