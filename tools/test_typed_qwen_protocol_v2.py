import copy
import json
import math
import unittest
from tools import typed_qwen_protocol_v2 as P

SCORER = '/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/bench/score_with_jobs.py'


def fixture():
    qs = {'c': dict(type='choice', instructions='Select', criteria={'z': 'last name', 'a': 'first name'}),
          'n': dict(type='noul', instructions='Approve?', criteria={'false': 'Reject it', 'true': 'Approve it'}),
          's': dict(type='score', instructions='Rate', criteria=['low', 'medium', 'high'])}
    qs['d'] = copy.deepcopy(qs['c']); qs['e'] = copy.deepcopy(qs['n'])
    gs = {k: dict(type=q['type'], probabilities=({'a': .5, 'z': .5} if q['type'] == 'choice' else {'false': .4, 'true': .6} if q['type'] == 'noul' else {'0': .2, '1': .7, '2': .1})) for k, q in qs.items()}
    return dict(id='case', split='test', workflow='synthetic', state='{"observation":"hello"}', questions=json.dumps(qs), gold=json.dumps(gs))


def predictions(gold):
    result = []
    for m in gold:
        probs = list(range(1, len(m['candidate_keys']) + 1)); total = sum(probs)
        result.append(dict(schema='bev-native-prediction-v1', mode='transformers_full_labels',
                           i=m['i'], qid=m['qid'], request_sha256=m['request_sha256'], contract_sha256='a' * 64,
                           route='one_forward', reasoning_tokens=0,
                           restricted_logprobs=[math.log(v / total) for v in probs],
                           first_index=len(probs) - 1, index=len(probs) - 1))
    return result


class TypedProtocol(unittest.TestCase):
    def test_mapping_preserves_names_definitions_order_and_gold_tie(self):
        items, gold = P.map_rows([fixture()])
        self.assertEqual(items[0]['options'], ['z: last name', 'a: first name'])
        self.assertEqual(items[0]['y'], 1)
        self.assertEqual(gold[1]['candidate_keys'], ['true', 'false'])
        self.assertEqual(items[1]['options'], ['Yes', 'No'])
        self.assertIn('Reject it', items[1]['question'])
        self.assertEqual(items[2]['options'], ['0: low', '1: medium', '2: high'])

    def test_bad_population_and_gold_rejected(self):
        row = fixture()
        for mutation in ('split', 'probabilities', 'questions'):
            r = copy.deepcopy(row)
            if mutation == 'split': r['split'] = 'train'
            elif mutation == 'probabilities':
                g = json.loads(r['gold']); g['c']['probabilities']['z'] = -1; r['gold'] = json.dumps(g)
            else: r['questions'] = r['questions'].replace('"c":', '"n":', 1)
            with self.assertRaises(ValueError): P.map_rows([r])
        with self.assertRaises(ValueError): P.map_rows([row, row])

    def test_published_null_noul_criteria_preserved(self):
        row = fixture(); qs = json.loads(row['questions']); qs['n']['criteria'] = None
        row['questions'] = json.dumps(qs)
        items, _ = P.map_rows([row])
        self.assertEqual(items[1]['question'], 'Approve?')
        self.assertEqual(items[1]['options'], ['Yes', 'No'])

    def test_parallel_exact_native_formula(self):
        _, gold = P.map_rows([fixture()]); pred = predictions(gold)
        one = P.score(gold, pred, scorer=SCORER, contract_sha256='a'*64, workers=1)
        four = P.score(gold, pred, scorer=SCORER, contract_sha256='a'*64, workers=4, chunk_size=2)
        self.assertEqual(one, four)
        native = P.load_native_score(SCORER)
        cells = [native(P.prediction_distribution(m, p, 'a'*64), m['gold']) for m, p in zip(gold, pred)]
        self.assertEqual(one['original_arithmetic_raw_readout'], P.aggregate(cells))
        self.assertFalse(one['inference_equivalent_to_published_endpoint'])

    def test_missing_invalid_foreign_never_uniform_success(self):
        _, gold = P.map_rows([fixture()]); pred = predictions(gold)
        with self.assertRaises(ValueError): P.score(gold, pred[:-1], scorer=SCORER, contract_sha256='a'*64)
        for key, value in [('contract_sha256', 'b'*64), ('i', True), ('restricted_logprobs', [-math.inf, 0]), ('first_index', 0)]:
            x = copy.deepcopy(pred); x[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): P.score(gold, x, scorer=SCORER, contract_sha256='a'*64)

    def test_native_fallback_is_separate_and_yes_no_maps(self):
        native = P.load_native_score(SCORER)
        gold = {'type': 'noul', 'probabilities': {'false': .4, 'true': .6}}
        self.assertEqual(native({'probabilities': {'yes': .8, 'no': .2}}, gold), native({'probabilities': {'true': .8, 'false': .2}}, gold))
        self.assertEqual(native({'probabilities': {}}, gold)[3], .5)


class NativeReductionOrder(unittest.TestCase):
    def test_published_incremental_ece(self):
        # Vary bin occupancy and nonbinary confidence values; derive the oracle
        # independently in item order, then reduce occupied bins incrementally.
        cells = [(i % 3 == 0, 0.1, 0.2, ((i * 37) % 997) / 997) for i in range(2000)]
        bins = [[] for _ in range(10)]
        for cell in cells: bins[min(int(cell[3] * 10), 9)].append(cell)
        expected = 0.0
        for group in bins:
            hits, total_confidence = 0, 0.0
            for correct, _, _, confidence in group:
                hits += int(correct)
                total_confidence += confidence
            if group:
                expected += len(group) / len(cells) * abs(hits / len(group) - total_confidence / len(group))
        self.assertEqual(P.aggregate(cells)['ece10'], expected)

if __name__ == '__main__': unittest.main()
