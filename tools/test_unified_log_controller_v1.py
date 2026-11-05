#!/usr/bin/env python3
"""Real supervisor/follower processes with a synthetic CPU and fake Docker CLI."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from tools import test_unified_container_log_follower_v1 as fixture
from tools import unified_log_controller_v1 as L
from tools import unified_container_log_follower_v1 as F


class Integration(unittest.TestCase):
    def setUp(self):
        self.f = fixture.FollowerTest('test_live_replay_completion_and_lock')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.info = L.prepare(self.f.ref, self.f.c['controller'], str(Path(sys.executable).resolve()), max_retries=1)
        self.state = Path(self.info['state_dir'])
        self.capture = Path(self.info['capture_dir'])
        self.config = self.info['supervisor_config']
        self.addCleanup(self.stop_processes)

    def stop_processes(self):
        # Only processes carrying this temporary test's exact config or recorded identity.
        for p in Path('/proc').iterdir():
            if p.name.isdecimal():
                try:
                    args = (p/'cmdline').read_bytes().split(b'\0')
                    if self.config['path'].encode() in args and b'monitor' in args:
                        os.kill(int(p.name), signal.SIGKILL)
                except (OSError, ValueError): pass
        for path in self.state.glob('attempts/*/*.json'):
            if path.name not in ('runner.json', 'service.json'): continue
            try:
                obj = json.loads(path.read_text()); ident = obj.get('identity', obj)
                if L.S.matches(ident): os.kill(ident['pid'], signal.SIGKILL)
            except (OSError, ValueError, TypeError): pass
        try: os.kill(int((self.f.root/'childpid').read_text()), signal.SIGTERM)
        except (OSError, ValueError): pass

    def wait(self, condition, timeout=8):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                result = condition()
                if result: return result
            except (OSError, ValueError, KeyError): pass
            time.sleep(.03)
        self.fail('timeout waiting for subprocess evidence')

    def start(self, env=None):
        p = subprocess.run([sys.executable, '-B', '-P', str(L.S.__file__), 'start', '--config', self.config['path'], '--sha256', self.config['sha256']], env=env or self.f.env, capture_output=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_eof_retry_monitor_restart_and_success(self):
        self.assertEqual(self.info, L.prepare(self.f.ref, self.f.c['controller'], str(Path(sys.executable).resolve()), max_retries=1))
        self.start(); self.wait(lambda: (self.f.root/'started').exists())
        self.wait(lambda: (self.state/'attempts/1/service.json').exists())
        monitors = []
        for p in Path('/proc').iterdir():
            if p.name.isdecimal():
                try:
                    args = (p/'cmdline').read_bytes().split(b'\0')
                    if self.config['path'].encode() in args and b'monitor' in args: monitors.append(int(p.name))
                except OSError: pass
        self.assertEqual(len(monitors), 1); os.kill(monitors[0], signal.SIGKILL)
        time.sleep(.15); self.start()
        (self.f.root/'release').touch()
        first = self.capture/'attempts/00000001/TERMINAL.json'
        self.wait(first.exists)
        self.assertEqual(json.loads(first.read_text())['status'], 'stream_eof_not_completion')
        self.f.end_consumer()
        status = self.wait(lambda: (lambda x: x if x['state'] in ('completed','exhausted','blocked') else None)(json.loads((self.state/'status.json').read_text())))
        self.assertEqual(status['state'], 'completed', status)
        with mock.patch.dict(os.environ, self.f.env, clear=True):
            reconciliation = F.reconcile(self.f.ref, str(self.capture))
        self.assertEqual(reconciliation['consumer_completion']['exit_code'], 0)
        self.assertFalse((self.capture/'attempts/00000002').exists())
        self.assertEqual(json.loads((self.state/'attempts/1/terminal.json').read_text())['exit_code'], 0)
        calls = [json.loads(x) for x in (self.f.root/'commands').read_text().splitlines()]
        self.assertTrue(all(x[-1] == self.info['container_id'] for x in calls if x[0] == 'logs'))

    def test_stream_failure_remains_failed_with_consumer_success(self):
        self.f.end_consumer(); (self.f.root/'release').touch()
        self.start(dict(self.f.env, LOG_EXIT='7'))
        status = self.wait(lambda: (lambda x: x if x['state'] == 'exhausted' else None)(json.loads((self.state/'status.json').read_text())))
        self.assertEqual(status['retries_used'], 1)
        terminal = json.loads((self.capture/'attempts/00000002/TERMINAL.json').read_text())
        self.assertEqual((terminal['status'], terminal['stream_returncode'], terminal['consumer_completion']['exit_code']), ('stream_failed', 7, 0))

    def test_binding_and_fixed_controller_required(self):
        binding = Path(self.info['consumer_job'])/'BINDING.json'
        original = binding.read_bytes(); binding.unlink()
        with self.assertRaises(FileNotFoundError): L.prepare(self.f.ref, self.f.c['controller'], str(Path(sys.executable).resolve()))
        binding.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'controller differs'):
            L.prepare(self.f.ref, str(self.f.root/'foreign'), str(Path(sys.executable).resolve()))


if __name__ == '__main__': unittest.main(verbosity=2)
