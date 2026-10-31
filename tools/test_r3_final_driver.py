import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
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
        self.prompt=SimpleNamespace(PROMPT_VERSION='synthetic-v1',PROMPT_FORMAT='synthetic')

    def vector_fixture(self):
        self.out.mkdir()
        inventory=self.root/'base-inventory.json';inventory.write_text(json.dumps({'inventory_sha256':'f'*64}))
        plan={'out':str(self.out),'model_sha256':'a'*64,'arm':'K1','model':str(self.root/'base'),'adapter':str(self.root/'adapter'),
              'base_inventory':{'path':str(inventory)},'closure':{'sha256':'d'*64},
              'scoring':{'mode':'rightpad','dtype':'float32','hf32':False,'token_budget':16384,'stages':'k','shards':1}}
        report={'header':{'arm':'K1','model':{'sha256':'a'*64,'kind':'lora-adapter-unmerged',
                  'path':str(self.root/'adapter'),'base_path':str(self.root/'base')},
                  'primary_input_mode':'full','render':'record_name','dtype':'float32','stages':'k',
                  'partitions':['calibration','test'],'limit':0,'limit_groups':0,'dry_run_warnings':[],
                  'prompt_version':'synthetic-v1','prompt_format':'synthetic',
                  'scorer':{'model_path':plan['model'],'adapter':plan['adapter'],'mode':'rightpad',
                    'dtype':'float32','token_budget':16384,'hf32':{'hf32':False},'record_grade':True,
                    'record_grade_problems':[],'render':'record_name','dedup':True}}}
        result={'state':'completed','verified_suites':{suite:{'keys':[str(i) for i in range(n)],
            'correct':[i%2 for i in range(n)],'dataset_sha256':'e'*64,'n':n,'tie_count':0}
            for suite,n in [('decision-v7',1200),('transfer-v4',656)]}}
        training={'arm':'K1','seed':2,'training_variant':{'recipe':'synthetic'}}
        return plan,result,report,training

    def test_verified_vector_export_is_idempotent_and_bound(self):
        plan,result,report,training=self.vector_fixture()
        first=D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)
        self.assertEqual(first,D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt))
        vector=json.loads(Path(first['path']).read_text())
        self.assertEqual(vector['seed'],2);self.assertFalse(vector['scientific_acceptance'])
        self.assertEqual(len(vector['suites']['decision-v7']['correct']),1200)
        result['verified_suites']['decision-v7']['correct'][0]=1
        with self.assertRaisesRegex(ValueError,'vector changed'):D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)

    def test_incomplete_vector_or_model_mismatch_never_exported(self):
        plan,result,report,training=self.vector_fixture()
        wrong=dict(result,state='reserved')
        with self.assertRaisesRegex(ValueError,'not completed'):D.export_vector(plan,self.pin,wrong,report,training,prompt=self.prompt)
        with self.assertRaisesRegex(ValueError,'complete verified'):D.export_vector(plan,self.pin,{'state':'completed'},report,training,prompt=self.prompt)
        report['header']['model']['sha256']='c'*64
        with self.assertRaisesRegex(ValueError,'model/arm'):D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)
        self.assertFalse((self.out/'TEST-VERIFIED-VECTOR.json').exists())

    def test_control_export_uses_actual_drop_protocol_and_recovery_is_idempotent(self):
        plan,result,report,training=self.vector_fixture()
        G=D.local('r3_final_gain_compare')
        plan.update(arm='K1-QO',model=G.CONTROL_BASE)
        report['header'].update(arm='K1-QO',primary_input_mode='drop')
        report['header']['model']['base_path']=plan['model']
        report['header']['scorer']['model_path']=plan['model']
        training['arm']='K1-QO'
        output=D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)
        vector=json.loads(Path(output['path']).read_text())
        self.assertEqual(vector['protocol']['input_mode'],'drop');self.assertEqual(vector['role'],'control')
        self.assertEqual(output,D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt))
        report['header']['primary_input_mode']='full'
        with self.assertRaisesRegex(ValueError,'primary input mode'):D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)
        report['header']['primary_input_mode']='drop';training['seed']=3
        with self.assertRaisesRegex(ValueError,'seed/arm'):D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)

    def test_pt_export_keeps_full_input_and_separate_control_role(self):
        plan,result,report,training=self.vector_fixture()
        G=D.local('r3_final_gain_compare')
        plan.update(arm='K1-PT',model=G.CONTROL_INSTRUCT)
        report['header']['arm']='K1-PT'
        report['header']['model']['base_path']=plan['model']
        report['header']['scorer']['model_path']=plan['model']
        training.update(arm='K1-PT',seed=3)
        output=D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)
        vector=json.loads(Path(output['path']).read_text())
        self.assertEqual(vector['protocol']['input_mode'],'full')
        self.assertEqual(vector['role'],'control');self.assertEqual(vector['seed'],3)

    def test_protocol_hash_excludes_verified_weight_identity_only(self):
        plan,result,report,training=self.vector_fixture()
        first=D.export_vector(plan,self.pin,result,report,training,prompt=self.prompt)
        candidate=json.loads(Path(first['path']).read_text())
        baseline_out=self.root/'baseline';baseline_out.mkdir()
        plan.update(out=str(baseline_out),arm='K0',adapter=None)
        report['header']['arm']='K0';report['header']['scorer']['adapter']=None
        report['header']['model'].update(kind='checkpoint',path=plan['model'])
        second=D.export_vector(plan,self.pin,result,report,prompt=self.prompt)
        baseline=json.loads(Path(second['path']).read_text())
        self.assertEqual(candidate['scoring_protocol_sha256'],baseline['scoring_protocol_sha256'])
        changed_out=self.root/'changed';changed_out.mkdir();plan['out']=str(changed_out)
        report['header']['scorer']['layout']='different-unreviewed-layout'
        changed=D.export_vector(plan,self.pin,result,report,prompt=self.prompt)
        self.assertNotEqual(baseline['scoring_protocol_sha256'],json.loads(Path(changed['path']).read_text())['scoring_protocol_sha256'])

    def test_export_refuses_mismatched_actual_scorer_identity_and_scope(self):
        plan,result,report,training=self.vector_fixture()
        for section,field,value in [('scorer','adapter','/foreign'),('scorer','model_path','/foreign'),
                ('scorer','token_budget',1),('scorer','hf32',{'hf32':True}),('header','stages','t_score'),
                ('header','partitions',['dev']),('header','prompt_version',None)]:
            wrong=copy.deepcopy(report)
            target=wrong['header'] if section=='header' else wrong['header']['scorer'];target[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):D.export_vector(plan,self.pin,result,wrong,training,prompt=self.prompt)
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
