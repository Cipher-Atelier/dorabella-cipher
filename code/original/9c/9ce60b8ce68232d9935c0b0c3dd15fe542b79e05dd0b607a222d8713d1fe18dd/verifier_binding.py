"""Prepared observed call of exact original readback source and fail-closed seal binding."""
from pathlib import Path
import json,time,types,marshal
from evidence_io import ReadWitness,need,digest,read_snapshot,atomic_json,CAP

def read_object(path,tick):
    need(path.stat().st_size<=CAP,'OBJECT_BOUND');raw=path.read_bytes();s=read_snapshot(path,tick)
    need(digest(raw)==s['sha256'] and len(raw)==s['bytes'],'OBJECT_READ_CHANGED')
    return json.loads(raw),s

def observed_real(base,tick):
    base=Path(base);attempt=base/'attempt';source=base/'readback.py'
    freeze=json.loads((base/'FREEZE.json').read_text());raw=source.read_bytes()
    need(digest(raw)==freeze['diagnostic']['original_readback_sha256'],'ORIGINAL_VERIFIER_HASH')
    # Compile exact authenticated bytes, avoiding ambiguity from an imported cached bytecode file.
    module=types.ModuleType('observed_original_readback');module.__file__=str(source)
    code=compile(raw,str(source),'exec');exec(code,module.__dict__)
    witness=ReadWitness(tick);module.iter_rows=witness.iter_rows;module.load=witness.load
    receipt={'source_path':str(source),'source_sha256':digest(raw),'loaded_code_sha256':digest(marshal.dumps(code)),
        'real_code_filename':module.real.__code__.co_filename,'real_code_sha256':digest(marshal.dumps(module.real.__code__)),
        'io_substitutions':['iter_rows','load'],'call_start_monotonic':time.monotonic(),'outcome':'NOT_RETURNED'}
    try:
        value=module.real();receipt.update(outcome='RETURNED',return_value=value,return_monotonic=time.monotonic())
        need(value['status']=='PASS_FINITE_COMBINED_TRANSPORT','ORIGINAL_VERIFIER_STATUS')
        need(all(r['EOF'] and r['error'] is None for r in witness.receipts),'VERIFIER_INCOMPLETE_READ')
        return value
    except BaseException as exc:
        receipt['exception']=repr(exc);receipt['outcome']='RAISED' if 'return_value' not in receipt else 'RETURNED_BUT_BINDING_REJECTED';raise
    finally:
        witness.finish()
        receipt['reads']=witness.receipts;receipt['finish_monotonic']=time.monotonic()
        atomic_json(attempt/'verifier_call_receipt.json',receipt)

def _final_binding(base,terminal,tick,observations):
    base=Path(base);a=base/'attempt'
    need(len(terminal)==2 and all(t['exit']==0 and t['group']==[] for t in terminal),'WAIT_TERMINAL')
    v,vs=read_object(a/'verifier_call_receipt.json',tick);observations.append(vs)
    wait,waits=read_object(a/'wait_before_verifier.json',tick);observations.append(waits)
    need(len(wait['terminal_phases'])==2 and {p['terminal'] for p in wait['terminal_phases']}=={'real_broker','real_perl'}
         and all(p['exit']==0 and p['group']==[] for p in wait['terminal_phases']),'WAIT_RECEIPT')
    need(v['outcome']=='RETURNED' and v['return_value']['status']=='PASS_FINITE_COMBINED_TRANSPORT','VERIFIER_RETURN')
    bound=[]
    for entry in v['reads']:
        tick();need(entry['EOF'] and entry['error'] is None,'VERIFIER_READ_COMPLETE');s=read_snapshot(entry['path'],tick);observations.append(s)
        need(s['sha256']==entry['sha256'] and s['bytes']==entry['bytes'] and s['before']==entry['after'],'VERIFIER_SEAL_MISMATCH')
        bound.append(s)
    journal=a/'real_broker_ipc.jsonl';writer,ws=read_object(a/'real_broker_ipc_writer_completion.json',tick);observations.append(ws)
    need(writer['status']=='WRITER_CLOSED_CONSISTENT' and writer['records']==2244,'WRITER_COMPLETION')
    seen=[r for r in v['reads'] if r['path']==str(journal)]
    need(len(seen)==1 and seen[0]['records']==2244,'VERIFIER_JOURNAL_CARDINALITY')
    j=read_snapshot(journal,tick);observations.append(j)
    need(j['sha256']==writer['intended_sha256']==writer['physical_incremental_sha256']==writer['closed_fd_sha256']==seen[0]['sha256'],'WRITER_READER_SEAL_HASH')
    need(j['bytes']==writer['bytes']==seen[0]['bytes'] and j['newlines']==2244 and j['last_newline'],'WRITER_READER_SEAL_SIZE')
    need(j['before']==writer['final']==seen[0]['before']==seen[0]['after'],'WRITER_READER_SEAL_IDENTITY')
    need(writer['close_completed_monotonic']<=writer['completion_monotonic']<v['call_start_monotonic']<=v['return_monotonic'],'ORDER_CLOSE_VERIFY')
    need(writer['completion_monotonic']<=wait['monotonic']<=v['call_start_monotonic'],'ORDER_CLOSE_WAIT_VERIFY')
    audit=read_snapshot(writer['audit_path'],tick);observations.append(audit)
    need(audit['sha256']==writer['audit_sha256'] and audit['bytes']==writer['audit_bytes'],'WRITER_AUDIT_HASH')
    # No recomputation of language or model values; bind already validated byte streams.
    result={'status':'BOUND_COMPLETE','writer':writer,'verifier_return':v['return_value'],
            'bound_reads':bound,'journal':j,'writer_audit':audit,'receipt_snapshots':[vs,ws,waits,audit],'monotonic':time.monotonic()}
    atomic_json(a/'seal_binding.json',result)
    return result

def final_binding(base,terminal,tick):
    observations=[];error=None
    try:return _final_binding(base,terminal,tick,observations)
    except BaseException as exc:error=repr(exc);raise
    finally:
        atomic_json(Path(base)/'attempt/seal_observations.json',{'observations':observations,'error':error,'monotonic':time.monotonic()})

def check_publication(base,file_hashes,tick):
    a=Path(base)/'attempt';binding=json.loads((a/'seal_binding.json').read_text())
    v=json.loads((a/'verifier_call_receipt.json').read_text())
    need(binding['status']=='BOUND_COMPLETE','BINDING_STATUS')
    for e in binding['bound_reads']+binding['receipt_snapshots']:
        s=read_snapshot(e['path'],tick)
        need(s['sha256']==e['sha256'] and s['bytes']==e['bytes'] and s['before']==e['after'],'POST_BIND_CHANGED')
        p=Path(e['path'])
        if p.parent==a:need(file_hashes[p.name]==e['sha256'],'SEALED_HASH_DIFFERS')
    for name in ['verifier_call_receipt.json','real_broker_ipc_writer_completion.json','real_broker_ipc_writer_events.jsonl','seal_binding.json']:
        need(read_snapshot(a/name,tick)['sha256']==file_hashes[name],'RECEIPT_SEAL_CHANGED')
    need(v['outcome']=='RETURNED','FINAL_RETURN_STATUS')
    return True
