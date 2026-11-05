#!/usr/bin/env python3
"""Versioned DAG policy; implementation/resource authority is injected, never inferred.

CLI is read-only planning. Dispatch is an integration seam for reviewed adapters,
not a generic shell launcher. No production adapter is registered by this module.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re

KINDS = {'resource_release', 'artifact', 'numerical_equivalence', 'scientific_admission', 'success'}
STATES = {'planned', 'preparing', 'blocked', 'ready', 'running', 'released', 'accepted', 'failed', 'uncertain'}
TERMINAL = {'released', 'accepted', 'failed'}

def require(ok, why):
    if not ok:
        raise ValueError(why)

def exact(value, keys, name):
    require(type(value) is dict and set(value) == set(keys), name + ' fields differ')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def pin(value):
    exact(value, ('path', 'sha256'), 'pin')
    require(type(value['path']) is str and Path(value['path']).is_absolute() and '..' not in Path(value['path']).parts, 'absolute pin required')
    require(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'invalid SHA256')

def read_pin(value):
    pin(value)
    p = Path(value['path'])
    require(not any(x.is_symlink() for x in [p, *p.parents]), 'symlink pin')
    raw = p.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == value['sha256'], 'changed pin: ' + str(p))
    return json.loads(raw)

def validate(g):
    exact(g, ('schema', 'id', 'policy', 'adapters', 'nodes'), 'graph')
    require(g['schema'] == 'nga-experiment-dag-v1', 'graph schema')
    require(type(g['id']) is str and bool(g['id']), 'graph id')
    p = g['policy']
    exact(p, ('poll_seconds', 'cpu_slots', 'target_ready_depth', 'target_reserve_depth', 'ordering'), 'policy')
    require(type(p['poll_seconds']) is int and p['poll_seconds'] >= 600, 'poll at least 600 seconds')
    for k in ('cpu_slots', 'target_ready_depth', 'target_reserve_depth'):
        require(type(p[k]) is int and p[k] > 0, 'positive policy integer')
    require(p['ordering'] == 'priority_then_id', 'ordering')
    require(type(g['adapters']) is dict, 'adapter registry')
    for k, v in g['adapters'].items():
        require(type(k) is str and bool(k), 'adapter id')
        exact(v, ('version', 'implementation', 'integration'), 'adapter')
        require(type(v['version']) is int and v['version'] > 0, 'adapter version')
        require(v['integration'] in ('reference_only', 'reviewed_dispatch'), 'adapter integration')
        pin(v['implementation'])
    require(type(g['nodes']) is list and bool(g['nodes']), 'nodes')
    ids = set()
    for n in g['nodes']:
        exact(n, ('id', 'lane', 'devices', 'priority', 'purpose', 'split', 'protocol', 'sources', 'adapter', 'stage', 'managed_by', 'depends_on', 'action', 'missing'), 'node')
        require(type(n['id']) is str and re.fullmatch('[a-z0-9_]+', n['id']) and n['id'] not in ids, 'duplicate/invalid node')
        ids.add(n['id'])
        require(n['lane'] in ('cpu', 'npu'), 'lane')
        require(type(n['devices']) is list and all(type(x) is int and 0 <= x < 8 for x in n['devices']) and len(set(n['devices'])) == len(n['devices']), 'devices')
        require((n['lane'] == 'cpu') == (not n['devices']), 'CPU/device mismatch')
        require(type(n['priority']) is int and n['priority'] >= 0, 'priority')
        require(all(type(n[k]) is str and n[k] for k in ('purpose', 'protocol', 'adapter', 'managed_by')), 'node strings')
        require(n['split'] in ('DEV', 'TEST', 'TRAIN', 'CONTROL', 'NONE'), 'split')
        require(n['stage'] in STATES and n['adapter'] in g['adapters'], 'stage/adapter')
        require(n['managed_by'] in ('external_frozen', 'dag'), 'management')
        require(type(n['sources']) is list and n['sources'], 'source provenance')
        for ref in n['sources']:
            pin(ref)
        require(type(n['missing']) is list and all(type(s) is str and s for s in n['missing']), 'missing prerequisites')
        require(type(n['depends_on']) is list, 'dependencies')
        pairs = set()
        for d in n['depends_on']:
            exact(d, ('node', 'kind'), 'dependency')
            require(type(d['node']) is str and d['kind'] in KINDS, 'dependency kind')
            require((d['node'], d['kind']) not in pairs, 'duplicate dependency')
            pairs.add((d['node'], d['kind']))
        if n['action'] is not None:
            exact(n['action'], ('binding', 'review'), 'action')
            pin(n['action']['binding']); pin(n['action']['review'])
    table = {n['id']: n for n in g['nodes']}
    visiting, done = set(), set()
    def visit(k):
        require(k not in visiting, 'dependency cycle')
        if k in done:
            return
        visiting.add(k)
        for d in table[k]['depends_on']:
            require(d['node'] in table, 'unknown dependency')
            visit(d['node'])
        visiting.remove(k); done.add(k)
    for k in table:
        visit(k)
    return table

def validate_snapshot(g, snap):
    exact(snap, ('schema', 'graph_sha256', 'as_of', 'authority', 'observations', 'resources'), 'snapshot')
    require(snap['schema'] == 'nga-dag-observation-v1' and snap['graph_sha256'] == digest(g), 'snapshot graph identity')
    require(type(snap['as_of']) is str and snap['authority'] in ('digest_only', 'adapter_observations'), 'snapshot source')
    ids = {n['id'] for n in g['nodes']}
    require(type(snap['observations']) is dict and set(snap['observations']) <= ids, 'observation nodes')
    for o in snap['observations'].values():
        exact(o, ('state', 'facts', 'failed_facts', 'evidence'), 'observation')
        require(o['state'] in STATES, 'observed state')
        for key in ('facts', 'failed_facts'):
            require(type(o[key]) is list and all(v in KINDS for v in o[key]) and len(set(o[key])) == len(o[key]), 'observed facts')
        require(not set(o['facts']) & set(o['failed_facts']), 'contradictory facts')
        require(type(o['evidence']) is list, 'evidence refs')
        for p in o['evidence']:
            pin(p)
    require(type(snap['resources']) is dict and set(snap['resources']) == {str(i) for i in range(8)}, 'eight resource observations required')
    require(all(v in ('free_observed', 'busy', 'unknown') for v in snap['resources'].values()), 'resource status')

def authorized_action(g, n, registry):
    require(n['action'] is not None, 'exact action/review not bound')
    registered = g['adapters'][n['adapter']]
    require(registered['integration'] == 'reviewed_dispatch', 'production dispatch adapter not integrated')
    require(registry is not None and n['adapter'] in registry, 'trusted adapter not supplied')
    adapter = registry[n['adapter']]
    require(adapter.implementation_sha256 == registered['implementation']['sha256'], 'adapter source differs')
    for ref in [registered['implementation'], *n['sources']]:
        p = Path(ref['path'])
        require(not any(x.is_symlink() for x in [p, *p.parents]), 'symlink dependency')
        require(hashlib.sha256(p.read_bytes()).hexdigest() == ref['sha256'], 'dependency changed')
    binding, review = read_pin(n['action']['binding']), read_pin(n['action']['review'])
    require(adapter.authorize(binding, review, n, digest(g)) is True, 'exact action not authorized')
    return adapter, binding

def plan(g, snap, registry=None):
    table = validate(g); validate_snapshot(g, snap)
    observations = snap['observations']; result = {}
    def classify(key):
        if key in result:
            return result[key]
        n = table[key]; o = observations.get(key)
        if o and o['state'] in {'running', 'released', 'accepted', 'failed', 'uncertain'}:
            r = {'state': o['state'], 'reasons': []}
        else:
            reasons = list(n['missing'])
            if n['managed_by'] == 'external_frozen':
                reasons.append('owned by existing frozen service; DAG cannot launch')
            if n['action'] is None:
                reasons.append('exact action/review not bound')
            if g['adapters'][n['adapter']]['integration'] != 'reviewed_dispatch':
                reasons.append('production dispatch adapter not integrated')
            if n['action'] is not None:
                try:
                    authorized_action(g, n, registry)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    reasons.append('action admission: ' + str(exc))
            for d in n['depends_on']:
                parent = classify(d['node']); evidence = observations.get(d['node'], {})
                if d['kind'] not in evidence.get('facts', []):
                    suffix = 'failed' if d['kind'] in evidence.get('failed_facts', []) or parent['state'] == 'failed' else 'pending'
                    reasons.append(d['node'] + ':' + d['kind'] + ':' + suffix)
            r = {'state': 'blocked' if reasons else 'ready', 'reasons': reasons}
            if not n['depends_on'] and reasons and n['stage'] in ('planned', 'preparing'):
                r['state'] = n['stage']
        result[key] = r
        return r
    for k in table:
        classify(k)
    ready = sorted((n for n in g['nodes'] if result[n['id']]['state'] == 'ready'), key=lambda n: (n['priority'], n['id']))
    selected, used, cpu = [], set(), 0
    # Observed owners dominate an optimistic aggregate free snapshot. Failed or
    # completed work retains its devices until an authenticated release fact.
    held = set()
    for n in g['nodes']:
        o = observations.get(n['id'], {})
        if n['lane'] == 'npu' and o.get('state') in {'running', 'uncertain', 'failed', 'released', 'accepted'} and 'resource_release' not in o.get('facts', []):
            held.update(n['devices'])
    active_cpu = sum(1 for n in g['nodes'] if n['lane'] == 'cpu' and result[n['id']]['state'] in ('running', 'uncertain'))
    for n in ready:
        if n['lane'] == 'cpu':
            if cpu + active_cpu >= g['policy']['cpu_slots']:
                continue
            cpu += 1
        else:
            if any(snap['resources'][str(i)] != 'free_observed' or i in used or i in held for i in n['devices']):
                continue
            used.update(n['devices'])
        selected.append(n['id'])
    coverage = {}
    for chip in range(8):
        ns = [n for n in g['nodes'] if chip in n['devices']]
        future = [n for n in ns if result[n['id']]['state'] not in TERMINAL | {'running', 'uncertain'}]
        count = sum(result[n['id']]['state'] == 'ready' for n in future)
        coverage[str(chip)] = {'running': [n['id'] for n in ns if result[n['id']]['state'] == 'running'], 'future_depth': len(future), 'ready_depth': count, 'reserve_depth': len(future)-count, 'ready_shortfall': max(0, g['policy']['target_ready_depth']-count)}
    return {'schema': 'nga-dag-plan-v1', 'graph_sha256': digest(g), 'observation_as_of': snap['as_of'], 'authority': snap['authority'], 'nodes': result, 'proposed': selected, 'per_chip': coverage, 'launch_authorized': False, 'scientific_acceptance': False}

def atomic(path, value):
    path = Path(path); tmp = path.with_name(path.name + '.pending')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def dispatch_once(g, snapshot, registry, state_dir):
    """Reviewed composition injects adapters; no CLI action can reach this path.

    Adapter authorize(binding, review, node, graph_hash) validates exact closure,
    attempt, device/policy and genuine review authority; it cannot be replaced by
    graph/snapshot booleans. reserve_and_start does live lock-held admission and
    detached launch; observe reconciles an intent and may return absent, running,
    released, accepted, failed or uncertain. Absent after intent remains uncertain.
    """
    validate(g); validate_snapshot(g, snapshot)
    require(snapshot['authority'] == 'adapter_observations', 'digest is not dispatch authority')
    root = Path(state_dir)
    require(root.is_absolute() and not any(x.is_symlink() for x in [root, *root.parents]), 'state directory')
    root.mkdir(parents=True, exist_ok=True)
    with (root/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = root/'state.json'; gh = digest(g)
        state = json.loads(path.read_text()) if path.exists() else {'graph_sha256': gh, 'attempts': {}}
        exact(state, ('graph_sha256', 'attempts'), 'controller state')
        require(state['graph_sha256'] == gh and type(state['attempts']) is dict, 'restart graph differs')
        table = {n['id']: n for n in g['nodes']}
        require(set(state['attempts']) <= set(table), 'unknown state node')
        snap = copy.deepcopy(snapshot)
        for key, rec in state['attempts'].items():
            n = table[key]
            try:
                adapter = registry[n['adapter']]
                require(adapter.implementation_sha256 == g['adapters'][n['adapter']]['implementation']['sha256'], 'adapter source differs')
                obs = adapter.observe(n, rec)
                require(type(obs) is dict and obs.get('state') in STATES | {'absent'}, 'adapter observation')
                if obs['state'] != 'absent':
                    validate_snapshot(g, dict(snap, observations={key: obs}))
            except Exception as exc:
                obs = {'state': 'absent'}
                rec['observation_error'] = type(exc).__name__
            if obs['state'] == 'absent':
                obs = {'state': 'uncertain', 'facts': [], 'failed_facts': [], 'evidence': []}
            snap['observations'][key] = obs
            rec['status'] = obs['state']
            if n['lane'] == 'npu' and 'resource_release' not in obs['facts']:
                for chip in n['devices']:
                    snap['resources'][str(chip)] = 'unknown'
        validate_snapshot(g, snap)
        p = plan(g, snap, registry); atomic(path, state)
        for key in p['proposed']:
            if key in state['attempts']:
                continue  # immutable intent: never automatically repeat a start
            n = table[key]
            try:
                adapter, binding = authorized_action(g, n, registry)
            except Exception:
                continue  # changed admission blocks this node, not unrelated lanes
            token = digest({'graph': gh, 'node': key, 'action': n['action']})
            state['attempts'][key] = {'status': 'intent', 'token': token, 'action': n['action']}
            atomic(path, state)  # durable intent before any potentially remote effect
            try:
                receipt = adapter.reserve_and_start(binding, n, token)
                require(type(receipt) is dict, 'launch receipt')
                state['attempts'][key].update(status='uncertain', receipt=receipt)
            except Exception as exc:
                state['attempts'][key].update(status='uncertain', error_type=type(exc).__name__)
                atomic(path, state)
                continue
            atomic(path, state)
        return state

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--snapshot', type=Path, required=True)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    result = plan(json.loads(args.config.read_text()), json.loads(args.snapshot.read_text()))
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        with args.out.open('x') as f:
            f.write(text)
    else:
        print(text, end='')

if __name__ == '__main__':
    main()
