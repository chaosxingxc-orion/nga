#!/usr/bin/env python3
"""Freeze PT/R0 scoring code and task inputs from an exact pinned R0 plan.

CPU preparation only: no model weights, Kev test data, NPU, training eligibility,
FINAL or review are read or produced. Existing source plans remain untouched.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def launcher():
    path = Path(__file__).with_name('r3_posttrain_eval_launcher.py')
    spec = importlib.util.spec_from_file_location('pt_r0_launcher', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def require(ok, why):
    if not ok:
        raise ValueError(why)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts
            and not any(q.is_symlink() for q in (p, *p.parents)), 'unsafe absolute path')
    return p


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def prepare(source_plan, source_sha256, out):
    source_plan, out = safe(source_plan), safe(out)
    require(not out.exists(), 'fresh closure output required')
    require(sha(source_plan) == source_sha256, 'source plan pin differs')
    source = json.loads(source_plan.read_text())
    L = launcher()
    require(source.get('schema') == 'r3-baseline-dev-spec-v1'
            and source.get('evaluation_profile') == 'track_t_r0'
            and source.get('model') == L.R0_MODEL
            and source.get('image_sha256') == L.IMAGE
            and source.get('network') == 'none'
            and source.get('test_read') is False
            and source.get('scientific_acceptance') is False, 'source is not frozen R0 engineering scoring')
    require(source.get('command') == L.expected_command(source, source_plan.parent), 'source command differs')
    data_paths = source['readonly_data_mounts']
    require(len(data_paths) == len(set(data_paths))
            and set(data_paths) == L.allowed_data_files(source), 'source task inventory differs')
    data = {}
    for filename in data_paths:
        digest = sha(filename)
        require(source['files'].get(filename) == digest, 'source data changed')
        data[filename] = digest
    expected = {str(L.BASE / folder) for folder in ('r3_code', 'r0_code', 'r1_code')}
    mounts = source['code_mounts']
    require(len(mounts) == 3 and {m['destination'] for m in mounts} == expected, 'source code mount inventory differs')
    contents = {}
    for mount in mounts:
        require(mount.get('readonly') is True, 'source code mount writable')
        root = safe(mount['source'])
        require(root.is_dir() and not out.is_relative_to(root) and not root.is_relative_to(out),
                'source/output overlap')
        paths = list(root.rglob('*'))
        require(paths and not any(p.is_symlink() for p in paths), 'empty or symlink code tree')
        count = 0
        for path in paths:
            if not path.is_file():
                require(path.is_dir(), 'nonregular code dependency')
                continue
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            require(source['files'].get(str(path)) == digest, 'source code changed or unbound')
            rel = Path(mount['destination']).name / path.relative_to(root)
            require(str(rel) not in contents, 'duplicate code destination')
            contents[str(rel)] = (raw, digest, str(path))
            count += 1
        require(count > 0, 'empty code mount')
    # Validate before creating the new closure; byte copies are exactly the
    # verified input, and final manifest pins are independent of live originals.
    spec = {'schema': 'r3-posttrain-dev-spec-v1', 'evaluation_profile': 'track_t_pt_r0',
            'model': L.R0_MODEL, 'adapter': '<COMPLETED_ADAPTER>',
            'training_variant': {'arm': 'k1-pt', 'seed': 2}}
    command = L.expected_command(spec, Path('/PT_R0_TEMPLATE'))
    replacements = {L.R0_MODEL: '<FROZEN_BASE_MODEL>',
                    '/PT_R0_TEMPLATE/results': '<FRESH_EVAL_OUTPUT>',
                    '/PT_R0_TEMPLATE/identity': '<FRESH_IDENTITY_CACHE>'}
    command = [replacements.get(word, word) for word in command]
    out.mkdir(parents=True)
    code = {}
    for rel, (raw, digest, old_path) in sorted(contents.items()):
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        code[old_path] = {'snapshot': str(target), 'sha256': digest}
    doc = {'schema': 'r3-pt-r0-closure-v1', 'evaluation_profile': 'track_t_pt_r0',
           'source_plan': {'path': str(source_plan), 'sha256': source_sha256},
           'data': data, 'code': code,
           'mounts': [{'source': str(out / Path(m['destination']).name),
                       'destination': m['destination'], 'readonly': True} for m in mounts],
           'command_template': command, 'test_read': False, 'scientific_acceptance': False,
           'scope': 'K1-PT R0-configuration raw Track T readouts; B-4 requires separate verified CPU comparison'}
    target = out / 'manifest.json'
    target.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    return {'root': str(out), 'sha256': sha(target), 'files': len(code),
            'test_read': False, 'scientific_acceptance': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-plan', required=True, type=Path)
    p.add_argument('--source-sha256', required=True)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(prepare(a.source_plan, a.source_sha256, a.out)))
