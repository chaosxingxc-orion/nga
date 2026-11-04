"""Portable first-K1 diagnostic refusal and replacement-dispatch fixtures."""
import copy
import unittest
from unittest.mock import patch
from tools import r3_dev_qualification_recovery_v4 as M


def report(status='void', flip=.2):
    return {'track_t': {'selection': {'typed-decisions': {'boolean': {
        'b2_status': status, 'b2_gap': .01 if status=='void' else .15,
        'flip_T1_argmax': flip, 'n_units': 10, 'n_pairs_used': 60,
        'n_pairs_dropped_tie': 0}}}}}


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.primary=[report(), report()]
        self.repeats={'samechip': report('fail', .3), 'diffchip': report('pass', .4)}
    def call(self):return M.typed_diagnostics(self.primary,self.repeats,['boolean'])
    def test_void_is_retained_and_not_numeric_zero_or_gate(self):
        before=copy.deepcopy((self.primary,self.repeats)); d=self.call()['cells']['boolean']
        self.assertEqual(d['observations']['primary_s2']['b2_status'],'void')
        for c in d['comparisons'].values():
            self.assertIsNone(c['difference']); self.assertFalse(c['gating']);self.assertEqual(c['status'],'VOID_OPERAND')
        self.assertEqual(before,(self.primary,self.repeats))
    def test_nonvoid_difference_is_descriptive(self):
        self.primary[0]=report('pass',.2);d=self.call()['cells']['boolean']['comparisons']
        self.assertAlmostEqual(d['samechip']['difference'],.1);self.assertFalse(d['diffchip']['gating'])
    def test_void_repeat_not_valid_floor(self):
        self.primary[0]=report('pass');self.repeats['diffchip']=report();d=self.call()
        self.assertIsNone(d['cells']['boolean']['comparisons']['diffchip']['difference'])
    def test_missing_repeat_refuses(self):
        del self.repeats['samechip']
        with self.assertRaises(ValueError):self.call()
    def test_empty_and_invalid_counts_refuse(self):
        for key,val in [('n_units',0),('n_units',True),('n_pairs_used',0),('n_pairs_dropped_tie',-1)]:
            with self.subTest(key=key,val=val):
                p=copy.deepcopy(self.primary);p[1]['track_t']['selection']['typed-decisions']['boolean'][key]=val
                with self.assertRaises(ValueError):M.typed_diagnostics(p,self.repeats,['boolean'])
    def test_mismatched_structural_population_refuses(self):
        self.repeats['samechip']['track_t']['selection']['typed-decisions']['boolean']['n_units']=11
        with self.assertRaises(ValueError):self.call()
    def test_nonfinite_and_out_of_range_refuse(self):
        for key,val in [('flip_T1_argmax',float('nan')),('flip_T1_argmax',1.1),('b2_gap',float('inf')),('b2_gap',2)]:
            with self.subTest(key=key,val=val):
                p=copy.deepcopy(self.primary);p[0]['track_t']['selection']['typed-decisions']['boolean'][key]=val
                with self.assertRaises(ValueError):M.typed_diagnostics(p,self.repeats,['boolean'])
    def test_unknown_status_and_missing_cell_refuse(self):
        self.primary[0]['track_t']['selection']['typed-decisions']['boolean']['b2_status']='unknown'
        with self.assertRaises(ValueError):self.call()
        self.primary[0]['track_t']['selection']['typed-decisions']={}
        with self.assertRaises(KeyError):self.call()
    def test_no_r0_active_refuses(self):
        with self.assertRaises(ValueError):M.typed_diagnostics(self.primary,self.repeats,[])
    def test_replacement_and_unknown_branch_delegate_unchanged(self):
        for branch in ('replacement','bad'):
            with patch.object(M,'_original_numerical',return_value={'sentinel':branch}) as fn:
                a,b,c=object(),object(),object();self.assertEqual(M.numerical(a,b,c,branch),{'sentinel':branch});fn.assert_called_once_with(a,b,c,branch)
    def test_replacement_exception_unchanged(self):
        with patch.object(M,'_original_numerical',side_effect=ValueError('original replacement refusal')):
            with self.assertRaisesRegex(ValueError,'original replacement refusal'):M.numerical({},None,None,'replacement')

if __name__=='__main__':unittest.main()
