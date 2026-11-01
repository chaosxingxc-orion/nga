import importlib.util
from pathlib import Path
import unittest
try:
    import torch
except ImportError:
    torch = None
spec = importlib.util.spec_from_file_location('boundary', Path(__file__).with_name('r3_k2_boundary_trace.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


@unittest.skipIf(torch is None, 'torch required')
class Boundary(unittest.TestCase):
    def replay(self, changed=False):
        p = torch.nn.Parameter(torch.tensor([1., 2.]))
        t = M.BoundaryTrace(torch, [('p', p)])
        t.install()
        try:
            for phase in range(2):
                if phase: t.begin_repeat()
                p.grad = None
                for question in range(12):
                    scores = p * (2 if changed and phase and question == 1 else 1)
                    if question == 5:
                        t.chunk()
                        t.reduction('before', [0, 0], scores)
                        t.reduction('after', [0, 0], scores.sum().reshape(1))
                    t.before(scores)
                    (scores.sum()/12).backward()
                    t.after()
            return t.summary(), p.grad
        finally: t.close()

    def test_observational_hooks_preserve_gradient_and_exact_repeat(self):
        result, gradient = self.replay()
        self.assertTrue(result['complete'])
        self.assertTrue(result['event_order_equal'])
        self.assertEqual(result['incoming_events'], 1)
        self.assertTrue(all(x['values_equal'] for x in result['comparisons']))
        self.assertTrue(torch.allclose(gradient, torch.ones(2)))

    def test_incoming_difference_does_not_blame_accumulator(self):
        result, _ = self.replay(True)
        bykey = {tuple(x['key']): x for x in result['comparisons']}
        self.assertTrue(bykey['prior', 1, 'p']['values_equal'])
        self.assertFalse(bykey['incoming', 'p', 0]['values_equal'])
        self.assertFalse(bykey['post', 1, 'p']['values_equal'])

    def test_budgets_nonfinite_and_missing_events_fail_closed(self):
        t = M.BoundaryTrace(torch, [], max_bytes=3)
        with self.assertRaisesRegex(ValueError, 'memory'): t.capture(('x',), torch.ones(1))
        t = M.BoundaryTrace(torch, [])
        with self.assertRaisesRegex(ValueError, 'nonfinite'): t.capture(('x',), torch.tensor([float('nan')]))
        self.assertFalse(t.summary()['complete'])
        t = M.BoundaryTrace(torch, [], max_events=0)
        with self.assertRaisesRegex(ValueError, 'event'): t.capture(('x',), None)

    def test_symmetric_missing_leaf_and_reduction_is_incomplete(self):
        p = torch.nn.Parameter(torch.ones(1))
        unused = torch.nn.Parameter(torch.ones(1))
        t = M.BoundaryTrace(torch, [('used', p), ('unused', unused)])
        t.install()
        try:
            for phase in range(2):
                if phase: t.begin_repeat()
                p.grad = unused.grad = None
                for question in range(12):
                    scores = p + unused if question == 0 else p
                    t.before(scores)
                    scores.sum().backward()
                    t.after()
            result = t.summary()
            self.assertFalse(result['complete'])
            self.assertEqual(result['incoming_events'], 1)
            self.assertEqual(result['coverage'][0]['missing_incoming_leaves'], ['unused'])
            self.assertFalse(result['coverage'][0]['paired_reductions_complete'])
        finally: t.close()


if __name__ == '__main__': unittest.main()
