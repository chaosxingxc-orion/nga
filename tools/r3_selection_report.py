#!/usr/bin/env python3
"""Rebuild CPU selection evidence from complete, verified producer readouts.

Never opens test partitions or calls report-half metric aggregation. Does not
write report.json or confer formal acceptance. All model rows retain provenance.
"""
import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def modules(code_dir):
    root = Path(code_dir).resolve()
    r0 = root.parent / 'r0_code'
    require(root.name == 'r3_code' and r0.is_dir(), 'frozen r3_code and sibling r0_code required')
    manifest = load(root.parent / 'manifest.json')
    require(isinstance(manifest.get('code'), dict) and manifest['code'], 'code manifest missing')
    pinned = set()
    for entry in manifest['code'].values():
        file = Path(entry['snapshot'])
        require(file.is_absolute() and not any(x.is_symlink() for x in (file, *file.parents)),
                'invalid frozen code dependency')
        require(sha(file) == entry['sha256'], 'frozen code changed: ' + str(file))
        pinned.add(file.resolve())
    actual = {p.resolve() for directory in (root, r0) for p in directory.rglob('*.py')}
    require(actual == pinned, 'frozen code inventory differs')
    sys.path[:0] = [str(root), str(r0)]
    C = importlib.import_module('core_r3')
    # core_r3 carries historical absolute paths. Resolve every subsequent local
    # import from this supplied closure, then check origins explicitly.
    sys.path[:0] = [str(root), str(r0)]
    names = ['selection_evidence_r3', 'degenerate_r3', 'prechecks_r3', 'variants_r3',
             'track_t_r3', 'provenance_r3', 'testlock_r3', 'common', 'split', 'thresholds', 'metrics', 'prompt', 'scorer']
    loaded = {name: importlib.import_module(name) for name in names}
    for m in [C, *loaded.values()]:
        require(Path(m.__file__).resolve().parent in (root, r0), 'module escaped frozen closure: ' + m.__name__)
    return C, loaded['selection_evidence_r3'], loaded['degenerate_r3'], loaded['prechecks_r3'], loaded['variants_r3']


def rebuild(run, kev_dir, data_root, deps):
    C, E, D, PC, V = deps
    run, kev_dir, data_root = map(Path, (run, kev_dir, data_root))
    receipt_path = run / 'SCORING_RECEIPT.track_kt.json'
    receipt = load(receipt_path)
    require(receipt.get('schema') == 'r3-scoring-receipt-v1', 'producer receipt schema differs')
    h = receipt['header']
    require(set(h.get('stages', '').split(',')) == {'k_score', 't_score'}, 'complete scoring stages required')
    require(set(h.get('partitions', [])) == {'dev', 'calibration'}, 'dev/calibration only required')
    require(h.get('track_t_config') == 'r3', 'r3 selection split required')
    require(h.get('arm') in ('K0', 'K1', 'K2'), 'unsupported arm')
    marker = load(run / 'EVAL_COMPLETE.track_kt.json')
    require(marker.get('exit_code') == 0, 'scoring did not complete successfully')
    evidence = E.verify_run(str(run), receipt)
    identity = E.train_identity(receipt) if h['arm'] != 'K0' else {
        'arm': 'K0', 'model_path': h['model']['path'], 'model_sha256': h['model']['sha256']}
    if h['arm'] == 'K0':
        require(h['model']['kind'] == 'checkpoint', 'K0 must be an untuned checkpoint')
    train, train_path = C.load_partition('decision-v7', 'train', kev_dir=str(kev_dir))
    parts, variants, paths = {}, {}, [train_path]
    for suite, split in [('decision-v7', 'dev'), ('decision-v7', 'calibration'), ('transfer-v4', 'dev')]:
        rows, path = C.load_partition(suite, split, kev_dir=str(kev_dir))
        parts[(suite, split)] = rows; paths.append(path)
        if split == 'dev':
            var, path = C.load_partition(suite, split, variants=True, kev_dir=str(kev_dir))
            require(bool(var), 'missing development variant population')
            variants[(suite, split)] = var; paths.append(path)
    PC.check_kev_manifest(paths, kev_dir=str(kev_dir))
    require({s: len(parts[(s, 'dev')]) for s in C.SUITES} == {'decision-v7': 1264, 'transfer-v4': 656},
            'development question counts differ from the frozen protocol')
    # Pin to the producing run as well as the normative manifests. A later data
    # replacement must not be accepted merely because another manifest changed.
    for path in paths:
        require(h.get('data_files', {}).get(str(path)) == C.sha256_file(path), 'producer data hash differs: ' + str(path))
    const = D.fit_constant(train)
    block = {'partitions': {}, 'scope': 'dev/calibration; no test metrics'}
    all_scores, keys, correct = {}, [], []
    for (suite, split), rows in parts.items():
        scores = {}
        for kind in ('clean', 'question_only', 'empty_input'):
            stored = C.read_jsonl(C.k_readout_path(str(run), suite, split, kind))
            ordered = E.validate_population(stored, rows, C.kev_key)
            scores[kind] = [x['s'] for x in ordered]
            if kind == 'clean' and split == 'dev':
                keys.extend((suite, x['k']) for x in ordered)
                correct.extend(int(x['argmax'] == x['gold_index']) for x in ordered)
        cs, tiers = D.score_constant(const, rows)
        label = suite + '/' + split
        block['partitions'][label] = {'n': len(rows), 'headline': C.headline(rows, scores['clean']),
            'gold_position_distribution': C.gold_position_distribution(rows),
            'near_tie_census': C.near_tie_census(scores['clean'], gold=[C.gold_index(r) for r in rows],
                keys=[C.kev_key(r) for r in rows], option_ids=[C.level_ids(r) for r in rows]),
            'arms': {'constant': {**C.headline(rows, cs), 'tier_usage': tiers},
                     'uniform': C.headline(rows, D.score_uniform(rows)),
                     **{k: C.headline(rows, scores[k]) for k in ('question_only', 'empty_input')}}}
        all_scores[(suite, split)] = {C.kev_key(r): s for r, s in zip(rows, scores['clean'])}
        if split == 'dev':
            var = variants[(suite, split)]
            readouts = C.read_jsonl(C.k_readout_path(str(run), suite, split, 'variants'))
            ordered = E.validate_population(readouts, var, C.kev_key)
            all_scores[(suite, split)].update({C.kev_key(r): x['s'] for r, x in zip(var, ordered)})
    cal = parts[('decision-v7', 'calibration')]
    fitted = V.fit_operator(cal, [all_scores[('decision-v7', 'calibration')][C.kev_key(r)] for r in cal])
    block['operator_fit'] = {'partition': 'decision-v7/calibration', 'n': len(cal), 'fitted': fitted.summary()}
    op = lambda row, scores: V.operator_decision(fitted, row, scores)[0]
    for (suite, split), var in variants.items():
        rows, scores = parts[(suite, split)], all_scores[(suite, split)]
        block['partitions'][suite + '/' + split]['secondary'] = {
            'permutation': V.permutation_metrics(V.build_permutation_pairs(rows, var), scores, op, h['arm']),
            'nota': V.nota_metrics(V.build_nota_units(rows, var), scores),
            'operator': V.operator_column(rows, [scores[C.kev_key(r)] for r in rows], fitted, suite + '/' + split)}
    for directory, sources in [('T1_level_names', ('typed-decisions', 'openjev-synth', 'akhilaaa3')),
                               ('T2_definition_swap', ('typed-decisions', 'openjev-synth', 'akhilaaa3')),
                               ('T3_question_set', ('typed-decisions',))]:
        for source in sources:
            path = data_root / directory / (source + '.jsonl')
            require(h.get('data_files', {}).get(str(path)) == C.sha256_file(str(path)),
                    'producer Track T data hash differs: ' + str(path))
    track_t = E.rebuild_track_t(str(run), 'r3', data_root=str(data_root), selection_only=True)
    # Defensive fail-closed boundary: even a faulty frozen consumer cannot emit
    # report-half performance through this output. Empty placeholder branches
    # are tolerated, but real values require fixing the consumer, not stripping.
    for key in ('cells', 'question70', 'decision_lines'):
        require(not track_t.get(key, {}).get('report'), 'consumer computed report-half metrics')
    result = {'schema': 'r3-selection-report-v1', 'header': copy.deepcopy(h), 'track_k': block, 'track_t': track_t,
              'selection_evidence': {**identity, 'provenance': evidence, 'keys': keys, 'correct': correct},
              'producer_receipt_sha256': sha(receipt_path), 'scientific_acceptance': False,
              'scope': 'development and selection-half evidence only; formal review remains separate'}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True); p.add_argument('--frozen-code-dir', required=True)
    p.add_argument('--kev-dir', default='/mnt/cephfs/xingchao/experiments/jev/KEV')
    p.add_argument('--data-root', default='/mnt/cephfs/xingchao/experiments/jev')
    p.add_argument('--output')
    a = p.parse_args()
    result = rebuild(a.run, a.kev_dir, a.data_root, modules(a.frozen_code_dir))
    out = Path(a.output) if a.output else Path(a.run) / 'selection_report.json'
    require(out.name != 'report.json', 'do not replace full report.json')
    require(not out.exists(), 'selection output already exists')
    temp = out.with_suffix('.pending')
    with temp.open('x') as stream: json.dump(result, stream, indent=2, sort_keys=True); stream.write('\n')
    os.replace(temp, out)
    print(json.dumps({'output': str(out), 'sha256': sha(out), 'scientific_acceptance': False}))


if __name__ == '__main__':
    main()
