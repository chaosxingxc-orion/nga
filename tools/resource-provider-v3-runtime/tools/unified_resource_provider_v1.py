#!/usr/bin/env python3
"""Read-only fixed resource observer; its snapshot is not a lease."""
import argparse
import copy
import fcntl
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import shutil
import tempfile
import subprocess
import sys
import time

# Support direct execution with isolated Python as well as package import.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import experiment_dag as D, unified_container_host_v1 as H
from tools import unified_resource_lease_v1 as U, r3_resource_adapter as R


def pin(path):
    raw = R.read_bytes(path)
    return {'path': str(path), 'sha256': R.sha_bytes(raw)}


def run(args, timeout=20):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if p.returncode or p.stderr.strip():
        raise RuntimeError('command failed: %s (exit %s)' % (args[0], p.returncode))
    return p.stdout


def strict_json(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            U.need(key not in obj, 'duplicate JSON member: ' + key)
            obj[key] = value
        return obj
    return json.loads(raw, object_pairs_hook=unique)


def docker_state(state):
    status = state.get('Status'); running = state.get('Running')
    U.need(status in ('created','running','paused','restarting','removing','exited','dead') and type(running) is bool, 'Docker state uncertain')
    for flag in ('Paused', 'Restarting', 'OOMKilled', 'Dead', 'RemovalInProgress'):
        U.need(flag not in state or type(state[flag]) is bool, 'Docker state flag uncertain')
    if status != 'removing':
        U.need(running == (status in ('running','paused','restarting')), 'Docker state contradictory')
        for flag, expected in (('Paused', status == 'paused'), ('Restarting', status == 'restarting'),
                               ('Dead', status == 'dead'), ('RemovalInProgress', False)):
            U.need(flag not in state or state[flag] == expected, 'Docker state contradictory')
    else:
        # Removal can overlap a running or stopped state; it always reserves mappings.
        paused = state.get('Paused', False); restarting = state.get('Restarting', False); dead = state.get('Dead', False)
        U.need(not (paused and restarting) and not ((paused or restarting) and not running)
               and not (dead and (running or paused or restarting)), 'Docker state contradictory')
    return status


# Docker repository names consist of lowercase path components with an optional
# registry domain/port, optional tag, and a canonical SHA-256 digest.
_REPO_DIGEST = re.compile(r'(?:[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*(?::[0-9]+)?/)?'
                          r'[a-z0-9]+(?:(?:[._]|__|[-]+)[a-z0-9]+)*'
                          r'(?:/[a-z0-9]+(?:(?:[._]|__|[-]+)[a-z0-9]+)*)*'
                          r'(?::[\w][\w.-]{0,127})?@sha256:[0-9a-f]{64}', re.ASCII)


def host_check():
    U.need(socket.gethostname() == 'k8s-node1' and not Path('/.dockerenv').exists()
           and Path('/proc/1/comm').read_text().strip() == 'systemd', 'physical 175 host identity unavailable')
    p = subprocess.run(['/usr/bin/systemd-detect-virt', '--container'], capture_output=True, text=True, timeout=10)
    U.need(p.returncode == 1 and p.stdout.strip() == 'none' and not p.stderr.strip(), 'physical host detection uncertain')


def device_query(chip):
    out = run(['/usr/local/sbin/npu-smi', 'info', '-t', 'proc-mem', '-i', str(chip)])
    lines = [x.strip() for x in out.splitlines() if x.strip()]
    U.need(len(lines) >= 4 and re.fullmatch(r'NPU ID\s*:\s*' + str(chip), lines[0]) and
           re.fullmatch(r'Chip Count\s*:\s*1', lines[1]) and re.fullmatch(r'Chip ID\s*:\s*0', lines[-1]), 'device query header uncertain')
    body = lines[2:-1]
    if body == ['No process in device.']: return False
    U.need(bool(body) and all(re.fullmatch(r'Process id:[1-9][0-9]*\s+Process name:\S+\s+Process memory\(MB\):[0-9]+', x) for x in body), 'device query body uncertain')
    return True


@contextmanager
def ledger_lock(alloc):
    # Never wait behind a writer: an observer must fail closed and let its caller progress.
    with open(str(alloc)+'.lock', 'r') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally: fcntl.flock(handle, fcntl.LOCK_UN)


def file_identity(path):
    stat=os.stat(path)
    return [stat.st_dev,stat.st_ino,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_size]


def graph_pins(graph):
    pins=[v['implementation'] for v in graph['adapters'].values()]
    for node in graph['nodes']:
        pins.extend(node['sources'])
        if node['action'] is not None: pins.extend(node['action'].values())
    return pins


def check_raw_pin(ref):
    D.pin(ref)
    path=Path(ref['path'])
    U.need(not any(x.is_symlink() for x in (path,*path.parents)) and R.sha_bytes(R.read_bytes(path))==ref['sha256'], 'source pin changed')


def closure_pins(graph):
    paths=[Path(__file__), Path(H.__file__), Path(U.__file__), Path(R.__file__), Path(D.__file__),
           Path(H.__file__).resolve().parents[1]/'docker/engineering-base/schema.json']
    pins=[pin(str(p.resolve())) for p in paths] + graph_pins(graph)
    for ref in pins: check_raw_pin(ref)
    return pins


class Inventory:
    def __init__(self):
        ids = run(['/usr/bin/docker', 'ps', '-aq', '--no-trunc']).split()
        U.need(len(ids) == len(set(ids)) and all(re.fullmatch('[0-9a-f]{64}', x) for x in ids), 'Docker listing identities uncertain')
        self.by_id = {}; self.by_name = {}; self.busy = set()
        for start in range(0, len(ids), 128):
            batch = ids[start:start+128]
            rows = strict_json(run(['/usr/bin/docker', 'inspect', *batch]))
            U.need(type(rows) is list and len(rows) == len(batch) and all(type(x) is dict for x in rows) and
                   sorted(x.get('Id', '') for x in rows) == sorted(batch), 'Docker inventory incomplete')
            for obj in rows:
                name = obj.get('Name'); state = obj.get('State'); host = obj.get('HostConfig')
                U.need(type(name) is str and re.fullmatch(r'/[A-Za-z0-9][A-Za-z0-9_.-]*',name) is not None and name[1:] not in self.by_name and type(state) is dict and type(host) is dict, 'Docker fields uncertain')
                name=name[1:]
                status = docker_state(state)
                devices = host.get('Devices'); U.need('Devices' in host and (devices is None or type(devices) is list), 'Docker devices uncertain')
                U.need(all(type(x) is dict and type(x.get('PathOnHost')) is str and type(x.get('PathInContainer')) is str for x in devices or []), 'Docker mapping uncertain')
                U.need(type(host.get('Privileged')) is bool and all(k in host and (host[k] is None or type(host[k]) is list) for k in ('DeviceCgroupRules','DeviceRequests')), 'Docker grants uncertain')
                if status not in ('exited','dead'):
                    if host['Privileged'] or host['DeviceCgroupRules'] or host['DeviceRequests']:
                        self.busy.update(range(8))
                    auxiliary={'/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc'}
                    paths=[x['PathOnHost'] for x in devices or []]
                    has_aux=bool(auxiliary.intersection(paths))
                    standard=(has_aux and len(paths)==len(set(paths)) and auxiliary.issubset(paths) and
                              all(x.get('PathInContainer')==x['PathOnHost'] and x.get('CgroupPermissions')=='rwm' for x in devices) and
                              all(p in auxiliary or re.fullmatch(r'/dev/davinci[0-7]',p) for p in paths) and
                              any(re.fullmatch(r'/dev/davinci[0-7]',p) for p in paths))
                    if has_aux and not standard: self.busy.update(range(8))
                    for x in devices or []:
                        path = x['PathOnHost']; m = re.fullmatch(r'/dev/davinci([0-7])', path)
                        if x['PathInContainer'] in ('/','/dev'): self.busy.update(range(8))
                        if m: self.busy.add(int(m[1]))
                        elif path in auxiliary and standard: pass
                        elif path.startswith('/dev/davinci') or path.startswith('/dev/ascend') or path in auxiliary or path in ('/dev','/'):
                            self.busy.update(range(8))
                    U.need(type(obj.get('Mounts')) is list, 'Docker mounts uncertain')
                    for mount in obj['Mounts']:
                        U.need(type(mount) is dict and type(mount.get('Source')) is str, 'Docker mount uncertain')
                        if mount['Source'] == '/dev' or mount['Source'].startswith('/dev/'):
                            self.busy.update(range(8))
                self.by_id[obj['Id']] = obj; self.by_name[name] = obj
    def inspect(self, name): return self.by_name.get(name) or self.by_id.get(name)
    def conflict(self, chip): return chip in self.busy


class DiagnosticFacade:
    """Read-only cached container inventory and bounded, deduplicated image queries."""
    def __init__(self, inventory):
        self.inventory=inventory; self.images={}; self.envs={}
    def inspect(self, name): return self.inventory.inspect(name)
    def image_id(self, ref):
        if ref not in self.images:
            result=strict_json(run(['/usr/bin/docker','image','inspect',ref]))
            U.need(type(result) is list and len(result)==1 and type(result[0]) is dict, 'image inspection uncertain')
            obj=result[0]; ident=obj.get('Id')
            U.need(type(ident) is str and re.fullmatch(r'sha256:[0-9a-f]{64}',ident), 'image ID')
            digests=obj.get('RepoDigests')
            U.need(digests is None or (type(digests) is list and all(type(x) is str and _REPO_DIGEST.fullmatch(x) for x in digests)), 'image RepoDigests uncertain')
            U.need(ref==ident if ref.startswith('sha256:') else ref in (digests or []), 'image digest differs')
            cfg=obj.get('Config'); U.need(type(cfg) is dict and 'Env' in cfg, 'image environment missing')
            env=H.env_map(cfg['Env'] if cfg['Env'] is not None else [])
            if ident in self.envs: U.need(self.envs[ident]==env, 'image environment changed')
            self.images[ref]=ident; self.envs[ident]=env
        return self.images[ref]
    def image_env(self, ident):
        U.need(ident in self.envs, 'image was not observed')
        return self.envs[ident].copy()


def validate_config(c):
    D.exact(c, ('schema','allocation','evidence_roots','host_configs','historical_releases','allowed_device_ids','max_age_seconds'), 'provider config')
    U.need(c['schema']=='unified-resource-provider-config-v1', 'provider schema')
    for p in [c['allocation'], *c['evidence_roots']]:
        U.need(type(p) is str and os.path.isabs(p) and os.path.normpath(p)==p and not any(x.is_symlink() for x in (Path(p), *Path(p).parents)), 'provider path')
    U.need(type(c['evidence_roots']) is list and bool(c['evidence_roots']) and all(Path(x).is_dir() for x in c['evidence_roots']), 'evidence roots')
    ids=c['allowed_device_ids']; U.need(type(ids) is list and ids==sorted(set(ids)) and bool(ids) and all(type(i) is int and 0<=i<8 for i in ids), 'allowed ids')
    U.need(type(c['max_age_seconds']) in (int,float) and 0<c['max_age_seconds']<=30, 'freshness bound')
    U.need(type(c['host_configs']) is list and bool(c['host_configs']), 'registered hosts required')
    U.need(type(c['historical_releases']) is list, 'historical releases')
    hosts=[]
    for ref in c['host_configs']:
        h=U.ref(ref); H.validate(h); l=h['lease']
        U.need(l['allocation']==c['allocation'] and set(l['eligible_device_ids'])<=set(ids) and len(l['eligible_device_ids'])==l['device_count'], 'fixed host devices or allocation differ')
        U.need('evidence_roots' in l and set(l['evidence_roots'])<=set(c['evidence_roots']), 'host evidence roots differ')
        hosts.append(h)
    for item in c['historical_releases']:
        D.exact(item, ('host_config','free_entry','refs'), 'historical release')
        U.need(item['host_config'] in c['host_configs'] and type(item['free_entry']) is dict, 'unregistered historical host')
        U.need(type(item['refs']) is dict and set(item['refs'])=={'claim','release','container','terminal'}, 'historical refs')
    return hosts


def boot(): return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def observe(c, graph):
    begin=time.monotonic(); wall=time.time(); boot_id=boot()
    graph=copy.deepcopy(graph); c=copy.deepcopy(c)
    D.validate(graph); sources=closure_pins(graph); hosts=validate_config(c)
    alloc=R.validated_path(c['allocation']); lock=Path(str(alloc)+'.lock')
    U.need(lock.is_file() and not lock.is_symlink(), 'existing allocation lock required')
    with ledger_lock(alloc):
        lock_start=time.monotonic(); raw=R.read_bytes(alloc); identity=file_identity(alloc); doc=strict_json(raw); R.validate_doc(doc); lock_end=time.monotonic()
    resources={str(i):'unknown' for i in range(8)}; reasons={str(i):'not configured' for i in range(8)}
    proofs={}; refs=[]; historical=[]
    for e in doc['allocation']:
        if e['chip'] in c['allowed_device_ids']: resources[str(e['chip'])]='busy'; reasons[str(e['chip'])]='ledger claimed'
    inventory=None; physical={}
    try:
        host_check(); inventory=Inventory()
        class Historical:
            def inspect(self, name): return inventory.inspect(name)
            def conflict(self, chip): return False
        for item in c['historical_releases']:
            try:
                lease=U.ref(item['host_config'])['lease']; entry=item['free_entry']; hr=item['refs']
                release=hr['release']['path']
                U.need(any(os.path.commonpath((root,release))==root and release!=root for root in c['evidence_roots']), 'historical release outside roots')
                U.predecessor(lease,entry,Historical(),hr)
                refs.extend(x for x in hr.values() if x is not None)
                historical.append({'chip':entry['chip'],'status':'authenticated','refs':hr})
            except Exception as exc:
                historical.append({'chip':item['free_entry'].get('chip'),'status':'uncertain','reason':type(exc).__name__+': '+str(exc)})
        for i in c['allowed_device_ids']:
            try: physical[i]=(device_query(i), None)
            except Exception as exc: physical[i]=(None, type(exc).__name__+': '+str(exc))
        pending=doc.get('pending_claims')
        for e in doc['free']:
            i=e['chip']; key=str(i)
            if i not in c['allowed_device_ids']: continue
            if pending != []: reasons[key]='pending claims missing, malformed, or nonempty'; continue
            if inventory.conflict(i) or physical[i][0] is True:
                resources[key]='busy'; reasons[key]='physical device conflict'; continue
            if physical[i][1]: reasons[key]='device probe: '+physical[i][1]; continue
            errors=[]
            for h in hosts:
                lease=h['lease']
                if i not in lease['eligible_device_ids']: continue
                try:
                    lineage=U.evidence_refs(lease,e); U.predecessor(lease,e,inventory,lineage)
                    refs.extend(x for x in lineage.values() if x is not None)
                    proofs[key]=lineage; resources[key]='free_observed'; reasons[key]='ledger, predecessor and physical checks passed'; break
                except Exception as exc: errors.append(type(exc).__name__+': '+str(exc))
            if key not in proofs: reasons[key]='predecessor: '+('; '.join(errors) or 'no registered host for device')
    except Exception as exc:
        for i in c['allowed_device_ids']:
            if resources[str(i)] != 'busy': reasons[str(i)]='physical inventory: '+type(exc).__name__+': '+str(exc)
    # Diagnostics use only the same successful host/device/inventory observation.
    owners={}; facade=DiagnosticFacade(inventory) if inventory is not None else None
    for h in hosts:
        l=h['lease']; entries=[x for x in doc['allocation'] if x.get('lease_id')==l['lease_id']]
        if not entries: continue
        try:
            U.need(facade is not None and all(i in physical and physical[i][1] is None for i in l['eligible_device_ids']), 'physical observation unavailable')
            claim=R.load(U.paths(l,'claim')[1]); image_id=facade.image_id(h['image'])
            with ledger_lock(alloc):
                U.accepted_identity(l); H.verify_binding_owned(h,facade,claim,image_id)
            owners[l['lease_id']]='authenticated'
        except Exception as exc: owners[l['lease_id']]='uncertain: '+type(exc).__name__+': '+str(exc)
    snap={'schema':'nga-dag-observation-v1','graph_sha256':D.digest(graph),'as_of':str(wall),'authority':'adapter_observations','observations':{},'resources':resources}
    D.validate_snapshot(graph,snap)
    stable=True
    try:
        with ledger_lock(alloc):
            for ref in refs: U.ref(ref)
            validate_config(c)
            for ref in sources: check_raw_pin(ref)
            D.validate_snapshot(graph,snap)
            stable=(raw==R.read_bytes(alloc) and identity==file_identity(alloc))
            final_boot=boot(); end=time.monotonic(); wall_end=time.time()
            stable=stable and boot_id==final_boot and 0<=lock_start-begin<=lock_end-begin<=end-begin<=c['max_age_seconds'] and 0<=wall_end-wall<=c['max_age_seconds']
    except Exception:
        stable=False; end=time.monotonic()
    if not stable:
        for key in resources:
            if resources[key]=='free_observed': resources[key]='unknown'; reasons[key]='ledger, pins, boot or monotonic freshness changed'
    D.validate_snapshot(graph,snap)
    receipt={'schema':'unified-resource-provider-receipt-v1','snapshot_sha256':D.digest(snap),'config_sha256':U.digest(c),'ledger_sha256':R.sha_bytes(raw),'ledger_bytes_hex':raw.hex(),'ledger_identity':identity,'source_pins':sources,'boot_id':boot_id,'monotonic_start':begin,'lock_start':lock_start,'lock_end':lock_end,'monotonic_end':end,'fresh':stable,'reasons':reasons,'lineage':proofs,'historical_releases':historical,'owners':owners}
    return snap,receipt


def publish(c, graph, snap, receipt, dest, input_pins=()):
    """Publish a complete pair only after rechecking the exact observation and closure."""
    dest=Path(dest); U.need(not dest.exists() and not any(x.is_symlink() for x in dest.parents), 'new evidence directory required')
    stage=Path(tempfile.mkdtemp(prefix='.'+dest.name+'.', dir=dest.parent))
    try:
        R.write_atomic(stage/'snapshot.json',snap); R.write_atomic(stage/'receipt.json',receipt)
        snapshot_pin=pin(stage/'snapshot.json'); receipt_pin=pin(stage/'receipt.json')
        alloc=R.validated_path(c['allocation'])
        with ledger_lock(alloc):
            for lineage in list(receipt['lineage'].values()) + [h['refs'] for h in receipt['historical_releases'] if h['status']=='authenticated']:
                for ref in lineage.values():
                    if ref is not None: U.ref(ref)
            validate_config(c)
            observed=U.ref(snapshot_pin); saved=U.ref(receipt_pin)
            D.validate_snapshot(graph,observed)
            U.need(observed==snap and saved==receipt and D.digest(observed)==receipt['snapshot_sha256'] and U.digest(c)==receipt['config_sha256'], 'publication snapshot differs')
            for ref in (*receipt['source_pins'], *input_pins): check_raw_pin(ref)
            U.need(R.read_bytes(alloc).hex()==receipt['ledger_bytes_hex'] and file_identity(alloc)==receipt['ledger_identity'], 'publication ledger changed')
            # Recheck exact staged bytes before taking terminal clock samples.
            check_raw_pin(snapshot_pin); check_raw_pin(receipt_pin)
            final_boot=boot(); now=time.monotonic(); wall=time.time()
            U.need(receipt['fresh'] is True and final_boot==receipt['boot_id'] and 0<=now-receipt['monotonic_start']<=c['max_age_seconds'] and 0<=wall-float(snap['as_of'])<=c['max_age_seconds'], 'observation expired before publication')
            os.rename(stage,dest)
        return {'snapshot':pin(dest/'snapshot.json'),'receipt':pin(dest/'receipt.json')}
    finally:
        if stage.exists(): shutil.rmtree(stage)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--sha256',required=True); p.add_argument('--graph',required=True); p.add_argument('--graph-sha256',required=True); p.add_argument('--evidence-dir',required=True); a=p.parse_args()
    c=U.ref({'path':os.path.abspath(a.config),'sha256':a.sha256}); graph=U.ref({'path':os.path.abspath(a.graph),'sha256':a.graph_sha256})
    dest=Path(a.evidence_dir).absolute(); U.need(not dest.exists() and not any(x.is_symlink() for x in dest.parents), 'new evidence directory required')
    snap,receipt=observe(c,graph)
    print(json.dumps(publish(c,graph,snap,receipt,dest,({'path':os.path.abspath(a.config),'sha256':a.sha256},{'path':os.path.abspath(a.graph),'sha256':a.graph_sha256}))))
if __name__=='__main__': main()
