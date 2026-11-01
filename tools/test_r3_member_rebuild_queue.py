import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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
        Q.write(self.path, {})
        self.pin = Q.sha(self.path)
        self.expected = {'role': 'control', 'arm': 'K1-PT', 'seed': 3,
                         'base': '/model', 'adapter': '/seed3/adapter'}
        self.job = {'id': 'pt', 'producer_queue': str(self.pq), 'producer_queue_sha256': Q.sha(self.pq),
                    'terminal': str(self.end), 'report': str(self.report), 'expected': self.expected,
                    'base_inventory': {'path': '/base-inventory', 'sha256': 'b'},
                    'adapter_inventory': {'path': '/adapter-inventory', 'sha256': 'a'}}
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
        Q.write(self.out/'evidence.json', dict(self.common, member=self.member))
        self.result = dict(self.common, producer=bindings, outputs={'evidence.json': Q.sha(self.out/'evidence.json')})
        self.finish()

    def finish(self, exit_code=0):
        Q.write(self.out/'RESULT.json', self.result)
        Q.write(self.out/'EXIT.json', dict(self.common, exit_code=exit_code, result_sha256=Q.sha(self.out/'RESULT.json')))

    def check(self):
        return Q.completed(self.out, self.job, self.path, self.pin)

    def test_valid_completion(self):
        self.assertEqual(self.check()['state'], 'producer_complete')

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


if __name__ == '__main__':
    unittest.main()
