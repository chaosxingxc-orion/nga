#!/usr/bin/env python3
"""E35 supplemental, read-only JEVal acceptance; never mutates frozen E33 runs.

Run under the immutable CPU image with TORCH_DEVICE_BACKEND_AUTOLOAD=0 and
python3 -P. The original frozen verifier still owns the original metric arithmetic.
This independent supplement checks omitted schemas, tokenization and launch closure.
"""
import argparse
import collections
import hashlib
import http.client
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time

MIN_N = 30  # tools/watchdog.py --min-n default, not a score-selection threshold.
IDENTITY_KEYS = {'index', 'id', 'input_sha256', 'request_sha256', 'config_sha256',
                 'type', 'source', 'source_item_id'}
SCRIPT_NAMES = ['jeval_reference_inference.py', 'jeval_reference_preflight.py',
                'verify_jeval_reference_inference.py', 'prepare_jeval_reference_inference.py',
                'jeval_reference_finish.py', 'test_jeval_reference_inference.py',
                'test_jeval_reference_chain.py']


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def stamp(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def receipt_manifest(run, expected_count=11257):
    """Bind the complete ordered receipt population, not just aggregate reports.

    The root authenticates the canonical JSON body (all fields except root_sha256).
    Consumers must rebuild this from disk immediately before acceptance/release;
    the stored root alone does not prove that the receipt files still exist.
    """
    require(type(expected_count) is int and expected_count >= 0, 'Receipt expected count')
    folder = Path(run) / 'records'
    require(folder.is_dir() and not folder.is_symlink(), 'Receipt directory missing/aliased')
    paths = sorted(folder.iterdir(), key=lambda p: p.name)
    require([p.name for p in paths] == [f'{i:06d}.json' for i in range(expected_count)],
            'Receipt manifest population')
    require(all(p.is_file() and not p.is_symlink() for p in paths), 'Receipt manifest file type')
    body = dict(schema=1, algorithm='sha256', count=expected_count,
                entries=[dict(path='records/' + p.name, sha256=sha(p)) for p in paths])
    root = hashlib.sha256(json.dumps(body, ensure_ascii=False, allow_nan=False,
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return dict(body, root_sha256=root)


def verify_receipt_manifest(run, manifest, expected_count=11257):
    require(isinstance(manifest, dict) and set(manifest) ==
            {'schema', 'algorithm', 'count', 'entries', 'root_sha256'}, 'Receipt manifest schema')
    require(type(manifest['schema']) is int and manifest['schema'] == 1 and
            manifest['algorithm'] == 'sha256' and type(manifest['count']) is int and
            manifest['count'] == expected_count, 'Receipt manifest protocol/count')
    entries = manifest['entries']
    require(isinstance(entries, list) and len(entries) == expected_count,
            'Receipt manifest entry count')
    for i, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {'path', 'sha256'} and
                entry['path'] == f'records/{i:06d}.json' and
                isinstance(entry['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', entry['sha256']),
                'Receipt manifest entry schema/order')
    require(isinstance(manifest['root_sha256'], str) and
            re.fullmatch(r'[0-9a-f]{64}', manifest['root_sha256']), 'Receipt manifest root schema')
    actual = receipt_manifest(run, expected_count)
    require(actual == manifest, 'Receipt manifest differs from current artifacts')
    return actual


def publish_text(path, text):
    """Publish a complete fsynced artifact atomically without replacing evidence.

    An interrupted/failed write leaves its uniquely named pending file for diagnosis.
    Hard-link publication is atomic on the same filesystem and refuses a destination
    created by another writer after the caller's initial existence check.
    """
    path = Path(path)
    require(not path.exists(), 'Existing supplemental evidence preserved')
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.pending-')
    with os.fdopen(fd, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.link(temporary, path)
    os.unlink(temporary)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def keys(q):
    return (['false', 'true'] if q['type'] == 'noul' else list(q['criteria'])
            if q['type'] == 'choice' else list(map(str, range(len(q['criteria'])))))


def exact_eligibility(family, q, observed, expected):
    """Require the complete output schema of E31 check(), including failure arms."""
    required = {'status', 'reason', 'candidate_count'}
    status, reason = expected['status'], expected['reason']
    if family == 'kev':
        require(status in ('eligible', 'overlength'), 'Kev eligibility status')
        if reason == 'native_context_overflow':
            require(status == 'overlength', 'Overflow status')
            required |= {'native_message', 'state_tokens'}
        else:
            require((status, reason) in (('eligible', 'within_native_budget'),
                                        ('overlength', 'packed_limit_16384')), 'Kev eligibility reason')
            required |= {'max_tokens', 'state_tokens', 'token_sha256'}
    elif family == 'openjev':
        require((status, reason) in (('eligible', 'within_native_budget'),
                                    ('overlength', 'candidate_limit_4096')), 'OpenJev eligibility reason')
        required |= {'max_tokens', 'lengths', 'token_sha256', 'native_record_sha256'}
    else:
        require(family == 'nimble', 'Unknown family')
        if status == 'unsupported':
            require(reason in ('native_v1_candidate_limit_26',
                               'native_nonempty_context_required'), 'Nimble unsupported reason')
        elif status == 'overlength':
            require(reason == 'native_prompt_limit_2048', 'Nimble overlength reason')
            required.add('max_tokens')
        else:
            require((status, reason) == ('eligible', 'within_native_budget'), 'Nimble eligible reason')
            required |= {'max_tokens', 'token_sha256', 'candidate_token_ids'}
    require(set(expected) - IDENTITY_KEYS == required, 'E31 eligibility schema')
    require(isinstance(observed, dict) and set(observed) == required, 'Complete eligibility schema')
    require(observed == {k: expected[k] for k in required}, 'Exact eligibility values')
    require(type(observed['candidate_count']) is int and
            observed['candidate_count'] == len(keys(q)), 'Eligibility candidate count')


def prediction(c, q, value, expected_tokens):
    """Independently reconstruct native response from raw logits and probabilities."""
    require(set(value) == {'answer', 'native_probabilities', 'logits',
                           'logits_temperature', 'consumed_token_sha256'}, 'Prediction schema')
    ks = keys(q)
    z, native = value['logits'], value['native_probabilities']
    require(isinstance(z, list) and len(z) == len(ks) and all(finite(x) for x in z), 'Logit schema')
    require(isinstance(native, dict) and list(native) == ks and
            all(finite(x) and 0 <= x <= 1 for x in native.values()), 'Native probability schema')
    pp = list(native.values())
    require(abs(sum(pp) - 1) <= 1e-5, 'Native probability mass')
    scaled = c['family'] == 'kev'
    require(value['logits_temperature'] == ('already_scaled' if scaled else 'unscaled'), 'Logit temperature')
    temp = 1. if scaled else c['temperature']
    require(finite(temp) and temp > 0, 'Temperature')
    ex = [math.exp((x - max(z)) / temp) for x in z]
    require(max(abs(x - y / sum(ex)) for x, y in zip(pp, ex)) <= 1e-5, 'Logit probability arithmetic')
    require(value['consumed_token_sha256'] == expected_tokens, 'Probe consumed tokens')
    a = value['answer']
    require(isinstance(a, dict) and a.get('type') == q['type'], 'Answer type')
    rounder = (lambda x: round(float(x), 4)) if scaled else float
    best = max(range(len(ks)), key=pp.__getitem__)
    if q['type'] == 'noul':
        require(set(a) == {'type', 'noul'} and finite(a['noul']) and
                0 <= a['noul'] <= 1 and abs(a['noul'] - rounder(pp[1])) < 1e-8, 'Noul wire')
        return
    allowed = {'type', 'probabilities', 'confidence'} | ({'choice'} if q['type'] == 'choice' else {'score', 'legend'})
    require(set(a) == allowed, 'Answer schema')
    probs = a['probabilities']
    require(isinstance(probs, dict) and list(probs) == ks and
            all(finite(v) and 0 <= v <= 1 for v in probs.values()), 'Wire probability schema')
    wire = [x / sum(pp) for x in pp] if c['family'] == 'openjev' else pp
    require(max(abs(probs[k] - rounder(x)) for k, x in zip(ks, wire)) < 1e-8, 'Wire probabilities')
    require(finite(a['confidence']) and 0 <= a['confidence'] <= 1, 'Wire confidence')
    if q['type'] == 'choice':
        require(type(a['choice']) is str and a['choice'] == ks[best], 'Returned choice')
        conf = wire[best] if c['family'] == 'nimble' else (1. if len(ks) == 1 else
                   (max(wire) / sum(wire) - 1 / len(ks)) / (1 - 1 / len(ks)))
    else:
        require(isinstance(a['legend'], dict) and list(a['legend']) == ks and
                list(a['legend'].values()) == q['criteria'], 'Score legend')
        score = best if c['family'] == 'nimble' else sum(i * p for i, p in enumerate(wire))
        require(finite(a['score']) and 0 <= a['score'] <= len(ks) - 1 and
                abs(a['score'] - rounder(score)) < 1e-7, 'Returned score')
        if c['family'] == 'nimble':
            conf = wire[best]
        elif len(ks) == 1:
            conf = 1.
        else:
            deviation = sum(abs(i - (len(ks) - 1) / 2) for i in range(len(ks))) / len(ks)
            conf = max(0., 1 - sum(p / sum(wire) * abs(i - best) for i, p in enumerate(wire)) / deviation)
    require(abs(a['confidence'] - rounder(conf)) < 1e-7, 'Native confidence')


def strict_probes(c, probes, eligibility, rows, tokenize):
    require(isinstance(probes, list) and len(probes) == 4, 'Probe count')
    boundary = max((e for e in eligibility['items'] if e['status'] == 'eligible'),
                   key=lambda e: (e['max_tokens'], -e['index']))
    for i, probe in enumerate(probes):
        if i < 3:
            kind = ['choice', 'noul', 'score'][i]
            q = {'type': kind, 'instructions': 'Choose the appropriate synthetic level.'}
            if kind != 'noul':
                q['criteria'] = {'a': 'first', 'b': 'second'} if kind == 'choice' else ['low', 'middle', 'high']
            req = {'state': 'Synthetic observation: choose the first level.', 'questions': {'q': q}}
            require(set(probe) == {'request', 'passes'} and probe['request'] == req, 'Synthetic request schema')
        else:
            require(set(probe) == {'boundary_index', 'input_sha256', 'max_tokens', 'passes',
                                    'chips', 'reserved_gib'}, 'Boundary schema')
            raw = rows[boundary['index']]
            req = {'state': raw['state'], 'questions': json.loads(raw['questions_json'])}
            q = next(iter(req['questions'].values()))
            require(probe['boundary_index'] == boundary['index'] and probe['input_sha256'] == stamp(raw)
                    and probe['max_tokens'] == boundary['max_tokens'], 'Boundary identity')
            require(probe['chips'] == 1 and finite(probe['reserved_gib']) and probe['reserved_gib'] > 0, 'Probe memory')
        actual = tokenize(req)
        require(actual['status'] == 'eligible', 'Probe retokenized eligibility')
        if i == 3:
            exact_eligibility(c['family'], q, actual, boundary)
        passes = probe['passes']
        require(isinstance(passes, list) and len(passes) == 2, 'Probe repeats')
        for one in passes:
            require(set(one) == {'seconds', 'prediction'} and finite(one['seconds']) and one['seconds'] > 0, 'Probe timing')
            prediction(c, q, one['prediction'], actual['token_sha256'])
        a, b = [one['prediction']['native_probabilities'] for one in passes]
        require(max(abs(a[k] - b[k]) for k in a) <= 1e-5, 'Probe repeated drift')
    return {'groups': 4, 'forwards': 8, 'tokenization': 'independent CPU native retokenization of all four requests',
            'boundary_index': boundary['index'], 'max_tokens': boundary['max_tokens']}


def required_closure(c):
    run = Path(c['out'])
    finish = Path(str(run) + '_finish')
    required = {str((run / n).resolve()) for n in SCRIPT_NAMES + ['NPU_SPEC.json', 'run.sh', 'LAUNCH_EXACT.sh', 'RESUME_EXACT.sh']}
    required |= {str((finish / n).resolve()) for n in ['run.sh', 'LAUNCH_EXACT.sh']}
    # Newer generations additionally ship resource-binding tests. No omission of a
    # present executable is allowed, while original v1 legitimately lacks this test.
    required |= {str(p.resolve()) for p in run.glob('*.py')}
    config_paths = ['data', 'preregistration', 'eligibility_config', 'eligibility_report']
    if c.get('mode', 'inference') == 'inference':
        config_paths += ['probe_config', 'probe_report', 'probe_review']
    required |= {str(Path(c[k]).resolve()) for k in config_paths}
    for role in ['base', 'code', 'adapter' if c.get('family') == 'nimble' else 'checkpoint']:
        if role not in c:  # Small closure unit fixtures omit native roots.
            continue
        root = Path(c[role]); require(root.is_dir(), 'Native dependency directory')
        required |= {str(p.resolve()) for p in root.rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    require(required <= set(c['files']), 'Required execution/finisher closure omitted')
    for p in required:
        require(sha(p) == c['files'][p], 'Required file changed: ' + p)
    return len(required)


def native_binding(c):
    """Authenticate all declared files before importing frozen/native Python."""
    require(c['family'] in ('kev', 'openjev', 'nimble'), 'Native family')
    require(c['runtime'] == {'torch': '2.10.0+cpu', 'torch_npu': '2.10.0.post7',
                             'transformers': '5.14.1', 'peft': '0.21.2'}, 'Frozen runtime protocol')
    roles = ['base', 'code', 'adapter' if c['family'] == 'nimble' else 'checkpoint']
    require(set(c['dependency_roles']) == set(roles), 'Dependency role schema')
    for path, expected_hash in c['files'].items():
        require(sha(path) == expected_hash, 'Frozen dependency changed: ' + path)
    ec = load(c['eligibility_config']); er = load(c['eligibility_report'])
    require(er['config_sha256'] == sha(c['eligibility_config']) and er['rows'] == 11257 and
            len(er['items']) == 11257 and er['data_sha256'] == sha(c['data']) ==
            '88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82', 'Eligibility data binding')
    for role in roles:
        require(c[role] == ec[role], 'Eligibility dependency path')
        prefix = str(Path(c[role]).resolve()) + '/'
        require({p: h for p, h in c['files'].items() if p.startswith(prefix)} ==
                {p: h for p, h in ec['files'].items() if p.startswith(prefix)}, 'Eligibility native closure')
    require(c['temperature'] == ec['temperature'], 'Eligibility temperature')
    require(Path(c['base'], '.complete').read_text().splitlines()[0] == c['base_revision'], 'Base revision')
    if c['family'] == 'nimble':
        adapter = load(Path(c['adapter']) / 'adapter_config.json')
        require(adapter['revision'] == c['base_revision'], 'Nimble adapter revision')
    return er


def mapping(host):
    return (sorted(host.get('Binds') or []),
            sorted((d['PathOnHost'], d['PathInContainer'], d['CgroupPermissions']) for d in host.get('Devices') or []))


def docker(name):
    conn = http.client.HTTPConnection('localhost', timeout=30)
    conn.sock = socket.socket(socket.AF_UNIX)
    conn.sock.settimeout(30)
    conn.sock.connect('/var/run/docker.sock')
    try:
        conn.request('GET', '/containers/' + name + '/json')
        res = conn.getresponse()
        require(res.status == 200, 'Docker identity unavailable')
        return json.loads(res.read())
    finally:
        conn.close()


def run_binding(c, cp, inspect=docker):
    run = Path(c['out'])
    receipt = load(run / 'LAUNCH_RECEIPT.json')
    spec = load(run / 'NPU_SPEC.json')
    info = inspect(receipt['container_id'])
    require(info['Id'] == receipt['container_id'] and info['Name'].lstrip('/') == c['container'], 'Docker ID/name')
    require(info['Image'] == receipt['image'] == spec['Image'] == c['image'], 'Docker image')
    require(info['Config']['Cmd'] == receipt['command'] == spec['Cmd'] == ['bash', str(run / 'run.sh')], 'Docker command')
    require(info['Config'].get('Entrypoint') == receipt['entrypoint'] == spec['Entrypoint'], 'Docker entrypoint')
    require(sorted(info['Config'].get('Env') or []) == sorted(spec.get('Env') or []), 'Docker environment differs')
    require(mapping(info['HostConfig']) == mapping(spec['HostConfig']), 'Docker mounts/devices')
    for key in ['NetworkMode', 'ShmSize']:
        require(info['HostConfig'][key] == spec['HostConfig'][key], 'Docker ' + key)
    chips = {d[0] for d in mapping(info['HostConfig'])[1] if re.fullmatch(r'/dev/davinci[0-9]+', d[0])}
    require(chips == {'/dev/davinci' + str(c['physical_chip'])}, 'Physical chip')
    require(info['State']['Status'] == 'exited' and info['State']['ExitCode'] == 0, 'Actual inference/probe exit')
    require(receipt['config_sha256'] == sha(cp) and receipt['wrapper_sha256'] == sha(run / 'run.sh'), 'Launch config/wrapper')
    require(re.fullmatch(r'rc=0 utc=\S+\n?', (run / 'EXIT').read_text()), 'Wrapper exit')
    return {'container_id': info['Id'], 'actual_exit': 0}


def finish_binding(c, cp, inspect=docker):
    run = Path(c['out']); finish = Path(str(run) + '_finish')
    receipt = load(finish / 'LAUNCH_RECEIPT.json'); term = load(finish / 'COMPLETE.json')
    info = inspect(receipt['container_id']); audit = load(finish / 'INDEPENDENT_AUDIT.json')
    require(info['Id'] == receipt['container_id'] and info['Name'].lstrip('/') == c['container'] + '-finish', 'Finisher ID/name')
    require(info['Image'] == receipt['image'] == c['image'], 'Finisher image')
    require(info['Config']['Cmd'] == receipt['command'] == [str(finish / 'run.sh')] and
            info['Config']['Entrypoint'] == receipt['entrypoint'] == ['bash'], 'Finisher command')
    require(mapping(info['HostConfig']) == (sorted(['/mnt/cephfs:/mnt/cephfs', '/var/run/docker.sock:/var/run/docker.sock']), []), 'Finisher resources')
    require(info['HostConfig']['NetworkMode'] == 'none' and 'TORCH_DEVICE_BACKEND_AUTOLOAD=0' in info['Config']['Env'], 'Finisher environment')
    require(info['State']['Status'] == 'exited' and info['State']['ExitCode'] == 0, 'Actual finisher exit')
    require(term['rc'] == 0 and term['config_sha256'] == receipt['config_sha256'] == audit['config_sha256'] == sha(cp), 'Finisher terminal identity')
    require(term['audit_sha256'] == sha(finish / 'INDEPENDENT_AUDIT.json') and receipt['wrapper_sha256'] == sha(finish / 'run.sh'), 'Finisher output/wrapper hash')
    require(audit['report_sha256'] == sha(run / 'report.json'), 'Finisher model report identity')
    require(re.fullmatch(r'rc=0 utc=\S+\n?', (finish / 'EXIT').read_text()), 'Finisher wrapper exit')
    require(term['review_flags'] == audit['review_flags'], 'Finisher flags changed')
    return {'container_id': info['Id'], 'actual_exit': 0, 'audit_sha256': term['audit_sha256'], 'review_flags': term['review_flags']}


def cell_analysis(rows, items):
    grouped = collections.defaultdict(list)
    for i, (row, item) in enumerate(zip(rows, items)):
        kind = next(iter(json.loads(row['questions_json']).values()))['type']
        for key in [('type', None, kind), ('source_type', row.get('source'), kind)]:
            grouped[key].append((i, row, item))
    cells, flags = [], []
    for (group, source, kind), entries in sorted(grouped.items(), key=lambda x: str(x[0])):
        valid = [(i, r, v) for i, r, v in entries if v['status'] == 'valid']
        cell = dict(group=group, source=source, type=kind, total=len(entries), valid=len(valid),
                    first_receipt=f'records/{entries[0][0]:06d}.json')
        if kind == 'score':
            cell['mae'] = sum(abs(v['answer']['score'] - json.loads(r['label_json'])) for _, r, v in valid) / len(valid) if valid else None
        else:
            correct = sum((v['answer']['noul'] >= .5 if kind == 'noul' else v['answer']['choice']) == json.loads(r['label_json']) for _, r, v in valid)
            cell.update(correct=correct, accuracy=correct / len(entries), valid_accuracy=correct / len(valid) if valid else None)
        cell['distinct_probability_vectors'] = len({stamp(list(v['native_probabilities'].values())) for _, _, v in valid})
        index = len(cells); cells.append(cell); pointer = f'/cells/{index}'
        def flag(code, metric):
            flags.append(dict(code=code, pointer=pointer + '/' + metric, evidence=cell['first_receipt']))
        if cell['total'] < MIN_N:
            flag('small_population', 'total')
        if cell['valid'] < MIN_N:
            flag('small_valid_population', 'valid')
        for metric in ['accuracy', 'valid_accuracy']:
            if cell.get(metric) in (0., 1.):
                flag('exact_boundary_rate', metric)
        if cell.get('mae') == 0.:
            flag('zero_score_mae', 'mae')
        if len(valid) >= 2 and cell['distinct_probability_vectors'] == 1:
            flag('identical_probability_vectors', 'distinct_probability_vectors')
    for group in ['type', 'source_type']:
        for kind in ['choice', 'noul', 'score']:
            for metric in (['mae'] if kind == 'score' else ['accuracy', 'valid_accuracy']):
                relevant = [(i, c[metric]) for i, c in enumerate(cells) if c['group'] == group and c['type'] == kind and c.get(metric) is not None]
                if len(relevant) >= 2 and len({v for _, v in relevant}) == 1:
                    flags.append(dict(code='identical_cell_metric', pointers=[f'/cells/{i}/{metric}' for i, _ in relevant]))
    return cells, flags


def tokenizer(c, run):
    # Rebuild the native CPU input path without constructing a model or reading labels.
    sys.path.insert(0, c['code'])
    from transformers import AutoTokenizer
    from importlib.metadata import version
    require(all(version(k) == v for k, v in c['runtime'].items()), 'Actual CPU runtime versions')
    native_check = module(run / 'jeval_reference_preflight.py', 'e35_frozen_preflight')
    tok = AutoTokenizer.from_pretrained(c.get('adapter', c['base']), local_files_only=True)
    if c['family'] == 'kev':
        from kev.api import SystemOneRequest, to_record
        from kev.model import encode, ContextOverflow
        native = (SystemOneRequest, to_record, encode, ContextOverflow)
    elif c['family'] == 'openjev':
        from jev.api import compile_request, candidate_prompts
        native = (compile_request, candidate_prompts)
    else:
        from nimble.scoring.release_contract import prompt_builder
        native = prompt_builder(c['adapter'], tok)
    return lambda req: native_check.check(req, c['family'], tok, native)


def check(cp, probe_only=False):
    os.environ.update(TORCH_DEVICE_BACKEND_AUTOLOAD='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    sys.dont_write_bytecode = True
    c = load(cp); ch = sha(cp); run = Path(c['out'])
    count = required_closure(c)
    eligibility = native_binding(c)
    require(c['mode'] == ('probe' if probe_only else 'inference'), 'Mode/CLI mismatch')
    receipts_before = receipt_manifest(run, 0 if probe_only else 11257)
    # The frozen verifier is authenticated before execution, never silently replaced.
    original = module(run / 'verify_jeval_reference_inference.py', 'e35_frozen_verifier')
    if probe_only:
        original.checkpoint_binding(c)
        import pyarrow.parquet as pq
        rows = pq.read_table(c['data']).to_pylist()
        require(len(rows) == 11257 and len({r['id'] for r in rows}) == 11257, 'Probe dataset population')
        term = load(run / 'COMPLETE.json')
        require(term['rc'] == 0 and term['stage'] == 'probe_completed' and term['progress'] == term['total'] == 4,
                'Probe complete terminal')
        require(term['config_sha256'] == ch and set(term['outputs']) == {'PROBE.json'} and
                term['outputs']['PROBE.json'] == sha(run / 'PROBE.json'), 'Probe terminal output identity')
        require((run / 'PROBE.json').stat().st_mtime_ns <= (run / 'COMPLETE.json').stat().st_mtime_ns <=
                (run / 'EXIT').stat().st_mtime_ns, 'Probe terminal chronology')
        require(receipts_before['count'] == 0, 'Probe emitted test receipts')
        result = strict_probes(c, load(run / 'PROBE.json'), eligibility, rows, tokenizer(c, run))
        actual = run_binding(c, cp)
        native_binding(c)
        require(sha(cp) == ch and sha(run / 'PROBE.json') == term['outputs']['PROBE.json'], 'Probe changed during audit')
        verify_receipt_manifest(run, receipts_before, expected_count=0)
        return dict(status='VERIFIED_HARDENED_PROBE_SCOPED', mode='probe', config_sha256=ch,
                    probe_sha256=term['outputs']['PROBE.json'], supplemental_required_files=count,
                    probes=result, containers={'probe': actual}, review_flags=[], inherited_review_flags=[],
                    utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    scope='Independent native probe schema/arithmetic and CPU retokenization of four requests; actual retained Docker/exit and full frozen closure. Not full-test metrics, memory-envelope certification, or Astra approval.')
    original_result = original.check(cp)
    import pyarrow.parquet as pq
    rows = pq.read_table(c['data']).to_pylist()
    probes = strict_probes(c, load(run / 'PROBE.json'), eligibility, rows, tokenizer(c, run))
    pc = Path(c['probe_config']); probe_c = load(pc)
    pt = load(Path(probe_c['out']) / 'COMPLETE.json')
    require(pt['rc'] == 0 and pt['stage'] == 'probe_completed' and pt['progress'] == pt['total'] == 4,
            'Probe complete terminal')
    require(pt['config_sha256'] == sha(pc) and set(pt['outputs']) == {'PROBE.json'} and
            pt['outputs']['PROBE.json'] == sha(c['probe_report']), 'Probe terminal output identity')
    required_closure(probe_c)
    native_binding(probe_c)
    for key in ['family', 'base', 'code', 'temperature', 'runtime', 'eligibility_config', 'eligibility_report']:
        require(c[key] == probe_c[key], 'Probe configuration identity: ' + key)
    for role in c['dependency_roles']:
        require(c[role] == probe_c[role], 'Probe dependency path: ' + role)
    require({p.name for p in run.glob('*.py')} == {p.name for p in Path(probe_c['out']).glob('*.py')},
            'Probe executable file set')
    for name in {p.name for p in run.glob('*.py')}:
        require(sha(run / name) == sha(Path(probe_c['out']) / name), 'Probe executable identity: ' + name)
    items = []
    for i, row in enumerate(rows):
        v = load(run / 'records' / f'{i:06d}.json')['payload']
        q = next(iter(json.loads(row['questions_json']).values()))
        exact_eligibility(c['family'], q, v['eligibility'], eligibility['items'][i])
        items.append(v)
    cells, flags = cell_analysis(rows, items)
    bindings = {'inference': run_binding(c, cp), 'probe': run_binding(probe_c, pc),
                'finisher': finish_binding(c, cp)}
    # Re-read authenticated artifacts after the supplemental pass.
    require(sha(cp) == ch, 'Config changed during supplemental audit')
    for p, h in c['files'].items():
        require(sha(p) == h, 'Frozen file changed during supplemental audit')
    require(sha(run / 'report.json') == original_result['report_sha256'], 'Report changed during supplemental audit')
    verify_receipt_manifest(run, receipts_before)
    return dict(status='VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED' if flags or original_result['review_flags'] else 'VERIFIED_HARDENED_SCOPED',
                config_sha256=ch, report_sha256=sha(run / 'report.json'), original_verifier=original_result,
                supplemental_required_files=count, probes=probes, containers=bindings, cells=cells,
                receipt_manifest=receipts_before,
                review_flags=flags, inherited_review_flags=original_result['review_flags'], min_n=MIN_N,
                utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                scope='Original frozen full-population metric verifier plus strict eligibility/probe/closure and actual container checks; four probe requests independently retokenized, full-test token hashes remain provenance checks; not Astra approval or model-memory-envelope certification.')


def main():
    p = argparse.ArgumentParser(); p.add_argument('--config', type=Path, required=True)
    p.add_argument('--probe-only', action='store_true', help='Audit a completed probe without waiting for full inference')
    p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    digest = args.out.with_suffix('.digest.md')
    require(not args.out.exists() and not digest.exists(), 'Existing supplemental evidence preserved')
    result = check(args.config, args.probe_only)
    publish_text(args.out, json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    population = result.get('original_verifier', {}).get('rows', 'probe:4')
    lines = [f"{result['utc']} {result['status']} rows={population} flags={len(result['review_flags'])} inherited={len(result['inherited_review_flags'])}"]
    lines.extend(json.dumps(flag, ensure_ascii=False)[:500] for flag in result['review_flags'][:12])
    lines.append(f'Full evidence: {args.out}')
    publish_text(digest, '\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
