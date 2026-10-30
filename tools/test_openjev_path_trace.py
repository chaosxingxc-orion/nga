"""E38 passive instrumentation checks; runnable with CPU PyTorch, no NPU."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('path_trace', Path(__file__).with_name('openjev_path_trace.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class TraceComparison(unittest.TestCase):
    def sample(self):
        return dict(candidates=15, width=186, order=['x'], events={
            'x': dict(dtype='torch.bfloat16', row_shape=[186, 8], rows={str(i): str(i) for i in range(15)})},
            expected_events=['x'], chunks=[{'range': [0, 15, 186], 'order': ['x']}])

    def test_exact_and_changed_candidate(self):
        a = self.sample(); b = copy.deepcopy(a)
        self.assertTrue(p.compare_traces(a, b)['exact'])
        b['events']['x']['rows']['8'] = 'different'
        self.assertEqual(p.compare_traces(a, b)['first_differing_observed_event'],
                         {'event': 'x', 'changed_candidates': [8]})

    def test_missing_extra_reordered_and_empty_rejected(self):
        a = self.sample()
        for mutation in ['missing', 'extra', 'shape', 'dtype', 'order', 'empty', 'skipped_hook', 'chunk_order']:
            b = copy.deepcopy(a)
            if mutation == 'missing': del b['events']['x']['rows']['1']
            if mutation == 'extra': b['events']['x']['rows']['15'] = 'extra'
            if mutation == 'shape': b['events']['x']['row_shape'] = [10]
            if mutation == 'dtype': b['events']['x']['dtype'] = 'other'
            if mutation == 'order': b['order'] = []
            if mutation == 'empty': b.update(order=[], events={})
            if mutation == 'skipped_hook': b['expected_events'].append('never_called')
            if mutation == 'chunk_order': b['chunks'][0]['order'] = []
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): p.compare_traces(a, b)


try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'CPU torch is required for actual tensor/hook checks')
class ActualTensors(unittest.TestCase):
    def model(self):
        class Projection(torch.nn.Module):
            def forward(self, x): return x + .25
        class Norm(torch.nn.Module):
            def forward(self, x, z): return x + z * .125
        def torch_chunk_gated_delta_rule(query, key, value, **kwargs):
            return (query + key + value) * .125, None
        class Gated(torch.nn.Module):
            def __init__(self):
                super().__init__()
                for name in ['in_proj_qkv','in_proj_z','in_proj_b','in_proj_a','conv1d','out_proj']:
                    setattr(self, name, Projection())
                self.norm = Norm(); self.chunk_gated_delta_rule = torch_chunk_gated_delta_rule
            def forward(self, x):
                b,l,d = x.shape
                q = self.in_proj_qkv(x); z = self.in_proj_z(x)
                beta = self.in_proj_b(x); g = self.in_proj_a(x)
                q = self.conv1d(q.transpose(1,2)).transpose(1,2)
                core,_ = self.chunk_gated_delta_rule(q.reshape(b,l,2,4),q.reshape(b,l,2,4),q.reshape(b,l,2,4),g=g,beta=beta)
                return self.out_proj(self.norm(core.reshape(-1,4),z.reshape(-1,4)).reshape(b,l,d))
        class MLP(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.gate_proj=Projection();self.up_proj=Projection();self.down_proj=Projection()
            def forward(self,x): return self.down_proj((self.gate_proj(x)+self.up_proj(x))*.25)
        class Qwen3_5DecoderLayer(torch.nn.Module):
            def __init__(self):
                super().__init__();self.block_type='linear_attention';self.linear_attn=Gated();self.mlp=MLP()
                self.input_layernorm=Projection();self.post_attention_layernorm=Projection()
            def forward(self, x): return self.mlp(self.post_attention_layernorm(self.linear_attn(self.input_layernorm(x))))
        class Backbone(torch.nn.Module):
            def __init__(self):
                super().__init__();self.layers=torch.nn.ModuleList([Qwen3_5DecoderLayer() for _ in range(24)])
            def forward(self,x):
                for layer in self.layers:x=layer(x)
                return x
        return Backbone().eval()

    def test_real_tensors_passive_hashes_global_rows_and_cleanup(self):
        torch.set_num_threads(1)
        model=self.model(); x=torch.arange(15*186*8,dtype=torch.float32).reshape(15,186,8)*.0001
        originals=[m.linear_attn.chunk_gated_delta_rule for m in model.layers]
        with torch.inference_mode():
            expected=model(x); full={}
            with p.trace_path(model,torch,full): actual=model(x)
            self.assertTrue(torch.equal(expected,actual))
            split={}; parts=[]
            with p.trace_path(model,torch,split) as observer:
                for start,end in [(0,8),(8,15)]:
                    observer(start,end,186);parts.append(model(x[start:end]))
            self.assertTrue(torch.equal(expected,torch.cat(parts)))
            self.assertTrue(p.compare_traces(full,split)['exact'])
        for layer,original in zip(model.layers,originals):
            self.assertIs(layer.linear_attn.chunk_gated_delta_rule,original)
        self.assertTrue(all(not m._forward_hooks and not m._forward_pre_hooks for m in model.modules()))

    def test_exception_cleanup_signed_zero_and_duplicate(self):
        model=self.model(); original=model.layers[0].linear_attn.chunk_gated_delta_rule
        with self.assertRaises(RuntimeError):
            with p.trace_path(model,torch,{}):raise RuntimeError('injected')
        self.assertIs(model.layers[0].linear_attn.chunk_gated_delta_rule,original)
        self.assertTrue(all(not m._forward_hooks and not m._forward_pre_hooks for m in model.modules()))
        a={};b={};pa=p.Recorder(torch,a);pb=p.Recorder(torch,b)
        pa.record('zero',torch.zeros(15,1));pb.record('zero',-torch.zeros(15,1))
        a['expected_events'] = b['expected_events'] = ['zero']
        self.assertEqual(len(p.compare_traces(a,b)['differences'][0]['changed_candidates']),15)
        with self.assertRaises(ValueError):pa.record('zero',torch.zeros(15,1))

    def test_unknown_shape_runtime_or_training_fails_closed(self):
        model=self.model();model.train()
        with self.assertRaises(ValueError):
            with p.trace_path(model,torch,{}):pass
        model.eval();model.layers[0].linear_attn.chunk_gated_delta_rule=lambda *a,**k:None
        with self.assertRaises(ValueError):
            with p.trace_path(model,torch,{}):pass
        self.assertTrue(all(not m._forward_hooks and not m._forward_pre_hooks for m in model.modules()))
        r=p.Recorder(torch,{})
        with self.assertRaises(ValueError):r.chunk(0,8,185)
        with self.assertRaises(ValueError):r.record('bad',torch.zeros(14,1))


if __name__ == '__main__':unittest.main()
