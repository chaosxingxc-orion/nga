"""Read-only, CPU-only verifier for the single pinned legacy Instruct completion.

No issuance, Docker, network, import of predecessor code, or resource operations.
The request digest is an OUT-OF-BAND parent trust input, never self-authentication.
Historical hash/reopen writers are not retroactively claimed to consume buffers.
"""
import argparse
import ast
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
ROOT = BASE/'r3_runs/instruct_k0_chip3_20261101_v1'
RUN = str(ROOT.relative_to(BASE))
EXECUTION = '4261e76402ff9b61fee41c98067fcecdaddb7af9a2b28964ea6d2a2203b2441b'
SPEC = '59872034731a8fe8f372a397c287037a045a024e3391bcb302705afcdcc25aed'
NAME = 'nga-r3-eng-eval-instruct-k0-chip3-20261101-v1-a1'
CID = 'c08d67d930f66eef7d0e914619259f9271ec1ee5010ededf6255ef38828ce692'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
SCHEMA_SHA = 'd144f1e8fcbdea2e64ce45535b06d852820af3a7f1ec9eb0bd79cd1bf984aa1f'
MAX_JSON = 2 * 1024**2
MAX_METADATA = 64 * 1024**2
MAX_LINE = 2 * 1024**2
MAX_RESULT = 512 * 1024**2
MAX_RESULTS = 4 * 1024**3
MAX_ROWS = 2000000
FIXED = dict(execution='execution.json', spec='plan.json', launch_spec='attempts/1/LAUNCH_SPEC.json',
             launch_receipt='attempts/1/LAUNCH_RECEIPT.json', claim='attempts/1/CLAIM.json',
             release='attempts/1/RELEASE.json', attempt_terminal='attempts/1/EXIT.json',
             root_terminal='ENGINEERING_EVAL_EXIT.json', supervisor_done='attempts/1/SUPERVISOR_DONE.json',
             evaluator_complete='results/EVAL_COMPLETE.track_kt.json',
             scoring_receipt='results/SCORING_RECEIPT.track_kt.json',
             run_identity='results/RUN_IDENTITY.json', unit_manifest='results/manifests/track_kt.json')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def equal(a, b, message):
    # JSON equality must distinguish false, 0, 0.0 and missing/null.
    require(type(a) is type(b), message)
    if isinstance(b, dict):
        require(a.keys() == b.keys(), message)
        for k in b: equal(a[k], b[k], message + ':' + k)
    elif isinstance(b, list):
        require(len(a) == len(b), message)
        for x, y in zip(a, b): equal(x, y, message)
    else:
        require(a == b, message)


def fields(doc, expected, label):
    require(type(doc) is dict, label)
    for k, v in expected.items():
        require(k in doc, label + ':missing ' + k)
        equal(doc[k], v, label + ':' + k)


def safe(path):
    require(type(path) is str and path.startswith('/'), 'absolute path required')
    p = Path(path)
    require(str(p) == path and '..' not in p.parts, 'noncanonical path')
    require(not any(x.lower() == 'test' or x.lower().startswith('test.') for x in p.parts), 'TEST forbidden')
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink forbidden')
    return p


def opened(path):
    """Walk with directory fds and NOFOLLOW; do not follow a swapped parent link."""
    p = safe(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in p.parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nxt
        leaf = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)
    if not stat.S_ISREG(os.fstat(leaf).st_mode):
        os.close(leaf)
        raise ValueError('regular file required')
    return os.fdopen(leaf, 'rb')


def digest(raw): return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            require(k not in d, 'duplicate JSON key')
            d[k] = v
        return d
    def bad(value): raise ValueError('nonfinite JSON: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def refcheck(ref):
    require(type(ref) is dict and set(ref) == {'path', 'sha256', 'bytes'}, 'exact artifact reference required')
    safe(ref['path'])
    require(type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'invalid digest')
    require(type(ref['bytes']) is int and ref['bytes'] > 0, 'invalid byte count')


class Checked:
    """All metadata parsed/compiled from one checked buffer, retaining original pins."""
    def __init__(self): self.buffers, self.refs, self.total = {}, {}, 0

    def raw(self, ref):
        refcheck(ref)
        path = ref['path']
        if path in self.refs:
            equal(ref, self.refs[path], 'conflicting path pin')
            return self.buffers[path]
        require(ref['bytes'] <= MAX_JSON, 'metadata size limit')
        with opened(path) as f:
            before = os.fstat(f.fileno())
            raw = f.read(MAX_JSON + 1)
            after = os.fstat(f.fileno())
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'changed open file')
        require(len(raw) == ref['bytes'] and digest(raw) == ref['sha256'], 'checked buffer pin mismatch: ' + path)
        self.total += len(raw)
        require(self.total <= MAX_METADATA, 'total metadata limit')
        self.refs[path], self.buffers[path] = dict(ref), raw
        return raw

    def doc(self, ref): return parse(self.raw(ref))


def timestamp(value):
    if type(value) in (int, float):
        require(math.isfinite(value) and value > 0, 'invalid numeric time')
        return value
    require(type(value) is str and value, 'missing time')
    t = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(t.tzinfo is not None, 'timezone required')
    require(t.year >= 2026, 'uninitialized time')
    return t.timestamp()


def schema_validate(value, schema):
    """The exact review schema uses this closed subset; unsupported keywords fail."""
    allowed = {'$schema', '$id', '$comment', 'type', 'const', 'required', 'properties',
               'additionalProperties', 'pattern', 'minimum', 'minLength', 'minItems',
               'uniqueItems', 'items', 'format'}
    require(set(schema) <= allowed, 'unsupported schema keyword')
    if 'const' in schema: equal(value, schema['const'], 'schema constant')
    if 'type' in schema:
        types = {'object': dict, 'array': list, 'string': str, 'integer': int}
        require(type(value) is types[schema['type']], 'schema type')
    if isinstance(value, dict):
        require(set(schema.get('required', [])) <= set(value), 'schema missing fields')
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False: require(set(value) <= set(props), 'schema extra fields')
        for k, v in value.items():
            if k in props: schema_validate(v, props[k])
    if isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0), 'schema empty array')
        if schema.get('uniqueItems'): require(len({json.dumps(x, sort_keys=True) for x in value}) == len(value), 'schema duplicates')
        for x in value: schema_validate(x, schema['items'])
    if isinstance(value, str):
        require(len(value) >= schema.get('minLength', 0), 'schema empty string')
        if 'pattern' in schema: require(re.search(schema['pattern'], value), 'schema pattern')
        if schema.get('format') == 'date-time': timestamp(value)
    if 'minimum' in schema: require(value >= schema['minimum'], 'schema minimum')


def derive(execution, spec, source):
    """Compile only the pinned pure command derivation AST, never the launcher."""
    tree = ast.parse(source)
    functions = {'require', 'profile', 'result_directory', 'is_baseline', 'expected_command', 'docker_command'}
    constants = {'BASE', 'IMAGE', 'R0_MODEL', 'ENTRY', 'GROUPS'}
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in functions)
             or (isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id in constants for t in n.targets))]
    require({n.name for n in nodes if isinstance(n, ast.FunctionDef)} == functions, 'missing derivation functions')
    scope = {'Path': Path}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<checked-pure-command-derivation>', 'exec'), scope)
    scorer = scope['expected_command'](spec, ROOT)
    equal(scorer, spec['command'], 'scorer command')
    argv = scope['docker_command'](execution, spec, ROOT/'execution.json', EXECUTION, 1)
    return argv, scorer


def container_policy(argv, image_config):
    require(argv[:4] == ['docker', 'run', '-d', '--pull=never'], 'Docker prefix')
    mounts, devices, env, ulimits = [], [], {}, []
    i = 4
    while argv[i] != '--entrypoint':
        arg = argv[i]
        if arg == '--network=none': i += 1; continue
        value = argv[i+1]; i += 2
        if arg == '--mount':
            parts = value.split(',')
            require(parts[0] == 'type=bind' and len(parts) in (3, 4), 'mount syntax')
            mounts.append(dict(Type='bind', Source=parts[1].removeprefix('src='),
                               Destination=parts[2].removeprefix('dst='), RW=len(parts) == 3))
        elif arg == '--device': devices.append(dict(PathOnHost=value, PathInContainer=value, CgroupPermissions='rwm'))
        elif arg == '-e':
            key, val = value.split('=', 1); require(key not in env, 'duplicate environment'); env[key] = val
        elif arg == '--ulimit':
            key, limits = value.split('='); soft, hard = limits.split(':')
            ulimits.append(dict(Name=key, Soft=int(soft), Hard=int(hard)))
        elif arg == '--name': equal(value, NAME, 'container name')
        elif arg == '--shm-size': equal(value, '64g', 'shm')
        else: raise ValueError('unexpected Docker option ' + arg)
    require(argv[i:i+3] == ['--entrypoint', 'python3', IMAGE], 'entrypoint/image')
    inherited = {}
    require(type(image_config.get('Env')) is list, 'missing effective image environment')
    for item in image_config['Env']:
        key, val = item.split('=', 1); require(key not in inherited, 'duplicate image env'); inherited[key] = val
    inherited.update(env)
    return dict(name=NAME, image=IMAGE, entrypoint=['python3'], cmd=argv[i+3:],
                mounts=sorted(mounts, key=lambda x: x['Destination']), devices=sorted(devices, key=lambda x: x['PathOnHost']),
                environment=inherited, network='none', auto_remove=False, restart={'Name': 'no', 'MaximumRetryCount': 0},
                shm_size=64*1024**3, ulimits=sorted(ulimits, key=lambda x: x['Name']),
                user=image_config['User'], working_dir=image_config['WorkingDir'])


def check_container(observation, argv):
    fields(observation, {'schema': 'k2-trusted-container-observation-v1', 'test_read': False,
                         'scientific_acceptance': False}, 'observer')
    image = observation['image_inspect']; equal(image['Id'], IMAGE, 'image observation')
    expected = container_policy(argv, image['Config'])
    actual = observation['inspect']
    fields(actual, {'Id': CID, 'Name': '/'+NAME, 'Image': IMAGE, 'RestartCount': 0}, 'container')
    config, host, state = actual['Config'], actual['HostConfig'], actual['State']
    fields(config, {'Entrypoint': expected['entrypoint'], 'Cmd': expected['cmd'], 'User': expected['user'],
                    'WorkingDir': expected['working_dir'], 'Image': IMAGE}, 'config')
    env = {}
    for item in config['Env']:
        key, val = item.split('=', 1); require(key not in env, 'duplicate actual env'); env[key] = val
    equal(env, expected['environment'], 'effective environment')
    fields(host, {'NetworkMode': 'none', 'AutoRemove': False, 'RestartPolicy': expected['restart'],
                  'ShmSize': expected['shm_size'], 'Privileged': False, 'ReadonlyRootfs': False,
                  'PidMode': '', 'IpcMode': 'private', 'CapAdd': None, 'CapDrop': None,
                  'SecurityOpt': None, 'Binds': None, 'VolumesFrom': None, 'DeviceRequests': None}, 'host policy')
    equal(sorted(host['Devices'], key=lambda x: x['PathOnHost']), expected['devices'], 'devices')
    equal(sorted(host['Ulimits'], key=lambda x: x['Name']), expected['ulimits'], 'ulimits')
    observed_mounts = []
    for m in actual['Mounts']:
        require(all(k in m for k in ('Type', 'Source', 'Destination', 'RW')), 'incomplete mount')
        observed_mounts.append({k: m[k] for k in ('Type', 'Source', 'Destination', 'RW')})
    equal(sorted(observed_mounts, key=lambda x: x['Destination']), expected['mounts'], 'mounts')
    fields(state, {'Status': 'exited', 'Running': False, 'Paused': False, 'Restarting': False,
                   'OOMKilled': False, 'Dead': False, 'ExitCode': 0, 'Error': ''}, 'state')
    require(timestamp(state['StartedAt']) < timestamp(state['FinishedAt']) <= timestamp(observation['observed_utc']), 'container time')
    return expected


def ledger_bytes(doc): return (json.dumps(doc, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()


def check_ledger(claim, release):
    fields(claim, {'schema': 'r3-resource-claim-v1', 'run': RUN, 'chip': 3, 'allocation': str(BASE/'CHIP-ALLOCATION.json')}, 'claim')
    fields(release, {'schema': 'r3-resource-release-v1', 'run': RUN, 'chip': 3,
                     'container': NAME, 'container_id': CID, 'exit_code': 0, 'scientific_acceptance': False}, 'release')
    for d in (claim, release):
        for side in ('before', 'after'):
            equal(digest(ledger_bytes(d['allocation_'+side])), d['allocation_'+side+'_sha256'], 'ledger serialization')
            ledger = d['allocation_'+side]
            require(type(ledger['chips']) is int and ledger['chips'] == 8, 'ledger chip count')
            entries = ledger['allocation'] + ledger['free']
            require(all(type(x['chip']) is int for x in entries), 'ledger chip type')
            require(sorted(x['chip'] for x in entries) == list(range(8)), 'ledger exclusive ownership')
    cb, ca = claim['allocation_before'], claim['allocation_after']
    rb, ra = release['allocation_before'], release['allocation_after']
    owner = claim['entry']
    fields(owner, {'run': RUN, 'chip': 3, 'claimed_utc': claim['claimed_utc']}, 'owner')
    pick = lambda ledger, key: [x for x in ledger[key] if x['chip'] == 3]
    equal(pick(cb, 'allocation'), [], 'claim before owner')
    require(len(pick(cb, 'free')) == 1, 'claim before free')
    equal(pick(ca, 'allocation'), [owner], 'claim owner'); equal(pick(ca, 'free'), [], 'claim free')
    equal(pick(rb, 'allocation'), [owner], 'ownership continuity'); equal(pick(rb, 'free'), [], 'release before free')
    equal(pick(ra, 'allocation'), [], 'release owner')
    free = pick(ra, 'free'); require(len(free) == 1, 'release free')
    fields(free[0], {'chip': 3, 'previous_run': RUN, 'release_evidence': str(ROOT/FIXED['release'])}, 'release reference')
    require(timestamp(free[0]['released_utc']) <= timestamp(release['released_utc']), 'release free time')
    # Changes on other chips are permitted between claim and release, not during either transaction.
    for before, after in ((cb, ca), (rb, ra)):
        for key in ('allocation', 'free'):
            equal([x for x in before[key] if x['chip'] != 3], [x for x in after[key] if x['chip'] != 3], 'unrelated transaction mutation')


def check_terminals(d, observation):
    t = d['attempt_terminal']; equal(t, d['root_terminal'], 'terminal copies')
    require('plan_sha256' not in t, 'legacy branch forbids any terminal pin')
    fields(t, {'attempt': 1, 'exit_code': 0, 'scientific_acceptance': False}, 'terminal')
    require('source' not in t, 'fallback terminal not successful scorer evidence')
    fields(d['supervisor_done'], {'exit_code': 0, 'scientific_acceptance': False}, 'DONE')
    fields(d['evaluator_complete'], {'exit_code': 0, 'error': None}, 'evaluator')
    state = observation['inspect']['State']; release = d['release']
    fields(release, {'container_started_at': state['StartedAt'], 'container_finished_at': state['FinishedAt']}, 'release times')
    # Evaluator utc is second precision; compare its containing second to driver time.
    sequence = [timestamp(d['claim']['claimed_utc']), timestamp(state['StartedAt']),
                timestamp(d['evaluator_complete']['utc'])+1, timestamp(t['utc_seconds'])+1,
                timestamp(state['FinishedAt'])+1, timestamp(release['released_utc'])+1,
                timestamp(observation['observed_utc'])+1]
    require(sequence == sorted(sequence), 'completion ordering')
    require(timestamp(t['utc_seconds']) <= timestamp(state['FinishedAt']), 'driver after container finish')


def expected_outputs(scorer):
    groups = scorer[scorer.index('--k-only')+1].split(',')
    names = {'trackk/'+suite+'__'+split+'/'+kind+'.jsonl' for suite, split, kind in (g.split('/') for g in groups)}
    for role in ('primary', 'empty_input', 'question_only'):
        for task in ('T1', 'T2', 'T3'):
            for src in (('typed-decisions',) if task == 'T3' else ('typed-decisions', 'openjev-synth', 'akhilaaa3')):
                names.add(f'trackt/readouts/{role}__{task}__{src}__shard0of1.jsonl')
    return names


def check_results(d, refs, spec, scorer, checked):
    receipt, manifest, rid = d['scoring_receipt'], d['unit_manifest'], d['run_identity']
    fields(receipt, {'schema': 'r3-scoring-receipt-v1', 'scientific_acceptance': False,
                     'scope': 'producer header only; CPU must verify and rebuild metrics from readouts',
                     'track_k': {'partitions': {}}}, 'scoring receipt')
    h = receipt['header']
    fields(h, {'argv': scorer[2:], 'arm': 'K0', 'stages': 'k_score,t_score', 'partitions': ['dev', 'calibration'],
               'dtype': 'float32', 'device': 'npu:0', 'track_t_config': 'r3', 'limit': 0, 'limit_groups': 0,
               'dry_run_warnings': [], 'provenance_manifest': str(ROOT/FIXED['unit_manifest'])}, 'header')
    prompt_paths = [p for p in spec['files'] if p.endswith('/r0_code/prompt.py')]
    require(len(prompt_paths) == 1, 'prompt source missing')
    prompt = ast.parse(checked.buffers[prompt_paths[0]])
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in prompt.body
                 if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                 and n.targets[0].id in ('PROMPT_VERSION', 'PROMPT_FORMAT')}
    fields(h, {'prompt_version': constants['PROMPT_VERSION'], 'prompt_format': constants['PROMPT_FORMAT'],
               'render': 'record_name', 'primary_input_mode': 'full',
               'track_t_sources': 'typed-decisions,openjev-synth,akhilaaa3'}, 'prompt and input protocol')
    require(timestamp(h['utc']) <= timestamp(manifest['utc']) <= timestamp(d['evaluator_complete']['utc'])+1,
            'result provenance ordering')
    model = spec['model']
    complete = str(Path(model)/'.complete')
    with opened(complete) as f: raw = f.read(MAX_JSON+1)
    require(len(raw) <= MAX_JSON and digest(raw) == spec['files'][complete], 'model revision pin')
    complete_ref = dict(path=complete, sha256=digest(raw), bytes=len(raw))
    require(complete not in checked.refs, 'unexpected duplicate revision input')
    checked.refs[complete], checked.buffers[complete] = complete_ref, raw
    checked.total += len(raw)
    require(checked.total <= MAX_METADATA, 'total metadata limit')
    revision = raw.decode().splitlines()[0].strip(); require(revision and revision != 'unknown', 'model revision absent')
    weights = {str(Path(p).relative_to(model)): sha for p, sha in spec['files'].items()
               if Path(p).is_relative_to(model) and Path(p).suffix in ('.safetensors', '.bin', '.pt')}
    require(weights, 'missing expected weights')
    model_sha = digest(json.dumps(dict(kind='checkpoint', weight_files=weights, revision=revision),
                                 sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())
    fields(h['model'], dict(path=model, sha256=model_sha, kind='checkpoint', base_path=model, base_revision=revision), 'model')
    fields(rid, dict(model_sha256=model_sha, model_path=model, arm='K0', track_t_config='r3', prompt_version=h['prompt_version']), 'run identity')
    fields(manifest, dict(model_sha256=model_sha, stamp=model_sha[:16], tag='track_kt', scorer=h['scorer']), 'manifest')
    fields(h['scorer'], {'record_grade': True, 'mode': 'rightpad', 'dtype': 'float32', 'token_budget': 16384}, 'scorer')
    fields(h['scorer']['hf32'], {'hf32': False}, 'HF32')
    require(type(h['data_files']) is dict and h['data_files'], 'data identities missing')
    expected_data = {p: spec['files'][p] for p in spec['readonly_data_mounts'] if Path(p).suffix == '.jsonl'}
    equal(h['data_files'], expected_data, 'exact scorer data inventory')
    for p, sha in h['data_files'].items():
        safe(p); require(p in spec['readonly_data_mounts'] and sha == spec['files'][p], 'data identity')
    expected = expected_outputs(scorer)
    equal(set(manifest['files']), expected, 'output inventory')
    result_map = {r['path']: r for r in refs}
    require(len(result_map) == len(refs), 'duplicate output reference')
    equal(set(result_map), {str(ROOT/'results'/x) for x in expected}, 'result paths')
    # Only enumerate allowed readout trees; never open TEST or logs.
    actual = set()
    for subtree in ('trackk', 'trackt'):
        for base, dirs, files in os.walk(ROOT/'results'/subtree, followlinks=False):
            for name in dirs: safe(str(Path(base)/name))
            for name in files:
                p = safe(str(Path(base)/name))
                if p.suffix == '.jsonl': actual.add(str(p))
    equal(actual, set(result_map), 'unlisted readouts')
    seen, total, total_rows = set(), 0, 0
    for path in sorted(result_map):
        ref = result_map[path]; require(set(ref) == {'path', 'sha256', 'bytes', 'rows'}, 'result reference shape')
        refcheck({k: ref[k] for k in ('path', 'sha256', 'bytes')})
        require(ref['bytes'] <= MAX_RESULT and type(ref['rows']) is int and 0 < ref['rows'] <= MAX_ROWS, 'result limits')
        rel = str(Path(path).relative_to(ROOT/'results'))
        equal(manifest['files'][rel], {'sha256': ref['sha256'], 'rows': ref['rows']}, 'manifest file edge')
        role = 'trackt/'+Path(path).name.split('__')[0] if rel.startswith('trackt/') else rel
        hsh, size, rows = hashlib.sha256(), 0, 0
        with opened(path) as f:
            before = os.fstat(f.fileno())
            while True:
                line = f.readline(MAX_LINE+1)
                if not line: break
                require(len(line) <= MAX_LINE and line.endswith(b'\n'), 'partial/oversize result row')
                size += len(line); total += len(line)
                require(size <= ref['bytes'] and total <= MAX_RESULTS, 'result byte limit')
                hsh.update(line)
                if not line.strip(): continue
                row = parse(line); fields(row, {'m': model_sha[:16]}, 'row stamp')
                require(type(row.get('k')) is str and row['k'], 'missing row key')
                key = (role, row['k']); require(key not in seen, 'duplicate role/key'); seen.add(key)
                rows += 1; total_rows += 1
                require(total_rows <= MAX_ROWS, 'total row limit')
            after = os.fstat(f.fileno())
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'changed result')
        equal((size, rows, hsh.hexdigest()), (ref['bytes'], ref['rows'], ref['sha256']), 'result buffer pin')
    return {'files': len(refs), 'rows': total_rows, 'bytes': total, 'expected_model_sha256': model_sha}


def verify(request_path, request_sha256, consumer_plan_sha256):
    """Return original-byte evidence pins. No files are created or mutated."""
    checked = Checked()
    with opened(str(request_path)) as f: raw = f.read(MAX_JSON+1)
    require(len(raw) <= MAX_JSON and digest(raw) == request_sha256, 'external request pin')
    request_ref = dict(path=str(request_path), sha256=request_sha256, bytes=len(raw))
    checked.refs[str(request_path)], checked.buffers[str(request_path)] = request_ref, raw
    checked.total = len(raw)
    request = parse(raw)
    fields(request, {'schema': 'k2-completion-verification-request-v1', 'consumer_plan_sha256': consumer_plan_sha256,
                     'activation_authorized': False, 'scientific_acceptance': False, 'test_read': False}, 'request')
    require(request.get('ready') is True, 'request is preparation only; evidence missing')
    require(type(request.get('parent_id')) is str and request['parent_id'], 'parent identity')
    for identity in ('reviewer_id', 'observer_id'):
        require(type(request.get(identity)) is str and request[identity], 'external identity missing')
    schema_ref = request['witness_schema']; equal(schema_ref['sha256'], SCHEMA_SHA, 'review schema pin')
    schema = checked.doc(schema_ref)
    witness_ref = request['witness']; w = checked.doc(witness_ref); schema_validate(w, schema)
    equal(w['consumer_plan_sha256'], consumer_plan_sha256, 'consumer replay')
    equal(w['verifier'], request['verifier'], 'verifier binding')
    equal(request['verifier']['path'], str(Path(__file__).absolute()), 'verifier path')
    checked.raw(request['verifier'])
    require(request['reviewer_id'] != w['issuer_id'], 'independent chain reviewer required')
    parent = checked.doc(request['parent_attestation'])
    fields(parent, {'schema': 'k2-completion-parent-attestation-v1', 'parent_id': request['parent_id'],
                    'consumer_plan_sha256': consumer_plan_sha256, 'witness': witness_ref,
                    'verifier': w['verifier'], 'prelaunch_authentication': request['prelaunch_authentication'],
                    'container_observation': request['container_observation'],
                    'verification_report': w['artifacts']['verification_report'], 'reviewer_id': request['reviewer_id'],
                    'issuer_id': w['issuer_id'], 'activation_authorized': False, 'scientific_acceptance': False,
                    'test_read': False}, 'external parent attestation')
    fields(w['authentication'], {'method': 'external-parent-pinned-attestation', 'authenticated_by': request['parent_id'],
                                 'trust_anchor': request['prelaunch_authentication']}, 'authentication')
    refs = w['artifacts']
    for k, rel in FIXED.items(): equal(refs[k]['path'], str(ROOT/rel), 'exact artifact path '+k)
    for key in ('prelaunch_authentication', 'container_observation'):
        equal(refs[key], request[key], 'external authentication edge')
    require(len({r['path'] for r in refs.values()}) == len(refs), 'artifact alias')
    d = {key: checked.doc(ref) for key, ref in refs.items()}
    e, s = d['execution'], d['spec']
    equal(refs['execution']['sha256'], EXECUTION, 'execution pin'); equal(refs['spec']['sha256'], SPEC, 'spec pin')
    fields(e, {'schema': 'r3-engineering-posttrain-execution-v1', 'run': RUN, 'out': str(ROOT), 'chip': 3,
               'container': NAME[:-3], 'spec': str(ROOT/'plan.json'), 'spec_sha256': SPEC,
               'execution_scope': 'engineering_only', 'scientific_acceptance': False, 'test_read': False}, 'execution')
    fields(s, {'schema': 'r3-baseline-dev-spec-v1', 'evaluation_profile': 'track_kt', 'test_read': False,
               'scientific_acceptance': False, 'image_sha256': IMAGE, 'network': 'none'}, 'spec')
    require(len(w['result_files']) == 32, 'exact result count')
    require(len(w['source_writers']) <= 128, 'source count limit')
    source_pins = {**e['tools'], **{p: h for p, h in s['files'].items() if p.endswith('.py')}}
    require(len({r['path'] for r in w['source_writers']}) == len(w['source_writers']), 'duplicate source')
    equal({r['path']: r['sha256'] for r in w['source_writers']}, source_pins, 'source closure')
    sources = {r['path']: checked.raw(r) for r in w['source_writers']}
    for mount in s['code_mounts']:
        require(mount['readonly'] is True, 'source mount writable')
        actual_sources = {str(p) for p in safe(mount['source']).rglob('*.py') if safe(str(p)).is_file()}
        require(actual_sources == {p for p in source_pins if Path(p).is_relative_to(mount['source'])}, 'unbound source closure')
    anchor = d['prelaunch_authentication']
    fields(anchor, {'schema': 'k2-prelaunch-parent-authentication-v1', 'parent_id': request['parent_id'],
                    'execution': refs['execution'], 'spec': refs['spec'], 'source_writers': w['source_writers'],
                    'historical_trust_scope': 'prelaunch-verification-and-retained-container-observation',
                    'source_consumption_proven': False, 'test_read': False, 'scientific_acceptance': False}, 'prelaunch anchor')
    # These are separately authenticated existing root receipts, not synthetic execution proof.
    pre = checked.doc(anchor['prelaunch_receipt']); act = checked.doc(anchor['activation_receipt'])
    equal(anchor['prelaunch_receipt']['path'], str(ROOT/'PRELAUNCH_VERIFIED.json'), 'prelaunch path')
    equal(anchor['activation_receipt']['path'], str(ROOT/'ACTUAL_ACTIVATION_VERIFIED.json'), 'activation path')
    fields(pre, {'execution_verified': True, 'scientific_acceptance': False}, 'prelaunch verification')
    historical = checked.doc(anchor['root_handoff'])
    fields(historical, {'status': 'INSTRUCT_K0_ENGINEERING_DEV_ACTIVATED_NOT_TERMINAL',
                        'root': str(ROOT), 'scientific_acceptance': False, 'completion': False}, 'root historical handoff')
    fields(historical['pins'], {'execution': EXECUTION, 'spec': SPEC,
                               'launcher': e['tools'][e['launcher']],
                               'resource_adapter': e['tools'][e['resource_adapter']]}, 'root historical pins')
    equal(historical['actual'], act, 'root historical observation')
    fields(act, {'container_id': CID, 'container_name': '/'+NAME, 'container_chip': 3, 'retained': True,
                 'supervisor_command_verified': True, 'ledger_owner_verified': True,
                 'launch_receipt_sha256': refs['launch_receipt']['sha256'], 'completion': False,
                 'scientific_acceptance': False}, 'historical observation')
    require(timestamp(pre['utc_seconds']) <= timestamp(anchor['verified_before_launch_utc']) <=
            timestamp(d['claim']['claimed_utc']), 'prelaunch ordering')
    fields(act['container_state'], {'Status': 'running', 'Running': True}, 'historical running state')
    observation = d['container_observation']
    equal(observation['observer_id'], request['observer_id'], 'external observer identity')
    authenticated_refs = {k: v for k, v in refs.items() if k in FIXED}
    equal(observation['artifacts'], authenticated_refs, 'authenticated terminal/result observations')
    equal(observation['result_files'], w['result_files'], 'authenticated result pins')
    argv, scorer = derive(e, s, sources[e['launcher']])
    equal(d['launch_spec'], {'command': argv, 'sha256': EXECUTION}, 'launch command')
    equal(d['launch_receipt'], {'id': CID, 'image': IMAGE, 'sha256': EXECUTION}, 'launch receipt')
    policy = check_container(observation, argv)
    fields(act['container_state'], {'StartedAt': observation['inspect']['State']['StartedAt']}, 'historical generation')
    require(timestamp(observation['inspect']['State']['StartedAt']) <= timestamp(act['utc_seconds']) <
            timestamp(observation['inspect']['State']['FinishedAt']), 'launch observation time')
    equal(w['derived']['docker_argv'], argv, 'witness Docker derivation')
    equal(w['derived']['scorer_argv'], scorer, 'witness scorer derivation')
    equal(checked.doc(w['derived']['container_spec']), policy, 'derived container spec')
    check_ledger(d['claim'], d['release']); check_terminals(d, observation)
    results = check_results(d, w['result_files'], s, scorer, checked)
    state = observation['inspect']['State']
    fields(w['completion'], {'started_at': state['StartedAt'], 'finished_at': state['FinishedAt'],
                            'released_utc': d['release']['released_utc'], 'observed_utc': observation['observed_utc']}, 'completion envelope')
    require(timestamp(observation['observed_utc']) <= timestamp(w['issued_utc']) <= timestamp(parent['attested_utc']), 'attestation ordering')
    report = d['verification_report']
    fields(report, {'schema': 'k2-completion-chain-verification-v1', 'reviewer_id': request['reviewer_id'],
                    'consumer_plan_sha256': consumer_plan_sha256, 'artifacts': authenticated_refs,
                    'source_writers': w['source_writers'], 'result_files': w['result_files'], 'results': results,
                    'derived': w['derived'], 'test_read': False, 'scientific_acceptance': False,
                    'activation_authorized': False}, 'verification report')
    return dict(status='VERIFIED_LEGACY_COMPLETION_NOT_ACTIVATION', consumer_plan_sha256=consumer_plan_sha256,
                checked_metadata=list(checked.refs.values()), result_files=w['result_files'], results=results,
                source_consumption_proven=False, activation_authorized=False, scientific_acceptance=False, test_read=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True); parser.add_argument('--sha256', required=True)
    parser.add_argument('--consumer-plan-sha256', required=True)
    a = parser.parse_args()
    try:
        result = verify(a.request, a.sha256, a.consumer_plan_sha256)
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as error:
        print(json.dumps({'status': 'REFUSED', 'reason': str(error), 'activation_authorized': False}))
        return 1
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
