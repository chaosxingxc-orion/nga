"""Disposable CPU-only checks for the experimental capture storage primitive."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import torch


class CaptureStorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        src = Path(__file__).with_name('capture_storage.py')
        shutil.copyfile(src, self.root / 'capture_storage.py')
        spec = importlib.util.spec_from_file_location('disposable_capture_storage', self.root / 'capture_storage.py')
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.expected = [{'name': 'preclip.a', 'shape': [2]}, {'name': 'postclip.a', 'shape': [2]}]

    def tearDown(self):
        self.tmp.cleanup()

    def attempt(self, name='one'):
        a = self.m.CPUAttempt(self.root, name, self.expected, 10000)
        a.tensor('preclip.a', torch.tensor([3., 4.]))
        a.tensor('postclip.a', torch.tensor([.6, .8]))
        a.finish()
        return a.directory

    def test_failure_latched_and_durable(self):
        a = self.m.CPUAttempt(self.root, 'latched', self.expected, 10000)
        with self.assertRaises(ValueError): a.tensor('preclip.a', torch.tensor([float('nan'), 1.]))
        self.assertTrue((a.directory / 'FAILED.json').exists())
        with self.assertRaises(ValueError): a.tensor('preclip.a', torch.ones(2))
        with self.assertRaises(ValueError): a.finish()
        self.assertFalse((a.directory / 'COMPLETE.json').exists())

    def test_reader_bound_corrupt_and_valid_shards(self):
        import tracemalloc
        expected = [{'name':'x', 'shape':[self.m.MAX_SHARD // 4]}]
        a = self.m.CPUAttempt(self.root, 'big', expected, self.m.MAX_SHARD + 10000)
        a.tensor('x', torch.ones(expected[0]['shape'])); a.finish()
        tracemalloc.start()
        try:
            self.m.validate(a.directory, expected)
            self.assertLessEqual(tracemalloc.get_traced_memory()[1], self.m.MAX_SHARD)
        finally: tracemalloc.stop()
        with (a.directory / '000000-000000.bin').open('ab') as f: f.truncate(12 * 1024 * 1024)
        tracemalloc.start()
        try:
            with self.assertRaises(ValueError): self.m.validate(a.directory, expected)
            self.assertLessEqual(tracemalloc.get_traced_memory()[1], self.m.MAX_SHARD)
        finally: tracemalloc.stop()

    def test_roundtrip_full_coordinates(self):
        p = self.attempt()
        obj = self.m.validate(p, self.expected)
        values = torch.frombuffer(bytearray((p / obj['records'][0]['shards'][0]['file']).read_bytes()), dtype=torch.float32)
        self.assertTrue(torch.equal(values, torch.tensor([3., 4.])))
        self.assertFalse(torch.equal(values, torch.tensor([4., 3.])))

    def test_corruption_extra_missing_and_partial(self):
        for mutation in ('corrupt', 'extra', 'missing', 'partial'):
            p = self.attempt(mutation)
            if mutation == 'corrupt': (p / '000000-000000.bin').write_bytes(b'abcdefgh')
            if mutation == 'extra': (p / 'extra').write_bytes(b'x')
            if mutation == 'missing': (p / '000001-000000.bin').unlink()
            if mutation == 'partial': (p / '.other.partial').write_bytes(b'x')
            with self.assertRaises(ValueError, msg=mutation): self.m.validate(p, self.expected)

    def test_none_nonfinite_order_quota_and_incomplete(self):
        for name, value in [('none', None), ('nan', torch.tensor([float('nan'), 0.])), ('dtype', torch.tensor([1., 2.], dtype=torch.float64))]:
            a = self.m.CPUAttempt(self.root, name, self.expected, 10000)
            with self.assertRaises(ValueError): a.tensor('preclip.a', value)
        a = self.m.CPUAttempt(self.root, 'order', self.expected, 10000)
        with self.assertRaises(ValueError): a.tensor('postclip.a', torch.ones(2))
        with self.assertRaises(ValueError): a.finish()
        a = self.m.CPUAttempt(self.root, 'quota', self.expected, 1)
        with self.assertRaises(ValueError): a.tensor('preclip.a', torch.ones(2))
        with self.assertRaises(ValueError): self.m.validate(a.directory, self.expected)

    def test_retry_does_not_replace_last_trace(self):
        p = self.attempt()
        before = (p / 'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError): self.m.CPUAttempt(self.root, 'one', self.expected, 10000)
        a = self.m.CPUAttempt(self.root, 'retry', self.expected, 10000)
        with self.assertRaises(ValueError): a.finish()
        self.assertEqual(before, (p / 'manifest.json').read_bytes())
        self.m.validate(p, self.expected)

    def test_reordered_expected_and_terminal(self):
        p = self.attempt()
        with self.assertRaises(ValueError): self.m.validate(p, list(reversed(self.expected)))
        (p / 'COMPLETE.json').write_text(json.dumps({'manifest_sha256': '0' * 64}))
        with self.assertRaises(ValueError): self.m.validate(p, self.expected)


if __name__ == '__main__':
    unittest.main()
