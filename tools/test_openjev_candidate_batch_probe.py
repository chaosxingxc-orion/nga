"""Probe arithmetic must not hide changed native output contracts."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from openjev_candidate_batch_probe import compare

class Comparison(unittest.TestCase):
    def item(self):
        return {'prediction':{'logits':[1.,0.],'native_probabilities':{'0':.75,'1':.25},'answer':{'type':'score','score':.25,'probabilities':{'0':.75,'1':.25},'legend':{'0':'low','1':'high'},'confidence':.5},'consumed_token_sha256':['a','b']}}
    def test_identical_and_real_numeric_drift(self):
        a=self.item();b=copy.deepcopy(a);self.assertTrue(compare(a,b)['wire_exact'])
        b['prediction']['logits'][0]+=.1;self.assertAlmostEqual(compare(a,b)['logits'],.1)
    def test_legend_text_not_ignored_by_numeric_flattening(self):
        a=self.item();b=copy.deepcopy(a);b['prediction']['answer']['legend']['0']='other'
        with self.assertRaisesRegex(ValueError,'legend'):compare(a,b)
    def test_wire_candidate_order_not_silently_accepted(self):
        a=self.item();b=copy.deepcopy(a);b['prediction']['answer']['probabilities']={'1':.25,'0':.75}
        with self.assertRaisesRegex(ValueError,'order'):compare(a,b)
    def test_token_change_exposed(self):
        a=self.item();b=copy.deepcopy(a);b['prediction']['consumed_token_sha256'].reverse()
        self.assertFalse(compare(a,b)['tokens_same'])

if __name__=='__main__':unittest.main()
