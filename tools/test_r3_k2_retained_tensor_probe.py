"""Synthetic CPU retention/provenance tests; never actual Ascend evidence."""
import importlib.util
import hashlib
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
                right=dict(kind='Tensor', **r[(M.CHECKPOINT, 0, 'forward', M.TARGET, 'producer_operand')]),
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
                self.assertEqual(row['backward_input_status'], 'UNRESOLVED_BACKWARD_INPUT')
                self.assertTrue(all(v['values_equal'] for v in row['cpu_float64_B_vjp_references'].values()))
                for key in ('accumulation', 'producer_edge', 'cpu_producer_multiply'):
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
            self.assertTrue(all(all(v['values_equal'] for v in r['cpu_float64_B_vjp_references'].values()) for r in d['cpu_vjp_interpretation']))

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
            with self.assertRaisesRegex(ValueError, 'checksum'): self.check(root, pin)

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

    def activation_fixture(self, root, accepted=True, terminal_pin=None):
        pred = root/'predecessor'; (pred/'attempts/1').mkdir(parents=True)
        fixed = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_k0_chip3_20261101_v1')
        M.atomic(root/'review.json', dict(plan_sha256=PIN, prepared_accepted=accepted, reviewer='independent'))
        M.atomic(pred/'execution.json', dict(schema='r3-engineering-posttrain-execution-v1',
            run='r3_runs/instruct_k0_chip3_20261101_v1', out=str(fixed), chip=3,
            container='nga-r3-eng-eval-instruct-k0-chip3-20261101-v1', test_read=False, scientific_acceptance=False))
        execution_pin = M.sha(pred/'execution.json')
        M.atomic(pred/'ENGINEERING_EVAL_EXIT.json', dict(exit_code=0, attempt=1,
            plan_sha256=execution_pin if terminal_pin is None else terminal_pin, scientific_acceptance=False))
        M.atomic(pred/'attempts/1/RELEASE.json', dict(chip=3, run='r3_runs/instruct_k0_chip3_20261101_v1',
            container='nga-r3-eng-eval-instruct-k0-chip3-20261101-v1-a1', container_id='cid', exit_code=0))
        M.atomic(pred/'attempts/1/LAUNCH_RECEIPT.json', dict(id='cid', sha256=execution_pin))
        pins = {str(p.relative_to(pred)): M.sha(p) for p in pred.rglob('*.json')}
        a = dict(schema='k2-retained-parent-activation-v1', plan_sha256=PIN, authorized_by='parent',
            allow_npu=True, test_read=False, no_TEST=True, independent_prepared_review_passed=True,
            review_path=str(root/'review.json'), review_sha256=M.sha(root/'review.json'),
            predecessor_pins=pins, automatic_rerun=False)
        M.atomic(root/'ACTIVATION.json', a)
        original = M.checked_bytes
        def route(path, *args, **kwargs):
            p = Path(path)
            return original(pred/p.relative_to(fixed) if p.is_relative_to(fixed) else p, *args, **kwargs)
        return a, pred, route

    def test_activation_binds_independent_review_release_and_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); a, pred, route = self.activation_fixture(root)
            with patch.object(M, 'checked_bytes', route):
                self.assertEqual(M.activation_guard(root, PIN), a)
                release = M.load(pred/'attempts/1/RELEASE.json'); release['container_id'] = 'other'
                M.atomic(pred/'attempts/1/RELEASE.json', release)
                with self.assertRaisesRegex(ValueError, 'checksum'): M.activation_guard(root, PIN)
                a['predecessor_pins']['attempts/1/RELEASE.json'] = M.sha(pred/'attempts/1/RELEASE.json')
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



class RepairRegressions(unittest.TestCase):
    # Reuse fixture helpers without rerunning the inherited test suite.
    def test_reviewer_index_replacement_after_check_cannot_use_old_pin(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'original'; alt=Path(tmp)/'alternate'
            _,pin=self.fixture(root);self.fixture(alt,changed=True)
            original=M.checked_bytes;swapped=[]
            def replacement(path,*args,**kwargs):
                value=original(path,*args,**kwargs)
                if Path(path)==root/'INDEX.json' and not swapped:
                    for f in alt.iterdir():shutil.copyfile(f,root/f.name)
                    swapped.append(True)
                return value
            with patch.object(M,'checked_bytes',replacement):
                with self.assertRaisesRegex(ValueError,'checksum'):self.check(root,pin)
            self.assertTrue(swapped)

    def test_reviewer_rejected_review_replacement_never_authorizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a,pred,route=self.activation_fixture(root,accepted=False)
            swapped=[]
            def replacement(path,*args,**kwargs):
                value=route(path,*args,**kwargs)
                if Path(path)==root/'review.json' and not swapped:
                    M.atomic(path,dict(plan_sha256=PIN,prepared_accepted=True,reviewer='independent'))
                    swapped.append(True)
                return value
            with patch.object(M,'checked_bytes',replacement):
                with self.assertRaisesRegex(ValueError,'independent prepared review'):M.activation_guard(root,PIN)
            self.assertTrue(swapped)

    def test_reviewer_recomputed_x_fixture_labels_both_references(self):
      Torch=torch
      with tempfile.TemporaryDirectory() as tmp:
       root=Path(tmp)/'retained';self.fixture(root);d=M.load(root/'INDEX.json')
       for e in d['entries']:
        i=e['identity']; k=i['key'];label=k[-1]
        change=(i['pair']=='observed' and ((len(k)==5 and k[2]=='recompute' and ((label=='B_mm_operands' and i['slot']=='0') or label=='A_mm_output')) or label=='incoming_B_gradient' or (label=='post_B_gradient' and i['question']==1)))
        if not change:continue
        t=Torch.frombuffer(bytearray((root/e['file']).read_bytes()),dtype=Torch.float32).clone().reshape(e['metadata']['shape'])
        t=(t-1)*2+1 if label=='post_B_gradient' else t*2
        raw=t.reshape(-1).view(Torch.uint8).numpy().tobytes();(root/e['file']).write_bytes(raw);e['sha256']=hashlib.sha256(raw).hexdigest()
        event=next(v for v in d['events']['records'][i['repeat']] if v['key']==k)
        target=event['observation'][int(i['slot'])] if i['slot'] else event['observation'];target['sha256']=e['sha256']
       M.atomic(root/'INDEX.json',d);r=self.check(root,M.sha(root/'INDEX.json'))
       for row in r['cpu_vjp_interpretation']:
        self.assertFalse(row['cpu_float64_B_vjp_references']['forward']['values_equal'])
        self.assertTrue(row['cpu_float64_B_vjp_references']['recompute']['values_equal'])
        self.assertTrue(row['accumulation']['values_equal'])
        self.assertEqual(row['backward_input_status'],'UNRESOLVED_BACKWARD_INPUT')
        self.assertEqual(row['cpu_mac_terms'],240)

    def test_reviewer_impossible_and_missing_producer_right_rejected(self):
        for value in (None, {'shape':[999],'dtype':'invented','device':'unrelated'}):
            with self.subTest(value=value),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'retained';self.fixture(root)
                def corrupt(d):
                    for records in d['events']['records']:
                        op=next(e for e in records if e['key'][-1]=='producer_operator')['observation']
                        if value is None:op.pop('right')
                        else:op['right']=value
                pin=self.mutate(root,corrupt)
                with self.assertRaisesRegex(ValueError,'producer right'):self.check(root,pin)

    def test_producer_tensor_scalar_linkage_and_discrimination(self):
        saved=torch.tensor(2.)
        tensor=M.producer_right(torch,saved.clone(),saved)
        self.assertEqual(tensor,dict(kind='Tensor',**M.metadata(saved),sha256=__import__('hashlib').sha256(saved.numpy().tobytes()).hexdigest()))
        for wrong in (torch.tensor(3.),torch.tensor([2.]),torch.tensor(2.,dtype=torch.float64),3.,float('nan')):
            with self.subTest(wrong=str(wrong)),self.assertRaises(ValueError):M.producer_right(torch,wrong,saved)
        for value in (2,2.):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'retained';self.fixture(root)
                def scalar(d):
                    for records in d['events']['records']:
                        op=next(e for e in records if e['key'][-1]=='producer_operator')['observation']
                        op.update(name='aten.mul.Scalar',right=M.producer_right(torch,value,saved))
                pin=self.mutate(root,scalar);self.assertEqual(self.check(root,pin)['tensors'],50)
                def wrong(d):
                    op=next(e for e in d['events']['records'][0] if e['key'][-1]=='producer_operator')['observation']
                    op['right']['value']=3
                with self.assertRaisesRegex(ValueError,'producer scalar'):self.check(root,self.mutate(root,wrong))

    def test_reviewer_wrong_missing_terminal_execution_pin_and_scope(self):
        mutations=[lambda t:t.update(plan_sha256='wrong-execution-pin'),lambda t:t.pop('plan_sha256'),
                   lambda t:t.update(attempt=2),lambda t:t.update(scientific_acceptance=True)]
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);a,pred,route=self.activation_fixture(root)
                t=M.load(pred/'ENGINEERING_EVAL_EXIT.json');mutate(t)
                a['predecessor_pins']['ENGINEERING_EVAL_EXIT.json']=M.atomic(pred/'ENGINEERING_EVAL_EXIT.json',t)
                M.atomic(root/'ACTIVATION.json',a)
                with patch.object(M,'checked_bytes',route),self.assertRaisesRegex(ValueError,'terminal execution/scope'):
                    M.activation_guard(root,PIN)
        for field,value in [('chip',2),('run','wrong'),('out','/tmp/wrong'),('container','wrong'),('test_read',True)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);a,pred,route=self.activation_fixture(root)
                e=M.load(pred/'execution.json');e[field]=value
                a['predecessor_pins']['execution.json']=M.atomic(pred/'execution.json',e)
                M.atomic(root/'ACTIVATION.json',a)
                with patch.object(M,'checked_bytes',route),self.assertRaisesRegex(ValueError,'execution scope'):
                    M.activation_guard(root,PIN)

    def test_actual_checkpoint_weight_vjp_uses_recomputed_input(self):
        from torch.utils.checkpoint import checkpoint
        x=torch.tensor([[1.,2.],[3.,4.]],dtype=torch.float64,requires_grad=True)
        w=torch.tensor([[2.],[3.]],dtype=torch.float64,requires_grad=True);calls=[]
        def f(a,b):
            current=a*(1 if not calls else 2);calls.append(current.detach().clone());return current@b
        out=checkpoint(f,x,w,use_reentrant=False);out.sum().backward()
        self.assertEqual(len(calls),2)
        self.assertTrue(torch.equal(w.grad,calls[1].T@torch.ones_like(out)))
        self.assertFalse(torch.equal(w.grad,calls[0].T@torch.ones_like(out)))

    def test_cpu_work_budget_and_backend_autoload(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'retained';_,pin=self.fixture(root);original=torch.Tensor.numel
            def inflated(t):return 134217729 if tuple(t.shape)==(4,5) else original(t)
            with patch.object(torch.Tensor,'numel',inflated),self.assertRaisesRegex(ValueError,'CPU VJP work budget'):
                self.check(root,pin)
        self.assertEqual(os.environ['TORCH_DEVICE_BACKEND_AUTOLOAD'],'0')
        self.assertNotIn('torch_npu',sys.modules)

    def test_source_checked_bytes_execute_not_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'module.py';path.write_text('VALUE = 17')
            pin=M.sha(path);original=M.checked_bytes
            def replacement(p,*args,**kwargs):
                result=original(p,*args,**kwargs);Path(p).write_text("raise RuntimeError('replacement executed')")
                return result
            with patch.object(M,'checked_bytes',replacement):module=M.source(path,pin)
            self.assertEqual(module.VALUE,17)
            self.assertEqual(module.__checked_sha256__,pin)
            with self.assertRaisesRegex(ValueError,'checksum'):M.source(path,pin)

    def test_transitive_import_and_ast_read_use_checked_source(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);helper=root/'kev_aug.py';trainer=root/'trainer.py'
            helper.write_text('VALUE = 23');trainer.write_text('import kev_aug\nVALUE = kev_aug.VALUE\n')
            pins={str(p):M.sha(p) for p in (helper,trainer)};sources=M.CheckedSources(pins)
            helper.write_text("raise RuntimeError('unverified helper')");trainer.write_text('VALUE = 99')
            with patch.dict(sys.modules,{'kev_aug':__import__('types').SimpleNamespace(VALUE=-1)}):
                self.assertEqual(sources.get(trainer).VALUE,23)
            self.assertIn('import kev_aug',sources.text_path(trainer).read_text())
            with self.assertRaisesRegex(ValueError,'unverified'):sources.get(root/'other.py')

    def test_actual_frozen_trainer_ast_and_helper_route(self):
        p=M.load(M.V4/'plan.json');sources=M.CheckedSources(p['files'])
        trainer=sources.get(Path(p['trainer']));trace=sources.get(Path(p['trainer']).with_name('r3_k2_reference_trace.py'))
        trace.Path=sources.text_path
        with patch.object(Path,'read_text',side_effect=AssertionError('AST path reopened')):
            fn=trace.instrument(trainer,lambda *args:None,lambda *args:None,lambda *args:None)
        self.assertTrue(callable(fn))
        self.assertEqual(trainer.B.__checked_sha256__,p['files'][str(Path(p['trainer']).with_name('build_kev_sft.py'))])

    def test_bounded_checked_json_and_payload_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bounded.json';path.write_bytes(b' '*(M.MAX_INDEX+1))
            with self.assertRaisesRegex(ValueError,'size'):M.checked_json(path)
            root=Path(tmp)/'retained';store,pin=self.fixture(root)
            payload=root/store.entries[0]['file'];original=M.checked_bytes
            def grow(p,*args,**kwargs):
                if Path(p)==payload:
                    with payload.open('ab') as f:f.write(b'!')
                return original(p,*args,**kwargs)
            with patch.object(M,'checked_bytes',grow),self.assertRaisesRegex(ValueError,'size'):self.check(root,pin)

    def test_trace_reconstruction_checked_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'results';out.mkdir()
            _,index_pin=self.fixture(root/'retained');report=self.check(root/'retained',index_pin)
            reconstruction_pin=M.atomic(out/'CPU_RECONSTRUCTION.json',report)
            trace=dict(plan_sha256=PIN,test_read=False,scientific_acceptance=False,
                backward_probe=dict(complete=True),control=dict(complete=True),
                retained_index_sha256=index_pin,cpu_reconstruction_sha256=reconstruction_pin)
            pin=M.atomic(out/'TRACE.json',trace)
            self.assertEqual(M.checked_result(out/'TRACE.json',pin,PIN),(trace,pin))
            original=M.checked_bytes
            def replacement(p,*args,**kwargs):
                result=original(p,*args,**kwargs)
                if Path(p)==out/'TRACE.json':M.atomic(p,dict(trace,plan_sha256='replacement'))
                return result
            with patch.object(M,'checked_bytes',replacement):
                self.assertEqual(M.checked_result(out/'TRACE.json',pin,PIN),(trace,pin))
            M.atomic(out/'TRACE.json',trace)
            for name in ('CPU_RECONSTRUCTION.json','../retained/INDEX.json'):
                target=out/name if not name.startswith('..') else root/'retained/INDEX.json'
                raw=target.read_bytes();target.write_bytes(raw+b' ')
                with self.assertRaisesRegex(ValueError,'checksum'):M.checked_result(out/'TRACE.json',pin,PIN)
                target.write_bytes(raw)

    def test_bootstrap_consumes_checked_buffer_and_rejects_wrong_pin(self):
        import sys,subprocess
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'entry.py';path.write_text("print('VERIFIED_ENTRY')")
            args=M.entrypoint(path,M.sha(path))
            result=subprocess.run([sys.executable,*args],capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.strip(),'VERIFIED_ENTRY')
            result=subprocess.run([sys.executable,*M.entrypoint(path,'0'*64)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('VERIFIED_ENTRY',result.stdout)

    def test_owned_supervisor_binds_terminal_to_consumed_trace_buffer(self):
        import types
        helper=M.V4.with_name('k2_retained_tensor_20261101_v3')/'tools/r3_k2_benchmark_launcher.py'
        L=M.source(helper,M.sha(helper))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'results';out.mkdir();attempt=root/'attempts/1';attempt.mkdir(parents=True)
            _,index_pin=self.fixture(root/'retained')
            reconstruction_pin=M.atomic(out/'CPU_RECONSTRUCTION.json',self.check(root/'retained',index_pin))
            trace=dict(schema='r3-k2-reference-trace-v1',complete=True,truncated=False,
                reference_questions=12,repeat_questions=12,comparisons=[{}]*12,
                plan_sha256=PIN,test_read=False,scientific_acceptance=False,
                backward_probe=dict(complete=True),control=dict(complete=True),
                retained_index_sha256=index_pin,cpu_reconstruction_sha256=reconstruction_pin)
            trace_pin=M.atomic(out/'TRACE.json',trace)
            M.atomic(out/'EXIT.json',dict(exit_code=0,plan_sha256=PIN,result_sha256=trace_pin))
            execution_pin='e'*64
            e=dict(out=str(root),run='mock/run',allocation=str(root/'allocation.json'),chip=3,
                benchmark_sha256=PIN,schema='r3-k2-reference-trace-execution-retained-v1')
            q=dict(out=str(out));spec=dict(name='mock-retained')
            M.atomic(attempt/'CLAIM.json',{})
            M.atomic(attempt/'LAUNCH_INTENT.json',dict(command=['MOCK_NO_LAUNCH'],pin=execution_pin))
            M.atomic(attempt/'LAUNCH_RECEIPT.json',dict(id='mock-cid',sha256=execution_pin))
            observed=dict(Id='mock-cid',State=dict(Status='exited',ExitCode=0))
            releases=[]
            resource=types.SimpleNamespace(load=lambda p:dict(allocation=[dict(chip=3,run='mock/run')]),
                docker_inspect=lambda name:observed,release=lambda args:releases.append(args))
            container=types.SimpleNamespace(command=lambda s:['MOCK_NO_LAUNCH'])
            L.module=lambda p:resource if Path(p).name=='r3_resource_adapter.py' else container
            L.verify=lambda path,pin:(e,q);L.spec=lambda *args:spec
            L.verify_container=lambda *args:None;L.load=M.load
            calls=[]
            def result(path,expected):
                value,pin=M.checked_result(path,expected,PIN);calls.append(pin)
                # Reviewer's replacement pattern at the actual supervisor edge:
                # the terminal must describe the validated buffer, not this file.
                M.atomic(path,dict(trace,complete=False))
                return value,pin
            L.checked_result=result
            with patch.object(L.subprocess,'run') as process:
                terminal=L.supervise(root/'execution.json',execution_pin)
            self.assertEqual(calls,[trace_pin]);self.assertEqual(len(releases),1)
            self.assertEqual(terminal['result_sha256'],trace_pin)
            self.assertNotEqual(terminal['result_sha256'],M.sha(out/'TRACE.json'))
            self.assertTrue(terminal['diagnostic_complete'])
            self.assertEqual(M.load(root/'ENGINEERING_EVAL_EXIT.json'),terminal)
            # Only docker logs is mocked; no launch/claim/SSH/device operation.
            self.assertEqual(process.call_args.args[0],['docker','logs','mock-cid'])

    def test_plan_and_execution_replacements_use_checked_original_or_fail(self):
        root=M.V4.with_name('k2_retained_tensor_20261101_v3')
        original=M.checked_bytes
        for filename in ('plan.json','execution.json'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                p=root/filename;pin=M.sha(p);replacement=Path(tmp)/filename
                replacement.write_bytes(p.read_bytes());swapped=[]
                def checked(path,*args,**kwargs):
                    if Path(path)!=p:return original(path,*args,**kwargs)
                    value=original(replacement,*args,**kwargs)
                    if not swapped:
                        d=json.loads(value[0]);d['test_read']=True
                        M.atomic(replacement,d);swapped.append(True)
                    return value
                frozen=M.source(root/'tools/r3_k2_retained_tensor_probe.py',M.sha(root/'tools/r3_k2_retained_tensor_probe.py'))
                frozen.checked_bytes=checked
                if filename=='plan.json':
                    result=frozen.verify_plan(p,pin)
                    self.assertIs(result['test_read'],False)
                else:
                    # Supervisor's additional verify must reject the changed
                    # execution on reread, before any spec/resource operation.
                    with self.assertRaisesRegex(ValueError,'checksum'):frozen.launcher(p,pin)
                self.assertEqual(swapped,[True])

    def test_predecessor_checked_proof_replacements_do_not_change_consumed_scope(self):
        for name in ('execution.json','ENGINEERING_EVAL_EXIT.json','attempts/1/RELEASE.json','attempts/1/LAUNCH_RECEIPT.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);a,pred,route=self.activation_fixture(root);swapped=[]
                def changed(path,*args,**kwargs):
                    result=route(path,*args,**kwargs)
                    if str(path).endswith('/'+name) and not swapped:
                        M.atomic(pred/name,{'corrupted_replacement':True});swapped.append(True)
                    return result
                with patch.object(M,'checked_bytes',changed):
                    self.assertEqual(M.activation_guard(root,PIN),a)
                self.assertTrue(swapped)
                with patch.object(M,'checked_bytes',route),self.assertRaisesRegex(ValueError,'checksum'):
                    M.activation_guard(root,PIN)


# Use helper methods without inheriting/rerunning RetainedTests' test methods.
for _name in ('fixture','check','mutate','activation_fixture'):
    setattr(RepairRegressions,_name,getattr(RetainedTests,_name))

if __name__ == '__main__':
    unittest.main()
