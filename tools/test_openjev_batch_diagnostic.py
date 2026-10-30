"""E37 protocol tests: metadata selection, no-op exactness and passive hooks."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('diagnostic', Path(__file__).with_name('openjev_batch_diagnostic.py'))
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)


def entry(index, width, length, status='eligible'):
    return dict(index=index, id=str(index), status=status,
                lengths=[length] * width, max_tokens=length)


def prediction():
    return dict(answer={'type': 'choice', 'choice': 'a', 'probabilities': {'a': .5, 'b': .5}, 'confidence': 0.},
                native_probabilities={'a': .5, 'b': .5}, logits=[0., 0.],
                logits_temperature='unscaled', consumed_token_sha256=['a', 'b'])


class FakeTensor:
    def __init__(self, values):
        self.values = values; self.shape = (len(values), len(values[0])); self.dtype = 'int64'; self.device = 'cpu'
    def detach(self): return self
    def cpu(self): return self
    def tolist(self): return self.values


class Handle:
    def __init__(self): self.removed = False
    def remove(self): self.removed = True


class FakeModule:
    def __init__(self): self.pre = []; self.post = []; self.handles = []
    def register_forward_pre_hook(self, hook, with_kwargs):
        self.pre.append(hook); h = Handle(); self.handles.append(h); return h
    def register_forward_hook(self, hook, with_kwargs):
        self.post.append(hook); h = Handle(); self.handles.append(h); return h


class FakeDecoderLayer(FakeModule):
    pass


class Tests(unittest.TestCase):
    def test_selection_metadata_only_reordering_and_labels_irrelevant(self):
        rows = [entry(9027, 30, 4096), entry(15, 10, 300), entry(12, 15, 186),
                entry(20, 24, 3500), entry(633, 255, 2156)]
        result = d.select({'items': rows})
        self.assertEqual([x['index'] for x in result['selected']], [9027, 12, 20])
        self.assertEqual(result['strata'][1]['selected_index'], None)
        changed = copy.deepcopy(rows)
        for e in changed: e.update(label='arbitrary', correctness=True)
        self.assertEqual(d.select({'items': list(reversed(changed))}), result)

    def test_max_batch_excluded_and_no_missing_stratum_substitution(self):
        result = d.select({'items': [entry(9027, 30, 4096), entry(633, 255, 2156), entry(1, 16, 500, 'overlength')]})
        self.assertEqual(len(result['selected']), 1)
        self.assertEqual([x['count'] for x in result['strata']], [0, 0, 1])
        self.assertEqual(result['strata'][2]['selected_index'], 9027)

    def test_original_boundary_change_rejected(self):
        with self.assertRaisesRegex(ValueError, 'boundary metadata'):
            d.select({'items': [entry(9000, 30, 4096)]})

    def test_noop_exactness_does_not_hide_small_change(self):
        a = prediction(); b = copy.deepcopy(a); b['logits'][0] = 1e-12
        c = d.comparison(a, b)
        self.assertFalse(c['exact_prediction']); self.assertFalse(c['decision_changed'])
        self.assertEqual(c['logits_max_delta'], 1e-12)

    def test_negative_zero_not_bit_exact(self):
        a = prediction(); b = copy.deepcopy(a); b['logits'][0] = -0.
        self.assertFalse(d.comparison(a, b)['exact_prediction'])

    def test_candidate_order_and_legend_rejected(self):
        a = prediction(); b = copy.deepcopy(a)
        b['native_probabilities'] = {'b': .5, 'a': .5}
        with self.assertRaisesRegex(ValueError, 'order'): d.comparison(a, b)

    def test_score_uses_returned_score_not_argmax(self):
        a = prediction(); a['answer'] = dict(type='score', score=.5, probabilities={'0': .5, '1': .5}, confidence=0., legend={'0': 'low', '1': 'high'})
        b = copy.deepcopy(a); b['answer']['score'] = .5001
        self.assertTrue(d.comparison(a, b)['decision_changed'])

    def test_receipt_mode_and_profile_identity_enforced(self):
        value = dict(plan_sha256='p', mode='original', profiled=False)
        env = dict(payload=value, sha256=d.stamp(value))
        self.assertEqual(d.verify_receipt(env, value), value)
        with self.assertRaisesRegex(ValueError, 'identity'):
            d.verify_receipt(env, dict(value, profiled=True))
        value['mode'] = 'chunk8'
        with self.assertRaisesRegex(ValueError, 'hash'): d.verify_receipt(env, {})

    def test_passive_hooks_record_shapes_order_and_clean_up_on_failure(self):
        backbone = FakeModule(); layer = FakeDecoderLayer()
        backbone.named_modules = lambda: [('layer0', layer)]
        npu = SimpleNamespace(synchronize=lambda: None, reset_peak_memory_stats=lambda: None,
            memory_allocated=lambda: 10, max_memory_allocated=lambda: 20, max_memory_reserved=lambda: 30)
        trace = dict(layers=[], backbone_inputs=[], backbone_outputs=[])
        ids = FakeTensor([[1, 2], [3, 0]]); mask = FakeTensor([[1, 1], [1, 0]])
        kwargs = dict(input_ids=ids, attention_mask=mask)
        original = copy.deepcopy(ids.values)
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            with d.profile(backbone, SimpleNamespace(npu=npu), trace):
                for hook in backbone.pre: self.assertIsNone(hook(backbone, (), kwargs))
                for hook in layer.pre: self.assertIsNone(hook(layer, (ids,), {}))
                for hook in layer.post: self.assertIsNone(hook(layer, (ids,), {}, (ids,)))
                result = SimpleNamespace(last_hidden_state=ids)
                for hook in backbone.post: self.assertIsNone(hook(backbone, (), kwargs, result))
                raise RuntimeError('injected')
        self.assertEqual(ids.values, original)
        self.assertEqual(trace['backbone_inputs'][0]['ordered_id_row_hashes'], [d.stamp(x) for x in original])
        self.assertEqual(trace['layers'][0]['peak_allocated'], 20)
        self.assertEqual(trace['backbone_outputs'][0]['last_hidden_state']['dtype'], 'int64')
        self.assertTrue(all(h.removed for h in backbone.handles + layer.handles))

    def test_empty_layer_profile_refused(self):
        b = FakeModule(); b.named_modules = lambda: []
        with self.assertRaisesRegex(ValueError, 'No decoder layers'):
            with d.profile(b, None, {}): pass


if __name__ == '__main__': unittest.main()
