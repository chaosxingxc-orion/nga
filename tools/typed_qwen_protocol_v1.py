"""Typed Decisions single-question Qwen full-label adapter and native metrics.

This names a new inference protocol, not the publisher's five-question endpoint.
Downloaded scorer code is hash checked and only score_one's AST is executed.
"""
import ast
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROTOCOL = 'typed-qwen-single-question-full-label-v1'
SCORER_SHA = '6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def ordered_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def map_rows(rows):
    """Return native-compatible hard items and CPU-only rich gold, in source order."""
    items, gold = [], []
    seen = set()
    for row_index, row in enumerate(rows):
        case_id = row['id']
        require(type(case_id) is str and case_id and case_id not in seen, 'duplicate/invalid case')
        seen.add(case_id)
        require(row['split'] == 'test', 'only public TEST admitted')
        require(type(row['state']) is str and isinstance(ordered_json(row['state']), dict), 'state JSON object required')
        questions, answers = ordered_json(row['questions']), ordered_json(row['gold'])
        require(type(questions) is dict and len(questions) == 5 and list(questions) == list(answers), 'question population/order differs')
        for qid, question in questions.items():
            require(type(qid) is str and qid and set(question) <= {'type', 'instructions', 'criteria'}, 'question fields differ')
            kind, instruction = question['type'], question['instructions']
            require(type(instruction) is str and instruction, 'instruction required')
            criteria = question.get('criteria')
            if kind == 'choice':
                require(type(criteria) is dict and 2 <= len(criteria) <= 26, 'choice criteria differ')
                keys = list(criteria)
                require(all(type(k) is str and k and type(v) is str for k, v in criteria.items()), 'choice definitions required')
                options = [k + ': ' + criteria[k] for k in keys]
                native_kind = 'choice'
            elif kind == 'noul':
                # The first workflow publishes no definitions (criteria=null); retain
                # the publisher's bare Yes/No readout in that case. Other workflows
                # publish explicit true/false definitions and those remain in prompt
                # text. Never invent definitions from the gold distribution.
                require(criteria is None or (type(criteria) is dict and set(criteria) == {'false', 'true'} and all(type(v) is str for v in criteria.values())), 'noul definitions differ')
                # Native yes/no options are fixed. Retain both expert definitions in input.
                if criteria is not None:
                    instruction += '\nCandidate definitions (true = Yes; false = No):\n' + json.dumps(criteria, ensure_ascii=False, separators=(',', ':'))
                keys, options, native_kind = ['true', 'false'], ['Yes', 'No'], 'yes_no'
            else:
                require(kind == 'score' and type(criteria) is list and 2 <= len(criteria) <= 10 and all(type(v) is str for v in criteria), 'ordinal criteria differ')
                keys = [str(i) for i in range(len(criteria))]
                options = [key + ': ' + value for key, value in zip(keys, criteria)]
                native_kind = 'score'
            answer = answers[qid]
            require(answer['type'] == kind and type(answer['probabilities']) is dict, 'gold type differs')
            probs = answer['probabilities']
            require(set(probs) == set(keys) and all(type(v) in (float, int) and math.isfinite(v) and v >= 0 for v in probs.values()), 'invalid gold distribution')
            require(abs(sum(probs.values()) - 1) <= 1e-5, 'gold mass differs')
            gold_keys = list(probs)
            # Native ties select first gold-key order, not inference option order.
            winner = gold_keys[max(range(len(gold_keys)), key=lambda i: probs[gold_keys[i]])]
            identity = json.dumps([case_id, qid], ensure_ascii=False, separators=(',', ':'))
            item = dict(i=len(items), qid=identity, state=row['state'], question=instruction,
                        options=options, kind=native_kind, y=keys.index(winner))
            items.append(item)
            gold.append(dict(i=item['i'], qid=identity, case_id=case_id, source_row=row_index,
                             source_qid=qid, workflow=row['workflow'], candidate_keys=keys,
                             gold=answer, request_sha256=digest({k: v for k, v in item.items() if k != 'y'})))
    require(bool(items), 'empty population')
    return items, gold


def load_native_score(path):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SCORER_SHA, 'native scorer identity differs')
    nodes = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'score_one']
    require(len(nodes) == 1, 'native scorer function missing')
    namespace = {'math': math}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['score_one']


def prediction_distribution(meta, prediction, contract_sha256):
    require(prediction.get('schema') == 'bev-native-prediction-v1' and prediction.get('mode') == 'transformers_full_labels', 'readout mode differs')
    require(prediction.get('i') == meta['i'] and type(prediction.get('i')) is int and prediction.get('qid') == meta['qid'], 'readout identity differs')
    require(prediction.get('request_sha256') == meta['request_sha256'] and prediction.get('contract_sha256') == contract_sha256, 'readout binding differs')
    require(prediction.get('route') == 'one_forward' and prediction.get('reasoning_tokens') == 0, 'unexpected reasoning route')
    logs = prediction.get('restricted_logprobs')
    require(type(logs) is list and len(logs) == len(meta['candidate_keys']) and all(type(v) in (int, float) and math.isfinite(v) and v <= 1e-12 for v in logs), 'invalid restricted log probabilities')
    probs = [math.exp(v) for v in logs]
    require(abs(sum(probs) - 1) <= 1e-5, 'predicted mass differs')
    index = max(range(len(logs)), key=lambda i: logs[i])
    require(type(prediction.get('first_index')) is int and prediction['first_index'] == index and prediction.get('index') == index, 'readout argmax differs')
    return {'probabilities': dict(zip(meta['candidate_keys'], probs))}


def aggregate(cells):
    n = len(cells)
    require(n > 0, 'empty score population')
    hits, counts, confidence = [0] * 10, [0] * 10, [0.0] * 10
    for ok, kl, brier, conf in cells:
        require(all(math.isfinite(v) for v in (kl, brier, conf)) and 0 <= conf <= 1, 'invalid metric')
        b = min(int(conf * 10), 9)
        counts[b] += 1
        hits[b] += int(ok)
        confidence[b] += conf
    ece = sum(counts[b] / n * abs(hits[b] / counts[b] - confidence[b] / counts[b]) for b in range(10) if counts[b])
    return dict(n=n, accuracy=sum(x[0] for x in cells) / n,
                kl_from_gold=sum(x[1] for x in cells) / n,
                brier=sum(x[2] for x in cells) / n, ece10=ece)


def score(gold, predictions, *, scorer, contract_sha256, workers=4, chunk_size=64):
    """Strict all-population score. Missing/invalid readouts never acquire a score."""
    require(type(workers) is int and 1 <= workers <= 64 and type(chunk_size) is int and chunk_size > 0, 'invalid CPU configuration')
    require(len(gold) == len(predictions) and len(gold) > 0, 'incomplete prediction population')
    require(len({m['qid'] for m in gold}) == len(gold), 'duplicate gold identity')
    native = load_native_score(scorer)
    def one(i):
        require(gold[i]['i'] == i, 'gold ordinal differs')
        return native(prediction_distribution(gold[i], predictions[i], contract_sha256), gold[i]['gold'])
    cells = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(gold), chunk_size):
            cells.extend(pool.map(one, range(start, min(start + chunk_size, len(gold)))))
    overall = aggregate(cells)
    return dict(protocol=PROTOCOL, native_metric_formula_sha256=SCORER_SHA,
                inference_equivalent_to_published_endpoint=False, scientific_acceptance=False,
                strict=dict(expected=len(gold), returned=len(predictions), valid=len(gold), invalid=0, **overall),
                original_arithmetic_raw_readout=overall,
                by_type={k: aggregate([c for m, c in zip(gold, cells) if m['gold']['type'] == k]) for k in sorted({m['gold']['type'] for m in gold})},
                by_workflow={k: aggregate([c for m, c in zip(gold, cells) if m['workflow'] == k]) for k in sorted({m['workflow'] for m in gold})})
