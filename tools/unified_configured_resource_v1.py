#!/usr/bin/env python3
"""Bounded subprocess around the exact simulated-review resource closure."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import types
import uuid

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = ROOT/'tools/resource-provider-v3-runtime'
CLOSURE = {
    'tools/unified_resource_provider_v1.py':'00333ca9ce97d0f474f28ceb59fd773905888629e979b0015f60ddd73d2f2c45',
    'tools/unified_container_host_v1.py':'afd86a405cdb08b1353ec1385f268794854ce4c2309847df018962d019759de1',
    'tools/unified_resource_lease_v1.py':'5c354ace3023d9cf2ca2c8d8d4a0a1ed468de71609aee797212d38eb2e467d7e',
    'tools/r3_resource_adapter.py':'f90ae21242b78c4c774ff5c12b5ff30d9e7b1bd927d42f910fc157c6538a574a',
    'tools/experiment_dag.py':'264d2b32b01059f91c40723b35b8204cb5add1cb3a0fecb4a200129ddbcf0ebe',
    'docker/engineering-base/schema.json':'2c4df3b73d2cec97a5715ade3a3f4bacf3c5fb29760ba4aaa15c367bd410e012',
}


def check_closure():
    allowed = set(CLOSURE) | {'README.md', 'inventory.json'}
    found = set()
    for path in REVIEWED.rglob('*'):
        if path.is_symlink():
            raise ValueError('closure symlink')
        if path.is_file():
            found.add(path.relative_to(REVIEWED).as_posix())
        elif not path.is_dir():
            raise ValueError('closure entry')
    if found != allowed:
        raise ValueError('closure inventory changed')
    if json.loads((REVIEWED/'inventory.json').read_text()) != {'schema':'resource-provider-v3-inventory-v1', 'files':CLOSURE}:
        raise ValueError('closure inventory differs')
    for rel, sha in CLOSURE.items():
        p = REVIEWED/rel
        if any(x.is_symlink() for x in (p,*p.parents)) or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ValueError('reviewed closure changed')


def observe(config, graph_pin, graph, python, state_dir):
    """A timeout, including validation/publication, raises to the service fallback."""
    started = time.monotonic()
    # Kept for the service's existing call signature; never execute a path
    # supplied by configuration or by the caller.
    argv = [sys.executable, '-B', '-E', '-P', str(Path(__file__).resolve()), json.dumps(config), json.dumps(graph_pin), str(state_dir)]
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=max(0.001, 5-(time.monotonic()-started)))
    except subprocess.TimeoutExpired:
        try: os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        p.communicate()
        raise TimeoutError('resource observation deadline')
    if p.returncode or time.monotonic()-started > 5 or len(out) > 65536:
        raise ValueError('resource observation failed or expired')
    result = json.loads(out)
    if result.get('graph_sha256') != hashlib.sha256(json.dumps(graph,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest():
        raise ValueError('graph changed')
    return result


def child(ref, graph_ref, state_dir):
    # The subprocess imports only the byte-pinned reviewed closure. No code from
    # the changing worktree is imported into the provider process.
    sys.path[:] = [p for p in sys.path if p != str(ROOT)]
    check_closure()
    sys.path.insert(0, str(REVIEWED))
    package = types.ModuleType('tools')
    package.__path__ = [str(REVIEWED/'tools')]
    sys.modules['tools'] = package
    from tools import unified_resource_provider_v1 as P
    from tools import experiment_dag as D
    from tools import unified_resource_lease_v1 as U
    cfg = U.ref(ref)
    D.exact(cfg, ('schema','provider_config'), 'configured resource')
    U.need(cfg['schema']=='unified-configured-resource-v1', 'configured resource schema')
    c=U.ref(cfg['provider_config']); graph=U.ref(graph_ref)
    U.need(type(c.get('max_age_seconds')) in (int,float) and 0 < c['max_age_seconds'] <= 5, 'provider age')
    hosts=P.validate_config(c); D.validate(graph)
    U.need(len({(p['path'],p['sha256']) for p in c['host_configs']})==len(c['host_configs']) and len({h['lease']['lease_id'] for h in hosts})==len(hosts), 'duplicate registered owner')
    graph_hosts=set()
    for node in graph['nodes']:
        if node['lane'] != 'npu': continue
        b=U.ref(node['action']['binding'])
        D.exact(b, ('schema','host_config'), 'NPU binding')
        U.need(b['schema']=='unified-dag-binding-v1' and b['host_config'] in c['host_configs'], 'unregistered graph host')
        key=(b['host_config']['path'],b['host_config']['sha256'])
        U.need(key not in graph_hosts, 'duplicate graph owner'); graph_hosts.add(key)
        h=U.ref(b['host_config']); lease=h['lease']
        U.need(lease['allocation']==c['allocation'] and sorted(node['devices'])==sorted(lease['eligible_device_ids']) and lease['device_count']==len(node['devices']), 'graph resource binding')
    root=Path(state_dir)/'resource-observations'; root.mkdir(mode=0o700,parents=True,exist_ok=True)
    U.need(not any(x.is_symlink() for x in (root,*root.parents)) and root.stat().st_uid==os.geteuid() and root.stat().st_mode & 0o077 == 0, 'evidence root')
    snap, receipt=P.observe(c,graph)
    pair=P.publish(c,graph,snap,receipt,root/uuid.uuid4().hex,(ref, cfg['provider_config'],graph_ref))
    saved=U.ref(pair['snapshot']); r=U.ref(pair['receipt'])
    U.need(saved==snap and r==receipt and r['fresh'] is True and r['snapshot_sha256']==D.digest(saved) and r['config_sha256']==U.digest(c), 'pair differs')
    U.need(r['boot_id']==P.boot() and 0 <= time.monotonic()-r['monotonic_start'] <= c['max_age_seconds'] and 0 <= time.time()-float(saved['as_of']) <= c['max_age_seconds'], 'pair expired')
    check_closure()
    for pin in (ref,cfg['provider_config'],graph_ref,*r['source_pins']): P.check_raw_pin(pin)
    U.need(r['boot_id']==P.boot() and 0 <= time.monotonic()-r['monotonic_start'] <= c['max_age_seconds'] and 0 <= time.time()-float(saved['as_of']) <= c['max_age_seconds'], 'pair expired at return')
    D.validate_snapshot(graph,saved)
    U.need(saved['observations']=={}, 'provider observations')
    print(json.dumps(saved,allow_nan=False))


if __name__ == '__main__':
    child(json.loads(sys.argv[1]), json.loads(sys.argv[2]), sys.argv[3])
