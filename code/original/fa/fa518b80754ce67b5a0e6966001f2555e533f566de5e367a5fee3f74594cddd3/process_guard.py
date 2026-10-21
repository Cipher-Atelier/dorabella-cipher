"""Own process-identity gate only. No spawn, signals, network or scientific code."""
from pathlib import Path
import os,json
from namespace_view import Stop

def identity(row):
    return (row['visible_pid'],row['starttime'],tuple(row['nspid']),row['pid_namespace'])

def classify(row,scripts,protected,context):
    args=row['cmdline']
    direct=[arg for arg in args if arg in scripts]
    embedded=[arg for arg in args if any(script in arg for script in scripts)]
    if not direct and not embedded:return 'UNRELATED'
    if not row['nspid'] or row['nspid'][0]!=row['visible_pid'] or row['starttime']<=0:
        raise Stop('STOP_MATCH_IDENTITY')
    if row.get('pid') is not None and row['pid']!=row['nspid'][-1]:
        raise Stop('STOP_MATCH_NSPID')
    if identity(row) in protected:return 'CURRENT_SELF_OR_ANCESTOR'
    if direct:return 'BLOCK_EXACT_SCRIPT_ARGV'
    # A carrier is exempt only for this exact invocation, not for a namespace or name alone.
    carrier=(bool(args) and Path(args[0]).name=='codex-linux-sandbox'
        and row.get('argv0_realpath')==context['carrier_executable']
        and row.get('proc_exe') in (None,context['carrier_executable'])
        and args[-4:]==['--','/bin/bash','-lc',context['shell_command']]
        and context['launch_floor_ticks']<=row['starttime']<=context['self_starttime'])
    if carrier:return 'CURRENT_INVOCATION_CARRIER'
    return 'BLOCK_EMBEDDED_UNRESOLVED'

def regression(base):
    cases=json.loads((base/'process_guard_cases.json').read_text())
    outcomes=[]
    for case in cases:
        try:
            actual=classify(case['row'],set(case['scripts']),
                {(x[0],x[1],tuple(x[2]),x[3]) for x in case['protected']},case['context'])
        except Stop as exc:actual=str(exc)
        outcomes.append({'id':case['id'],'expected':case['expected'],'actual':actual})
        if actual!=case['expected']:raise Stop('STOP_PROCESS_GUARD_CASE:'+case['id'])
    return outcomes

def inspect_prior(ns,base,freeze,check):
    st=os.stat(freeze['carrier_executable'])
    if {k:getattr(st,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns')}!=freeze['carrier_file_stat']:
        raise Stop('STOP_CARRIER_EXECUTABLE_IDENTITY')
    launch=json.loads(Path(freeze['launch_evidence_path']).read_text())
    if launch['shell_command']!=freeze['launch_shell_command'] or launch['freeze_sha256']!=freeze['_observed_sha256']:
        raise Stop('STOP_LAUNCH_EVIDENCE')
    if launch['clock_ticks_per_second']!=os.sysconf('SC_CLK_TCK'):
        raise Stop('STOP_LAUNCH_CLOCK')
    floor=launch['launch_floor_ticks']
    if not isinstance(floor,int) or floor<=0 or floor>ns.self_starttime:
        raise Stop('STOP_LAUNCH_STARTTIME')
    scripts=set(freeze['guard_script_paths'])
    protected={identity(ns.self_record),*[identity(row) for row in ns.ancestors]}
    context={'carrier_executable':freeze['carrier_executable'],
        'shell_command':freeze['launch_shell_command'],'launch_floor_ticks':floor,
        'self_starttime':ns.self_starttime}
    output=[]
    for initial in ns.snapshot():
        if not any(any(script in arg for script in scripts) for arg in initial['cmdline']):continue
        check();row=dict(initial);proc=Path('/proc')/str(row['visible_pid'])
        try:row['proc_exe']=os.readlink(proc/'exe');row['exe_read_error']=None
        except (PermissionError,FileNotFoundError,ProcessLookupError) as exc:
            row['proc_exe']=None;row['exe_read_error']=type(exc).__name__
        row['argv0_realpath']=os.path.realpath(row['cmdline'][0]) if row['cmdline'] else None
        after=ns.read_visible(row['visible_pid'])
        if after is None:
            output.append({'classification':'EXITED_DURING_READ','record':row});continue
        if identity(after)!=identity(row) or after['cmdline']!=row['cmdline']:
            raise Stop('STOP_MATCH_CHANGED_DURING_READ')
        decision=classify(row,scripts,protected,context)
        output.append({'classification':decision,'record':row})
    return {'records':output,'blockers':[item for item in output if item['classification'].startswith('BLOCK_')],
        'context':context,'namespace_self':ns.self_record,
        'identity_exclusion':'visible_pid + starttime + full NSpid + pid_namespace; no foreign namespace blanket exclusion'}
