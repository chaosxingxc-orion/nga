import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('r0_prepare', Path(__file__).with_name('r3_r0_prepare.py'))
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)


class R0Preparation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.base = self.root / 'base'; self.model = self.root / 'model'; self.out = self.root / 'out'
        self.base.mkdir(); self.model.mkdir(); self.out.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(P, 'BASE', self.base).start(); patch.object(P, 'MODEL', self.model).start()
        self.data = {}
        for directory, sources in P.TASKS.items():
            for source in sources:
                path = self.base / directory / (source + '.jsonl'); path.parent.mkdir(exist_ok=True); path.write_text('{}\n'); self.data[str(path)] = P.sha(path)
        manifest = self.base / 'manifest.json'; manifest.write_text('{}'); self.data[str(manifest)] = P.sha(manifest)
        files = {}
        for name in ('code', 'r0_code', 'r1_code'):
            folder = self.out / name; folder.mkdir(); path = folder / 'module.py'; path.write_text('X=1\n'); files[str(path)] = P.sha(path)
        weight = self.model / 'model.safetensors'; weight.write_bytes(b'fixture')
        complete=self.model/'.complete';complete.write_text(P.REVISION+'\n')
        model_files={str(weight):P.sha(weight),str(complete):P.sha(complete)}
        self.doc = {'schema': 'r3-r0-gating-preparation-v1', 'out': str(self.out), 'model': P.model_identity(self.model,model_files),
                    'image_sha256': P.IMAGE, 'network': 'none', 'roles': P.ROLES[:], 'records_per_role': 102654, 'track_t_config': 'r0', 'limit_groups': 0, 'limit': 0,
                    'candidate_test_read': False, 'scientific_acceptance': False, 'ready_to_launch': False, 'num_shards': 32,
                    'commands': P.commands(self.out, self.model, 32), 'split_policy': {'tau': 'full group70 train fitting rows', 'evaluation': 'whole group70 heldout', 'halves': False, 'tie_rule': 'r0_published'},
                    'data': self.data, 'files': files, 'model_files': model_files,
                    'population_by_file': {p: 14664 + (i == 0)*6 for i,p in enumerate(self.data) if p != str(manifest)},
                    'required_code_mounts': [{'source': str(self.out / n), 'destination': str(self.base / n), 'readonly': True} for n in ('r0_code','r1_code')]}
        self.path = self.out / 'PREPARATION.json'
        P.write(self.path, self.doc); self.pin = P.sha(self.path)

    def test_complete_preparation_validates_but_never_authorizes_launch(self):
        result = P.validate(self.path, self.pin)
        self.assertTrue(result['validated']); self.assertFalse(result['ready_to_launch'])
        self.assertEqual(len(self.doc['commands']['score']), 32)
        self.assertFalse(any('r0rescore_worker' in x for cmd in self.doc['commands']['score'] for x in cmd))

    def test_missing_role_limited_population_or_changed_split_refused(self):
        for key,value in [('roles',P.ROLES[:2]),('limit_groups',1),('limit',1),('track_t_config','r3'),('records_per_role',102653)]:
            d=copy.deepcopy(self.doc);d[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): P.validate_contract(d)
        d=copy.deepcopy(self.doc);d['commands']['score'][0] += ['--limit-groups','1']
        with self.assertRaisesRegex(ValueError,'command differs'): P.validate_contract(d)

    def test_changed_data_code_or_weights_refused(self):
        for name in [next(iter(self.data)),next(iter(self.doc['files'])),next(iter(self.doc['model_files']))]:
            path=Path(name); old=path.read_bytes();path.write_bytes(old+b'changed')
            with self.subTest(path=name),self.assertRaisesRegex(ValueError,'dependency changed'): P.validate(self.path,self.pin)
            path.write_bytes(old)

    def test_false_model_identity_refused_even_with_new_manifest_pin(self):
        d=copy.deepcopy(self.doc);d['model']['sha256']='0'*64;P.write(self.path,d)
        with self.assertRaisesRegex(ValueError,'aggregate identity differs'): P.validate(self.path,P.sha(self.path))

    def test_extra_code_or_removed_data_cannot_hide_behind_manifest_pin(self):
        extra=self.out/'code/extra.py';extra.write_text('X=2')
        with self.assertRaisesRegex(ValueError,'unbound code inventory'): P.validate(self.path,self.pin)
        extra.unlink();d=copy.deepcopy(self.doc);del d['data'][next(iter(self.data))];P.write(self.path,d)
        with self.assertRaisesRegex(ValueError,'data inventory differs'): P.validate(self.path,P.sha(self.path))


if __name__ == '__main__': unittest.main()
