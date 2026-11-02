"""CPU integration-contract tests; no watcher/service or qualifier authority."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import r3_dev_qualification_service as S

ROOT=Path(__file__).resolve().parents[1]
PREPARATION=ROOT/'.local/preparations/production-dev-qualification-20261102-v2'


class ProductionConfiguration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref=json.loads((PREPARATION/'CONFIG-PIN.json').read_text())
        spec=importlib.util.spec_from_file_location('prepared_service',PREPARATION/'r3_dev_qualification_service.py')
        cls.consumer=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.consumer)
    def test_real_immutable_configuration_and_specific_wait(self):
        config=self.consumer.verify(**dict(path=self.ref['path'],pin=self.ref['sha256']))
        result=self.consumer.status(config)
        self.assertEqual(result['status'],'WAIT')
        self.assertFalse(result['candidate_eligibility_granted'])
        self.assertEqual(set(config['members']),{'primary_s2','primary_s3','samechip_s2','diffchip_s2','qo_s2','pt_s2','pt_s3','k0_base','k0_instruct'})
        missing={(x['member'],Path(x['path']).name) for x in result['missing']}
        self.assertIn(('campaign','ADJUDICATION.json'),missing)
        self.assertIn(('campaign','BUNDLE.json'),missing)
        self.assertIn(('k0_base','k0_base.json'),missing)
    def test_real_partial_qualifier_stays_wait(self):
        result=json.loads((PREPARATION/'PARTIAL-RESULT.json').read_text())
        self.assertEqual(result['status'],'WAIT');self.assertFalse(result['candidate_eligibility_granted'])
        self.assertIn('independent campaign adjudication',' '.join(result['missing']))
    def test_config_pin_mutation_rejected(self):
        with self.assertRaisesRegex(ValueError,'pin changed'):
            self.consumer.verify(self.ref['path'],'a'*64)
    def test_no_watch_without_exact_activation(self):
        with self.assertRaisesRegex(ValueError,'activation required'):
            self.consumer.main(['watch','--config',self.ref['path'],'--sha256',self.ref['sha256']])


class ReadinessAndConsumption(unittest.TestCase):
    def test_presence_never_grants_eligibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'done.json';p.write_text('{}')
            result=S.status({'required_paths':[{'path':str(p),'member':'campaign','purpose':'fixture'}]})
            self.assertEqual(result['status'],'READY_FOR_PINNED_CONSUMPTION')
            self.assertFalse(result['candidate_eligibility_granted'])
    def test_test_and_symlink_paths_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.jsonl'
            with self.assertRaisesRegex(ValueError,'TEST'):S.safe(p)
            original=Path(tmp)/'original';original.write_text('{}');link=Path(tmp)/'link';link.symlink_to(original)
            with self.assertRaisesRegex(ValueError,'unsafe'):S.safe(link)
    def test_bundle_binds_all_roles_plans_and_sources(self):
        config=json.loads((PREPARATION/'CONFIG.json').read_text())
        entries={}
        for name,m in config['members'].items():
            entries[name]={'arm':m['arm'],'report':m['report'],'execution':m['execution'],'model':{'base_path':m['checkpoint']}}
            if 'seed' in m:entries[name].update(seed=m['seed'],plan=m['plan']['path'])
        bundle={'branch':'firstK1','entries':entries,'files':config['immutable_files']}
        for key in ('source_applicability','schedule','role_validator','resource_validator','selection_report_source'):bundle[key]=config[key]
        S.bind_bundle(config,bundle)
        for key,value in [('report','/wrong/selection_report.json'),('execution','/wrong/execution.json'),('seed',3),('plan','/wrong/plan.json')]:
            changed=copy.deepcopy(bundle);changed['entries']['primary_s2'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):S.bind_bundle(config,changed)
        changed=copy.deepcopy(bundle);changed['entries']['k0_base']['model']['base_path']='instruct'
        with self.assertRaisesRegex(ValueError,'checkpoint'):S.bind_bundle(config,changed)
    def test_missing_adjudication_never_invokes_qualifier(self):
        config={'bundle_path':'/missing/bundle.json','adjudication_path':'/missing/adjudication.json'}
        with patch.object(S,'module') as mod,self.assertRaises(FileNotFoundError):
            S.consume(config,'a'*64,'b'*64,'/output.json')
        mod.assert_not_called()
    def test_supplied_wrong_authority_pin_rejected_before_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle=Path(tmp)/'bundle.json';bundle.write_text('{}')
            adjudication=Path(tmp)/'adjudication.json';adjudication.write_text('{}')
            config={'bundle_path':str(bundle),'adjudication_path':str(adjudication)}
            with patch.object(S,'module') as mod,self.assertRaisesRegex(ValueError,'pin changed'):
                S.consume(config,S.digest(bundle.read_bytes()),'b'*64,str(Path(tmp)/'output.json'))
            mod.assert_not_called()


if __name__=='__main__':unittest.main()
