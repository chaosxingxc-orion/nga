import importlib.util
from pathlib import Path
import unittest

s=importlib.util.spec_from_file_location('probe',Path(__file__).with_name('r3_prefix_probe.py'))
P=importlib.util.module_from_spec(s);s.loader.exec_module(P)


class Probe(unittest.TestCase):
    def test_stratification_is_deterministic_and_without_duplicates(self):
        rows=[{'levels':list(range(n))} for n in (77,2,4,77,2,4,10)]
        selected=P.select(rows)
        self.assertEqual(selected,[1,2,6,0,4,5])
        self.assertEqual(len(set(selected)),6)
        many=[{'levels':list(range(n))} for n in range(2,22)]
        selected=P.select(many)
        self.assertEqual((selected[0],selected[-1]),(0,19))

    def test_changed_argmax_far_from_tie_and_tied_candidate_refused(self):
        self.assertFalse(P.compare([[0.,-.002]], [[-.0008,-.0008]])['pass'])
        self.assertTrue(P.compare([[0.,-.0005]], [[-.0005,0.]])['pass'])
        self.assertEqual(len(P.compare([[0.,-.0005]], [[-.0005,0.]])['near_ties']),1)

    def test_constant_shift_and_wrong_candidate_counterpart_rejected(self):
        self.assertFalse(P.compare([[0.,-1.]], [[.01,-.99]])['pass'])
        self.assertFalse(P.compare([[0.,-1.]], [[.01,-.98]])['pass'])
        self.assertTrue(P.compare([[0.,-1.]], [[.0001,-.9999]])['pass'])

    def test_nonfinite_and_population_change_refused(self):
        for value in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):P.compare([[0.,-1.]],[[value,-1.]])
        with self.assertRaises(ValueError):P.compare([[0.,-1.]],[[0.]])


if __name__=='__main__':unittest.main()
