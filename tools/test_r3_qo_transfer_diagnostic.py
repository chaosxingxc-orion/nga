"""Synthetic diagnostic checks; no measured model-performance evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from test_r3_development_compare import report,E
import r3_qo_transfer_diagnostic as Q


class Diagnostic(unittest.TestCase):
    def setUp(self):
        self.candidates=[report(2),report(3)];self.qo=report(2)
        self.qo['header']['arm']='K1-QO';self.qo['header']['primary_input_mode']='drop'
        self.qo['selection_evidence']['arm']='K1-QO'
        self.qo['selection_evidence']['adapter_path']='/qo-adapter'
        self.qo['header']['model']['path']='/qo-adapter'
        for r in self.candidates+[self.qo]:
            r['header']['model']['base_path']='/models/Qwen__Qwen3.5-0.8B-Base'
            r['selection_evidence']['correct']=[0]*1920
        self.candidates[0]['selection_evidence']['correct'][1264:1264+32]=[1]*32
        self.candidates[1]['selection_evidence']['correct'][1264:1264+33]=[1]*33

    def test_discrete_five_point_boundary_and_no_pooled_pass(self):
        result=Q.compare(self.candidates,self.qo,E)
        self.assertEqual([x['meets_registered_five_pp_margin'] for x in result['per_seed']],[False,True])
        self.assertAlmostEqual(result['per_seed'][0]['difference_pp'],100*32/656)
        self.assertEqual(result['per_seed'][0]['interpretation'],'not a semantic-transfer claim')
        self.assertEqual(result['n'],656);self.assertFalse(result['test_read'])
        self.assertFalse(result['adoption_authorized']);self.assertFalse(result['scientific_acceptance'])
        self.assertNotIn('arm_pass',result)

    def test_protocol_population_seed_and_control_mismatch_refused(self):
        for mutation in ('seed','mode','base','revision','keys','report_half','arm','bool_correct','alias','prompt'):
            candidates=copy.deepcopy(self.candidates);qo=copy.deepcopy(self.qo)
            if mutation=='seed':qo['selection_evidence']['seed']=3
            if mutation=='mode':qo['header']['primary_input_mode']='full'
            if mutation=='base':candidates[0]['header']['model']['base_path']='/other'
            if mutation=='revision':candidates[0]['header']['model']['base_revision']='other'
            if mutation=='keys':qo['selection_evidence']['keys'][1264][1]='other'
            if mutation=='report_half':qo['track_t']['cells']['report']={'accuracy':1}
            if mutation=='arm':qo['header']['arm']='K1'
            if mutation=='bool_correct':qo['selection_evidence']['correct'][0]=True
            if mutation=='alias':qo['selection_evidence']['adapter_path']=candidates[0]['selection_evidence']['adapter_path']
            if mutation=='prompt':qo['header']['prompt_version']='other'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):Q.compare(candidates,qo,E)

    def test_rebuild_required_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'selection_report.json';path.write_text(json.dumps(self.qo));r=Mock();r.rebuild.return_value=self.qo
            actual,pin=Q.rebuilt(path,r,(),'kev','data');self.assertEqual(actual,self.qo)
            changed=copy.deepcopy(self.qo);changed['selection_evidence']['correct'][0]=1;path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'verified readouts'):Q.rebuilt(path,r,(),'kev','data')
            r.rebuild.side_effect=ValueError('producer invalid')
            with self.assertRaisesRegex(ValueError,'producer invalid'):Q.rebuilt(path,r,(),'kev','data')

    def test_test_paths_refused_before_read(self):
        with self.assertRaisesRegex(ValueError,'test path'):Q.safe('/tmp/test/selection_report.json')

    def test_redirected_closure_refused_before_module_execution(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'A';b=root/'B';a.mkdir();b.mkdir()
            (b/'r3_code').mkdir();(a/'r3_code').symlink_to(b/'r3_code',target_is_directory=True)
            (a/'manifest.json').write_text('{}');pin=hashlib.sha256(b'{}').hexdigest();loader=Mock()
            with self.assertRaisesRegex(ValueError,'unsafe path'):Q.closure_modules(a,pin,loader)
            loader.modules.assert_not_called()
            (a/'r3_code').unlink();(a/'r3_code').mkdir();(a/'r0_code').mkdir()
            Q.closure_modules(a,pin,loader);loader.modules.assert_called_once_with(a/'r3_code')


if __name__=='__main__':unittest.main()
