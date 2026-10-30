import copy
import importlib.util
from pathlib import Path
import unittest

s=importlib.util.spec_from_file_location('comparison',Path(__file__).with_name('compare_kev9_extended_rows.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class ComparisonTests(unittest.TestCase):
    def fixture(self):
        records=[{'_meta':{'id':'collision','source':'source','variant':'clean'},'questions':{'q':{'type':'choice','criteria':{'a':'A','b':'B'},'label':'a','src':'task'}},'state':str(i)} for i in range(2)]
        upstream=[];local=[]
        for i,record in enumerate(records):
            base={'id':'collision','question':'q','keys':['a','b'],'label':0,'source':'source','variant':'clean','type':'choice','task':'task'}
            upstream.append({**base,'logits':[2.,0.],'p':m.softmax([2.,0.]),'inference_temperature':1.})
            local.append({**base,'logits':[1.,0.],'p':m.softmax([1.,0.]),'inference_temperature':2.,'record_index':i,'question_index':0,'input_sha256':m.objsha(record)})
        return upstream,local,records
    def test_temperature_and_collisions(self):
        u,l,r=self.fixture();result=m.compare(u,l,r,[],2.)
        self.assertEqual(result['rows_verified'],2)
        for p in result['populations']['full'].values():
            self.assertEqual(p['max_probability_delta'],0.)
            self.assertEqual(p['ece_bin_changes'],0)
            self.assertEqual(p['argmax_changes'],[])
    def test_bad_ordered_source_binding(self):
        u,l,r=self.fixture();l.reverse()
        with self.assertRaisesRegex(ValueError,'source binding'):m.compare(u,l,r,[],2.)
    def test_changed_candidate_order(self):
        u,l,r=self.fixture();u[0]['keys'].reverse()
        with self.assertRaisesRegex(ValueError,'Identity differs'):m.compare(u,l,r,[],2.)
    def test_temperature_not_applied_twice(self):
        row={'logits':[1.,0.],'inference_temperature':2.}
        self.assertEqual(m.probs(row,2.),m.softmax([1.,0.]))
        self.assertEqual(m.probs(row,1.),m.softmax([2.,0.]))
    def test_ece_edges(self):
        self.assertEqual(m.bin10(.6),5)
        self.assertEqual(m.bin10(.6000000000000001),6)
        self.assertEqual(m.bin10(1.),9)

if __name__=='__main__':unittest.main()
