#!/usr/bin/env python3
"""Strict dataset and model bindings for the E24 original-test supplement."""
from collections import Counter
import hashlib
import json
from pathlib import Path

FULL_SHA = 'fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b'
PUBLIC_SHA = '0c4b953282a4292272110536ca543fe6e2736ab729b81d9b0464dd8ab4eec86a'
SUPPLEMENT_SHA = 'e1d5bbf9212fff1fba6b3e26df5afd34c55bbe9d83fdc3464446d6da23a0a83d'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def tree_signature(config, key):
    root = Path(config[key]).resolve()
    paths = sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    require(paths, 'Empty ' + key + ' dependency tree')
    result = {}
    for path in paths:
        absolute = str(path.resolve())
        require(absolute in config['files'], 'Model dependency not frozen: ' + absolute)
        require(sha(path) == config['files'][absolute], 'Model dependency changed: ' + absolute)
        result[str(path.relative_to(root))] = config['files'][absolute]
    return result


def model_signature(config):
    return {**{k: config[k] for k in ('image', 'base_id', 'base_revision', 'max_length', 'temperature')},
            **{k: tree_signature(config, k) for k in ('base', 'checkpoint', 'code')}}


def validate_partition(full, public, supplement, positions):
    require(len({r['id'] for r in full}) == len(full), 'Duplicate original IDs')
    require(len({r['id'] for r in public}) == len(public), 'Duplicate public IDs')
    require(len({r['id'] for r in supplement}) == len(supplement), 'Duplicate supplement IDs')
    require(positions == sorted(set(positions)) and all(type(p) is int and 1 <= p <= len(full) for p in positions),
            'Invalid original positions')
    excluded = set(positions)
    require([r for i,r in enumerate(full,1) if i not in excluded] == public, 'Public projection changed')
    require([r for i,r in enumerate(full,1) if i in excluded] == supplement, 'Supplement content/order changed')
    require(len(full) == len(public) + len(supplement), 'Partition denominator mismatch')


def validate_dataset(config, rows):
    """Validate supplement without calling the inference driver or its metrics."""
    parent_path = Path(config['parent_config'])
    require(sha(parent_path) == config['parent_config_sha256'], 'Parent config changed')
    parent = load(parent_path)
    for key in ('parent_config', 'original_data', 'restoration_report'):
        path = str(Path(config[key]).resolve())
        require(config['files'].get(path) == sha(path), 'Unfrozen supplementary dependency: ' + key)
    require(sha(config['original_data']) == FULL_SHA, 'Original full test hash mismatch')
    require(sha(parent['data']) == PUBLIC_SHA, 'Public projection hash mismatch')
    require(sha(config['data']) == SUPPLEMENT_SHA, 'Supplement hash mismatch')
    full = [json.loads(line) for line in Path(config['original_data']).read_text().splitlines()]
    public = [json.loads(line) for line in Path(parent['data']).read_text().splitlines()]
    restored = load(config['restoration_report'])
    manifest = restored['missing_public_rows']['test']
    require(restored['status'] == 'RESTORED_EXACT_ORIGINAL', 'Restoration did not succeed')
    require(restored['splits']['test'] == {'count': 10532, 'sha256': FULL_SHA}, 'Original manifest mismatch')
    require(manifest['count'] == 176 and manifest['sha256'] == SUPPLEMENT_SHA, 'Supplement manifest mismatch')
    require(manifest['original_line_numbers'] == list(range(1465, 1641)), 'Original positions mismatch')
    require(manifest['ids'] == [r['id'] for r in rows], 'Restored ID order mismatch')
    validate_partition(full, public, rows, manifest['original_line_numbers'])
    require(len(full) == 10532 and len(public) == 10356 and len(rows) == config['expected_rows'] == 176,
            'Fixed denominators mismatch')
    require(sum(max(r['target']) == 1 for r in full) == 10046 and
            sum(max(r['target']) == 1 for r in rows) == config['hard_count'] == 51, 'Hard counts mismatch')
    require(all(r['split'] == 'test' for r in full), 'Non-test record')
    require(model_signature(config) == model_signature(parent), 'Parent/supplement model protocol differs')
    model = load(Path(config['checkpoint']) / 'model.json')
    require((model['model_id'], model['revision'], model['max_length']) ==
            (config['base_id'], config['base_revision'], config['max_length']), 'Checkpoint protocol differs')
    require(config['max_length'] == 4096, 'Native length changed')
    return {'count': len(rows), 'raw_uncompressed_sha256': SUPPLEMENT_SHA,
            'sources': dict(Counter(r['source'] for r in rows)), 'kinds': dict(Counter(r['kind'] for r in rows))}
