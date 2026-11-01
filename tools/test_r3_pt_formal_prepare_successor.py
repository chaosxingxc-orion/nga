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


if __name__ == '__main__':
    unittest.main(verbosity=2)
