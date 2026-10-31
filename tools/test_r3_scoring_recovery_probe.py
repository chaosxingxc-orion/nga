"""Fail-closed recovery evidence checks; no scorer, checkpoint or NPU access."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

import r3_scoring_recovery_probe as P

SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2/r3_code/core_r3.py')

class RecoveryEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():raise unittest.SkipTest('frozen original core absent')
        spec=importlib.util.spec_from_file_location('core_for_probe_test',SOURCE)
        cls.C=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.C)

    def setUp(self):
        self.rows=[{'kev':{'id':str(i),'qindex':0},'source':'synthetic','level_type':'nominal',
                    'qname':'q','levels':[{'id':'a'},{'id':'b'}],'gold':'a'} for i in range(8)]
        self.readouts=[self.C.readout_row(r,[0.,-1.]) for r in self.rows]

    def test_exact_and_within_tolerance(self):
        self.assertEqual(P.compare_readouts(self.rows,self.readouts,self.readouts,self.C),0.)
        other=copy.deepcopy(self.readouts);other[-1]['s'][1]+=0.0005
        self.assertLess(P.compare_readouts(self.rows,self.readouts,other,self.C),1e-3)

    def test_nonfinite_values_in_either_operand_rejected(self):
        for value in (float('nan'),float('inf'),-float('inf'),True,'0'):
            for side in (0,1):
                pair=[copy.deepcopy(self.readouts),copy.deepcopy(self.readouts)]
                pair[side][-1]['s'][1]=value
                with self.subTest(value=value,side=side),self.assertRaises(ValueError):
                    P.compare_readouts(self.rows,*pair,self.C)

    def test_truncation_extra_duplicate_wrong_population_rejected(self):
        cases=[self.readouts[:-1],self.readouts+[self.readouts[-1]],
               self.readouts[:-1]+[self.readouts[0]],list(reversed(self.readouts))]
        x=copy.deepcopy(self.readouts);x[-1]['s']=[0.];cases.append(x)
        x=copy.deepcopy(self.readouts);x[-1]['s'].append(-2.);cases.append(x)
        for bad in cases:
            with self.subTest(bad=bad[-1]),self.assertRaises(ValueError):
                P.compare_readouts(self.rows,bad,bad,self.C)

    def test_self_consistent_wrong_metadata_rejected(self):
        for key,value in (('argmax',1),('tie',True),('ids',['b','a']),('gold','b'),('argmax',False)):
            bad=copy.deepcopy(self.readouts);bad[0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                P.compare_readouts(self.rows,bad,bad,self.C)

    def test_tolerance_and_decision_disagreement_rejected(self):
        for scores in ([0.,-0.9],[-0.0001,0.]):
            other=copy.deepcopy(self.readouts);other[0]=self.C.readout_row(self.rows[0],scores)
            reference=copy.deepcopy(self.readouts)
            if scores[0]<0:reference[0]=self.C.readout_row(self.rows[0],[0.,-0.0001])
            with self.assertRaises(ValueError):P.compare_readouts(self.rows,reference,other,self.C)

    def test_truncated_batch_rejected_before_storage(self):
        with self.assertRaisesRegex(ValueError,'batch population'):
            P.validate_scores(self.rows,[[0.,-1.] for _ in range(7)])

    def test_interruption_binds_exact_first_two_keys_plan_and_bytes(self):
        prefix=b'committed prefix\n';pin='a'*64
        marker={'committed':2,'keys':['0/0','1/0'],'plan_sha256':pin,
                'prefix_sha256':hashlib.sha256(prefix).hexdigest()}
        P.validate_interruption(marker,pin,self.rows,self.readouts[:2],prefix,self.C)
        for key,value in (('committed',3),('keys',['2/0','3/0']),('plan_sha256','b'*64),('prefix_sha256','c'*64)):
            bad=dict(marker);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                P.validate_interruption(bad,pin,self.rows,self.readouts[:2],prefix,self.C)
        with self.assertRaises(ValueError):
            P.validate_interruption(marker,pin,self.rows,self.readouts[2:4],prefix,self.C)

    def test_module_origin_must_be_exact_frozen_file(self):
        root=Path('/tmp/frozen');m=types.SimpleNamespace(__name__='eval_r3',__file__='/tmp/frozen/r3_code/eval_r3.py')
        P.validate_origin(m,root)
        for path in ('/tmp/elsewhere/eval_r3.py','/tmp/frozen/r0_code/eval_r3.py'):
            m.__file__=path
            with self.assertRaises(ValueError):P.validate_origin(m,root)

    def test_sample_keys_preserved_and_cross_suite_collision_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            sources={}
            for suite,rows in zip(('decision-v7','transfer-v4'),(self.rows[:4],self.rows[4:])):
                path=Path(directory)/suite/'dev.jsonl';path.parent.mkdir()
                path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
                sources[suite]={'path':str(path),'sha256':P.sha(path),'indices':[0,1,2,3]}
            self.assertEqual(P.sample_rows(sources,self.C),self.rows)
            path=Path(sources['transfer-v4']['path'])
            path.write_text(''.join(json.dumps(r)+'\n' for r in self.rows[:4]))
            sources['transfer-v4']['sha256']=P.sha(path)
            with self.assertRaisesRegex(ValueError,'keys overlap'):P.sample_rows(sources,self.C)

if __name__=='__main__':unittest.main()
