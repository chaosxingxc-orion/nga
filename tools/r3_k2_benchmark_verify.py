"""Recompute K2 benchmark arithmetic from bounded result metadata.

This verifies arithmetic only. Gradients, reference-repeat tensors, actual chip
use and training-data population are not independently recoverable from RESULT.
The question denominator is the frozen protocol's 10 questions per step, not
stats.rows (which counts augmented examples).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

LIMIT = 262144
ARMS = ('reference', 'candidate')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, name, minimum=None):
    require(type(value) in (int, float), name + ': expected number')
    require(math.isfinite(value), name + ': nonfinite')
    if minimum is not None:
        require(value >= minimum, name + ': below minimum')
    return value


def equal_number(actual, expected, name):
    number(actual, name)
    require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), name + ': summary differs')


def verify(report, plan_sha256):
    require(isinstance(report, dict), 'invalid report')
    require(isinstance(plan_sha256, str) and len(plan_sha256) == 64
            and all(c in '0123456789abcdef' for c in plan_sha256), 'invalid expected plan hash')
    require(report.get('schema') == 'r3-k2-sync-benchmark-result-v1', 'schema differs')
    require(report.get('plan_sha256') == plan_sha256, 'plan differs')
    require(report.get('scientific_acceptance') is False and report.get('test_read') is False, 'scope differs')
    require(type(report.get('chips')) is int and report['chips'] == 1, 'chip count differs')
    require(report.get('exact_loss_and_gradients') is True, 'equivalence not reported')
    rows = report.get('rows')
    require(isinstance(rows, list) and len(rows) == 13, 'expected thirteen pairs')
    for step, row in enumerate(rows):
        require(isinstance(row, dict), 'invalid pair')
        require(type(row.get('step')) is int and row['step'] == step, 'step population differs')
        order = list(ARMS if step % 2 == 0 else reversed(ARMS))
        require(row.get('order') == order or row.get('order') == tuple(order), 'arm order differs')
        require(row.get('exact') is True, 'inexact pair reported')
        for arm in ARMS:
            item = row.get(arm)
            require(isinstance(item, dict), 'invalid arm')
            number(item.get('loss'), 'loss')
            require(number(item.get('seconds'), 'seconds', 0) > 0, 'nonpositive elapsed time')
            number(item.get('reserved_gib'), 'reserved_gib', 0)
            stats = item.get('stats')
            require(isinstance(stats, dict), 'invalid statistics')
            for key in ('tokens', 'rows', 'resp_tokens'):
                require(type(stats.get(key)) is int and stats[key] >= 0, 'invalid stats.' + key)
            require(stats['tokens'] > 0 and stats['rows'] > 0, 'empty measured population')
        require(row['reference']['loss'] == row['candidate']['loss'], 'paired loss differs')
        require(row['reference']['stats'] == row['candidate']['stats'], 'paired statistics differ')
    measured = rows[3:]
    seconds = {arm: sum(row[arm]['seconds'] for row in measured) for arm in ARMS}
    require(all(math.isfinite(s) and s >= 60 for s in seconds.values()), 'measured window too short or nonfinite')
    require(isinstance(report.get('seconds'), dict), 'missing seconds summary')
    require(isinstance(report.get('performance'), dict), 'missing performance summary')
    performance = {}
    for arm in ARMS:
        equal_number(report['seconds'].get(arm), seconds[arm], arm + '.seconds')
        performance[arm] = {
            'questions_per_second_per_chip': 100 / seconds[arm],
            'tokens_per_second_per_chip': sum(row[arm]['stats']['tokens'] for row in measured) / seconds[arm],
            'reserved_gib_peak': max(row[arm]['reserved_gib'] for row in measured),
            'chips': 1,
        }
        observed = report['performance'].get(arm)
        require(isinstance(observed, dict), 'missing arm performance')
        require(type(observed.get('chips')) is int and observed['chips'] == 1, 'performance chip count differs')
        for key, value in performance[arm].items():
            equal_number(observed.get(key), value, arm + '.' + key)
    speedup = seconds['reference'] / seconds['candidate']
    equal_number(report.get('speedup'), speedup, 'speedup')
    require(report.get('engineering_speed_candidate') is (speedup >= 1.05), 'speed threshold classification differs')
    return {'arithmetic_verified': True, 'plan_sha256': plan_sha256, 'measured_pairs': 10,
            'protocol_questions': 100, 'seconds': seconds, 'speedup': speedup,
            'performance': performance, 'engineering_speed_candidate': speedup >= 1.05,
            'gradient_equivalence_independently_verified': False,
            'scientific_acceptance': False, 'completion_verified': False,
            'scope': 'result arithmetic only; question count assumed from frozen protocol; no tensor, process or data verification'}


def verify_file(path, plan_sha256):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe result path')
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    require(len(raw) <= LIMIT, 'result size limit exceeded')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    report = json.loads(raw, object_pairs_hook=unique)
    result = verify(report, plan_sha256)
    result['result_sha256'] = hashlib.sha256(raw).hexdigest()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', required=True)
    parser.add_argument('--plan-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_file(args.result, args.plan_sha256), indent=2, allow_nan=False))
