#!/usr/bin/env python3
"""CPU-only formal provenance capture and gated reuse of the existing eval binder.

Review before deployment. No service start, device operation, evaluation or scoring.
A watch completes at REVIEW_REQUIRED; prepare is a separate root-invoked operation.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import types

QUEUE_PIN = '5228b351bfa8629e8519e3f2d4a64307dee7c7cb35b55c04fd6d83737aa28c03'
BINDING_PIN = '44328b4dfe6eb777ca0735587d8e75c550bc916612859dfda4aa68c655188741'
BASE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
QUEUE = BASE/'formal_v7_attached_20261101_v1/seed2-service/queue.json'
BINDING = BASE/'formal_v7_attached_20261101_v1/DOWNSTREAM_BINDING.json'
BINDER = '/home/xingchao/workspace/nga/tools/r3_posttrain_eval_plan.py'
EXTRA = ['attempts/1/CLAIM.json', 'attempts/1/LAUNCH_RECEIPT.json',
         'attempts/1/LAUNCH_SPEC.json', 'SUPERVISOR_RECEIPT.json', 'SUCCESSOR_PRECONDITION.json']


def require(ok, why):
    if not ok:
        raise ValueError(why)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and str(p) == str(path)
            and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    require(not any(x.lower().split('.')[0] == 'test' for x in p.parts), 'TEST path forbidden')
    return p


def raw(path, pin=None, limit=2**20):
    with safe(path).open('rb') as stream:
        value = stream.read(limit + 1)
    require(len(value) <= limit, 'metadata exceeds bound')
    require(pin is None or hashlib.sha256(value).hexdigest() == pin, 'pin changed: '+str(path))
    return value


def load(path, pin=None):
    return json.loads(raw(path, pin))


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def write(path, doc, exclusive=False):
    path = safe(path)
    data = (json.dumps(doc, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    target = path if exclusive else path.with_suffix('.pending')
    with target.open('xb' if exclusive else 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    if not exclusive:
        target.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def identity():
    queue = load(QUEUE, QUEUE_PIN); binding = load(BINDING, BINDING_PIN)
    require(queue['bindings'][str(BINDING)] == BINDING_PIN, 'binding not attached')
    require(binding['test_read'] is False and binding['scientific_acceptance'] is False,
            'binding scope differs')
    job = next(x for x in binding['jobs'] if x['seed'] == 2)
    qjob = next(x for x in queue['jobs'] if x['id'] == 'formal-k1-seed2')
    require(job['training_plan'] == {'path': qjob['plan'], 'sha256': qjob['plan_raw_sha256']}
            and job['canonical_plan_sha256'] == qjob['plan_sha256'], 'plan binding differs')
    plan = load(job['training_plan']['path'], job['training_plan']['sha256'])
    require(plan['out'] == job['training'] and plan['seed'] == 2
            and plan['command'] == job['command'] and plan['image_sha256'] == job['image_sha256'],
            'training identity differs')
    require(job['binder_call'] == dict(tool=BINDER, function='prepare', training=job['training'],
            closure=str(Path(binding['closure']['path']).parent), out=job['fresh_eval_out']), 'binder call differs')
    require(job['new_adapter'] == str(Path(job['training'])/'adapter'), 'adapter root differs')
    raw(binding['closure']['path'], binding['closure']['sha256'])
    for path, pin in binding['tools'].items():
        raw(path, pin)
    return binding, job, plan


def capture(binding, job, plan):
    """Saved records are not proof of retained-container reality; independent gate follows."""
    root = safe(job['training']); terminal = root/'TRAIN_EXIT.json'
    if not terminal.exists():
        return {'status': 'waiting_training'}
    end = load(terminal)
    require(type(end.get('exit_code')) is int and end.get('attempt') == 1, 'invalid terminal')
    if end['exit_code'] != 0:
        return {'status': 'training_failed', 'exit_code': end['exit_code']}
    names = job['late_bound_hashes'] + EXTRA
    if not all(safe(root/name).is_file() for name in names):
        return {'status': 'waiting_completion_evidence'}
    hashes = {str(root/name): sha(root/name) for name in names}
    docs = {name: load(root/name, hashes[str(root/name)]) for name in names if name.endswith('.json')}
    require(docs['TRAIN_EXIT.json'] == end == docs['attempts/1/EXIT.json'], 'terminal mismatch')
    require(end.get('scientific_acceptance') is False and end.get('started_utc')
            and end.get('finished_utc') and end.get('source') != 'retained-container-exit', 'not genuine driver completion')
    release = docs['attempts/1/RELEASE.json']; done = docs['attempts/1/SUPERVISOR_DONE.json']
    launch = docs['attempts/1/LAUNCH_RECEIPT.json']; claim = docs['attempts/1/CLAIM.json']
    require(release.get('schema') == 'r3-resource-release-v1' and release['run'] == plan['run']
            and release['chip'] == plan['chip'] and release['container'] == plan['container']+'-a1'
            and release['container_id'] == launch['id'] and launch['image'] == plan['image_sha256']
            and launch['plan_sha256'] == job['canonical_plan_sha256']
            and release.get('claim_sha256') == hashes[str(root/'attempts/1/CLAIM.json')]
            and claim['run'] == plan['run'] and claim['chip'] == plan['chip'], 'release/launch/claim mismatch')
    for record in (release, done):
        require(type(record.get('exit_code')) is int and record['exit_code'] == 0
                and record.get('scientific_acceptance') is False, 'completion scope or exit differs')
    manifest = docs['manifest.json']; args = manifest.get('args', {})
    require(manifest.get('summary', {}).get('final_step') == job['required_final_step'] == 3116
            and manifest.get('arm') == args.get('arm') == 'k1' and args.get('seed') == 2
            and manifest.get('model_path') == args.get('model_path') == plan['model'], 'manifest identity differs')
    adapter = safe(job['new_adapter'])
    for path in adapter.iterdir():
        require(not path.is_symlink() and path.is_file(), 'unexpected adapter entry')
        hashes[str(path)] = sha(path)
    hashes[job['training_plan']['path']] = job['training_plan']['sha256']
    require(all(sha(path) == pin for path, pin in hashes.items()), 'provenance changed during capture')
    return dict(schema='r3-formal-posttrain-capture-v1', status='REVIEW_REQUIRED', training=job['training'],
                queue_sha256=QUEUE_PIN, binding_sha256=BINDING_PIN, files=hashes,
                adapter_files={p: h for p, h in hashes.items() if Path(p).parent == adapter},
                test_read=False, scientific_acceptance=False, retained_container_verified=False,
                scope='CPU saved provenance only; independent actual postrun verification required')


def check_capture(doc, binding, job, plan):
    require(doc == capture(binding, job, plan), 'capture changed or incomplete')
    require(doc['status'] == 'REVIEW_REQUIRED', 'capture not complete')


def prepare(state, review_path, review_pin):
    """Root supplies an independently authenticated review pin, never producer self-approval."""
    binding, job, plan = identity()
    captured = load(state/'CAPTURE.json')
    check_capture(captured, binding, job, plan)
    review = load(review_path, review_pin)
    require(review.get('schema') == 'r3-formal-independent-postrun-v1'
            and review.get('verdict') == 'PASS' and review.get('independent') is True
            and review.get('training') == job['training'] and review.get('queue_sha256') == QUEUE_PIN
            and review.get('binding_sha256') == BINDING_PIN
            and review.get('capture_sha256') == sha(state/'CAPTURE.json')
            and review.get('files') == captured['files']
            and review.get('test_read') is False and review.get('scientific_acceptance') is False,
            'independent postrun review differs')
    required = ('genuine_train_exit', 'retained_container_identity', 'claim_release_done_identity',
                'training_inputs_and_code', 'adapter_provenance', 'final_step_3116')
    require(all(review.get('checks', {}).get(k) is True for k in required), 'postrun verification incomplete')
    require(review.get('evidence_files'), 'independent evidence absent')
    require(str(safe(review_path)) not in captured['files'] and safe(review_path).parent != state,
            'review must be separate from producer state and training evidence')
    require(all(sha(p) == h for p, h in review['evidence_files'].items()), 'independent evidence changed')
    out = safe(job['fresh_eval_out'])
    if (state/'PREPARED.json').exists():
        receipt = load(state/'PREPARED.json')
        require(receipt['review_sha256'] == review_pin and receipt['plan'] == str(out/'plan.json')
                and sha(receipt['plan']) == receipt['sha256'], 'prepared receipt changed')
        return receipt
    require(not (state/'PREPARE_INTENT.json').exists(), 'uncertain binder attempt; explicit repair required')
    require(not out.exists(), 'evaluation output already exists; never adopt or clobber')
    code = raw(BINDER, binding['tools'][BINDER])
    module = types.ModuleType('frozen_posttrain_binder'); module.__file__ = BINDER
    exec(compile(code, BINDER, 'exec'), module.__dict__)
    write(state/'PREPARE_INTENT.json', dict(review_sha256=review_pin, binding_sha256=BINDING_PIN,
          output=str(out), attempt=1), exclusive=True)
    result = module.prepare(Path(job['training']), Path(binding['closure']['path']).parent, out)
    require(result['status'] == 'prepared', 'binder did not prepare')
    check_capture(captured, binding, job, plan)
    identity()  # Recheck pinned plan, binding, closure, and tool bytes after consumer.
    load(review_path, review_pin)
    require(all(sha(p) == h for p, h in review['evidence_files'].items()), 'independent evidence changed after consumer')
    spec = load(out/'plan.json')
    require(spec['training'] == job['training'] and spec['adapter'] == job['new_adapter']
            and spec['training_variant']['training_plan_sha256'] == job['training_plan']['sha256']
            and all(spec['files'].get(p) == h for p, h in captured['adapter_files'].items())
            and spec['execution_review'] == spec['chip_assignment'] == 'PENDING'
            and spec['test_read'] is False and spec['scientific_acceptance'] is False, 'generated specification differs')
    require(result['plan'] == str(out/'plan.json') and result['sha256'] == sha(out/'plan.json'), 'binder receipt differs')
    result.update(review_sha256=review_pin, evaluation_authorized=False, scientific_acceptance=False, test_read=False)
    write(state/'PREPARED.json', result, exclusive=True)
    return result


def watch(state, once=False):
    while True:
        binding, job, plan = identity()
        if (state/'CAPTURE.json').exists():
            value = load(state/'CAPTURE.json'); check_capture(value, binding, job, plan)
        else:
            value = capture(binding, job, plan)
            if value['status'] == 'REVIEW_REQUIRED':
                write(state/'CAPTURE.json', value, exclusive=True)
        status = value['status']
        write(state/'heartbeat.json', dict(utc_seconds=time.time(), status=status,
              progress_count=int(status == 'REVIEW_REQUIRED'), scientific_acceptance=False, test_read=False))
        if status in ('REVIEW_REQUIRED', 'training_failed'):
            terminal = dict(status=status, exit_code=int(status == 'training_failed'),
                            scientific_acceptance=False, test_read=False)
            if (state/'EXIT.json').exists():
                require(load(state/'EXIT.json') == terminal, 'capture terminal changed')
            else:
                write(state/'EXIT.json', terminal, exclusive=True)
            return value
        if once:
            return value
        time.sleep(600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('watch', 'prepare'))
    parser.add_argument('--state', required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--review'); parser.add_argument('--review-sha256')
    args = parser.parse_args(); state = safe(args.state)
    require(not state.is_relative_to(BASE/'formal_k1_preparation_20261101_v7')
            and not state.is_relative_to(QUEUE.parent), 'state overlaps active training/service')
    state.mkdir(parents=True, exist_ok=True)
    with (state/'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (state/'FAILURE.json').exists(), 'prior failure requires explicit repair')
        try:
            if args.op == 'prepare':
                require(args.review and args.review_sha256, 'independent root-pinned review required')
                result = prepare(state, args.review, args.review_sha256)
                terminal = dict(exit_code=0, status='prepared', evaluation_authorized=False,
                                scientific_acceptance=False, test_read=False)
                if (state/'PREPARE_EXIT.json').exists():
                    require(load(state/'PREPARE_EXIT.json') == terminal, 'prepare terminal changed')
                else:
                    write(state/'PREPARE_EXIT.json', terminal, exclusive=True)
            else:
                result = watch(state, args.once)
            print(json.dumps({'status': result['status'], 'evaluation_authorized': False}))
        except Exception as exc:
            write(state/'FAILURE.json', {'status': 'needs_repair', 'error_type': type(exc).__name__,
                  'automatic_retry': False, 'scientific_acceptance': False, 'test_read': False}, exclusive=True)
            terminal = state/('PREPARE_EXIT.json' if args.op == 'prepare' else 'EXIT.json')
            if not terminal.exists():
                write(terminal, dict(exit_code=1, status='needs_repair', scientific_acceptance=False,
                      test_read=False), exclusive=True)
            raise


if __name__ == '__main__':
    main()
