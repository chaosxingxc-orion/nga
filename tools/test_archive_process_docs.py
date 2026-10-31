import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('archive_docs', Path(__file__).with_name('archive_process_docs.py'))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


class Archive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)

    def file(self, name, text='evidence', old=True):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        if old:
            os.utime(p, (time.time()-4*86400,)*2)
        return p

    def test_missing_directories_and_dry_run(self):
        self.assertFalse(A.archive(self.root)['moved'])
        p = self.file('experiments/history.md')
        self.assertEqual(len(A.archive(self.root, dry_run=True)['moved']), 1)
        self.assertTrue(p.exists())

    def test_protect_current_tracked_and_executable_inputs(self):
        for name in ['.local/reports/STATUS-LATEST.md', 'wiki/CURRENT-CONCLUSIONS.md',
                     'experiments/plan.json', 'experiments/R3-PREREG.md', 'experiments/run.py']:
            self.file(name)
        self.file('experiments/tracked.md')
        subprocess.run(['git', '-C', str(self.root), 'add', 'experiments/tracked.md'], check=True)
        self.assertFalse(A.archive(self.root)['moved'])

    def test_only_old_eligible_reports_move(self):
        old = self.file('.local/reports/training-status-20261020.json')
        self.file('.local/reports/training-status-new.json', old=False)
        self.file('.local/reports/cpu-deployment.json')
        result = A.archive(self.root, date='2026-10-31')
        self.assertEqual(len(result['moved']), 1)
        self.assertFalse(old.exists())
        self.assertEqual((self.root / result['moved'][0]['target']).read_text(), 'evidence')

    def test_collision_preserves_both(self):
        old = self.file('experiments/history.md', 'original')
        target = self.file('.local/archive/2026-10-31/experiments/history.md', 'prior')
        result = A.archive(self.root, date='2026-10-31')
        self.assertEqual(len(result['collisions']), 1)
        self.assertEqual(old.read_text(), 'original')
        self.assertEqual(target.read_text(), 'prior')

    def test_symlink_source_and_destination(self):
        source = self.file('outside.md')
        (self.root/'wiki').mkdir()
        (self.root/'wiki/history.md').symlink_to(source)
        self.assertFalse(A.archive(self.root)['moved'])
        self.file('experiments/history.md')
        (self.root/'.local/archive').symlink_to(self.root/'wiki', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            A.archive(self.root)

    def test_invalid_retention_or_date(self):
        for days in (0, -1, float('nan')):
            with self.assertRaises(ValueError): A.archive(self.root, days=days)
        with self.assertRaises(ValueError): A.archive(self.root, date='../escape')


if __name__ == '__main__': unittest.main()
