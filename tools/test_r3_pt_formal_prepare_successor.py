#!/usr/bin/env python3
"""CPU rejection tests. Synthetic linkage fixtures are NOT genuine precheck success.

No producer is run, no acceptance consumer is mocked, no PT plan is prepared.
The live-input tests only check absence, identity and real validator rejection.
"""
import copy
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('pt_successor', HERE/'r3_pt_formal_prepare_successor.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def competing_lock(path, output):
    try:
        with m.exclusive(Path(path)):
            output.put('ACQUIRED')
    except BlockingIOError:
        output.put('REJECTED')


class CPURejections(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root/'K0_PRECHECKS.json'
        self.q = {'output': str(self.output)}
        self.consumed = {'queue': '/fixture/report/queue.json', 'queue_sha256': 'b'*64,
                         'job': {'id': 'instruct-k0'}, 'terminal': '/fixture/report/EXIT.json',
                         'terminal_sha256': 'c'*64, 'report': '/fixture/selection_report.json',
                         'report_sha256': 'd'*64}
        self.bundle = {'schema': 'r3-fresh-k0-prechecks-v2', 'status': 'PASS', 'model': m.MODEL,
                       'scientific_acceptance': False, 'test_read': False,
                       'checks': {f'/fixture/check{i}': 'e'*64 for i in range(6)},
                       'inputs': {self.consumed['report']: self.consumed['report_sha256']},
                       'k0_report': self.consumed['report']}
        self.validation = {'schema': self.bundle['schema'], 'output': str(self.output),
                           'output_sha256': m.digest(m.canonical(self.bundle)),
                           'full_validate_bundle_completed': True, 'checks': 6, 'inputs': 1,
                           'scientific_acceptance': False, 'test_read': False, 'consumed': self.consumed}
        self.end = {'exit_code': 0, 'queue_sha256': m.QUEUE_PIN,
                    'validation_sha256': m.digest(m.canonical(self.validation)),
                    'output_sha256': m.digest(m.canonical(self.bundle)),
                    'scientific_acceptance': False, 'test_read': False}

    def tearDown(self):
        self.tmp.cleanup()

    def linked(self, refresh=False):
        if refresh:
            self.validation['output_sha256'] = m.digest(m.canonical(self.bundle))
            self.end['output_sha256'] = self.validation['output_sha256']
            self.end['validation_sha256'] = m.digest(m.canonical(self.validation))
        return m.linkage(self.q, m.QUEUE_PIN, m.canonical(self.end),
                         m.canonical(self.validation), m.canonical(self.bundle), self.consumed)

    def test_null_and_pending_hashes_never_read(self):
        for h in (None, '', 'PENDING', 'g'*64, 0):
            with self.subTest(h=h), self.assertRaisesRegex(ValueError, 'non-concrete'):
                m.checked(self.root/'absent', h)

    def test_real_file_buffer_mutation_rejected(self):
        p = self.root/'data.json'; p.write_bytes(b'{"value":1}')
        pin = m.sha(p); raw = m.checked(p, pin)
        p.write_bytes(b'{"value":2}')
        self.assertEqual(json.loads(raw), {'value': 1})
        with self.assertRaisesRegex(ValueError, 'pin differs'):
            m.doc(p, pin)

    def test_module_executes_checked_source_buffer(self):
        p = self.root/'code.py'; p.write_text('VALUE = 17\n')
        pin = m.sha(p)
        self.assertEqual(m.module(p, pin).VALUE, 17)
        p.write_text('raise RuntimeError("mutated source executed")\n')
        with self.assertRaisesRegex(ValueError, 'pin differs'):
            m.module(p, pin)

    def test_validation_buffer_mutation_rejected(self):
        self.validation['inputs'] = 9
        with self.assertRaisesRegex(ValueError, 'buffer linkage'):
            self.linked()

    def test_bundle_buffer_mutation_rejected(self):
        self.bundle['status'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'buffer linkage'):
            self.linked()

    def test_wrong_queue(self):
        self.end['queue_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'queue differs'):
            self.linked()

    def test_non_integer_failed_and_incomplete_terminal(self):
        for code in (False, True, 1, None, '0'):
            self.end['exit_code'] = code
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.linked()

    def test_incomplete_validation_even_rehashed(self):
        for field, value in [('full_validate_bundle_completed', False), ('checks', 5),
                             ('test_read', True), ('scientific_acceptance', True), ('output', '/wrong')]:
            old = self.validation[field]; self.validation[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.linked(refresh=True)
            self.validation[field] = old

    def test_wrong_model_even_rehashed(self):
        self.bundle['model'] += '-Base'
        with self.assertRaisesRegex(ValueError, 'bundle model'):
            self.linked(refresh=True)

    def test_wrong_report_even_rehashed(self):
        self.bundle['k0_report'] = '/wrong/report.json'
        with self.assertRaisesRegex(ValueError, 'bundle model/report'):
            self.linked(refresh=True)

    def test_stale_consumed_mapping_even_rehashed(self):
        self.validation['consumed'] = {**self.consumed, 'terminal_sha256': 'f'*64}
        with self.assertRaisesRegex(ValueError, 'consumed mapping'):
            self.linked(refresh=True)

    def test_consumed_mapping_extra_field_rejected(self):
        self.validation['consumed'] = {**self.consumed, 'unreviewed': True}
        with self.assertRaisesRegex(ValueError, 'consumed mapping'):
            self.linked(refresh=True)

    def test_report_hash_linkage(self):
        self.bundle['inputs'][self.consumed['report']] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'bundle model/report'):
            self.linked(refresh=True)

    def test_missing_prerequisite(self):
        self.consumed = None
        with self.assertRaisesRegex(ValueError, 'consumed mapping'):
            self.linked()

    def test_partial_prepare_output_never_adopted(self):
        out = self.root/'seed2'; out.mkdir(); (out/'plan.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'uncertain interrupted'):
            m.seed_state(self.root, 2, out)
        self.assertEqual((out/'plan.json').read_text(), '{}')

    def test_intent_without_output_never_retried(self):
        m.save(self.root/'SEED2_INTENT.json', {'started': True})
        with self.assertRaisesRegex(ValueError, 'uncertain interrupted'):
            m.seed_state(self.root, 2, self.root/'seed2')

    def test_partial_prepared_receipt_never_adopted(self):
        (self.root/'SEED2_PREPARED.json').write_text('{')
        m.save(self.root/'SEED2_INTENT.json', {})
        with self.assertRaises(json.JSONDecodeError):
            m.seed_state(self.root, 2, self.root/'seed2')

    def test_durable_write_never_overwrites(self):
        p = self.root/'receipt.json'; pin = m.save(p, {'a': 1})
        with self.assertRaises(FileExistsError):
            m.save(p, {'a': 2})
        self.assertEqual(m.sha(p), pin)

    def test_explicit_completed_output_inventory_rechecked(self):
        out = self.root/'seed2'; out.mkdir(); (out/'plan.json').write_text('{"fixture_only":true}')
        intent_pin = m.save(self.root/'SEED2_INTENT.json', {'fixture_only': True})
        row = {'out': str(out), 'intent_sha256': intent_pin, 'output_inventory': m.tree(out)}
        m.save(self.root/'SEED2_PREPARED.json', row)
        self.assertEqual(m.seed_state(self.root, 2, out), row)  # state only, never full consumer acceptance
        (out/'partial').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed or partial'):
            m.seed_state(self.root, 2, out)

    def test_duplicate_real_processes(self):
        context = multiprocessing.get_context('fork'); queue = context.Queue()
        with m.exclusive(self.root/'worker.lock'):
            child = context.Process(target=competing_lock, args=(str(self.root/'worker.lock'), queue))
            child.start(); child.join(10)
            self.assertFalse(child.is_alive()); self.assertEqual(child.exitcode, 0)
            self.assertEqual(queue.get(timeout=2), 'REJECTED')
        queue.close()

    def test_symlinks_and_test_paths_rejected(self):
        p = self.root/'a'; p.write_text('data'); (self.root/'link').symlink_to(p)
        for path in (self.root/'link', self.root/'test.jsonl', self.root/'test'/'data.parquet'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                m.safe(path)

    def test_missing_full_validation_never_reaches_prepare(self):
        with self.assertRaisesRegex(ValueError, 'genuine full prechecks'):
            m.prepare_plans({'root': str(self.root)}, 'a'*64,
                            {'state': 'WAIT_EXTERNAL_COMPLETION_AUTHENTICATION'}, {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unauthenticated_signal_is_not_written(self):
        # Test the receipt validator directly; no production service is activated.
        p = self.root/'deployment.json'
        r = {'worker_sha256': 'a'*64, 'precheck_service': {'path': '/fixture', 'sha256': 'b'*64}}
        a = {'schema': 'r3-pt-preparation-deployment-v1', 'request_sha256': 'c'*64,
             'worker_sha256': r['worker_sha256'], 'root_source_review_completed': True,
             'publication_completed': False, 'precheck_process_authenticated': True,
             'precheck_service': r['precheck_service'], 'scientific_acceptance': False,
             'training_authorized': False}
        pin = m.save(p, a)
        with self.assertRaisesRegex(ValueError, 'external root deployment'):
            m.deployment(r, 'c'*64, p, pin)

    def test_unapproved_deployment_rejected(self):
        p = self.root/'deployment.json'; pin = m.save(p, {'schema': 'r3-pt-preparation-deployment-v1'})
        with self.assertRaisesRegex(ValueError, 'external root deployment'):
            m.deployment({'worker_sha256': 'a'*64}, 'b'*64, p, pin)


class RealFrozenConsumers(unittest.TestCase):
    """Real source, negative cases. No fabricated current Instruct success."""
    @classmethod
    def setUpClass(cls):
        cls.q = m.doc(m.QUEUE, m.QUEUE_PIN)
        cls.waiter = m.module(cls.q['worker'], cls.q['worker_sha256'])
        cls.consumer = m.module(cls.q['consumer'], cls.q['source_pins'][cls.q['consumer']])

    def test_exact_live_queue_identity(self):
        self.assertEqual(self.waiter.request(m.QUEUE, m.QUEUE_PIN), self.q)
        self.waiter.dependencies(self.q)

    def test_genuine_base_bundle_rejected_for_pt(self):
        base = m.RUNS/'fresh_k0_source_verified_cpu_20261101_v1/evidence/K0_PRECHECKS.json'
        with self.assertRaisesRegex(ValueError, 'scope differs'):
            self.consumer.validate_bundle(str(base), '8f97ec9e559830cf62f9ec15e064cce959a42ee65b7ca66a56a3835efb8f7810', m.MODEL)

    def test_real_validator_rejects_wrong_split_arm_model(self):
        header = {'arm': 'K0', 'model': {'kind': 'checkpoint', 'path': m.MODEL},
                  'partitions': ['dev', 'calibration']}
        for change in ({'arm': 'K1'}, {'partitions': ['dev', 'test']},
                       {'model': {'kind': 'checkpoint', 'path': m.MODEL+'-Base'}}):
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                self.consumer.validate_baseline({'header': {**header, **change}}, m.MODEL)

    def test_real_waiter_prerequisite_rejects_wrong_queue(self):
        q = copy.deepcopy(self.q); q['producer']['queue_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'source pin differs'):
            self.waiter.prerequisite(q)

    def test_real_waiter_report_scope_rejections(self):
        # Feed negative report terminal fixtures to unchanged pinned prerequisite.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); jobs = root/'jobs/instruct-k0'; jobs.mkdir(parents=True)
            out = root/'results'; out.mkdir()
            controller = root/'controller.py'; controller.write_text('# fixture, never executed\n')
            q = copy.deepcopy(self.q); p = q['producer']
            p['queue'] = str(root/'queue.json'); p['terminal'] = str(jobs/'EXIT.json')
            p['job'] = {'id': 'instruct-k0', 'kind': 'report', 'eval_out': str(root),
                        'output': str(out/'selection_report.json')}
            queue = {'schema': 'r3-cpu-report-queue-v1', 'scientific_acceptance': False, 'test_read': False,
                     'controller': str(controller), 'controller_sha256': m.sha(controller), 'jobs': [p['job']]}
            p['queue_sha256'] = m.save(root/'queue.json', queue)
            self.assertIsNone(self.waiter.prerequisite(q))
            for code in (1, False, None):
                (jobs/'EXIT.json').write_bytes(m.canonical({'exit_code': code, 'scientific_acceptance': False}))
                with self.assertRaisesRegex(ValueError, 'producer failed'):
                    self.waiter.prerequisite(q)
            for changes in ({'arm': 'K1'}, {'model': {'kind': 'checkpoint', 'path': m.MODEL+'-Base'}},
                            {'partitions': ['dev', 'test']}):
                header = {'arm': 'K0', 'model': {'kind': 'checkpoint', 'path': m.MODEL},
                          'partitions': ['dev', 'calibration']}
                report = {'schema': 'r3-selection-report-v1', 'scientific_acceptance': False,
                          'header': {**header, **changes}}
                (out/'selection_report.json').write_bytes(m.canonical(report))
                (jobs/'EXIT.json').write_bytes(m.canonical({'exit_code': 0, 'scientific_acceptance': False,
                    'output_sha256': m.sha(out/'selection_report.json')}))
                with self.assertRaisesRegex(ValueError, 'K0 identity differs'):
                    self.waiter.prerequisite(q)
            (out/'selection_report.json').write_bytes(b'{')
            with self.assertRaisesRegex(ValueError, 'source pin differs'):
                self.waiter.prerequisite(q)

class RepairExecution(unittest.TestCase):
    """Actual copied consumers; mocks only inject bytes/races, never success."""
    GEN = HERE if (HERE/'REQUEST.json').is_file() else m.RUNS/'pt_formal_prepare_successor_20261101_v3'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.r = json.loads((self.GEN/'REQUEST.json').read_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def helper(self, name):
        p = self.GEN/'source/tools'/name
        return m.module(p, self.r['source_pins'][str(p)])

    def test_review_case1_top_buffer_swap_after_check(self):
        from unittest.mock import patch
        p = self.root/'fixture.py'; p.write_text('VALUE = 17\n'); pin = m.sha(p)
        original = m.checked
        def mutate(path, expected):
            raw = original(path, expected)
            p.write_text('raise AssertionError("executed mutation")\n')
            return raw
        with patch.object(m, 'checked', mutate):
            self.assertEqual(m.module(p, pin).VALUE, 17)

    def test_review_case2_real_launcher_hash_read_substitution(self):
        from unittest.mock import patch
        launcher = self.helper('r3_formal_launcher.py')
        helper = self.GEN/'source/tools/r3_fresh_prechecks.py'
        pin = m.sha(helper); original = Path.read_bytes
        executed = self.root/'EXECUTED'
        evil = f'from pathlib import Path\nPath({str(executed)!r}).touch()\n'.encode()
        injected = []
        def mutate(path):
            if path == helper:
                injected.append(True); return evil
            return original(path)
        plan = {'files': {str(helper): pin, '/fixture/bundle': 'a'*64},
                'fresh_k0_prechecks': '/fixture/bundle', 'fresh_k0_prechecks_sha256': 'a'*64,
                'model': m.MODEL}
        # Real sha(open) sees genuine bytes; ONLY subsequent source read changes.
        with patch.object(Path, 'read_bytes', mutate), self.assertRaisesRegex(ValueError, 'buffer pin'):
            launcher.verify_fresh_prechecks(plan)
        self.assertTrue(injected); self.assertFalse(executed.exists()); self.assertEqual(m.sha(helper), pin)

    def test_review_case3_real_prepare_hash_read_substitution(self):
        from unittest.mock import patch
        prep = self.helper('r3_formal_prepare.py')
        helper = self.GEN/'source/tools/r3_fresh_prechecks.py'
        prep.ROOT = self.GEN/'source'
        original = Path.read_bytes; executed = self.root/'EXECUTED'
        def mutate(path):
            if path == helper:
                return f'from pathlib import Path\nPath({str(executed)!r}).touch()\n'.encode()
            return original(path)
        with patch.object(Path, 'read_bytes', mutate), self.assertRaisesRegex(ValueError, 'buffer pin'):
            prep.prepare(self.root/'plan', 2, 1, model=Path(m.MODEL), control_arm='K1-PT',
                         fresh_prechecks='/fixture/bundle', fresh_prechecks_sha256='a'*64)
        self.assertFalse(executed.exists()); self.assertFalse((self.root/'plan').exists())

    def test_real_disk_mutation_between_launcher_hash_and_read(self):
        from unittest.mock import patch
        # Copy actual repaired launcher/helper into an isolated layout. Mutate
        # the on-disk helper immediately AFTER the real launcher.sha returns.
        launcher_path = self.root/'r3_formal_launcher.py'
        launcher_path.write_bytes((self.GEN/'source/tools/r3_formal_launcher.py').read_bytes())
        helper = self.root/'r3_fresh_prechecks.py'
        helper.write_bytes((self.GEN/'source/tools/r3_fresh_prechecks.py').read_bytes())
        launcher = m.module(launcher_path, m.sha(launcher_path)); pin = m.sha(helper)
        executed = self.root/'EXECUTED'; original = launcher.sha
        def mutate(path):
            result = original(path)
            if path == helper:
                helper.write_text(f'from pathlib import Path\nPath({str(executed)!r}).touch()\n')
            return result
        plan = {'files': {str(helper): pin, '/fixture/bundle': 'a'*64},
                'fresh_k0_prechecks': '/fixture/bundle', 'fresh_k0_prechecks_sha256': 'a'*64,
                'model': m.MODEL}
        with patch.object(launcher, 'sha', mutate), self.assertRaisesRegex(ValueError, 'buffer pin'):
            launcher.verify_fresh_prechecks(plan)
        self.assertFalse(executed.exists())

    def test_actual_report_transitive_imports_and_manifest_race(self):
        from unittest.mock import patch
        report_path = m.RUNS/'fresh_k0_source_verified_cpu_20261101_v1/r3_selection_report.py'
        closure = m.RUNS/'selection_cpu_closure_20261031_v2'
        pins = m.execution_scope(self.r)
        with m.checked_execution(pins):
            report = m.module(report_path, pins[str(report_path)])
            modules = report.modules(closure/'r3_code')
            self.assertEqual(len(modules), 5)  # actual project imports, no metric claim
            loader = modules[0].__loader__
            self.assertIn('prompt', loader.loaded)
        # Alter BOTH manifest read and helper buffer after inventory hash. The
        # independent request closure still rejects before compilation/execution.
        helper = closure/'r0_code/prompt.py'; manifest = closure/'manifest.json'
        original = Path.read_bytes; original_text = Path.read_text
        executed = self.root/'EXECUTED'
        evil = f'from pathlib import Path\nPath({str(executed)!r}).touch()\n'.encode()
        altered = json.loads(original(manifest))
        for entry in altered['code'].values():
            if entry['snapshot'] == str(helper): entry['sha256'] = m.digest(evil)
        def mutate(path): return evil if path == helper else original(path)
        def mutate_text(path, *args, **kwargs):
            return json.dumps(altered) if path == manifest else original_text(path, *args, **kwargs)
        with m.checked_execution(pins):
            report = m.module(report_path, pins[str(report_path)])
            with patch.object(Path, 'read_bytes', mutate), patch.object(Path, 'read_text', mutate_text):
                with self.assertRaisesRegex(ValueError, 'execution buffer pin'):
                    report.modules(closure/'r3_code')
        self.assertFalse(executed.exists())

    def test_cached_bytecode_and_unpinned_project_exec_rejected(self):
        p = self.root/'fixture.py'; p.write_text('VALUE = 17\n')
        code = compile(p.read_bytes(), str(p), 'exec')
        with m.checked_execution({str(p): m.sha(p)}):
            with self.assertRaisesRegex(ValueError, 'unchecked project code'):
                exec(code, {})
            with self.assertRaisesRegex(ValueError, 'outside reviewed closure'):
                compile('VALUE = 1', str(m.REPO/'tools/unreviewed_fixture.py'), 'exec')

    def test_real_resume_transitive_loader_rejects_mutation(self):
        from unittest.mock import patch
        consumer = self.helper('r3_resume_reconstruction_evidence.py')
        helper = self.GEN/'source/tools/r3_resume_evidence.py'; original = Path.read_bytes
        def mutate(path):
            return b'raise AssertionError("executed unchecked resume")\n' if path == helper else original(path)
        with m.checked_execution(m.execution_scope(self.r)), patch.object(Path, 'read_bytes', mutate):
            with self.assertRaisesRegex(ValueError, 'implementation differs'):
                consumer.validator()

    def test_real_prepare_and_launcher_negative_base_consumers(self):
        base = m.RUNS/'fresh_k0_source_verified_cpu_20261101_v1/evidence/K0_PRECHECKS.json'
        pin = '8f97ec9e559830cf62f9ec15e064cce959a42ee65b7ca66a56a3835efb8f7810'
        with m.checked_execution(m.execution_scope(self.r)):
            prep = self.helper('r3_formal_prepare.py'); prep.ROOT = self.GEN/'source'
            with self.assertRaisesRegex(ValueError, 'scope differs'):
                prep.prepare(self.root/'plan', 2, 1, model=Path(m.MODEL), control_arm='K1-PT',
                             fresh_prechecks=str(base), fresh_prechecks_sha256=pin)
            launcher = self.helper('r3_formal_launcher.py')
            helper = self.GEN/'source/tools/r3_fresh_prechecks.py'
            plan = {'files': {str(helper): self.r['source_pins'][str(helper)], str(base): pin},
                    'fresh_k0_prechecks': str(base), 'fresh_k0_prechecks_sha256': pin, 'model': m.MODEL}
            with self.assertRaisesRegex(ValueError, 'scope differs'):
                launcher.verify_fresh_prechecks(plan)
        self.assertFalse((self.root/'plan').exists())

    def test_review_case5_external_deployment_trust_boundary_unchanged(self):
        p = self.root/'opaque.txt'; p.write_text('synthetic, not publication or review')
        a = {'schema': 'r3-pt-preparation-deployment-v1', 'request_sha256': 'a'*64,
             'worker_sha256': self.r['worker_sha256'], 'root_source_review_completed': True,
             'publication_completed': True, 'precheck_process_authenticated': True,
             'precheck_service': self.r['precheck_service'], 'scientific_acceptance': False,
             'training_authorized': False, 'source_review': m.receipt_ref(p), 'publication': m.receipt_ref(p)}
        auth = self.root/'synthetic-deployment.json'; pin = m.save(auth, a)
        self.assertEqual(m.deployment(self.r, 'a'*64, auth, pin), a)

    def test_review_case6_cpu_guard_direct_hooks(self):
        import sys
        from unittest.mock import patch
        hooks = []; (self.root/'tmp').mkdir()
        with patch.object(sys, 'addaudithook', hooks.append), patch.object(os, 'devnull'), patch.dict(sys.modules):
            m.cpu_guard(self.root)
        for event, args in [('socket.connect', (None, ('fixture.invalid', 1))),
                            ('subprocess.Popen', ('fixture',)), ('open', ('/dev/davinci0', 'r', 0)),
                            ('open', (str(self.root/'test.jsonl'), 'r', 0)),
                            ('open', (str(self.root/'fixture.log'), 'r', 0)),
                            ('open', ('/fixture/outside', 'w', os.O_WRONLY))]:
            with self.subTest(event=event, args=args), self.assertRaises((ValueError, PermissionError)):
                hooks[0](event, args)


class RepairSignal(unittest.TestCase):
    """Only request() redirects to fixture root. Real dependency, real pinned
    waiter/request/prerequisite/linkage/schema/inventory. NO full validator mock:
    admission_only checks links; synthetic PASS metadata proves no numerical or
    genuine producer success. No SERVICE means no signal/process activation.
    """
    def setUp(self):
        from unittest.mock import patch
        import sys
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        pre = self.root/'prechecks'; pre.mkdir()
        jobs = self.root/'report/jobs/instruct-k0'; jobs.mkdir(parents=True)
        results = self.root/'results'; results.mkdir()
        self.q = copy.deepcopy(m.doc(m.QUEUE, m.QUEUE_PIN))
        p = self.q['producer']; p['queue'] = str(self.root/'report/queue.json')
        p['terminal'] = str(jobs/'EXIT.json')
        p['job'] = {'id': 'instruct-k0', 'kind': 'report', 'eval_out': str(self.root),
                    'output': str(results/'selection_report.json')}
        ctrl = self.root/'fixture_controller.py'; ctrl.write_text('# inert, never executed\n')
        p['queue_sha256'] = m.save(Path(p['queue']), {'schema': 'r3-cpu-report-queue-v1',
            'scientific_acceptance': False, 'test_read': False, 'controller': str(ctrl),
            'controller_sha256': m.sha(ctrl), 'jobs': [p['job']]})
        m.save(Path(p['job']['output']), {'schema': 'r3-selection-report-v1', 'scientific_acceptance': False,
            'header': {'arm': 'K0', 'model': self.q['expected_report_model'], 'partitions': ['dev','calibration']}})
        m.save(Path(p['terminal']), {'exit_code': 0, 'scientific_acceptance': False,
                                   'output_sha256': m.sha(p['job']['output'])})
        self.q['output'] = str(pre/'evidence/K0_PRECHECKS.json'); (pre/'evidence').mkdir()
        qp = pre/'queue.json'; qh = m.save(qp, self.q)
        self.r = {'root': str(self.root), 'queue': {'path': str(qp), 'sha256': qh},
                  'source_pins': self.q['source_pins'], 'frozen_repository': str(self.root/'source'),
                  'targets': [], 'python': sys.executable}
        service = {'command': [sys.executable, '-B', '-P', self.q['worker'], 'watch', '--queue', str(qp), '--sha256', qh],
                   'pid': 123, 'start_ticks': '456'}
        sp = pre/'SERVICE.json'; m.save(sp, service); self.r['precheck_service'] = m.receipt_ref(sp)
        ap = pre/'ACTIVATION.json'; m.save(ap, {'service': service, 'process_identity_verified': True, 'queue_sha256': qh})
        self.r['precheck_activation'] = m.receipt_ref(ap)
        waiter = m.module(self.q['worker'], self.q['worker_sha256']); consumed = waiter.prerequisite(self.q)
        bundle = {'schema': 'r3-fresh-k0-prechecks-v2', 'status': 'PASS', 'model': m.MODEL,
            'scientific_acceptance': False, 'test_read': False, 'checks': {f'/fixture/check{i}': 'e'*64 for i in range(6)},
            'inputs': {consumed['report']: consumed['report_sha256']}, 'k0_report': consumed['report']}
        bh = m.save(Path(self.q['output']), bundle)
        v = {'schema': bundle['schema'], 'output': self.q['output'], 'output_sha256': bh,
             'full_validate_bundle_completed': True, 'checks': 6, 'inputs': 1,
             'scientific_acceptance': False, 'test_read': False, 'consumed': consumed}
        vp = pre/'VALIDATION.json'; vh = m.save(vp, v)
        ep = pre/'EXIT.json'; eh = m.save(ep, {'exit_code': 0, 'queue_sha256': qh, 'validation_sha256': vh,
                   'output_sha256': bh, 'scientific_acceptance': False, 'test_read': False})
        self.artifacts = {str(ep): eh, str(vp): vh, self.q['output']: bh,
                          consumed['terminal']: consumed['terminal_sha256'], consumed['report']: consumed['report_sha256']}
        self.a = {'schema': 'r3-pt-precheck-authentication-v1', 'external_process_and_terminal_authenticated': True,
                  'queue': self.r['queue'], 'precheck_service': self.r['precheck_service'],
                  'worker_sha256': self.q['worker_sha256'], 'artifacts': self.artifacts, 'scientific_acceptance': False}
        self.redirect = patch.object(m, 'request', return_value=self.r); self.redirect.start()
        self.n = 0

    def tearDown(self):
        self.redirect.stop(); self.tmp.cleanup()

    def send(self, a=None):
        self.n += 1; auth = self.root/f'fixture_auth{self.n}.json'; pin = m.save(auth, self.a if a is None else a)
        return m.send_signal(self.root/'fixture-request.json', 'a'*64, auth, pin), auth, pin

    def reject(self, a=None):
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)):
            self.send(a)
        self.assertFalse((self.root/'SIGNAL.json').exists())

    def test_review_case4_incomplete_auth_never_occupies_signal(self):
        bad = {k: self.a[k] for k in ('external_process_and_terminal_authenticated','queue','precheck_service')}
        self.reject(bad)
        result, _, _ = self.send()
        self.assertTrue(result['signal_retained'])

    def test_schema_worker_scope_and_exact_five_path_pins(self):
        for key, value in [('schema', 'wrong'), ('worker_sha256', 'f'*64), ('scientific_acceptance', True),
                           ('artifacts', {}), ('artifacts', {**self.artifacts, '/fixture/extra': 'a'*64}),
                           ('artifacts', {**self.artifacts, self.q['output']: None})]:
            with self.subTest(key=key, value=value): self.reject({**self.a, key: value})

    def test_early_signal_no_terminal(self):
        (Path(self.r['queue']['path']).parent/'EXIT.json').unlink()
        self.reject()

    def test_stale_signal_changed_artifact(self):
        self.reject({**self.a, 'artifacts': {**self.artifacts, self.q['output']: 'f'*64}})

    def test_bad_observed_links_even_with_matching_hashes(self):
        vp = Path(self.r['queue']['path']).parent/'VALIDATION.json'
        v = json.loads(vp.read_bytes()); v['consumed']['report_sha256'] = 'f'*64
        vp.write_bytes(m.canonical(v)); ep = vp.with_name('EXIT.json'); e = json.loads(ep.read_bytes())
        e['validation_sha256'] = m.sha(vp); ep.write_bytes(m.canonical(e))
        self.a['artifacts'][str(vp)] = m.sha(vp); self.a['artifacts'][str(ep)] = m.sha(ep)
        self.reject()

    def test_same_valid_identity_idempotent_conflicting_valid_rejected(self):
        result, auth, pin = self.send(); envelope = (self.root/'SIGNAL.json').read_bytes()
        self.assertTrue(result['signal_retained'])
        again = m.send_signal(self.root/'fixture-request.json', 'a'*64, auth, pin)
        self.assertTrue(again['signal_retained'])
        with self.assertRaisesRegex(ValueError, 'no overwrite'):
            self.send()  # another valid receipt path, same real observed five hashes
        self.assertEqual((self.root/'SIGNAL.json').read_bytes(), envelope)

    def test_run_dependency_rechecks_stale_admitted_signal(self):
        _, auth, pin = self.send()
        ep = Path(self.r['queue']['path']).parent/'EXIT.json'
        end = json.loads(ep.read_bytes()); end['fixture_changed'] = True; ep.write_bytes(m.canonical(end))
        with self.assertRaisesRegex(ValueError, 'authentication differs'):
            m.dependency(self.r, {'path': str(auth), 'sha256': pin})

    def test_ingress_pass_does_not_replace_run_full_consumer(self):
        _, auth, pin = self.send()
        # Actual full consumer rejects synthetic bundle; no patched success.
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)):
            m.dependency(self.r, {'path': str(auth), 'sha256': pin})

    def test_changed_activation_is_rejected_before_signal(self):
        Path(self.r['precheck_activation']['path']).write_text('{}')
        self.reject()


class CompilerBoundary(unittest.TestCase):
    """Actual compile/exec; substitutions never mock numerical success."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root/'compiler_fixture.py'
        self.raw = b'VALUE = 7\n'
        self.path.write_bytes(self.raw)
        self.pins = {str(self.path): m.sha(self.path)}

    def calls(self, source, filename):
        return [((source, filename, 'exec'), {}),
                ((), dict(source=source, filename=filename, mode='exec')),
                ((source,), dict(filename=filename, mode='exec')),
                ((source, filename), dict(mode='exec'))]

    def test_matching_buffers_positional_keyword_and_filename_forms(self):
        for filename in (str(self.path), bytes(self.path), self.path):
            for source in (self.raw, self.raw.decode()):
                for args, kwargs in self.calls(source, filename):
                    with self.subTest(filename=filename, kwargs=kwargs), m.checked_execution(self.pins):
                        ns = {}; exec(compile(*args, **kwargs), ns)
                        self.assertEqual(ns['VALUE'], 7)

    def test_ast_rejected_before_underlying_compile_all_argument_forms(self):
        import ast, builtins
        from unittest.mock import patch
        tree = ast.parse('raise AssertionError("UNCHECKED_AST_EXECUTED")')
        for filename in (str(self.path), bytes(self.path), self.path):
            for args, kwargs in self.calls(tree, filename):
                with self.subTest(filename=filename, kwargs=kwargs):
                    with patch.object(builtins, 'compile', wraps=builtins.compile) as compiler:
                        with m.checked_execution(self.pins):
                            compiler.reset_mock()
                            with self.assertRaisesRegex(ValueError, 'AST compilation forbidden'):
                                compile(*args, **kwargs)
                            compiler.assert_not_called()
                            self.assertEqual(m._EXECUTION.state[1], [])

    def test_wrong_buffer_rejected_before_underlying_compile(self):
        import builtins
        from unittest.mock import patch
        for args, kwargs in self.calls(b'VALUE = 8\n', str(self.path)):
            with patch.object(builtins, 'compile', wraps=builtins.compile) as compiler:
                with m.checked_execution(self.pins):
                    compiler.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'execution buffer pin'):
                        compile(*args, **kwargs)
                    compiler.assert_not_called()
                    self.assertEqual(m._EXECUTION.state[1], [])

    def test_unpinned_project_source_and_ast_rejected(self):
        import ast
        for source in (self.raw, ast.parse(self.raw)):
            for args, kwargs in self.calls(source, str(m.REPO/'tools/unreviewed_compiler.py')):
                with m.checked_execution(self.pins), self.assertRaisesRegex(ValueError, 'outside reviewed closure'):
                    compile(*args, **kwargs)

    def test_mutable_project_source_rejected(self):
        for source in (bytearray(self.raw), memoryview(self.raw)):
            with m.checked_execution(self.pins), self.assertRaisesRegex(ValueError, 'AST compilation forbidden'):
                compile(source=source, filename=self.path, mode='exec')

    def test_nonproject_ast_stays_usable_without_project_registration(self):
        import ast
        with m.checked_execution(self.pins):
            tree = ast.parse('VALUE = 9\n')
            ns = {}; exec(compile(source=tree, filename='<runtime-generated>', mode='exec'), ns)
            self.assertEqual(ns['VALUE'], 9)
            self.assertEqual(m._EXECUTION.state[1], [])

    def test_project_ast_only_parse_does_not_authorize_recompile(self):
        import ast
        with m.checked_execution(self.pins):
            tree = compile(self.raw, self.path, 'exec', ast.PyCF_ONLY_AST)
            self.assertIsInstance(tree, ast.AST)
            self.assertEqual(m._EXECUTION.state[1], [])
            with self.assertRaisesRegex(ValueError, 'AST compilation forbidden'):
                compile(tree, self.path, 'exec')

    def test_flags_and_keyword_only_compiler_option_preserved(self):
        with m.checked_execution(self.pins):
            ns = {}
            exec(compile(source=self.raw, filename=self.path, mode='exec', flags=0,
                         dont_inherit=True, optimize=2, _feature_version=-1), ns)
            self.assertEqual(ns['VALUE'], 7)
            self.assertEqual(len(m._EXECUTION.state[1]), 1)

    def test_argument_errors_never_register_code(self):
        calls = [((self.raw,), {}),
                 ((self.raw, self.path, 'exec'), {'source': self.raw}),
                 ((self.raw, self.path, 'exec'), {'filename': self.path}),
                 ((self.raw, self.path, 'exec'), {'unexpected': True}),
                 ((self.raw, None, 'exec'), {})]
        with m.checked_execution(self.pins):
            for args, kwargs in calls:
                with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                    compile(*args, **kwargs)
                self.assertEqual(m._EXECUTION.state[1], [])

    def test_filename_pathlike_resolved_once(self):
        class ChangingPath:
            def __init__(self, value): self.value, self.calls = value, 0
            def __fspath__(self):
                self.calls += 1
                return self.value if self.calls == 1 else '<changed>'
        filename = ChangingPath(str(self.path))
        with m.checked_execution(self.pins):
            code = compile(self.raw, filename, 'exec')
            self.assertEqual(filename.calls, 1)
            self.assertEqual(code.co_filename, str(self.path))
            ns = {}; exec(code, ns); self.assertEqual(ns['VALUE'], 7)

    def test_original_compiler_ast_code_is_not_registered(self):
        import ast, builtins
        original = builtins.compile
        tree = ast.parse(self.raw)
        with m.checked_execution(self.pins):
            code = original(tree, str(self.path), 'exec')
            with self.assertRaisesRegex(ValueError, 'unchecked project code'):
                exec(code, {})

    def test_exception_restores_compiler_scope(self):
        import ast, builtins
        original = builtins.compile
        tree = ast.parse(self.raw)
        with self.assertRaisesRegex(ValueError, 'AST compilation forbidden'):
            with m.checked_execution(self.pins):
                compile(tree, self.path, 'exec')
        self.assertIs(builtins.compile, original)
        self.assertIsNone(m._EXECUTION.state)

    def test_actual_pinned_kev_loader_clean_and_substituted_ast_rejected(self):
        import builtins, io
        from unittest.mock import patch
        generation = RepairExecution.GEN
        r = json.loads((generation/'REQUEST.json').read_bytes())
        pins = m.execution_scope(r)
        (self.root/'kev').mkdir(); source = self.root/'kev/data.py'
        good = ('NONE_OPTIONS = "PINNED"\nDISTRACTORS = []\n'
                'def source_seed(*args): return 0\ndef augment(*args): return []\n'
                'def none_pair(*args): return []\n')
        evil = good.replace('"PINNED"', '"UNREVIEWED_AST_EXECUTED"')
        source.write_text(good); pin = m.sha(source); pins[str(source)] = pin
        report_path = m.RUNS/'fresh_k0_source_verified_cpu_20261101_v1/r3_selection_report.py'
        with m.checked_execution(pins):
            report = m.module(report_path, pins[str(report_path)])
            consumer = report.modules(m.RUNS/'selection_cpu_closure_20261031_v2/r3_code')[3]
            # Minimal reject also rejects the clean AST extraction path.
            with self.assertRaisesRegex(ValueError, 'AST compilation forbidden'):
                consumer.load_kev_functions(str(self.root))
            reads = []
            def swap(path, *args, **kwargs):
                if str(path) == str(source):
                    reads.append(str(path)); return io.StringIO(evil)
                return builtins.open(path, *args, **kwargs)
            with patch.dict(consumer.__dict__, {'open': swap}):
                with self.assertRaisesRegex(ValueError, 'AST compilation forbidden'):
                    consumer.load_kev_functions(str(self.root))
            self.assertEqual(reads, [str(source)])
            self.assertFalse(any(code.co_filename == str(source) for code in m._EXECUTION.state[1]))
        self.assertEqual(m.sha(source), pin)


if __name__ == '__main__':
    unittest.main(verbosity=2)
