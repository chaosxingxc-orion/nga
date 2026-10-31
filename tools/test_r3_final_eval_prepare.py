"""CPU checks of generated real evaluator control flow; no real data or model."""
import ast
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('prepare', HERE/'r3_final_eval_prepare.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
spec = importlib.util.spec_from_file_location('r3_test_execution_guard', HERE/'r3_test_execution_guard.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
SOURCE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code/full_eval_r3.py')


class Preparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():
            raise unittest.SkipTest('pinned source closure not installed')
        cls.source = SOURCE.read_bytes()
        cls.generated = P.transform(cls.source)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.round = self.root/'round'; self.round.mkdir()
        self.final = self.round/'FINAL.json'; self.final.write_text('{}')
        self.owner = dict(model_sha256='a'*64, execution_sha256='b'*64,
                          final_sha256=hashlib.sha256(self.final.read_bytes()).hexdigest(),
                          run_dir=str(self.root/'out'))
        self.args = SimpleNamespace(partitions='calibration,test', stages='k', limit=0,
            limit_groups=0, shard=0, num_shards=1, k_only='', b4_base=None, unit_tag='',
            dtype='float32', no_hf32=True, require_record_grade=True, device='npu',
            model_path=str(self.root/'model'), adapter=None, round_dir=str(self.round), out=self.owner['run_dir'])
        self.core = SimpleNamespace(TestLockRefusal=ValueError,
            sha256_file=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest())
        self.tl = SimpleNamespace(model_identity=Mock(return_value={'sha256':'a'*64}),
                                 authorize_test_read=Mock(return_value='synthetic-ticket'))
        self.producer = Mock(return_value={'track_k':{'operator_fit':'preserved'}})
        self.env = dict(C=self.core, TL=self.tl, _run_full_deferred=self.producer)
        tree = ast.parse(self.generated)
        bridge = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name in ('run_full', '_check_test_leases', 'run_guarded_test')], type_ignores=[])
        exec(compile(bridge, '<generated-real-bridge>', 'exec'), self.env)
        self.modules = patch.dict(sys.modules, {'r3_test_transaction':SimpleNamespace(G=G)})
        self.modules.start(); self.addCleanup(self.modules.stop)

    def leases(self, stack):
        return {s:stack.enter_context(G.execution(self.round, suite=s, **self.owner))
                for s in ('decision-v7','transfer-v4')}

    def test_guarded_entry_keeps_calibration_and_defers_publication(self):
        with ExitStack() as stack:
            leases = self.leases(stack)
            report, tickets = self.env['run_guarded_test'](self.args, 'scorer', leases=leases, owner=self.owner)
        self.assertEqual(report['track_k']['operator_fit'], 'preserved')
        self.assertEqual(len(tickets), 2)
        self.assertEqual(self.tl.authorize_test_read.call_count, 2)
        self.producer.assert_called_once()
        self.assertFalse((self.round/'TEST-READS.log').exists())

    def test_ordinary_test_entry_refuses_before_producer(self):
        with self.assertRaisesRegex(ValueError, 'guarded transaction'):
            self.env['run_full'](self.args, 'scorer')
        self.producer.assert_not_called(); self.tl.authorize_test_read.assert_not_called()

    def test_missing_calibration_or_non_record_settings_refuse(self):
        for field, value in [('partitions','test'), ('stages','k,report'), ('dtype','bfloat16'),
                             ('require_record_grade',False), ('limit',1), ('num_shards',2)]:
            with self.subTest(field=field):
                args = SimpleNamespace(**vars(self.args)); setattr(args,field,value)
                with self.assertRaises(ValueError):
                    self.env['run_guarded_test'](args,'scorer',leases={},owner=self.owner)
        self.producer.assert_not_called(); self.tl.authorize_test_read.assert_not_called()

    def test_released_lease_and_changed_final_refuse_before_authorization(self):
        with ExitStack() as stack:
            leases = self.leases(stack)
            self.final.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'FINAL changed'):
                self.env['run_guarded_test'](self.args,'scorer',leases=leases,owner=self.owner)
            self.final.write_text('{}')
        with self.assertRaisesRegex(ValueError,'live reserved'):
            self.env['run_guarded_test'](self.args,'scorer',leases=leases,owner=self.owner)
        self.tl.authorize_test_read.assert_not_called()

    def test_source_pin_and_no_overwrite(self):
        with self.assertRaises(ValueError): P.transform(self.source+b'\n')
        out=self.root/'prepared'
        manifest=P.prepare(SOURCE,out)
        self.assertFalse(manifest['deployable'])
        self.assertEqual(hashlib.sha256((out/'full_eval_r3.py').read_bytes()).hexdigest(),manifest['generated_sha256'])
        with self.assertRaises(ValueError): P.prepare(SOURCE,out)
        self.assertEqual(SOURCE.read_bytes(),self.source)

    def test_numerical_functions_unchanged_and_publication_calls_removed(self):
        def functions(source):
            return {n.name:ast.dump(n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
        before,after=functions(self.source),functions(self.generated)
        for name,value in before.items():
            if name!='run_full': self.assertEqual(after[name],value,name)
        body=next(n for n in ast.parse(self.generated).body
                  if isinstance(n,ast.FunctionDef) and n.name=='_run_full_deferred')
        calls=[n.func.attr for n in ast.walk(body) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertNotIn('record_test_read',calls)
        self.assertNotIn('authorize_test_read',calls)
        self.assertIn('refuse_harness_identity',calls)
        self.assertIn('write_unit_manifest',calls)


if __name__=='__main__': unittest.main()
