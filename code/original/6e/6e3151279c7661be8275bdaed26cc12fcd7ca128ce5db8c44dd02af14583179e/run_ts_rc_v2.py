"""TS-RC-v2: namespace-aware supervisor; original Perl/argv unchanged.

No target, retry, resume, installation, model change or score implementation.
The bounded supervisor probe uses only this stdlib file. Core probe and MCTS
retain the pinned GNU timeout/env/prlimit chain. Author date is unchanged.
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
IMPL = BASE / 'TREESEARCH_first_control_implementation_v2'
ROOT = BASE / 'TREESEARCH_first_control_v1'
RUNROOT = BASE / 'TREESEARCH_first_control_v2'
ATT = RUNROOT / 'attempt'
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


class NamespaceView:
    """Keep proc-visible IDs and syscall-local IDs separate, never guess equality.

    Only exact membership in our PID namespace permits local signal addressing.
    Outer namespaces are still inspected for prior matching commands. Sources
    never create PID namespaces/sessions. Unexpected namespace/ancestry => STOP.
    """
    def __init__(self):
        self.visible_self = int(os.readlink('/proc/self'))
        self.ns = os.readlink('/proc/self/ns/pid')
        if self.ns != os.readlink('/proc/self/ns/pid_for_children'):
            raise Stop('STOP_CHILD_PID_NAMESPACE_DIFFERS')
        me = self.read_visible(self.visible_self)
        if me is None or me['nspid'][-1] != os.getpid() or me['nspgid'][-1] != os.getpgrp() or me['nssid'][-1] != os.getsid(0):
            raise Stop('STOP_SELF_NAMESPACE_MAPPING')
        self.depth = len(me['nspid']) - 1
        self.self_starttime = me['starttime']
        self.ancestors = []
        r, seen = me, set()
        while r and r['visible_ppid']:
            vp = r['visible_ppid']
            if vp in seen or len(seen) >= 1024:
                raise Stop('STOP_ANCESTOR_CHAIN')
            seen.add(vp)
            r = self.read_visible(vp)
            if r:
                self.ancestors.append({k: r[k] for k in ('visible_pid', 'visible_ppid', 'starttime', 'pid_namespace', 'nspid')})
        self.self_record = self.localize(me)

    @staticmethod
    def read_visible(vpid):
        p = Path('/proc') / str(vpid)
        try:
            raw = (p / 'stat').read_text()
            f = raw.rsplit(')', 1)[1].split()
            s = dict(line.split(':', 1) for line in (p / 'status').read_text().splitlines())
            try:
                ns = os.readlink(p / 'ns/pid')
            except (FileNotFoundError, PermissionError):
                ns = None  # Preserve zombies in terminal evidence, do not hide them.
            args = (p / 'cmdline').read_bytes().decode(errors='replace').split('\0')[:-1]
            f2 = (p / 'stat').read_text().rsplit(')', 1)[1].split()
            if f[19] != f2[19]:
                raise Stop('STOP_PID_REUSE_DURING_READ')
            # Identity is stable across exec; refresh mutable state/group/parent.
            nspid = list(map(int, s['NSpid'].split()))
            nspgid = list(map(int, s['NSpgid'].split()))
            nssid = list(map(int, s['NSsid'].split()))
            if nspid[0] != int(vpid) or int(s['Pid']) != int(vpid):
                raise Stop('STOP_PROC_PID_INCONSISTENCY')
            # A setpgid race is not a usable identity sample. Next poll may read it.
            if nspgid[0] != int(f2[2]) or nssid[0] != int(f2[3]) or int(s['PPid']) != int(f2[1]):
                return None
            return {'visible_pid': int(vpid), 'visible_ppid': int(f2[1]),
                    'visible_pgid': int(f2[2]), 'visible_session': int(f2[3]),
                    'state': f2[0], 'starttime': int(f2[19]), 'pid_namespace': ns,
                    'nspid': nspid, 'nspgid': nspgid, 'nssid': nssid, 'cmdline': args,
                    'memory_status': [line for line in (p / 'status').read_text().splitlines()
                                      if line.startswith(('VmRSS:', 'VmHWM:', 'VmSize:', 'VmPeak:'))]}
        except (FileNotFoundError, ProcessLookupError):
            return None

    def localize(self, r):
        r = dict(r)
        r.update(pid=None, pgid=None, session=None)
        if r['pid_namespace'] == self.ns:
            if any(len(r[k]) != self.depth+1 for k in ('nspid', 'nspgid', 'nssid')):
                raise Stop('STOP_NAMESPACE_VECTOR_DEPTH')
            r.update(pid=r['nspid'][self.depth], pgid=r['nspgid'][self.depth], session=r['nssid'][self.depth])
        return r

    def snapshot(self):
        records = []
        for p in Path('/proc').iterdir():
            if p.name.isdecimal():
                r = self.read_visible(p.name)
                if r:
                    records.append(self.localize(r))
        return records

    def by_local(self, pid):
        matches = [r for r in self.snapshot() if r['pid'] == pid]
        if len(matches) > 1:
            raise Stop('STOP_AMBIGUOUS_LOCAL_PID')
        return matches[0] if matches else None

    def group(self, anchor, known):
        records = self.snapshot()
        by_visible = {r['visible_pid']: r for r in records}
        a = by_visible.get(anchor['visible_pid'])
        if a and a['starttime'] != anchor['starttime']:
            raise Stop('STOP_ANCHOR_PID_REUSED')
        result = [r for r in records if r['visible_pgid'] == anchor['visible_pid']]
        for r in result:
            dead_known = r['state'] == 'Z' and (r['visible_pid'], r['starttime']) in known
            if dead_known and r['pid_namespace'] is None:
                r.update(pid=r['nspid'][self.depth], pgid=r['nspgid'][self.depth], session=r['nssid'][self.depth])
                r['namespace_evidence'] = 'previously observed identity; now zombie'
            if (r['pid_namespace'] != self.ns and not dead_known) or r['pgid'] != anchor['pid'] or r['pid'] is None:
                raise Stop('STOP_GROUP_NAMESPACE_MISMATCH')
            if r['visible_pid'] == self.visible_self or any(r['visible_pid'] == x['visible_pid'] and r['starttime'] == x['starttime'] for x in self.ancestors):
                raise Stop('STOP_GROUP_INCLUDES_SELF_OR_ANCESTOR')
            node, traversed = r, set()
            owned = False
            while node and node['visible_pid'] not in traversed:
                identity = (node['visible_pid'], node['starttime'])
                if identity == (anchor['visible_pid'], anchor['starttime']) or identity in known:
                    owned = True
                    break
                traversed.add(node['visible_pid'])
                node = by_visible.get(node['visible_ppid'])
            if not owned:
                raise Stop('STOP_UNPROVEN_GROUP_MEMBER')
            known.add((r['visible_pid'], r['starttime']))
        return result


NS = None


def proc(local_pid):
    return NS.by_local(local_pid)


def scan(pgid=None, matching=False):
    found = []
    for r in NS.snapshot():
        if r['visible_pid'] == NS.visible_self and r['starttime'] == NS.self_starttime:
            continue
        if pgid is not None and r['pgid'] == pgid:
            found.append(r)
        if matching and any(Path(a).name in {'masc_solver_mcts.pl', 'masc_solver_beamsearch.pl',
                                            'run_ts_rc.py', 'run_ts_rc_v2.py'} for a in r['cmdline']):
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
        self.receipt = {'schema': 'TS-RC-v2-execution', 'attempt_t0_utc': wall,
                        'attempt_t0_monotonic': t0, 'deadline_monotonic': self.deadline,
                        'allowed_stages': ['supervisor_probe', 'runtime_probe', 'model_load', 'README87_control'],
                        'target_allowed': False, 'retry_resume_allowed': False,
                        'supervisor_pid': os.getpid(), 'supervisor_pgid': os.getpgrp(),
                        'namespace_self': NS.self_record, 'namespace_ancestors': NS.ancestors,
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
        allowance = min(5, self.deadline-time.monotonic()) if name in {'runtime', 'supervisor_probe'} else self.deadline-time.monotonic()
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
        # One same-PID stdlib exec gate lets us bind Popen's local PID to proc's
        # visible PID/starttime BEFORE an extremely short probe can exit.
        gate_read, gate_write = os.pipe()
        gate_argv = [sys.executable, '-I', '-S', str(Path(__file__).resolve()),
                     '--exec-gate', str(gate_read), json.dumps(cmd)]
        phase['gate_argv'] = gate_argv
        p = subprocess.Popen(gate_argv, cwd=ROOT / 'work', env=ENV, shell=False,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             close_fds=True, pass_fds=(gate_read,))
        os.close(gate_read)
        if name == 'author':
            self.receipt['author_launch_count'] += 1
        phase['timeout_pid'] = p.pid
        phase['expected_pgid'] = p.pid
        phase['pid_numbering'] = 'pid/pgid are syscall-local; visible_* are proc mount IDs'
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
        anchor = None
        known_owned = set()
        phase_deadline = min(self.deadline, phase['start_monotonic']+(5 if name in {'runtime', 'supervisor_probe'} else 60))
        fed = False
        probe_signalled = False
        last_proc_sample = 0.0

        def signal_group(sig):
            nonlocal verified_group
            r = proc(p.pid)
            if r and (anchor is None or r['visible_pid'] != anchor['visible_pid'] or r['starttime'] != anchor['starttime']):
                raise Stop('STOP_SIGNAL_IDENTITY_CHANGED')
            if r and r['pgid'] == p.pid and p.pid != os.getpgrp():
                if r['visible_pgid'] != anchor['visible_pid'] or os.getpgid(p.pid) != p.pid:
                    raise Stop('STOP_SIGNAL_GROUP_MAPPING')
                verified_group = True
            members_now = NS.group(anchor, known_owned) if anchor else []
            # timeout starts this group; never signal our inherited group.
            if verified_group and p.pid != os.getpgrp():
                if members_now:
                    try:
                        os.killpg(p.pid, sig)
                    except ProcessLookupError:
                        pass
                phase['signals'].append({'utc': utc(), 'signal': int(sig), 'pgid': p.pid, 'members': members_now})
            elif p.poll() is None and r is not None and anchor is not None:
                # No confirmed group: terminate only the known live direct child,
                # mark uncertainty, never feed input; its timeout remains bounded.
                try:
                    p.send_signal(sig)
                except ProcessLookupError:
                    pass
                phase['signals'].append({'utc': utc(), 'signal': int(sig), 'direct_pid_only': p.pid})

        try:
            gate_deadline = min(self.deadline, phase['start_monotonic']+1)
            while time.monotonic() < gate_deadline:
                anchor = proc(p.pid)
                if anchor:
                    break
                if p.poll() is not None:
                    raise Stop('STOP_GATE_EXITED')
                time.sleep(.01)
            if not anchor or anchor['visible_ppid'] != NS.visible_self or anchor['pid_namespace'] != NS.ns:
                raise Stop('STOP_GATE_PARENT_OR_NAMESPACE')
            if anchor['pgid'] != os.getpgrp() or os.getpgid(p.pid) != anchor['pgid']:
                raise Stop('STOP_GATE_GROUP_MAPPING')
            phase['anchor_before_exec'] = anchor
            known_owned.add((anchor['visible_pid'], anchor['starttime']))
            os.write(gate_write, b'G')
            os.close(gate_write)
            gate_write = None
            phase['gate_release_utc'] = utc()
            while True:
                now = time.monotonic()
                rc = p.poll()
                try:
                    if reason is None:
                        self.tick()
                        if now >= phase_deadline:
                            raise Stop('STOP_' + ('RUNTIME' if name == 'runtime' else ('CONTROL' if fed else 'MODEL_LOAD')) + '_DEADLINE')
                    if now-last_proc_sample >= .1:
                        members_now = NS.group(anchor, known_owned)
                        r = proc(p.pid)
                        if r and (r['visible_pid'] != anchor['visible_pid'] or r['starttime'] != anchor['starttime']):
                            raise Stop('STOP_ANCHOR_IDENTITY_CHANGED')
                        if r and r['pgid'] == p.pid and p.pid != os.getpgrp():
                            if r['visible_pgid'] != anchor['visible_pid'] or os.getpgid(p.pid) != r['pgid']:
                                raise Stop('STOP_LIVE_GROUP_MAPPING')
                            verified_group = True
                        details = []
                        for member in members_now:
                            try:
                                raw = (Path('/proc') / str(member['visible_pid']) / 'status').read_text()
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
                    if name == 'supervisor_probe' and reason is None and not probe_signalled and b'PROBE_READY ' in outputs['stdout']:
                        line = next(x for x in bytes(outputs['stdout']).splitlines() if x.startswith(b'PROBE_READY '))
                        payload = json.loads(line[len(b'PROBE_READY '):])
                        current_anchor = proc(p.pid)
                        if current_anchor and current_anchor['visible_pid'] == anchor['visible_pid'] and current_anchor['starttime'] == anchor['starttime']:
                            if current_anchor['pgid'] == p.pid and current_anchor['visible_pgid'] == anchor['visible_pid'] and os.getpgid(p.pid) == p.pid and p.pid != os.getpgrp():
                                verified_group = True
                        members = NS.group(anchor, known_owned)
                        locals_found = {r['pid'] for r in members}
                        if not verified_group or not {p.pid, payload['parent_local_pid'], payload['leaf_local_pid']} <= locals_found:
                            raise Stop('STOP_PROBE_TREE_NOT_IDENTIFIED')
                        phase['probe_members_before_TERM'] = members
                        signal_group(signal.SIGTERM)
                        phase['probe_TERM_monotonic'] = time.monotonic()
                        probe_signalled = True
                        phase_deadline = min(phase_deadline, time.monotonic()+2)
                    if name == 'author' and reason is None and not fed and READY in outputs['stdout']:
                        if outputs['stdout'].count(READY) != 1 or not verified_group or p.poll() is not None or author_identity is None:
                            raise Stop('STOP_READY_IDENTITY')
                        current = proc(author_identity['pid'])
                        if not current or current['starttime'] != author_identity['starttime'] or current['pgid'] != p.pid or current['state'] == 'Z':
                            raise Stop('STOP_AUTHOR_IDENTITY')
                        raw_limits = (Path('/proc') / str(current['visible_pid']) / 'limits').read_text()
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
            if gate_write is not None:
                os.close(gate_write)  # An unreleased gate gets EOF and never execs.
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
            remaining = NS.group(anchor, known_owned) if anchor else []
            if remaining:
                signal_group(signal.SIGTERM)
                end = time.monotonic()+2
                while remaining and time.monotonic() < end:
                    time.sleep(.1)
                    remaining = NS.group(anchor, known_owned)
                if remaining:
                    signal_group(signal.SIGKILL)
                    end = time.monotonic()+2
                    while remaining and time.monotonic() < end:
                        time.sleep(.1)
                        remaining = NS.group(anchor, known_owned)
                if remaining:
                    reason = 'UNKNOWN_GROUP_MEMBERS_REMAIN'
            first_empty_utc = utc() if not remaining else None
            time.sleep(.1)
            remaining = NS.group(anchor, known_owned) if anchor else []
            if remaining:
                reason = 'UNKNOWN_GROUP_REAPPEARED_OR_NOT_TERMINAL'
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
                          'observed_exit_is_timeout_wrapper': True,
                          'terminal_first_empty_utc': first_empty_utc,
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
        if name == 'supervisor_probe':
            if not probe_signalled or not verified_group or p.returncode not in (0, 143, -15) or b'PROBE_REAPED -15' not in outputs['stdout']:
                raise Stop('STOP_SUPERVISOR_PROBE_NOT_PROVEN')
            self.receipt['supervisor_probe_passed'] = True
            self.tick()
            return bytes(outputs['stdout']).decode()
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
    global NS
    # Exclusive root and attempt are never removed or reused.
    t0, wall = time.monotonic(), utc()
    NS = NamespaceView()
    prior = scan(matching=True)
    if ROOT.exists() or ROOT.is_symlink() or RUNROOT.exists() or RUNROOT.is_symlink() or prior:
        print(json.dumps({'status': 'REFUSED_PRIOR_ATTEMPT_OR_PROCESS', 'root_exists': ROOT.exists(), 'v2_root_exists': RUNROOT.exists(), 'processes': prior}), flush=True)
        return 3
    ROOT.mkdir()
    RUNROOT.mkdir()
    ATT.mkdir()
    dump(ATT / 'T0.json', {'utc': wall, 'monotonic': t0, 'deadline_monotonic': t0+180,
                          'prior_processes': prior, 'root_exclusive': True})
    attempt = Attempt(t0, wall)
    status, error = 'UNKNOWN', None
    try:
        if len(sys.argv) != 2:
            raise Stop('STOP_EXPECTED_FREEZE_SHA_ARGUMENT')
        plan = attempt.prepare(sys.argv[1])
        prefix = plan['runtime_probe_argv'][:plan['runtime_probe_argv'].index('/usr/bin/perl')]
        probe = prefix + [sys.executable, '-I', '-S', str(Path(__file__).resolve()), '--probe-parent']
        attempt.execute('supervisor_probe', probe)
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


def probe_parent():
    child = subprocess.Popen([sys.executable, '-I', '-S', str(Path(__file__).resolve()), '--probe-leaf'],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             env=ENV, close_fds=True, shell=False)
    def stop(signum, frame):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child.terminate()
        rc = child.wait(timeout=1)
        print('PROBE_REAPED ' + str(rc), flush=True)
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    print('PROBE_READY ' + json.dumps({'parent_local_pid': os.getpid(), 'leaf_local_pid': child.pid}), flush=True)
    time.sleep(10)  # External watchdog is <=5 s; this is not a background service.
    child.terminate()
    child.wait(timeout=1)
    sys.exit(4)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--exec-gate':
        fd = int(sys.argv[2])
        grant = os.read(fd, 1)
        os.close(fd)
        if grant != b'G':
            sys.exit(4)
        command = json.loads(sys.argv[3])
        os.execve(command[0], command, ENV)
    elif sys.argv[1:] == ['--probe-parent']:
        probe_parent()
    elif sys.argv[1:] == ['--probe-leaf']:
        time.sleep(10)
        sys.exit(4)
    else:
        sys.exit(main())
