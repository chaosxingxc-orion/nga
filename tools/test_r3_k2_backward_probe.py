import functools
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch, Mock
import torch
from torch.utils.checkpoint import checkpoint

spec = importlib.util.spec_from_file_location('probe', Path(__file__).with_name('r3_k2_backward_probe.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class Branch(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.lora_dropout = torch.nn.ModuleDict({'default': torch.nn.Dropout(.05)})
        self.lora_A = torch.nn.ModuleDict({'default': torch.nn.Linear(8, 3, bias=False)})
        self.lora_B = torch.nn.ModuleDict({'default': torch.nn.Linear(3, 8, bias=False)})
        torch.nn.init.zeros_(self.lora_B['default'].weight)

    def forward(self, x):
        return x + 2*self.lora_B['default'](self.lora_A['default'](self.lora_dropout['default'](x)))


class Layer(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.branch = Branch()
        self.gradient_checkpointing = True
        self._gradient_checkpointing_func = functools.partial(checkpoint, use_reentrant=False)

    def forward(self, x):
        return self._gradient_checkpointing_func(self.branch, x)


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = Layer()
    def forward(self, x):
        return self.layer(x)


class ProbeTests(unittest.TestCase):
    def exercise(self, mutate=None, observed=True, bf16=False, changed=False):
        torch.manual_seed(42)
        model = Model().train()
        probe = M.BackwardProbe(torch, model, lambda: M.hashlib.sha256(bytes(torch.get_rng_state().tolist())).hexdigest(),
                                target='layer.branch', checkpoint='layer')
        if observed:
            probe.install()
        grads, endpoints = [], []
        try:
            for phase in range(2):
                if phase and observed:
                    probe.begin_repeat()
                torch.manual_seed(2000006)
                model.zero_grad(set_to_none=True)
                for q in range(3):
                    outputs = []
                    for chunk in range(2):
                        # Includes actual zeros: mask reconstruction from output
                        # would be ambiguous, dispatch mask observation is not.
                        x = torch.arange(32.).reshape(4, 8)/32
                        if changed and phase == 1 and q == 1:
                            x = x + .125
                        if bf16:
                            x = x.reshape(2, 2, 8)
                        with torch.autocast('cpu', dtype=torch.bfloat16, enabled=bf16):
                            outputs.append(model(x.requires_grad_()).sum())
                        if observed:
                            probe.chunk()
                    scores = torch.stack(outputs)
                    if observed:
                        probe.before(scores)
                    (scores.sum()/3).backward()
                    if observed:
                        probe.after()
                grads.append(model.layer.branch.lora_B['default'].weight.grad.clone())
                endpoints.append(torch.get_rng_state().clone())
            if mutate:
                mutate(probe)
            return probe.summary(), grads, endpoints, probe
        finally:
            probe.close()

    def test_real_checkpoint_dropout_cotangent_coverage(self):
        result, _, _, _ = self.exercise()
        self.assertTrue(result['complete'], result['coverage'])
        self.assertTrue(all(x['equal'] for x in result['comparisons']))
        self.assertEqual([x['checkpoint_calls'] for x in result['coverage']], [2, 2])
        masks = [x for x in result['records'][0] if x['key'][-1] == 'dropout_mask']
        self.assertEqual(len(masks), 4)
        self.assertTrue(all(x['observation']['shape'] == [4, 8] for x in masks))

    def test_autocast_3d_records_actual_low_precision_mm_operands(self):
        result, observed, rng, _ = self.exercise(bf16=True)
        self.assertTrue(result['complete'], result['coverage'])
        operands = [x for x in result['records'][0] if x['key'][-1] == 'B_mm_operands']
        self.assertTrue(operands)
        self.assertTrue(all(x['observation'][0]['dtype'] == 'torch.bfloat16' for x in operands))
        _, plain, plain_rng, _ = self.exercise(observed=False, bf16=True)
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(observed+rng, plain+plain_rng)))

    def test_actual_matmul_route_records_operands_operator_and_output_once(self):
        probe = M.BackwardProbe(torch, Model(), lambda: {})
        probe.context = (0, 'forward')
        a = torch.randn(2, 3, 8, dtype=torch.bfloat16)
        b = torch.randn(8, 4, dtype=torch.bfloat16)
        class Count:
            calls = 0
            def __str__(self): return 'aten.matmul.default'
            def __call__(self, *args, **kwargs):
                self.calls += 1
                return torch.ops.aten.matmul.default(*args, **kwargs)
        op = Count()
        result = probe.observe_operation('A', op, (a, b), {})
        self.assertEqual(op.calls, 1)
        records = {k[-1]: v for k,v in probe.records[0].items()}
        self.assertEqual(records['A_mm_operator'], dict(name='aten.matmul.default', kwargs={}))
        self.assertEqual(records['A_mm_operands'], [probe.tensor(a), probe.tensor(b)])
        self.assertEqual(records['A_mm_output'], probe.tensor(result))
        # An observer error after dispatch must not retry the operation.
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            probe.observe_operation('A', op, (a, b), {})
        self.assertEqual(op.calls, 2)
        self.assertFalse(probe.summary()['complete'])
        class Unknown(Count):
            def __str__(self): return 'unknown.linear.default'
        unknown = Unknown()
        before = dict(probe.records[0])
        probe.observe_operation('B', unknown, (a, b), {})
        self.assertEqual(unknown.calls, 1)
        self.assertEqual(before, probe.records[0])

    def test_unknown_linear_route_and_symmetric_operation_omission_fail_closed(self):
        from contextlib import nullcontext
        original = M.BackwardProbe.dispatch
        with patch.object(M.BackwardProbe, 'dispatch',
                          lambda self, scope: original(self, scope) if scope == 'dropout' else nullcontext()):
            result = self.exercise()[0]
        self.assertFalse(result['complete'])
        for phase in result['coverage']:
            self.assertTrue(any(k[-1] == 'A_mm_operands' for k in phase['missing']))
            self.assertTrue(any(k[-1] == 'B_mm_operator' for k in phase['missing']))

    def test_observers_preserve_rng_and_gradients(self):
        _, observed, rng, _ = self.exercise()
        _, plain, plain_rng, _ = self.exercise(observed=False)
        for x, y in zip(observed+ rng, plain+plain_rng):
            self.assertTrue(torch.equal(x, y))

    def test_symmetric_omissions_rejected(self):
        result, _, _, probe = self.exercise()
        for label in ['dropout_mask', 'B_cotangent', 'checkpoint_inputs', 'A_mm_operator', 'B_mm_operator', 'A_mm_operands', 'A_mm_output', 'B_mm_operands', 'B_mm_output', 'A_input', 'checkpoint_rng_exit', 'B_input', 'B_weight', 'B_early_stop']:
            saved = [dict(r) for r in probe.records]
            for records in probe.records:
                for key in list(records):
                    if key[-1] == label:
                        del records[key]
            self.assertFalse(probe.summary()['complete'], label)
            probe.records = saved
        probe.chunk_counts = [0, 0]
        self.assertFalse(probe.summary()['complete'])

    def test_null_leaf_and_extra_events_rejected(self):
        def mutate(probe):
            probe.records[0]['q1', 'incoming_B_gradient'] = None
        self.assertFalse(self.exercise(mutate)[0]['complete'])
        def extra(probe):
            probe.records[0]['unexpected',] = 1
        self.assertFalse(self.exercise(extra)[0]['complete'])

    def test_actual_changed_operand_with_zero_B_is_localized(self):
        result = self.exercise(changed=True)[0]
        self.assertTrue(result['complete'])
        differences = [x['key'] for x in result['comparisons'] if not x['equal']]
        self.assertTrue(any(k[-1] == 'B_input' for k in differences))
        self.assertTrue(any(k[-1] == 'incoming_B_gradient' for k in differences))
        self.assertFalse(any(k[-1] == 'dropout_mask' for k in differences))

    def test_hook_and_wrapper_cleanup(self):
        _, _, _, probe = self.exercise()
        branch = probe.model.layer.branch
        self.assertFalse(probe.restore)
        self.assertFalse(probe.handles)
        self.assertNotIn('forward', branch.lora_B['default'].__dict__)
        self.assertFalse(branch.lora_B['default'].weight._backward_hooks)
        self.assertIsInstance(probe.model.layer._gradient_checkpointing_func, functools.partial)

    def test_changed_operand_is_visible(self):
        def mutate(probe):
            key = next(k for k in probe.records[1] if k[-1] == 'B_cotangent')
            probe.records[1][key] = dict(probe.records[1][key], sha256='changed')
        result = self.exercise(mutate)[0]
        self.assertTrue(result['complete'])
        self.assertEqual(sum(not x['equal'] for x in result['comparisons']), 1)

    def test_recipe_and_budgets_fail_closed(self):
        model = Model()
        model.layer.branch.lora_dropout['default'].p = 0
        probe = M.BackwardProbe(torch, model, lambda: {}, target='layer.branch', checkpoint='layer')
        with self.assertRaisesRegex(ValueError, 'recipe'):
            probe.install()
        probe = M.BackwardProbe(torch, model, lambda: {}, max_events=0)
        with self.assertRaisesRegex(ValueError, 'budget'):
            probe.put(('a',), torch.ones(1))
        self.assertFalse(probe.summary()['complete'])

    def test_unsupported_dropout_without_mask_cannot_complete(self):
        from contextlib import nullcontext
        original = M.BackwardProbe.dispatch
        try:
            M.BackwardProbe.dispatch = lambda self, scope: nullcontext() if scope == 'dropout' else original(self, scope)
            result = self.exercise()[0]
            self.assertFalse(result['complete'])
            self.assertTrue(any(k[-1] == 'dropout_mask' for k in result['coverage'][0]['missing']))
        finally:
            M.BackwardProbe.dispatch = original


class LifecycleTests(unittest.TestCase):
    # Run the actual frozen production start function, real verification,
    # locking and filesystem writes in a disposable clone. Only hostname and
    # process creation are mocked. External data/model hashes are declarations.
    bundle = Path(os.environ.get('K2_REPAIR_BUNDLE',
        '/mnt/cephfs/xingchao/experiments/jev/r3_runs/k2_backward_probe_20261101_v3'))

    def test_production_start_preserves_entire_frozen_inventory(self):
        with tempfile.TemporaryDirectory(prefix='k2-relaunch-') as tmp:
            base = Path(tmp)
            root = base/'r3_runs/repair'
            manifest = self.bundle/'IMMUTABLE_MANIFEST.json'
            names = list(M.load(manifest)) + ['IMMUTABLE_MANIFEST.json'] if manifest.exists() else [
                str(p.relative_to(self.bundle)) for p in self.bundle.rglob('*') if p.is_file()]
            for name in names:
                dest = root/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.bundle/name, dest)
            probe = M.source(root/'tools/r3_k2_backward_probe.py')
            plan = json.loads((root/'plan.json').read_text().replace(str(self.bundle), str(root)))
            probe.atomic(root/'plan.json', plan)
            doc = json.loads((root/'execution.json').read_text().replace(str(self.bundle), str(root)))
            doc.update(allocation=str(base/'CHIP-ALLOCATION.json'), run='r3_runs/repair',
                       benchmark_sha256=probe.sha(root/'plan.json'))
            doc['container'] = 'nga-k2-backward-'+doc['benchmark_sha256'][:16]
            probe.atomic(root/'execution.json', doc)
            pin = probe.sha(root/'execution.json')
            external = {f: h for f, h in plan['files'].items() if not Path(f).is_relative_to(root)}
            real_sha, real_source = probe.sha, probe.source
            def declared_sha(path):
                return external[str(path)] if str(path) in external else real_sha(path)
            def local_source(path):
                module = real_source(path)
                if Path(path).name == 'r3_k2_benchmark_launcher.py':
                    module.BASE = base
                return module
            before = {name: probe.sha(root/name) for name in names}
            with patch.object(probe, 'sha', side_effect=declared_sha), patch.object(probe, 'source', side_effect=local_source):
                launcher = probe.launcher(root/'execution.json', pin)
                with patch.object(launcher.socket, 'gethostname', return_value='k8s-node1'), \
                        patch.object(launcher.subprocess, 'Popen', return_value=types.SimpleNamespace(pid=2147483647)) as spawn:
                    receipt = launcher.start(root/'execution.json', pin)
                    self.assertEqual(spawn.call_count, 1)
                    self.assertTrue(spawn.call_args.kwargs['start_new_session'])
                    self.assertEqual(receipt, probe.load(root/'SUPERVISOR_RECEIPT.json'))
                    relaunch = probe.load(root/'SUPERVISOR_RELAUNCH.json')
                    self.assertEqual(relaunch['command'][2:], [doc['launcher'], 'start', '--plan', str(root/'execution.json'), '--sha256', pin])
                    self.assertEqual(before, {name: probe.sha(root/name) for name in names})
                    # Regression control: the unadapted production atomic write
                    # really corrupts the preparation record in this same test.
                    launcher.atomic = real_source(root/'tools/r3_k2_benchmark_launcher.py').atomic
                    launcher.start(root/'execution.json', pin)
                    changed = [n for n in names if probe.sha(root/n) != before[n]]
                    self.assertEqual(changed, ['RELAUNCH.json'])

    def test_typed_exact_v2_predecessor_and_release_fail_closed(self):
        previous = dict(M.V2_PREDECESSOR)
        base = Path('/mnt/cephfs/xingchao/experiments/jev')
        good = dict(attempt=1, exit_code=0, container_id=previous['container_id'])
        successor = types.SimpleNamespace(predecessor=Mock(return_value=good))
        with patch.object(M, 'sha', return_value=previous['execution_sha256']):
            self.assertEqual(M.released_predecessor({'predecessor': previous}, successor, base), good)
            successor.predecessor.assert_called_with(dict(previous_kind='evaluation', previous_eval=previous['out'], chip=3))
            for key, value in [('kind', 'unknown'), ('out', previous['out']+'-other'),
                               ('execution_sha256', '0'*64), ('container_id', 'wrong')]:
                with self.subTest(key=key), self.assertRaises(ValueError):
                    M.verify_predecessor(dict(previous, **{key: value}), base)
            for result in [None, dict(good, exit_code=1), dict(good, attempt=2), dict(good, container_id='wrong')]:
                successor.predecessor.return_value = result
                with self.subTest(result=result), self.assertRaises(ValueError):
                    M.released_predecessor({'predecessor': previous}, successor, base)
        with patch.object(M, 'sha', return_value='changed'), self.assertRaisesRegex(ValueError, 'v2 predecessor changed'):
            M.verify_predecessor(previous, base)

    def test_recovery_requires_exact_failed_terminal_and_release(self):
        previous = dict(M.V2_RECOVERY_PREDECESSOR)
        base = Path('/mnt/cephfs/xingchao/experiments/jev')
        pins = {'execution.json': previous['execution_sha256'],
                'ENGINEERING_EVAL_EXIT.json': previous['terminal_sha256'],
                'RELEASE.json': previous['release_sha256']}
        good = dict(attempt=1, exit_code=1, container_exit_code=1,
                    container_id=previous['container_id'], release_sha256=previous['release_sha256'])
        successor = types.SimpleNamespace(predecessor=Mock(return_value=good))
        with patch.object(M, 'sha', side_effect=lambda p: pins[Path(p).name]):
            self.assertEqual(M.released_predecessor({'predecessor': previous}, successor, base), good)
            for key, value in [('exit_code', 0), ('exit_code', True), ('container_exit_code', 0),
                               ('container_exit_code', True), ('attempt', 2), ('container_id', 'wrong'),
                               ('release_sha256', 'wrong')]:
                successor.predecessor.return_value = dict(good, **{key: value})
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    M.released_predecessor({'predecessor': previous}, successor, base)
            for key in ['expected_exit_code', 'terminal_sha256', 'release_sha256', 'authorization']:
                invalid = dict(previous); invalid.pop(key)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    M.verify_predecessor(invalid, base)
        with patch.object(M, 'sha', return_value='changed'), self.assertRaises(ValueError):
            M.verify_predecessor(previous, base)

    def test_main_start_and_supervise_enforce_release_before_launch(self):
        for op in ('start', 'supervise'):
            launcher = types.SimpleNamespace(BASE=Path('/unused'), start=Mock(), supervise=Mock())
            with patch('sys.argv', ['probe', op, '--plan', '/unused/execution.json', '--sha256', 'pin']), \
                    patch.object(M, 'launcher', return_value=launcher), \
                    patch.object(M, 'load', return_value={'out': '/unused', 'predecessor': M.V2_PREDECESSOR}), \
                    patch.object(M, 'source'), \
                    patch.object(M, 'released_predecessor', side_effect=ValueError('not released')) as gate:
                with self.assertRaisesRegex(ValueError, 'not released'):
                    M.main()
                gate.assert_called_once()
                launcher.start.assert_not_called()
                launcher.supervise.assert_not_called()


if __name__ == '__main__':
    unittest.main()
