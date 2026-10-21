from pathlib import Path
import os
class Stop(RuntimeError):
    pass

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

