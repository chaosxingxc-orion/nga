import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).parent
def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
M = load('r3_reference_metrics')
R = load('verify_reference_kev')


class Metrics(unittest.TestCase):
    def test_uniform_variable_options_and_ties(self):
        d = M.summarize([[0, 0], [0, 0, 0, 0], [4]], [0, 2, 0])
        self.assertEqual(d['accuracy'], 2/3); self.assertEqual(d['tie_count'], 2)
        self.assertAlmostEqual(d['brier_sum'], (0.5 + 0.75)/3)
        self.assertAlmostEqual(d['nll'], (math.log(2)+math.log(4))/3)
        self.assertEqual(sum(b['n'] for b in d['ece10_bins']), 3)
        json.dumps(d, allow_nan=False)

    def test_reference_formula_agreement(self):
        rng = random.Random(28)
        for count in (1, 17, 93):
            scores = [[rng.uniform(-40, 5) for _ in range(rng.randint(2, 12))] for _ in range(count)]
            gold = [rng.randrange(len(s)) for s in scores]
            reference = R.metrics([{'logits':s, 'p':R.softmax(s), 'label':y} for s,y in zip(scores,gold)])
            actual = M.summarize(scores, gold)
            self.assertEqual(actual['probability_argmax_mismatch_count'],0)
            for a,b in [('accuracy','acc'),('brier_sum','brier'),('ece10','ece'),('nll','nll')]:
                self.assertAlmostEqual(actual[a], reference[b], places=12)

    def test_reference_probability_argmax_is_a_distinct_convention(self):
        scores=[[0.,1e-20],[.01,0.]]; gold=[1,0]
        actual=M.summarize(scores,gold)
        reference=R.metrics([{'logits':s,'p':R.softmax(s),'label':y} for s,y in zip(scores,gold)])
        self.assertEqual(actual['accuracy'],1.)
        self.assertEqual(reference['acc'],.5)
        self.assertEqual(actual['probability_argmax_mismatch_count'],1)
        self.assertNotEqual(actual['ece10'],reference['ece'])
        self.assertEqual(actual['brier_sum'],reference['brier'])

    def test_ece_edges_and_empty_bins(self):
        confidence = list(M.EDGES)
        value, bins = M.ece10([0]*11, confidence)
        self.assertEqual([b['n'] for b in bins], [1]*9+[2])
        self.assertAlmostEqual(value, math.fsum(confidence)/11)
        _, sparse = M.ece10([1], [1.])
        self.assertIsNone(sparse[0]['accuracy']); self.assertEqual(sparse[0]['contribution'], 0)
        below = math.nextafter(M.EDGES[3], 0)
        _, bins = M.ece10([0, 1], [below, M.EDGES[3]])
        self.assertEqual([bins[2]['n'], bins[3]['n']], [1, 1])

    def test_large_losses_translation_and_rounding_mismatch(self):
        d = M.summarize([[0., -10000.]], [1])
        self.assertEqual((d['nll'],d['brier_sum'],d['ece10']), (10000.,2.,1.))
        self.assertEqual(M.summarize([[0., -1e308]]*2, [1,1])['nll'], 1e308)
        row=[-1., -sys.float_info.max]
        self.assertEqual(M.summarize([row]*3,[1]*3)['nll'], M.summarize([row],[1])['nll'])
        a = M.summarize([[0., -4., -3.]], [2]); b = M.summarize([[1e12, 1e12-4, 1e12-3]], [2])
        self.assertEqual(a,b)
        d = M.summarize([[0., 1e-20]], [1])
        self.assertEqual(d['accuracy'],1); self.assertEqual(d['probability_argmax_mismatch_count'],1)
        self.assertEqual(d['tie_count'],0)
        with self.assertRaises(ValueError): M.summarize([[1e308,-1e308]],[1])

    def test_malformed_populations_refused(self):
        cases = [([],[]),([[0]],[]),([[]],[0]),([[True,0]],[0]),([[float('nan'),0]],[0]),
                 ([[float('inf'),0]],[0]),([[0,1]],[True]),([[0,1]],[2]),([[0,1]],[-1]),
                 ([[0,'1']],[0]),([[0,10**1000]],[0])]
        for scores,gold in cases:
            with self.subTest(scores=str(scores)[:50]), self.assertRaises(ValueError): M.summarize(scores,gold)
        with self.assertRaises(ValueError): M.ece10([1],[1.01])

    def test_specification_identity_and_no_authorization(self):
        path=HERE.parent/'experiments/R3-REFERENCE-METRICS-SUPPLEMENT-2026-11-01.md'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),M.SPECIFICATION_SHA256)
        d=M.summarize([[1,0]],[0]); self.assertFalse(d['scientific_acceptance']); self.assertFalse(d['publication_authorized'])


if __name__ == '__main__': unittest.main()
