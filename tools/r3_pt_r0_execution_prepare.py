#!/usr/bin/env python3
"""Derive a fresh PT/R0 execution from an exact completed PT DEV specification.

CPU preparation only. Neither allocation nor producer/consumer services start.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import types


def require(ok, why):
    if not ok:
        raise ValueError(why)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(q.is_symlink() for q in (p, *p.parents)), 'unsafe path')
    return p


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(safe(path).read_bytes())


def pin(ref):
    require(set(ref) == {'path', 'sha256'}, 'pin shape differs')
    p = safe(ref['path'])
    require(sha(p) == ref['sha256'], 'input pin differs')
    return p


def module(path):
    m = types.ModuleType(Path(path).stem)
    m.__file__ = str(path)
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), m.__dict__)
    return m


def write(path, doc):
    with Path(path).open('x') as f:
        json.dump(doc, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')


def derive(source, closure, out, launcher):
    spec = copy.deepcopy(source)
    require(spec['training_variant']['arm'] == 'k1-pt' and
            type(spec['training_variant']['seed']) is int and
            spec['training_variant']['seed'] in (2, 3), 'PT identity required')
    require(closure['evaluation_profile'] == 'track_t_pt_r0' and
            closure['test_read'] is False and closure['scientific_acceptance'] is False,
            'R0 closure scope differs')
    keep = {spec['training'] + '/' + n for n in ('plan.json', 'manifest.json', 'TRAIN_EXIT.json')}
    keep.update(p for p in spec['files'] if p.startswith(spec['model'] + '/') or
                p.startswith(spec['adapter'] + '/'))
    require(keep <= set(spec['files']), 'training identity unbound')
    spec['files'] = {p: spec['files'][p] for p in keep}
    spec['files'].update(closure['data'])
    spec['files'].update({v['snapshot']: v['sha256'] for v in closure['code'].values()})
    spec.update(evaluation_profile='track_t_pt_r0', code_mounts=closure['mounts'],
                readonly_data_mounts=list(closure['data']),
                scope='PT R0-configuration readouts; separate B-4 CPU comparison required',
                execution_review='PENDING', chip_assignment='PENDING')
    spec['command'] = launcher.expected_command(spec, out)
    return spec


def verify(config, digest):
    require(sha(config) == digest, 'configuration changed')
    c = read(config)
    require(set(c) == {'schema', 'source_spec', 'closure', 'launcher', 'resource_adapter',
                      'root', 'chip', 'container'}, 'configuration fields differ')
    require(c['schema'] == 'r3-pt-r0-execution-prepare-v1', 'schema differs')
    refs = {k: pin(c[k]) for k in ('source_spec', 'closure', 'launcher', 'resource_adapter')}
    require(refs['launcher'].name == 'r3_posttrain_eval_launcher.py' and
            refs['resource_adapter'] == refs['launcher'].with_name('r3_resource_adapter.py'),
            'launcher siblings differ')
    L = module(refs['launcher'])
    source = read(refs['source_spec']); L.verify_spec(source, refs['source_spec'].parent)
    closure = read(refs['closure'])
    require(closure['schema'] == 'r3-pt-r0-closure-v1', 'closure schema differs')
    r0 = read(pin(closure['source_plan']))
    L.verify_spec(r0, Path(closure['source_plan']['path']).parent)
    expected = {v['snapshot']: v['sha256'] for v in closure['code'].values()}
    actual = {str(p): sha(p) for m in closure['mounts'] for p in safe(m['source']).rglob('*') if p.is_file()}
    require(actual == expected and closure['data'] ==
            {p: r0['files'][p] for p in r0['readonly_data_mounts']}, 'R0 closure inventory differs')
    for original, v in closure['code'].items():
        require(r0['files'].get(original) == v['sha256'] and sha(original) == v['sha256'],
                'R0 scientific source differs')
    out = safe(c['root'])
    require(out.is_relative_to(L.BASE / 'r3_runs') and out != L.BASE / 'r3_runs' and not out.exists(),
            'fresh output required')
    require(type(c['chip']) is int and 0 <= c['chip'] < 8, 'chip differs')
    require(c['container'].startswith('nga-r3-eng-eval-') and
            all(x.isalnum() or x in '-_' for x in c['container']), 'container differs')
    spec = derive(source, closure, out, L); L.verify_spec(spec, out)
    return c, refs, L, spec


def prepare(config, digest):
    c, refs, L, spec = verify(config, digest)
    out = Path(c['root']); out.mkdir()
    write(out / 'plan.json', spec)
    exe, h = L.bind(out / 'plan.json', c['chip'], c['container'])
    frozen = module(out / 'execution-tools/r3_posttrain_eval_launcher.py')
    frozen.verify(exe, h)
    write(out / 'QUEUE_EXECUTION_PIN.json', {'sha256': h})
    receipt = {'schema': 'r3-pt-r0-preparation-v1', 'configuration': {'path': str(config), 'sha256': digest},
               'source_spec': c['source_spec'], 'closure': c['closure'], 'plan_sha256': sha(out / 'plan.json'),
               'execution': {'path': str(exe), 'sha256': h}, 'training': spec['training'],
               'seed': spec['training_variant']['seed'], 'npu_started': False, 'cpu_started': False,
               'launch_authorized': False, 'scientific_acceptance': False, 'test_read': False,
               'status': 'PREPARED_PENDING_EXACT_REVIEW_RESOURCE_AND_CPU_CONSUMER'}
    write(out / 'PREPARATION.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('op', choices=('verify', 'prepare'))
    p.add_argument('--config', required=True, type=Path); p.add_argument('--sha256', required=True)
    a = p.parse_args()
    if a.op == 'verify':
        verify(a.config, a.sha256); print('PT_R0_PREPARATION_VERIFIED')
    else:
        print(json.dumps(prepare(a.config, a.sha256), indent=2))


if __name__ == '__main__':
    main()
