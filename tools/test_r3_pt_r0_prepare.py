"""Synthetic end-to-end PT/R0 preparation/bind; no NPU or real datasets."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def module(name):
    p = Path(__file__).with_name(name + '.py')
    s = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


F = module('r3_pt_r0_prepare')
L = module('r3_posttrain_eval_launcher')
P = module('r3_posttrain_eval_plan')


class PTR0(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.base = self.root / 'data'
        self.model = self.root / 'instruct'; self.model.mkdir()
        (self.model / 'model.safetensors').write_bytes(b'synthetic weights')
        for obj, attr, value in [(L, 'BASE', self.base), (L, 'R0_MODEL', str(self.model)),
                                  (P, 'PT_MODEL', str(self.model))]:
            ctx = patch.object(obj, attr, value); ctx.start(); self.addCleanup(ctx.stop)
        ctx = patch.object(F, 'launcher', return_value=L); ctx.start(); self.addCleanup(ctx.stop)
        self.source = self.root / 'r0'; self.source.mkdir()
        spec = {'schema': 'r3-baseline-dev-spec-v1', 'evaluation_profile': 'track_t_r0',
                'model': str(self.model), 'image_sha256': L.IMAGE, 'network': 'none',
                'test_read': False, 'scientific_acceptance': False, 'files': {}, 'code_mounts': []}
        spec['readonly_data_mounts'] = sorted(L.allowed_data_files(spec))
        for filename in spec['readonly_data_mounts']:
            p = Path(filename); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('{}\n')
            spec['files'][filename] = L.sha(p)
        for name in ('r3_code', 'r0_code', 'r1_code'):
            root = self.source / name; root.mkdir(); p = root / 'fixture.py'; p.write_text('X = 1\n')
            spec['files'][str(p)] = L.sha(p)
            spec['code_mounts'].append({'source': str(root), 'destination': str(self.base / name), 'readonly': True})
        spec['command'] = L.expected_command(spec, self.source)
        self.source_spec = spec; self.plan = self.source / 'plan.json'
        self.plan.write_text(json.dumps(spec)); self.closure = self.root / 'closure'

    def prepare(self):
        return F.prepare(self.plan, L.sha(self.plan), self.closure)

    def test_template_prepares_and_binds_real_spec(self):
        original = self.plan.read_bytes(); result = self.prepare()
        self.assertFalse(result['scientific_acceptance']); self.assertEqual(self.plan.read_bytes(), original)
        training = self.root / 'training'; training.mkdir(); adapter = training / 'adapter'; adapter.mkdir()
        for name in ('adapter_config.json', 'adapter_model.safetensors'):
            (adapter / name).write_text('{}')
        plan = {'arm': 'k1', 'control_arm': 'K1-PT', 'seed': 3, 'model': str(self.model),
                'command': ['train'], 'image_sha256': L.IMAGE,
                'files': {str(p): L.sha(p) for p in self.model.iterdir()}}
        manifest = {'arm': 'k1', 'model_path': str(self.model), 'summary': {'final_step': 3116},
                    'args': {'arm': 'k1', 'model_path': str(self.model), 'seed': 3, 'drop_state': False}}
        for name, value in [('plan.json', plan), ('manifest.json', manifest), ('TRAIN_EXIT.json', {'exit_code': 0})]:
            (training / name).write_text(json.dumps(value))
        out = self.base / 'r3_runs/pt-s3'
        prepared = P.prepare(training, self.closure, out)
        self.assertEqual(prepared['status'], 'prepared')
        spec = json.loads((out / 'plan.json').read_text())
        L.verify_spec(spec, out)
        path, pin = L.bind(out / 'plan.json', 2, 'nga-r3-eng-eval-pt-fixture')
        self.assertEqual(L.sha(path), pin)
        execution = json.loads(path.read_text())
        cmd = L.docker_command(execution, spec, path, pin, 1)
        self.assertIn('type=bind,src=' + str(training / 'manifest.json') + ',dst=' + str(training / 'manifest.json') + ',readonly', cmd)
        self.assertEqual(spec['command'][spec['command'].index('--stages') + 1], 't_score')
        self.assertEqual(spec['command'][spec['command'].index('--track-t-config') + 1], 'r0')
        self.assertEqual(spec['command'][spec['command'].index('--out') + 1], str(out / 'results'))
        self.assertNotIn('--k-only', spec['command'])
        altered = copy.deepcopy(spec); altered['command'][altered['command'].index('--partitions') + 1] = 'test'
        with self.assertRaisesRegex(RuntimeError, 'command differs'):
            L.verify_spec(altered, out)

    def test_refuses_wrong_role_model_seed_and_baseline(self):
        spec = {'schema': 'r3-posttrain-dev-spec-v1', 'evaluation_profile': 'track_t_pt_r0',
                'model': str(self.model), 'adapter': '/adapter', 'training_variant': {'arm': 'k1-pt', 'seed': 2}}
        for key, value in [('arm', 'K1-QO'), ('arm', 'K1'), ('seed', 1), ('seed', True),
                           ('model', '/base'), ('schema', 'r3-baseline-dev-spec-v1')]:
            bad = copy.deepcopy(spec)
            if key in ('arm', 'seed'): bad['training_variant'][key] = value
            else: bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(RuntimeError, 'PT R0 requires'):
                L.expected_command(bad, Path('/out'))

    def test_changed_code_rejected_before_creating_output(self):
        (self.source / 'r3_code/fixture.py').write_text('X = 2\n')
        with self.assertRaisesRegex(ValueError, 'source code changed'):
            self.prepare()
        self.assertFalse(self.closure.exists())

    def test_unbound_extra_code_and_wrong_source_pin_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source plan pin'):
            F.prepare(self.plan, '0' * 64, self.closure)
        (self.source / 'r1_code/extra.py').write_text('X=1\n')
        with self.assertRaisesRegex(ValueError, 'unbound'):
            self.prepare()

    def test_test_input_and_writable_mount_rejected(self):
        for change in ('data', 'mount'):
            d = copy.deepcopy(self.source_spec)
            if change == 'data': d['readonly_data_mounts'].append('/test.jsonl')
            else: d['code_mounts'][0]['readonly'] = False
            self.plan.write_text(json.dumps(d))
            with self.subTest(change=change), self.assertRaises(ValueError): self.prepare()
            self.assertFalse(self.closure.exists())


if __name__ == '__main__': unittest.main()
