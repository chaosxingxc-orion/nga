import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('r3_formal_dev_prepare.py')
SPEC = importlib.util.spec_from_file_location('formal_dev_prepare', SOURCE)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class PreparationContract(unittest.TestCase):
    def test_only_two_output_arguments_and_source_paths_move(self):
        old, new, closure, clean = map(Path, ('/old', '/new', '/closure', '/clean'))
        spec = {'command': ['python3', '--adapter', '/old/adapter', '--out', '/old/results',
                            '--round-dir', '/old/identity', '--partitions', 'dev,calibration'],
                'code_mounts': [{'source': '/closure/r3_code', 'destination': '/run/r3_code', 'readonly': True}],
                'files': {'/closure/r3_code/a.py': 'hash', '/old/adapter/a': 'adapter-hash'},
                'training_variant': {'seed': 3}, 'scientific_acceptance': False}
        original = copy.deepcopy(spec)
        d = M.relocate_spec(spec, old, new, closure, clean, {'/closure/r3_code/a.py': '/clean/r3_code/a.py'})
        self.assertEqual(spec, original)
        self.assertEqual(d['command'], ['python3', '--adapter', '/old/adapter', '--out', '/new/results',
                                       '--round-dir', '/new/identity', '--partitions', 'dev,calibration'])
        self.assertEqual(d['training_variant'], spec['training_variant'])
        self.assertEqual(d['files']['/old/adapter/a'], 'adapter-hash')

    def test_duplicate_or_foreign_output_is_rejected(self):
        for command in [['--out', '/old/results', '--out', '/old/results', '--round-dir', '/old/identity'],
                        ['--out', '/foreign/results', '--round-dir', '/old/identity'],
                        ['--out', '/old/results']]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                M.relocate_spec({'command': command, 'code_mounts': [], 'files': {}},
                                Path('/old'), Path('/new'), Path('/closure'), Path('/clean'), {})

    def test_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'real').write_text('x'); (root/'alias').symlink_to(root/'real')
            with self.assertRaises(ValueError): M.safe(root/'alias')

    def fixture(self, root):
        def put(name, value):
            p = root/name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(value)); return {'path': str(p), 'sha256': M.sha(p)}
        schedule = put('schedule.json', {'nodes': [
            {'id': 'samechip_s2', 'kind': 'training', 'out': '/training'},
            {'id': 'samechip_s2_dev', 'kind': 'dev_calibration_track_t_readout', 'training_id': 'samechip_s2',
             'chip': 1, 'depends_on': ['primary_s2_dev_release']}]})
        spec = put('spec.json', {'training': '/training', 'test_read': False, 'scientific_acceptance': False,
             'training_variant': {'formal_role_identity': {'role': 'samechip_s2', 'chip': 1, 'schedule_sha256': schedule['sha256']}},
             'code_mounts': [], 'files': {}})
        receipt = put('prepared.json', {'status': 'prepared', 'role': 'samechip_s2', 'chip': 1,
            'plan': spec['path'], 'sha256': spec['sha256'], 'evaluation_authorized': False,
            'test_read': False, 'scientific_acceptance': False, 'launch_dependencies': ['primary_s2_dev_release']})
        closure = put('closure/manifest.json', {'code': {}, 'mounts': []})
        cpu = put('cpu.json', {})
        tools = {n: put('tools/'+n, {}) for n in M.TOOLS}
        return {'schema': 'r3-formal-dev-prepare-v1', 'prepared': receipt, 'spec': spec,
                'schedule': schedule, 'closure': closure, 'cpu_template': cpu, 'tools': tools,
                'root': str(root/'fresh'), 'role': 'samechip_s2', 'chip': 1, 'container': 'nga-r3-eng-eval-test'}

    def test_config_accepts_matching_role_and_rejects_scope_or_chip_changes(self):
        with tempfile.TemporaryDirectory() as td, patch.object(M, 'BASE', Path(td)):
            root = Path(td); config = self.fixture(root)
            def inspect(c):
                p = root/'config.json'; p.write_text(json.dumps(c)); return M.inspect_config(p, M.sha(p))
            self.assertEqual(inspect(config)[0]['role'], 'samechip_s2')
            for key, value in [('role', 'diffchip_s2'), ('chip', True), ('chip', 2),
                               ('container', 'other'), ('launch_authorized', True)]:
                mutated = copy.deepcopy(config); mutated[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError): inspect(mutated)
            Path(config['root']).mkdir()
            with self.assertRaises(ValueError): inspect(config)

    def test_changed_receipt_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as td, patch.object(M, 'BASE', Path(td)):
            root=Path(td); config=self.fixture(root); p=root/'config.json';p.write_text(json.dumps(config))
            Path(config['prepared']['path']).write_text('{}')
            with self.assertRaises(ValueError): M.prepare(p, M.sha(p))
            self.assertFalse(Path(config['root']).exists())


if __name__ == '__main__':
    unittest.main()
