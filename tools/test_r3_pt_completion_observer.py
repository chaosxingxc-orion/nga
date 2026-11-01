#!/usr/bin/env python3
"""Offline fixtures only. Actual v3 dependency and send_signal; no numerical PASS.

Reuses pinned producer fixture construction, which redirects only request() to a
private root. Process inspection is mocked for observer state-machine cases;
/proc self-inspection and inotify tests use real local kernel APIs. Authorization
fixtures are never written to the production generation. No producer is started.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).absolute().parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('observer', HERE/'r3_pt_completion_observer.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
TEST_PIN = '80a94dc5f334f20c9925de58b95c23a4c0052b252fc4935cafc06ee6c08c2387'
fixture_path = o.GEN/'test_r3_pt_formal_prepare_successor.py'
raw = o.checked({'path': str(fixture_path), 'sha256': TEST_PIN})
f = type(sys)('frozen_observer_fixture')
f.__file__ = str(fixture_path)
exec(compile(raw, str(fixture_path), 'exec'), f.__dict__)


class ObserverCases(unittest.TestCase):
    def setUp(self):
        self.fixture = f.RepairSignal()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.m, self.r, self.q = f.m, self.fixture.r, self.fixture.q
        self.root = self.fixture.root/'observer'
        self.root.mkdir()
        self.paths = [self.q['producer']['terminal'], self.q['producer']['job']['output'],
                      str(Path(self.r['queue']['path']).parent/'EXIT.json'),
                      str(Path(self.r['queue']['path']).parent/'VALIDATION.json'), self.q['output']]
        owners = {'report': {'pid': 111, 'start_ticks': '100'}, 'precheck': {'pid': 222, 'start_ticks': '200'}}
        self.a = {'owners': owners, 'observer': o.reference(Path(o.__file__).absolute())}
        self.auth_ref = o.durable(self.fixture.root/'root-authorization.fixture.json', self.a)
        self.config = {'state_directory': str(self.root), 'artifact_paths': self.paths,
                       'request': {'path': str(self.fixture.root/'fixture-request.json'), 'sha256': 'a'*64},
                       'worker': {'path': str(o.GEN/'r3_pt_formal_prepare_successor.py'), 'sha256': o.WORKER_PIN},
                       'bindings': {'queue': self.r['queue'], 'precheck_service': self.r['precheck_service'],
                                    'precheck_activation': self.r['precheck_activation'],
                                    'report_queue': {'path': self.q['producer']['queue'], 'sha256': self.q['producer']['queue_sha256']},
                                    'report_controller': o.reference(self.fixture.root/'fixture_controller.py'),
                                    'precheck_worker': {'path': self.q['worker'], 'sha256': self.q['worker_sha256']}}}
        self.config_ref = o.durable(self.fixture.root/'config.fixture.json', self.config)
        self.processes = {x['pid']: copy.deepcopy(x) for x in owners.values()}
        self.proc = patch.object(o, 'process_identity', side_effect=self.inspect)
        self.proc.start()
        self.addCleanup(self.proc.stop)
        self.observer = self.new_observer()

    def inspect(self, pid):
        if pid not in self.processes:
            raise FileNotFoundError('fixture owner absent')
        return self.processes[pid]

    def new_observer(self):
        return o.Observer(self.config, self.r, self.q, self.a, self.auth_ref, self.config_ref, self.m)

    def assert_block(self):
        with self.assertRaises((ValueError, KeyError, OSError, TypeError)):
            self.observer.step()
        self.assertFalse((self.fixture.root/'SIGNAL.json').exists())

    def rewrite(self, path, change):
        value = json.loads(Path(path).read_bytes())
        change(value)
        Path(path).write_bytes(o.canonical(value))

    def relink(self):
        validation = Path(self.paths[3]); end = Path(self.paths[2])
        self.rewrite(validation, lambda x: x.update(output_sha256=o.digest(Path(self.paths[4]).read_bytes())))
        self.rewrite(end, lambda x: x.update(validation_sha256=o.digest(validation.read_bytes()),
                                           output_sha256=o.digest(Path(self.paths[4]).read_bytes())))

    def test_actual_signal_duplicate_and_restart(self):
        self.assertEqual(self.observer.step(), 'SIGNALLED')
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.processes.clear()  # Durable ownership permits exact retries, not new ownership.
        self.assertEqual(self.new_observer().step(), 'SIGNALLED')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        auth = o.document(o.reference(self.root/'AUTHENTICATION.json'))
        self.assertEqual(set(auth['artifacts']), set(self.paths))
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)):
            self.m.dependency(self.r, o.reference(self.root/'AUTHENTICATION.json'))

    def test_disappeared_owner_with_all_valid_artifacts_blocks(self):
        del self.processes[111]
        self.assert_block()
        self.assertFalse((self.root/'AUTHENTICATION.json').exists())

    def test_pid_reuse_before_start(self):
        self.processes[222]['start_ticks'] = '201'
        self.assert_block()

    def test_pid_reuse_between_observation_fences(self):
        original = o.stable
        def reuse(paths, seconds=0.05):
            result = original(paths, 0)
            self.processes[111]['start_ticks'] = '999'
            return result
        with patch.object(o, 'stable', side_effect=reuse):
            self.assert_block()
        self.assertFalse((self.root/'OWNER_report.json').exists())

    def test_restart_without_durable_ownership_blocks(self):
        self.observer.restore()
        self.processes.clear()
        self.assert_block()

    def test_wait_is_not_authentication(self):
        Path(self.paths[2]).unlink()
        self.assertEqual(self.observer.step(), 'WAIT_GENUINE_COMPLETION')
        self.assertFalse((self.root/'AUTHENTICATION.json').exists())
        del self.processes[222]
        self.assert_block()

    def test_failed_or_boolean_report_terminals(self):
        for code in [False, True, 1, '0', None]:
            with self.subTest(code=code):
                self.rewrite(self.paths[0], lambda x: x.update(exit_code=code))
                self.assert_block()

    def test_failed_or_boolean_precheck_terminal(self):
        for code in [False, True, 1, '0', None]:
            with self.subTest(code=code):
                self.rewrite(self.paths[2], lambda x: x.update(exit_code=code))
                self.assert_block()

    def test_wrong_queue_rehashed(self):
        self.rewrite(self.paths[2], lambda x: x.update(queue_sha256='e'*64))
        self.assert_block()

    def test_full_consumed_linkage_rehashed(self):
        self.rewrite(self.paths[3], lambda x: x['consumed'].update(report_sha256='e'*64))
        self.relink()
        self.assert_block()
        self.assertFalse((self.root/'AUTHENTICATION.json').exists())

    def test_bundle_wrong_model_rehashed(self):
        self.rewrite(self.paths[4], lambda x: x.update(model='/fixture/wrong'))
        self.relink()
        self.assert_block()

    def test_report_wrong_partition_rehashed(self):
        self.rewrite(self.paths[1], lambda x: x['header'].update(partitions=['test']))
        self.rewrite(self.paths[0], lambda x: x.update(output_sha256=o.digest(Path(self.paths[1]).read_bytes())))
        self.assert_block()

    def test_missing_validation_blocks(self):
        Path(self.paths[3]).unlink()
        self.assert_block()

    def test_partial_terminal_blocks(self):
        Path(self.paths[2]).write_bytes(b'{')
        self.assert_block()

    def test_partial_observer_files_never_overwritten(self):
        for name in ['STARTED.json', 'OWNER_report.json', 'PROVENANCE.json', 'AUTHENTICATION.json', 'SIGNALLED.json']:
            with self.subTest(name=name):
                p = self.root/name
                p.write_bytes(b'{')
                self.assert_block()
                self.assertEqual(p.read_bytes(), b'{')
                p.unlink()  # fixture reset only; never operational repair.

    def test_partial_producer_signal_preserved(self):
        p = self.fixture.root/'SIGNAL.json'; p.write_bytes(b'{')
        with self.assertRaises(ValueError):
            self.observer.step()
        self.assertEqual(p.read_bytes(), b'{')
        self.assertFalse((self.root/'SIGNALLED.json').exists())

    def test_conflicting_valid_authentication_identity_preserved(self):
        self.fixture.send()
        before = (self.fixture.root/'SIGNAL.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'no overwrite'):
            self.observer.step()
        self.assertEqual((self.fixture.root/'SIGNAL.json').read_bytes(), before)

    def test_owned_artifact_mutation_blocks(self):
        self.observer.restore(); self.observer.owner('report')
        self.rewrite(self.paths[1], lambda x: x.update(mutation=True))
        self.assert_block()

    def test_mutation_at_final_signal_admission_blocks(self):
        original = self.m.send_signal
        def mutate(*args):
            self.rewrite(self.paths[3], lambda x: x.update(mutation=True))
            return original(*args)
        with patch.object(self.m, 'send_signal', side_effect=mutate):
            self.assert_block()
        self.assertFalse((self.root/'SIGNALLED.json').exists())

    def test_auth_receipt_mutation_before_signal_blocks(self):
        original = self.m.send_signal
        def mutate(*args):
            (self.root/'AUTHENTICATION.json').write_bytes(b'{}')
            return original(*args)
        with patch.object(self.m, 'send_signal', side_effect=mutate):
            self.assert_block()

    def test_rehashed_activation_wrong_service_blocks_actual_linkage(self):
        self.rewrite(self.r['precheck_activation']['path'], lambda x: x['service'].update(pid=999))
        self.r['precheck_activation'] = o.reference(self.r['precheck_activation']['path'])
        self.config['bindings']['precheck_activation'] = self.r['precheck_activation']
        Path(self.config_ref['path']).write_bytes(o.canonical(self.config))
        self.config_ref = o.reference(self.config_ref['path'])
        self.observer = self.new_observer()
        self.assert_block()
        self.assertFalse((self.root/'AUTHENTICATION.json').exists())

    def test_partial_write_failure_leaves_evidence(self):
        original = o.os.fsync
        def fail_file(fd):
            if Path('/proc/self/fd/' + str(fd)).resolve().name == 'AUTHENTICATION.json':
                raise OSError('fixture interrupted fsync')
            return original(fd)
        with patch.object(o.os, 'fsync', side_effect=fail_file), self.assertRaises(OSError):
            self.observer.step()
        self.assertTrue((self.root/'AUTHENTICATION.json').exists())
        self.assertFalse((self.fixture.root/'SIGNAL.json').exists())
        # Complete identical bytes are durably resynced on retry; incomplete bytes block.
        self.assertEqual(self.new_observer().step(), 'SIGNALLED')

    def test_activation_mutation_blocks(self):
        Path(self.r['precheck_activation']['path']).write_bytes(b'{}')
        self.assert_block()

    def test_owner_receipt_wrong_identity_blocks(self):
        self.observer.restore(); self.observer.owner('report')
        self.rewrite(self.root/'OWNER_report.json', lambda x: x['owner'].update(pid=999))
        self.assert_block()

    def test_root_authorization_mutation_blocks(self):
        Path(self.auth_ref['path']).write_bytes(b'{}')
        self.assert_block()

    def test_interrupted_after_provenance_is_retryable_with_owned_bytes(self):
        original = o.durable
        def interrupt(path, value):
            if Path(path).name == 'AUTHENTICATION.json':
                raise OSError('fixture crash before auth create')
            return original(path, value)
        with patch.object(o, 'durable', side_effect=interrupt), self.assertRaises(OSError):
            self.observer.step()
        self.processes.clear()
        self.assertEqual(self.new_observer().step(), 'SIGNALLED')

    def test_unknown_partial_file_requires_repair(self):
        (self.root/'auth.tmp').write_bytes(b'{')
        self.assert_block()


class KernelAndPrimitiveCases(unittest.TestCase):
    def test_actual_proc_identity_and_wrong_environment(self):
        expected = o.process_identity(os.getpid())
        self.assertEqual(o.live_identity(expected), expected)
        expected['environment_sha256'] = 'f'*64
        with self.assertRaises(o.Block):
            o.live_identity(expected)

    def test_actual_inotify_and_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'terminal.json'
            events = o.Events([str(p)])
            try:
                self.assertFalse(events.wait(0.001))
                p.write_text('{}')
                self.assertTrue(events.wait(0.1))
            finally:
                events.close()
        self.assertEqual(o.FALLBACK_SECONDS, 600)

    def test_stable_read_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'x'; p.write_bytes(b'1')
            with patch.object(o.time, 'sleep', side_effect=lambda _: p.write_bytes(b'2')):
                with self.assertRaisesRegex(o.Block, 'mutated'):
                    o.stable([p])

    def test_no_clobber_and_durable_order(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'receipt.json'
            calls = []
            original = o.os.fsync
            with patch.object(o.os, 'fsync', side_effect=lambda fd: (calls.append(fd), original(fd))[-1]):
                first = o.durable(p, {'value': 1})
            self.assertGreaterEqual(len(calls), 2)
            self.assertEqual(o.durable(p, {'value': 1}), first)
            with self.assertRaises(o.Block):
                o.durable(p, {'value': 2})
            p.write_bytes(b'{')
            with self.assertRaises(o.Block):
                o.durable(p, {'value': 1})
            self.assertEqual(p.read_bytes(), b'{')

    def test_symlinks_nonregular_and_nonconcrete_pins_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'file'; p.write_bytes(b'1')
            link = Path(d)/'link'; link.symlink_to(p)
            fifo = Path(d)/'fifo'; os.mkfifo(fifo)
            for target in [link, fifo]:
                with self.assertRaises(o.Block): o.read(target)
            for h in [None, 'PENDING', 'A'*64, 0]:
                with self.assertRaises(o.Block): o.checked({'path': str(p), 'sha256': h})

    def test_exclusive_observer_lock(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'observer.lock'
            with o.exclusive(path):
                with self.assertRaises(BlockingIOError):
                    with o.exclusive(path):
                        self.fail('duplicate observer acquired lock')
            with o.exclusive(path):
                pass

    def test_runtime_inventory_membership_and_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'runtime'; root.mkdir()
            p = root/'python'; p.write_bytes(b'fixture interpreter, never executed')
            inv = o.durable(Path(d)/'inventory.json', {'schema': 'pt-observer-runtime-inventory-v1',
                         'roots': [str(root)], 'files': {str(p): o.digest(p.read_bytes())}, 'symlinks': {}})
            o.runtime_inventory(inv)
            (root/'extra.py').write_bytes(b'')
            with self.assertRaisesRegex(o.Block, 'membership'): o.runtime_inventory(inv)
            (root/'extra.py').unlink(); p.write_bytes(b'changed')
            with self.assertRaisesRegex(o.Block, 'pin differs'): o.runtime_inventory(inv)


class AuthorizationCases(unittest.TestCase):
    """Real config/receipt checks; kernel UID/runtime are injected only here.

    A positive authorization fixture tests schema plumbing, never genuine root
    authorization. Its authority fields all point to explicitly synthetic files.
    """
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.authority = root/'authority'; self.authority.mkdir(mode=0o700)
        self.state = root/'state'; self.state.mkdir(mode=0o755)
        config_path = HERE/'CONFIG.json'
        if not config_path.exists():
            config_path = HERE.parent/'.local/preparations/pt-completion-observer-20261101-v2/CONFIG.json'
        self.config = json.loads(config_path.read_bytes())
        self.config['state_directory'] = str(self.state)
        self.config_ref = o.durable(root/'config.json', self.config)
        self.c, self.r, self.q = o.load_config(self.config_ref)
        pre = o.document(self.r['precheck_service'])
        report_ref = o.reference(Path(self.q['producer']['queue']).parent/'SERVICE.json')
        report = o.document(report_ref)
        dummy = o.durable(root/'FIXTURE_ONLY.json', {'fixture': True})
        exe = str(Path(self.r['python']).resolve())
        self.a = {'schema':'pt-completion-observer-root-authorization-v1', 'authorized':True,
                  'observer':o.reference(Path(o.__file__).absolute()),'config':self.config_ref,
                  'observer_uid':os.geteuid(), 'scientific_acceptance':False,'training_authorized':False,
                  'producer_review':o.reference(Path('/home/xingchao/workspace/nga/.local/reports/pt-v3-independent-review.json')),
                  'producer_parent_decision':o.reference(Path('/home/xingchao/workspace/nga/.local/reports/pt-v3-review-parent-decision.json')),
                  'report_service':report_ref,
                  'owners':{role:{'pid':v['pid'],'command':v['command'],
                                  'start_ticks':v.get('start_ticks','209801794'),
                                  'uid':os.geteuid()+1,'exe':o.reference(exe)}
                            for role,v in [('report',report),('precheck',pre)]},
                  'runtime_inventories':{role:dummy for role in ['observer','report','precheck']},
                  'observer_runtime':{'executable':exe,'environment_sha256':o.digest(Path('/proc/self/environ').read_bytes()),
                                      'cwd':str(Path.cwd()),'command':[os.fsdecode(x) for x in Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')]}}
        for name in ['source_review','publication','producer_deployment','upstream_launch_evidence','member_launch_evidence']:
            self.a[name]=dummy
        self.exe=exe

    def auth(self):
        path=self.authority/'auth.json'
        path.write_bytes(o.canonical(self.a))
        with patch.object(o.sys,'executable',self.exe), patch.dict(o.os.environ,self.r['runtime_environment']), patch.object(o,'runtime_inventory',return_value={'files':{self.exe:'fixture'}}):
            return o.authenticate(self.config_ref,o.reference(path))

    def test_schema_positive_fixture_only(self):
        self.assertEqual(self.auth()[3],self.a)

    def test_no_authorization(self):
        self.a['authorized']=False
        with self.assertRaisesRegex(o.Block,'authorization differs'):self.auth()

    def test_same_writer_as_producer(self):
        self.a['owners']['precheck']['uid']=os.geteuid()
        with self.assertRaisesRegex(o.Block,'separate owner'):self.auth()

    def test_wrong_start_ticks(self):
        self.a['owners']['precheck']['start_ticks']='9'
        with self.assertRaisesRegex(o.Block,'start ticks'):self.auth()

    def test_wrong_report_command(self):
        self.a['owners']['report']['command']=['wrong']
        with self.assertRaises(o.Block):self.auth()

    def test_wrong_observer_environment(self):
        self.a['observer_runtime']['environment_sha256']='e'*64
        with self.assertRaisesRegex(o.Block,'environment differs'):self.auth()

    def test_nonprivate_root_authority(self):
        self.authority.chmod(0o755)
        with self.assertRaisesRegex(o.Block,'directory owner/mode'):self.auth()

    def test_wrong_v3_pin(self):
        self.config['request']['sha256']='f'*64
        path=Path(self.config_ref['path']);path.write_bytes(o.canonical(self.config))
        with self.assertRaisesRegex(o.Block,'different frozen v3'):o.load_config(o.reference(path))

    def test_wrong_artifact_mapping(self):
        self.config['artifact_paths']=self.config['artifact_paths'][:4]
        path=Path(self.config_ref['path']);path.write_bytes(o.canonical(self.config))
        with self.assertRaisesRegex(o.Block,'five artifact paths'):o.load_config(o.reference(path))


DURABILITY_DETAILS = []


class DurableRestartCases(unittest.TestCase):
    """Actual fork exits and /proc owners; synthetic authority/artifacts only.

    No physical power loss or deployment is claimed. Frozen dependency and signal
    execute unchanged; only request admission is redirected by the base fixture.
    """
    def fixture(self):
        c = ObserverCases()
        c.setUp()
        self.addCleanup(c.doCleanups)
        c.proc.stop()
        kids, owners = {}, {}
        for role in ('report', 'precheck'):
            kid = subprocess.Popen([sys.executable, '-B', '-P', '-c', 'import time; time.sleep(45)'],
                                   env={'LD_LIBRARY_PATH': os.environ.get('LD_LIBRARY_PATH', ''),
                                        'OBSERVER_FIXTURE': 'synthetic-only'},
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
            def stop(kid=kid):
                if kid.poll() is None:
                    kid.terminate()
                kid.wait(timeout=3)
            self.addCleanup(stop)
            for _ in range(100):
                identity = o.process_identity(kid.pid)
                if identity['command'] == kid.args:
                    break
                time.sleep(.005)
            self.assertEqual(identity['command'], kid.args)
            kids[role], owners[role] = kid, identity
        c.a['owners'] = owners
        Path(c.auth_ref['path']).write_bytes(o.canonical(c.a))
        c.auth_ref = o.reference(c.auth_ref['path'])
        c.observer = c.new_observer()
        return c, kids

    def crash(self, target):
        c, kids = self.fixture()
        child = os.fork()
        if child == 0:
            original = o.os.fsync
            def abrupt(fd):
                if Path('/proc/self/fd/' + str(fd)).resolve() == c.root/target:
                    os._exit(77)  # after flush, before the selected file fsync
                return original(fd)
            try:
                with patch.object(o.os, 'fsync', side_effect=abrupt):
                    c.observer.step()
            except BaseException:
                os._exit(79)
            os._exit(78)
        _, status = os.waitpid(child, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 77)
        path = c.root/target
        self.assertEqual(path.read_bytes(), o.canonical(json.loads(path.read_bytes())))
        self.assertFalse((c.root/'BLOCKED.json').exists())
        self.assertFalse((c.fixture.root/'SIGNAL.json').exists())
        if target.startswith('OWNER_'):
            role = target[len('OWNER_'):-len('.json')]
            kids[role].terminate()
            kids[role].wait(timeout=3)
            with self.assertRaises(o.Block):
                o.live_identity(c.a['owners'][role])
        return c, kids

    def retry(self, target, failure=None):
        c, _ = self.crash(target)
        before = {p.name: p.read_bytes() for p in c.root.iterdir()}
        events = []
        original_sync, original_durable = o.os.fsync, o.durable
        original_signal = c.m.send_signal
        target_synced = False
        def sync(fd):
            nonlocal target_synced
            path = Path('/proc/self/fd/' + str(fd)).resolve()
            if failure == 'file' and path == c.root/target:
                events.append(['failed_file', target])
                raise OSError('injected reused record file fsync failure')
            if failure == 'directory' and path == c.root and target_synced:
                events.append(['failed_directory', str(path)])
                raise OSError('injected reused record directory fsync failure')
            result = original_sync(fd)
            events.append(['fsync', str(path)])
            if path == c.root/target:
                target_synced = True
            return result
        def publication(path, value):
            if Path(path).name in ('PROVENANCE.json', 'AUTHENTICATION.json', 'SIGNALLED.json'):
                events.append(['publish', Path(path).name])
            return original_durable(path, value)
        def signal(*args):
            events.append(['signal', 'actual_frozen_send_signal'])
            return original_signal(*args)
        with patch.object(o.os, 'fsync', side_effect=sync), \
             patch.object(o, 'durable', side_effect=publication), \
             patch.object(c.m, 'send_signal', side_effect=signal):
            if failure:
                with self.assertRaises(OSError):
                    c.new_observer().step()
                self.assertFalse((c.fixture.root/'SIGNAL.json').exists())
                self.assertFalse((c.root/'AUTHENTICATION.json').exists())
                self.assertFalse(any(e[0] in ('publish', 'signal') for e in events))
                result = 'BLOCKED_BY_IO_ERROR'
            else:
                result = c.new_observer().step()
                self.assertEqual(result, 'SIGNALLED')
                for record in ('STARTED.json', 'OWNER_report.json', 'OWNER_precheck.json'):
                    file_index = events.index(['fsync', str(c.root/record)])
                    directory_index = events.index(['fsync', str(c.root)], file_index + 1)
                    publication_index = next(i for i, e in enumerate(events) if e[0] in ('publish', 'signal'))
                    self.assertLess(file_index, directory_index)
                    self.assertLess(directory_index, publication_index)
        for name, raw in before.items():
            self.assertEqual((c.root/name).read_bytes(), raw)
        DURABILITY_DETAILS.append({'target': target, 'crash_exit': 77,
            'owner_exited_before_retry': target.startswith('OWNER_'),
            'retry_failure_injection': failure, 'result': result, 'events': events,
            'retained_bytes_unchanged': True, 'synthetic_only': True})

    def test_report_crash_retry(self): self.retry('OWNER_report.json')
    def test_precheck_crash_retry(self): self.retry('OWNER_precheck.json')
    def test_started_crash_retry(self): self.retry('STARTED.json')
    def test_report_retry_file_failure(self): self.retry('OWNER_report.json', 'file')
    def test_precheck_retry_file_failure(self): self.retry('OWNER_precheck.json', 'file')
    def test_started_retry_file_failure(self): self.retry('STARTED.json', 'file')
    def test_report_retry_directory_failure(self): self.retry('OWNER_report.json', 'directory')
    def test_precheck_retry_directory_failure(self): self.retry('OWNER_precheck.json', 'directory')
    def test_started_retry_directory_failure(self): self.retry('STARTED.json', 'directory')

    def test_started_crash_then_owner_exit_cannot_adopt_completion(self):
        c, kids = self.crash('STARTED.json')
        kids['report'].terminate(); kids['report'].wait(timeout=3)
        before = (c.root/'STARTED.json').read_bytes()
        with self.assertRaises(o.Block): c.new_observer().step()
        self.assertEqual((c.root/'STARTED.json').read_bytes(), before)
        self.assertFalse((c.fixture.root/'SIGNAL.json').exists())

    def test_invalid_reused_bytes_preserved_without_record_fsync(self):
        for target in ('STARTED.json', 'OWNER_report.json', 'OWNER_precheck.json'):
            for mutation in ('partial', 'identity', 'extra', 'noncanonical', 'duplicate_key'):
                with self.subTest(target=target, mutation=mutation):
                    c, _ = self.crash(target)
                    path = c.root/target
                    doc = json.loads(path.read_bytes())
                    if mutation == 'partial': raw = b'{'
                    elif mutation == 'noncanonical': raw = json.dumps(doc).encode()
                    elif mutation == 'duplicate_key':
                        raw = b'{"schema":"conflict",' + o.canonical(doc)[1:]
                    else:
                        if mutation == 'identity': doc['authorization']['sha256'] = 'e'*64
                        else: doc['unexpected'] = True
                        raw = o.canonical(doc)
                    path.write_bytes(raw)
                    synced = []
                    original = o.os.fsync
                    def sync(fd):
                        synced.append(Path('/proc/self/fd/' + str(fd)).resolve())
                        return original(fd)
                    with patch.object(o.os, 'fsync', side_effect=sync), self.assertRaises(ValueError):
                        c.new_observer().step()
                    self.assertNotIn(path, synced)
                    self.assertEqual(path.read_bytes(), raw)
                    self.assertFalse((c.fixture.root/'SIGNAL.json').exists())

    def test_reused_owner_artifact_mutation_rejected_before_resync(self):
        for role in ('report', 'precheck'):
            with self.subTest(role=role):
                c, _ = self.crash('OWNER_' + role + '.json')
                path = c.root/('OWNER_' + role + '.json')
                before = path.read_bytes()
                artifact = Path(c.observer.groups[role][-1])
                artifact.write_bytes(artifact.read_bytes() + b' ')
                synced = []
                original = o.os.fsync
                def sync(fd):
                    synced.append(Path('/proc/self/fd/' + str(fd)).resolve())
                    return original(fd)
                with patch.object(o.os, 'fsync', side_effect=sync), self.assertRaises(o.Block):
                    c.new_observer().restore()
                self.assertNotIn(path, synced)
                self.assertEqual(path.read_bytes(), before)
                self.assertFalse((c.fixture.root/'SIGNAL.json').exists())

    def test_reused_record_changed_between_validation_and_sync_preserved(self):
        for role in ('report', 'precheck'):
            with self.subTest(role=role):
                c, _ = self.crash('OWNER_' + role + '.json')
                path = c.root/('OWNER_' + role + '.json')
                original = o.durable
                def mutate(p, value):
                    if Path(p) == path: path.write_bytes(b'{')
                    return original(p, value)
                with patch.object(o, 'durable', side_effect=mutate), self.assertRaises(o.Block):
                    c.new_observer().step()
                self.assertEqual(path.read_bytes(), b'{')
                self.assertFalse((c.fixture.root/'SIGNAL.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
