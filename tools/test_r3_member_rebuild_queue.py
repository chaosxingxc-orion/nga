import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).with_name('r3_member_rebuild_queue.py')
S = importlib.util.spec_from_file_location('queue', P)
Q = importlib.util.module_from_spec(S)
S.loader.exec_module(Q)


class QueueEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.r = Path(self.tmp.name)
        self.producer = self.r/'producer'
        (self.producer/'jobs/pt').mkdir(parents=True)
        self.report = self.producer/'report.json'
        Q.write(self.report, {'sample': 'synthetic'})
        self.pq = self.producer/'queue.json'
        Q.write(self.pq, {'jobs': [{'id': 'pt', 'kind': 'report', 'output': str(self.report)}]})
        self.end = self.producer/'jobs/pt/EXIT.json'
        Q.write(self.end, {'exit_code': 0, 'output_sha256': Q.sha(self.report), 'scientific_acceptance': False})
        self.path = self.r/'queue.json'
        self.code = {str(self.r/n): n for n in ('r3_selection_report.py', 'r3_campaign_sources.py',
                                               'r3_final_campaign.py', 'r3_model_inventory.py')}
        self.q = {'code': self.code, 'closure_manifest': {'path': '/closure', 'sha256': 'c'}}
        Q.write(self.path, self.q)
        self.pin = Q.sha(self.path)
        self.expected = {'role': 'control', 'arm': 'K1-PT', 'seed': 3,
                         'base': '/model', 'adapter': '/seed3/adapter'}
        self.job = {'id': 'pt', 'producer_queue': str(self.pq), 'producer_queue_sha256': Q.sha(self.pq),
                    'terminal': str(self.end), 'report': str(self.report), 'expected': self.expected,
                    'base_inventory': {'path': '/base-inventory', 'sha256': 'b'},
                    'adapter_inventory': {'path': '/adapter-inventory', 'sha256': 'a'}}
        for name in ('base_inventory', 'adapter_inventory'):
            ip = self.r/(name+'.json')
            inv = {'root': name, 'files': {'synthetic': {'sha256': 'x'}}}
            Q.write(ip, {'inventory': inv, 'inventory_sha256': Q.canonical_pin(inv)})
            self.job[name] = {'path': str(ip), 'sha256': Q.sha(ip)}
        self.out = self.r/'member'
        self.out.mkdir()
        bindings = Q.producer(self.job)
        self.req = {'queue': {'path': str(self.path), 'sha256': self.pin}, 'job_id': 'pt',
                    'expected': self.expected, 'producer': bindings,
                    'entry': {'report': bindings['report'], 'base_inventory': self.job['base_inventory'],
                              'adapter_inventory': self.job['adapter_inventory']},
                    'scientific_acceptance': False, 'test_read': False}
        Q.write(self.out/'request.json', self.req)
        self.common = {'queue_sha256': self.pin, 'job_id': 'pt',
                       'request_sha256': Q.sha(self.out/'request.json'),
                       'scientific_acceptance': False, 'test_read': False}
        Q.write(self.out/'INTENT.json', self.common)
        self.member = {'role': 'control', 'arm': 'K1-PT',
                       'model': {'base_path': '/model', 'path': '/seed3/adapter'},
                       'training': {'seed': 3, 'arm': 'K1-PT', 'adapter_path': '/seed3/adapter'}}
        self.payload = {'report': bindings['report'],
            'inventories': {name: Q.load(self.job[name]['path'])['inventory_sha256']
                            for name in ('base_inventory', 'adapter_inventory')},
            'code': {'report_tool': {'path': str(self.r/'r3_selection_report.py'), 'sha256': 'r3_selection_report.py'},
                     'closure_manifest': self.q['closure_manifest'], 'consumer_sha256': 'r3_campaign_sources.py',
                     'structure_sha256': 'r3_final_campaign.py', 'inventory_sha256': 'r3_model_inventory.py'},
            'reconstructed_report_sha256': Q.canonical_pin(Q.load(self.report)),
            'source_snapshot': {'files': {e['path']: e['sha256'] for e in self.req['entry'].values()},
                                'trees': {'tree': []}, 'models': {'model': {}}},
            'training': self.member['training']}
        self.member['verified_evidence_sha256'] = Q.canonical_pin(self.payload)
        self.member['model']['base_inventory_sha256'] = self.payload['inventories']['base_inventory']
        Q.write(self.out/'evidence.json', dict(self.common, member=self.member, evidence=self.payload))
        self.result = dict(self.common, producer=bindings, outputs={'evidence.json': Q.sha(self.out/'evidence.json')})
        self.finish()
        self.source_member = copy.deepcopy(self.member)
        self.source_payload = copy.deepcopy(self.payload)
        replay = patch.object(Q, 'reconstruct', side_effect=lambda req,q:
                              (copy.deepcopy(self.source_member), copy.deepcopy(self.source_payload)))
        self.replay = replay.start()
        self.addCleanup(replay.stop)

    def finish(self, exit_code=0):
        Q.write(self.out/'RESULT.json', self.result)
        Q.write(self.out/'EXIT.json', dict(self.common, exit_code=exit_code, result_sha256=Q.sha(self.out/'RESULT.json')))

    def check(self):
        return Q.completed(self.out, self.job, self.path, self.pin)

    def test_valid_completion(self):
        self.assertEqual(self.check()['state'], 'producer_complete')
        self.replay.assert_called_once()

    def test_bool_or_bare_terminal_rejected(self):
        self.finish(False)
        with self.assertRaises(ValueError): self.check()
        Q.write(self.out/'EXIT.json', {'exit_code': 0})
        with self.assertRaises(ValueError): self.check()

    def test_empty_and_extra_outputs_rejected_even_rehashed(self):
        for outputs in ({}, {'evidence.json': Q.sha(self.out/'evidence.json'), 'extra': 'a'}):
            self.result['outputs'] = outputs
            self.finish()
            with self.assertRaises(ValueError): self.check()

    def test_wrong_seed_under_seed3_path_rejected(self):
        self.member['training']['seed'] = 2
        Q.write(self.out/'evidence.json', dict(self.common, member=self.member))
        self.result['outputs']['evidence.json'] = Q.sha(self.out/'evidence.json')
        self.finish()
        with self.assertRaisesRegex(ValueError, 'seed'): self.check()

    def test_producer_mapping_and_rehash_tamper_rejected(self):
        Q.write(self.pq, {'jobs': [{'id': 'pt', 'kind': 'report', 'output': '/other'}]})
        with self.assertRaises(ValueError): self.check()
        self.job['producer_queue_sha256'] = Q.sha(self.pq)
        with self.assertRaisesRegex(ValueError, 'mapping'): Q.producer(self.job)

    def test_symlink_terminal_and_exclusive_intent(self):
        saved = self.end.with_name('original.json')
        self.end.rename(saved)
        self.end.symlink_to(saved)
        with self.assertRaisesRegex(ValueError, 'unsafe'): self.check()
        with self.assertRaises(FileExistsError): Q.write(self.out/'INTENT.json', {}, exclusive=True)

    def test_source_loader_ignores_pyc_and_rejects_unpinned_child(self):
        path = Path(__file__).with_name('r3_campaign_sources.py')
        import types
        m = types.ModuleType('C'); m.__file__ = str(path)
        paths = [path, path.with_name('r3_final_campaign.py'), path.with_name('r3_model_inventory.py')]
        m._SOURCE_PINS = {str(p): Q.sha(p) for p in paths}
        exec(compile(Q.read(path), str(path), 'exec'), m.__dict__)
        helper = self.r/'helper.py'
        helper.write_text('answer = 7\n')
        import py_compile
        py_compile.compile(str(helper), cfile=str(helper.with_suffix('.pyc')))
        helper.write_text('answer = 9\n')
        m._SOURCE_PINS[str(helper)] = Q.sha(helper)
        self.assertEqual(m.module(helper, 'helper').answer, 9)
        helper.write_text('answer = 8\n')
        with self.assertRaisesRegex(ValueError, 'not pinned'): m.module(helper, 'helper')

    def test_persisted_failure_prevents_reconsidering_producer(self):
        # A complete fixture with a persisted failure must never be declared done.
        failure = dict(self.common, state='failed_no_retry', error='prior mismatch')
        Q.write(self.out/'FAILURE.json', failure, exclusive=True)
        with self.assertRaisesRegex(ValueError, 'persisted failure'):
            self.check()

    def test_spoofed_failure_success_rejected(self):
        f = dict(self.common, state='producer_complete')
        with self.assertRaisesRegex(ValueError, 'persisted failure'):
            Q.failure_state(f, 'pt', self.pin)

    def test_missing_reconstruction_payload_rejected(self):
        Q.write(self.out/'evidence.json', dict(self.common, member=self.member))
        self.result['outputs']['evidence.json'] = Q.sha(self.out/'evidence.json')
        self.finish()
        with self.assertRaisesRegex(ValueError, 'payload'): self.check()

    def test_duplicate_output_owner_rejected(self):
        d = Q.load(self.pq); d['jobs'].append(dict(d['jobs'][0], id='other'))
        Q.write(self.pq, d); self.job['producer_queue_sha256'] = Q.sha(self.pq)
        with self.assertRaisesRegex(ValueError, 'multiple owners'): Q.producer(self.job)

    def test_single_buffer_hash_and_parse(self):
        original = Q.read(self.end)
        changed = json.dumps({'exit_code': 1}).encode()
        with patch.object(Q, 'read', side_effect=[original, changed]) as reader:
            doc, pin = Q.snapshot(self.end)
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(doc['exit_code'], 0)
        self.assertEqual(pin, __import__('hashlib').sha256(original).hexdigest())

    def test_bootstrap_rejects_changed_executed_source(self):
        import subprocess, sys
        target = self.r/'controller.py'
        target.write_text('raise RuntimeError("must not execute")\n')
        result = subprocess.run([sys.executable, '-P', '-c', Q.BOOTSTRAP, str(target), '0'*64],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('controller bytes changed', result.stderr)
        self.assertNotIn('RuntimeError: must not execute', result.stderr)

    def republish(self, doc):
        Q.write(self.out/'evidence.json', doc)
        self.result['outputs']['evidence.json'] = Q.sha(self.out/'evidence.json')
        self.finish()

    def test_foreign_envelope_rejected_after_rehash(self):
        for key in ('job_id', 'queue_sha256'):
            d = dict(self.common, member=self.member, evidence=self.payload)
            d[key] = 'foreign'
            self.republish(d)
            with self.assertRaisesRegex(ValueError, 'envelope'): self.check()

    def test_recovered_snapshot_and_member_forgery_rejected(self):
        for change in ('model_hash', 'tree_root', 'model_kind', 'steps'):
            member, evidence = copy.deepcopy(self.source_member), copy.deepcopy(self.source_payload)
            if change == 'model_hash': evidence['source_snapshot']['models'] = {'model': {'wrong': 'hash'}}
            if change == 'tree_root': evidence['source_snapshot']['trees'] = {'unrelated': []}
            if change == 'model_kind': member['model']['kind'] = 'forged'
            if change == 'steps':
                member['training']['training_variant'] = {'total_steps': 1}
                evidence['training'] = copy.deepcopy(member['training'])
            member['verified_evidence_sha256'] = Q.canonical_pin(evidence)
            self.republish(dict(self.common, member=member, evidence=evidence))
            with self.assertRaisesRegex(ValueError, 'actual source reconstruction'): self.check()

    def test_receipt_changed_during_rebuild_cannot_enter_cache(self):
        def rebuild(req, q):
            doc = Q.load(self.out/'evidence.json')
            doc['job_id'] = 'foreign'
            self.republish(doc)
            return self.source_member, self.source_payload
        self.replay.side_effect = rebuild
        with self.assertRaisesRegex(ValueError, 'changed during reconstruction'): self.check()

    def test_cached_success_cannot_revive_after_failure(self):
        cache = {'pt': self.check()}
        saved = Q.read(self.out/'evidence.json')
        Q.write(self.out/'evidence.json', {'changed': True})
        with self.assertRaisesRegex(ValueError, 'receipt changed'):
            Q.cached_state(self.out, self.job, self.pin, cache)
        self.assertNotIn('pt', cache)
        (self.out/'evidence.json').write_bytes(saved)
        Q.write(self.out/'FAILURE.json', dict(self.common, state='failed_no_retry'), exclusive=True)
        # Even a stale cache supplied by a caller cannot override the failure.
        cache['pt'] = {'state': 'producer_complete'}
        state = Q.cached_state(self.out, self.job, self.pin, cache)
        self.assertEqual(state['state'], 'failed_no_retry')
        self.assertNotIn('pt', cache)


if __name__ == '__main__':
    unittest.main()
