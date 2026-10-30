#!/usr/bin/env python3
"""Copy published aggregate tables with provenance; no inference or test-item reads.

python3 -I tools/build_reference_tables.py --out DIR
"""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def source(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def tables(path):
    lines = path.read_text().splitlines()
    heading = ""
    found = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#"):
            heading = lines[i].lstrip("# ")
        if (i + 1 < len(lines) and lines[i].startswith("|")
                and re.fullmatch(r"[| :\-]+", lines[i + 1])):
            start = i
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                i += 1
            raw = lines[start:i]
            found.append({"heading": heading, "line": start + 1,
                          "header": [x.strip() for x in raw[0].strip("|").split("|")],
                          "rows": [[x.strip() for x in line.strip("|").split("|")]
                                   for line in raw[2:]], "markdown": "\n".join(raw)})
        else:
            i += 1
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datasets-root", type=Path,
                    default=Path('/mnt/cephfs/xingchao/omni/datasets/jev'))
    ap.add_argument("--kev-repo", type=Path,
                    default=Path('/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev'))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cards = []
    markdown = ["# Published dataset-card tables\n",
                "Copied verbatim with source hashes. Includes data inventories and non-test tables; "
                "only explicitly identified model-test tables are test evidence.\n"]
    for path in sorted(args.datasets_root.glob('*/README.md')):
        extracted = tables(path)
        cards.append({**source(path), "dataset": path.parent.name, "tables": extracted})
        markdown.append(f"\n## {path.parent.name}\n\nSource: `{path}`\n\nSHA256: `{source(path)['sha256']}`\n")
        for table in extracted:
            markdown.append(f"\n### {table['heading']} — source line {table['line']}\n\n{table['markdown']}\n")
    write_json(args.out/'dataset_readme_tables.json', cards)
    (args.out/'dataset_readme_tables.md').write_text('\n'.join(markdown))

    panels = []
    specifications = {
        'Praveenrajus__jev-bench': ['results/leaderboard/leaderboard.json',
                                  'results/community/report.json',
                                  'results/tev1-comparison/comparison.json'],
        'startlux-models__DecisionPivot': ['tables/T1_core_headline_intervals.csv',
                                          'tables/T2_core_per_family.csv',
                                          'tables/T3_reference_layers.csv',
                                          'tables/T4_one_pass_vs_reasoning.csv',
                                          'tables/jev113_core_headline.csv'],
        'yflantmy__DecisionRobust': ['results/asr.csv', 'results/flip_asr.csv',
                                   'results/additional_models_by_config.csv',
                                   'results/additional_models_by_dataset.csv',
                                   'results/additional_models_matched_coverage.csv'],
        'bespokelabs__bespoke-nimble-9b-v3-decision-index': ['runs/bespoke-nimble-9b-v3/scores.json'],
        'DaehanKim__korean-jev-benchmark': ['results/20261008_v7/korean_plotted_metrics.csv',
                                         'results/20261008_v7/english_plotted_metrics.csv'],
    }
    missing = []
    for dataset, rels in specifications.items():
        for rel in rels:
            path = args.datasets_root/dataset/rel
            if not path.exists():
                missing.append(str(path))
                continue
            data = (list(csv.DictReader(path.open(newline=''))) if path.suffix == '.csv'
                    else json.loads(path.read_text()))
            panels.append({**source(path), "dataset": dataset,
                           "scope": "Published aggregate; retain source split, version and coverage. Not all panels are test.",
                           "data": data})
    # All existing per-config test summaries, without reading prediction rows.
    for path in sorted((args.datasets_root/'Praveenrajus__jev-bench/results').rglob('test_metrics.json')):
        panels.append({**source(path), "dataset": "Praveenrajus__jev-bench",
                       "scope": "Published per-config test metrics; historical runs remain separate.",
                       "data": json.loads(path.read_text())})
    write_json(args.out/'reference_panels.json', panels)

    release = []
    for name in ['kev-08b-r15', 'kev-4b-r10', 'kev-9b-r27', 'kev-27b-r23']:
        path = args.kev_repo/'runs/release'/f'{name}.json'
        data = json.loads(path.read_text())
        for panel in ['locked_decision', 'locked_transfer', 'hard_test', 'devtools_test', 'docs1_test']:
            if panel in data['candidate']:
                release.append({**source(path), 'model_run': name, 'panel': panel,
                                'split': 'test', 'calibration': 'upstream release served temperature',
                                'json_pointer': f'/candidate/{panel}', 'metrics': data['candidate'][panel]})
    write_json(args.out/'kev_release_test_metrics.json', release)
    fields = ['model_run', 'panel', 'split', 'calibration', 'n', 'acc', 'brier', 'ece', 'nll',
              'confident_error_rate', 'coverage_at_5pct_error', 'path', 'sha256']
    with (args.out/'kev_release_test_metrics.csv').open('w', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for item in release:
            writer.writerow({k: item.get(k, item['metrics'].get(k)) for k in fields})
    # Human-readable non-selected model rows: preserve all configurations.
    panel_md = ['# Published aggregate panels\n',
                'Source-native values; test/eval/challenge and versions are not merged.\n']
    for panel in panels:
        data = panel['data']
        if isinstance(data, list) and data and isinstance(data[0], dict):
            panel_md.append(f"\n## {panel['dataset']} — {Path(panel['path']).name}\n\n`{panel['path']}`\n\nSHA256 `{panel['sha256']}`\n")
            if panel['path'].endswith('leaderboard.json'):
                fields = ['run', 'label', 'tier', 'acc', 'ece', 'brier', 'sel90']
                display = [{**x, **x.get('summary', {}).get('macro', {})} for x in data]
            else:
                fields = list(data[0]); display = data
            panel_md.append('| ' + ' | '.join(fields) + ' |\n| ' + ' | '.join(['---']*len(fields)) + ' |')
            for row in display:
                panel_md.append('| ' + ' | '.join(str(row.get(k, '')).replace('|', '\\|').replace('\n', ' ') for k in fields) + ' |')
    (args.out/'reference_panels.md').write_text('\n'.join(panel_md)+'\n')
    index = {'generated_utc': datetime.now(timezone.utc).isoformat(),
             'no_model_inference': True, 'no_test_items_or_predictions_read': True,
             'dataset_cards': [{k:v for k,v in c.items() if k != 'tables'} | {'tables':len(c['tables'])} for c in cards],
             'panels': [{k:v for k,v in p.items() if k != 'data'} for p in panels],
             'kev_release_panels': len(release), 'missing_sources': missing,
             'output_directory': str(args.out)}
    write_json(args.out/'reference_table_manifest.json', index)
    print(json.dumps({'dataset_cards':len(cards), 'markdown_tables':sum(len(c['tables']) for c in cards),
                      'aggregate_panels':len(panels), 'release_panels':len(release), 'missing':missing}))


if __name__ == '__main__':
    main()
