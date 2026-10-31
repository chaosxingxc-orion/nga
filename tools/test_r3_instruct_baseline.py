"""Synthetic instruct K0 preparation with the real launcher verifier."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


B = module('r3_baseline_eval_prepare')
L = module('r3_posttrain_eval_launcher')


class InstructBaseline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.base = self.root / 'data'
        self.model = self.root / 'models/Qwen__Qwen3.5-0.8B'
        self.model.mkdir(parents=True); (self.model / 'model.safetensors').write_bytes(b'synthetic')
        for obj, field, value in ((L, 'BASE', self.base), (L, 'R0_MODEL', str(self.model))):
            ctx = patch.object(obj, field, value); ctx.start(); self.addCleanup(ctx.stop)
        ctx = patch.object(B, 'launcher_module', return_value=L); ctx.start(); self.addCleanup(ctx.stop)
        self.closure = self.root / 'closure'; self.closure.mkdir()
        doc = {'evaluation_profile': 'track_kt', 'data': {}, 'code': {}, 'mounts': []}
        for name in L.allowed_data_files({'evaluation_profile': 'track_kt'}):
            p = Path(name); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('{}\n')
            doc['data'][name] = L.sha(p)
        for name in ('r3_code', 'r0_code'):
            root = self.closure / name; root.mkdir(); p = root / 'fixture.py'; p.write_text('X=1\n')
            doc['code'][str(p)] = {'snapshot': str(p), 'sha256': L.sha(p)}
            doc['mounts'].append({'source': str(root), 'destination': str(self.base / name), 'readonly': True})
        (self.closure / 'manifest.json').write_text(json.dumps(doc))
        self.out = self.base / 'r3_runs/instruct-k0'

    def test_registered_instruct_is_untrained_k0_and_verifies(self):
        B.prepare(self.closure, self.model, self.out)
        spec = json.loads((self.out / 'plan.json').read_text())
        L.verify_spec(spec, self.out)
        self.assertEqual(spec['baseline_role'], 'instruct_control')
        self.assertEqual(spec['baseline_identity']['arm'], 'K0')
        self.assertNotIn('training', spec); self.assertNotIn('adapter', spec)
        self.assertNotIn('--adapter', spec['command'])
        self.assertEqual(spec['command'][spec['command'].index('--partitions') + 1], 'dev,calibration')
        bad = copy.deepcopy(spec)
        bad['command'][bad['command'].index('--partitions') + 1] = 'test'
        with self.assertRaisesRegex(RuntimeError, 'command differs'): L.verify_spec(bad, self.out)

    def test_instruct_same_basename_at_other_path_refused(self):
        other = self.root / 'foreign/Qwen__Qwen3.5-0.8B'
        with self.assertRaisesRegex(ValueError, 'registered instruct'): B.prepare(self.closure, other, self.out)
        self.assertFalse(self.out.exists())

    def test_existing_base_family_still_prepares(self):
        model = self.root / 'models/Qwen__Qwen3.5-2B-Base'; model.mkdir()
        (model / 'model.safetensors').write_bytes(b'synthetic base')
        B.prepare(self.closure, model, self.out)
        spec = json.loads((self.out / 'plan.json').read_text())
        self.assertEqual(spec['baseline_role'], 'base'); L.verify_spec(spec, self.out)


if __name__ == '__main__': unittest.main()
