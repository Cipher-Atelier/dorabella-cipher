"""Prepared only. Small-fixture readonly bridge, never a solver or model scorer."""
from pathlib import Path
import sys, json, time, hashlib, sqlite3
sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from adapter import CompactPatList

def main():
    if sys.version_info[:3] != (3,12,14) or sqlite3.sqlite_version != '3.53.1':
        raise RuntimeError('RUNTIME_MISMATCH')
    freeze = json.loads((BASE/'FREEZE.json').read_text())
    for name in ('fixture.sqlite','fixture.patlst'):
        p=BASE/'fixtures'/name
        if hashlib.sha256(p.read_bytes()).hexdigest() != freeze['fixture_hashes'][name]:
            raise RuntimeError('FIXTURE_HASH')
    deadline=json.loads((BASE/'attempt/T0.json').read_text())['deadline']
    def tick():
        if time.monotonic() >= deadline: raise RuntimeError('DEADLINE')
    tick()
    store=CompactPatList(BASE/'fixtures/fixture.sqlite',BASE/'fixtures/fixture.patlst',tick)
    seq=0
    closed=False
    with (BASE/'attempt/broker_ipc.jsonl').open('x',encoding='ascii') as log:
        try:
            while seq < 80000:
                tick()
                raw=sys.stdin.buffer.readline(65537)
                if not raw or len(raw)>65536 or not raw.endswith(b'\n'):
                    raise RuntimeError('REQUEST_EOF_OR_FRAME')
                request=json.loads(raw)
                if not isinstance(request,list) or len(request)!=3:
                    raise RuntimeError('REQUEST_SHAPE')
                number,op,value=request
                seq+=1
                if type(number) is not int or number!=seq or not isinstance(value,str):
                    raise RuntimeError('REQUEST_ID_OR_TYPE')
                arg=value.encode('ascii')
                if op=='meta' and value=='': answer={'maxlen':store.maxlen}
                elif op=='list':
                    v=store.candidates(arg)
                    answer=None if v is None else [s.decode('ascii') for s in v]
                elif op=='word': answer=1 if store.is_word(arg) else 0
                elif op=='close' and value=='': answer='closed';closed=True
                else: raise RuntimeError('OP_DOMAIN')
                response=json.dumps([seq,answer],ensure_ascii=True,separators=(',',':')).encode()+b'\n'
                if len(response)>65536: raise RuntimeError('RESPONSE_BOUND')
                log.write(json.dumps({'request':request,'response':[seq,answer]},separators=(',',':'))+'\n')
                log.flush()
                sys.stdout.buffer.write(response);sys.stdout.buffer.flush()
                if closed: break
            if not closed: raise RuntimeError('REQUEST_BOUND')
        finally:
            stats=store.stats.copy()
            store.close()
        if not closed: raise RuntimeError('UNCLEAN_CLOSE')
    (BASE/'attempt/broker_terminal.json').write_text(json.dumps(
        {'closed':closed,'requests':seq,'stats':stats},indent=2)+'\n')

if __name__=='__main__': main()
