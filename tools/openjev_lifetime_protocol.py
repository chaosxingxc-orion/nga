"""E40 fixed eight-forward protocol; stdlib only, no device or model import."""
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'e40-full-shape-lifetime-v1'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
SOURCE = '0e2cd8dc50885b2701d26b116c585eedcdc62a24080ec34345af55b963126ded'


def require(value, message):
    if not value:
        raise ValueError(message)


def stamp(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def schedule():
    return [dict(mode=mode, repetition=rep) for mode in ('original', 'L1', 'L2', 'L1L2') for rep in (0, 1)]


def name(task):
    return '4200_' + task['mode'] + '_' + str(task['repetition'])


def identity(plan, plan_sha, task):
    return dict(plan_sha256=plan_sha, source_config_sha256=plan['source_config_sha256'],
                input_sha256=stamp(plan['input']), request_sha256=plan['input']['request_sha256'],
                index=4200, **task)


def validate_plan(p):
    require(p['schema'] == SCHEMA and p['image'] == IMAGE and p['schedule'] == schedule(), 'E40 protocol differs')
    require(p['candidate_batch_admission'] is False and p['physical_chip'] == 1
            and p['logical_device'] == 'npu:0', 'E40 admission/device differs')
    require(p['input']['index'] == 4200 and p['input']['shape'] == [15, 186]
            and len(p['input']['candidate_order']) == 15
            and stamp(p['input']['request']) == p['input']['request_sha256'], 'E40 fixed input differs')
    require(p['native_source_sha256'] == SOURCE, 'E40 native source differs')
    require(p['safety'] == dict(max_reserved_gib=48, min_free_gib=8, chips=1,
            on_error='stop_and_preserve_generation', larger_inputs_authorized=False), 'E40 safety envelope differs')
    require(p['performance_scope'] == 'full forward including identical passive token guard; no internal instrumentation',
            'E40 instrumentation differs')
    require(p['resume_policy'] == 'verified fixed prefix, same Docker start generation only; unmatched intent fails closed',
            'E40 resume policy differs')
    require(p['expected_core_names'] and len(p['expected_core_names']) == len(set(p['expected_core_names'])) == 18,
            'E40 2B GDN population differs')


def check_metrics(v, p):
    fields = ['seconds', 'questions_per_second_per_chip', 'tokens_per_second_per_chip',
              'baseline_allocated_gib', 'baseline_reserved_gib', 'peak_allocated_gib', 'peak_reserved_gib', 'free_before_gib']
    require(all(type(v[k]) in (int, float) and math.isfinite(v[k]) and v[k] >= 0 for k in fields), 'Invalid performance value')
    require(v['seconds'] > 0 and v['chips'] == 1 and type(v['chips']) is int, 'Invalid time/chip count')
    require(v['questions_per_second_per_chip'] == 1 / v['seconds'], 'Question throughput differs')
    require(v['tokens_per_second_per_chip'] == sum(p['input']['eligibility']['lengths']) / v['seconds'], 'Token throughput differs')
    require(v['peak_reserved_gib'] >= v['baseline_reserved_gib']
            and v['peak_allocated_gib'] >= v['baseline_allocated_gib'], 'Memory peaks below baseline')
    require(v['free_before_gib'] >= p['safety']['min_free_gib']
            and v['peak_reserved_gib'] <= p['safety']['max_reserved_gib'], 'Safety envelope exceeded')


def check_receipts(p, ph, evidence, prediction_check, complete=False, generation=None):
    """Authenticate complete prefix and both sides of every durable attempt/receipt."""
    validate_plan(p)
    out = Path(p['out']); wanted = {name(t)+'.json': t for t in schedule()}
    paths = {}
    for folder in ('items', 'attempts'):
        root = out / folder
        if not root.exists():
            paths[folder] = {}; continue
        require(root.is_dir() and not root.is_symlink(), 'Invalid receipt directory')
        entries = list(root.iterdir())
        require(all(x.is_file() and not x.is_symlink() and x.name in wanted for x in entries),
                'Foreign, pending or uncertain item publication')
        paths[folder] = {x.name: x for x in entries}
    require(set(paths['items']) == set(paths['attempts']), 'Unmatched forward intent; generation fails closed')
    require(set(paths['items']) == set(list(wanted)[:len(paths['items'])]), 'Receipts not a fixed prefix')
    if complete:
        require(len(paths['items']) == 8, 'Incomplete eight-forward population')
    values = {}; generations = set()
    for filename, path in paths['items'].items():
        env = evidence.load(path)
        require(set(env) == {'payload', 'sha256'} and stamp(env['payload']) == env['sha256'], 'Receipt hash differs')
        v = env['payload']; ident = identity(p, ph, wanted[filename])
        require(all(type(v.get(k)) is type(x) and v.get(k) == x for k, x in ident.items()), 'Receipt identity differs')
        intent = evidence.load(paths['attempts'][filename])
        require(set(intent) == set(ident) | {'generation', 'phase', 'utc'}
                and all(type(intent.get(k)) is type(x) and intent.get(k) == x for k, x in ident.items())
                and intent['phase'] == 'forward_intent' and type(intent['utc']) is str and intent['utc'], 'Intent identity differs')
        require(v['attempt_sha256'] == evidence.sha(paths['attempts'][filename])
                and v['generation'] == intent['generation'], 'Attempt or generation binding differs')
        g = v['generation']
        require(set(g) == {'container_id', 'started_at', 'launch_receipt_sha256'}
                and all(type(x) is str and x for x in g.values()), 'Invalid Docker generation')
        generations.add(stamp(g))
        if generation is not None:
            require(g == generation, 'Resume Docker start generation differs')
        require(v['observed_input'] == {k:p['input'][k] for k in
                ('shape', 'ordered_id_row_hashes', 'ordered_mask_row_hashes')}, 'Input token/mask identity differs')
        require(v['core_calls'] == p['expected_core_names'], 'Native GDN call population/order differs')
        require(v['candidate_source_sha256'] == p['candidate_sources'][wanted[filename]['mode']], 'Candidate source differs')
        prediction_check(v['prediction'], p); check_metrics(v, p)
        values[filename] = v
    require(len(generations) <= 1, 'Mixed Docker start generations')
    evidence.verify()
    return values
