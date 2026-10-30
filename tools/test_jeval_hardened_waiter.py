#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
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


if __name__ == '__main__': unittest.main()
