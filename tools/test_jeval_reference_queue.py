#!/usr/bin/env python3
"""Failure boundaries for E34; optional real Docker seam fixture."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('queue_impl', Path(__file__).with_name('jeval_reference_queue.py'))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def obj(spec, name='worker', status='created'):
    return {'Id': name + '-id', 'Image': spec['Image'], 'Config': {k: copy.deepcopy(spec.get(k)) for k in ['Cmd', 'Entrypoint', 'Env', 'Labels']},
            'HostConfig': copy.deepcopy(spec['HostConfig']), 'State': {'Status': status, 'ExitCode': 0}}


class FixtureQueue(q.Queue):
    def spec(self, c, role):
        out, _ = self.context(c, role)
        return {'Image': q.IMAGE, 'Cmd': [str(out / 'run.sh')], 'Entrypoint': ['bash'],
                'Env': q.image_environment() if getattr(self, 'real_docker', False) else ['TORCH_DEVICE_BACKEND_AUTOLOAD=0'],
                'Labels': {'nga.jeval.queue': self.hash, 'nga.jeval.key': c['key'], 'nga.jeval.role': role},
                'HostConfig': {'Binds': ['/mnt/cephfs:/mnt/cephfs'], 'Devices': [], 'NetworkMode': 'none', 'ShmSize': 67108864}}

    def resource(self, c, own_id=None, claim=False):
        # CPU fixture never reads or changes the real chip allocation.
        pass


def fixture(root):
    z = FixtureQueue.__new__(FixtureQueue)
    z.hash = 'fixture-plan-bound'
    z.out = root
    z.plan = {'allocation': str(root / 'fixture-allocation.json')}
    z.state_path = root / 'STATE.json'
    z.state = q.load(z.state_path) if z.state_path.exists() else {'intents': {}}
    run = root / 'worker'
    c = {'out': str(run), 'key': 'nimble', 'container': 'nga-' + root.parent.name + '-worker'}
    entry = {'config_sha256': 'fixture-config-bound'}
    return z, c, entry


def setup_fixture(root):
    root.mkdir(parents=True)
    q.atomic(root / 'fixture-allocation.json', {'allocation': [], 'free': [{'chip': 1}]})
    for name in ['worker', 'worker_finish']:
        out = root / name
        out.mkdir()
        (out / 'run.sh').write_text('#!/bin/bash\nset -e\npython3 -P -c "import time; time.sleep(2)"\nprintf "rc=0 utc=%s\\n" "$(date -u +%FT%TZ)" > ' + str(out / 'FIXTURE_EXIT') + '\n')


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'fixture'
        setup_fixture(self.root)
        self.z, self.c, self.entry = fixture(self.root)
        self.containers = {}
        self.created = 0
        self.started = 0

    def tearDown(self):
        self.tmp.cleanup()

    def docker(self, method, path, value=None):
        if method == 'GET' and path == '/containers/json':
            return []
        if method == 'GET':
            name = path.split('/')[2]
            return self.containers.get(name)
        if '/create?' in path:
            name = path.split('name=')[1]
            self.created += 1
            self.containers[name] = obj(value, name)
            self.containers[name + '-id'] = self.containers[name]
            return {'Id': name + '-id'}
        self.started += 1
        self.containers[path.split('/')[2]]['State']['Status'] = 'running'

    def run_role(self, role='inference'):
        with patch.object(q, 'docker', self.docker):
            return self.z.reconcile(self.c, self.entry, role)

    def test_create_gap_recovers_only_persisted_intent(self):
        real = self.docker
        def crash(method, path, value=None):
            result = real(method, path, value)
            if '/create?' in path:
                raise KeyboardInterrupt()
            return result
        with patch.object(q, 'docker', crash), self.assertRaises(KeyboardInterrupt):
            self.z.reconcile(self.c, self.entry, 'inference')
        self.z, self.c, self.entry = fixture(self.root)
        self.assertEqual(self.run_role(), 'running')
        self.assertEqual((self.created, self.started), (1, 1))

    def test_receipt_gap_recovers_no_duplicate(self):
        real = q.atomic
        def crash(path, value):
            real(path, value)
            if Path(path).name == 'LAUNCH_RECEIPT.json':
                raise KeyboardInterrupt()
        with patch.object(q, 'atomic', crash), patch.object(q, 'docker', self.docker), self.assertRaises(KeyboardInterrupt):
            self.z.reconcile(self.c, self.entry, 'inference')
        self.z, self.c, self.entry = fixture(self.root)
        self.assertEqual(self.run_role(), 'running')
        self.assertEqual((self.created, self.started), (1, 1))

    def test_finisher_gap_recovers(self):
        real = self.docker
        def crash(method, path, value=None):
            result = real(method, path, value)
            if '/create?' in path:
                raise KeyboardInterrupt()
            return result
        with patch.object(q, 'docker', crash), self.assertRaises(KeyboardInterrupt):
            self.z.reconcile(self.c, self.entry, 'finish')
        self.assertEqual(self.run_role('finish'), 'running')
        self.assertEqual(self.created, 1)

    def test_foreign_created_rejected(self):
        s = self.z.spec(self.c, 'inference')
        self.containers[self.c['container']] = obj(s)
        with self.assertRaisesRegex(ValueError, 'Unknown unreceipted'):
            self.run_role()
        self.assertEqual(self.started, 0)

    def test_foreign_labels_rejected(self):
        s = self.z.spec(self.c, 'inference')
        s['Labels']['nga.jeval.queue'] = 'other'
        self.containers[self.c['container']] = obj(s)
        with self.assertRaisesRegex(ValueError, 'intent label'):
            self.run_role()

    def test_receipt_config_change_rejected(self):
        self.run_role()
        self.entry['config_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'Receipt config'):
            self.run_role()

    def test_container_identity_change_rejected(self):
        self.run_role()
        self.containers[self.c['container']]['Id'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'Receipt container'):
            self.run_role()

    def test_terminal_on_created_rejected(self):
        s = self.z.spec(self.c, 'inference')
        info = obj(s, self.c['container'])
        self.containers[self.c['container']] = info
        out = Path(self.c['out'])
        q.atomic(out / 'LAUNCH_RECEIPT.json', dict(container_id=info['Id'], image=q.IMAGE, command=s['Cmd'], entrypoint=s['Entrypoint'], config_sha256=self.entry['config_sha256'], wrapper_sha256=q.sha(out / 'run.sh')))
        q.atomic(out / 'COMPLETE.json', {'rc': 0})
        with self.assertRaisesRegex(ValueError, 'terminal evidence'):
            self.run_role()

    def test_failed_exit_is_not_retried(self):
        self.run_role()
        self.containers[self.c['container']]['State'] = {'Status': 'exited', 'ExitCode': 137}
        with self.assertRaisesRegex(ValueError, 'manual reviewed resume'):
            self.run_role()
        self.assertEqual(self.started, 1)

    def test_all_spec_fields_bound(self):
        s = self.z.spec(self.c, 'inference')
        for category, key, value in [('Config', 'Env', ['TORCH_DEVICE_BACKEND_AUTOLOAD=1']), ('HostConfig', 'NetworkMode', 'host'), ('HostConfig', 'ShmSize', 1), ('HostConfig', 'Binds', []), ('Config', 'Cmd', ['bad'])]:
            d = obj(s)
            d[category][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                q.binding(d, s)

    def test_no_terminal_cannot_be_complete(self):
        for role in ['inference', 'finish']:
            self.run_role(role)
            _, name = self.z.context(self.c, role)
            self.containers[name]['State']['Status'] = 'exited'
        with patch.object(q, 'docker', self.docker), self.assertRaises(FileNotFoundError):
            self.z.completion(self.c, self.entry, include_hardened=False)


    def completed_artifacts(self, flags=None):
        flags = flags or []
        for role in ['inference', 'finish']:
            self.run_role(role)
            out, name = self.z.context(self.c, role)
            self.containers[name]['State']['Status'] = 'exited'
        run = Path(self.c['out'])
        end = Path(str(run) + '_finish')
        q.atomic(run / 'report.json', {'config_sha256': self.entry['config_sha256']})
        q.atomic(run / 'PROBE.json', {})
        q.atomic(run / 'COMPLETE.json', {'rc': 0, 'config_sha256': self.entry['config_sha256'], 'stage': 'completed', 'progress': 11257, 'total': 11257,
            'outputs': {n: q.sha(run / n) for n in ['report.json', 'PROBE.json']}})
        (run / 'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
        q.atomic(end / 'INDEPENDENT_AUDIT.json', {'status': 'VERIFIED_SCOPED', 'config_sha256': self.entry['config_sha256'], 'report_sha256': q.sha(run / 'report.json'), 'rows': 11257, 'review_flags': flags})
        q.atomic(end / 'COMPLETE.json', {'rc': 0, 'config_sha256': self.entry['config_sha256'], 'audit_sha256': q.sha(end / 'INDEPENDENT_AUDIT.json'), 'review_flags': flags,
            'status': 'COMPLETED_SCOPED_REVIEW_REQUIRED' if flags else 'COMPLETED_SCOPED'})
        (end / 'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
        return run, end

    def test_complete_flags_preserved(self):
        self.completed_artifacts(['boundary accuracy'])
        with patch.object(q, 'docker', self.docker):
            result = self.z.completion(self.c, self.entry, include_hardened=False)
        self.assertEqual(result['review_flags'], ['boundary accuracy'])

    def test_changed_report_rejected(self):
        run, end = self.completed_artifacts()
        (run / 'report.json').write_text('{}')
        with patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'output changed'):
            self.z.completion(self.c, self.entry, include_hardened=False)

    def test_missing_audit_marker_rejected(self):
        run, end = self.completed_artifacts()
        (end / 'COMPLETE.json').unlink()
        with patch.object(q, 'docker', self.docker), self.assertRaises(FileNotFoundError):
            self.z.completion(self.c, self.entry, include_hardened=False)

    def test_changed_audit_digest_rejected(self):
        run, end = self.completed_artifacts()
        a = q.load(end / 'INDEPENDENT_AUDIT.json')
        a['rows'] = 1
        q.atomic(end / 'INDEPENDENT_AUDIT.json', a)
        with patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'Audit binding'):
            self.z.completion(self.c, self.entry, include_hardened=False)


    def test_hardened_stage_blocks_completion_and_preserves_flags(self):
        run, end = self.completed_artifacts(['native flag'])
        ho = self.root / 'hardened'
        ho.mkdir()
        (ho / 'run.sh').write_text('exit 0')
        self.entry['key'] = 'nimble'
        self.entry['hardened'] = {'out': str(ho), 'container': 'hardened'}
        self.z.plan['entries'] = [self.entry]
        self.run_role('hardened')
        with patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'Hardened actual exit'):
            self.z.completion(self.c, self.entry)
        self.containers['hardened']['State']['Status'] = 'exited'
        hr = {'status': 'VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED', 'config_sha256': self.entry['config_sha256'],
              'report_sha256': q.sha(run / 'report.json'), 'review_flags': [{'kind': 'small_cell'}], 'inherited_review_flags': ['native flag']}
        q.atomic(ho / 'HARDENED_AUDIT.json', hr)
        q.atomic(ho / 'COMPLETE.json', {'rc': 0, 'config_sha256': self.entry['config_sha256'], 'audit_sha256': q.sha(ho / 'HARDENED_AUDIT.json')})
        (ho / 'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
        with patch.object(q, 'docker', self.docker):
            result = self.z.completion(self.c, self.entry)
        self.assertEqual(result['review_flags']['hardened'], [{'kind': 'small_cell'}])
        self.assertEqual(result['review_flags']['native'], ['native flag'])
        (ho / 'HARDENED_AUDIT.json').write_text('{}')
        with patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'Hardened terminal'):
            self.z.completion(self.c, self.entry)

    def test_release_gap_recovers_matching_intent(self):
        acceptance = self.root / 'accepted.json'
        q.atomic(acceptance, {'config_sha256': self.entry['config_sha256']})
        allocation = Path(self.z.plan['allocation'])
        q.atomic(allocation, {'allocation': [{'chip': 1, 'run': 'reference_inference/' + Path(self.c['out']).name}], 'free': []})
        real = q.atomic
        def crash(path, value):
            real(path, value)
            if Path(path) == allocation:
                raise KeyboardInterrupt()
        with patch.object(q, 'atomic', crash), patch.object(q, 'docker', self.docker), self.assertRaises(KeyboardInterrupt):
            self.z.release(self.c, acceptance)
        with patch.object(q, 'docker', self.docker):
            self.z.release(self.c, acceptance)
        self.assertTrue((self.root / 'nimble-RELEASED.json').exists())
        q.atomic(acceptance, {'config_sha256': 'changed'})
        with self.assertRaisesRegex(ValueError, 'Release receipt differs'):
            self.z.release(self.c, acceptance)

    def test_live_device_rejects_before_create(self):
        self.z = q.Queue.__new__(q.Queue)
        self.z.__dict__.update(fixture(self.root)[0].__dict__)
        self.z.spec = lambda c, role: FixtureQueue.spec(self.z, c, role)
        real = self.docker
        def api(method, path, value=None):
            if path == '/containers/json':
                return [{'Id': 'foreign'}]
            if path == '/containers/foreign/json':
                return {'HostConfig': {'Devices': [{'PathOnHost': '/dev/davinci1', 'PathInContainer': '/dev/davinci1', 'CgroupPermissions': 'rwm'}]}}
            return real(method, path, value)
        with patch.object(q, 'docker', api), self.assertRaisesRegex(ValueError, 'Live chip before create'):
            self.z.reconcile(self.c, self.entry, 'inference')
        self.assertEqual(self.created, 0)


    def test_changed_entry_config_fails_before_admission(self):
        cp = self.root / 'config.json'
        q.atomic(cp, {'version': 1})
        entry = {'config': str(cp), 'config_sha256': q.sha(cp)}
        q.atomic(cp, {'version': 2})
        self.z.check_plan = lambda: None
        with self.assertRaisesRegex(ValueError, 'Config changed'):
            self.z.check_entry(self.c, entry)


def real_child(root, role, crash):
    z, c, entry = fixture(root)
    z.real_docker = True
    real_docker, real_atomic = q.docker, q.atomic
    def api(method, path, value=None):
        result = real_docker(method, path, value)
        if crash == 'create' and '/create?' in path:
            os.kill(os.getpid(), signal.SIGKILL)
        return result
    def write(path, value):
        real_atomic(path, value)
        if crash == 'receipt' and Path(path).name == 'LAUNCH_RECEIPT.json':
            os.kill(os.getpid(), signal.SIGKILL)
    q.docker, q.atomic = api, write
    z.reconcile(c, entry, role)


def real_fixture(root):
    require = q.require
    require(q.docker('GET', '/info')['Name'] == 'k8s-node1', '175 only')
    setup_fixture(root)
    script = str(Path(__file__).resolve())
    results = []
    for role, crash in [('inference', 'create'), ('inference', 'receipt'), ('finish', 'create')]:
        cmd = [sys.executable, '-P', script, '--fixture-child', str(root), role, crash]
        p = subprocess.run(cmd)
        require(p.returncode == -signal.SIGKILL, 'Expected actual child SIGKILL')
        results.append({'role': role, 'seam': crash, 'child_exit': p.returncode})
    for role in ['inference', 'finish']:
        real_child(root, role, 'none')
    z, c, entry = fixture(root)
    z.real_docker = True
    ids = []
    deadline = q.time.monotonic() + 45
    for role in ['inference', 'finish']:
        out, name = z.context(c, role)
        while True:
            d = q.inspect(name)
            q.binding(d, z.spec(c, role), q.load(out / 'LAUNCH_RECEIPT.json'))
            if d['State']['Status'] == 'exited':
                require(d['State']['ExitCode'] == 0 and (out / 'FIXTURE_EXIT').exists(), 'Fixture did not complete')
                break
            require(q.time.monotonic() < deadline, 'Fixture still running')
            q.time.sleep(1)
        ids.append(d['Id'])
    q.atomic(root / 'FIXTURE_COMPLETE.json', {'rc': 0, 'utc': q.utc(), 'interruptions': results, 'container_ids': ids,
        'scope': 'Actual CPU-only Docker create/receipt/finisher seams with SIGKILL; no NPU allocation or model-score acceptance claim'})
    print(json.dumps(q.load(root / 'FIXTURE_COMPLETE.json')))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--fixture-child':
        real_child(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    elif len(sys.argv) > 1 and sys.argv[1] == '--docker-fixture':
        real_fixture(Path(sys.argv[2]))
    else:
        unittest.main()
