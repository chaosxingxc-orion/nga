#!/usr/bin/env python3
"""Failure boundaries for E34; optional real Docker seam fixture."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
import types
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

    def empty_device_query(self, reason):
        # Fixture allocation is a local test file, not the production allocation.
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


def receipt_tree(run, count=11257):
    folder = run / 'records'
    folder.mkdir()
    entries = []
    for i in range(count):
        path = folder / f'{i:06d}.json'
        path.write_text('{}')
        entries.append({'path': 'records/' + path.name, 'sha256': q.sha(path)})
    body = dict(schema=1, algorithm='sha256', count=count, entries=entries)
    return dict(body, root_sha256=hashlib.sha256(json.dumps(body, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest())


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
        hr['receipt_manifest'] = receipt_tree(run)
        q.atomic(ho / 'HARDENED_AUDIT.json', hr)
        q.atomic(ho / 'COMPLETE.json', {'rc': 0, 'config_sha256': self.entry['config_sha256'], 'audit_sha256': q.sha(ho / 'HARDENED_AUDIT.json')})
        (ho / 'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
        with patch.object(q, 'docker', self.docker):
            result = self.z.completion(self.c, self.entry)
        self.assertEqual(result['review_flags']['hardened'], [{'kind': 'small_cell'}])
        self.assertEqual(result['review_flags']['native'], ['native flag'])
        (run / 'records' / '000000.json').write_text('{"changed":true}')
        with patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'Receipt content changed'):
            self.z.completion(self.c, self.entry)
        q.atomic(self.z.out / 'nimble-ACCEPTED.json', result)
        self.z.configs, self.z.keys = [self.c], ['nimble']
        self.z.check_plan = lambda: None
        with patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'Receipt content changed'):
            self.z.step()
        (ho / 'HARDENED_AUDIT.json').write_text('{}')
        with patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'Hardened terminal'):
            self.z.completion(self.c, self.entry)

    def test_release_gap_recovers_matching_intent(self):
        acceptance = self.root / 'accepted.json'
        manifest = receipt_tree(Path(self.c['out']))
        q.atomic(acceptance, {'config_sha256': self.entry['config_sha256'], 'receipt_manifest': manifest})
        allocation = Path(self.z.plan['allocation'])
        q.atomic(allocation, {'allocation': [{'chip': 1, 'run': 'reference_inference/' + Path(self.c['out']).name}], 'free': []})
        real = q.atomic
        before = allocation.read_bytes()
        with patch.object(self.z, 'empty_device_query', side_effect=ValueError('host query failed')), patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'host query failed'):
            self.z.release(self.c, acceptance)
        self.assertEqual(allocation.read_bytes(), before)
        def crash(path, value):
            real(path, value)
            if Path(path) == allocation:
                raise KeyboardInterrupt()
        with patch.object(q, 'atomic', crash), patch.object(q, 'docker', self.docker), self.assertRaises(KeyboardInterrupt):
            self.z.release(self.c, acceptance)
        with patch.object(q, 'docker', self.docker):
            self.z.release(self.c, acceptance)
        self.assertTrue((self.root / 'nimble-RELEASED.json').exists())
        (Path(self.c['out']) / 'records' / '000000.json').write_text('{"changed":1}')
        with self.assertRaisesRegex(ValueError, 'Receipt content changed'):
            self.z.release(self.c, acceptance)
        (Path(self.c['out']) / 'records' / '000000.json').write_text('{}')
        q.atomic(acceptance, {'config_sha256': 'changed', 'receipt_manifest': manifest})
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

    def test_live_bind_or_privileged_rejects_before_create(self):
        self.z = q.Queue.__new__(q.Queue)
        self.z.__dict__.update(fixture(self.root)[0].__dict__)
        self.z.spec = lambda c, role: FixtureQueue.spec(self.z, c, role)
        for host in [{'Binds': ['/dev:/devices']}, {'Privileged': True}, {'DeviceRequests': [{'Driver':'npu'}]}, {'DeviceCgroupRules':['c *:* rwm']}]:
            def api(method, path, value=None):
                if path == '/containers/json': return [{'Id':'foreign'}]
                if path == '/containers/foreign/json': return {'HostConfig':host}
                return self.docker(method, path, value)
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

    def test_resource_exposure_forms(self):
        for host in [{'Privileged': True}, {'DeviceRequests': [{'Driver': 'npu'}]}, {'DeviceCgroupRules': ['c *:* rwm']},
                     {'Binds': ['/dev:/elsewhere:ro']}, {'Binds': ['/dev/davinci1:/alias']},
                     {'Mounts': [{'Type': 'bind', 'Source': '/', 'Target': '/host'}]},
                     {'Devices': [{'PathOnHost': '/dev/davinci1', 'PathInContainer': '/alias', 'CgroupPermissions': 'rwm'}]}]:
            with self.subTest(host=host):
                self.assertTrue(q.chip_access({'HostConfig': host}))
        self.assertTrue(q.chip_access({'HostConfig': {}, 'Mounts': [{'Type': 'bind', 'Source': '/dev', 'Destination': '/host-dev'}]}))
        self.assertFalse(q.chip_access({'HostConfig': {'Binds': ['/mnt/cephfs:/mnt/cephfs'], 'Devices': [{'PathOnHost': '/dev/davinci2', 'PathInContainer': '/dev/davinci2', 'CgroupPermissions': 'rwm'}]}}))
        for host in [{'Binds': ['unknown']}, {'Mounts': [{'Type': 'unknown'}]}, {'Binds': ['relative:/dev']}]:
            with self.assertRaises(ValueError):
                q.chip_access({'HostConfig': host})

    def test_manifest_population_and_file_mutations(self):
        run = Path(self.c['out'])
        manifest = receipt_tree(run, count=2)
        self.assertEqual(q.verify_receipts(run, manifest, count=2), manifest['root_sha256'])
        for mutation in ['extra', 'missing', 'symlink', 'content', 'root']:
            p = run / 'records' / '000000.json'
            m = copy.deepcopy(manifest)
            with self.subTest(mutation=mutation):
                if mutation == 'extra': (run / 'records' / 'extra.json').write_text('{}')
                if mutation in ['missing', 'symlink']: p.unlink()
                if mutation == 'symlink': p.symlink_to(run / 'records' / '000001.json')
                if mutation == 'content': p.write_text('[]')
                if mutation == 'root': m['root_sha256'] = 'bad'
                with self.assertRaises(ValueError): q.verify_receipts(run, m, count=2)
                if p.exists() or p.is_symlink(): p.unlink()
                p.write_text('{}')
                (run / 'records' / 'extra.json').unlink(missing_ok=True)
        with self.assertRaisesRegex(ValueError, 'population'): q.verify_receipts(run, manifest)

    def test_process_query_strict_grammar(self):
        header = '\tNPU ID : 1\n\tChip Count : 1\n\n'
        footer = '\tChip ID : 0\n'
        empty = header + 'No process in device.\n' + footer
        live = header + 'Process id:833969  Process name:python3  Process memory(MB):19404\n' + footer
        self.assertEqual(q.parse_processes(empty), [])
        self.assertEqual(q.parse_processes(live), [{'pid':833969,'name':'python3','memory_mb':19404}])
        for output in ['', 'dcmi module initialize failed. ret is -8005', empty.replace('ID : 1', 'ID : 2'),
                       empty.replace('Count : 1', 'Count : 2'), empty.replace('No process in device.', ''),
                       empty + 'warning\n', live.replace('Process id:833969', 'Process id:unknown')]:
            with self.subTest(output=output), self.assertRaises(ValueError): q.parse_processes(output)

    def test_manifest_records_root_symlink_rejected(self):
        run = Path(self.c['out'])
        manifest = receipt_tree(run, count=2)
        (run / 'records').rename(run / 'original-records')
        (run / 'records').symlink_to(run / 'original-records', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Receipt directory changed'):
            q.verify_receipts(run, manifest, count=2)

    def test_claim_query_failure_never_changes_allocation(self):
        self.z = q.Queue.__new__(q.Queue)
        self.z.__dict__.update(fixture(self.root)[0].__dict__)
        allocation = Path(self.z.plan['allocation'])
        before = allocation.read_bytes()
        with patch.object(self.z, 'empty_device_query', side_effect=ValueError('query unavailable')), patch.object(q, 'docker', self.docker), self.assertRaisesRegex(ValueError, 'query unavailable'):
            self.z.resource(self.c, claim=True)
        self.assertEqual(allocation.read_bytes(), before)


class ProcessQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        script = str(Path(q.__file__).resolve())
        self.spec = dict(Image=q.IMAGE, Cmd=['-P', script, '--process-query', '{request}'], Entrypoint=['python3'], Env=['TORCH_DEVICE_BACKEND_AUTOLOAD=0'], Labels={},
            HostConfig=dict(Binds=['/mnt/cephfs:/mnt/cephfs', '/usr/local/sbin:/usr/local/sbin:ro', '/usr/local/Ascend/driver:/usr/local/Ascend/driver:ro', '/etc/ascend_install.info:/etc/ascend_install.info:ro'],
                Devices=[dict(PathOnHost=p, PathInContainer=p, CgroupPermissions='rwm') for p in ['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci1']],
                PidMode='host', NetworkMode='none', ShmSize=67108864))
        self.sp = self.root / 'SPEC.json'; q.atomic(self.sp, self.spec)
        self.z = q.Queue.__new__(q.Queue)
        self.z.out, self.z.hash = self.root, 'queue-hash'
        self.z.plan = dict(preparation_files=dict(process_query_spec=str(self.sp)), files={str(self.sp):q.sha(self.sp),script:q.sha(script)})
        self.output = 'NPU ID : 1\nChip Count : 1\nNo process in device.\nChip ID : 0\n'
        self.rc, self.mutation = 0, None
        self.containers = {}

    def tearDown(self): self.tmp.cleanup()

    def api(self, method, path, value=None):
        if path == '/containers/json': return []
        if method == 'GET': return self.containers.get(path.split('/')[2])
        if '/create?' in path:
            name = path.split('name=')[1]
            self.info = obj(value, name)
            self.containers[name] = self.containers[self.info['Id']] = self.info
            return {'Id':self.info['Id']}
        request = Path(self.info['Config']['Cmd'][-1])
        with patch.object(q.subprocess, 'run', return_value=types.SimpleNamespace(returncode=self.rc, stdout=self.output, stderr='')):
            try: q.process_query(request)
            except SystemExit as exc: self.info['State'].update(Status='exited', ExitCode=exc.code)
        if self.mutation == 'identity': self.info['Id'] = 'foreign'
        if self.mutation in ('nonce','stale'):
            report = q.load(request.parent / 'REPORT.json')
            report['nonce' if self.mutation == 'nonce' else 'finished_unix'] = 'wrong' if self.mutation == 'nonce' else 0
            q.atomic(request.parent / 'REPORT.json', report)
            t = q.load(request.parent / 'COMPLETE.json'); t['report_sha256'] = q.sha(request.parent / 'REPORT.json'); q.atomic(request.parent / 'COMPLETE.json', t)

    def test_empty_query_accepts_exact_retained_identity(self):
        with patch.object(q, 'docker', self.api): self.z.empty_device_query('claim')
        self.assertEqual(len(list((self.root/'process_queries').glob('*/ACCEPTED.json'))), 1)

    def test_busy_command_and_unknown_output_fail_closed(self):
        for mode in ['busy','unknown','processes']:
            self.containers = {}
            self.rc = 172 if mode == 'busy' else 0
            self.output = 'dcmi initialize failed' if mode != 'processes' else 'NPU ID : 1\nChip Count : 1\nProcess id:17  Process name:python3  Process memory(MB):3\nChip ID : 0\n'
            with patch.object(q, 'docker', self.api), self.assertRaises(ValueError): self.z.empty_device_query('release')
        self.assertEqual(len(list((self.root/'process_queries').glob('*/GUARD_FAILURE.json'))), 3)
        self.assertFalse(list((self.root/'process_queries').glob('*/ACCEPTED.json')))

    def test_identity_nonce_and_staleness_fail_closed(self):
        for mutation in ['identity','nonce','stale']:
            self.containers, self.mutation = {}, mutation
            with patch.object(q, 'docker', self.api), self.assertRaises(ValueError): self.z.empty_device_query('release')

    def test_changed_template_or_extra_device_never_launches(self):
        self.spec['HostConfig']['Privileged'] = True
        q.atomic(self.sp,self.spec)
        with patch.object(q, 'docker', side_effect=AssertionError('must not launch')), self.assertRaisesRegex(ValueError,'template changed'):
            self.z.empty_device_query('claim')
        self.z.plan['files'][str(self.sp)] = q.sha(self.sp)
        with patch.object(q, 'docker', side_effect=AssertionError('must not launch')), self.assertRaisesRegex(ValueError,'access differs'):
            self.z.empty_device_query('claim')


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
