"""Synthetic test-run reservations; never creates a real FINAL or test ticket."""
import importlib.util
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest

spec=importlib.util.spec_from_file_location('guard',Path(__file__).with_name('r3_test_execution_guard.py'))
G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)


def child_claim(root,kwargs,connection):
    try:
        with G.execution(root,**kwargs):connection.send('entered')
    except ValueError as error:connection.send(str(error))
    finally:connection.close()


def child_hold(root,kwargs,connection):
    with G.execution(root,**kwargs):
        connection.send('reserved');connection.close()
        while True:time.sleep(1)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.kw=dict(model_sha256='a'*64,suite='decision-v7',run_dir=str(self.root/'run'),
                     execution_sha256='b'*64,final_sha256='c'*64)

    def test_other_process_cannot_acquire_active_test_even_same_owner(self):
        # fork child closes inherited lock FDs through normal process teardown;
        # its new independent flock must still conflict with parent's held lock.
        ctx=multiprocessing.get_context('fork');receiver,sender=ctx.Pipe(duplex=False)
        with G.execution(self.root,**self.kw):
            p=ctx.Process(target=child_claim,args=(self.root,self.kw,sender));p.start();sender.close()
            self.assertTrue(receiver.poll(5));self.assertIn('already active',receiver.recv());p.join(5)
            self.assertEqual(p.exitcode,0)
        receiver.close()

    def test_interruption_resumes_only_same_pinned_execution(self):
        with self.assertRaises(RuntimeError):
            with G.execution(self.root,**self.kw):raise RuntimeError('simulated interruption')
        for key,value in [('run_dir',str(self.root/'new')),('execution_sha256','d'*64),('final_sha256','e'*64)]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'another execution'):
                with G.execution(self.root,**dict(self.kw,**{key:value})):pass
        with G.execution(self.root,**self.kw) as lease:lease.complete('f'*64)
        with self.assertRaisesRegex(ValueError,'completed'):
            with G.execution(self.root,**self.kw):pass

    def test_process_death_retains_owner_but_releases_execution_lock(self):
        ctx=multiprocessing.get_context('fork');receiver,sender=ctx.Pipe(duplex=False)
        p=ctx.Process(target=child_hold,args=(self.root,self.kw,sender));p.start();sender.close()
        try:
            self.assertTrue(receiver.poll(5));self.assertEqual(receiver.recv(),'reserved')
        finally:
            p.kill();p.join(5);receiver.close()
        with self.assertRaisesRegex(ValueError,'another execution'):
            with G.execution(self.root,**dict(self.kw,execution_sha256='d'*64)):pass
        with G.execution(self.root,**self.kw) as lease:lease.complete('f'*64)

    def test_completed_ticket_cannot_be_reused_with_another_owner(self):
        with G.execution(self.root,**self.kw) as lease:lease.complete('f'*64)
        with self.assertRaises(ValueError):
            with G.execution(self.root,**dict(self.kw,run_dir=str(self.root/'other'))):pass

    def test_completion_outside_lock_and_invalid_digest_refused(self):
        with G.execution(self.root,**self.kw) as lease:
            with self.assertRaises(ValueError):lease.complete('invalid')
        with self.assertRaisesRegex(ValueError,'not held'):lease.complete('f'*64)

    def test_model_and_suite_have_distinct_reservations(self):
        with G.execution(self.root,**self.kw):
            with G.execution(self.root,**dict(self.kw,suite='transfer-v4')):pass
            with G.execution(self.root,**dict(self.kw,model_sha256='d'*64)):pass

    def test_symlink_reservation_directory_refused(self):
        target=self.root/'elsewhere';target.mkdir()
        (self.root/'test-execution-reservations').symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):
            with G.execution(self.root,**self.kw):pass


if __name__=='__main__':unittest.main()
