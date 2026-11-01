import functools
import importlib.util
from pathlib import Path
import unittest
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

    def test_observers_preserve_rng_and_gradients(self):
        _, observed, rng, _ = self.exercise()
        _, plain, plain_rng, _ = self.exercise(observed=False)
        for x, y in zip(observed+ rng, plain+plain_rng):
            self.assertTrue(torch.equal(x, y))

    def test_symmetric_omissions_rejected(self):
        result, _, _, probe = self.exercise()
        for label in ['dropout_mask', 'B_cotangent', 'checkpoint_inputs', 'B_mm_operands', 'A_input', 'checkpoint_rng_exit', 'B_input', 'B_weight', 'B_early_stop']:
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


if __name__ == '__main__':
    unittest.main()
