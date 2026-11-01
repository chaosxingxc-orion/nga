import ast
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('handoff', Path(__file__).with_name('r3_formal_posttrain_handoff.py'))
H = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(H)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.train = self.root/'training'; self.train.mkdir()
        self.state = self.root/'state'; self.state.mkdir()
        self.out = self.root/'evaluation'; self.model = self.root/'base'; self.model.mkdir()
        self.closure = self.root/'closure'; self.closure.mkdir()
        self.put(self.model/'config.json', {})
        self.plan = dict(out=str(self.train), run='formal/seed2', chip=1, container='formal', seed=2,
                         image_sha256='image', model=str(self.model), arm='k1', command=['train'],
                         files={str(self.model/'config.json'): H.sha(self.model/'config.json')})
        self.put(self.train/'plan.json', self.plan)
        self.job = dict(seed=2, training=str(self.train), new_adapter=str(self.train/'adapter'),
                        canonical_plan_sha256='canonical', required_final_step=3116,
                        training_plan={'path': str(self.train/'plan.json'), 'sha256': H.sha(self.train/'plan.json')},
                        fresh_eval_out=str(self.out), late_bound_hashes=[
                            'TRAIN_EXIT.json', 'attempts/1/EXIT.json', 'attempts/1/RELEASE.json',
                            'attempts/1/SUPERVISOR_DONE.json', 'manifest.json',
                            'adapter/adapter_config.json', 'adapter/adapter_model.safetensors'])
        closure = dict(data={}, code={}, mounts=[], command_template=['python3', '--arm', 'K1', '--adapter',
                       '<COMPLETED_ADAPTER>', '--out', '<FRESH_EVAL_OUTPUT>'], evaluation_profile='track_kt')
        self.put(self.closure/'manifest.json', closure)
        self.binding = dict(closure={'path': str(self.closure/'manifest.json'), 'sha256': H.sha(self.closure/'manifest.json')},
                            tools={H.BINDER: H.sha(H.BINDER)})

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value))

    def complete(self):
        end = dict(exit_code=0, attempt=1, started_utc='start', finished_utc='end', scientific_acceptance=False)
        self.put(self.train/'TRAIN_EXIT.json', end); self.put(self.train/'attempts/1/EXIT.json', end)
        self.put(self.train/'attempts/1/CLAIM.json', dict(run=self.plan['run'], chip=1))
        self.put(self.train/'attempts/1/RELEASE.json', dict(schema='r3-resource-release-v1', run=self.plan['run'], chip=1,
            container='formal-a1', container_id='id', claim_sha256=H.sha(self.train/'attempts/1/CLAIM.json'),
            exit_code=0, scientific_acceptance=False))
        self.put(self.train/'attempts/1/SUPERVISOR_DONE.json', dict(exit_code=0, scientific_acceptance=False))
        self.put(self.train/'attempts/1/LAUNCH_RECEIPT.json', dict(id='id', image='image', plan_sha256='canonical'))
        for name in ('attempts/1/LAUNCH_SPEC.json', 'SUPERVISOR_RECEIPT.json', 'SUCCESSOR_PRECONDITION.json'):
            self.put(self.train/name, {'fixture': True})
        self.put(self.train/'manifest.json', dict(summary={'final_step': 3116}, arm='k1', model_path=str(self.model),
            args=dict(arm='k1', seed=2, model_path=str(self.model))))
        self.put(self.train/'adapter/adapter_config.json', {})
        (self.train/'adapter/adapter_model.safetensors').write_bytes(b'fixture adapter')

    def capture(self):
        return H.capture(self.binding, self.job, self.plan)

    def review(self):
        H.write(self.state/'CAPTURE.json', self.capture(), exclusive=True)
        evidence = self.root/'independent-evidence.json'; self.put(evidence, {'fixture': True})
        review = dict(schema='r3-formal-independent-postrun-v1', verdict='PASS', independent=True,
            training=str(self.train), queue_sha256=H.QUEUE_PIN, binding_sha256=H.BINDING_PIN,
            capture_sha256=H.sha(self.state/'CAPTURE.json'), files=self.capture()['files'],
            test_read=False, scientific_acceptance=False, evidence_files={str(evidence): H.sha(evidence)},
            checks={k: True for k in ('genuine_train_exit', 'retained_container_identity', 'claim_release_done_identity',
                                    'training_inputs_and_code', 'adapter_provenance', 'final_step_3116')})
        path = self.root/'review.json'; self.put(path, review)
        return path

    def test_wait_and_failure_never_capture_adapter(self):
        self.assertEqual(self.capture()['status'], 'waiting_training')
        self.put(self.train/'TRAIN_EXIT.json', dict(exit_code=1, attempt=1))
        self.assertEqual(self.capture()['status'], 'training_failed')

    def test_incomplete_and_synthetic_completion(self):
        self.put(self.train/'TRAIN_EXIT.json', dict(exit_code=0, attempt=1))
        self.assertEqual(self.capture()['status'], 'waiting_completion_evidence')
        self.complete()
        for name in ('TRAIN_EXIT.json', 'attempts/1/EXIT.json'):
            self.put(self.train/name, dict(exit_code=0, attempt=1, source='retained-container-exit'))
        with self.assertRaisesRegex(ValueError, 'genuine'):
            self.capture()

    def test_capture_requires_real_release_claim_and_seed(self):
        self.complete(); self.assertEqual(self.capture()['status'], 'REVIEW_REQUIRED')
        for relative, field, value in [('attempts/1/RELEASE.json', 'claim_sha256', 'wrong'),
                                       ('attempts/1/LAUNCH_RECEIPT.json', 'plan_sha256', 'wrong'),
                                       ('attempts/1/SUPERVISOR_DONE.json', 'exit_code', 1)]:
            path = self.train/relative; original = path.read_bytes(); doc = H.load(path); doc[field] = value; self.put(path, doc)
            with self.assertRaises(ValueError): self.capture()
            path.write_bytes(original)
        path = self.train/'manifest.json'; doc = H.load(path); doc['args']['seed'] = 3; self.put(path, doc)
        with self.assertRaisesRegex(ValueError, 'manifest'): self.capture()

    def test_adapter_symlink_and_test_path_refused(self):
        self.complete(); (self.train/'adapter/extra').symlink_to(self.model/'config.json')
        with self.assertRaises(ValueError): self.capture()
        with self.assertRaisesRegex(ValueError, 'TEST'): H.sha(self.root/'test.jsonl')

    def test_adapter_changed_after_capture_refused(self):
        self.complete(); saved = self.capture()
        (self.train/'adapter/adapter_model.safetensors').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'capture changed'): H.check_capture(saved, self.binding, self.job, self.plan)

    def test_real_binder_and_idempotent_resume(self):
        self.complete(); review = self.review()
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)):
            result = H.prepare(self.state, review, H.sha(review))
            self.assertEqual(result['status'], 'prepared'); self.assertFalse(result['evaluation_authorized'])
            before = (self.out/'plan.json').read_bytes()
            self.assertEqual(result, H.prepare(self.state, review, H.sha(review)))
            self.assertEqual(before, (self.out/'plan.json').read_bytes())
        spec = H.load(self.out/'plan.json')
        self.assertEqual(spec['execution_review'], 'PENDING')
        self.assertFalse((self.out/'execution.json').exists())

    def test_review_gate_wrong_pin_and_incomplete_checks(self):
        self.complete(); review = self.review()
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)):
            with self.assertRaisesRegex(ValueError, 'pin changed'): H.prepare(self.state, review, 'wrong')
            doc = H.load(review); doc['checks']['retained_container_identity'] = False; self.put(review, doc)
            with self.assertRaisesRegex(ValueError, 'incomplete'): H.prepare(self.state, review, H.sha(review))
        self.assertFalse(self.out.exists()); self.assertFalse((self.state/'PREPARE_INTENT.json').exists())

    def test_uncertain_attempt_and_existing_output_not_adopted(self):
        self.complete(); review = self.review()
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)):
            self.out.mkdir()
            with self.assertRaisesRegex(ValueError, 'already exists'): H.prepare(self.state, review, H.sha(review))
            self.out.rmdir(); self.put(self.state/'PREPARE_INTENT.json', {})
            with self.assertRaisesRegex(ValueError, 'uncertain'): H.prepare(self.state, review, H.sha(review))
        self.assertFalse(self.out.exists())

    def test_partial_binder_failure_never_retried(self):
        self.complete(); review = self.review()
        # Actual binder fails when the base bytes differ; durable intent remains.
        self.put(self.model/'config.json', {'changed': True})
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)):
            with self.assertRaisesRegex(RuntimeError, 'base model changed'): H.prepare(self.state, review, H.sha(review))
            with self.assertRaisesRegex(ValueError, 'uncertain'): H.prepare(self.state, review, H.sha(review))

    def test_changed_review_inventory_refused(self):
        self.complete(); review = self.review(); doc = H.load(review)
        doc['files'][str(self.train/'adapter/adapter_model.safetensors')] = 'substituted'
        self.put(review, doc)
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)):
            with self.assertRaisesRegex(ValueError, 'review differs'): H.prepare(self.state, review, H.sha(review))
        self.assertFalse(self.out.exists())

    def test_adapter_change_during_consumer_fails_without_receipt(self):
        self.complete(); review = self.review(); check = H.check_capture; calls = []
        def changing_check(*args):
            calls.append(1)
            if len(calls) == 2:
                (self.train/'adapter/adapter_model.safetensors').write_bytes(b'substitution during binder')
            return check(*args)
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)), patch.object(H, 'check_capture', side_effect=changing_check):
            with self.assertRaisesRegex(ValueError, 'capture changed'): H.prepare(self.state, review, H.sha(review))
        self.assertTrue((self.state/'PREPARE_INTENT.json').exists())
        self.assertFalse((self.state/'PREPARED.json').exists())

    def test_prepared_spec_tamper_refused_on_resume(self):
        self.complete(); review = self.review()
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)):
            H.prepare(self.state, review, H.sha(review))
            self.put(self.out/'plan.json', {'foreign': True})
            with self.assertRaisesRegex(ValueError, 'receipt changed'): H.prepare(self.state, review, H.sha(review))

    def test_watch_capture_resume_and_tamper(self):
        self.complete()
        with patch.object(H, 'identity', return_value=(self.binding, self.job, self.plan)):
            result = H.watch(self.state, once=True)
            self.assertEqual(result['status'], 'REVIEW_REQUIRED')
            self.assertEqual(H.watch(self.state, once=True), result)
            (self.train/'adapter/adapter_model.safetensors').write_bytes(b'changed')
            with self.assertRaises(ValueError): H.watch(self.state, once=True)


class MonitorTests(unittest.TestCase):
    def test_isolated_sections_are_bounded_and_pinned(self):
        # Compile ONLY new pure functions. Never execute the real monitor or its SSH/cadence block.
        source = Path(__file__).parents[1]/'.local/operations/inspect-once.py'
        tree = ast.parse(source.read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith('formal_')]
        namespace = dict(Path=Path, json=json, hashlib=hashlib, now=dt.datetime.now(dt.timezone.utc))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self_path = root/'small.json'; self_path.write_text('{}')
            self.assertEqual(namespace['formal_json'](self_path, hashlib.sha256(b'{}').hexdigest()), {})
            with self.assertRaisesRegex(ValueError, 'pin changed'): namespace['formal_json'](self_path, 'wrong')
            with self.assertRaisesRegex(ValueError, 'bound'): namespace['formal_json'](self_path, limit=1)
            job = dict(id='formal-k1-seed2', plan=str(root/'training/plan.json'))
            namespace.update(FORMAL_SERVICE=root, FORMAL_QUEUE_PIN='q', FORMAL_BINDING_PIN='b',
                             formal_identity=lambda: ({'jobs': [job]}, {'allowed_jobs': [job['id']]}))
            (root/'digest.json').write_text(json.dumps(dict(jobs={job['id']:dict(status='needs_repair', error='RAW_SECRET')},
                                                          hashes={'large': 'not surfaced'})))
            result = namespace['formal_service']()
            self.assertTrue(result['repair_state'][job['id']]['flagged'])
            self.assertNotIn('RAW_SECRET', json.dumps(result)); self.assertNotIn('large', json.dumps(result))
            self.assertFalse(result['metadata']['service_heartbeat.json']['present'])


if __name__ == '__main__':
    unittest.main()
