import importlib.util
from pathlib import Path
import struct
import unittest
from dataclasses import replace
import sys

spec = importlib.util.spec_from_file_location('qhost_contract', Path(__file__).with_name('qhost_transport_contract.py'))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.meta = m.Metadata((2, 4), (4, 1))
        # Signed zero, infinities, quiet/signalling NaN payloads, subnormal.
        self.raw = struct.pack('<8I', 0, 0x80000000, 0x7f800000, 0xff800000,
                               0x7fc12345, 0x7f812345, 1, 0x3f800000)

    def restore(self, data, metadata):
        return bytearray(data), metadata

    def test_bit_patterns_and_metadata_exact(self):
        stage = m.HostStage(self.meta, self.raw)
        self.assertEqual(stage.restore(self.restore), (self.raw, self.meta))
        self.assertIsNone(stage._host)
        self.assertEqual(stage.state, 'restored')

    def test_owned_copy_survives_source_mutation_and_deletion(self):
        source = bytearray(self.raw)
        stage = m.HostStage(self.meta, source, lambda x: x)
        source[:] = b'\xff' * len(source)
        del source
        self.assertEqual(stage.restore(self.restore)[0], self.raw)

    def test_rejects_unsupported_metadata(self):
        for change in ({'stride': (1, 2)}, {'storage_offset': 1},
                       {'external_aliases': 1}, {'dtype': 'bfloat16'},
                       {'device_format': 'FRACTAL_NZ'}, {'byteorder': 'big'},
                       {'shape': (0, 4)}, {'device': 'cpu'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.HostStage(replace(self.meta, **change), self.raw)

    def test_rejects_partial_storage_and_views(self):
        for data in (self.raw[:-1], memoryview(self.raw)):
            with self.assertRaises(ValueError):
                m.HostStage(self.meta, data)

    def test_copy_failure_and_corruption(self):
        def fail(_):
            raise RuntimeError('D2H failed')
        for callback, error in ((fail, RuntimeError), (lambda _: b'\0' * 32, ValueError)):
            stage = m.HostStage.__new__(m.HostStage)
            with self.assertRaises(error):
                stage.__init__(self.meta, self.raw, callback)
            self.assertIsNone(stage._host)
            self.assertEqual(stage.state, 'failed')

    def test_restore_failure_cleans_host_and_forbids_retry(self):
        stage = m.HostStage(self.meta, self.raw)
        def fail(*_):
            raise RuntimeError('H2D failed')
        with self.assertRaises(RuntimeError):
            stage.restore(fail)
        self.assertIsNone(stage._host)
        self.assertEqual(stage.state, 'failed')
        with self.assertRaises(ValueError):
            stage.restore(self.restore)

    def test_restore_rejects_metadata_and_byte_changes(self):
        for callback in (lambda b, md: (b, replace(md, device='npu:1')),
                         lambda b, md: (b'\0' * len(b), md)):
            stage = m.HostStage(self.meta, self.raw)
            with self.assertRaises(ValueError):
                stage.restore(callback)
            self.assertIsNone(stage._host)
            self.assertEqual(stage.state, 'failed')

    def test_closed_stage_cannot_be_used(self):
        stage = m.HostStage(self.meta, self.raw)
        stage.close()
        stage.close()
        with self.assertRaises(ValueError):
            stage.restore(self.restore)


if __name__ == '__main__':
    unittest.main()
