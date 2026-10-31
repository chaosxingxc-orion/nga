import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('track_t_prepare', Path(__file__).with_name('r3_track_t_prepare.py'))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class TrackTPrepare(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'data'
        self.base.mkdir()
        self.manifest = {'tasks': {}}
        for task, directory in P.TASKS.items():
            self.manifest['tasks'][directory] = {}
            for source in P.SOURCES if task != 'T3' else ('typed-decisions',):
                path = self.base / directory / (source + '.jsonl')
                path.parent.mkdir(exist_ok=True)
                path.write_text('{"fixture":true}\n')
                self.manifest['tasks'][directory][source] = P.builder_identity(path)
        (self.base / 'manifest.json').write_text(json.dumps(self.manifest))
        for name in ('r3_code', 'r0_code'):
            (self.base / name).mkdir()
        (self.base / 'r3_code/eval_r3.py').write_text('import common\n')
        (self.base / 'r3_code/selection_evidence_r3.py').write_text('import common\n')
        (self.base / 'r0_code/common.py').write_text('X = 1\n')
        self.out = self.root / 'frozen'

    def test_exact_population_scored_without_report_stage_or_test_mount(self):
        summary = P.prepare(self.out, self.base)
        self.assertEqual((summary['task_files'], summary['data_files']), (7, 8))
        d = json.loads((self.out / 'manifest.json').read_text())
        command = d['command_template']
        self.assertEqual(command[command.index('--stages') + 1], 't_score')
        self.assertEqual(command[command.index('--track-t-config') + 1], 'r3')
        self.assertNotIn('report', command)
        self.assertFalse(any('/KEV/' in x or '/test' in x for x in d['data']))
        self.assertTrue(d['split_policy']['report_half_raw_readouts_scored'])
        self.assertFalse(d['split_policy']['report_half_metrics_computed'])
        self.assertIn('report_half=False', d['split_policy']['selection_consumer'])
        self.assertFalse(summary['ready_to_score'])

    def test_changed_normative_task_refused_before_creating_output(self):
        (self.base / 'T1_level_names/typed-decisions.jsonl').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'normative manifest'):
            P.prepare(self.out, self.base)
        self.assertFalse(self.out.exists())

    def test_wrong_record_count_refused_despite_matching_content_hash(self):
        self.manifest['tasks']['T1_level_names']['typed-decisions']['records'] += 1
        (self.base / 'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'normative manifest'):
            P.prepare(self.out, self.base)

    def test_missing_task_cannot_silently_reduce_population(self):
        (self.base / 'T2_definition_swap/akhilaaa3.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'missing regular'):
            P.prepare(self.out, self.base)

    def test_symlink_source_refused_and_frozen_generation_not_overwritten(self):
        src = self.base / 'r0_code/common.py'
        other = self.root / 'other.py'
        src.rename(other)
        src.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            P.prepare(self.out, self.base)
        src.unlink()
        other.rename(src)
        P.prepare(self.out, self.base)
        before = (self.out / 'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError):
            P.prepare(self.out, self.base)
        self.assertEqual((self.out / 'manifest.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
