#!/usr/bin/env python3
"""Independent stdlib audit of native Kev reference artifacts; never imports the driver.

This verifies content/provenance and clean accuracy, Brier, ECE10 and NLL, not every
upstream diagnostic or whether an attacker controlling all files forged the run.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def object_digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def close(a, b, context, tolerance=1e-10):
    require(isinstance(a, (int, float)) and not isinstance(a, bool) and math.isfinite(a),
            context + ': nonnumeric/nonfinite value')
    require(abs(a - b) <= tolerance, context + f': {a} != {b}')


def option_keys(question):
    typ = question['type']
    require(typ in ('choice', 'noul', 'score'), 'Unsupported question type')
    if typ == 'choice':
        return list(question['criteria'])
    if typ == 'noul':
        return ['false', 'true']
    return [str(i) for i in range(len(question['criteria']))]


def softmax(logits):
    require(bool(logits) and all(math.isfinite(z) for z in logits), 'Invalid logits')
    vals = [math.exp(z - max(logits)) for z in logits]
    total = math.fsum(vals)
    return [v / total for v in vals]


def build_rows(record, prediction, temperature):
    questions = record['questions']
    require(set(prediction['probabilities']) == set(questions) == set(prediction['logits']),
            'Prediction question coverage mismatch')
    close(prediction['inference_temperature'], temperature, 'prediction temperature')
    meta = record['_meta']
    rows = []
    for qid, q in questions.items():
        keys = option_keys(q)
        require(bool(keys), 'Empty candidate set')
        probs = prediction['probabilities'][qid]
        logits = prediction['logits'][qid]
        require(set(probs) == set(keys) == set(logits), 'Prediction candidate coverage mismatch')
        p, z = [probs[k] for k in keys], [logits[k] for k in keys]
        require(all(isinstance(v, (int, float)) and not isinstance(v, bool) and
                    math.isfinite(v) and 0 <= v <= 1 for v in p), 'Invalid probabilities')
        total = math.fsum(p)
        require(abs(total - 1) <= 1e-5, 'Probability sum mismatch')
        expected = softmax(z)
        for a, b in zip(p, expected):
            close(a, b, 'Probability/logit mismatch', 1e-5)
        y = keys.index(q['label']) if q['type'] == 'choice' else int(q['label'])
        require(0 <= y < len(keys), 'Invalid label')
        rows.append({'id': meta['id'], 'question': qid, 'keys': keys, 'label': y,
                     'source': meta['source'], 'variant': meta['variant'], 'type': q['type'],
                     'task': q['src'], 'p': [v / total for v in p], 'logits': z,
                     'inference_temperature': temperature})
    return rows


def metrics(rows, raw_temperature=None):
    require(bool(rows), 'Empty metric population')
    correct, conf, brier, nll = [], [], [], []
    for row in rows:
        z = row['logits']
        p = row['p']
        if raw_temperature is not None:
            z = [v * raw_temperature for v in z]
            p = softmax(z)
        y = row['label']
        correct.append(int(max(range(len(p)), key=p.__getitem__) == y))
        conf.append(max(p))
        brier.append(math.fsum((v - int(i == y)) ** 2 for i, v in enumerate(p)))
        high = max(z)
        nll.append(math.log(math.fsum(math.exp(v - high) for v in z)) + high - z[y])
    n = len(rows)
    ece = 0.
    # numpy.linspace boundaries used upstream: i * 0.1, with the final edge exactly 1.
    edges = [i * 0.1 for i in range(10)] + [1.]
    for lo, hi in zip(edges[:-1], edges[1:]):
        indices = [i for i, c in enumerate(conf) if c >= lo and (c < hi or hi == 1 and c <= hi)]
        if indices:
            ece += abs(math.fsum(correct[i] - conf[i] for i in indices)) / n
    return {'n': n, 'acc': sum(correct) / n, 'brier': math.fsum(brier) / n,
            'ece': ece, 'nll': math.fsum(nll) / n}


def compare_metrics(observed, expected, context):
    require(type(observed['n']) is int and observed['n'] == expected['n'], context + ': denominator mismatch')
    for key in ('acc', 'brier', 'ece', 'nll'):
        close(observed[key], expected[key], context + '.' + key)


def audit(config_path, partial=False):
    config = read(config_path)
    stamp = object_digest(config)
    root = Path(config['out'])
    require(bool(config['files']) and bool(config['suites']), 'Empty frozen inputs or suites')
    for path, expected in config['files'].items():
        require(digest(path) == expected, 'Frozen file hash mismatch: ' + path)
    require(read(root / 'CONFIG_RECEIPT.json') == {'stamp': stamp}, 'Config receipt mismatch')
    environment = read(root / 'ENVIRONMENT.json')
    require(environment['runtime'] == config['runtime'], 'Runtime version mismatch')
    temperature = environment['temperature']
    require(type(temperature) in (int, float) and math.isfinite(temperature) and temperature > 0,
            'Invalid environment temperature')
    terminal_path = root / 'REFERENCE_COMPLETE.json'
    terminal = read(terminal_path) if terminal_path.exists() else None
    if not partial:
        require(terminal is not None, 'Terminal marker missing')
        require(type(terminal.get('rc')) is int and terminal['rc'] == 0, 'Terminal not successful')
        require(terminal['stamp'] == stamp, 'Terminal config mismatch')
        require(set(terminal['suites']) == {s['name'] for s in config['suites']}, 'Terminal suite coverage mismatch')
        aggregate = read(root / 'report.json')
        require(aggregate['stamp'] == stamp and aggregate['run_of_record'] is True and
                aggregate['suite_reports'] == terminal['suites'], 'Aggregate receipt mismatch')
    result = {'status': 'PARTIAL_NOT_ACCEPTED' if partial else 'VERIFIED_SCOPED',
              'stamp': stamp, 'frozen_files_verified': len(config['files']), 'suites': {},
              'scope': 'Native/raw clean accuracy, Brier, ECE10, NLL and artifact identities; other diagnostics not independently verified.'}
    for suite in config['suites']:
        source = Path(suite['path'])
        require(str(source / 'test.jsonl') in config['files'] and str(source / 'manifest.json') in config['files'],
                'Suite inputs not frozen')
        manifest = read(source / 'manifest.json')
        require(digest(source / 'test.jsonl') == manifest['files']['test.jsonl']['sha256'], 'Official split hash mismatch')
        records = [json.loads(line) for line in (source / 'test.jsonl').read_text().splitlines() if line.strip()]
        ids = [r['_meta']['id'] for r in records]
        require(len(ids) == len(set(ids)) == suite['records'] > 0, 'Test IDs/count mismatch')
        require(len(records) == manifest['files']['test.jsonl']['records'], 'Manifest record count mismatch')
        require(sum(len(r['questions']) for r in records) == suite['questions'] == manifest['files']['test.jsonl']['questions'],
                'Question count mismatch')
        directory = root / suite['name']
        expected_path = directory / 'EXPECTED.json'
        expected = {'stamp': stamp, 'ids': ids, 'input_hashes': [object_digest(r) for r in records]}
        if expected_path.exists():
            require(read(expected_path) == expected, 'Expected record inventory mismatch')
        elif not partial:
            raise ValueError('Expected record inventory missing')
        paths = sorted((directory / 'records').glob('*.json'))
        allowed = {f'{i:06d}.json' for i in range(len(records))}
        require(all(p.name in allowed for p in paths), 'Unexpected record file')
        if not partial:
            require(len(paths) == len(records), 'Missing persisted records')
        rows = []
        for path in paths:
            i = int(path.stem)
            record = records[i]
            obj = read(path)
            payload = obj['payload']
            require(object_digest(payload) == obj['sha256'], 'Record payload hash mismatch')
            require(payload['stamp'] == stamp and payload['input_sha256'] == object_digest(record), 'Record provenance mismatch')
            rows.extend(build_rows(record, payload['prediction'], temperature))
        entry = {'records_verified': len(paths), 'records_expected': len(records), 'questions_verified': len(rows)}
        if partial:
            result['suites'][suite['name']] = entry
            continue
        bindings = terminal['suites'][suite['name']]
        require(digest(directory / 'report.json') == bindings['report_sha256'], 'Report hash mismatch')
        require(digest(directory / 'rows.json') == bindings['rows_sha256'], 'Rows hash mismatch')
        saved_rows = read(directory / 'rows.json')
        require(len(saved_rows) == len(rows) == suite['questions'], 'Saved question coverage mismatch')
        pairs = [(r['id'], r['question']) for r in saved_rows]
        require(len(set(pairs)) == len(pairs), 'Duplicate saved question rows')
        for row, saved in zip(rows, saved_rows):
            for key in ('id', 'question', 'keys', 'label', 'source', 'variant', 'type', 'task'):
                require(saved[key] == row[key], 'Saved row metadata mismatch: ' + key)
            for key in ('p', 'logits'):
                require(len(saved[key]) == len(row[key]), 'Saved row shape mismatch')
                for a, b in zip(saved[key], row[key]):
                    close(a, b, 'Saved row ' + key)
            close(saved['inference_temperature'], temperature, 'Saved row temperature')
        report = read(directory / 'report.json')
        require(report['stamp'] == stamp and report['split'] == 'test' and report['reference_model'] == config['checkpoint'],
                'Report identity mismatch')
        require(report['records'] == len(records) and report['questions'] == len(rows), 'Report coverage mismatch')
        close(report['native_serving_temperature'], temperature, 'Report temperature')
        clean = [r for r in rows if r['variant'] == 'clean' and r['source'] != 'unknowable']
        require(len(clean) == suite['clean_questions'], 'Clean headline denominator mismatch')
        native, raw = metrics(clean), metrics(clean, temperature)
        compare_metrics(report['native']['clean'], native, suite['name'] + '.native')
        compare_metrics(report['raw_temperature_one']['clean'], raw, suite['name'] + '.raw')
        entry.update(native=native, raw_temperature_one=raw)
        result['suites'][suite['name']] = entry
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--partial', action='store_true', help='Audit only available records; never grants acceptance')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.config, args.partial)
        rc = 0 if not args.partial else 3
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result, rc = {'status': 'REJECTED', 'reason': str(exc)}, 1
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.out:
        args.out.write_text(text)
    print(text, end='')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
