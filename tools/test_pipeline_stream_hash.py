"""Large artifacts must not be allocated in full merely to verify their identity."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import unified_cpu_pipeline_v1 as pipeline


class StreamHash(unittest.TestCase):
    def test_empty_and_multiple_chunks_without_full_file_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'artifact'
            for payload in (b'', b'abc', bytes(range(256)) * 12345):
                path.write_bytes(payload)
                with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('whole file read')):
                    self.assertEqual(pipeline.sha(path), hashlib.sha256(payload).hexdigest())
            path.write_bytes(b'changed')
            self.assertNotEqual(pipeline.sha(path), hashlib.sha256(payload).hexdigest())

    def test_missing_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing'
            with self.assertRaises(FileNotFoundError):
                pipeline.sha(path)
            path.write_bytes(b'data')
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                pipeline.sha(link)


if __name__ == '__main__':
    unittest.main()
