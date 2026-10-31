import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

s = importlib.util.spec_from_file_location('queue', Path(__file__).with_name('r3_posttrain_eval_queue.py'))
Q = importlib.util.module_from_spec(s); s.loader.exec_module(Q)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.training = self.root / 'training'; self.training.mkdir()
        self.out = self.root / 'out'; self.out.mkdir()
        self.job = {'id': 'fixture', 'training': str(self.training), 'out': str(self.out), 'chip': 2,
                    'container': 'nga-r3-eng-eval-fixture', 'training_plan_sha256': 'frozen'}
        self.prepare, self.launcher, self.resource = Mock(), Mock(), Mock()

    def write(self, path, value):
        path.parent.mkdir(exist_ok=True, parents=True); path.write_text(json.dumps(value))

    def tick(self):
        return Q.tick(self.job, str(self.root / 'closure'), self.prepare, self.launcher, self.resource)

    def ready(self):
        self.write(self.training / 'TRAIN_EXIT.json', {'exit_code': 0})
        self.write(self.out / 'plan.json', {'training': str(self.training), 'training_variant': {'training_plan_sha256': 'frozen'}})
        self.plan = {'chip': 2, 'container': self.job['container'], 'spec': str(self.out / 'plan.json'),
                     'launcher': str(self.out / 'execution-tools/launcher.py'), 'run': 'r3_runs/fixture'}
        self.write(self.out / 'execution.json', self.plan)
        self.write(self.out / 'QUEUE_EXECUTION_PIN.json', {'sha256': Q.sha(self.out / 'execution.json')})

    def test_manifest_binds_tools_closure_and_training_chip(self):
        tools = self.root / 'tools'; tools.mkdir()
        names = ('r3_posttrain_eval_queue.py', 'r3_posttrain_eval_plan.py',
                 'r3_posttrain_eval_launcher.py', 'r3_resource_adapter.py')
        for name in names:
            (tools / name).write_text('# frozen fixture')
        self.write(self.training / 'plan.json', {'chip': 2})
        self.job['training_plan_sha256'] = Q.sha(self.training / 'plan.json')
        closure = self.root / 'closure'; self.write(closure / 'manifest.json', {})
        doc = {'schema': 'r3-posttrain-queue-v1', 'test_read': False, 'scientific_acceptance': False,
               'tools': {str(tools / n): Q.sha(tools / n) for n in names},
               'closure': str(closure), 'closure_sha256': Q.sha(closure / 'manifest.json'), 'jobs': [self.job]}
        manifest = self.root / 'queue.json'; self.write(manifest, doc); pin = Q.sha(manifest)
        with patch.object(Q, '__file__', str(tools / names[0])):
            self.assertEqual(Q.verify_manifest(manifest, pin)['jobs'][0]['chip'], 2)
            (tools / names[1]).write_text('# changed')
            with self.assertRaisesRegex(RuntimeError, 'tool changed'):
                Q.verify_manifest(manifest, pin)
        self.write(manifest, dict(doc, test_read=True))
        with self.assertRaisesRegex(RuntimeError, 'manifest changed'):
            Q.verify_manifest(manifest, pin)

    def test_wait_and_failed_training_never_prepare_or_launch(self):
        self.assertEqual(self.tick()['status'], 'waiting_training')
        self.write(self.training / 'TRAIN_EXIT.json', {'exit_code': 1})
        self.assertEqual(self.tick()['status'], 'training_failed')
        self.prepare.prepare.assert_not_called(); self.launcher.bind.assert_not_called()

    def test_probe_not_treated_as_complete(self):
        self.write(self.training / 'TRAIN_EXIT.json', {'exit_code': 0})
        self.prepare.prepare.return_value = {'status': 'not_complete_training'}
        self.assertEqual(self.tick()['status'], 'not_complete_training')
        self.launcher.bind.assert_not_called()

    def test_launch_once_intent_prevents_duplicate_after_uncertainty(self):
        self.ready()
        with patch.object(Q.subprocess, 'run') as run:
            self.assertEqual(self.tick()['status'], 'launch_requested')
            self.assertEqual(self.tick()['status'], 'needs_repair')
            self.assertEqual(run.call_count, 1)
        self.assertTrue((self.out / 'QUEUE_START_INTENT.json').exists())

    def test_actual_pid_command_checked_and_missing_not_restarted(self):
        self.ready(); pin = Q.sha(self.out / 'execution.json')
        command = [Q.sys.executable, '-P', self.plan['launcher'], 'supervise', '--plan', str(self.out / 'execution.json'), '--sha256', pin, '--attempt', '1']
        self.write(self.out / 'SUPERVISOR_RECEIPT.json', {'pid': 123, 'command': command})
        with patch.object(Q, 'process_matches', return_value=True), patch.object(Q.subprocess, 'run') as run:
            self.assertEqual(self.tick()['status'], 'supervisor_live'); run.assert_not_called()
        with patch.object(Q, 'process_matches', return_value=False), patch.object(Q.subprocess, 'run') as run:
            self.assertEqual(self.tick()['status'], 'needs_repair'); run.assert_not_called()

    def test_process_matches_real_command_bytes_and_pid_reuse(self):
        proc = self.root / 'proc'; (proc / '123').mkdir(parents=True)
        (proc / '123/cmdline').write_bytes(b'python\0script.py\0')
        self.assertTrue(Q.process_matches({'pid': 123, 'command': ['python', 'script.py']}, proc))
        self.assertFalse(Q.process_matches({'pid': 123, 'command': ['python', 'different.py']}, proc))
        self.assertFalse(Q.process_matches({'pid': 124, 'command': ['python', 'script.py']}, proc))

    def test_completion_requires_matching_marker_release_and_retained_container(self):
        self.ready()
        self.write(self.out / 'ENGINEERING_EVAL_EXIT.json', {'exit_code': 0})
        self.write(self.out / 'attempts/1/RELEASE.json', {'container_id': 'exact', 'exit_code': 0, 'chip': 2, 'run': self.plan['run']})
        self.write(self.out / 'attempts/1/LAUNCH_RECEIPT.json', {'id': 'exact'})
        self.resource.docker_inspect.return_value = {'Id': 'exact', 'State': {'Status': 'exited', 'ExitCode': 0}}
        self.assertEqual(self.tick()['status'], 'done')
        self.resource.docker_inspect.return_value['State']['Status'] = 'running'
        with self.assertRaisesRegex(RuntimeError, 'still live'): self.tick()
        self.resource.docker_inspect.side_effect = RuntimeError('daemon unavailable')
        with self.assertRaisesRegex(RuntimeError, 'unavailable'): self.tick()

    def test_changed_execution_and_wrong_training_refused(self):
        self.ready(); self.plan['chip'] = 3
        self.write(self.out / 'execution.json', self.plan)
        with self.assertRaisesRegex(RuntimeError, 'execution identity'): self.tick()
        self.write(self.out / 'plan.json', {'training': 'another'})
        with self.assertRaisesRegex(RuntimeError, 'another training'): self.tick()


if __name__ == '__main__': unittest.main()
