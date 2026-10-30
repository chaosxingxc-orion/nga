import importlib.util
import json
from pathlib import Path
import unittest


def module(name):
    s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

m=module('reference_kev_devtools');v=module('verify_reference_kev_devtools')

class DualPopulation(unittest.TestCase):
    def test_collision_is_not_overwritten(self):
        records=[{'_meta':{'id':'same'},'state':'first'},{'_meta':{'id':'same'},'state':'second'}]
        keys=m.record_keys(records)
        self.assertEqual(len(keys),2);self.assertNotEqual(keys[0]['input_sha256'],keys[1]['input_sha256'])
        self.assertEqual([k['index'] for k in keys],[0,1])
    def test_drop_removes_both_not_one(self):
        rows=[{'id':'same'},{'id':'different'},{'id':'same'}]
        self.assertEqual(m.release_rows(rows,['same']),[{'id':'different'}])
    def test_original_frozen_counts(self):
        root=Path('/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev')
        rows=[json.loads(x) for x in (root/'evals/devtools-v1/test.jsonl').read_text().splitlines()]
        drop=json.loads((root/'experiments/releases/kev-08b-r15.json').read_text())['drop_ids']
        self.assertEqual(len(rows),900);self.assertEqual(sum(len(r['questions']) for r in rows),1073)
        self.assertEqual([i for i,r in enumerate(rows) if r['_meta']['id'] in drop],[570,622])
        self.assertEqual(sum(len(r['questions']) for r in rows if r['_meta']['id'] not in drop),1071)
    def test_independent_wrong_denominator_rejected(self):
        actual={'n':1073,'acc':.5,'brier':.5,'ece':0.,'nll':.7}
        with self.assertRaisesRegex(ValueError,'denominator'):v.compare_metrics(actual,{**actual,'n':1071},'release')
    def test_independent_wrong_aggregate_rejected(self):
        actual={'n':1071,'acc':.5,'brier':.5,'ece':0.,'nll':.7}
        with self.assertRaises(ValueError):v.compare_metrics({**actual,'acc':1.},actual,'release')

if __name__=='__main__':unittest.main()
