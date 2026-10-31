"""Synthetic metric contracts, never model-performance evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/r3_sft/r3_code'))
import select_r3 as S
import selection_evidence_r3 as E
spec = importlib.util.spec_from_file_location('development_compare', ROOT / 'tools/r3_development_compare.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)


def report(seed=None, impl='rows'):
    keys = [[s, str(i)] for s, n in [('decision-v7',1264),('transfer-v4',656)] for i in range(n)]
    correct = [int(i % 5 != 0) for i in range(1920)]
    arm = 'K0' if seed is None else 'K1'
    model = {'kind':'checkpoint' if seed is None else 'lora-adapter-unmerged',
             'path':'/base' if seed is None else f'/adapter{seed}', 'base_path':'/base','base_revision':'revision'}
    evidence = {'keys':keys,'correct':correct,'arm':arm}
    if seed is not None:
        evidence.update(seed=seed,adapter_path=model['path'],training_variant={'schema':1,'args':{'k2_impl':impl}})
    return {'header':{'arm':arm,'model':model,'partitions':['dev','calibration'],'track_t_config':'r3',
                      'data_files':{'/dev':'same'},'prompt_version':'v1','prompt_format':'fixed',
                      'render':'record_name','primary_input_mode':'full','dtype':'float32','readings':{}}, 'selection_evidence':evidence,
            'track_k':{'partitions':{s+'/dev':{'headline':{'kev_rule_accuracy':.8},
                'arms':{k:{'kev_rule_accuracy':.5} for k in ['constant','question_only']}}
                for s in ['decision-v7','transfer-v4']}},
            'track_t':{'cells':{'selection':{}},'selection':{}},
            'schema':'r3-selection-report-v1','scientific_acceptance':False}


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.a=[report(2),report(3)];self.b=report()

    def test_identical_scores_give_zero_paired_delta_no_adoption(self):
        result=D.compare(self.a,self.b,E,S)
        self.assertEqual(result['against_k0']['combined'],S.paired_bootstrap(
            self.a[0]['selection_evidence']['correct'],self.b['selection_evidence']['correct']))
        self.assertEqual(result['against_k0']['combined']['ci_lower'],0.)
        self.assertFalse(result['scientific_acceptance'])
        self.assertNotIn('a_replaces_b',result)
        self.assertTrue(result['blockers'])

    def test_mixed_recipes_duplicate_seeds_and_foreign_base_rejected(self):
        for change in ['recipe','seed','base','revision','data','keys','report_half','prompt','reading']:
            with self.subTest(change=change):
                a=copy.deepcopy(self.a)
                if change=='recipe':a[1]['selection_evidence']['training_variant']['args']['k2_impl']='shared'
                if change=='seed':a[1]['selection_evidence']['seed']=2
                if change=='base':a[1]['header']['model']['base_path']='/other'
                if change=='revision':a[1]['header']['model']['base_revision']='other'
                if change=='data':a[1]['header']['data_files']['/dev']='other'
                if change=='keys':a[1]['selection_evidence']['keys'][0][1]='different'
                if change=='report_half':a[1]['track_t']['cells']['report']={'accuracy':.9}
                if change=='prompt':a[1]['header']['prompt_version']='other'
                if change=='reading':a[1]['header']['readings']={'denominator':'other'}
                with self.assertRaises(ValueError):D.compare(a,self.b,E,S)

    def test_incumbent_missing_r0_returns_blocker_not_winner(self):
        result=D.compare(self.a,self.b,E,S,incumbent=copy.deepcopy(self.a))
        self.assertEqual(result['condition_c']['status'],'blocked')
        self.assertNotIn('a_replaces_b',result)
        self.assertFalse(result['test_read'])

    def test_k0_never_fabricates_seed(self):
        self.b['selection_evidence']['seed']=2
        with self.assertRaisesRegex(ValueError,'impersonate'):D.compare(self.a,self.b,E,S)

    def test_saved_metric_tampering_and_changed_source_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'selection_report.json';original=report();p.write_text(json.dumps(original))
            tool=Mock();tool.load.side_effect=lambda path:json.loads(Path(path).read_text())
            tool.rebuild.return_value=original
            self.assertEqual(D.verified_report(p,tool,(),'kev','data'),original)
            changed=copy.deepcopy(original);changed['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy']=1.
            p.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'verified readouts'):D.verified_report(p,tool,(),'kev','data')
            p.write_text(json.dumps(original));tool.rebuild.side_effect=ValueError('provenance changed')
            with self.assertRaisesRegex(ValueError,'provenance changed'):D.verified_report(p,tool,(),'kev','data')


if __name__=='__main__':unittest.main()
