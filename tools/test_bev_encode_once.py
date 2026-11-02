"""Synthetic CPU regressions for BEV encoding reuse; no dataset or model reads."""
from collections import namedtuple
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


R = module(HERE / 'bev_public_test_runner.py', 'encode_once_runner')
B = module(HERE / 'bev_public_test_bridge.py', 'encode_once_bridge')
P = module(HERE.parent / 'experiments/r0_baseline/prompt.py', 'encode_once_prompt')
Enc = namedtuple('Enc', 'prefix cands')
PLAN = {'scoring': {'mode': 'rightpad', 'max_sequence_tokens': 4096}}


def row(identifier, text='context', kind='choice', n=2):
    keys = ['true', 'false'] if kind == 'noul' else [str(i) for i in range(n)]
    definitions = ['True', 'False'] if kind == 'noul' else ['level ' + str(i) for i in range(n)]
    return {'id': identifier, 'request': dict(
        input=text, question='Choose one', type=kind,
        level_type={'choice': 'nominal', 'noul': 'boolean', 'score': 'ordinal'}[kind],
        candidate_set='exclusive', candidate_keys=keys, definitions=definitions)}


class CountingTokenizer:
    pad_token_id = 0

    def __init__(self, overrides=None):
        self.calls = []
        self.overrides = overrides or {}

    def __call__(self, text, *, add_special_tokens):
        if add_special_tokens is not False:
            raise AssertionError('special tokens changed')
        self.calls.append(text)
        return {'input_ids': list(self.overrides.get(text, [ord(c) for c in text]))}


class Scorer:
    """Frozen encode/score_raw contract with deterministic, input-sensitive CPU scores."""
    def __init__(self, tok=None):
        self.tok = tok or CountingTokenizer()
        self.encoded = []
        self.scored = []

    def encode(self, rows):
        out = []
        for parsed in rows:
            rendered = P.build_prompt(parsed, 'record_name')
            prefix = self.tok(rendered.text, add_special_tokens=False)['input_ids']
            labels = [self.tok(c, add_special_tokens=False)['input_ids'] for c in rendered.candidates]
            if any(len(c) == 0 for c in labels):
                raise ValueError('a level identifier tokenized to nothing')
            out.append(Enc(prefix, labels))
        self.encoded.extend(out)
        return out

    def score_raw(self, rows, mode):
        return self.score_enc(self.encode(rows), mode)

    def score_enc(self, enc, mode):
        self.scored.append((list(enc), mode))
        return [[float(sum(e.prefix) % 17) * (j + 1) - sum(c) / 100.
                 for j, c in enumerate(e.cands)] for e in enc]


def baseline(batch, scorer):
    """Previous two-encoding path retained only as a synthetic regression oracle."""
    eligible, results = [], {}
    for r in batch:
        parsed = B.to_r3_row(r['request'])
        rendered = P.build_prompt(parsed, render='record_name', input_mode='full')
        prefix = scorer.tok(rendered.text, add_special_tokens=False)['input_ids']
        labels = [scorer.tok(c, add_special_tokens=False)['input_ids'] for c in rendered.candidates]
        R.require(prefix and all(labels), 'empty tokenizer sequence')
        R.require(len({tuple(c) for c in labels}) == len(labels), 'duplicate tokenized candidates')
        length = max(len(prefix) + len(c) for c in labels)
        if length > 4096:
            results[r['id']] = (r, None, dict(id=r['id'], status='unsupported_length', sequence_tokens=length))
        else:
            eligible.append((r, parsed))
    if eligible:
        raw = scorer.score_raw([parsed for _, parsed in eligible], mode='rightpad')
        for (r, _), scores in zip(eligible, raw):
            results[r['id']] = (r, list(scores), B.from_raw(r['id'], scores, len(r['request']['candidate_keys'])))
    return [results[r['id']] for r in batch]


class EncodeOnceTests(unittest.TestCase):
    def score(self, rows, scorer):
        return R.score_batch(rows, scorer, P, B, PLAN)

    def test_exact_tokens_objects_order_and_output_with_half_the_tokenizer_calls(self):
        rows = [row('choice'), row('bool', 'other input', 'noul'), row('score', 'third input', 'score', 3)]
        before, after = Scorer(), Scorer()
        expected = baseline(rows, before)
        with mock.patch.object(after, 'score_raw', side_effect=AssertionError('encoded twice')):
            actual = self.score(rows, after)
        self.assertEqual(actual, expected)
        self.assertEqual(len(before.tok.calls), 20)
        self.assertEqual(len(after.tok.calls), 10)
        self.assertEqual(after.tok.calls, before.tok.calls[:10])
        enc, mode = after.scored[0]
        self.assertEqual(mode, 'rightpad')
        self.assertEqual(enc, before.scored[0][0])
        for encoded, scored in zip(after.encoded, enc):
            self.assertIs(encoded, scored)
        self.assertEqual(enc[-1].cands, [[32, 76, 49], [32, 76, 50], [32, 76, 51]])
        self.assertNotEqual(actual[0][1], actual[1][1])

    def test_mixed_length_eligibility_including_exact_boundary(self):
        rows = [row('long', 'x' * 5000), row('short'), row('edge', 'boundary'), row('long2', 'y' * 5000)]
        text = P.build_prompt(B.to_r3_row(rows[2]['request'])).text
        before = Scorer(CountingTokenizer({text: [7] * 4093}))
        after = Scorer(CountingTokenizer({text: [7] * 4093}))
        actual = self.score(rows, after)
        self.assertEqual(actual, baseline(rows, before))
        self.assertEqual([r['id'] for r, _, _ in actual], ['long', 'short', 'edge', 'long2'])
        self.assertEqual([p['status'] for _, _, p in actual], ['unsupported_length', 'ok', 'ok', 'unsupported_length'])
        self.assertEqual(after.scored[0][0], [after.encoded[1], after.encoded[2]])
        self.assertEqual(len(after.tok.calls), 12)
        self.assertEqual(len(before.tok.calls), 18)

    def test_all_unsupported_and_empty_batches_do_not_score(self):
        for rows in ([], [row('long', 'z' * 5000)]):
            scorer = Scorer()
            self.assertEqual(self.score(rows, scorer), baseline(rows, Scorer()))
            self.assertEqual(scorer.scored, [])

    def test_token_collisions_rejected_even_if_overlength(self):
        for text in ('context', 'z' * 5000):
            scorer = Scorer(CountingTokenizer({' L1': [8], ' L2': [8]}))
            with self.assertRaisesRegex(ValueError, 'duplicate tokenized candidates'):
                self.score([row('collision', text)], scorer)
            self.assertEqual(scorer.scored, [])

    def test_empty_prefix_and_candidate_rejected_before_scoring(self):
        r = row('empty')
        text = P.build_prompt(B.to_r3_row(r['request'])).text
        for empty in (text, ' L1'):
            scorer = Scorer(CountingTokenizer({empty: []}))
            with self.assertRaises(ValueError):
                self.score([r], scorer)
            self.assertEqual(scorer.scored, [])

    def test_duplicate_requests_keep_distinct_ids_and_outputs(self):
        rows = [row('first'), row('duplicate')]
        scorer = Scorer()
        actual = self.score(rows, scorer)
        self.assertEqual(actual, baseline(rows, Scorer()))
        self.assertEqual([r['id'] for r, _, _ in actual], ['first', 'duplicate'])
        self.assertEqual(actual[0][1], actual[1][1])
        self.assertEqual(len(scorer.scored[0][0]), 2)

    def test_malformed_request_aborts_entire_batch_without_scoring(self):
        broken = row('broken'); broken['request']['label'] = 'forbidden'
        scorer = Scorer()
        with self.assertRaisesRegex(ValueError, 'gold_free'):
            self.score([row('valid'), broken], scorer)
        self.assertEqual(scorer.scored, [])

    def test_scorer_population_and_nonfinite_scores_fail_closed(self):
        for result, message in (([], 'population'), ([[float('nan'), 1.]], 'nonfinite'), ([[1.]], 'malformed')):
            scorer = Scorer()
            with mock.patch.object(scorer, 'score_enc', return_value=result):
                with self.assertRaisesRegex(ValueError, message):
                    self.score([row('valid')], scorer)

    def test_exact_tie_keeps_first_candidate_rule(self):
        scorer = Scorer()
        with mock.patch.object(scorer, 'score_enc', return_value=[[2., 2.]]):
            result = self.score([row('tie')], scorer)
        self.assertEqual(result[0][2], dict(id='tie', status='ok', index=0,
                                          exact_tie=True, top2_gap_nats=0.))

    def test_resume_preserves_chunk8_missing_order_and_committed_bytes(self):
        rows = [row(str(i), 'x' * 5000 if i == 3 else 'input ' + str(i)) for i in range(14)]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            first = Scorer()
            def interrupt(n):
                if n == 3:
                    raise RuntimeError('synthetic disconnect')
            with self.assertRaisesRegex(RuntimeError, 'disconnect'):
                R.process(rows, out, 'a' * 64, B, lambda batch: self.score(batch, first), interrupt)
            committed = {R.item_path(out, r['id']): R.item_path(out, r['id']).read_bytes() for r in rows[:3]}
            resumed, batches = Scorer(), []
            def score(batch):
                batches.append([r['id'] for r in batch])
                return self.score(batch, resumed)
            values = R.process(rows, out, 'a' * 64, B, score, lambda n: None)
            self.assertEqual(batches, [[str(i) for i in range(3, 11)], ['11', '12', '13']])
            expected = baseline(rows, Scorer())
            self.assertEqual([(v['id'], v['raw'], v['prediction']) for v in values],
                             [(r['id'], raw, pred) for r, raw, pred in expected])
            self.assertEqual(len(resumed.tok.calls), 33)
            self.assertEqual([len(enc) for enc, _ in resumed.scored], [7, 3])
            for path, data in committed.items():
                self.assertEqual(path.read_bytes(), data)
            self.assertEqual(R.process(rows, out, 'a' * 64, B, lambda _: self.fail('rescored'), lambda n: None), values)

    def test_actual_frozen_encode_interface_without_loading_model(self):
        path = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code/scorer_r3.py')
        if not path.exists():
            self.skipTest('frozen scorer source is not mounted')
        self.assertEqual(R.sha(path), 'f1de708a28b47cdb513eb79c7306510df8312f6a92f96a75adcfe59ba0cf6a49')
        previous_path = list(sys.path)
        try:
            with mock.patch.dict(sys.modules, {'prompt': P}):
                frozen = module(path, 'encode_once_frozen_scorer')
        finally:
            sys.path[:] = previous_path
        rows = [row('one'), row('two', 'changed input', 'score', 3)]
        tok = CountingTokenizer()
        scorer = frozen.R3Scorer('/unused', model=object(), tokenizer=tok, render='record_name')
        expected = frozen.encode_rows(CountingTokenizer(), [B.to_r3_row(r['request']) for r in rows])
        with mock.patch.object(scorer, 'score_enc', return_value=[[1., 2.], [3., 2., 1.]]) as score:
            actual = self.score(rows, scorer)
        self.assertEqual(score.call_args.args[0], expected)
        self.assertTrue(all(type(e) is frozen.Enc for e in score.call_args.args[0]))
        reduced, maps, duplicates, removed = frozen.dedup_enc(score.call_args.args[0])
        self.assertEqual((maps, duplicates, removed), ([[0, 1], [0, 1, 2]], 0, 0))
        self.assertEqual(scorer._flat_rows(reduced), scorer._flat_rows(expected))
        self.assertEqual(score.call_args.kwargs, {'mode': 'rightpad'})
        self.assertEqual(len(tok.calls), 7)
        self.assertEqual([pred['index'] for _, _, pred in actual], [1, 0])


if __name__ == '__main__':
    unittest.main()
