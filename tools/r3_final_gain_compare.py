"""Same-test paired gain arithmetic over externally verified question vectors.

This module never loads readouts, test datasets, FINAL, or approval files. A
caller must first verify published source evidence and construct these vectors.
Passing this arithmetic is neither publication authorization nor scientific
acceptance. Bootstrap questions after averaging the two candidate seeds; K0 is
one deterministic checkpoint and is never duplicated into synthetic seeds.
"""
import ast
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

SELECTOR = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/cpu_selection_queue_20261031_v5/select_r3.py')
SELECTOR_SHA256 = '43b9a54530bf178596fc06ed2e714054b935115cf2d7dedfa354ea7d64a71e08'
SUITES = {'decision-v7': 1200, 'transfer-v4': 656}
CONTROL_BASE = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'
CONTROL_INSTRUCT = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'
PROTOCOL = {'mode': 'rightpad', 'dtype': 'float32', 'hf32': False,
            'token_budget': 16384, 'headline': 'kev_argmax_first',
            'input_mode': 'full', 'render': 'record_name'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def pin(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None,
            'invalid identity SHA256')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


@lru_cache(maxsize=1)
def original_bootstrap():
    """Use the hash-pinned original function without importing its data loaders."""
    raw = SELECTOR.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SELECTOR_SHA256, 'selector source changed')
    tree = ast.parse(raw)
    names = {'BOOTSTRAP_SEED', 'BOOTSTRAP_RESAMPLES', 'CI_LEVEL', 'BOOTSTRAP_DRAW'}
    nodes = [node for node in tree.body if
             (isinstance(node, ast.FunctionDef) and node.name == 'paired_bootstrap') or
             (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets))]
    require(len(nodes) == 5, 'bootstrap source shape differs')
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SELECTOR), 'exec'), namespace)
    require(namespace['BOOTSTRAP_SEED'] == 20261030 and namespace['BOOTSTRAP_RESAMPLES'] == 10000
            and namespace['CI_LEVEL'] == .90, 'bootstrap protocol differs')
    return namespace['paired_bootstrap']


def protocol_for_arm(arm):
    require(arm in ('K0', 'K1', 'K2', 'K1-QO', 'K1-PT'), 'unregistered vector arm')
    return dict(PROTOCOL, input_mode='drop' if arm == 'K1-QO' else 'full')


def validate(report):
    require(report.get('schema') == 'r3-verified-test-vector-v1', 'vector schema differs')
    require(report.get('partition') == 'test', 'same-test vectors required')
    require(report.get('protocol') == protocol_for_arm(report.get('arm')), 'scoring protocol differs')
    require(set(report.get('suites', {})) == set(SUITES), 'suite population differs')
    model = report['model']
    for field in ('sha256', 'base_inventory_sha256'):
        pin(model[field])
    require(isinstance(model.get('path'), str) and Path(model['path']).is_absolute()
            and isinstance(model.get('base_path'), str) and Path(model['base_path']).is_absolute(),
            'absolute model/base identities required')
    # This SHA identifies evidence previously verified by the caller. Its
    # presence cannot prove verification; no publication claim follows here.
    pin(report['verified_evidence_sha256'])
    # The caller hashes the complete scoring code/layout/prompt protocol,
    # excluding model weights so trained and untuned arms can be compared.
    pin(report['scoring_protocol_sha256'])
    arm = report['arm']
    if arm in ('K1-QO', 'K1-PT'):
        require(model.get('kind') == 'lora-adapter-unmerged', 'control requires unmerged adapter')
        require(type(report.get('seed')) is int and report['seed'] in ((2,) if arm == 'K1-QO' else (2, 3)),
                'control seed differs')
        require(model['base_path'] == (CONTROL_BASE if arm == 'K1-QO' else CONTROL_INSTRUCT),
                'control base differs')
        require(isinstance(report.get('training_variant'), dict) and report['training_variant'],
                'control training recipe absent')
        require(report.get('role', 'control') == 'control', 'control cannot be a candidate')
    for suite, n in SUITES.items():
        cell = report['suites'][suite]
        pin(cell['dataset_sha256'])
        keys, correct = cell['keys'], cell['correct']
        require(isinstance(keys, list) and len(keys) == n
                and all(isinstance(k, str) and bool(k) for k in keys)
                and len(set(keys)) == n, 'wrong or duplicate question population')
        require(isinstance(correct, list) and len(correct) == n
                and all(type(v) is int and v in (0, 1) for v in correct),
                'correctness vector must contain one binary integer per question')


def compare(candidate, baseline):
    """Compute diagnostics from two verified candidate seed vectors and one K0.

    Each vector declares model/base byte identities, exact protocol, evidence
    SHA, and two ordered test populations. No result here certifies the caller's
    claim that those identities or vectors were source-verified.
    """
    require(isinstance(candidate, list) and len(candidate) == 2, 'exactly two candidate seeds required')
    for report in candidate + [baseline]:
        validate(report)
    require(all(type(r.get('seed')) is int for r in candidate)
            and sorted(r['seed'] for r in candidate) == [2, 3], 'candidate seeds must be distinct 2 and 3')
    candidate = sorted(candidate, key=lambda r: r['seed'])
    require('seed' not in baseline and baseline.get('arm') == 'K0'
            and baseline['model'].get('kind') == 'checkpoint', 'K0 must be a single untuned checkpoint')
    require(baseline['model']['path'] == baseline['model']['base_path'], 'K0 base path differs')
    require(candidate[0].get('arm') in ('K1', 'K2') and candidate[0]['arm'] == candidate[1].get('arm'),
            'candidate arms differ')
    require(isinstance(candidate[0].get('training_variant'), dict) and bool(candidate[0]['training_variant'])
            and canonical(candidate[0]['training_variant']) == canonical(candidate[1].get('training_variant')),
            'candidate training recipes differ')
    require(candidate[0]['model']['path'] != candidate[1]['model']['path'], 'candidate seed artifacts alias')
    for report in candidate:
        require(report['scoring_protocol_sha256'] == baseline['scoring_protocol_sha256'],
                'scoring code/layout/prompt identity differs')
        require(report['model'].get('kind') == 'lora-adapter-unmerged', 'trained candidate must be unmerged adapter')
        for field in ('base_path', 'base_inventory_sha256'):
            require(report['model'][field] == baseline['model'][field], 'different base checkpoint bytes or path')
        for suite in SUITES:
            a, b = report['suites'][suite], baseline['suites'][suite]
            require(a['dataset_sha256'] == b['dataset_sha256'] and a['keys'] == b['keys'],
                    'paired test population or dataset identity differs')
    bootstrap = original_bootstrap()
    results, gains, drops = {}, [], []
    for suite, n in SUITES.items():
        vectors = [r['suites'][suite]['correct'] for r in candidate]
        k0 = baseline['suites'][suite]['correct']
        means = [(x+y)/2 for x,y in zip(*vectors)]
        # Exact rational counts decide inclusive point thresholds, avoiding
        # floating-point rounding at +1pp and -1pp boundaries.
        delta = Fraction(sum(map(sum, vectors)), 2*n) - Fraction(sum(k0), n)
        gain, drop = delta >= Fraction(1,100), delta >= -Fraction(1,100)
        gains.append(gain); drops.append(drop)
        results[suite] = {'n_questions': n, 'candidate_seeds': [2,3],
            'candidate_seed_accuracy': [sum(v)/n for v in vectors],
            'candidate_mean_accuracy': sum(means)/n, 'k0_accuracy': sum(k0)/n,
            'difference_percentage_points': float(delta*100),
            'paired_bootstrap': bootstrap(means, k0),
            'gain_at_least_one_percentage_point': gain, 'drop_at_most_one_percentage_point': drop}
    return {'schema': 'r3-final-gain-diagnostics-v1', 'scientific_acceptance': False,
            'publication_authorized': False, 'scope': 'arithmetic over caller-verified vectors only',
            'population_unit': 'questions; candidate seeds averaged before resampling',
            'selector_sha256': SELECTOR_SHA256, 'per_suite': results,
            'point_gain_requirement_met': any(gains) and all(drops),
            'thresholds': {'minimum_gain_pp_one_suite': 1, 'minimum_delta_pp_each_suite': -1},
            'inputs': {'candidate': [r['verified_evidence_sha256'] for r in candidate],
                       'baseline': baseline['verified_evidence_sha256']},
            'limitations': ['Caller must source-verify published readouts and model/dataset identities.',
                           'Confidence intervals are reported, not an additional unregistered gate.',
                           'No FINAL, eligibility, source verification or independent review is granted.']}
