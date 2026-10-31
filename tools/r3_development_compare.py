#!/usr/bin/env python3
"""Revalidate selection reports and compare dev evidence; never select FINAL.

K0 is a single deterministic checkpoint, not a fabricated two-seed arm. Optional
incumbent reports provide the actual two-seed arm-to-arm adoption diagnostics.
Formal launch review, R0 eligibility and test authorization remain separate.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def verified_report(path, report_tool, deps, kev_dir, data_root):
    path = Path(path).resolve()
    require(path.name == 'selection_report.json', 'selection report required')
    stored = report_tool.load(path)
    require(stored.get('schema') == 'r3-selection-report-v1' and
            stored.get('scientific_acceptance') is False, 'report scope differs')
    # Recompute rather than trusting saved metrics, keys, training manifests or
    # receipt hashes. This reruns producer, weight and population verification.
    actual = report_tool.rebuild(path.parent, kev_dir, data_root, deps)
    require(canonical(stored) == canonical(actual), 'saved report differs from verified readouts')
    return actual


def compare(candidate, baseline, E, S, incumbent=None, r0_gating=None):
    E.validate_seed_reports(candidate)
    require(baseline['header']['arm'] == 'K0' and
            baseline['header']['model']['kind'] == 'checkpoint', 'untuned K0 required')
    require('seed' not in baseline['selection_evidence'], 'K0 must not impersonate a training seed')
    if incumbent:
        E.validate_seed_reports(incumbent)
    reports = candidate + [baseline] + (incumbent or [])
    base = baseline['header']['model']
    keys = baseline['selection_evidence']['keys']
    require(len(keys) == 1920 and len({tuple(k) for k in keys}) == 1920, 'invalid development population')
    require([k[0] for k in keys] == ['decision-v7'] * 1264 + ['transfer-v4'] * 656,
            'development suites or order differ')
    for report in reports:
        h, evidence = report['header'], report['selection_evidence']
        require(set(h['partitions']) == {'dev', 'calibration'} and h['track_t_config'] == 'r3',
                'development scope differs')
        require(evidence['keys'] == keys, 'paired question populations differ')
        require(len(evidence['correct']) == len(keys) and all(type(x) is int and x in (0, 1)
                for x in evidence['correct']), 'invalid correctness vector')
        require(h['data_files'] == baseline['header']['data_files'], 'producer datasets differ')
        for field in ('prompt_version', 'prompt_format', 'render', 'primary_input_mode', 'dtype', 'readings'):
            require(field in h and h[field] == baseline['header'].get(field),
                    'evaluation protocol differs: ' + field)
        require(Path(h['model']['base_path']).resolve() == Path(base['path']).resolve()
                and h['model']['base_revision'] == base['base_revision'], 'different base checkpoint')
        for field in ('cells', 'question70', 'decision_lines'):
            require(not report['track_t'].get(field, {}).get('report'), 'report-half metrics forbidden')
    a = [r['selection_evidence']['correct'] for r in candidate]
    k0 = [baseline['selection_evidence']['correct']]

    def paired(left, right):
        am, bm = S._seed_mean(left), S._seed_mean(right)
        suites, start = {}, 0
        for suite, n in [('decision-v7', 1264), ('transfer-v4', 656)]:
            sl = slice(start, start + n); start += n
            av, bv = [sum(x[sl]) / n for x in left], [sum(x[sl]) / n for x in right]
            suites[suite] = {'n': n, 'candidate_seed_accuracy': av, 'reference_accuracy': bv,
                'paired_bootstrap': S.paired_bootstrap(am[sl], bm[sl]),
                'suite_drop_within_registered_limit': S.drop_ok(sum(av)/len(av), sum(bv)/len(bv)),
                'discordant': S.discordant(am[sl], bm[sl])}
        return {'combined': S.paired_bootstrap(am, bm), 'per_suite': suites,
                'discordant': S.discordant(am, bm)}

    result = {'schema': 'r3-development-comparison-v1', 'scientific_acceptance': False,
              'test_read': False, 'scope': 'verified development diagnostics; no adoption or FINAL',
              'candidate_seeds': [r['selection_evidence']['seed'] for r in candidate],
              'candidate_variant': candidate[0]['selection_evidence']['training_variant'],
              'against_k0': paired(a, k0), 'k_floor': S.k_floor(candidate),
              'blockers': ['exact-plan independent acceptance and formal run eligibility not established',
                           'candidate not locked; final same-test gain has not been evaluated']}
    if candidate[0]['header']['arm'] == 'K1' and Path(base['path']).name == 'Qwen__Qwen3.5-0.8B-Base':
        result['k_align'] = S.k_align(candidate)
    elif candidate[0]['header']['arm'] == 'K1':
        result['k_align'] = {'status': 'not_applicable',
                             'reason': 'registered K-align decision line is for 0.8B only'}
    if incumbent:
        b = [r['selection_evidence']['correct'] for r in incumbent]
        result['against_incumbent'] = paired(a, b)
        if r0_gating is None:
            result['condition_c'] = {'status': 'blocked', 'reason': 'verified R0 gating missing'}
            result['blockers'].append('verified R0 gating missing for arm adoption condition c')
        else:
            result['condition_c'] = S.condition_c([r['track_t']['selection'] for r in candidate],
                [r['track_t']['selection'] for r in incumbent], r0_gating)
    else:
        result['blockers'].append('no two-seed incumbent supplied; K0 diagnostics do not decide arm adoption')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', nargs=2, required=True)
    p.add_argument('--baseline', required=True)
    p.add_argument('--incumbent', nargs=2)
    p.add_argument('--frozen-code-dir', required=True)
    p.add_argument('--selector', required=True)
    p.add_argument('--selector-sha256', required=True)
    p.add_argument('--report-tool', required=True)
    p.add_argument('--report-tool-sha256', required=True)
    p.add_argument('--r0-run')
    p.add_argument('--kev-dir', default='/mnt/cephfs/xingchao/experiments/jev/KEV')
    p.add_argument('--data-root', default='/mnt/cephfs/xingchao/experiments/jev')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    import hashlib
    for path, pin in [(args.selector, args.selector_sha256), (args.report_tool, args.report_tool_sha256)]:
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == pin, 'consumer code identity differs')
    R = module(args.report_tool, 'development_report_tool')
    deps = R.modules(args.frozen_code_dir)
    S = module(args.selector, 'development_selector')
    require(S.C is deps[0] and S.E is deps[1], 'selector dependencies escaped verified closure')
    load = lambda path: verified_report(path, R, deps, args.kev_dir, args.data_root)
    candidates = [load(path) for path in args.candidate]
    baseline = load(args.baseline)
    incumbents = [load(path) for path in args.incumbent] if args.incumbent else None
    gate = deps[1].load_r0_gating(args.r0_run) if args.r0_run else None
    result = compare(candidates, baseline, deps[1], S, incumbents, gate)
    result['inputs'] = {str(Path(path).resolve()): R.sha(path)
        for path in args.candidate + [args.baseline] + (args.incumbent or [])}
    result['code'] = {'selector_sha256': args.selector_sha256, 'report_tool_sha256': args.report_tool_sha256,
                      'closure_manifest_sha256': R.sha(Path(args.frozen_code_dir).parent / 'manifest.json')}
    out = Path(args.output)
    require(out.name not in ('FINAL.json', 'report.json', 'selection_report.json'), 'reserved output name')
    with out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'output': str(out), 'scientific_acceptance': False}))


if __name__ == '__main__':
    main()
