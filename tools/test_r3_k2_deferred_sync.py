"""Actual frozen step_loss with synthetic differentiable scores, CPU-only.

Checks stochastic call order, exact gradients, counters, and logged loss. Does
not establish real Qwen/NPU throughput or numerical admission.
"""
import ast
import copy
from pathlib import Path
import unittest

import torch
import r3_k2_deferred_sync as P

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/r3_sft/r3_code/train_r3.py'
if not SOURCE.exists():
    SOURCE = Path(__file__).with_name('k2_reference_train_r3.py')


def loss_function(raw, calls):
    tree = ast.parse(raw)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'step_loss')
    def encode(tok, example, max_len, counters):
        counters['encoded'] = counters.get('encoded', 0) + 1
        return example['prompt'], example['candidates']
    def score(torch, weight, seqs, starts, pad_id, device, **kwargs):
        calls.append((copy.deepcopy(seqs), list(starts), kwargs))
        features = torch.tensor([[sum(s), len(s), st] for s, st in zip(seqs, starts)], dtype=torch.float32)
        features = torch.nn.functional.dropout(features, p=.05, training=True)
        return features @ weight
    env = {'encode_candidates': encode, 'row_logprob_sums': score}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<actual-step-loss>', 'exec'), env)
    return env['step_loss']


class DeferredSync(unittest.TestCase):
    def test_exact_loss_gradients_rng_order_and_stats(self):
        raw = SOURCE.read_bytes()
        candidate = P.transform(raw)
        for backward in (False, True):
            results = []
            for code in (raw, candidate):
                calls = []; fn = loss_function(code, calls)
                w = torch.tensor([.01, -.02, .03], requires_grad=True)
                units = [[{'prompt': [2, 3, 4], 'candidates': [[1], [2, 5]], 'gold_index': 0},
                          {'prompt': [3], 'candidates': [[1, 3], [4], [5, 2, 1]], 'gold_index': 2}],
                         [{'prompt': [7, 2], 'candidates': [[1], [2]], 'gold_index': 1}]]
                counters = {}; torch.manual_seed(42)
                result = fn(torch, w, None, units, 'k2', 'cpu', 0, 4096, 12000, counters,
                            backward=backward, autocast=False)
                results.append((result, calls, counters, w.grad.clone() if backward else None, torch.get_rng_state()))
            self.assertEqual(results[0][:3], results[1][:3])
            if backward:self.assertTrue(torch.equal(results[0][3], results[1][3]))
            self.assertTrue(torch.equal(results[0][4], results[1][4]))

    def test_changed_original_refused(self):
        with self.assertRaisesRegex(ValueError, 'source differs'):
            P.transform(SOURCE.read_bytes() + b'\n')

    def test_k1_and_other_functions_unchanged(self):
        before = ast.parse(SOURCE.read_bytes());after = ast.parse(P.transform(SOURCE.read_bytes()))
        def isolate(tree):
            for fn in tree.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == 'step_loss':
                    fn.body = [n for n in fn.body if not (isinstance(n, ast.If) and ast.unparse(n.test) == "arm == 'k2'")]
            return ast.dump(tree)
        self.assertEqual(isolate(before), isolate(after))


if __name__ == '__main__':unittest.main()
