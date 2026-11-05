#!/usr/bin/env python3
"""Durable supervisor functional tests and registered local fake service."""
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SUP = HERE / 'unified_service_supervisor_v1.py'
sys.path.insert(0, str(HERE))
import unified_service_supervisor_v1 as S


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):
    p = str(Path(p).resolve()); return {'path': p, 'sha256': sha(p)}


def fake():
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--fake-service', action='store_true'); p.add_argument('--config'); p.add_argument('--sha256'); a = p.parse_args()
    if sha(a.config) != a.sha256: sys.exit(2)
    c = json.loads(Path(a.config).read_text())
    print('fake started', flush=True)
    if c['mode'] == 'terminal': return
    if c['mode'] == 'fail': sys.exit(3)
    while True: time.sleep(.1)


class Functional(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='supervisor-test-'); self.root = Path(self.tmp.name); self.state = self.root / 'state'
        self.service = self.root / 'service.json'; self.service.write_text('{"mode":"wait"}')
        self.config = self.root / 'supervisor.json'; self.write_config()

    def write_config(self):
        c = {'schema':'unified-service-supervisor-v1', 'service':'synthetic_fake_physical_v1', 'entry':ref(__file__), 'python':ref(sys.executable), 'service_config':ref(self.service), 'supervisor':ref(SUP), 'state_dir':str(self.state), 'heartbeat_seconds':10, 'max_retries':2, 'retry_backoff_seconds':1}
        self.config.write_text(json.dumps(c)); self.config_sha = sha(self.config)

    def call(self, *extra):
        return subprocess.run([sys.executable, '-B', '-P', str(SUP), 'start', '--config', str(self.config), '--sha256', self.config_sha, *extra], capture_output=True, timeout=5)

    def wait(self, fn, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = fn()
                if result: return result
            except (FileNotFoundError, json.JSONDecodeError, KeyError): pass
            time.sleep(.05)
        self.fail('timed out: ' + str(self.state))

    def attempt(self, n=1):
        a = self.state / 'attempts' / str(n)
        self.wait(lambda: (a / 'service.json').exists())
        return a

    def stop(self):
        # Stop the monitor before its child to prevent an intentional test teardown restart.
        lock = self.state / 'owner.lock'
        # Find monitor via /proc commandline restricted to this unique config.
        if lock.exists():
            for p in Path('/proc').iterdir():
                if not p.name.isdecimal(): continue
                try:
                    args = (p / 'cmdline').read_bytes().split(b'\0')
                    if b'monitor' in args and str(self.config).encode() in args: os.kill(int(p.name), signal.SIGKILL)
                except (OSError, ValueError): pass
        attempts = self.state / 'attempts'
        if attempts.exists():
            for a in attempts.iterdir():
                for name in ['service.json', 'runner.json']:
                    try:
                        obj = json.loads((a / name).read_text()); ident = obj.get('identity', obj)
                        if S.matches(ident): os.kill(ident['pid'], signal.SIGKILL)
                    except (OSError, ValueError, TypeError): pass
        time.sleep(.1); self.tmp.cleanup()

    def tearDown(self): self.stop()

    def test_terminal_and_stale_terminal(self):
        self.service.write_text('{"mode":"terminal"}'); self.write_config()
        self.state.mkdir(); (self.state / 'TERMINAL.json').write_text('{"exit_code":0}')
        self.assertNotEqual(self.call().returncode, 0)
        (self.state / 'OWNER.json').write_text(json.dumps({'config':str(self.config), 'sha256':self.config_sha}))
        self.assertEqual(self.call().returncode, 0)
        self.wait(lambda: json.loads((self.state / 'status.json').read_text())['state'] == 'completed')
        t = json.loads((self.state / 'attempts/1/terminal.json').read_text()); self.assertEqual((t['generation'], t['exit_code']), ('1', 0))
        self.assertIn('fake started', (self.state / 'attempts/1/stdout.log').read_text())

    def test_config_and_code_tamper(self):
        self.service.write_text('{}'); self.assertNotEqual(self.call().returncode, 0)
        self.write_config(); c = json.loads(self.config.read_text()); c['entry']['sha256'] = '0'*64; self.config.write_text(json.dumps(c)); self.config_sha = sha(self.config)
        self.assertNotEqual(self.call().returncode, 0); self.assertFalse(self.state.exists())
        self.write_config(); copied = self.root / 'python'; shutil.copyfile(sys.executable, copied); copied.chmod(0o755)
        c = json.loads(self.config.read_text()); c['python'] = ref(copied); self.config.write_text(json.dumps(c)); self.config_sha = sha(self.config)
        with copied.open('ab') as f: f.write(b'tampered')
        self.assertNotEqual(self.call().returncode, 0); self.assertFalse(self.state.exists())

    def test_service_kill_recover(self):
        self.call(); a = self.attempt(); ident = json.loads((a / 'service.json').read_text())['identity']; os.kill(ident['pid'], signal.SIGKILL)
        b = self.attempt(2); self.assertEqual(json.loads((a / 'terminal.json').read_text())['exit_code'], -signal.SIGKILL)
        self.assertNotEqual(json.loads((b / 'service.json').read_text())['identity'], ident)

    def test_supervisor_kill_clean_relaunch(self):
        self.call(); a = self.attempt(); old = json.loads((a / 'service.json').read_text())['identity']
        monitors = []
        for p in Path('/proc').iterdir():
            if p.name.isdecimal():
                try:
                    args = (p / 'cmdline').read_bytes().split(b'\0')
                    if b'monitor' in args and str(self.config).encode() in args: monitors.append(int(p.name))
                except OSError: pass
        self.assertEqual(len(monitors), 1); os.kill(monitors[0], signal.SIGKILL)
        time.sleep(.2)
        heartbeat = (self.state / 'heartbeat.json')
        before = json.loads(heartbeat.read_text())['utc_seconds']
        result = subprocess.run([str(self.state / 'relaunch.sh')], cwd='/', env={'PATH':'/usr/bin:/bin'}, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.wait(lambda: json.loads(heartbeat.read_text())['utc_seconds'] > before)
        self.assertTrue(S.matches(old)); self.assertFalse((self.state / 'attempts/2').exists())
        os.kill(old['pid'], signal.SIGKILL); self.attempt(2)
        self.service.write_text('{"mode":"tampered"}')
        result = subprocess.run([str(self.state / 'relaunch.sh')], cwd='/', env={'PATH':'/usr/bin:/bin'}, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)

    def test_simultaneous_start(self):
        argv = [sys.executable, '-B', '-P', str(SUP), 'start', '--config', str(self.config), '--sha256', self.config_sha]
        ps = [subprocess.Popen(argv) for _ in range(8)]
        self.assertTrue(all(p.wait(timeout=5) == 0 for p in ps)); self.attempt(); time.sleep(.5)
        self.assertEqual([p.name for p in (self.state / 'attempts').iterdir()], ['1'])

    def test_failure_budget_survives_relaunch(self):
        self.service.write_text('{"mode":"fail"}'); self.write_config()
        self.assertEqual(self.call().returncode, 0)
        self.wait(lambda: (self.state / 'attempts/2/terminal.json').exists())
        self.assertEqual(self.call().returncode, 0)
        status = self.wait(lambda: (lambda x: x if x['state'] == 'exhausted' else None)(json.loads((self.state / 'status.json').read_text())))
        self.assertEqual(status['retries_used'], 2)
        self.assertEqual(len(list((self.state / 'attempts').iterdir())), 3)
        times = [json.loads((self.state / 'attempts' / str(i) / 'terminal.json').read_text())['time'] for i in (1, 2, 3)]
        self.assertTrue(all(b - a >= 1 for a, b in zip(times, times[1:])))
        self.assertEqual(self.call().returncode, 0)
        time.sleep(.3)
        self.assertEqual(len(list((self.state / 'attempts').iterdir())), 3)

    def test_changed_source_blocks_retry(self):
        self.call(); a = self.attempt()
        self.service.write_text('{"mode":"changed"}')
        os.kill(json.loads((a / 'service.json').read_text())['identity']['pid'], signal.SIGKILL)
        status = self.wait(lambda: (lambda x: x if x['state'] == 'blocked' else None)(json.loads((self.state / 'status.json').read_text())))
        self.assertIn('pin mismatch', status['error'])
        self.assertFalse((self.state / 'attempts/2').exists())

    def test_retry_budget_after_monitor_kill(self):
        self.service.write_text('{"mode":"fail"}'); self.write_config()
        c = json.loads(self.config.read_text()); c['retry_backoff_seconds'] = 2; c['max_retries'] = 1
        self.config.write_text(json.dumps(c)); self.config_sha = sha(self.config)
        self.call(); self.wait(lambda: (self.state / 'attempts/1/terminal.json').exists())
        for p in Path('/proc').iterdir():
            if p.name.isdecimal():
                try:
                    args = (p / 'cmdline').read_bytes().split(b'\0')
                    if b'monitor' in args and str(self.config).encode() in args: os.kill(int(p.name), signal.SIGKILL)
                except OSError: pass
        result = subprocess.run([str(self.state / 'relaunch.sh')], cwd='/', env={'PATH':'/usr/bin:/bin'}, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.wait(lambda: json.loads((self.state / 'status.json').read_text())['state'] == 'exhausted')
        self.assertEqual(len(list((self.state / 'attempts').iterdir())), 2)

    def test_idle_wait_does_not_rehash(self):
        self.state.mkdir(); attempts = self.state / 'attempts'; attempts.mkdir(); a = attempts / '1'; a.mkdir()
        runlock = (a / 'runner.lock').open('a'); S.fcntl.flock(runlock, S.fcntl.LOCK_EX)
        owner = (self.state / 'owner.lock').open('a')
        original = S.load
        try:
            with mock.patch.object(S, 'load', wraps=original) as loads, mock.patch.object(S, 'atomic', wraps=S.atomic) as writes, mock.patch.object(S.select, 'select', side_effect=KeyboardInterrupt) as waiting:
                with self.assertRaises(KeyboardInterrupt): S.monitor(str(self.config), self.config_sha, os.dup(owner.fileno()))
            self.assertEqual(loads.call_count, 1)
            self.assertEqual(writes.call_count, 1)
            self.assertGreater(waiting.call_args.args[3], 9)
        finally:
            runlock.close(); owner.close()

    def test_delayed_runner_exit_is_reaped(self):
        import fcntl
        self.state.mkdir()
        runner = self.root / 'delay.py'
        runner.write_text("import sys,time\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nimport unified_service_supervisor_v1 as S\no=S.atomic\ndef delayed(p,v):\n o(p,v)\n if Path(p).name=='terminal.json':time.sleep(.7)\nS.atomic=delayed\nS.runner(sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5]))\n")
        wrapper = self.root / 'monitor.py'
        wrapper.write_text("import sys,subprocess\nsys.path.insert(0,sys.argv[1])\nimport unified_service_supervisor_v1 as S\no=S.subprocess.Popen\ndef launch(argv,**kw):\n if 'runner' in argv: argv=[sys.executable,'-B','-P'," + repr(str(runner)) + ",sys.argv[1],sys.argv[2],sys.argv[3],argv[argv.index('--attempt')+1],argv[-1]]\n return o(argv,**kw)\nS.subprocess.Popen=launch\nS.monitor(sys.argv[2],sys.argv[3],int(sys.argv[4]))\n")
        lock = (self.state / 'owner.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX)
        proc = subprocess.Popen([sys.executable, '-B', '-P', str(wrapper), str(HERE), str(self.config), self.config_sha, str(lock.fileno())], pass_fds=(lock.fileno(),))
        lock.close()
        try:
            a = self.attempt(); rid = json.loads((a / 'runner.json').read_text())['pid']
            os.kill(json.loads((a / 'service.json').read_text())['identity']['pid'], signal.SIGKILL)
            self.wait(lambda: (a / 'terminal.json').exists())
            self.assertFalse((self.state / 'attempts/2').exists())
            self.attempt(2)
            self.wait(lambda: not Path('/proc/%d' % rid).exists())
            self.assertIsNone(proc.poll())
        finally:
            proc.kill(); proc.wait()

    def test_config_bounds(self):
        for key, value in [('heartbeat_seconds', 9), ('heartbeat_seconds', True), ('max_retries', -1), ('retry_backoff_seconds', 0)]:
            self.write_config(); c = json.loads(self.config.read_text()); c[key] = value
            self.config.write_text(json.dumps(c)); self.config_sha = sha(self.config)
            self.assertNotEqual(self.call().returncode, 0)
        self.assertFalse(self.state.exists())

    def test_pid_reuse_negative(self):
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
        try:
            ident = S.identity(proc.pid); ident['starttime'] = str(int(ident['starttime']) + 1)
            self.assertFalse(S.terminate_matching(ident)); self.assertIsNone(proc.poll())
        finally: proc.terminate(); proc.wait()

    def test_unconfirmed_fails_closed(self):
        self.call(); a = self.attempt(); runner = json.loads((a / 'runner.json').read_text()); os.kill(runner['pid'], signal.SIGKILL)
        self.wait(lambda: json.loads((self.state / 'status.json').read_text())['state'] == 'unconfirmed')
        self.assertFalse((self.state / 'attempts/2').exists())


if __name__ == '__main__':
    if '--fake-service' in sys.argv: fake()
    else: unittest.main(verbosity=2)
