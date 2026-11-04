"""Actual subprocess checks for readiness before delivering SIGUSR1."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tools import experiment_event_relay_v2 as R


class ReadyHandshake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def wait_for(self, predicate):
        until = time.monotonic()+5
        while not predicate():
            self.assertLess(time.monotonic(), until)
            time.sleep(.01)

    def child(self, publish=True):
        source = self.root/'child.py'
        source.write_text('''import json,os,pathlib,signal,time
r=pathlib.Path(__file__).parent
def ident():
 f=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
 return dict(pid=os.getpid(),boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=f[19],argv=[v.decode() for v in pathlib.Path('/proc/self/cmdline').read_bytes().split(b'\\0') if v])
(r/'START.json').write_text(json.dumps(dict(process=ident())))
while not (r/'INSTALL').exists():time.sleep(.01)
def wake(*_):
 with (r/'received').open('a') as f:f.write('wake\\n')
signal.signal(signal.SIGUSR1,wake)
if '''+repr(publish)+''':
 (r/'SERVICE.json').write_text(json.dumps(dict(process=ident(),signals=dict(wake='SIGUSR1'))))
else:
 try:raise OSError('injected ready publication failure')
 except OSError:pass
(r/'INSTALLED').touch()
while True:time.sleep(.02)
''')
        p = subprocess.Popen([sys.executable, '-B', '-P', str(source)])
        def cleanup():
            if p.poll() is None:
                p.terminate()
            p.wait(timeout=5)
        self.addCleanup(cleanup)
        self.wait_for(lambda: (self.root/'START.json').exists())
        self.wait_for(lambda: (self.root/'START.json').stat().st_size > 0)
        return p

    def target(self, filename='SERVICE.json'):
        p = self.root/filename
        d = json.loads(p.read_text())
        return dict(identity=d['process'], service=dict(path=str(p), sha256=R.V.sha(p)))

    def ready(self, p):
        (self.root/'INSTALL').touch()
        self.wait_for(lambda: (self.root/'INSTALLED').exists())
        self.assertIsNone(p.poll())
        return self.target()

    def test_live_launcher_receipt_before_handler_is_refused(self):
        p = self.child()
        with self.assertRaisesRegex(ValueError, 'handshake absent'):
            R.wake(self.target('START.json'))
        self.assertIsNone(p.poll())
        self.assertFalse((self.root/'received').exists())

    def test_forged_ready_before_kernel_handler_is_refused(self):
        p = self.child()
        d = json.loads((self.root/'START.json').read_text())
        d['signals'] = dict(wake='SIGUSR1')
        (self.root/'SERVICE.json').write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError, 'handler not installed'):
            R.wake(self.target())
        self.assertIsNone(p.poll())

    def test_ready_handler_receives_signal(self):
        p = self.child(); t = self.ready(p)
        R.wake(t)
        self.wait_for(lambda: (self.root/'received').exists())
        self.assertEqual((self.root/'received').read_text(), 'wake\n')
        self.assertIsNone(p.poll())

    def test_stale_identity_is_refused_even_with_handshake(self):
        p = self.child(); t = self.ready(p)
        t['identity']['start_ticks'] = str(int(t['identity']['start_ticks'])+1)
        d = json.loads((self.root/'SERVICE.json').read_text())
        d['process'] = t['identity']
        (self.root/'SERVICE.json').write_text(json.dumps(d)); t = self.target()
        with self.assertRaisesRegex(ValueError, 'stale process identity'):
            R.wake(t)
        self.assertIsNone(p.poll())

    def test_changed_ready_receipt_refused(self):
        p = self.child(); t = self.ready(p)
        (self.root/'SERVICE.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'receipt changed'):
            R.wake(t)
        self.assertIsNone(p.poll())

    def test_ready_publication_failure_never_promotes_launcher(self):
        p = self.child(publish=False)
        (self.root/'INSTALL').touch()
        self.wait_for(lambda: (self.root/'INSTALLED').exists())
        R.kernel_handler_present(p.pid)
        with self.assertRaisesRegex(ValueError, 'handshake absent'):
            R.wake(self.target('START.json'))
        self.assertIsNone(p.poll())

    def test_durable_intent_failure_happens_before_signal(self):
        p = self.child(); t = self.ready(p)
        plan = self.root/'PLAN.json'
        plan.write_text(json.dumps(dict(run='test/run',chip=0)))
        trigger = self.root/'RELEASE.json'
        trigger.write_text(json.dumps(dict(schema='r3-resource-release-v1',run='test/run',chip=0,exit_code=0,scientific_acceptance=False)))
        c = dict(events=[dict(id='release',kind='release',plan=str(plan),trigger=str(trigger),run='test/run',target=t)])
        def fail(_):raise OSError('intent persistence failed')
        with self.assertRaises(OSError):R.tick(c,dict(events={}),fail)
        self.assertFalse((self.root/'received').exists())
        self.assertIsNone(p.poll())

    def test_ignored_signal_is_not_caught_signal(self):
        p = self.child(); t = self.ready(p)
        # Readiness must use SigCgt rather than SigIgn/SigPnd. A synthetic
        # status text isolates this exact parser decision after real startup.
        with mock.patch.object(Path, 'read_text', return_value='SigIgn:\t0000000000000200\nSigCgt:\t0000000000000000\n'):
            with self.assertRaisesRegex(ValueError, 'handler not installed'):
                R.kernel_handler_present(p.pid)
        self.assertIsNone(p.poll())

    def test_actual_prepare_queue_service_is_ready_after_handler(self):
        repo = Path(__file__).resolve().parents[1]
        root = self.root/'queue'; root.mkdir()
        config = self.root/'CONFIG.json'
        config.write_text(json.dumps(dict(output=str(root), poll_seconds=600)))
        source = self.root/'queue_fixture.py'
        source.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(repo))+')\n'
                          'from tools import bev_successor_prepare_queue_v3 as Q\n'
                          'Q.validate=lambda c:c\n'
                          'def once(c):\n'
                          ' p=Path(c["output"])/"PASSES"\n'
                          ' with p.open("a") as f:f.write("pass\\n")\n'
                          ' return [dict(state="prepared_pending_review" if (p.parent/"FINISH").exists() else "waiting")]\n'
                          'Q.once=once\n'
                          'Q.run('+repr(str(config))+','+repr(R.V.sha(config))+')\n')
        p = subprocess.Popen([sys.executable,'-B','-P',str(source)])
        def cleanup():
            if p.poll() is None:p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill();p.wait(timeout=5)
        self.addCleanup(cleanup)
        self.wait_for(lambda: (root/'SERVICE.json').exists())
        receipt = R.V.read(root/'SERVICE.json')
        target = dict(identity=receipt['process'],service=dict(path=str(root/'SERVICE.json'),sha256=R.V.sha(root/'SERVICE.json')))
        self.wait_for(lambda: (root/'PASSES').exists())
        R.wake(target)
        self.wait_for(lambda: len((root/'PASSES').read_text().splitlines()) >= 2)
        self.assertIsNone(p.poll())
        (root/'FINISH').touch()
        R.wake(target);p.wait(timeout=5)
        self.assertEqual(R.V.read(root/'QUEUE-EXIT.json')['exit_code'],0)


if __name__ == '__main__':unittest.main()
