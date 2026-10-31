import importlib.util
from pathlib import Path
import unittest
s=importlib.util.spec_from_file_location('num',Path(__file__).with_name('r3_fastref_numerics.py'))
N=importlib.util.module_from_spec(s);s.loader.exec_module(N)

class Admission(unittest.TestCase):
    def test_all_nonfinite_inputs_rejected(self):
        for slot in range(9):
            for bad in (float('nan'),float('inf'),-float('inf')):
                values=[1.0]*5+[0.01,0.02,0.01,0.01]
                values[slot]=bad
                with self.subTest(slot=slot,bad=bad),self.assertRaises(ValueError):
                    N.judge(values[:5],values[5:])
    def test_zero_floor_is_valid_without_division(self):
        self.assertIsNone(N.judge([1]*5,[0,0,0,0])['gradient_floor_ratio'])
    def test_each_original_threshold(self):
        N.judge([1]*5,[.02,.02,.012,.01])
        for distances in ([.021,.02,.01,.01],[.01,.02,.0121,.01]):
            with self.assertRaises(ValueError):N.judge([1]*5,distances)
        with self.assertRaises(ValueError):N.judge([1,1.01,1,1,1],[0,0,0,0])
    def test_finite_inputs_with_overflow_are_rejected(self):
        with self.assertRaises(ValueError):N.judge([-1e308,1e308,1e308,1,1],[0,0,0,0])

if __name__=='__main__':unittest.main()
