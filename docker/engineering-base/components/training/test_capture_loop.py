"""Actual train_r3.run/step_loss CPU fixture, with independent normal-run observations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import torch
import capture_qualification as capture
import capture_storage as storage

ROOT = Path(__file__).resolve().parents[2] / 'source' / 'train'
os.environ['NGA_R0_CODE'] = str(ROOT / 'r0_code')
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('capture_test_train_r3', ROOT / 'train_r3.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

class Data:
    def __init__(self, args): self.rows = [None] * 15576; self.sym = []
    def steps_per_epoch(self): return 1558
    def step_units(self, step):
        return step // 1558, [[{'prompt': 'p', 'response': 'a', 'candidates': None}]] * 3

class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.q_proj = torch.nn.Linear(2, 2)
        self.base_model = types.SimpleNamespace(model=self)
    def save_pretrained(self, path): Path(path).mkdir()

class Tokenizer:
    pad_token_id = 0
    def __call__(self, text, **kwargs): return {'input_ids': [1, 2] if text == 'p' else [3]}

class NPU:
    def synchronize(self): pass
    def max_memory_reserved(self): return 0
    def manual_seed_all(self, seed): pass

class CaptureLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.fake = types.ModuleType('transformers'); self.fake.__version__ = 'fixture'
        self.fake.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda _: Tokenizer())
        import torch._dynamo
        self.modules = [patch.dict(sys.modules, {'torch_npu': types.ModuleType('torch_npu')}), patch.dict(sys.modules, {'transformers': self.fake})]
        for module_patch in self.modules: module_patch.start()
        self.npu = patch.object(torch, 'npu', NPU(), create=True); self.npu.start()
        self.data = patch.object(t, 'Data', Data); self.data.start()
        self.sha = patch.object(t, 'file_sha256', return_value='fixture'); self.sha.start()
        self.row = patch.object(t, 'row_logprob_sums', self.row_sums); self.row.start()
        self.ck = patch.object(t, 'save_ckpt', self.save); self.ck.start()
        self.models = []; self.initial = []
        self.build = patch.object(t, 'build_model', self.make); self.build.start()
        self.saved = []
    def tearDown(self):
        for p in (self.build, self.ck, self.row, self.sha, self.data, self.npu): p.stop()
        for module_patch in reversed(self.modules): module_patch.stop()
        self.tmp.cleanup()
    def make(self, args, torch_):
        torch.manual_seed(123); model = Model(); self.models.append(model); self.initial.append({n:p.detach().numpy().tobytes() for n,p in model.named_parameters()})
        return model, list(model.named_parameters()), 1
    def save(self, torch_, out, step, trainable, opt, sched, keep=2):
        self.saved.append((step, sched.total_steps))
    def row_sums(self, torch_, core, seqs, starts, pad_id, device, **kwargs):
        x = torch.tensor([[float(len(s)), float(st)] for s, st in zip(seqs, starts)])
        return core.q_proj(x).log_softmax(dim=-1)[:, 0]
    def args(self, name):
        return t.parse_args(['--out', str(self.root/name), '--device', 'cpu', '--stop-after', '2', '--no-merge', '--model-path', str(self.root/'fake-model')])
    def values(self, directory, spec):
        obj = storage.validate(directory/'records', spec)
        result = {}
        for record in obj['records']:
            raw = b''.join((directory/'records'/s['file']).read_bytes() for s in record['shards'])
            result[record['name']] = raw
        return result
    def test_actual_loop_matches_independent_normal_observation(self):
        observed = {}; step = [0]; origclip = torch.nn.utils.clip_grad_norm_; origstep = torch.optim.AdamW.step
        def clip(params, *a, **kw):
            params = list(params); step[0] += 1
            for (n, _), p in zip(self.models[-1].named_parameters(), params): observed[f'{step[0]}/preclip/{n}'] = p.grad.detach().numpy().tobytes()
            ret = origclip(params, *a, **kw)
            for (n, _), p in zip(self.models[-1].named_parameters(), params): observed[f'{step[0]}/postclip/{n}'] = p.grad.detach().numpy().tobytes()
            return ret
        def optstep(opt, *a, **kw):
            result = origstep(opt, *a, **kw)
            for n, p in self.models[-1].named_parameters(): observed[f'{step[0]}/postupdate/{n}'] = p.detach().numpy().tobytes()
            return result
        actual_loss = t.step_loss
        def loss(*a, **kw):
            result = actual_loss(*a, **kw)
            observed[f'{step[0]+1}/loss/returned'] = torch.tensor(result[0],dtype=torch.float64).numpy().tobytes()
            return result
        with patch.object(torch.nn.utils, 'clip_grad_norm_', clip), patch.object(torch.optim.AdamW, 'step', optstep), patch.object(t, 'step_loss', loss):
            self.assertEqual(t.run(self.args('normal')), {'step': 2, 'stopped': True})
        normal_model = self.models[-1]
        census_dir = self.root/'attempts'; census_dir.mkdir()
        self.assertEqual(capture.run_cpu_two_updates(t, self.args('captured'), census_dir, 'a'), {'step': 2, 'stopped': True})
        directory = census_dir/'a'; census = json.loads((directory/'CENSUS.json').read_text())
        self.assertEqual(census['schedule'], 3116)
        topology = [(n, list(p.shape)) for n,p in normal_model.named_parameters()]
        capture.validate_attempt(directory, topology)
        vals = self.values(directory, census['records'])
        self.assertEqual({k:v for k,v in vals.items() if not k.startswith('0/')}, observed)
        for n, p in normal_model.named_parameters():
            self.assertEqual(vals['2/postupdate/'+n], p.detach().numpy().tobytes())
            self.assertEqual(vals['0/initial/'+n], self.initial[0][n])
        self.assertEqual(self.saved, [(2,3116), (2,3116)])
        # Census is independently required: a missing stage cannot pass validation.
        incomplete = [x for x in census['records'] if '/postclip/' not in x['name']]
        with self.assertRaises(ValueError): storage.validate(directory/'records', incomplete)
        # Rewrite a self-consistent census and terminal with the same omission: external topology still rejects it.
        original_census = (directory/'CENSUS.json').read_bytes(); original_terminal = (directory/'COMPLETE.json').read_bytes()
        altered = storage._canonical({'schedule':3116, 'updates':[1,2], 'records':incomplete})
        (directory/'CENSUS.json').write_bytes(altered)
        (directory/'COMPLETE.json').write_bytes(storage._canonical({'census_sha256': hashlib.sha256(altered).hexdigest()}))
        with self.assertRaises(ValueError): capture.validate_attempt(directory, topology)
        (directory/'CENSUS.json').write_bytes(original_census); (directory/'COMPLETE.json').write_bytes(original_terminal)
        with self.assertRaises(FileExistsError): capture.run_cpu_two_updates(t, self.args('captured'), census_dir, 'a')
        self.values(directory, census['records'])
    def test_observer_failure_closes_files_and_records_failure(self):
        parent = self.root/'attempts'; parent.mkdir()
        with patch.object(capture._Observer, 'preclip', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError, 'injected'): capture.run_cpu_two_updates(t, self.args('failure'), parent, 'bad')
        d = parent/'bad'
        self.assertTrue((d/'FAILED.json').exists()); self.assertFalse((d/'COMPLETE.json').exists())
        self.assertTrue((d/'records'/'FAILED.json').exists())
        # Open file descriptors to trainer output are closed on the exception path.
        out = str(self.root/'failure')
        for fd in Path('/proc/self/fd').iterdir():
            try: target = os.readlink(fd)
            except FileNotFoundError: continue
            self.assertFalse(target.startswith(out), target)
    def test_zero_update_resume_fails_without_overwrite(self):
        parent = self.root/'attempts'; parent.mkdir()
        capture.run_cpu_two_updates(t, self.args('first'), parent, 'first')
        before = hashlib.sha256((parent/'first'/'COMPLETE.json').read_bytes()).hexdigest()
        fake_ckpt = self.root/'ckpt.pt'
        model = self.models[-1]
        opt = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=.01)
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-4, total_steps=3116, pct_start=.1)
        torch.save({'lora':dict(model.named_parameters()), 'opt':opt.state_dict(), 'sched':sched.state_dict(), 'step':3116}, fake_ckpt)
        with patch.object(t, 'latest_ckpt', return_value=str(fake_ckpt)):
            with self.assertRaisesRegex(ValueError, 'fresh run'): capture.run_cpu_two_updates(t, self.args('retry'), parent, 'retry')
        self.assertTrue((parent/'retry'/'FAILED.json').exists())
        self.assertEqual(before, hashlib.sha256((parent/'first'/'COMPLETE.json').read_bytes()).hexdigest())

if __name__ == '__main__': unittest.main()
