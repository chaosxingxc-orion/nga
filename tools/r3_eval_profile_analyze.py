#!/usr/bin/env python3
"""Read-only independent reconstruction of persisted DEV profile operands.

Does not import the runtime, model, or scorer. A complete operand set is not a
successful run: both terminal markers and the exact release must also exist.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

PHASES = ('cold_reference', 'split_gate', 'warmup', 'wall_0', 'wall_1', 'wall_2', 'trace')


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def typed_equal(left, right):
    """JSON comparison that cannot alias booleans, integers and floats."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def pinned(ref):
    require(sha(ref['path']) == ref['sha256'], 'pin differs: ' + ref['path'])
    return read(ref['path'])


def reconstruct(plan_path, expected_sha, attempt=1):
    require(integer(attempt, 1), 'invalid attempt type')
    require(sha(plan_path) == expected_sha, 'host plan differs')
    plan = read(plan_path)
    require(plan['test_read'] is False and plan['scientific_acceptance'] is False
            and plan['candidate_selection_allowed'] is False and type(plan['chip']) is int and plan['chip'] == 6, 'scope differs')
    for path, digest in plan['files'].items():
        require(sha(path) == digest, 'dependency differs: ' + path)
    profile = pinned(plan['profile'])
    panel_ref = profile['panel']
    require(sha(panel_ref['path']) == panel_ref['sha256'], 'panel differs')
    panel = [json.loads(line) for line in Path(panel_ref['path']).read_text().splitlines() if line]
    cells = {}
    for row in panel:
        cells.setdefault(row['cell'], []).append(row)
    require(len(cells) == 32 and len(panel) == 1024, 'panel population differs')
    root = Path(plan['out'])
    results, phases, pins = {}, {}, {str(Path(plan_path)): expected_sha}
    trials = []
    for phase in PHASES:
        receipts = []
        for cell, rows in cells.items():
            path = root / 'items' / phase / (hashlib.sha256(cell.encode()).hexdigest() + '.json')
            receipt_path = path.with_suffix('.receipt.json')
            require(path.exists() and receipt_path.exists(), 'incomplete operands: ' + phase + '/' + cell)
            operand, receipt = read(path), read(receipt_path)
            require(receipt['plan_sha256'] == expected_sha and receipt['operand_sha256'] == sha(path), 'receipt binding differs')
            require(type(receipt['attempt']) is int and receipt['attempt'] == attempt, 'mixed/resumed attempts are not timing-comparable')
            require(operand['cell'] == cell and typed_equal([x['id'] for x in operand['rows']], [x['id'] for x in rows]), 'row identity differs')
            for measured, source in zip(operand['rows'], rows):
                scores = measured['s']
                require(len(scores) == len(source['row']['levels']) and all(type(x) in (int, float) and math.isfinite(x) for x in scores), 'malformed scores')
                require(type(measured['index']) is int and type(measured['tie']) is bool
                        and measured['index'] == max(range(len(scores)), key=lambda i: scores[i])
                        and measured['tie'] == (scores.count(max(scores)) > 1), 'typed output differs from raw')
            if phase == 'cold_reference':
                results[cell] = operand
            else:
                require(typed_equal(operand, results[cell]), 'encoded/raw/typed equality differs: ' + phase + '/' + cell)
            for field in ('score_wall_seconds', 'commit_seconds'):
                require(number(receipt[field]), 'invalid timing')
            require(receipt['score_wall_seconds'] > 0, 'zero score timing')
            counters = receipt['counter_delta']
            require(isinstance(counters, dict) and integer(counters.get('tokens'), 1), 'invalid token counter')
            for key, value in counters.items():
                require(number(value) if key.endswith('_s') else integer(value), 'invalid counter: ' + key)
            require(counters.get('padded_tokens', 0) <= counters['tokens'], 'padding exceeds tokens')
            require(number(receipt.get('tokens_per_second_per_chip')) and
                    receipt['tokens_per_second_per_chip'] == counters['tokens'] / receipt['score_wall_seconds'],
                    'receipt score throughput differs')
            pins[str(path)] = sha(path)
            pins[str(receipt_path)] = sha(receipt_path)
            receipts.append(receipt)
            trials.append(dict(receipt, phase=phase, cell=cell, rows=len(rows)))
        seconds = sum(x['score_wall_seconds'] for x in receipts)
        tokens = sum(x['counter_delta']['tokens'] for x in receipts)
        phases[phase] = dict(chunks=len(receipts), questions=len(panel), tokens=tokens,
                            score_wall_seconds=seconds,
                            score_tokens_per_second_per_chip=tokens / seconds,
                            commit_seconds=sum(x['commit_seconds'] for x in receipts),
                            forwards=sum(x['counter_delta'].get('forwards', 0) for x in receipts),
                            padded_tokens=sum(x['counter_delta'].get('padded_tokens', 0) for x in receipts))
    adir = root / 'attempts' / str(attempt)
    hdir = root / 'host_attempts' / str(attempt)
    needed = [adir / 'EXIT.json', hdir / 'EXIT.json', hdir / 'RELEASE.json', adir / 'report.json']
    missing = [str(x) for x in needed if not x.exists()]
    out = dict(schema='r3-profile-independent-analysis-v1', status='WAIT_TERMINAL' if missing else 'PASS_DIAGNOSTIC_ONLY',
               missing=missing, plan_sha256=expected_sha, phases=phases, operand_chunks=224,
               encoded_raw_argmax_tie_exact=True, chips=1, scientific_acceptance=False,
               candidate_selection_allowed=False, test_read=False, evidence=pins,
               scope='Instrumented diagnostic panel only; encode hash, explicit sync and diagnostic fsync included. Not production VerifiedStore throughput.',
               device_attribution='unavailable until separately interpreted device trace')
    if missing:
        return out
    runtime_exit, host_exit, release, report = [read(x) for x in needed]
    claim, launch = read(hdir / 'CLAIM.json'), read(hdir / 'LAUNCH_RECEIPT.json')
    require(all(type(doc[key]) is int for doc, key in ((runtime_exit, 'exit_code'),
            (runtime_exit, 'attempt'), (host_exit, 'exit_code'), (host_exit, 'container_exit_code'))),
            'terminal integer type differs')
    require(runtime_exit['exit_code'] == host_exit['exit_code'] == host_exit['container_exit_code'] == 0
            and runtime_exit['attempt'] == attempt and runtime_exit['plan_sha256'] == expected_sha
            and host_exit['runner_terminal_matches'] is True, 'terminal mismatch/failure')
    require(release.get('schema') == 'r3-resource-release-v1'
            and claim.get('schema') == 'r3-resource-claim-v1'
            and launch['plan_sha256'] == expected_sha
            and release['claim_sha256'] == sha(hdir / 'CLAIM.json')
            and release['container_id'] == host_exit['container_id'] == launch['container_id']
            and release['run'] == claim['run'] == plan['run']
            and type(release['chip']) is int and type(claim['chip']) is int
            and release['chip'] == claim['chip'] == 6,
            'release lineage mismatch')
    require(report.get('schema') == 'r3-profile-runtime-report-v1'
            and type(report['reused_chunks']) is int and report['reused_chunks'] == 0 and report['timing_comparable'] is True
            and report['all_raw_exact'] is True and typed_equal(report['trials'], trials), 'runtime trials differ')
    require(report['test_read'] is False and report['scientific_acceptance'] is False
            and report['candidate_selection_allowed'] is False
            and type(report['runtime']['chips']) is int and report['runtime']['chips'] == 1, 'report scope differs')
    for phase, summary in phases.items():
        stated = report['phases'][phase]
        require(stated['complete'] is True and type(stated['chunks']) is int and stated['chunks'] == 32
                and type(stated['tokens']) is int and number(stated['score_wall_seconds'])
                and stated['score_wall_seconds'] == summary['score_wall_seconds']
                and stated['tokens'] == summary['tokens'], 'phase reconstruction differs')
        wall = stated['wall_seconds_including_commit_and_comparison']
        require(number(wall) and wall >= summary['score_wall_seconds'], 'invalid phase wall')
        require(number(stated['tokens_per_second_per_chip']) and
                stated['tokens_per_second_per_chip'] == summary['score_tokens_per_second_per_chip'],
                'phase score throughput differs')
        require(number(stated['end_to_end_tokens_per_second_per_chip']) and stated['end_to_end_tokens_per_second_per_chip'] == summary['tokens'] / wall, 'wall throughput differs')
        summary['wall_seconds_including_commit_and_comparison'] = wall
        summary['end_to_end_tokens_per_second_per_chip'] = summary['tokens'] / wall
    require(all(number(report['runtime'][key])
                for key in ('reserved_gib', 'peak_reserved_gib', 'model_load_seconds')),
            'invalid runtime memory/timing')
    require(report['runtime']['peak_reserved_gib'] >= report['runtime']['reserved_gib'], 'peak below reserved')
    wall_mean = statistics.mean(phases['wall_' + str(i)]['wall_seconds_including_commit_and_comparison'] for i in range(3))
    ratio = phases['trace']['wall_seconds_including_commit_and_comparison'] / wall_mean
    require(number(report['profile_overhead_ratio']) and math.isclose(ratio, report['profile_overhead_ratio'], rel_tol=1e-12), 'trace overhead differs')
    out.update(runtime=report['runtime'], profile_overhead_ratio=ratio,
               mean_wall_seconds=wall_mean, mean_questions_per_second_per_chip=len(panel) / wall_mean,
               timing_comparable=True)
    host_trace = adir / 'host-trace.json'
    if host_trace.exists():
        trace = read(host_trace)
        require(trace['nested_not_additive'] is True, 'host spans overlap')
        by_method = {}
        for event in trace['events']:
            require(number(event['host_seconds']), 'invalid host span')
            by_method.setdefault(event['method'], []).append(event['host_seconds'])
        out['nested_host_spans_not_additive'] = {k:dict(count=len(v), seconds=sum(v)) for k,v in by_method.items()}
        needed.append(host_trace)
    for path in needed + [hdir / 'CLAIM.json', hdir / 'LAUNCH_RECEIPT.json']:
        pins[str(path)] = sha(path)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = reconstruct(args.plan, args.sha256)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('evidence', 'phases')}))


if __name__ == '__main__':
    main()
