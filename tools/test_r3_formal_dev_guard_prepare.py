import copy
import json
from pathlib import Path
import tempfile
import unittest
from tools import r3_formal_dev_guard_prepare as G

class GuardPreparationTests(unittest.TestCase):
    def fixture(self):
        role={'role':'primary_s3','chip':2,'schedule_sha256':'s'}
        spec={'training_variant':{'formal_role_identity':role},'training':'/wave/primary_s3'}
        execution={'chip':2}
        previous={'schema':'r3-formal-k1-plan-v1','test_read':False,'scientific_acceptance':False,'formal_role':'diffchip_s2','chip':2,'formal_schedule':'/wave/schedule.json','formal_schedule_sha256':'s','out':'/wave/diffchip_s2'}
        schedule={'nodes':[{'id':'primary_s3','out':'/wave/primary_s3'},{'id':'diffchip_s2','out':'/wave/diffchip_s2'},{'id':'primary_s3_dev','kind':'dev_calibration_track_t_readout','training_id':'primary_s3','depends_on':['diffchip_s2_release'],'chip':2}]}
        return [spec,execution,previous,schedule,{'path':'/wave/diffchip_s2/plan.json','sha256':'p'},{'path':'/wave/schedule.json','sha256':'s'}]
    def test_registered_training_edge(self):
        self.assertEqual(G.edge(*self.fixture()),('primary_s3','primary_s3_dev'))
    def test_wrong_edge_chip_schedule_and_scope_reject(self):
        for obj,key,value in [(1,'chip',1),(2,'formal_role','samechip_s2'),(2,'formal_schedule_sha256','x'),(2,'test_read',True),(2,'control_arm','PT')]:
            a=self.fixture();a[obj][key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):G.edge(*a)
    def test_eval_predecessor_not_supported(self):
        a=self.fixture();a[3]['nodes'][-1]['depends_on']=['primary_s3_dev_release']
        with self.assertRaisesRegex(ValueError,'training edge'):G.edge(*a)
    def test_relocation_only_changes_two_argv_paths(self):
        s={'command':['x','--out','/old/results','--round-dir','/old/identity','--model','/old/model'],'unchanged':{'n':5}}
        original=copy.deepcopy(s);v=G.relocated(s,Path('/old'),Path('/new'))
        self.assertEqual(s,original);self.assertEqual(v['command'][-1],'/old/model');self.assertEqual(v['unchanged'],s['unchanged'])
        v['command'][2]='/old/results';v['command'][4]='/old/identity';self.assertEqual(v,s)
    def test_duplicate_or_wrong_outputs_reject(self):
        for cmd in [['--out','/old/results','--out','/old/results','--round-dir','/old/identity'],['--out','/foreign/results','--round-dir','/old/identity']]:
            with self.assertRaises(ValueError):G.relocated({'command':cmd},Path('/old'),Path('/new'))
    def test_hash_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('{}');ref=G.pin(p);self.assertEqual(G.pinned(ref),p)
            p.write_text('[]')
            with self.assertRaises(ValueError):G.pinned(ref)
            q=Path(d)/'q';q.symlink_to(p)
            with self.assertRaises(ValueError):G.pin(q)
if __name__=='__main__':unittest.main()
