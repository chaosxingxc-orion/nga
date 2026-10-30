import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('probe', Path(__file__).with_name('nimble_reference_probe.py'))
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def test_probability_validity(self):
        probe.validate_output([1., 2.], [.25, .75], 2)
        for logits, probs in [([1.], [.25, .75]), ([float('nan'), 2], [.25, .75]),
                              ([1., 2.], [.2, .7]), ([1., 2.], [-.1, 1.1])]:
            with self.assertRaises(ValueError): probe.validate_output(logits, probs, 2)

    def test_alias_is_rejected(self):
        config = {'adapter': '/mnt/cephfs/xingchao/omni/models/jev/bespokelabs__Bespoke-Nimble-9B'}
        with self.assertRaisesRegex(ValueError, 'v1 schema'):
            probe.validate_contract_identity(config)

    def test_restored_initial_identity(self):
        config = {'adapter': '/mnt/cephfs/xingchao/experiments/jev/reference_inference/nimble_initial_inventory_20261030/adapter',
                  'base': '/mnt/cephfs/xingchao/omni/models/jev/Qwen__Qwen3.5-9B',
                  'base_revision': 'c202236235762e1c871ad0ccb60c8ee5ba337b9a'}
        self.assertEqual(probe.validate_contract_identity(config)['max_length'], 2048)


if __name__ == '__main__': unittest.main()
