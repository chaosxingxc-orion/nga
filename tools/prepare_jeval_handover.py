#!/usr/bin/env python3
"""Prepare a reviewed queue handover; never stop/start a model or mutate allocation."""
import argparse
import fcntl
import importlib.util
import json
from pathlib import Path
import threading


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def validate(q, intent, require_stopped=True):
    q.require(q.docker('GET', '/info')['Name'] == 'k8s-node1', '175 Docker only')
    q.frozen(intent['files'])
    q.require(q.sha(intent['old_plan']) == intent['old_plan_sha256'], 'Old plan identity changed')
    prior = q.load(intent['old_plan'])
    old = q.inspect(prior['container'])
    q.binding(old, q.load(prior['preparation_files']['container_spec']), q.load(Path(prior['out']) / 'LAUNCH_RECEIPT.json'))
    q.require(old['Id'] == intent['old_controller_id'] and not q.chip_access(old), 'Old controller identity or CPU scope changed')
    if require_stopped:
        q.require(old['State']['Status'] == 'exited', 'Old controller must already be stopped by the parent')
    q.require(q.sha(intent['config']) == intent['config_sha256'], 'Formal config changed')
    c = q.load(intent['config'])
    for role in ['inference', 'finish']:
        out = Path(c['out'] + ('' if role == 'inference' else '_finish'))
        name = c['container'] + ('' if role == 'inference' else '-finish')
        actual = q.inspect(name)
        receipt = q.load(out / 'LAUNCH_RECEIPT.json')
        q.require(actual is not None and actual['Id'] == intent['adopted_ids'][role] == receipt['container_id'], 'Adopted role identity changed: ' + role)
        labels = actual['Config'].get('Labels') or {}
        q.require(labels.get('nga.jeval.queue') == q.role_label_hash(intent['old_plan'], c['key'], role) and labels.get('nga.jeval.role') == role
                  and labels.get('nga.jeval.key') == c['key'], 'Adopted role labels changed: ' + role)
    return old


def execute(path):
    root = path.parent
    intent = json.loads(path.read_text())
    q = module(Path(intent['source']) / 'jeval_reference_queue.py', 'handover_queue')
    q.require(q.load(root / 'PARENT_REVIEW.json')['approved_intent_sha256'] == q.sha(path), 'Handover intent not reviewed')
    with (root / 'execution.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        q.require(not (root / 'COMPLETE.json').exists(), 'Preparation terminal already exists')
        stop = threading.Event()
        phase = ['validate_stopped_generation']
        def heartbeat():
            while not stop.is_set():
                q.atomic(root / 'HEARTBEAT.json', dict(utc=q.utc(), progress=phase[0], intent_sha256=q.sha(path)))
                (root / 'digest.md').write_text(q.utc() + ' handover preparation: ' + phase[0] + '\n')
                stop.wait(5)
        worker = threading.Thread(target=heartbeat, daemon=True)
        worker.start()
        result = dict(rc=1, intent_sha256=q.sha(path), launched_queue=False, stopped_containers=False, allocation_mutated=False)
        try:
            before = validate(q, intent)
            phase[0] = 'prepare_new_frozen_queue'
            prep = module(Path(intent['source']) / 'prepare_jeval_reference_queue.py', 'handover_preparer')
            prep.prepare(Path(intent['source']), Path(intent['preregistration']), Path(intent['config']),
                         Path(intent['new_out']), intent['new_container'], Path(intent['old_plan']))
            after = validate(q, intent)
            q.require(before['State']['FinishedAt'] == after['State']['FinishedAt'], 'Stopped controller generation changed during preparation')
            plan = Path(intent['new_out']) / 'plan.json'
            result.update(rc=0, status='PREPARED_NOT_LAUNCHED', plan=str(plan), plan_sha256=q.sha(plan),
                          old_finished_at=after['State']['FinishedAt'], adopted_ids=intent['adopted_ids'])
            phase[0] = 'prepared_not_launched'
        except Exception as exc:
            result.update(status='FAILED_RETAINED', error=type(exc).__name__ + ': ' + str(exc))
            phase[0] = 'failed_retained'
        finally:
            stop.set(); worker.join(timeout=6)
            result['utc'] = q.utc()
            q.atomic(root / 'COMPLETE.json', result)
            (root / 'digest.md').write_text(q.utc() + ' ' + result['status'] + '; evidence ' + str(root / 'COMPLETE.json') + '\n')
        raise SystemExit(result['rc'])


def launch(path):
    root = path.parent
    intent = json.loads(path.read_text())
    q = module(Path(intent['source']) / 'jeval_reference_queue.py', 'handover_queue')
    q.require(q.load(root / 'PARENT_REVIEW.json')['approved_intent_sha256'] == q.sha(path), 'Handover intent not reviewed')
    with (root / 'launch.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate(q, intent)
        q.require(not (root / 'COMPLETE.json').exists() and not (root / 'EXIT').exists(), 'Preparation terminal retained')
        spec = q.load(root / 'CONTAINER_SPEC.json')
        q.require(not q.chip_access(spec), 'Preparation must be CPU-only')
        receipt_path = root / 'LAUNCH_RECEIPT.json'
        intent_path = root / 'LAUNCH_INTENT.json'
        expected = dict(handover_intent_sha256=q.sha(path), spec_sha256=q.sha(root / 'CONTAINER_SPEC.json'))
        actual = q.inspect(intent['preparation_container'])
        if actual is None:
            q.require(not receipt_path.exists(), 'Missing retained preparation container')
            if intent_path.exists():
                q.require(q.load(intent_path) == expected, 'Preparation launch intent changed')
            else:
                q.atomic(intent_path, expected)
            q.docker('POST', '/containers/create?name=' + intent['preparation_container'], spec)
            actual = q.inspect(intent['preparation_container'])
        q.binding(actual, spec)
        if receipt_path.exists():
            q.binding(actual, spec, q.load(receipt_path))
        else:
            q.require(actual['State']['Status'] == 'created' and intent_path.exists() and q.load(intent_path) == expected, 'Unknown preparation container')
            q.atomic(receipt_path, dict(container_id=actual['Id'], image=q.IMAGE, command=spec['Cmd'], entrypoint=spec['Entrypoint']))
        q.require(actual['State']['Status'] in ('created', 'running'), 'Preparation restart requires new reviewed generation')
        if actual['State']['Status'] == 'created':
            q.docker('POST', '/containers/' + actual['Id'] + '/start')
        print('Preparation retained container: ' + actual['Id'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch', type=Path)
    parser.add_argument('--execute', type=Path)
    args = parser.parse_args()
    if args.launch:
        launch(args.launch)
    else:
        execute(args.execute)
