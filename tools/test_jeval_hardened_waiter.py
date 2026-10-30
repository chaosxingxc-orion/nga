#!/usr/bin/env python3
import copy
import json
import os
import subprocess
import sys
import time
import importlib.util
from pathlib import Path
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch

s = importlib.util.spec_from_file_location('waiter', Path(__file__).with_name('jeval_hardened_waiter.py'))
w = importlib.util.module_from_spec(s)
s.loader.exec_module(w)


class WaiterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = self.root / 'run'
        self.finish = self.root / 'run_finish'
        self.run.mkdir(); self.finish.mkdir()
        self.cp = self.run / 'config.json'
        w.atomic(self.cp, {'out': str(self.run)})
        self.plan = {'config': str(self.cp), 'config_sha256': w.sha(self.cp), 'sources': {}}
        self.actual = {}
        for role, out in [('inference', self.run), ('finish', self.finish)]:
            (out / 'run.sh').write_text('exit 0')
            d = {'Id': role, 'Image': w.IMAGE, 'State': {'Status': 'running', 'ExitCode': 0},
                 'Config': {'Cmd': ['bash', str(out / 'run.sh')], 'Entrypoint': ['bash'], 'Env': ['A=1']},
                 'HostConfig': {'Binds': [], 'Devices': [], 'ShmSize': 67108864, 'NetworkMode': 'none'}}
            r = {'container_id': role, 'config_sha256': w.sha(self.cp), 'wrapper_sha256': w.sha(out / 'run.sh')}
            w.atomic(out / 'LAUNCH_RECEIPT.json', r)
            self.plan['sources'][role] = {'container_id': role, 'Config': copy.deepcopy(d['Config']), 'HostConfig': copy.deepcopy(d['HostConfig']), 'receipt_sha256': w.sha(out / 'LAUNCH_RECEIPT.json')}
            self.actual[role] = d

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        with patch.object(w, 'inspect', lambda n: self.actual[n]):
            return w.source_state(self.plan)

    def completed(self):
        w.atomic(self.run / 'report.json', {})
        w.atomic(self.run / 'PROBE.json', {})
        w.atomic(self.run / 'COMPLETE.json', {'rc': 0, 'config_sha256': w.sha(self.cp), 'stage': 'completed', 'progress': 11257, 'total': 11257,
            'outputs': {n: w.sha(self.run / n) for n in ['report.json', 'PROBE.json']}})
        (self.run / 'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
        w.atomic(self.finish / 'INDEPENDENT_AUDIT.json', {'config_sha256': w.sha(self.cp), 'report_sha256': w.sha(self.run / 'report.json'), 'rows': 11257, 'status': 'VERIFIED_SCOPED', 'review_flags': ['x']})
        w.atomic(self.finish / 'COMPLETE.json', {'rc': 0, 'config_sha256': w.sha(self.cp), 'audit_sha256': w.sha(self.finish / 'INDEPENDENT_AUDIT.json'), 'review_flags': ['x']})
        (self.finish / 'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
        for d in self.actual.values(): d['State']['Status'] = 'exited'

    def test_actual_running_waits_even_if_markers_exist(self):
        self.completed()
        self.actual['finish']['State']['Status'] = 'running'
        self.assertFalse(self.state())

    def test_both_complete_accepts(self):
        self.completed()
        self.assertTrue(self.state())

    def test_foreign_container_fails(self):
        self.actual['inference']['Id'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'identity'): self.state()

    def test_nonzero_exit_fails(self):
        self.actual['finish']['State'] = {'Status': 'exited', 'ExitCode': 137}
        with self.assertRaisesRegex(ValueError, 'Source failed'): self.state()

    def test_changed_config_fails(self):
        self.cp.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'config changed'): self.state()

    def test_missing_terminal_fails(self):
        self.actual['inference']['State']['Status'] = 'exited'
        with self.assertRaises(FileNotFoundError): self.state()

    def test_changed_output_fails(self):
        self.completed()
        (self.run / 'report.json').write_text('{"bad":true}')
        with self.assertRaisesRegex(ValueError, 'output changed'): self.state()

    def test_changed_audit_flags_fails(self):
        self.completed()
        t = w.load(self.finish / 'COMPLETE.json'); t['review_flags'] = []
        w.atomic(self.finish / 'COMPLETE.json', t)
        (self.finish / 'EXIT').write_text('rc=0 utc=2026-10-30T00:00:00Z\n')
        with self.assertRaisesRegex(ValueError, 'audit differs'): self.state()



class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        self.cp = self.out / 'config.json'; w.atomic(self.cp, {'out': str(self.out)})
        self.auditor = self.out / 'auditor.py'
        self.auditor.write_text("""import argparse,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--out');a=p.parse_args()
Path(a.out).write_text(json.dumps(dict(config_sha256=hashlib.sha256(Path(a.config).read_bytes()).hexdigest(),status='VERIFIED_HARDENED_SCOPED',review_flags=[],inherited_review_flags=[])))
""")
        self.plan = {'config': str(self.cp), 'config_sha256': w.sha(self.cp), 'auditor': str(self.auditor)}
        self.validate = lambda p, r: self.assertEqual(r['config_sha256'], p['config_sha256'])

    def tearDown(self): self.tmp.cleanup()

    def reconcile(self):
        return w.reconcile_audit(self.plan, 'plan', self.out, lambda p: True, self.validate)

    def test_real_success_attempt_recovers_published_report(self):
        first = self.reconcile(); state = w.load(self.out / 'AUDIT_STATE.json')
        second = self.reconcile()
        self.assertEqual(first, second)
        self.assertEqual(len(w.load(self.out / 'AUDIT_STATE.json')['attempts']), 1)
        self.assertEqual(state['phase'], 'committed')

    def test_changed_published_report_rejected(self):
        self.reconcile(); w.atomic(self.out / 'HARDENED_AUDIT.json', {'changed': True})
        with self.assertRaisesRegex(ValueError, 'Published audit differs'): self.reconcile()

    def test_changed_attempt_report_rejected(self):
        self.reconcile(); p = self.out / 'attempts/attempt-0/HARDENED_AUDIT.json'
        p.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Attempt output changed'): self.reconcile()

    def test_missing_completion_preserves_partial_attempt(self):
        ad = self.out / 'attempts/attempt-0'; ad.mkdir(parents=True)
        (ad / 'attempt.lock').touch()
        a = {'plan_sha256': 'plan', 'config_sha256': self.plan['config_sha256'],
             'auditor': str(self.auditor), 'auditor_sha256': w.sha(self.auditor)}
        w.atomic(ad / 'attempt.json', a); (ad / 'HARDENED_AUDIT.json').write_text('{')
        w.atomic(self.out / 'AUDIT_STATE.json', {'plan_sha256': 'plan', 'attempts': [{'path': str(ad / 'attempt.json'), 'sha256': w.sha(ad / 'attempt.json')}], 'phase': 'prepared'})
        self.reconcile()
        self.assertEqual((ad / 'HARDENED_AUDIT.json').read_text(), '{')
        self.assertTrue((ad / 'ABANDONED.json').exists())
        self.assertEqual(len(w.load(self.out / 'AUDIT_STATE.json')['attempts']), 2)

    def test_abandoned_marker_before_state_commit_recovers(self):
        original_atomic = w.atomic
        def interrupted_atomic(path, value):
            if Path(path).name == 'AUDIT_STATE.json' and value.get('phase') == 'abandoned':
                raise RuntimeError('simulated metadata interruption')
            original_atomic(path, value)
        with patch.object(w, 'atomic', interrupted_atomic):
            with self.assertRaisesRegex(RuntimeError, 'metadata interruption'):
                self.test_missing_completion_preserves_partial_attempt()
        marker = self.out / 'attempts/attempt-0/ABANDONED.json'
        before = w.sha(marker)
        self.reconcile()
        self.assertEqual(w.sha(marker), before)
        self.assertEqual(len(w.load(self.out / 'AUDIT_STATE.json')['attempts']), 2)

    def test_untracked_prepared_directory_preserved(self):
        ad = self.out / 'attempts/attempt-0'; ad.mkdir(parents=True)
        (ad / 'partial.json').write_text('{')
        self.reconcile()
        orphans = list(ad.parent.glob('attempt-0.untracked-*'))
        self.assertEqual(len(orphans), 1)
        self.assertEqual((orphans[0] / 'partial.json').read_text(), '{')

    def test_live_untracked_directory_not_moved_or_launched(self):
        ad = self.out / 'attempts/attempt-0'; ad.mkdir(parents=True)
        with (ad / 'attempt.lock').open('w') as lock:
            w.fcntl.flock(lock, w.fcntl.LOCK_EX | w.fcntl.LOCK_NB)
            with patch.object(w.time, 'sleep', side_effect=RuntimeError('waiting safely')):
                with self.assertRaisesRegex(RuntimeError, 'waiting safely'):self.reconcile()
            self.assertTrue(ad.is_dir())
            self.assertFalse((self.out / 'AUDIT_STATE.json').exists())
            self.assertFalse(list(ad.parent.glob('*.untracked-*')))

    def test_failed_auditor_not_retried(self):
        self.auditor.write_text('raise RuntimeError("actual audit failed")')
        with self.assertRaisesRegex(ValueError, 'Audit attempt failed'): self.reconcile()
        self.assertEqual(len(w.load(self.out / 'AUDIT_STATE.json')['attempts']), 1)

    def test_auditor_signal_preserved_and_retried(self):
        self.auditor.write_text(self.auditor.read_text().replace('Path(a.out).write_text',
            "import os\nif Path(a.out).parent.name == 'attempt-0':\n Path(a.out).write_text('{');os.kill(os.getpid(),9)\nPath(a.out).write_text"))
        self.reconcile()
        old = self.out / 'attempts/attempt-0'
        self.assertEqual(w.load(old / 'ATTEMPT_COMPLETE.json')['auditor_returncode'], -9)
        self.assertEqual((old / 'HARDENED_AUDIT.json').read_text(), '{')
        self.assertEqual(len(w.load(self.out / 'AUDIT_STATE.json')['attempts']), 2)

    def test_reused_supervisor_pid_waits_for_inherited_lock(self):
        ad = self.out / 'attempts/attempt-0'; ad.mkdir(parents=True)
        a = dict(plan_sha256='plan', config_sha256=self.plan['config_sha256'],
                 auditor=str(self.auditor), auditor_sha256=w.sha(self.auditor), command=['supervisor'])
        w.atomic(ad / 'attempt.json', a)
        h = w.sha(ad / 'attempt.json')
        w.atomic(self.out / 'AUDIT_STATE.json', dict(plan_sha256='plan', phase='prepared',
                 attempts=[dict(path=str(ad / 'attempt.json'), sha256=h)]))
        w.atomic(ad / 'PROCESS.json', dict(attempt_sha256=h, process=dict(pid=123, argv=['supervisor'])))
        with (ad / 'attempt.lock').open('w') as lock:
            w.fcntl.flock(lock, w.fcntl.LOCK_EX | w.fcntl.LOCK_NB)
            with patch.object(w, 'process_identity', return_value=dict(pid=123, argv=['unrelated'])), \
                    patch.object(w.time, 'sleep', side_effect=RuntimeError('still waiting')):
                with self.assertRaisesRegex(RuntimeError, 'still waiting'): self.reconcile()
        self.assertFalse((ad / 'ABANDONED.json').exists())
        self.assertTrue((self.out / 'SUPERVISOR_IDENTITY_NOTICE.json').exists())

    def test_wrapper_exit_requires_exact_review_then_archives(self):
        e = self.out / 'EXIT'; e.write_text('rc=137 utc=2026-10-30T20:00:00Z\n')
        with self.assertRaises(FileNotFoundError):w.recover_wrapper_exit(self.plan, 'plan', self.out, 'container')
        w.atomic(self.out / 'RESUME_REVIEW.json', {'approved_plan_sha256': 'plan', 'container_id': 'container', 'exit_sha256': w.sha(e)})
        w.recover_wrapper_exit(self.plan, 'plan', self.out, 'container')
        self.assertFalse(e.exists()); self.assertEqual(len(list(self.out.glob('interruption-*/EXIT'))), 1)

    def test_success_wrapper_cannot_resume(self):
        e = self.out / 'EXIT'; e.write_text('rc=0 utc=2026-10-30T20:00:00Z\n')
        w.atomic(self.out / 'RESUME_REVIEW.json', {'approved_plan_sha256': 'plan', 'container_id': 'container', 'exit_sha256': w.sha(e)})
        with self.assertRaisesRegex(ValueError, 'Successful/invalid'):w.recover_wrapper_exit(self.plan, 'plan', self.out, 'container')

    def test_active_attempt_lock_prevents_duplicate_auditor(self):
        self.auditor.write_text(self.auditor.read_text().replace("Path(a.out).write_text", "import time;time.sleep(0.25)\nPath(a.out).write_text"))
        self.reconcile()
        self.assertEqual(len(w.load(self.out / 'AUDIT_STATE.json')['attempts']), 1)

    def test_auditor_success_without_report_is_failed_terminal(self):
        self.auditor.write_text('pass')
        with self.assertRaisesRegex(ValueError, 'Audit attempt failed'): self.reconcile()
        self.assertEqual(w.load(self.out / 'attempts/attempt-0/ATTEMPT_COMPLETE.json')['rc'], 1)

    def test_publication_is_atomic_and_no_clobber(self):
        p = self.out / 'evidence.json'; w.no_clobber_json(p, {'x': 1})
        with self.assertRaises(FileExistsError):w.no_clobber_json(p, {'x': 2})
        self.assertEqual(w.load(p), {'x': 1})
        self.assertEqual(p.stat().st_mode & 0o777, 0o644)


def production_setup(out, auditor, wrapper_text='exit 0\n'):
    cp = out / 'config.json'
    wrapper = out / 'run.sh'; wrapper.write_text(wrapper_text)
    prereg = out / 'PREREGISTRATION.md'; prereg.write_text('Synthetic CPU recovery control\n')
    spec = dict(Config=dict(Cmd=[str(wrapper)], Entrypoint=['bash'], Env=[]),
                HostConfig=dict(Binds=[], Devices=[], NetworkMode='none', ShmSize=67108864))
    w.atomic(out / 'CONTAINER_SPEC.json', spec)
    files = [Path(w.__file__).resolve(), cp, wrapper, auditor, out / 'CONTAINER_SPEC.json', prereg]
    plan = dict(schema=1, image=w.IMAGE, readonly_sources=True, out=str(out), config=str(cp),
                config_sha256=w.sha(cp), wrapper=str(wrapper), auditor=str(auditor),
                container='fixture-container', container_spec=str(out / 'CONTAINER_SPEC.json'),
                preregistration=str(prereg), files={str(p): w.sha(p) for p in files})
    w.atomic(out / 'plan.json', plan)
    ph = w.sha(out / 'plan.json')
    w.atomic(out / 'PARENT_REVIEW.json', dict(approved_plan_sha256=ph))
    w.atomic(out / 'LAUNCH_RECEIPT.json', dict(container_id='fixture-container', plan_sha256=ph,
                                            wrapper_sha256=w.sha(wrapper)))
    actual = dict(spec, Id='fixture-container', Image=w.IMAGE)
    return plan, actual


def production_controls(plan, actual):
    """Mock only synthetic source/Docker/metric controls; run() commits for real."""
    stack = ExitStack()
    validate = lambda p, r: w.require(r['config_sha256'] == p['config_sha256'], 'Fixture config differs')
    original = w.reconcile_audit
    stack.enter_context(patch.object(w, 'inspect', return_value=actual))
    stack.enter_context(patch.object(w, 'source_state', return_value=True))
    stack.enter_context(patch.object(w, 'cpu_mount_binding'))
    stack.enter_context(patch.object(w, 'audit_report', side_effect=validate))
    stack.enter_context(patch.object(w, 'reconcile_audit', side_effect=lambda p, ph, out:
        original(p, ph, out, source_validator=lambda p: True, report_validator=validate)))
    return stack


class ProductionRunTests(unittest.TestCase):
    def setUp(self):
        RecoveryTests.setUp(self)
        self.plan, self.actual = production_setup(self.out, self.auditor)

    def tearDown(self):
        self.tmp.cleanup()

    def production_run(self):
        w.run(self.out / 'plan.json')

    def test_public_report_tamper_before_production_terminal_rejected(self):
        with production_controls(self.plan, self.actual):
            reconcile = w.reconcile_audit
            def replace_public(*args):
                report = reconcile(*args)
                (self.out / 'HARDENED_AUDIT.json').write_text('{}')
                return report
            with patch.object(w, 'reconcile_audit', side_effect=replace_public):
                with self.assertRaisesRegex(ValueError, 'published audit changed'):self.production_run()
        self.assertEqual(w.load(self.out / 'COMPLETE.json')['rc'], 1)

    def test_concurrent_production_terminal_preserved(self):
        original = w.no_clobber_json
        def race(path, value):
            if Path(path) == self.out / 'COMPLETE.json':
                original(path, dict(rc=99, competing='preserve me'))
            return original(path, value)
        with production_controls(self.plan, self.actual), patch.object(w, 'no_clobber_json', side_effect=race):
            with self.assertRaises(FileExistsError):self.production_run()
        self.assertEqual(w.load(self.out / 'COMPLETE.json'), dict(rc=99, competing='preserve me'))

    def test_production_success_terminal_wrapper_recovery_preserves_bytes(self):
        with production_controls(self.plan, self.actual):self.production_run()
        complete_hash = w.sha(self.out / 'COMPLETE.json')
        report_hash = w.sha(self.out / 'HARDENED_AUDIT.json')
        (self.out / 'EXIT').write_text('rc=137 utc=fixture\n')
        w.atomic(self.out / 'RESUME_REVIEW.json', dict(approved_plan_sha256=w.sha(self.out / 'plan.json'),
                 container_id='fixture-container', exit_sha256=w.sha(self.out / 'EXIT')))
        with production_controls(self.plan, self.actual):self.production_run()
        self.assertEqual(w.sha(self.out / 'COMPLETE.json'), complete_hash)
        self.assertEqual(w.sha(self.out / 'HARDENED_AUDIT.json'), report_hash)
        self.assertFalse((self.out / 'EXIT').exists())
        self.assertEqual(len(w.load(self.out / 'AUDIT_STATE.json')['attempts']), 1)


def fixture_child(root, seam):
    plan = w.load(root / 'fixture-plan.json'); ph = w.sha(root / 'fixture-plan.json')
    def source(p):
        return w.sha(p['config']) == p['config_sha256']
    def validate(p, report):
        assert report['config_sha256'] == p['config_sha256']
        if seam == 'publish' and (root / 'HARDENED_AUDIT.json').exists() and not (root / 'KILLED_ONCE').exists():
            (root / 'KILLED_ONCE').write_text('publication-before-waiter-terminal')
            os.kill(os.getpid(), 9)
    if (root / 'EXIT').exists():w.recover_wrapper_exit(plan, ph, root, 'fixture-container')
    report = w.reconcile_audit(plan, ph, root, source, validate)
    w.no_clobber_json(root / 'COMPLETE.json', {'rc': 0, 'plan_sha256': ph, 'audit_sha256': w.sha(root / 'HARDENED_AUDIT.json')})


def docker_fixture(root):
    root.mkdir()
    script = Path(__file__).resolve()
    results = []
    for seam in ['publish', 'partial']:
        out = root / seam; out.mkdir(); cp = out / 'config.json'; w.atomic(cp, {'fixture': seam})
        auditor = out / 'fixture_auditor.py'
        auditor.write_text("import argparse,json,hashlib,os\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--out');a=p.parse_args();out=Path(a.out)\n"
            + ("if out.parent.name=='attempt-0':\n out.write_text('{');os.kill(os.getppid(),9);os._exit(137)\n" if seam == 'partial' else '')
            + "out.write_text(json.dumps(dict(config_sha256=hashlib.sha256(Path(a.config).read_bytes()).hexdigest(),status='VERIFIED_HARDENED_SCOPED')))\n")
        plan = {'config': str(cp), 'config_sha256': w.sha(cp), 'auditor': str(auditor)}
        w.atomic(out / 'fixture-plan.json', plan)
        wrapper = out / 'run.sh'
        import shlex
        wrapper.write_text('#!/bin/bash\nset -uo pipefail\n' + shlex.join([sys.executable, '-P', str(script), '--fixture-child', str(out), seam])
                          + '\nrc=$?\nprintf "rc=%s utc=%s\\n" "$rc" "$(date -u +%FT%TZ)" > ' + shlex.quote(str(out / 'EXIT')) + '\nexit "$rc"\n')
        first = subprocess.run(['bash', str(wrapper)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if seam == 'publish':
            assert first.returncode == 137 and not (out / 'COMPLETE.json').exists()
            before = w.sha(out / 'HARDENED_AUDIT.json')
            w.atomic(out / 'RESUME_REVIEW.json', {'approved_plan_sha256': w.sha(out / 'fixture-plan.json'), 'container_id': 'fixture-container', 'exit_sha256': w.sha(out / 'EXIT')})
            second = subprocess.run(['bash', str(wrapper)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            assert second.returncode == 0 and w.sha(out / 'HARDENED_AUDIT.json') == before
            assert len(w.load(out / 'AUDIT_STATE.json')['attempts']) == 1
        else:
            assert first.returncode == 0
            assert (out / 'attempts/attempt-0/HARDENED_AUDIT.json').read_text() == '{'
            assert (out / 'attempts/attempt-0/ABANDONED.json').exists()
            assert len(w.load(out / 'AUDIT_STATE.json')['attempts']) == 2
        results.append({'seam': seam, 'initial_wrapper_exit': first.returncode, 'final_exit': 0, 'audit_sha256': w.sha(out / 'HARDENED_AUDIT.json'), 'attempts': len(w.load(out / 'AUDIT_STATE.json')['attempts'])})
    w.no_clobber_json(root / 'FIXTURE_COMPLETE.json', {'rc': 0, 'utc': w.utc(), 'results': results, 'scope': 'Actual CPU subprocess SIGKILL with wrapper EXIT 137 and incomplete auditor artifact; no model or NPU claims'})


def production_fixture_child(root, seam):
    plan = w.load(root / 'plan.json')
    actual = dict(w.load(root / 'CONTAINER_SPEC.json'), Id='fixture-container', Image=w.IMAGE)
    original = w.no_clobber_json
    def kill_at_publication(path, value):
        original(path, value)
        target = root / ('COMPLETE.json' if seam == 'terminal' else 'HARDENED_AUDIT.json')
        if seam in ['publish', 'terminal'] and Path(path) == target and not (root / 'KILLED_ONCE').exists():
            (root / 'KILLED_ONCE').write_text(seam)
            os.kill(os.getpid(), 9)
    with production_controls(plan, actual), patch.object(w, 'no_clobber_json', side_effect=kill_at_publication):
        w.run(root / 'plan.json')


def production_docker_fixture(root):
    import shlex
    root.mkdir()
    results = []
    for seam in ['publish', 'terminal', 'auditor_signal', 'partial']:
        out = root / seam; out.mkdir()
        w.atomic(out / 'config.json', dict(out=str(out), fixture=seam))
        auditor = out / 'fixture_auditor.py'
        control = ''
        if seam in ['auditor_signal', 'partial']:
            victim = 'os.getpid()' if seam == 'auditor_signal' else 'os.getppid()'
            control = "if out.parent.name=='attempt-0':\n out.write_text('{');os.kill(" + victim + ",9);os._exit(137)\n"
        auditor.write_text("import argparse,json,hashlib,os\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--out');a=p.parse_args();out=Path(a.out)\n"
            + control + "out.write_text(json.dumps(dict(config_sha256=hashlib.sha256(Path(a.config).read_bytes()).hexdigest(),status='VERIFIED_HARDENED_SCOPED',review_flags=[],inherited_review_flags=[])))\n")
        wrapper = '#!/bin/bash\nset -uo pipefail\n' + shlex.join([sys.executable, '-P', str(Path(__file__).resolve()), '--production-fixture-child', str(out), seam])
        wrapper += '\nrc=$?\nprintf "rc=%s utc=%s\\n" "$rc" "$(date -u +%FT%TZ)" > ' + shlex.quote(str(out / 'EXIT')) + '\nexit "$rc"\n'
        production_setup(out, auditor, wrapper)
        first = subprocess.run(['bash', str(out / 'run.sh')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        terminal_before = None
        if seam in ['publish', 'terminal']:
            assert first.returncode == 137
            report_before = w.sha(out / 'HARDENED_AUDIT.json')
            if seam == 'terminal':terminal_before = w.sha(out / 'COMPLETE.json')
            else:assert not (out / 'COMPLETE.json').exists()
            w.atomic(out / 'RESUME_REVIEW.json', dict(approved_plan_sha256=w.sha(out / 'plan.json'),
                     container_id='fixture-container', exit_sha256=w.sha(out / 'EXIT')))
            second = subprocess.run(['bash', str(out / 'run.sh')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            assert second.returncode == 0 and w.sha(out / 'HARDENED_AUDIT.json') == report_before
            if terminal_before:assert w.sha(out / 'COMPLETE.json') == terminal_before
            assert len(w.load(out / 'AUDIT_STATE.json')['attempts']) == 1
        else:
            assert first.returncode == 0
            assert (out / 'attempts/attempt-0/HARDENED_AUDIT.json').read_text() == '{'
            assert (out / 'attempts/attempt-0/ABANDONED.json').exists()
            assert len(w.load(out / 'AUDIT_STATE.json')['attempts']) == 2
            if seam == 'auditor_signal':
                assert w.load(out / 'attempts/attempt-0/ATTEMPT_COMPLETE.json')['auditor_returncode'] == -9
        terminal = w.load(out / 'COMPLETE.json')
        assert terminal['rc'] == 0 and terminal['audit_sha256'] == w.sha(out / 'HARDENED_AUDIT.json')
        results.append(dict(seam=seam, initial_wrapper_exit=first.returncode, final_exit=0,
                            original_terminal_preserved=terminal_before is not None,
                            attempts=len(w.load(out / 'AUDIT_STATE.json')['attempts']),
                            audit_sha256=terminal['audit_sha256']))
    w.no_clobber_json(root / 'FIXTURE_COMPLETE.json', dict(rc=0, utc=w.utc(), results=results,
        scope='Actual production run() commits and CPU subprocess SIGKILL; synthetic Docker/source/metric controls; not a model score or capability-isolation certification'))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--fixture-child':fixture_child(Path(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == '--docker-fixture':docker_fixture(Path(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == '--production-fixture-child':production_fixture_child(Path(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == '--production-docker-fixture':production_docker_fixture(Path(sys.argv[2]))
    else:unittest.main()
