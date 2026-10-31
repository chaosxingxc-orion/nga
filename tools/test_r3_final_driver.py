import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('driver',Path(__file__).with_name('r3_final_driver.py'))
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)


class Driver(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'out';self.plan=self.root/'plan.json'
        p={'out':str(self.out)};self.plan.write_text(json.dumps(p))
        self.pin=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.review={'path':str(self.root/'review.json'),'sha256':'b'*64}

    def vector_fixture(self):
        self.out.mkdir()
        inventory=self.root/'base-inventory.json';inventory.write_text(json.dumps({'inventory_sha256':'f'*64}))
        plan={'out':str(self.out),'model_sha256':'a'*64,'arm':'K1',
              'base_inventory':{'path':str(inventory)},'closure':{'sha256':'d'*64},
              'scoring':{'mode':'rightpad','dtype':'float32','hf32':False,'token_budget':16384,'stages':'k','shards':1}}
        report={'header':{'arm':'K1','model':{'sha256':'a'*64,'kind':'lora-adapter-unmerged',
                  'path':str(self.root/'adapter'),'base_path':str(self.root/'base')}}}
        result={'state':'completed','verified_suites':{suite:{'keys':[str(i) for i in range(n)],
            'correct':[i%2 for i in range(n)],'dataset_sha256':'e'*64,'n':n,'tie_count':0}
            for suite,n in [('decision-v7',1200),('transfer-v4',656)]}}
        training={'arm':'K1','seed':2,'training_variant':{'recipe':'synthetic'}}
        return plan,result,report,training

    def test_verified_vector_export_is_idempotent_and_bound(self):
        plan,result,report,training=self.vector_fixture()
        first=D.export_vector(plan,self.pin,result,report,training)
        self.assertEqual(first,D.export_vector(plan,self.pin,result,report,training))
        vector=json.loads(Path(first['path']).read_text())
        self.assertEqual(vector['seed'],2);self.assertFalse(vector['scientific_acceptance'])
        self.assertEqual(len(vector['suites']['decision-v7']['correct']),1200)
        result['verified_suites']['decision-v7']['correct'][0]=1
        with self.assertRaisesRegex(ValueError,'vector changed'):D.export_vector(plan,self.pin,result,report,training)

    def test_incomplete_vector_or_model_mismatch_never_exported(self):
        plan,result,report,training=self.vector_fixture()
        wrong=dict(result,state='reserved')
        with self.assertRaisesRegex(ValueError,'not completed'):D.export_vector(plan,self.pin,wrong,report,training)
        with self.assertRaisesRegex(ValueError,'complete verified'):D.export_vector(plan,self.pin,{'state':'completed'},report,training)
        report['header']['model']['sha256']='c'*64
        with self.assertRaisesRegex(ValueError,'model/arm'):D.export_vector(plan,self.pin,result,report,training)
        self.assertFalse((self.out/'TEST-VERIFIED-VECTOR.json').exists())

    def test_success_retains_result_terminal_and_heartbeat(self):
        with patch.object(D,'evaluate',return_value={'state':'completed','scientific_acceptance':False}):
            self.assertEqual(D.run(self.plan,self.pin,self.review,1),0)
        directory=self.out/'final-attempts/1'
        self.assertEqual(json.loads((directory/'EXIT.json').read_text())['exit_code'],0)
        self.assertTrue((directory/'heartbeat.json').exists())
        self.assertTrue((directory/'COMMAND.txt').exists())
        self.assertEqual((directory/'EXIT.json').stat().st_mode & 0o777,0o644)
        self.assertFalse(json.loads((directory/'EXIT.json').read_text())['scientific_acceptance'])

    def test_failure_retained_then_new_attempt_does_not_erase_evidence(self):
        with patch.object(D,'evaluate',side_effect=ValueError('admission failure')):
            self.assertEqual(D.run(self.plan,self.pin,self.review,1),1)
        with patch.object(D,'evaluate',return_value={'state':'completed'}):
            self.assertEqual(D.run(self.plan,self.pin,self.review,2),0)
        self.assertEqual(json.loads((self.out/'final-attempts/1/EXIT.json').read_text())['exit_code'],1)
        self.assertEqual(json.loads((self.out/'FINAL_EVAL_EXIT.json').read_text())['attempt'],2)
        with self.assertRaises(FileExistsError):D.run(self.plan,self.pin,self.review,2)

    def test_unpinned_plan_never_creates_output(self):
        with self.assertRaisesRegex(ValueError,'plan differs'):D.run(self.plan,'f'*64,self.review,1)
        self.assertFalse(self.out.exists())

    def test_terminal_records_process_level_exception(self):
        with patch.object(D,'evaluate',side_effect=KeyboardInterrupt):
            self.assertEqual(D.run(self.plan,self.pin,self.review,1),1)
        self.assertEqual(json.loads((self.out/'FINAL_EVAL_EXIT.json').read_text())['exit_code'],1)


if __name__=='__main__':unittest.main()
