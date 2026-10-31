import importlib.util
import json
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

    def rebuild(self, track=None):
        with patch.object(E, 'rebuild_track_t', return_value=track or {'cells': {'selection': {}}, 'question70': {}}) as t:
            result = R.rebuild(self.run, self.kev, self.root, (C, E, D, PC, self.v))
            t.assert_called_once_with(str(self.run), 'r3', data_root=str(self.root), selection_only=True)
            return result

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
