import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.util.spec_from_file_location('eval_launcher', Path(__file__).with_name('r3_posttrain_eval_launcher.py'))
L = importlib.util.module_from_spec(loader); loader.loader.exec_module(L)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.base_patch = patch.object(L, 'BASE', self.base); self.base_patch.start(); self.addCleanup(self.base_patch.stop)
        self.out = self.base / 'r3_runs/eval'; self.out.mkdir(parents=True)
        self.training = self.base / 'training'; self.training.mkdir()
        self.files = {}
        def put(path, value=b'fixture'):
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(value)
            self.files[str(path)] = L.sha(path)
            return str(path)
        put(self.training / 'manifest.json', b'{"summary":{"final_step":3116}}')
        put(self.training / 'TRAIN_EXIT.json', b'{"exit_code":0}')
        model = self.base / 'model'; put(model / 'model.safetensors')
        adapter = self.training / 'adapter'; put(adapter / 'adapter_model.safetensors')
        data = [put(self.base / 'KEV/manifest.json'), put(self.base / 'KEV/decision-v7/train.jsonl')]
        for suite, split in [('decision-v7', 'dev'), ('decision-v7', 'calibration'), ('transfer-v4', 'dev')]:
            data.append(put(self.base / 'KEV' / suite / (split + '.jsonl')))
            if split == 'dev': data.append(put(self.base / 'KEV' / suite / (split + '.variants.jsonl')))
        mounts = []
        for name in ('r3_code', 'r0_code'):
            directory = self.base / 'closure' / name
            put(directory / 'code.py')
            mounts.append({'source': str(directory), 'destination': str(self.base / name), 'readonly': True})
        self.spec = {'schema': 'r3-posttrain-dev-spec-v1', 'image_sha256': L.IMAGE, 'network': 'none',
                     'test_read': False, 'scientific_acceptance': False, 'training_exit': {'exit_code': 0},
                     'training_variant': {'arm': 'k2'}, 'training': str(self.training), 'model': str(model),
                     'adapter': str(adapter), 'files': self.files, 'readonly_data_mounts': data, 'code_mounts': mounts}
        self.spec['command'] = L.expected_command(self.spec, self.out)
        self.path = self.out / 'plan.json'
        self.path.write_text(json.dumps(self.spec))

    def test_valid_contract_and_test_partition_injection_refused(self):
        L.verify_spec(self.spec, self.out)
        self.spec['command'][self.spec['command'].index('--partitions') + 1] = 'test'
        with self.assertRaisesRegex(RuntimeError, 'command differs'): L.verify_spec(self.spec, self.out)

    def test_unhashed_code_and_changed_weights_refused(self):
        extra = Path(self.spec['code_mounts'][0]['source']) / 'extra.py'; extra.write_text('x=1')
        with self.assertRaisesRegex(RuntimeError, 'unbound code'): L.verify_spec(self.spec, self.out)
        extra.unlink()
        (Path(self.spec['model']) / 'model.safetensors').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'dependency changed'): L.verify_spec(self.spec, self.out)

    def test_training_incomplete_and_new_adapter_file_refused(self):
        file = self.training / 'manifest.json'; file.write_text('{"summary":{"final_step":100}}')
        self.files[str(file)] = L.sha(file)
        with self.assertRaisesRegex(RuntimeError, 'incomplete training'): L.verify_spec(self.spec, self.out)
        (Path(self.spec['adapter']) / 'unexpected.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'unbound model/adapter'): L.verify_spec(self.spec, self.out)

    def test_bind_freezes_tools_and_docker_has_narrow_mounts(self):
        execution, pin = L.bind(self.path, 2, 'nga-r3-eng-eval-fixture')
        plan = L.load(execution)
        with patch.object(L, '__file__', plan['launcher']):
            L.verify(execution, pin)
        cmd = L.docker_command(plan, self.spec, execution, pin, 1)
        self.assertIn('--network=none', cmd); self.assertNotIn('--rm', cmd)
        self.assertIn('/dev/davinci2', cmd); self.assertNotIn('/dev/davinci0', cmd)
        mounts = [cmd[i + 1] for i, x in enumerate(cmd) if x == '--mount']
        self.assertTrue(all('readonly' in x for x in mounts if 'KEV/' in x))
        self.assertFalse(any(f'src={self.base},' in x for x in mounts))
        self.assertEqual(self.spec['command'][self.spec['command'].index('--k-only') + 1].count(',') + 1, 11)
        self.path.write_text(self.path.read_text() + ' ')
        with patch.object(L, '__file__', plan['launcher']):
            with self.assertRaisesRegex(RuntimeError, 'specification changed'): L.verify(execution, pin)

    def test_existing_results_cannot_be_bound_as_fresh(self):
        (self.out / 'results').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'fresh output'): L.bind(self.path, 2, 'nga-r3-eng-eval-fixture')
        self.assertFalse((self.out / 'execution.json').exists())

    def test_driver_records_startup_failure(self):
        execution, pin = L.bind(self.path, 2, 'nga-r3-eng-eval-fixture')
        attempt = self.out / 'attempts/1'; attempt.mkdir(parents=True)
        with patch.object(L.subprocess, 'Popen', side_effect=OSError('fixture spawn error')):
            with self.assertRaises(OSError): L.drive(execution, pin, 1)
        self.assertEqual(L.load(self.out / 'ENGINEERING_EVAL_EXIT.json')['exit_code'], 125)
        self.assertFalse(L.load(attempt / 'EXIT.json')['scientific_acceptance'])


if __name__ == '__main__': unittest.main()
