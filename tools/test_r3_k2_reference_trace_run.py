"""Exercise the real runner and AST observer with synthetic CPU model/data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

try:
    import torch
except ImportError:
    torch = None

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('trace_runner', HERE/'r3_k2_reference_trace_run.py')
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)


@unittest.skipIf(torch is None, 'torch CPU required')
class Runner(unittest.TestCase):
    def test_same_model_two_reference_passes_and_complete_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); trainer_path = root/'trainer.py'
            trainer_path.write_text('''def row_logprob_sums(torch, core, seqs, starts, pad, device):
    ids = torch.tensor(seqs); mask = torch.ones_like(ids)
    chunk, bi, ti, tg, owner = [0], [0], [0], [2], [0]
    bi_t = torch.tensor(bi)
    return core.weight * (core.calls + 1)

def step_loss(torch, core, tok, units, arm, device, pad, maxlen, micro, counters, backward=True):
    exs = [e for unit in units for e in unit]
    total = 0.
    for e in exs:
        seqs, starts = [[1, 2]], [1]
        s = row_logprob_sums(torch, core, seqs, starts, pad, device)
        lq = s.sum()
        if backward:
            lq.backward()
        total += float(lq.detach())
    core.calls += 1
    return total, {'rows': len(exs)}
''')
            model = torch.nn.Module(); model.weight = torch.nn.Parameter(torch.tensor([0., 0.])); model.calls = 0
            core = types.SimpleNamespace(weight=model.weight, calls=0)
            model.base_model = types.SimpleNamespace(model=core)
            trainer = R.B.source(trainer_path, 'synthetic_trainer')
            trainer.TRAIN_FILE = str(root/'train.jsonl'); Path(trainer.TRAIN_FILE).write_text('synthetic')
            trainer.file_sha256 = R.B.sha
            parsed = []
            def parse(argv):
                parsed.extend(argv)
                return types.SimpleNamespace(model_path='synthetic', device='cpu')
            trainer.parse_args = parse
            trainer.Data = lambda args: types.SimpleNamespace(step_units=lambda step: (None, [[{'id': 'one'}]]))
            builds = []
            def build(args, torch):
                builds.append(True)
                return model, [('weight', model.weight)], 1
            trainer.build_model = build
            plan = {'schema':'r3-k2-reference-trace-plan-v1', 'protocol':R.PROTOCOL,
                    'test_read':False,'scientific_acceptance':False,'model':'synthetic',
                    'trainer':str(trainer_path),'out':str(root/'results')}
            files = [trainer_path, Path(trainer.TRAIN_FILE), Path(R.__file__), HERE/'r3_k2_reference_trace.py']
            plan['files'] = {str(p.resolve()):R.B.sha(p) for p in files}
            path=root/'plan.json';path.write_text(json.dumps(plan));seeds=[]
            npu=types.SimpleNamespace(synchronize=lambda:None)
            transformer=types.SimpleNamespace(AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda p:types.SimpleNamespace(pad_token_id=0)))
            with patch.dict(sys.modules, {'torch_npu':types.ModuleType('torch_npu'),'transformers':transformer}), \
                 patch.object(torch,'npu',npu,create=True),patch.object(R.B,'source',return_value=trainer), \
                 patch.object(R.B,'rng_snapshot',return_value={'fixed':'rng'}), \
                 patch.object(R.B,'seed_and_snapshot',side_effect=lambda t,s,i:seeds.append((s,i)) or {'fixed':'rng'}):
                result=R.run(path,R.B.sha(path))
            self.assertEqual(len(builds),1)
            self.assertEqual(seeds,[(2,0),(2,0)])
            self.assertIn('--grad-ckpt',parsed)
            self.assertTrue(result['complete'])
            self.assertEqual(result['reference_questions'],1)
            self.assertEqual(result['first_difference']['question'],0)
            self.assertTrue(result['first_difference']['components_equal']['loss'])
            self.assertFalse(result['first_difference']['gradient_diagnostic']['gradient_values_equal'])
            self.assertFalse(result['scientific_acceptance'])
            self.assertTrue((root/'results/TRACE.json').exists())
            self.assertTrue((root/'results/TRACE_PARTIAL.json').exists())
            self.assertFalse((root/'results/RESULT.json').exists())


if __name__ == '__main__':unittest.main()
