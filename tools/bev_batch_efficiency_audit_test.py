import unittest
from bev_batch_efficiency_audit import shapes

class ShapeTests(unittest.TestCase):
    def test_exact_small_layout_and_padding(self):
        rows=[dict(id='a',lengths=[10,9]),dict(id='b',lengths=[4,4])]
        r=shapes(rows,budget=20)
        self.assertEqual((r['forwards'],r['useful_tokens'],r['forwarded_tokens'],r['padded_tokens']),(2,27,28,1))
    def test_bucketing_preserves_population_reduces_mixed_padding(self):
        rows=[dict(id=str(i),lengths=[n,n]) for i,n in enumerate([100,10,100,10])]
        a=shapes(rows,budget=1000,chunk=2);b=shapes(rows,budget=1000,chunk=2,order='length')
        self.assertEqual(a['useful_tokens'],b['useful_tokens']);self.assertEqual(a['candidate_rows'],b['candidate_rows'])
        self.assertGreater(a['padded_tokens'],b['padded_tokens']);self.assertEqual(b['padded_tokens'],0)
    def test_wide_row_budget_is_not_truncation(self):
        r=shapes([dict(id='a',lengths=[31,30])],budget=10)
        self.assertEqual(r['forwards'],2);self.assertEqual(r['useful_tokens'],61)
    def test_reject_duplicate_ids_or_invalid_order(self):
        with self.assertRaises(ValueError):shapes([dict(id='x',lengths=[1])]*2)
        with self.assertRaises(ValueError):shapes([dict(id='x',lengths=[1])],order='unknown')

if __name__=='__main__':unittest.main()
