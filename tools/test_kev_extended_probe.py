import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('probe', Path(__file__).with_name('kev_extended_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.row = {'questions': {'q': {}}}
        prediction = {'probabilities': {'q': {'a': .5, 'b': .5}},
                      'logits': {'q': {'a': 0., 'b': 0.}},
                      'inference_temperature': 1., 'input_tokens': 8}
        self.item = {'identity': 'run', 'input_hash': probe.objhash(self.row), 'index': 2,
                     'packed_tokens': 8, 'predictions': [prediction, copy.deepcopy(prediction)],
                     'seconds': [.1, .2]}

    def check(self, item):
        return probe.validate_saved({'payload': item, 'sha256': probe.objhash(item)}, self.row, 'run', 2, 8)

    def test_valid(self):
        self.assertEqual(self.check(self.item), self.item)

    def test_empty_passes_even_with_valid_hash(self):
        self.item['predictions'] = []
        with self.assertRaisesRegex(ValueError, 'two completed'): self.check(self.item)

    def test_invalid_timing(self):
        self.item['seconds'][0] = 0
        with self.assertRaisesRegex(ValueError, 'duration'): self.check(self.item)

    def test_wrong_tokens(self):
        self.item['predictions'][0]['input_tokens'] = 7
        with self.assertRaisesRegex(ValueError, 'token'): self.check(self.item)

    def test_corruption(self):
        saved = {'payload': self.item, 'sha256': probe.objhash(self.item)}
        self.item['seconds'][0] = 9
        with self.assertRaisesRegex(ValueError, 'checksum'):
            probe.validate_saved(saved, self.row, 'run', 2, 8)


if __name__ == '__main__': unittest.main()
