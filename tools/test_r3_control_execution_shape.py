"""Real prospective control plan shape, with synthetic completion metadata only."""
import argparse
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from tools import r3_posttrain_eval_launcher as L

ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_controls_prospective_20261102_v1')

class ControlExecutionShape(unittest.TestCase):
    def spec(self, root, plan):
        path=root/'plan.json';path.write_text(json.dumps(plan))
        manifest={'arm':'k1','model_path':plan['model'], 'args':{'arm':'k1','seed':plan['seed'],
                  'model_path':plan['model'],'drop_state':plan['control_arm']=='K1-QO'}}
        (root/'manifest.json').write_text(json.dumps(manifest))
        return {'schema':'r3-posttrain-dev-spec-v1','training':str(root),'model':plan['model'],
                'training_variant':{'arm':plan['control_arm'].lower(),'seed':plan['seed'],'training_plan_sha256':L.sha(path)},
                'files':{str(path):L.sha(path)}}
    def plans(self):
        return [json.loads((ROOT/p/'plan.json').read_text()) for p in ('qo/seed2','pt/seed2','pt/seed3')]
    def test_three_actual_frozen_shapes_accept_without_invented_arm(self):
        for plan in self.plans():
            self.assertNotIn('arm',plan)
            with self.subTest(control=plan['control_arm'],seed=plan['seed']), tempfile.TemporaryDirectory() as td:
                root=Path(td);spec=self.spec(root,plan);before=(root/'plan.json').read_bytes()
                L.verify_control_manifest(spec)
                self.assertEqual((root/'plan.json').read_bytes(),before)
                explicit=copy.deepcopy(plan);explicit['arm']='k1'
                L.verify_control_manifest(self.spec(root,explicit))
    def test_contradictory_and_ambiguous_argv_rejected(self):
        base=self.plans()[0]
        changes={
          'explicit_arm':lambda p:p.update(arm='k2'),
          'null_arm':lambda p:p.update(arm=None),
          'objective':lambda p:p['command'].__setitem__(p['command'].index('--arm')+1,'k2'),
          'duplicate_arm':lambda p:p['command'].extend(['--arm','k1']),
          'abbreviated_arm':lambda p:p['command'].__setitem__(p['command'].index('--arm'),'--ar'),
          'equals_arm':lambda p:p['command'].__setitem__(p['command'].index('--arm'),'--arm=k1'),
          'missing_arm':lambda p:p['command'].__delitem__(slice(p['command'].index('--arm'),p['command'].index('--arm')+2)),
          'duplicate_seed':lambda p:p['command'].extend(['--seed','2']),
          'wrong_seed':lambda p:p['command'].__setitem__(p['command'].index('--seed')+1,'3'),
          'boolean_seed':lambda p:p.update(seed=True),
          'duplicate_model':lambda p:p['command'].extend(['--model-path',p['model']]),
          'wrong_model':lambda p:p['command'].__setitem__(p['command'].index('--model-path')+1,'/other/model'),
          'abbreviated_model':lambda p:p['command'].__setitem__(p['command'].index('--model-path'),'--model'),
          'duplicate_drop':lambda p:p['command'].append('--drop-state'),
          'equals_drop':lambda p:p['command'].__setitem__(p['command'].index('--drop-state'),'--drop-state=true'),
          'missing_drop':lambda p:p['command'].remove('--drop-state'),
          'wrong_entry':lambda p:p['command'].__setitem__(2,'/other/train.py'),
          'wrong_container_kind':lambda p:p.update(control_arm='K1-PT'),
          'unlabelled_control':lambda p:p.update(control_arm='K1'),
        }
        for name,change in changes.items():
            with self.subTest(case=name),tempfile.TemporaryDirectory() as td:
                plan=copy.deepcopy(base);change(plan);spec=self.spec(Path(td),plan)
                with self.assertRaises(RuntimeError):L.verify_control_manifest(spec)
    def test_manifest_and_spec_mismatch_rejected(self):
        for change in ('objective','model','seed','drop','variant_seed','plan_pin'):
            with self.subTest(case=change),tempfile.TemporaryDirectory() as td:
                root=Path(td);spec=self.spec(root,self.plans()[0]);manifest=json.loads((root/'manifest.json').read_text())
                if change=='objective':manifest['args']['arm']='k2'
                elif change=='model':manifest['model_path']='/other'
                elif change=='seed':manifest['args']['seed']=3
                elif change=='drop':manifest['args']['drop_state']=False
                elif change=='variant_seed':spec['training_variant']['seed']=True
                elif change=='plan_pin':spec['files'][str(root/'plan.json')]='0'*64
                (root/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(RuntimeError):L.verify_control_manifest(spec)
    def test_short_aliases_change_real_parser_but_launcher_rejects(self):
        trainer = ROOT/'qo/seed2/code/train_r3.py'
        tree = ast.parse(trainer.read_text())
        parser_node = next(n for n in tree.body
                           if isinstance(n, ast.FunctionDef) and n.name == 'parse_args')
        namespace = {'argparse': argparse, '__doc__': 'CPU-only exact parser'}
        exec(compile(ast.Module(body=[parser_node], type_ignores=[]),
                     str(trainer), 'exec'), namespace)
        cases = [
            (0, ['--a', 'k2'], 'arm', 'k2'),
            (0, ['--se', '3'], 'seed', 3),
            (0, ['--mo', '/other/model'], 'model_path', '/other/model'),
            (1, ['--dr'], 'drop_state', True),
        ]
        for index, extra, field, expected in cases:
            with self.subTest(alias=extra), tempfile.TemporaryDirectory() as td:
                plan = self.plans()[index]
                plan['command'] += extra
                parsed = namespace['parse_args'](plan['command'][3:])
                self.assertEqual(getattr(parsed, field), expected)
                with self.assertRaises(RuntimeError):
                    L.verify_control_manifest(self.spec(Path(td), plan))

    def test_complete_argv_grammar_rejects_unknown_arity_and_extra_tokens(self):
        cases = [
            ['--unknown', 'x'], ['--'], ['stray'], ['--device=npu:0'],
            ['--device'], ['--device', '--no-merge'], ['--no-merge', 'false'],
            ['--epochs', '2'], ['--grad-ckpt'], ['--max', '4096'],
            ['--symbol-file', 'x', 'stray'], ['--device', '-x'],
        ]
        for extra in cases:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as td:
                plan = self.plans()[0]
                plan['command'] += extra
                with self.assertRaises(RuntimeError):
                    L.verify_control_manifest(self.spec(Path(td), plan))

    def test_pt_rejects_dropped_state_and_base(self):
        for change in ('drop','base'):
            with self.subTest(case=change),tempfile.TemporaryDirectory() as td:
                plan=self.plans()[1]
                if change=='drop':plan['command'].append('--drop-state')
                else:
                    plan['model']=L.R0_MODEL+'-Base';plan['command'][plan['command'].index('--model-path')+1]=plan['model']
                with self.assertRaises(RuntimeError):L.verify_control_manifest(self.spec(Path(td),plan))

if __name__=='__main__':unittest.main()
