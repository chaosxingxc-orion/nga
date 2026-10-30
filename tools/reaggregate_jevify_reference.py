#!/usr/bin/env python3
"""Reaggregate published Jevify test summaries without reading predictions.

Run with python3 -I. Only leaderboard.json and mapped test_metrics.json files
are opened. Values are fractions, never percentages. No inference is performed.
"""

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from statistics import fmean


DEFAULT_ROOT = Path('/mnt/cephfs/xingchao/omni/datasets/jev/Praveenrajus__jev-bench/results')
DEFAULT_OUT = Path('/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/jevify_reaggregation')
METRICS = {'acc': 'accuracy', 'brier': 'brier', 'ece': 'ece',
           'sel90': 'selective_acc_at_90'}
TOLERANCE = 1e-12


def read_json(path):
    data = path.read_bytes()
    return json.loads(data), {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}


def checked_metrics(path):
    data, source = read_json(path)
    if not isinstance(data, dict) or not data:
        raise ValueError(f'Expected nonempty per-config mapping: {path}')
    clean = {}
    for config, row in data.items():
        n = row.get('n')
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ValueError(f'Invalid n: {path}: {config}')
        clean[config] = {'n': n}
        for key in METRICS.values():
            value = row.get(key)
            if value is not None and (isinstance(value, bool) or
                    not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f'Invalid {key}: {path}: {config}')
            clean[config][key] = value
    return clean, source


def summarize(configs):
    macro, weighted, coverage = {}, {}, {}
    for key in METRICS.values():
        rows = [v for v in configs.values() if v[key] is not None]
        n = sum(v['n'] for v in rows)
        macro[key] = fmean(v[key] for v in rows) if rows else None
        weighted[key] = math.fsum(v['n'] * v[key] for v in rows) / n if n else None
        coverage[key] = {'configs': len(rows), 'n': n}
    return {'config_count': len(configs), 'n_per_seed': sum(v['n'] for v in configs.values()),
            'config_macro': macro, 'sample_weighted_config_metrics': weighted,
            'metric_coverage': coverage}


def process_row(root, row):
    run = row['run']
    match = re.search(r'mean of (\d+) seeds', row['label'])
    count = int(match.group(1)) if match else 1
    paths = [root / f'{run}-s{i}' / 'test_metrics.json' for i in range(count)] if match else [root / run / 'test_metrics.json']
    if not match and not paths[0].exists() and run.startswith('post-training/'):
        paths = [root / 'post-training' / 'models' / run.split('/', 1)[1] / 'test_metrics.json']
    result = {'run': run, 'label': row['label'], 'tier': row.get('tier'),
              'aggregation': 'seed_mean' if match else 'single_published_run',
              'seed_count': count, 'published_summary': row['summary'],
              'missing_mappings': [str(p) for p in paths if not p.is_file()]}
    if result['missing_mappings']:
        result['status'] = 'missing_mapping'
        return result
    sources, configs = [], []
    for path in paths:
        metrics, source = checked_metrics(path)
        sources.append({**source, 'per_config': metrics, 'recomputed': summarize(metrics)})
        configs.append(metrics)
    reference = configs[0]
    for data in configs[1:]:
        if set(data) != set(reference) or any(data[k]['n'] != reference[k]['n'] for k in reference):
            raise ValueError(f'Seed config coverage / sample counts differ: {run}')
    # Equal seed weighting; n is one test split, not independent replicated data.
    mean_configs = {}
    for config, first in reference.items():
        mean_configs[config] = {'n': first['n']}
        for key in METRICS.values():
            values = [data[config][key] for data in configs]
            mean_configs[config][key] = fmean(values) if all(v is not None for v in values) else None
    summary = summarize(mean_configs)
    delta = {}
    for published_key, key in METRICS.items():
        original = row['summary']['macro'].get(published_key)
        recomputed = summary['config_macro'][key]
        delta[key] = recomputed - original if original is not None and recomputed is not None else None
    matches = all(v is not None and abs(v) <= TOLERANCE for v in delta.values())
    result.update(status='verified' if matches else 'macro_mismatch', sources=sources,
                  per_config=mean_configs, recomputed=summary,
                  recomputed_minus_published_macro=delta,
                  published_macro_matches=matches)
    return result


def write_csv(path, rows):
    fields = ['record_type', 'run', 'label', 'aggregation', 'seed_count', 'config', 'status',
              'config_count', 'n_per_seed', 'accuracy', 'brier', 'ece', 'selective_acc_at_90',
              'weighted_accuracy', 'weighted_brier', 'weighted_config_ece_not_pooled',
              'weighted_config_selective_acc_at_90', 'delta_accuracy', 'delta_brier',
              'delta_ece', 'delta_selective_acc_at_90', 'source_paths', 'source_sha256']
    with path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            base = {k: row[k] for k in ('run', 'label', 'aggregation', 'seed_count', 'status')}
            base['source_paths'] = '|'.join(s['path'] for s in row.get('sources', []))
            base['source_sha256'] = '|'.join(s['sha256'] for s in row.get('sources', []))
            summary = row.get('recomputed', {})
            weighted = summary.get('sample_weighted_config_metrics', {})
            writer.writerow({**base, 'record_type': 'summary',
                'config_count': summary.get('config_count'), 'n_per_seed': summary.get('n_per_seed'),
                **summary.get('config_macro', {}), 'weighted_accuracy': weighted.get('accuracy'),
                'weighted_brier': weighted.get('brier'), 'weighted_config_ece_not_pooled': weighted.get('ece'),
                'weighted_config_selective_acc_at_90': weighted.get('selective_acc_at_90'),
                **{'delta_' + k: v for k, v in row.get('recomputed_minus_published_macro', {}).items()}})
            for config, metrics in row.get('per_config', {}).items():
                writer.writerow({**base, 'record_type': 'per_config', 'config': config,
                                 'n_per_seed': metrics['n'],
                                 **{k: metrics[k] for k in METRICS.values()}})


def number(value):
    return '—' if value is None else f'{value:.9f}'


def write_markdown(path, report):
    lines = ['# Jevify published test metrics: reaggregation', '',
        'This is arithmetic over published summary files, not a local model reproduction.', '',
        '- Config macro: equal mean over available dataset configurations.',
        '- Question-weighted accuracy/Brier: sum(n × metric) / sum(n).',
        '- Weighted-config ECE: sum(n × config ECE) / sum(n); **not pooled ECE**.',
        '- sel90 is selective accuracy at 90% coverage, not confidence ≥ 0.9. Its weighted config mean is not a globally reranked selective metric.',
        '- Seed-mean rows average each metric equally across the named seeds, then across configurations. n is per seed; repeated test examples are not new independent samples.',
        '- Null metrics are excluded with explicit per-metric coverage in JSON. Missing seed values are retained as null in seed means.',
        '- The JSON preserves original summaries, every source hash, individual seed metrics, and per-config n/accuracy/Brier/ECE/sel90.',
        '- All numbers are fractions. Recomputed macro comparisons use absolute tolerance 1e-12.', '',
        f"Leaderboard: `{report['leaderboard_source']['path']}`", '',
        f"SHA256: `{report['leaderboard_source']['sha256']}`", '',
        '| Run | Seeds | Configs | n/seed | Macro acc | Weighted acc | Macro Brier | Weighted Brier | Macro ECE | Weighted-config ECE (not pooled) | Max macro delta | Status |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for row in report['rows']:
        s = row.get('recomputed', {})
        macro, weighted = s.get('config_macro', {}), s.get('sample_weighted_config_metrics', {})
        deltas = [abs(v) for v in row.get('recomputed_minus_published_macro', {}).values() if v is not None]
        cells = [row['run'], str(row['seed_count']), str(s.get('config_count', '—')),
                 str(s.get('n_per_seed', '—')), number(macro.get('accuracy')), number(weighted.get('accuracy')),
                 number(macro.get('brier')), number(weighted.get('brier')), number(macro.get('ece')),
                 number(weighted.get('ece')), f'{max(deltas):.3g}' if deltas else '—', row['status']]
        lines.append('| ' + ' | '.join(cells) + ' |')
    lines += ['', '## Mapping and validation', '', '```json', json.dumps(report['validation'], indent=2), '```', '']
    for row in report['rows']:
        lines += [f"## {row['run']}", '', row['label'], '',
                  '| Config | n/seed | Accuracy | Brier | ECE | sel90 |',
                  '|---|---:|---:|---:|---:|---:|']
        for config, values in row.get('per_config', {}).items():
            lines.append('| ' + ' | '.join([config, str(values['n'])] +
                         [number(values[k]) for k in METRICS.values()]) + ' |')
        lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT, help='Output filename prefix (no extension)')
    args = parser.parse_args()
    leaderboard, source = read_json(args.results_root / 'leaderboard' / 'leaderboard.json')
    if len({row['run'] for row in leaderboard}) != len(leaderboard):
        raise ValueError('Duplicate leaderboard run IDs')
    rows = [process_row(args.results_root, row) for row in leaderboard]
    validation = {'leaderboard_rows': len(rows),
                  'verified_rows': sum(row['status'] == 'verified' for row in rows),
                  'seed_mean_rows': [row['run'] for row in rows if row['aggregation'] == 'seed_mean'],
                  'missing_mappings': {row['run']: row['missing_mappings'] for row in rows if row['missing_mappings']},
                  'macro_mismatches': [row['run'] for row in rows if row['status'] == 'macro_mismatch'],
                  'source_metrics_files': sum(len(row.get('sources', [])) for row in rows),
                  'per_config_rows': sum(len(row.get('per_config', {})) for row in rows)}
    report = {'schema_version': 1, 'leaderboard_source': source,
              'formulas': {'config_macro': 'sum(config_metric) / number_of_nonnull_configs',
                           'sample_weighted_config_metrics': 'sum(n_config * config_metric) / sum(n_config)',
                           'seed_mean': 'equal mean over explicitly named seeds; n remains per seed'},
              'limitations': ['Weighted-config ECE is not pooled ECE.',
                             'Weighted-config sel90 is not global selective accuracy.',
                             'Published model results; no local inference or reproduction.',
                             'Single-run rows are not upgraded to seed means merely because sibling seeds exist.'],
              'validation': validation, 'rows': rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Path(str(args.out) + '.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    write_csv(Path(str(args.out) + '.csv'), rows)
    write_markdown(Path(str(args.out) + '.md'), report)
    print(json.dumps(validation, indent=2))
    return 1 if validation['missing_mappings'] or validation['macro_mismatches'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
