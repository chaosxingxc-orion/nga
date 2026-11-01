"""Synthetic CPU retention/provenance tests; never actual Ascend evidence."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ['TORCH_DEVICE_BACKEND_AUTOLOAD'] = '0'
import torch

spec = importlib.util.spec_from_file_location('retained_probe', Path(__file__).with_name('r3_k2_retained_tensor_probe.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
PIN = 'a'*64


class RetainedTests(unittest.TestCase):
    def fixture(self, root, changed=False):
        store = M.Retention(root, torch, PIN)
        records = [{}, {}]
        for i in M.required_identities():
            label = i['key'][-1]
            x = torch.arange(24, dtype=torch.float32).reshape(2, 3, 4)/16
            g = torch.ones(2, 3, 5)
            if changed and i['repeat'] == 1:
                g[0, 0, 0] += .25
            w = torch.zeros(5, 4).T
            inc = g.reshape(-1, 5).T @ x.reshape(-1, 4)
            values = {'dropout_mask': torch.tensor([0, 255, 7], dtype=torch.uint8),
                      'A_mm_operands': [x, torch.eye(4)], 'B_mm_operands': [x, w],
                      'A_mm_output': x, 'B_mm_output': torch.zeros(2, 3, 5),
                      'B_cotangent': g, 'producer_operand': torch.tensor(2.),
                      'producer_incoming': g/2, 'producer_outgoing': g,
                      'prior_B_gradient': torch.ones(5, 4), 'incoming_B_gradient': inc,
                      'post_B_gradient': torch.ones(5, 4) if i['question'] == 0 else 1+inc}
            v = values[label]
            if i['slot']:
                v = v[int(i['slot'])]
            meta = store.save(i['pair'], i['repeat'], i['key'], v, i['slot'])
            if i['pair'] == 'observed':
                r = records[i['repeat']]; k = tuple(i['key'])
                if i['slot']:
                    r.setdefault(k, [None, None])[int(i['slot'])] = meta
                else:
                    r[k] = meta
        for r in records:
            r[(M.CHECKPOINT, 0, 'backward', M.TARGET, 'producer_operator')] = dict(name='aten.mul.Tensor', kwargs={},
                left={k:v for k,v in r[(M.CHECKPOINT, 0, 'backward', M.TARGET, 'producer_incoming')].items() if k != 'sha256'},
                output={k:v for k,v in r[(M.CHECKPOINT, 0, 'backward', M.TARGET, 'producer_outgoing')].items() if k != 'sha256'})
            for stage in M.STAGES:
                prefix = (M.CHECKPOINT, 0, stage, M.TARGET)
                for part in ('A', 'B'):
                    r[(*prefix, part+'_mm_operator')] = dict(name='aten.matmul.default', kwargs={})
                r[(*prefix, 'dropout_mask_op')] = 'aten.native_dropout.default'
                r[(*prefix, 'checkpoint_exit_kind')] = 'returned' if stage == 'forward' else '_StopRecomputationError'
        events = dict(complete=True, producer=[{'0': dict(node='MulBackward0', edge=0, search_nodes=2)} for _ in range(2)], records=[[dict(key=list(k), observation=v) for k, v in r.items()] for r in records])
        context = dict(full_step_questions=12, q1_chunks=[1, 1], seed=2,
                       q0_prefix_preserved=True, full_step_denominator_preserved=True)
        index = store.finish(events, context)
        return store, index

    def check(self, root, pin):
        return M.validate(root, pin, PIN, torch)

    def mutate(self, root, fn):
        d = M.load(root/'INDEX.json'); fn(d); M.atomic(root/'INDEX.json', d)
        return M.sha(root/'INDEX.json')

    def test_actual_cpu_values_hashes_layout_and_vjp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'retained'; store, pin = self.fixture(root)
            d = self.check(root, pin)
            self.assertEqual(d['tensors'], 50)
            self.assertTrue(all(x['values_equal'] for x in d['cross_repeat']))
            self.assertTrue(all(x['values_equal'] for x in d['forward_recompute']))
            for row in d['cpu_vjp_interpretation']:
                for key in ('cpu_float64_B_vjp', 'accumulation', 'producer_edge', 'cpu_producer_multiply'):
                    self.assertTrue(row[key]['values_equal'], (key, row))
            weights = [e for e in store.entries if e['identity']['key'][-1] == 'B_mm_operands' and e['identity']['slot'] == '1']
            self.assertTrue(all(e['metadata']['stride'] == [1, 4] for e in weights))

    def test_changed_cotangent_numeric_magnitude_independently_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'retained'; _, pin = self.fixture(root, changed=True)
            d = self.check(root, pin)
            row = next(x for x in d['cross_repeat'] if x['identity']['key'][-1] == 'B_cotangent')
            self.assertEqual(row['mismatched_elements'], 1)
            self.assertEqual(row['max_abs_difference'], .25)
            self.assertTrue(all(r['cpu_float64_B_vjp']['values_equal'] for r in d['cpu_vjp_interpretation']))

    def test_payload_byte_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'retained'; store, pin = self.fixture(root)
            p = root/store.entries[0]['file']; b = bytearray(p.read_bytes()); b[0] ^= 1; p.write_bytes(b)
            with self.assertRaisesRegex(ValueError, 'checksum'):
                self.check(root, pin)

    def test_missing_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'retained'; store, pin = self.fixture(root)
            (root/store.entries[0]['file']).unlink()
            with self.assertRaises(FileNotFoundError): self.check(root, pin)

    def test_index_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'retained'; _, pin = self.fixture(root)
            with (root/'INDEX.json').open('a') as f: f.write(' ')
            with self.assertRaisesRegex(ValueError, 'index checksum'): self.check(root, pin)

    def test_rehashed_manifest_corruptions_fail_closed(self):
        mutations = {
            'identity': lambda d: d['entries'][0]['identity'].update(question=1),
            'plan': lambda d: d['entries'][0].update(plan_sha256='b'*64),
            'duplicate': lambda d: d['entries'].append(d['entries'][0]),
            'symmetric_missing': lambda d: d.update(entries=[e for e in d['entries'] if e['identity']['key'][-1] != 'B_cotangent']),
            'operator': lambda d: next(e for e in d['events']['records'][0] if e['key'][-1] == 'B_mm_operator')['observation'].update(name='unknown.op'),
            'extent': lambda d: next(e for e in d['events']['records'][0] if e['key'][-1] == 'checkpoint_exit_kind').update(observation='unknown'),
            'producer': lambda d: d['events']['producer'][0]['0'].update(edge=1),
            'context': lambda d: d['context'].update(full_step_questions=2),
            'layout': lambda d: next(e for e in d['entries'] if e['identity']['pair'] == 'observed')['metadata'].update(stride=[99, 1]),
            'total': lambda d: d.update(total_bytes=d['total_bytes']+1),
            'traversal': lambda d: d['entries'][0].update(file='../outside.bin'),
            'dtype': lambda d: d['entries'][0]['metadata'].update(dtype='torch.complex64'),
            'oversize': lambda d: d['entries'][0].update(bytes=M.MAX_TENSOR+1),
            'event_hash': lambda d: d['events']['records'][0][0]['observation'].update(sha256='0'*64),
        }
        for name, fn in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)/'retained'; self.fixture(root)
                pin = self.mutate(root, fn)
                with self.assertRaises(ValueError): self.check(root, pin)

    def test_extra_payload_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'retained'; store, pin = self.fixture(root)
            (root/'unexpected.bin').write_bytes(b'!')
            with self.assertRaisesRegex(ValueError, 'extra/missing'): self.check(root, pin)
            (root/'unexpected.bin').unlink()
            p = root/store.entries[0]['file']; target = Path(tmp)/'target'; p.rename(target); p.symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'unsafe'): self.check(root, pin)

    def test_allowlist_budget_missing_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = M.Retention(Path(tmp)/'retained', torch, PIN)
            k = ('q0', 'post_B_gradient')
            with self.assertRaisesRegex(ValueError, 'missing'): store.save('observed', 0, k, None)
            with self.assertRaisesRegex(ValueError, 'allowlist'): store.save('observed', 0, ('q2', 'post_B_gradient'), torch.ones(1))
            with patch.object(M, 'MAX_BYTES', 3):
                with self.assertRaisesRegex(ValueError, 'budget'): store.save('observed', 0, k, torch.ones(1))
            store.save('observed', 0, k, torch.ones(1))
            with self.assertRaisesRegex(ValueError, 'duplicate'): store.save('observed', 0, k, torch.ones(1))

    def test_root_no_test_and_missing_parent_activation(self):
        for p in ('/tmp/TEST/x', '/tmp/Test.json', '/tmp/test/data', '/tmp/x/../y'):
            with self.assertRaises(ValueError): M.safe(p)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError): M.activation_guard(Path(tmp), PIN)
            M.atomic(Path(tmp)/'ACTIVATION.json', dict(allow_npu=True))
            with self.assertRaisesRegex(ValueError, 'parent activation'): M.activation_guard(Path(tmp), PIN)

    def test_activation_binds_independent_review_release_and_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); pred = root/'predecessor'; (pred/'attempts/1').mkdir(parents=True)
            M.atomic(root/'review.json', dict(plan_sha256=PIN, prepared_accepted=True, reviewer='independent'))
            M.atomic(pred/'execution.json', dict(run='r3_runs/instruct_k0_chip3_20261101_v1', container='instruct'))
            M.atomic(pred/'ENGINEERING_EVAL_EXIT.json', dict(exit_code=0, attempt=1))
            M.atomic(pred/'attempts/1/RELEASE.json', dict(chip=3, run='r3_runs/instruct_k0_chip3_20261101_v1',
                     container='instruct-a1', container_id='cid', exit_code=0))
            M.atomic(pred/'attempts/1/LAUNCH_RECEIPT.json', dict(id='cid', sha256=M.sha(pred/'execution.json')))
            pins = {str(p.relative_to(pred)): M.sha(p) for p in pred.rglob('*.json')}
            a = dict(schema='k2-retained-parent-activation-v1', plan_sha256=PIN, authorized_by='parent',
                     allow_npu=True, test_read=False, no_TEST=True, independent_prepared_review_passed=True,
                     review_path=str(root/'review.json'), review_sha256=M.sha(root/'review.json'),
                     predecessor_pins=pins, automatic_rerun=False)
            M.atomic(root/'ACTIVATION.json', a)
            orig_sha, orig_load = M.sha, M.load
            frozen_pred = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_k0_chip3_20261101_v1')
            def route(p):
                p = Path(p)
                return pred/p.relative_to(frozen_pred) if p.is_relative_to(frozen_pred) else p
            with patch.object(M, 'sha', lambda p: orig_sha(route(p))), patch.object(M, 'load', lambda p: orig_load(route(p))):
                self.assertEqual(M.activation_guard(root, PIN), a)
                release = orig_load(pred/'attempts/1/RELEASE.json'); release['container_id'] = 'other'
                M.atomic(pred/'attempts/1/RELEASE.json', release)
                with self.assertRaisesRegex(ValueError, 'release pin'): M.activation_guard(root, PIN)
                a['predecessor_pins']['attempts/1/RELEASE.json'] = orig_sha(pred/'attempts/1/RELEASE.json')
                M.atomic(root/'ACTIVATION.json', a)
                with self.assertRaisesRegex(ValueError, 'container identity'): M.activation_guard(root, PIN)

    def test_bf16_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = M.Retention(Path(tmp)/'retained', torch, PIN)
            v = torch.tensor([1., 1.0078125, -2.], dtype=torch.bfloat16)
            store.save('observed', 0, ('q0', 'post_B_gradient'), v)
            data = (store.root/store.entries[0]['file']).read_bytes()
            self.assertTrue(torch.equal(torch.frombuffer(bytearray(data), dtype=torch.bfloat16), v))


class IntegrationTests(unittest.TestCase):
    def exercise(self, observed=True, early_stop=False):
        import functools
        from torch.utils.checkpoint import checkpoint, set_checkpoint_early_stop
        class Branch(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.lora_dropout = torch.nn.ModuleDict({'default': torch.nn.Dropout(.05)})
                self.lora_A = torch.nn.ModuleDict({'default': torch.nn.Linear(8, 3, bias=False)})
                self.lora_B = torch.nn.ModuleDict({'default': torch.nn.Linear(3, 8, bias=False)})
                torch.nn.init.zeros_(self.lora_B['default'].weight)
            def forward(self, x):
                return x+2*self.lora_B['default'](self.lora_A['default'](self.lora_dropout['default'](x)))
        class Layer(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.branch = Branch(); self.gradient_checkpointing = True
                self._gradient_checkpointing_func = functools.partial(checkpoint, use_reentrant=False)
            def forward(self, x): return self._gradient_checkpointing_func(self.branch, x)
        class Model(torch.nn.Module):
            def __init__(self): super().__init__(); self.layer = Layer()
            def forward(self, x): return self.layer(x)
            def named_modules(self, *args, **kwargs):
                return iter([(M.CHECKPOINT, self.layer), (M.TARGET, self.layer.branch)])
        torch.manual_seed(2); model = Model().train()
        gradients, rngs = [], []
        with tempfile.TemporaryDirectory() as tmp:
            store = M.Retention(Path(tmp)/'retained', torch, PIN)
            probe = M.make_probe(M.frozen(), torch, model, lambda: {}, store)
            if observed: probe.install()
            try:
                for phase in (0, 1):
                    if phase and observed: probe.begin_repeat()
                    torch.manual_seed(2000006); model.zero_grad(set_to_none=True)
                    for q in range(3):
                        with set_checkpoint_early_stop(early_stop):
                            y = model(torch.arange(32.).reshape(4, 8).requires_grad_()/32)
                        if observed: probe.chunk(); probe.before(y)
                        (y.sum()/3).backward()
                        if observed: probe.after()
                    gradients.append(model.layer.branch.lora_B['default'].weight.grad.clone())
                    rngs.append(torch.get_rng_state().clone())
                summary = probe.summary()
                if observed:
                    if early_stop:
                        self.assertFalse(summary['complete'])
                        self.assertLess(len(store.entries), 44)
                    else:
                        self.assertTrue(summary['complete'], summary['coverage'])
                        self.assertEqual(len(store.entries), 44)
                    self.assertEqual(summary['producer'][0][0]['node'], 'MulBackward0')
                return gradients, rngs
            finally:
                probe.close()
                self.assertFalse(probe.handles)
                self.assertFalse(probe.restore)

    def test_real_cpu_autograd_retention_and_observer_control(self):
        a, ar = self.exercise(); b, br = self.exercise(False)
        self.assertTrue(all(torch.equal(x, y) for x, y in zip(a+ar, b+br)))

    def test_real_cpu_default_early_stop_is_explicit_incomplete_extent(self):
        self.exercise(early_stop=True)

    def test_actual_3d_matmul_retains_dispatched_bf16_operands_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = M.Retention(Path(tmp)/'retained', torch, PIN)
            probe = M.make_probe(M.frozen(), torch, None, lambda: {}, store)
            probe.context = (0, 'forward')
            class Matmul:
                calls = 0
                def __str__(self): return 'aten.matmul.default'
                def __call__(self, *args, **kwargs):
                    self.calls += 1
                    return torch.ops.aten.matmul.default(*args, **kwargs)
            op = Matmul()
            a = torch.arange(24.).reshape(2, 3, 4).to(torch.bfloat16)
            b = torch.ones(5, 4, dtype=torch.bfloat16).T
            value = probe.observe_operation('B', op, (a, b), {})
            self.assertEqual(op.calls, 1)
            self.assertEqual(len(store.entries), 3)
            self.assertEqual(store.entries[1]['metadata']['stride'], [1, 4])
            payload = (store.root/store.entries[0]['file']).read_bytes()
            self.assertTrue(torch.equal(torch.frombuffer(bytearray(payload), dtype=torch.bfloat16).reshape(a.shape), a))
            self.assertEqual(list(value.shape), [2, 3, 5])

    def test_unknown_dispatch_fails_before_execution(self):
        class Unknown:
            called = False
            def __str__(self): return 'unknown.linear.default'
            def __call__(self, *args, **kwargs): self.called = True
        with tempfile.TemporaryDirectory() as tmp:
            store = M.Retention(Path(tmp)/'retained', torch, PIN)
            probe = M.make_probe(M.frozen(), torch, None, lambda: {}, store)
            op = Unknown()
            with self.assertRaisesRegex(ValueError, 'unknown dispatch'):
                probe.observe_operation('B', op, (), {})
            self.assertFalse(op.called)


if __name__ == '__main__':
    unittest.main()
