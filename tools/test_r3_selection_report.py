import importlib.util
import json
import copy
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch
import unittest

s = importlib.util.spec_from_file_location('selection_report', Path(__file__).with_name('r3_selection_report.py'))
R = importlib.util.module_from_spec(s); s.loader.exec_module(R)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/r3_sft/r3_code'))
from test_selection_evidence_r3 import Evidence, write, task
import core_r3 as C
import selection_evidence_r3 as E
import degenerate_r3 as D
import prechecks_r3 as PC
import provenance_r3 as PV
import testlock_r3 as TL


class ReportTests(Evidence):
    # Reuse real stamped readouts, weights, population and producer manifest.
    # Track T numerical aggregation and variant arithmetic have dedicated tests;
    # here enforce the consumer call and acceptance/write boundary.
    def setUp(self):
        super().setUp()
        self.v = Mock()
        self.v.fit_operator.return_value.summary.return_value = {}
        self.v.permutation_metrics.return_value = {'fixture': True}
        self.v.nota_metrics.return_value = {'fixture': True}
        self.v.operator_column.return_value = {'fixture': True}
        manifest = json.loads((self.kev / 'manifest.json').read_text())
        cal = [task(i) for i in range(10)]
        path = Path(C.partition_path('decision-v7', 'calibration', kev_dir=str(self.kev)))
        C.write_jsonl(str(path), cal)
        manifest['suites']['decision-v7']['partitions']['calibration'] = {'outputs': {'clean': {
            'path': str(path.relative_to(self.kev)), 'sha256': C.sha256_file(str(path))}}}
        for kind in ('clean', 'question_only', 'empty_input'):
            readouts = [PV.stamp(C.readout_row(r, [1., 0.]), self.identity['sha256']) for r in cal]
            f = C.k_readout_path(str(self.run), 'decision-v7', 'calibration', kind)
            C.write_jsonl(f, readouts); self.paths.append(f)
        for suite in C.SUITES:
            rows = self.tasks[(suite, 'dev')]
            path = Path(C.partition_path(suite, 'dev', variants=True, kev_dir=str(self.kev)))
            C.write_jsonl(str(path), rows)
            manifest['suites'][suite]['partitions']['dev']['outputs']['variants'] = {
                'path': str(path.relative_to(self.kev)), 'sha256': C.sha256_file(str(path))}
            f = C.k_readout_path(str(self.run), suite, 'dev', 'variants')
            C.write_jsonl(f, [PV.stamp(C.readout_row(r, [1., 0.]), self.identity['sha256']) for r in rows])
            self.paths.append(f)
        write(self.kev / 'manifest.json', manifest)
        self.manifest()
        self.receipt = {'schema': 'r3-scoring-receipt-v1', **self.report}
        self.receipt['header'].update(stages='k_score,t_score', partitions=['dev', 'calibration'],
            data_files={str(p): C.sha256_file(str(p)) for p in self.kev.glob('*/*.jsonl')})
        for directory, sources in [('T1_level_names', ('typed-decisions', 'openjev-synth', 'akhilaaa3')),
                                   ('T2_definition_swap', ('typed-decisions', 'openjev-synth', 'akhilaaa3')),
                                   ('T3_question_set', ('typed-decisions',))]:
            for source in sources:
                path = self.root / directory / (source + '.jsonl')
                path.parent.mkdir(exist_ok=True); path.write_text('{"fixture":true}\n')
                self.receipt['header']['data_files'][str(path)] = C.sha256_file(str(path))
        self.save_receipt()
        write(self.run / 'EVAL_COMPLETE.track_kt.json', {'exit_code': 0})

    def save_receipt(self):
        write(self.run / 'SCORING_RECEIPT.track_kt.json', self.receipt)

    def rebuild(self, track=None, role_binding=None):
        with patch.object(E, 'rebuild_track_t', return_value=track or {'cells': {'selection': {}}, 'question70': {}}) as t:
            result = R.rebuild(self.run, self.kev, self.root, (C, E, D, PC, self.v), role_binding)
            t.assert_called_once_with(str(self.run), 'r3', data_root=str(self.root), selection_only=True)
            return result

    def formal_binding_fixture(self):
        schedule=self.root/'schedule.json';write(schedule,{'fixture':True})
        role={'role':'primary_s2','seed':2,'schedule_sha256':R.sha(schedule),'candidate_for_adoption':True}
        helper=self.root/'trusted-role-helper.py'
        helper.write_text('def validate_plan(p):\n    return '+repr(role)+'\n')
        # Fixture helper isolates consumer trust binding; real validator has its own tests.
        plan=self.train/'plan.json';write(plan,{'formal_role':'primary_s2','formal_schedule':str(schedule),'formal_schedule_sha256':R.sha(schedule)})
        binding={'schema':'r3-selection-role-binding-v1','training_plan':str(plan),'training_plan_sha256':R.sha(plan),'schedule':str(schedule),'schedule_sha256':R.sha(schedule),'helper':str(helper),'helper_sha256':R.sha(helper)}
        ev=self.run.parent/'plan.json';write(ev,{'training':str(self.train),'adapter':str(self.adapter),'command':['runner','--out',str(self.run)],'training_variant':{'seed':2,'training_plan_sha256':R.sha(plan),'formal_role_identity':role},'formal_role_binding':binding,'files':{str(plan):R.sha(plan),str(self.train/'manifest.json'):R.sha(self.train/'manifest.json'),str(helper):R.sha(helper)}})
        return dict(binding,evaluation_plan=str(ev),evaluation_plan_sha256=R.sha(ev))

    def test_external_role_binding_rebuilds_and_missing_plan_fails_closed(self):
        binding=self.formal_binding_fixture();result=self.rebuild(role_binding=binding)
        self.assertEqual(result['selection_evidence']['formal_role_identity']['role'],'primary_s2')
        (self.train/'plan.json').unlink()
        with self.assertRaises((ValueError,FileNotFoundError)):self.rebuild(role_binding=binding)
        with self.assertRaisesRegex(ValueError,'external role binding'):self.rebuild()

    def test_unbound_adjacent_plan_and_self_pinned_helper_cannot_execute(self):
        marker=self.root/'ATTACK_EXECUTED';helper=self.root/'attacker.py'
        helper.write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\ndef validate_plan(p): return {}\n')
        write(self.train/'plan.json',{'formal_role':'diffchip_s2','launcher':str(self.root/'launcher.py'),'files':{str(helper):R.sha(helper)}})
        with self.assertRaisesRegex(ValueError,'external role binding'):self.rebuild()
        self.assertFalse(marker.exists())
        # Legacy path never imports this helper, even after hostile adjacent data disappears.
        (self.train/'plan.json').unlink();result=self.rebuild()
        self.assertNotIn('formal_role_identity',result['selection_evidence'])
        self.assertFalse(marker.exists())

    def test_external_role_binding_rejects_mutated_helper_and_producer(self):
        binding=self.formal_binding_fixture()
        for field in ('evaluation_plan_sha256','training_plan_sha256','helper_sha256','schedule_sha256'):
            changed=copy.deepcopy(binding);changed[field]='0'*64
            with self.subTest(field=field),self.assertRaises(ValueError):self.rebuild(role_binding=changed)
        helper=Path(binding['helper']);helper.write_text(helper.read_text()+'#changed')
        with self.assertRaisesRegex(ValueError,'helper changed'):self.rebuild(role_binding=binding)

    def test_rehashed_wrong_producer_association_refused(self):
        binding=self.formal_binding_fixture();ev=Path(binding['evaluation_plan']);d=R.load(ev)
        d['adapter']=str(self.root/'other-adapter');write(ev,d);binding['evaluation_plan_sha256']=R.sha(ev)
        with self.assertRaisesRegex(ValueError,'association differs'):self.rebuild(role_binding=binding)

    def test_real_provenance_and_population_rebuilt_without_writing_full_report(self):
        previous = (self.run / 'report.json').read_bytes()
        result = self.rebuild()
        self.assertEqual(result['track_k']['partitions']['decision-v7/dev']['headline']['n'], 1264)
        self.assertEqual(result['track_k']['partitions']['decision-v7/dev']['headline']['kev_rule_accuracy'], 1.)
        self.assertFalse(result['scientific_acceptance'])
        self.assertEqual((self.run / 'report.json').read_bytes(), previous)
        self.assertFalse((self.run / 'selection_report.json').exists())
        self.assertFalse(list(self.kev.glob('**/test*')))

    def test_k0_requires_real_checkpoint_provenance_without_training_identity(self):
        self.identity = TL.model_identity(str(self.base), None, str(self.root / 'k0cache'))
        self.receipt['header'].update(arm='K0', model=self.identity)
        self.save_receipt()
        write(self.run / 'RUN_IDENTITY.json', {'model_sha256': self.identity['sha256'], 'arm': 'K0', 'track_t_config': 'r3'})
        for path in self.paths:
            rows = C.read_jsonl(path)
            C.write_jsonl(path, [PV.stamp(r, self.identity['sha256']) for r in rows])
        self.manifest()
        with patch.object(E, 'train_identity', side_effect=AssertionError('K0 has no trainer')):
            result = self.rebuild()
        self.assertEqual(result['selection_evidence']['arm'], 'K0')
        self.assertNotIn('seed', result['selection_evidence'])

    def control_fixture(self, arm):
        target=self.root/('Qwen__Qwen3.5-0.8B-Base' if arm=='K1-QO' else 'Qwen__Qwen3.5-0.8B')
        self.base.rename(target);self.base=target
        self.training['model_path']=str(target);self.training['args']['drop_state']=arm=='K1-QO'
        write(self.train/'manifest.json',self.training)
        self.identity=TL.model_identity(str(target),str(self.adapter),str(self.root/'controlcache'))
        self.receipt['header'].update(arm=arm,model=self.identity,primary_input_mode='drop' if arm=='K1-QO' else 'full')
        self.save_receipt()
        write(self.run/'RUN_IDENTITY.json',{'model_sha256':self.identity['sha256'],'arm':arm,'track_t_config':'r3'})
        for path in self.paths:
            C.write_jsonl(path,[PV.stamp(r,self.identity['sha256']) for r in C.read_jsonl(path)])
        self.manifest()

    def test_qo_is_drop_control_and_not_adoption_candidate(self):
        self.control_fixture('K1-QO');result=self.rebuild()
        self.assertFalse(result['control']['adoption_candidate'])
        self.assertEqual(result['selection_evidence']['seed'],2)
        self.receipt['header']['primary_input_mode']='full';self.save_receipt()
        with self.assertRaisesRegex(ValueError,'primary input mode'):self.rebuild()

    def test_pt_requires_instruct_base_and_preserves_control_limit(self):
        self.control_fixture('K1-PT');result=self.rebuild()
        self.assertIn('separate R0-configuration',result['control']['scope'])
        self.assertFalse(result['control']['adoption_candidate'])
        self.training['args']['drop_state']=True;write(self.train/'manifest.json',self.training)
        with self.assertRaisesRegex(ValueError,'question-only'):self.rebuild()

    def test_incomplete_scoring_or_test_partition_refused_before_metrics(self):
        for key, value in [('stages', 'k_score'), ('partitions', ['dev', 'test'])]:
            original = self.receipt['header'][key]
            self.receipt['header'][key] = value; self.save_receipt()
            with self.assertRaises(ValueError): self.rebuild()
            self.receipt['header'][key] = original
        self.v.fit_operator.assert_not_called()

    def test_unstamped_and_foreign_population_are_not_accepted(self):
        self.change_rows(lambda rows: rows[0].pop('m'))
        with self.assertRaises(PV.ProvenanceRefusal): self.rebuild()

    def test_report_half_consumer_leak_rejected(self):
        with self.assertRaisesRegex(ValueError, 'report-half'):
            self.rebuild({'cells': {}, 'question70': {'report': {'leaked': .5}}})

    def test_changed_producer_data_hash_refused(self):
        self.receipt['header']['data_files'][str(self.kev / 'decision-v7/dev.jsonl')] = 'changed'
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, 'producer data hash'): self.rebuild()


if __name__ == '__main__':
    suite = unittest.TestSuite()
    # Run only this module's added cases, not the inherited base suite again.
    for name in ReportTests.__dict__:
        if name.startswith('test_'): suite.addTest(ReportTests(name))
    result = unittest.TextTestRunner().run(suite)
    raise SystemExit(not result.wasSuccessful())
