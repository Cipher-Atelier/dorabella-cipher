"""TS-RC-v1: one attempt, original Perl unchanged. Standard library only.

No target, retry, resume, installation, model change or score implementation.
The only two possible executable children are the pinned core probe and MCTS,
each under the pinned GNU timeout/env/prlimit chain. Author date is unchanged.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tarfile
import time
import traceback

BASE = Path('/workspace/scratch/f24f8fae4976')
IMPL = BASE / 'TREESEARCH_first_control_implementation_v1'
ROOT = BASE / 'TREESEARCH_first_control_v1'
ATT = ROOT / 'attempt'
CODE = BASE / 'TREESEARCH_feasibility_20261017/original'
PLAN = BASE / 'TREESEARCH_resource_plan_evidence_20261017/PLAN_MANIFEST.json'
PLAN_HASH = '7a713995f66a6f7fa0d66269b60e3bfab71ccaccf8dacd736172ec4d19937940'
CG = Path('/sys/fs/cgroup')
CAP = 1048576
READY = b'Ready to go! Timer resetting.'
ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TZ': 'UTC'}
EXPECTED_LIMITS = {'Max cpu time': (150, 152), 'Max file size': (16777216, 16777216),
                   'Max core file size': (0, 0), 'Max open files': (64, 64),
                   'Max address space': (4294967296, 4294967296)}


class Stop(Exception):
    pass


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def dump(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def digest(path, tick=lambda: None):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while b := f.read(1048576):
            h.update(b)
            tick()
    return h.hexdigest()


def proc(pid):
    p = Path('/proc') / str(pid)
    try:
        stat = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'state': stat[0], 'ppid': int(stat[1]),
                'pgid': int(stat[2]), 'session': int(stat[3]), 'starttime': int(stat[19]),
                'cmdline': (p / 'cmdline').read_bytes().decode(errors='replace').split('\0')[:-1]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def scan(pgid=None, matching=False):
    found = []
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():
            continue
        r = proc(p.name)
        if r is None or r['pid'] == os.getpid():
            continue
        if pgid is not None and r['pgid'] == pgid:
            found.append(r)
        if matching and any(Path(a).name in {'masc_solver_mcts.pl',
                           'masc_solver_beamsearch.pl', 'run_ts_rc.py'} for a in r['cmdline']):
            found.append(r)
    return found


def memory():
    info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return {'utc': utc(), 'monotonic': time.monotonic(),
            'cgroup': Path('/proc/self/cgroup').read_text(),
            'max': int((CG / 'memory.max').read_text()),
            'current': int((CG / 'memory.current').read_text()),
            'events': {k: int(v) for k, v in (line.split() for line in (CG / 'memory.events').read_text().splitlines())},
            'MemAvailable_bytes': int(info['MemAvailable'].split()[0]) * 1024}


def limits_ok(text):
    got = {}
    for name, expected in EXPECTED_LIMITS.items():
        m = re.search(r'^' + re.escape(name) + r'\s+(\d+)\s+(\d+)\s', text, re.M)
        got[name] = list(map(int, m.groups())) if m else None
        if got[name] != list(expected):
            raise Stop('STOP_LIMITS: ' + name + ': ' + repr(got[name]))
    return got


class Attempt:
    def __init__(self, t0, wall):
        self.t0, self.deadline = t0, t0 + 180
        self.receipt = {'schema': 'TS-RC-v1-execution', 'attempt_t0_utc': wall,
                        'attempt_t0_monotonic': t0, 'deadline_monotonic': self.deadline,
                        'allowed_stages': ['runtime_probe', 'model_load', 'README87_control'],
                        'target_allowed': False, 'retry_resume_allowed': False,
                        'supervisor_pid': os.getpid(), 'supervisor_pgid': os.getpgrp(),
                        'python': sys.version, 'python_path': sys.executable,
                        'phases': [], 'author_launch_count': 0, 'control_feed_count': 0}
        self.log = (ATT / 'events.jsonl').open('x', encoding='utf-8')
        self.samples = (ATT / 'resource_samples.jsonl').open('x', encoding='utf-8')
        self.initial_mem = memory()
        self.last_sample = 0.0
        self.record('T0', self.receipt)
        self.receipt['resource_before'] = self.initial_mem

    def record(self, event, data=None):
        self.log.write(json.dumps({'utc': utc(), 'elapsed': time.monotonic()-self.t0,
                                   'event': event, 'data': data}, ensure_ascii=False) + '\n')
        self.log.flush()

    def resource_gate(self):
        m = memory()
        self.record('start_resource_gate', m)
        if m['max']-m['current'] < 5368709120 or m['MemAvailable_bytes'] < 5368709120:
            raise Stop('NOT_STARTED_RESOURCE: less than 5 GiB headroom')
        self.tick(force=True)

    def tick(self, force=False):
        now = time.monotonic()
        if now >= self.deadline:
            raise Stop('STOP_GLOBAL_DEADLINE')
        if force or now-self.last_sample >= .1:
            m = memory()
            self.samples.write(json.dumps(m) + '\n')
            self.samples.flush()
            self.last_sample = now
            if m['current'] >= 7516192768 or any(m['events'].get(k, 0) > self.initial_mem['events'].get(k, 0)
                                                for k in ('max', 'oom', 'oom_kill', 'oom_group_kill')):
                raise Stop('STOP_RESOURCE: cgroup threshold/event')

    def prepare(self, freeze_sha):
        self.resource_gate()
        fpath = IMPL / 'FREEZE.json'
        if digest(fpath, self.tick) != freeze_sha:
            raise Stop('STOP_FREEZE_HASH')
        freeze = json.loads(fpath.read_bytes())
        checks = []
        items = freeze['files'] + [{'path': str(PLAN), 'sha256': PLAN_HASH}]
        for item in items:
            actual = digest(Path(item['path']), self.tick)
            checks.append({'path': item['path'], 'expected': item['sha256'], 'actual': actual})
            if actual != item['sha256']:
                raise Stop('STOP_IDENTITY: ' + item['path'])
        plan = json.loads(PLAN.read_bytes())
        if plan['source_commit'] != '2c7ad49cd4f4fa852168a8ce295bf739bf076adc':
            raise Stop('STOP_COMMIT')
        for item in plan['source_and_model_downloads']['files'] + plan['system_file_hashes_not_runtime_test']:
            p = Path(item['path']) if item['path'].startswith('/') else CODE / item['path']
            actual = digest(p, self.tick)
            checks.append({'path': str(p), 'expected': item['sha256'], 'actual': actual})
            if actual != item['sha256']:
                raise Stop('STOP_IDENTITY: ' + str(p))
        dump(ATT / 'identity_checks.json', checks)
        if (ROOT / 'Modules').exists() or (ROOT / 'Modules').is_symlink():
            raise Stop('STOP_MODULE_PATH')
        (ROOT / 'work').mkdir()
        (ROOT / 'model').mkdir()
        members = {r['member']: r for r in plan['model_members']}
        extracted = []
        for archive in dict.fromkeys(r['archive'] for r in members.values()):
            with tarfile.open(CODE / archive, mode='r|gz') as tar:
                for entry in tar:
                    self.tick()
                    r = members.get(entry.name)
                    if r is None or r['archive'] != archive or not entry.isfile() or entry.size != r['bytes']:
                        raise Stop('STOP_ARCHIVE_MEMBER: ' + entry.name)
                    h, n = hashlib.sha256(), 0
                    with tar.extractfile(entry) as src, (ROOT / 'model' / entry.name).open('xb') as dest:
                        while b := src.read(1048576):
                            dest.write(b)
                            h.update(b)
                            n += len(b)
                            self.tick()
                    actual = h.hexdigest()
                    extracted.append({'member': entry.name, 'bytes': n, 'sha256': actual})
                    if n != r['bytes'] or actual != r['sha256']:
                        raise Stop('STOP_MEMBER_HASH: ' + entry.name)
        if len(extracted) != 7 or {r['member'] for r in extracted} != set(members):
            raise Stop('STOP_MEMBER_COUNT')
        dump(ATT / 'extracted_models.json', extracted)
        self.record('preparation_completed', {'model_bytes': sum(r['bytes'] for r in extracted)})
        return plan

    def control(self, spec):
        text = ''.join(r['literal']*r['repeat'] for r in spec['plaintext_concatenation'])
        a, b = spec['plaintext_alphabet'], spec['ciphertext_alphabet']
        if len(text) != 87 or len(a) != 26 or set(a) != set(b) or len(set(b)) != 26 or not set(text) <= set(a):
            raise Stop('STOP_CONTROL_SPEC')
        forward = dict(zip(a, b))
        cipher = ''.join(forward[c] for c in text)
        positions = [{'position': i+1, 'plaintext': p, 'ciphertext': c,
                      'inverse': a[b.index(c)], 'match': a[b.index(c)] == p}
                     for i, (p, c) in enumerate(zip(text, cipher))]
        if not all(r['match'] for r in positions):
            raise Stop('STOP_CONTROL_INVERSE')
        (ATT / 'truth.txt').write_bytes(text.encode()+b'\n')
        (ATT / 'ciphertext.txt').write_bytes(cipher.encode()+b'\n')
        dump(ATT / 'control_identity.json', {'id': spec['id'], 'plaintext': text, 'ciphertext': cipher,
              'plaintext_alphabet': a, 'ciphertext_alphabet': b, 'positions': positions,
              'truth_file_sha256': digest(ATT / 'truth.txt'), 'cipher_file_sha256': digest(ATT / 'ciphertext.txt'),
              'input_bytes_including_LF': 88, 'truth_inverse_matches': 87,
              'independent_validation': False})
        self.receipt['control_materialized'] = True
        self.tick()
        return text, cipher

    def execute(self, name, argv, cipher=None):
        self.tick(force=True)
        allowance = min(5, self.deadline-time.monotonic()) if name == 'runtime' else self.deadline-time.monotonic()
        duration = math.floor(allowance*1000)/1000
        if duration <= 0:
            raise Stop('STOP_NO_TIME')
        cmd = ['/usr/bin/timeout', '--signal=TERM', '--kill-after=2s', f'{duration:.3f}s'] + argv
        phase = {'name': name, 'argv': cmd, 'cwd': str(ROOT / 'work'), 'outer_env': ENV,
                 'start_utc': utc(), 'start_monotonic': time.monotonic(), 'stdin_bytes': 0,
                 'timeout_seconds': duration, 'process_samples': [], 'signals': []}
        self.receipt['phases'].append(phase)
        self.record('launch', phase)
        print(json.dumps({'phase': name, 'event': 'launch', 'utc': phase['start_utc']}), flush=True)
        p = subprocess.Popen(cmd, cwd=ROOT / 'work', env=ENV, shell=False,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             close_fds=True)
        if name == 'author':
            self.receipt['author_launch_count'] += 1
        phase['timeout_pid'] = p.pid
        phase['expected_pgid'] = p.pid
        outputs = {'stdout': bytearray(), 'stderr': bytearray()}
        files = {k: (ATT / f'{name}.{k}.bin').open('xb') for k in outputs}
        sel = selectors.DefaultSelector()
        for stream, key in ((p.stdout, 'stdout'), (p.stderr, 'stderr')):
            os.set_blocking(stream.fileno(), False)
            sel.register(stream, selectors.EVENT_READ, key)
        verified_group = False
        reason = None
        terminated_at = None
        killed = False
        author_identity = None
        phase_deadline = min(self.deadline, phase['start_monotonic']+(5 if name == 'runtime' else 60))
        fed = False
        last_proc_sample = 0.0

        def signal_group(sig):
            nonlocal verified_group
            r = proc(p.pid)
            if r and r['pgid'] == p.pid and p.pid != os.getpgrp():
                verified_group = True
            members_now = scan(pgid=p.pid)
            # timeout starts this group; never signal our inherited group.
            if verified_group and p.pid != os.getpgrp():
                if members_now:
                    try:
                        os.killpg(p.pid, sig)
                    except ProcessLookupError:
                        pass
                phase['signals'].append({'utc': utc(), 'signal': int(sig), 'pgid': p.pid, 'members': members_now})
            elif p.poll() is None:
                # No confirmed group: terminate only the known live direct child,
                # mark uncertainty, never feed input; its timeout remains bounded.
                try:
                    p.send_signal(sig)
                except ProcessLookupError:
                    pass
                phase['signals'].append({'utc': utc(), 'signal': int(sig), 'direct_pid_only': p.pid})

        try:
            while True:
                now = time.monotonic()
                rc = p.poll()
                try:
                    if reason is None:
                        self.tick()
                        if now >= phase_deadline:
                            raise Stop('STOP_' + ('RUNTIME' if name == 'runtime' else ('CONTROL' if fed else 'MODEL_LOAD')) + '_DEADLINE')
                    if now-last_proc_sample >= .1:
                        members_now = scan(pgid=p.pid)
                        r = proc(p.pid)
                        if r and r['pgid'] == p.pid and p.pid != os.getpgrp():
                            verified_group = True
                        details = []
                        for member in members_now:
                            try:
                                raw = (Path('/proc') / str(member['pid']) / 'status').read_text()
                                member['memory_status'] = [line for line in raw.splitlines() if line.startswith(('VmRSS:', 'VmHWM:', 'VmSize:', 'VmPeak:'))]
                            except (FileNotFoundError, ProcessLookupError):
                                pass
                            details.append(member)
                            if str(CODE / 'masc_solver_mcts.pl') in member['cmdline'] and member['cmdline'][0] == '/usr/bin/perl':
                                author_identity = member
                        phase['process_samples'].append({'elapsed': now-self.t0, 'members': details})
                        last_proc_sample = now
                    for key, _ in sel.select(.1):
                        try:
                            data = os.read(key.fileobj.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not data:
                            sel.unregister(key.fileobj)
                            continue
                        out = key.data
                        room = max(0, CAP-len(outputs[out]))
                        files[out].write(data[:room])
                        files[out].flush()
                        outputs[out].extend(data[:room])
                        if len(data) > room:
                            phase[out + '_discarded_over_cap_bytes'] = phase.get(out + '_discarded_over_cap_bytes', 0) + len(data)-room
                            raise Stop('STOP_OUTPUT_LIMIT_' + out)
                    if reason is None and outputs['stderr']:
                        raise Stop('STOP_' + name.upper() + '_STDERR')
                    if name == 'author' and reason is None and not fed and READY in outputs['stdout']:
                        if outputs['stdout'].count(READY) != 1 or not verified_group or p.poll() is not None or author_identity is None:
                            raise Stop('STOP_READY_IDENTITY')
                        current = proc(author_identity['pid'])
                        if not current or current['starttime'] != author_identity['starttime'] or current['pgid'] != p.pid or current['state'] == 'Z':
                            raise Stop('STOP_AUTHOR_IDENTITY')
                        raw_limits = (Path('/proc') / str(current['pid']) / 'limits').read_text()
                        phase['author_limits'] = limits_ok(raw_limits)
                        (ATT / 'author.proc_limits.txt').write_text(raw_limits)
                        phase['author_identity_before_feed'] = current
                        self.tick(force=True)
                        if time.monotonic() >= phase_deadline:
                            raise Stop('STOP_MODEL_LOAD_DEADLINE')
                        phase['ready_utc'] = utc()
                        phase['ready_monotonic'] = time.monotonic()
                        phase['model_load_elapsed'] = phase['ready_monotonic']-phase['start_monotonic']
                        phase['feed_utc'] = utc()
                        phase['feed_monotonic'] = time.monotonic()
                        p.stdin.write(cipher.encode('ascii')+b'\n')
                        p.stdin.flush()
                        p.stdin.close()
                        fed = True
                        phase['stdin_bytes'] = 88
                        self.receipt['control_feed_count'] += 1
                        phase_deadline = min(self.deadline, phase['feed_monotonic']+120)
                        self.record('control_fed_once', {'pid': current['pid'], 'bytes': 88, 'phase_deadline': phase_deadline})
                        print(json.dumps({'phase': 'control', 'event': 'fed_once', 'utc': phase['feed_utc']}), flush=True)
                except Exception as exc:
                    if reason is None:
                        reason = str(exc) if isinstance(exc, Stop) else type(exc).__name__ + ': ' + str(exc)
                        phase['failure'] = reason
                        self.record('stop', {'phase': name, 'reason': reason})
                        signal_group(signal.SIGTERM)
                        terminated_at = time.monotonic()
                if reason is not None and terminated_at is not None and time.monotonic()-terminated_at >= 2 and not killed:
                    signal_group(signal.SIGKILL)
                    killed = True
                if p.poll() is not None and not sel.get_map():
                    break
                # A watchdog/host failure is not silently treated as a completed run.
                if time.monotonic() > self.deadline+7:
                    if not killed:
                        signal_group(signal.SIGKILL)
                    reason = reason or 'UNKNOWN_WATCHDOG_TERMINATION'
                    break
        finally:
            if p.poll() is None:
                signal_group(signal.SIGTERM)
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    signal_group(signal.SIGKILL)
                    try:
                        p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        reason = 'UNKNOWN_DIRECT_CHILD_NOT_REAPED'
            else:
                p.wait()
            remaining = scan(pgid=p.pid)
            if remaining:
                signal_group(signal.SIGTERM)
                end = time.monotonic()+2
                while remaining and time.monotonic() < end:
                    time.sleep(.1)
                    remaining = scan(pgid=p.pid)
                if remaining:
                    signal_group(signal.SIGKILL)
                    end = time.monotonic()+2
                    while remaining and time.monotonic() < end:
                        time.sleep(.1)
                        remaining = scan(pgid=p.pid)
                if remaining:
                    reason = 'UNKNOWN_GROUP_MEMBERS_REMAIN'
            for f in files.values():
                f.flush()
                os.fsync(f.fileno())
                f.close()
            sel.close()
            for stream in (p.stdin, p.stdout, p.stderr):
                if stream and not stream.closed:
                    stream.close()
            phase.update({'end_utc': utc(), 'end_monotonic': time.monotonic(),
                          'observed_exit': p.returncode, 'group_verified_while_live': verified_group,
                          'terminal_group_scan_utc': utc(), 'terminal_group_members': remaining,
                          'terminal_evidence': p.returncode is not None and not remaining,
                          'stdout_bytes': len(outputs['stdout']), 'stderr_bytes': len(outputs['stderr']),
                          'failure': reason})
            phase['elapsed'] = phase['end_monotonic']-phase['start_monotonic']
            if fed:
                phase['control_elapsed'] = phase['end_monotonic']-phase['feed_monotonic']
            dump(ATT / f'{name}.phase.json', phase)
            self.record('phase_terminal', {'name': name, 'exit': p.returncode, 'failure': reason, 'group_members': remaining})
        if not phase['terminal_evidence']:
            raise Stop('UNKNOWN_TERMINATION: ' + name)
        if reason:
            raise Stop(reason)
        if p.returncode != 0:
            raise Stop('STOP_' + name.upper() + '_EXIT_' + str(p.returncode))
        self.tick()
        output = bytes(outputs['stdout']).decode('utf-8', errors='strict')
        if name == 'runtime':
            if output.splitlines()[:2] != ['v5.38.2', 'x86_64-linux-gnu-thread-multi']:
                raise Stop('STOP_RUNTIME_IDENTITY')
            phase['verified_limits'] = limits_ok(output)
            if phase['elapsed'] > 5:
                raise Stop('STOP_RUNTIME_TIME')
        elif not fed:
            raise Stop('STOP_NO_CONTROL_FEED')
        return output

    def verify_result(self, stdout, truth, cipher):
        self.tick()
        solutions = re.findall(r'^SOLUTION:\t([^\r\n]*)$', stdout, re.M)
        starts = re.findall(r'Iteration (\d+) starting\.', stdout)
        completed = re.findall(r'Iteration (\d+) complete\.', stdout)
        children = re.findall(r'Expansion -- Found (\d+) total children\.', stdout)
        summary = {'solution_count': len(solutions), 'iteration_starts': starts,
                   'iteration_completions': completed, 'reported_children': list(map(int, children)),
                   'exact_score_evaluation_count': 'not instrumented; no source modifications',
                   'ready_count': stdout.count(READY.decode())}
        self.receipt['workload'] = summary
        if len(solutions) != 1 or starts != ['1', '2'] or completed != ['1', '2'] or summary['ready_count'] != 1:
            raise Stop('STOP_INCOMPLETE_OUTPUT_ACCOUNTING')
        candidate = solutions[0]
        if not re.fullmatch('[a-z]{87}', candidate):
            raise Stop('STOP_CANDIDATE_FORMAT')
        dec, enc, violations = {}, {}, []
        for i, (c, p) in enumerate(zip(cipher, candidate), 1):
            if c in dec and dec[c] != p:
                violations.append({'position': i, 'kind': 'inconsistent_mapping'})
            if p in enc and enc[p] != c:
                violations.append({'position': i, 'kind': 'noninjective_mapping'})
            dec[c], enc[p] = p, c
        positions = [{'position': i+1, 'ciphertext': c, 'candidate': p, 'truth': t,
                      'reencoded': enc[p], 'inverse_match': enc[p] == c, 'truth_match': p == t}
                     for i, (c, p, t) in enumerate(zip(cipher, candidate, truth))]
        proof = {'candidate': candidate, 'ciphertext_to_candidate': dec, 'candidate_to_ciphertext': enc,
                 'mapping_violations': violations, 'positions': positions,
                 'inverse_matches': sum(x['inverse_match'] for x in positions),
                 'exact_matches': sum(x['truth_match'] for x in positions),
                 'exact_recovery': candidate == truth,
                 'unobserved_alphabet_slots': 'not inferred from output or claimed as recovered',
                 'technical_control_only': True}
        dump(ATT / 'candidate_verification.json', proof)
        self.receipt['verification'] = {k: v for k, v in proof.items() if k not in {'positions', 'ciphertext_to_candidate', 'candidate_to_ciphertext'}}
        if violations or proof['inverse_matches'] != 87:
            raise Stop('STOP_CANDIDATE_INVERSE')
        self.tick()
        return 'TECHNICAL_CONTROL_RECOVERED' if candidate == truth else 'CONTROL_NOT_RECOVERED'

    def finish(self, status, error=None):
        if 'workload' not in self.receipt:
            source = ATT / 'author.stdout.bin'
            raw = source.read_text(errors='replace') if source.exists() else ''
            self.receipt['workload'] = {
                'ready_count': raw.count(READY.decode()),
                'iteration_starts': re.findall(r'Iteration (\d+) starting\.', raw),
                'iteration_completions': re.findall(r'Iteration (\d+) complete\.', raw),
                'reported_children': list(map(int, re.findall(r'Expansion -- Found (\d+) total children\.', raw))),
                'solution_count': len(re.findall(r'^SOLUTION:\t', raw, re.M)),
                'exact_score_evaluation_count': 0 if self.receipt['control_feed_count'] == 0 else 'not instrumented',
                'basis': 'saved stdout and feed receipt only; no score recomputation'}
        self.receipt.update({'status': status, 'error': error, 'end_utc': utc(),
                             'end_monotonic': time.monotonic(), 'resource_after': memory()})
        self.receipt['elapsed_including_preparation'] = self.receipt['end_monotonic']-self.t0
        self.receipt['live_matching_processes_at_end'] = scan(matching=True)
        if self.receipt['live_matching_processes_at_end']:
            self.receipt['status'] = 'UNKNOWN_LIVE_PROCESS'
        self.record('terminal', self.receipt)
        self.log.flush()
        self.samples.flush()
        os.fsync(self.log.fileno())
        os.fsync(self.samples.fileno())
        self.log.close()
        self.samples.close()
        dump(ATT / 'receipt.json', self.receipt)
        hashes = {str(p.relative_to(ATT)): digest(p) for p in sorted(ATT.rglob('*')) if p.is_file()}
        dump(ATT / 'terminal_hashes.json', hashes)
        print(json.dumps({'status': self.receipt['status'], 'elapsed': self.receipt['elapsed_including_preparation'],
                          'author_launches': self.receipt['author_launch_count'],
                          'control_feeds': self.receipt['control_feed_count'], 'error': error}), flush=True)


def main():
    # Exclusive root and attempt are never removed or reused.
    t0, wall = time.monotonic(), utc()
    prior = scan(matching=True)
    if ROOT.exists() or ROOT.is_symlink() or prior:
        print(json.dumps({'status': 'REFUSED_PRIOR_ATTEMPT_OR_PROCESS', 'root_exists': ROOT.exists(), 'processes': prior}), flush=True)
        return 3
    ROOT.mkdir()
    ATT.mkdir()
    dump(ATT / 'T0.json', {'utc': wall, 'monotonic': t0, 'deadline_monotonic': t0+180,
                          'prior_processes': prior, 'root_exclusive': True})
    attempt = Attempt(t0, wall)
    status, error = 'UNKNOWN', None
    try:
        if len(sys.argv) != 2:
            raise Stop('STOP_EXPECTED_FREEZE_SHA_ARGUMENT')
        plan = attempt.prepare(sys.argv[1])
        truth, cipher = attempt.control(plan['control_spec'])
        attempt.execute('runtime', plan['runtime_probe_argv'])
        attempt.resource_gate()
        output = attempt.execute('author', plan['author_argv'], cipher)
        status = attempt.verify_result(output, truth, cipher)
    except Exception as exc:
        error = str(exc)
        status = 'UNKNOWN' if 'UNKNOWN' in error else ('NOT_STARTED_RESOURCE' if error.startswith('NOT_STARTED_RESOURCE') else 'STOP')
        (ATT / 'exception.txt').write_text(traceback.format_exc())
    finally:
        attempt.finish(status, error)
    return 0 if attempt.receipt['status'] in {'TECHNICAL_CONTROL_RECOVERED', 'CONTROL_NOT_RECOVERED'} else 2


if __name__ == '__main__':
    sys.exit(main())
