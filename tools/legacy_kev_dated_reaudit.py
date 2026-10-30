#!/usr/bin/env python3
"""E39: current-date CPU re-audit; never edits legacy runs or historical bindings."""
import argparse
import fcntl
import hashlib
import http.client
import types
import json
import math
import os
from pathlib import Path
import socket
import tempfile
import threading
import time


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def atomic(path, obj):
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(canonical(obj) + b'\n'); f.flush(); os.fsync(f.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def identity(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def checked_bytes(path, collect=False):
    path = Path(path)
    path_before = path.stat()
    h = hashlib.sha256(); chunks = []
    with path.open('rb') as f:
        fd_before = os.fstat(f.fileno())
        if identity(fd_before) != identity(path_before):
            raise ValueError('Path changed before file open: ' + str(path))
        for chunk in iter(lambda: f.read(4 << 20), b''):
            h.update(chunk)
            if collect: chunks.append(chunk)
        fd_after = os.fstat(f.fileno())
        path_after = path.stat()
        if identity(fd_before) != identity(fd_after) or identity(fd_after) != identity(path_after):
            raise ValueError('File or path changed during read: ' + str(path))
    return {'sha256': h.hexdigest(), 'bytes': fd_after.st_size}, b''.join(chunks) if collect else None


def file_hash(path):
    return checked_bytes(path)[0]


def frozen_json(path, manifest):
    """Parse exactly the bytes whose digest is checked, with fd/path binding."""
    observed, data = checked_bytes(path, collect=True)
    if observed != manifest[str(path)]:
        raise ValueError('Changed JSON snapshot: ' + str(path))
    return json.loads(data)


def hash_phase(entries, out, name, expected_previous, status):
    """Each restart hashes actual bytes again; a journal is never an mtime cache."""
    values = {}
    with (out / (name + '.journal.jsonl')).open('a') as journal:
        for i, entry in enumerate(entries, 1):
            path = entry['path']; observed = file_hash(path)
            if entry.get('expected_sha256') and observed['sha256'] != entry['expected_sha256']:
                raise ValueError('Frozen expected hash mismatch: ' + path)
            if expected_previous is not None and observed != expected_previous[path]:
                raise ValueError('Evidence changed since preceding full scan: ' + path)
            values[path] = observed
            journal.write(json.dumps({'utc': utc(), 'index': i, 'path': path, **observed}) + '\n')
            journal.flush(); os.fsync(journal.fileno())
            status.update(progress=i, total=len(entries), last_path=path)
    atomic(out / (name + '.json'), values)
    return values


class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(15)
        self.sock.connect('/var/run/docker.sock')


def inspect_container(container_id):
    if len(container_id) != 64 or any(c not in '0123456789abcdef' for c in container_id):
        raise ValueError('Container ID must be full hex')
    client = UnixHTTP('localhost', timeout=15)
    try:
        client.request('GET', '/containers/' + container_id + '/json')
        response = client.getresponse(); data = response.read()
        if response.status != 200: raise ValueError('Docker inspect HTTP ' + str(response.status))
        obj = json.loads(data)
        # Environment is deliberately never saved or printed.
        return {k: obj[k] for k in ('Id', 'Name', 'Image', 'State', 'Path', 'Args')}
    finally:
        client.close()


def verify_container(observation, run):
    if observation['Id'] != run['container_id'] or observation['Image'] != run['image']:
        raise ValueError('Container identity mismatch')
    state = observation['State']
    if state['Status'] != 'exited' or state['Running'] or state['ExitCode'] != 0:
        raise ValueError('Original inference container not exited/0')
    if str(Path(run['directory']) / 'run.sh') not in observation['Args']:
        raise ValueError('Container wrapper mismatch')


def load_auditor(path, manifest):
    observed, data = checked_bytes(path, collect=True)
    if observed != manifest[str(path)]:
        raise ValueError('Changed auditor source')
    module = types.ModuleType('e39_auditor_' + Path(path).stem)
    module.__file__ = str(path)
    # Existing independent auditors use one direct text read for test.jsonl.
    # Bind that read to the same frozen bytes too; leave their arithmetic intact.
    source = data.decode()
    old = "(source / 'test.jsonl').read_text().splitlines()"
    if source.count(old) != 1:
        raise ValueError('Unexpected auditor direct-read shape')
    source = source.replace(old, "frozen_text(source / 'test.jsonl').splitlines()")
    def frozen_text(input_path):
        observed, content = checked_bytes(input_path, collect=True)
        if observed != manifest[str(input_path)]:
            raise ValueError('Changed source text')
        return content.decode()
    module.frozen_text = frozen_text
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def flags_for_panels(panels):
    flags = []
    for panel in panels:
        m = panel['metrics']
        if m['n'] < 30: flags.append({'code': 'small_population', 'panel': panel['key'], 'n': m['n']})
        if m['acc'] in (0, 1): flags.append({'code': 'exact_boundary_rate', 'panel': panel['key'], 'accuracy': m['acc']})
    for metric in ('acc', 'brier', 'ece', 'nll'):
        if len(panels) > 1 and len({p['metrics'][metric] for p in panels}) == 1:
            flags.append({'code': 'identical_metric_across_all_panels', 'metric': metric})
    return flags


def compare_panels(audit, run, matrix):
    panels = []
    for row_index in run['matrix_row_indices']:
        row = matrix['rows'][row_index]
        suite, population = row['dataset'].split('/')
        section = audit['suites'][suite]
        result = section[population][row['protocol']] if population in ('full', 'release') else section[row['protocol']]
        for key, value in row['metrics'].items():
            if not isinstance(result[key], (int, float)) or not math.isfinite(result[key]) or abs(result[key] - value) > 1e-10:
                raise ValueError('Recomputed matrix metric mismatch: ' + str(row_index) + '/' + key)
        panels.append({'key': str(row_index) + ':' + row['model'] + ':' + row['dataset'] + ':' + row['protocol'], 'matrix_row_index': row_index, 'metrics': result, 'historical_binding': row['audit_terminal_binding']})
    return panels


def inventory_check(plan, manifest):
    for run in plan['runs']:
        cfg = frozen_json(run['config'], manifest)
        for suite in cfg['suites']:
            actual = {str(p) for p in (Path(run['directory']) / suite['name'] / 'records').iterdir()}
            expected = {str(Path(run['directory']) / suite['name'] / 'records' / f'{i:06d}.json') for i in range(suite['records'])}
            if actual != expected: raise ValueError('Receipt file set mismatch: ' + run['name'])


def execute(plan_path, expected_plan_sha):
    observed, data = checked_bytes(plan_path, collect=True)
    if observed['sha256'] != expected_plan_sha: raise ValueError('Plan hash mismatch')
    plan = json.loads(data); out = Path(plan['out'])
    lock = (out / 'driver.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    generations = out / 'generations'; generations.mkdir(exist_ok=True)
    generation = generations / f'{len(list(generations.iterdir())) + 1:04d}'; generation.mkdir()
    status = {'utc': utc(), 'stage': 'before_hash', 'progress': 0, 'total': len(plan['inputs']), 'chips': 0, 'generation': str(generation)}
    atomic(generation / 'START.json', {'utc': utc(), 'plan_sha256': expected_plan_sha, 'pid': os.getpid()})
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(10):
            snapshot = {'utc': utc(), **status}; snapshot['utc'] = utc()
            atomic(out / 'digest.json', snapshot)
            (out / 'digest.md').write_text(f"E39 {snapshot['stage']} {snapshot['progress']}/{snapshot['total']} chips=0 generation={generation.name} utc={snapshot['utc']}\n")
            with (out / 'heartbeat.log').open('a') as f: f.write(json.dumps(snapshot) + '\n')
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    rc = 1
    try:
        before = hash_phase(plan['inputs'], generation, 'BEFORE', None, status)
        inventory_check(plan, before)
        matrix = frozen_json(plan['matrix_path'], before)
        selected = [i for i, row in enumerate(matrix['rows']) if row.get('audit_terminal_binding') == 'absent_legacy_inline_audit']
        if sorted(i for run in plan['runs'] for i in run['matrix_row_indices']) != selected or len(selected) != 28:
            raise ValueError('Legacy matrix coverage mismatch')
        panel_results = []; runs = []; population_flags = []; cache = out / 'completed_runs'; cache.mkdir(exist_ok=True)
        manifest_sha = sha_bytes(canonical(before))
        for index, run in enumerate(plan['runs'], 1):
            status.update(stage='independent_audit:' + run['name'], progress=index-1, total=len(plan['runs']))
            observation = inspect_container(run['container_id']); verify_container(observation, run)
            atomic(generation / (run['name'] + '.docker.json'), observation)
            done = Path(run['directory']) / 'DONE'
            done_observed, payload = checked_bytes(done, collect=True)
            if done_observed != before[str(done)] or not payload.startswith(b'rc=0 utc='):
                raise ValueError('Invalid original wrapper DONE')
            if (Path(run['directory']) / 'FAILED').exists(): raise ValueError('Conflicting original FAILED marker')
            result_path = cache / (run['name'] + '.json')
            binding_path = cache / (run['name'] + '.binding.json')
            cached = False
            if result_path.exists() and binding_path.exists():
                _, binding_bytes = checked_bytes(binding_path, collect=True)
                binding = json.loads(binding_bytes)
                result_observed, result_bytes = checked_bytes(result_path, collect=True)
                cached = binding['manifest_sha256'] == manifest_sha and binding['result_sha256'] == result_observed['sha256'] and binding['plan_sha256'] == expected_plan_sha
            if cached:
                audit = json.loads(result_bytes)
            else:
                auditor = load_auditor(run['auditor'], before)
                auditor.read = lambda path: frozen_json(path, before)
                def checked_digest(path):
                    value = file_hash(path)
                    if value != before[str(path)]: raise ValueError('Changed dependency during audit: ' + str(path))
                    return value['sha256']
                auditor.digest = checked_digest
                audit = auditor.audit(run['config'])
                if audit['status'] != 'VERIFIED_SCOPED': raise ValueError('Audit not accepted')
                atomic(result_path, audit)
                atomic(binding_path, {'manifest_sha256': manifest_sha, 'result_sha256': file_hash(result_path)['sha256'], 'plan_sha256': expected_plan_sha, 'utc': utc()})
            panel_results.extend(compare_panels(audit, run, matrix))
            config = frozen_json(run['config'], before)
            for suite in config['suites']:
                saved = frozen_json(str(Path(run['directory']) / suite['name'] / 'rows.json'), before)
                vectors = {canonical(row['p']) for row in saved}
                if len(vectors) == 1:
                    population_flags.append({'code': 'constant_probability_vector', 'run': run['name'], 'suite': suite['name'], 'questions': len(saved)})
            runs.append({'name': run['name'], 'result_path': str(result_path), 'result_sha256': file_hash(result_path)['sha256'], 'resumed_from_verified_result': cached, 'records': sum(s['records_verified'] for s in audit['suites'].values()), 'questions': sum(s['questions_verified'] for s in audit['suites'].values())})
        status.update(stage='after_hash', progress=0, total=len(plan['inputs']))
        after = hash_phase(plan['inputs'], generation, 'AFTER', before, status)
        inventory_check(plan, after)
        if sum(r['records'] for r in runs) != 8462 or sum(r['questions'] for r in runs) != 11495 or len(panel_results) != 28:
            raise ValueError('Final population coverage mismatch')
        flags = flags_for_panels(panel_results) + population_flags
        report = {'schema': 1, 'experiment': 'E39', 'utc': utc(), 'status': 'CURRENT_REAUDIT_COMPLETE_FLAGS_RETAINED' if flags else 'CURRENT_REAUDIT_COMPLETE_SCOPED', 'runs': runs, 'records': 8462, 'questions': 11495, 'panels': panel_results, 'review_flags': flags, 'plan_sha256': expected_plan_sha, 'before_manifest_sha256': file_hash(generation/'BEFORE.json')['sha256'], 'after_manifest_sha256': file_hash(generation/'AFTER.json')['sha256'], 'historical_binding': 'absent_legacy_inline_audit_unchanged', 'scope': 'Current saved evidence integrity and 28 legacy reference-panel metrics only. Does not recreate historical finisher binding, repeat inference, prove historical immutability/no contamination, or establish training gain. Actual new Docker exit must be checked separately after this process exits.'}
        atomic(generation / 'report.json', report)
        terminal = {'rc': 0, 'utc': utc(), 'plan_sha256': expected_plan_sha, 'report_sha256': file_hash(generation/'report.json')['sha256'], 'generation': str(generation)}
        atomic(generation / 'COMPLETE.json', terminal); atomic(out / 'LATEST_COMPLETE.json', terminal)
        status.update(stage='completed_scoped', progress=28, total=28, review_flags=len(flags)); rc=0
    except BaseException as exc:
        status.update(stage='failed', error=str(exc))
        atomic(generation / 'COMPLETE.json', {'rc': 1, 'utc': utc(), 'plan_sha256': expected_plan_sha, 'error': str(exc), 'generation': str(generation)})
        raise
    finally:
        stop.set(); thread.join()
        atomic(out / 'digest.json', {'utc': utc(), **status})
        (out / 'digest.md').write_text(f"E39 {status['stage']} {status['progress']}/{status['total']} chips=0 generation={generation.name} utc={utc()}\n")
        (generation / 'EXIT').write_text(f'rc={rc} utc={utc()}\n')
    return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    args = parser.parse_args()
    return execute(args.plan, args.plan_sha256)


if __name__ == '__main__':
    raise SystemExit(main())
