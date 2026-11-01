import importlib.util
from pathlib import Path
import tempfile
import types
import unittest

import r3_k2_reference_trace as T
import r3_k2_sync_benchmark as B

try:
    import torch
except ImportError:
    torch = None


class Instrumentation(unittest.TestCase):
    def test_observer_runs_after_backward_and_scalar_accumulation(self):
        code = '''def step_loss(exs):
    total = 0.
    for e in exs:
        seqs, starts, s = [e], [0], [e]
        lq = make_loss(e)
        lq.backward()
        total += float(lq.detach())
    return total
'''
        events = []
        class Loss:
            def __init__(self, value): self.value = value
            def backward(self): events.append(('backward', self.value))
            def detach(self): events.append(('scalar', self.value)); return self.value
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/'trainer.py'; source.write_text(code)
            trainer = types.ModuleType('trainer'); trainer.__file__ = str(source)
            trainer.make_loss = Loss
            fn = T.instrument(trainer, lambda e, seqs, starts, s, loss, total: events.append(('observe', e, total)))
            self.assertEqual(fn([1., 2.]), 3.)
            self.assertEqual(events, [('backward',1.),('scalar',1.),('observe',1.,1.),
                                      ('backward',2.),('scalar',2.),('observe',2.,3.)])
            source.write_text(code.replace('total += float(lq.detach())', 'total += 1.'))
            with self.assertRaisesRegex(ValueError, 'boundary differs'):
                T.instrument(trainer, lambda *args: None)


@unittest.skipIf(torch is None, 'torch CPU required')
class Trace(unittest.TestCase):
    def setUp(self):
        self.weight = torch.nn.Parameter(torch.tensor([1., 2.]))
        proxy = types.SimpleNamespace(npu=types.SimpleNamespace(synchronize=lambda: None), isfinite=torch.isfinite)
        self.trace = T.ReferenceTrace(proxy, [('w', self.weight)], lambda _: {'state': 'fixed'},
                                      lambda _, *args: B.equality_diagnostic(torch, *args))

    def observe(self, number, gradient):
        self.weight.grad = torch.tensor(gradient)
        self.trace.observe({'id':number}, [[number, 2]], [1], torch.tensor([-.1, -.2]), torch.tensor(.5), number*.5)

    def test_first_differing_accumulation_is_identified_and_values_not_emitted(self):
        self.observe(1,[1.,2.]); self.observe(2,[2.,4.]); self.trace.begin_repeat()
        self.observe(1,[1.,2.]); self.observe(2,[2.,4.125])
        result = self.trace.summary()
        self.assertTrue(result['complete'])
        self.assertEqual(result['first_difference']['question'],1)
        self.assertEqual(result['first_difference']['gradient_diagnostic']['gradient_max_abs_difference'],.125)
        self.assertFalse(result['scientific_acceptance'])
        self.assertTrue(all(not g for _,g in self.trace.reference))
        self.assertNotIn('seqs', str(result))

    def test_equal_diagnostic_is_complete_but_not_acceptance(self):
        self.observe(1,[1.,2.]);self.trace.begin_repeat();self.observe(1,[1.,2.])
        self.assertTrue(self.trace.summary()['complete'])
        self.assertIsNone(self.trace.summary()['first_difference'])
        self.assertFalse(self.trace.summary()['scientific_acceptance'])

    def test_limits_missing_questions_and_nonfinite_refuse_completion(self):
        self.trace.max_bytes=1
        with self.assertRaisesRegex(ValueError,'memory budget'):self.observe(1,[1.,2.])
        self.assertFalse(self.trace.summary()['complete'])
        self.assertTrue(self.trace.summary()['truncated'])
        self.setUp();self.observe(1,[1.,2.]);self.observe(2,[2.,4.]);self.trace.begin_repeat()
        self.observe(1,[1.,2.]);self.assertFalse(self.trace.summary()['complete'])
        with self.assertRaisesRegex(ValueError,'nonfinite'):self.observe(2,[float('nan'),4.])


if __name__ == '__main__':unittest.main()
