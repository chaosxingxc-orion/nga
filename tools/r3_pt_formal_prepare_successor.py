#!/usr/bin/env python3
"""CPU-only PT preparation. Root review/publication precedes activation.

freeze is inert. start/run require an externally pinned deployment receipt.
signal supplies an externally pinned, authenticated *actual* precheck completion;
it is not scientific review. No receipt is generated on behalf of an operator.
An interrupted prepare with no durable PREPARED receipt is never adopted/retried.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import types

REPO = Path('/home/xingchao/workspace/nga')
RUNS = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
MODEL = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'
QUEUE = RUNS / 'instruct_k0_chip3_20261101_v1/prechecks/queue.json'
QUEUE_PIN = 'de38be5667ca3511529e2d2953d6514dab0a93e52e80d86591629d316db7af36'
PENDING_PIN = '5bffb8f8d522463c9b36692f8e759830561d007483277c4378dee12a201e948c'
GUIDANCE_PIN = '6d6ab6d4495d7304dc5977e1ee71d81d2eb8e8d4c20acd907c9ad9f274ff57c1'
WAIT_SECONDS = 600


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and str(p) == str(path) and '..' not in p.parts
            and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    require(p.name not in ('test.jsonl', 'test.variants.jsonl') and not
            ('test' in p.parts and p.suffix in ('.jsonl', '.parquet')), 'TEST forbidden')
    return p


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def valid_pin(pin):
    require(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin), 'non-concrete SHA256')
    return pin


def checked(path, pin):
    valid_pin(pin)
    raw = safe(path).read_bytes()
    require(digest(raw) == pin, 'pin differs: ' + str(path))
    return raw


def doc(path, pin):
    return json.loads(checked(path, pin))


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def fsync_dir(path):
    fd = os.open(str(path), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    """No clobber; interrupted writes remain visible and require inspection."""
    p = safe(path)
    raw = canonical(value)
    with p.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    fsync_dir(p.parent)
    return digest(raw)


def replace(path, value):
    p = safe(path)
    tmp = p.with_name(p.name + '.tmp')
    with tmp.open('wb') as f:
        f.write(canonical(value)); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    fsync_dir(p.parent)


def module(path, pin):
    raw = checked(path, pin)
    m = types.ModuleType('pt_checked_' + Path(path).stem)
    m.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), m.__dict__)
    return m


def inventory(pins):
    for p, h in pins.items():
        safe(p); valid_pin(h)
    for p, h in pins.items():
        require(sha(p) == h, 'inventory changed: ' + p)


@contextlib.contextmanager
def exclusive(path):
    with safe(path).open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def receipt_ref(path):
    return {'path': str(path), 'sha256': sha(path)}


def ref(value):
    return doc(value['path'], value['sha256'])


def freeze(out, handoff, handoff_pin, review, review_pin):
    """Freeze a NEW inert generation; preserve pending request and old outputs."""
    h = doc(handoff, handoff_pin)
    r = doc(review, review_pin)
    require(r['input_handoff'] == {'path': str(handoff), 'sha256': handoff_pin}, 'review handoff differs')
    pending = h['pt']['pending_request']
    require(pending['sha256'] == PENDING_PIN, 'different pending request')
    p = ref(pending)
    guidance = {'path': r['pt']['requirements'], 'sha256': r['pt']['requirements_sha256']}
    require(guidance['sha256'] == GUIDANCE_PIN, 'different PT guidance')
    checked(**{'path': guidance['path'], 'pin': guidance['sha256']})
    require(p['current_precheck_queue'] == {'path': str(QUEUE), 'sha256': QUEUE_PIN}, 'different queue')
    q = doc(QUEUE, QUEUE_PIN)
    inventory(p['current_producer_source_pins'])
    require([(x['seed'], x['chip']) for x in p['targets']] == [(2, 1), (3, 4)], 'targets differ')
    for target in p['targets']:
        k = target['kwargs']
        require(k['model'] == MODEL and k['control_arm'] == 'K1-PT' and k['engineering'] is False
                and k['fresh_prechecks'] == q['output'] and k['fresh_prechecks_sha256'] is None,
                'pending target differs')
        for field in ('training_evidence', 'resume_plan', 'resume_reconstruction', 'reconstruction_target'):
            checked(k[field], k[field + '_sha256'])
    out = safe(out)
    require(out.parent == RUNS, 'generation must be a new run root')
    out.mkdir(exist_ok=False)
    # Frozen repository layout used through prepare.ROOT. Source bytes unmodified.
    frozen = out / 'source'; frozen.mkdir()
    paths = [REPO / 'tools' / n for n in (
        'r3_formal_prepare.py', 'r3_formal_launcher.py', 'r3_resource_adapter.py',
        'r3_formal_driver.py', 'r3_fresh_prechecks.py', 'r3_training_evidence.py',
        'r3_resume_evidence.py', 'r3_resume_reconstruction_evidence.py', 'r3_resume_recompute.py')]
    paths += [REPO / 'experiments/r3_sft/r3_code' / n for n in ('train_r3.py', 'build_kev_sft.py', 'kev_aug.py')]
    paths += [REPO / 'experiments/r0_baseline/prompt.py']
    paths += [REPO / '.local/archive/2026-10-31/experiments' / n for n in
              ('R3-SFT-PREREG.md', 'R3-TRAINING-WAVE-PREREG-2026-10-31.md')]
    pins = dict(p['current_producer_source_pins'])
    copies = {}
    for source in paths:
        target = frozen / source.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = safe(source).read_bytes()
        target.write_bytes(raw)
        copies[str(source)] = {'path': str(target), 'sha256': digest(raw)}
        pins[str(target)] = digest(raw)
    require(pins[str(frozen/'tools/r3_formal_prepare.py')] == p['prepare_source']['sha256'], 'prepare source differs')
    # Legacy precheck copy is an actual input of the unmodified preparation tool.
    legacy = RUNS / 'formal_k1_prechecks_20261031/prechecks'
    for f in legacy.rglob('*'):
        if f.is_file():
            pins[str(f)] = sha(f)
    train = RUNS.parent/'KEV/decision-v7/train.jsonl'
    pins[str(train)] = sha(train)
    for model_file in safe(MODEL).iterdir():
        if model_file.is_file():
            pins[str(model_file)] = sha(model_file)
    for target in p['targets']:
        for field in ('training_evidence', 'resume_plan', 'resume_reconstruction', 'reconstruction_target'):
            pins[target['kwargs'][field]] = target['kwargs'][field + '_sha256']
    for name, value in [('HANDOFF.json', h), ('INDEPENDENT_QO_REVIEW.json', r), ('PT_PENDING_REQUEST.json', p)]:
        # Preserve exact original bytes, including formatting.
        original = handoff if name == 'HANDOFF.json' else review if name == 'INDEPENDENT_QO_REVIEW.json' else Path(pending['path'])
        raw = original.read_bytes(); (out/name).write_bytes(raw); pins[str(out/name)] = digest(raw)
    raw = checked(guidance['path'], guidance['sha256'])
    (out/'PT_AUTOMATIC_PREPARATION_HANDOFF.md').write_bytes(raw)
    pins[str(out/'PT_AUTOMATIC_PREPARATION_HANDOFF.md')] = digest(raw)
    worker = out / Path(__file__).name
    worker.write_bytes(Path(__file__).read_bytes()); worker.chmod(0o755)
    service = QUEUE.parent/'SERVICE.json'; activation = QUEUE.parent/'ACTIVATION.json'
    pins[str(service)] = sha(service); pins[str(activation)] = sha(activation)
    (out/'tmp').mkdir(mode=0o700)
    request = {'schema': 'r3-pt-formal-prepare-successor-v1', 'root': str(out),
        'worker': str(worker), 'worker_sha256': sha(worker), 'source_pins': pins,
        'copies': copies, 'frozen_repository': str(frozen),
        'handoff': receipt_ref(out/'HANDOFF.json'), 'pending': receipt_ref(out/'PT_PENDING_REQUEST.json'),
        'guidance': guidance, 'queue': {'path': str(QUEUE), 'sha256': QUEUE_PIN},
        'precheck_service': receipt_ref(service), 'precheck_activation': receipt_ref(activation),
        'targets': [{**x, 'out': str(out/'plans'/f'seed{x["seed"]}')} for x in p['targets']],
        'runtime_environment': {**q['runtime_environment'], 'TMPDIR': str(out/'tmp'),
            'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'},
        'python': json.loads(service.read_bytes())['command'][0],
        'wait_seconds': WAIT_SECONDS, 'scientific_acceptance': False, 'test_read': False,
        'launch_authorized': False, 'review': 'PENDING_ROOT_SOURCE_REVIEW_AND_PUBLICATION'}
    sync_tree(out)
    pin = save(out/'REQUEST.json', request)
    save(out/'FROZEN.json', {'request_sha256': pin, 'files': {**pins, str(worker): sha(worker)},
                            'service_activated': False})
    return {'request': str(out/'REQUEST.json'), 'sha256': pin}


def request(path, pin):
    r = doc(path, pin)
    require(r['schema'] == 'r3-pt-formal-prepare-successor-v1' and r['scientific_acceptance'] is False
            and r['test_read'] is False and r['launch_authorized'] is False and r['wait_seconds'] == 600,
            'request scope differs')
    require(r['root'] == str(safe(path).parent) and r['worker'] == str(Path(__file__).absolute()), 'worker/root differs')
    checked(r['worker'], r['worker_sha256'])
    require(r['queue'] == {'path': str(QUEUE), 'sha256': QUEUE_PIN}, 'wrong queue')
    p = ref(r['pending'])
    require(r['pending']['sha256'] == PENDING_PIN, 'wrong pending request')
    expected = [{**x, 'out': str(Path(r['root'])/'plans'/f'seed{x["seed"]}')} for x in p['targets']]
    require(r['targets'] == expected, 'pending target arguments changed')
    inventory(r['source_pins'])
    return r


def deployment(r, pin, path, auth_pin):
    a = doc(path, auth_pin)
    require(a.get('schema') == 'r3-pt-preparation-deployment-v1'
            and a.get('request_sha256') == pin and a.get('worker_sha256') == r['worker_sha256']
            and a.get('root_source_review_completed') is True and a.get('publication_completed') is True
            and a.get('precheck_process_authenticated') is True
            and a.get('precheck_service') == r['precheck_service']
            and a.get('scientific_acceptance') is False and a.get('training_authorized') is False,
            'external root deployment receipt required')
    # Exact retained root artifacts, not bare boolean admission.
    for field in ('source_review', 'publication'):
        checked(a[field]['path'], a[field]['sha256'])
    return a


def linkage(q, queue_pin, end_raw, validation_raw, bundle_raw, consumed):
    """Parse the SAME buffers used for all terminal/output hash comparisons."""
    end, v, b = map(json.loads, (end_raw, validation_raw, bundle_raw))
    require(type(end.get('exit_code')) is int and end['exit_code'] == 0
            and end.get('queue_sha256') == queue_pin and end.get('scientific_acceptance') is False
            and end.get('test_read') is False, 'precheck terminal failed/scope/queue differs')
    require(end.get('validation_sha256') == digest(validation_raw)
            and end.get('output_sha256') == digest(bundle_raw), 'terminal buffer linkage differs')
    require(v.get('output') == q['output'] and v.get('output_sha256') == digest(bundle_raw)
            and v.get('full_validate_bundle_completed') is True and v.get('checks') == 6
            and v.get('schema') == 'r3-fresh-k0-prechecks-v2'
            and v.get('scientific_acceptance') is False and v.get('test_read') is False,
            'validation incomplete or output differs')
    require(consumed is not None and v.get('consumed') == consumed, 'prerequisite consumed mapping differs')
    require(b.get('schema') == v['schema'] and b.get('status') == 'PASS' and b.get('model') == MODEL
            and b.get('scientific_acceptance') is False and b.get('test_read') is False
            and len(b.get('checks', {})) == 6 and len(b.get('inputs', {})) == v.get('inputs')
            and b.get('k0_report') == consumed['report']
            and b['inputs'].get(consumed['report']) == consumed['report_sha256'], 'bundle model/report/scope differs')
    return b


def dependency(r, authentication=None):
    q = ref(r['queue'])
    waiter = module(q['worker'], q['worker_sha256'])
    waiter.request(Path(r['queue']['path']), r['queue']['sha256'])
    waiter.dependencies(q)
    consumed = waiter.prerequisite(q)  # original current implementation, exact mapping
    end_path = Path(r['queue']['path']).parent/'EXIT.json'
    if not end_path.exists():
        return None
    end_raw = end_path.read_bytes()
    end = json.loads(end_raw)
    require(type(end.get('exit_code')) is int and end['exit_code'] == 0, 'precheck failed')
    require(consumed is not None, 'precheck terminal without report terminal')
    v_path = end_path.with_name('VALIDATION.json')
    v_raw = v_path.read_bytes()
    b_raw = safe(q['output']).read_bytes()
    bundle = linkage(q, r['queue']['sha256'], end_raw, v_raw, b_raw, consumed)
    pins = {str(end_path): digest(end_raw), str(v_path): digest(v_raw), q['output']: digest(b_raw),
            consumed['terminal']: consumed['terminal_sha256'], consumed['report']: consumed['report_sha256']}
    if authentication is None:
        return {'state': 'WAIT_EXTERNAL_COMPLETION_AUTHENTICATION', 'observed': pins}
    a = ref(authentication)
    require(a.get('schema') == 'r3-pt-precheck-authentication-v1'
            and a.get('external_process_and_terminal_authenticated') is True
            and a.get('queue') == r['queue'] and a.get('precheck_service') == r['precheck_service']
            and a.get('worker_sha256') == q['worker_sha256'] and a.get('artifacts') == pins
            and a.get('scientific_acceptance') is False, 'external completion authentication differs')
    service = ref(r['precheck_service'])
    activation = ref(r['precheck_activation'])
    require(activation.get('service') == service and activation.get('process_identity_verified') is True
            and activation.get('queue_sha256') == r['queue']['sha256'], 'precheck process receipt linkage differs')
    expected_command = [r['python'], '-B', '-P', q['worker'], 'watch', '--queue',
                        r['queue']['path'], '--sha256', r['queue']['sha256']]
    require(service.get('command') == expected_command and type(service.get('pid')) is int
            and isinstance(service.get('start_ticks'), str), 'precheck process command identity differs')
    consumer = module(q['consumer'], q['source_pins'][q['consumer']])
    actual = consumer.validate_bundle(q['output'], digest(b_raw), MODEL)
    require(actual == bundle, 'full consumer returned different bytes')
    require(waiter.prerequisite(q) == consumed, 'report changed during full validation')
    inventory({**pins, **bundle['inputs'], **bundle['checks'], **r['source_pins']})
    return {'state': 'AUTHENTICATED_FULL_PRECHECK_PASS', 'artifacts': pins,
            'consumed': consumed, 'authentication': authentication, 'bundle': bundle}


def tree(path):
    return {str(p): sha(p) for p in safe(path).rglob('*') if p.is_file()}


def sync_tree(path):
    # Completion receipts must never outrun the plan bytes on durable storage.
    root = safe(path)
    for p in root.rglob('*'):
        safe(p)
        if p.is_file():
            with p.open('rb') as f:
                os.fsync(f.fileno())
    for p in sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        fsync_dir(p)
    fsync_dir(root)
    fsync_dir(root.parent)


def seed_state(root, seed, output):
    """Only explicit durable completion permits reuse; presence never implies success."""
    intent = root/f'SEED{seed}_INTENT.json'
    prepared = root/f'SEED{seed}_PREPARED.json'
    if prepared.exists():
        require(intent.exists(), 'prepared without intent')
        data = json.loads(prepared.read_bytes())
        require(data['intent_sha256'] == sha(intent) and data['out'] == str(output), 'prepared intent differs')
        require(tree(output) == data['output_inventory'], 'prepared output changed or partial')
        return data
    require(not intent.exists() and not output.exists(), 'uncertain interrupted prepare; preserve and use a new generation')
    return None


def verify_plan(r, target, prepared, dep):
    out = Path(target['out']); plan_path = out/'plan.json'
    plan = doc(plan_path, prepared['plan_sha256'])
    require(plan['out'] == str(out) and plan['seed'] == target['seed'] and plan['chip'] == target['chip']
            and plan['model'] == MODEL and plan['control_arm'] == 'K1-PT'
            and plan['review_sha256'] == 'PENDING' and not Path(plan['review_path']).exists(), 'PT target/review differs')
    for key in ('training_evidence', 'resume_plan', 'resume_reconstruction', 'reconstruction_target'):
        require(plan[key] == target['kwargs'][key] and plan[key+'_sha256'] == target['kwargs'][key+'_sha256'], 'own PT evidence differs')
    require(plan['fresh_k0_prechecks'] == r['targets'][0]['kwargs']['fresh_prechecks']
            and plan['fresh_k0_prechecks_sha256'] == dep['artifacts'][plan['fresh_k0_prechecks']], 'wrong genuine baseline')
    inventory(plan['files'])
    events = []
    def profile(frame, event, result):
        if event != 'return' or not isinstance(result, dict):
            return
        name, file = frame.f_code.co_name, frame.f_code.co_filename
        if name == 'validate' and file.endswith(('r3_resume_reconstruction_evidence.py', 'r3_training_evidence.py')):
            events.append({'file': file, 'function': name, 'inputs': len(result), 'inventory': result})
        if name == 'validate_bundle' and file.endswith('r3_fresh_prechecks.py'):
            events.append({'file': file, 'function': name, 'inputs': len(result['inputs']), 'checks': len(result['checks'])})
    launcher = module(plan['launcher'], plan['files'][plan['launcher']])
    require(launcher.identity(plan) == prepared['plan_sha256'], 'canonical identity differs')
    before = time.monotonic()
    sys.setprofile(profile)
    try:
        actual = launcher.verify(str(plan_path), prepared['plan_sha256'], reviewed=False)
    finally:
        sys.setprofile(None)
    require(actual == plan, 'launcher returned different plan')
    require(any(x['file'].endswith('r3_resume_reconstruction_evidence.py') and x['inputs'] == 64 for x in events), 'own 64-input PT recovery not consumed')
    require(any(x['function'] == 'validate_bundle' and x['checks'] == 6 for x in events), 'genuine six checks not consumed')
    inventory({**plan['files'], **dep['artifacts'], **r['source_pins']})
    require(tree(out) == prepared['output_inventory'], 'plan generation changed during validation')
    return {'plan': str(plan_path), 'plan_sha256': prepared['plan_sha256'], 'reviewed': False,
            'actual_full_launcher_completed': True, 'seconds': time.monotonic()-before,
            'inventory': plan['files'], 'consumers': events, 'scientific_acceptance': False,
            'test_read': False, 'training_started': False}


def prepare_plans(r, request_pin, dep, progress):
    root = Path(r['root'])
    require(dep['state'] == 'AUTHENTICATED_FULL_PRECHECK_PASS', 'genuine full prechecks required')
    resolved = {'request_sha256': request_pin, 'dependency': dep,
                'targets': [{**x, 'kwargs': {**x['kwargs'], 'fresh_prechecks_sha256':
                    dep['artifacts'][x['kwargs']['fresh_prechecks']]}} for x in r['targets']]}
    resolved_path = root/'RESOLVED_REQUEST.json'
    if resolved_path.exists():
        require(resolved_path.read_bytes() == canonical(resolved), 'resolved generation changed')
    else:
        save(resolved_path, resolved)
    frozen = Path(r['frozen_repository'])
    prep_path = frozen/'tools/r3_formal_prepare.py'
    prepare = module(prep_path, r['source_pins'][str(prep_path)])
    prepare.ROOT = frozen  # explicit frozen repository layout; unmodified source
    results = []
    for target in resolved['targets']:
        seed = target['seed']; out = Path(target['out'])
        progress.update(state=f'prepare_seed{seed}', progress_count=len(results))
        prepared = seed_state(root, seed, out)
        intent = root/f'SEED{seed}_INTENT.json'
        if prepared is None:
            inventory(r['source_pins']); inventory(dep['artifacts'])
            intent_pin = save(intent, {'request_sha256': request_pin, 'resolved_sha256': sha(resolved_path),
                                      'target': target, 'utc_seconds': time.time()})
            kwargs = dict(target['kwargs']); kwargs['model'] = Path(kwargs['model'])
            result = prepare.prepare(out, seed, target['chip'], **kwargs)
            sync_tree(out)
            prepared = {'intent_sha256': intent_pin, 'out': str(out), 'plan_sha256': result['sha256'],
                        'output_inventory': tree(out)}
            save(root/f'SEED{seed}_PREPARED.json', prepared)
        else:
            intent_doc = json.loads(intent.read_bytes())
            require(intent_doc['request_sha256'] == request_pin and intent_doc['target'] == target
                    and intent_doc['resolved_sha256'] == sha(resolved_path), 'old intent belongs to another request')
        progress['state'] = f'full_launcher_reviewed_false_seed{seed}'
        validated = verify_plan(r, target, prepared, dep)
        validation_path = root/f'SEED{seed}_VALIDATION.json'
        if validation_path.exists():
            old = json.loads(validation_path.read_bytes())
            require(old['plan_sha256'] == validated['plan_sha256'] and old['inventory'] == validated['inventory']
                    and old['actual_full_launcher_completed'] is True and old['reviewed'] is False,
                    'completed validation differs')
        else:
            save(validation_path, validated)
        results.append(receipt_ref(validation_path))
    return results


def cpu_guard(root):
    """No subprocess, sockets, device access, TEST data or writes outside generation."""
    sys.dont_write_bytecode = True
    sys.modules['torch_npu'] = None
    os.devnull = str(root/'tmp/runtime-null')
    Path(os.devnull).touch(exist_ok=True)
    def audit(event, args):
        if event in ('subprocess.Popen', 'os.system', 'socket.connect', 'socket.bind', 'socket.getaddrinfo'):
            raise PermissionError('CPU preparation forbids '+event)
        if event == 'open' and isinstance(args[0], (str, bytes)):
            p = Path(os.fsdecode(args[0])).absolute()
            mode, flags = args[1:]
            writing = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if writing:
                require(p.is_relative_to(root), 'write outside preparation generation')
                safe(p)
            require(p.name not in ('test.jsonl', 'test.variants.jsonl') and not
                    ('test' in p.parts and p.suffix in ('.jsonl', '.parquet')), 'TEST forbidden')
            require(not str(p).startswith(('/dev/davinci', '/dev/devmm', '/dev/hisi')), 'NPU forbidden')
            require(not (p.suffix == '.log' and not writing), 'raw log reading forbidden')
    sys.addaudithook(audit)


def run(path, pin, deployment_path, deployment_pin, resume=False):
    r = request(path, pin)
    deployment(r, pin, deployment_path, deployment_pin)
    root = Path(r['root'])
    with exclusive(root/'worker.lock'):
        attempts = root/'attempts'; attempts.mkdir(exist_ok=True)
        old = list(attempts.iterdir())
        require(resume or not old, 'explicit --resume required')
        # Reject ambiguous seed writes before allocating any new attempt.
        for target in r['targets']:
            seed_state(root, target['seed'], Path(target['out']))
        attempt = attempts/str(len(old)+1); attempt.mkdir()
        cmd = [r['python'], '-B', '-P', r['worker'], 'start', '--request', str(path), '--sha256', pin,
               '--deployment', str(deployment_path), '--deployment-sha256', deployment_pin, '--resume']
        save(attempt/'RELAUNCH.json', {'command': cmd, 'environment': r['runtime_environment'],
             'policy': 'Explicit resume; ambiguous prepare output is never retried or adopted.'})
        save(attempt/'INTENT.json', {'request_sha256': pin, 'deployment': {'path': str(deployment_path), 'sha256': deployment_pin},
                                  'pid': os.getpid(), 'utc_seconds': time.time()})
        wake = threading.Event(); stop = threading.Event()
        signal.signal(signal.SIGUSR1, lambda *_: wake.set())
        signal.signal(signal.SIGTERM, lambda *_: (stop.set(), wake.set()))
        progress = {'state': 'waiting_actual_precheck_terminal', 'progress_count': 0}
        def heartbeat():
            while not stop.is_set():
                replace(attempt/'heartbeat.json', {**progress, 'utc_seconds': time.time(), 'pid': os.getpid(),
                    'wait_seconds': 600, 'scientific_acceptance': False, 'test_read': False})
                stop.wait(30)
        os.environ.update(r['runtime_environment'])
        cpu_guard(root)
        thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
        try:
            while True:
                require(not stop.is_set(), 'explicit stop; preserved for resume')
                inventory(r['source_pins'])
                authentication = None
                if (root/'SIGNAL.json').exists():
                    envelope = json.loads((root/'SIGNAL.json').read_bytes())
                    require(envelope['request_sha256'] == pin, 'signal request differs')
                    authentication = envelope['authentication']
                dep = dependency(r, authentication)
                if dep and dep['state'] == 'AUTHENTICATED_FULL_PRECHECK_PASS':
                    break
                progress['state'] = dep['state'] if dep else 'WAIT_GENUINE_INSTRUCT_PRECHECKS'
                wake.wait(WAIT_SECONDS); wake.clear()
            results = prepare_plans(r, pin, dep, progress)
            inventory(dep['artifacts'])
            result_pin = save(attempt/'RESULT.json', {'status': 'PREPARED_FULL_REVIEWED_FALSE_PENDING_INDEPENDENT_REVIEW',
                 'request_sha256': pin, 'plans': results, 'dependency': dep, 'scientific_acceptance': False,
                 'test_read': False, 'training_started': False, 'no_seed3_restart_execution_claim': True})
            progress.update(state='complete_pending_independent_review', progress_count=2)
            save(attempt/'EXIT.json', {'exit_code': 0, 'result_sha256': result_pin, 'request_sha256': pin})
            return 0
        except BaseException as error:
            progress['state'] = 'failed_closed'
            fail_pin = save(attempt/'FAILURE.json', {'type': type(error).__name__, 'message': str(error)[:1500]})
            save(attempt/'EXIT.json', {'exit_code': 1, 'failure_sha256': fail_pin, 'request_sha256': pin})
            return 1
        finally:
            stop.set(); thread.join()
            replace(attempt/'heartbeat.json', {**progress, 'utc_seconds': time.time(), 'pid': os.getpid()})


def live(service):
    try:
        stat = (Path('/proc')/str(service['pid'])/'stat').read_text().rsplit(')', 1)[1].split()
        cmd = (Path('/proc')/str(service['pid'])/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
        return stat[19] == service['start_ticks'] and cmd == [os.fsencode(x) for x in service['command']]
    except FileNotFoundError:
        return False


def start(path, pin, deployment_path, deployment_pin, resume=False):
    r = request(path, pin); deployment(r, pin, deployment_path, deployment_pin)
    root = Path(r['root'])
    with exclusive(root/'start.lock'):
        services = sorted(root.glob('SERVICE_*.json'))
        for s in services:
            require(not live(json.loads(s.read_bytes())), 'worker already live')
        require(resume or not services, 'explicit --resume required')
        # A launch-intent without a process receipt is uncertain, never auto-adopted.
        require(len(list(root.glob('START_*.json'))) == len(services), 'uncertain start; root inspection required')
        with exclusive(root/'worker.lock'):
            for target in r['targets']:
                seed_state(root, target['seed'], Path(target['out']))
        n = len(services)+1
        cmd = [r['python'], '-B', '-P', r['worker'], 'run', '--request', str(path), '--sha256', pin,
               '--deployment', str(deployment_path), '--deployment-sha256', deployment_pin]
        if resume:
            cmd.append('--resume')
        save(root/f'START_{n}.json', {'command': cmd, 'environment': r['runtime_environment'], 'utc_seconds': time.time()})
        with (root/f'service_{n}.log').open('xb') as log:
            process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env={**os.environ, **r['runtime_environment']}, cwd=root)
        stat = (Path('/proc')/str(process.pid)/'stat').read_text().rsplit(')', 1)[1].split()
        service = {'pid': process.pid, 'command': cmd, 'start_ticks': stat[19], 'request_sha256': pin}
        save(root/f'SERVICE_{n}.json', service)
        return service


def send_signal(path, pin, authentication_path, authentication_pin):
    r = request(path, pin)
    a = doc(authentication_path, authentication_pin)
    require(a.get('external_process_and_terminal_authenticated') is True and a.get('queue') == r['queue']
            and a.get('precheck_service') == r['precheck_service'], 'external authentication required')
    root = Path(r['root'])
    envelope = {'request_sha256': pin, 'authentication': {'path': str(authentication_path), 'sha256': authentication_pin}}
    with exclusive(root/'signal.lock'):
        if (root/'SIGNAL.json').exists():
            require((root/'SIGNAL.json').read_bytes() == canonical(envelope), 'different authentication signal; no overwrite')
        else:
            save(root/'SIGNAL.json', envelope)
        for f in root.glob('SERVICE_*.json'):
            service = json.loads(f.read_bytes())
            # Persistent envelope is sufficient before the run installs its handler.
            ready = any(json.loads(h.read_bytes()).get('pid') == service['pid']
                        for h in root.glob('attempts/*/heartbeat.json'))
            if ready and live(service):
                os.kill(service['pid'], signal.SIGUSR1)
    return {'signal_retained': True, 'request_sha256': pin}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('freeze', 'inspect', 'start', 'run', 'signal'))
    for name in ('out', 'handoff', 'review', 'request', 'deployment', 'authentication'):
        parser.add_argument('--'+name, type=Path)
    for name in ('sha256', 'handoff-sha256', 'review-sha256', 'deployment-sha256', 'authentication-sha256'):
        parser.add_argument('--'+name)
    parser.add_argument('--resume', action='store_true')
    a = parser.parse_args()
    if a.op == 'freeze':
        result = freeze(a.out, a.handoff, a.handoff_sha256, a.review, a.review_sha256)
    elif a.op == 'inspect':
        r = request(a.request, a.sha256)
        dep = dependency(r)
        result = {'status': dep['state'] if dep else 'WAIT_GENUINE_INSTRUCT_PRECHECKS',
                  'service_activated': False, 'plans_created': False, 'request_sha256': a.sha256}
    elif a.op == 'signal':
        result = send_signal(a.request, a.sha256, a.authentication, a.authentication_sha256)
    elif a.op == 'start':
        result = start(a.request, a.sha256, a.deployment, a.deployment_sha256, a.resume)
    else:
        return run(a.request, a.sha256, a.deployment, a.deployment_sha256, a.resume)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
