import copy
import tempfile
from pathlib import Path
import unittest
from tools import r3_pt_r0_execution_prepare as P


class DerivationTests(unittest.TestCase):
    def setUp(self):
        self.source = {'training': '/train', 'model': '/model', 'adapter': '/train/adapter',
                       'training_variant': {'arm': 'k1-pt', 'seed': 3},
                       'files': {p: 'digest' for p in ['/train/plan.json', '/train/manifest.json',
                                 '/train/TRAIN_EXIT.json', '/model/weights', '/train/adapter/weights',
                                 '/old/tasks', '/old/scorer']}, 'command': ['old']}
        self.closure = {'evaluation_profile': 'track_t_pt_r0', 'test_read': False,
                        'scientific_acceptance': False, 'data': {'/r0/data': 'data'},
                        'code': {'/old/code': {'snapshot': '/r0/code', 'sha256': 'code'}},
                        'mounts': [{'source': '/r0', 'destination': '/code', 'readonly': True}]}
        self.launcher = type('Launcher', (), {'expected_command': staticmethod(lambda s, o: ['t_score', 'r0', str(o)])})

    def test_preserves_training_drops_unrelated_dev_population(self):
        before = copy.deepcopy(self.source)
        d = P.derive(self.source, self.closure, Path('/new'), self.launcher)
        self.assertEqual(self.source, before)
        self.assertEqual(d['training_variant'], before['training_variant'])
        self.assertEqual(set(d['files']), {'/train/plan.json', '/train/manifest.json',
                         '/train/TRAIN_EXIT.json', '/model/weights', '/train/adapter/weights',
                         '/r0/data', '/r0/code'})
        self.assertEqual(d['command'], ['t_score', 'r0', '/new'])

    def test_non_pt_and_bool_seed_rejected(self):
        for value in ({'arm': 'k1', 'seed': 3}, {'arm': 'k1-pt', 'seed': True}):
            self.source['training_variant'] = value
            with self.assertRaises(ValueError):
                P.derive(self.source, self.closure, Path('/new'), self.launcher)

    def test_test_or_acceptance_scope_rejected(self):
        for field in ('test_read', 'scientific_acceptance'):
            c = dict(self.closure, **{field: True})
            with self.assertRaises(ValueError):
                P.derive(self.source, c, Path('/new'), self.launcher)

    def test_training_plan_cannot_be_dropped(self):
        del self.source['files']['/train/plan.json']
        with self.assertRaises(ValueError):
            P.derive(self.source, self.closure, Path('/new'), self.launcher)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'actual').write_text('x'); (root/'link').symlink_to(root/'actual')
            with self.assertRaises(ValueError): P.safe(root/'link')


if __name__ == '__main__':
    unittest.main()
