#!/usr/bin/env python3
"""Prepare a formal DEV execution from a reviewed handoff; never launch it.

Only source-copy and output paths may change. The resulting execution still
needs an independent exact review and a successful predecessor guard.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import types

BASE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
TOOLS = ('r3_posttrain_eval_launcher.py', 'r3_resource_adapter.py',
         'r3_cpu_report_queue.py', 'r3_selection_report.py')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    return p


def pinned(ref):
    require(set(ref) == {'path', 'sha256'}, 'invalid pin')
    p = safe(ref['path'])
    require(sha(p) == ref['sha256'], 'changed input: ' + str(p))
    return p


def module(path):
    m = types.ModuleType(Path(path).stem)
    m.__file__ = str(path)
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), m.__dict__)
    return m


def write(path, doc):
    with Path(path).open('x') as f:
        json.dump(doc, f, indent=2, allow_nan=False)
        f.write('\n')


def inspect_config(path, pin):
    require(sha(safe(path)) == pin, 'config changed')
    c = read(path)
    require(set(c) == {'schema', 'prepared', 'spec', 'schedule', 'closure',
                      'cpu_template', 'tools', 'root', 'role', 'chip', 'container'},
            'unknown or missing configuration field')
    require(c['schema'] == 'r3-formal-dev-prepare-v1', 'unsupported schema')
    refs = {k: pinned(c[k]) for k in ('prepared', 'spec', 'schedule', 'closure', 'cpu_template')}
    require(set(c['tools']) == set(TOOLS), 'tool set differs')
    tool_paths = {n: pinned(c['tools'][n]) for n in TOOLS}
    receipt, spec, schedule = (read(refs[k]) for k in ('prepared', 'spec', 'schedule'))
    require(receipt['status'] == 'prepared' and receipt['role'] == c['role']
            and receipt['plan'] == str(refs['spec']) and receipt['sha256'] == c['spec']['sha256']
            and receipt['chip'] == c['chip'], 'handoff identity differs')
    require(receipt['evaluation_authorized'] is False and receipt['test_read'] is False
            and receipt['scientific_acceptance'] is False, 'handoff authority differs')
    role = spec['training_variant']['formal_role_identity']
    nodes = {n['id']: n for n in schedule['nodes']}
    targets = [n for n in schedule['nodes'] if n['kind'] == 'dev_calibration_track_t_readout'
               and n['training_id'] == c['role']]
    require(len(targets) == 1, 'formal DEV node differs')
    node = targets[0]
    require(type(c['chip']) is int and c['chip'] == role['chip'] == node['chip']
            and role['role'] == c['role'] and role['schedule_sha256'] == c['schedule']['sha256']
            and spec['training'] == nodes[c['role']]['out']
            and receipt['launch_dependencies'] == node['depends_on'], 'formal role/schedule differs')
    require(spec['test_read'] is False and spec['scientific_acceptance'] is False, 'scope differs')
    root = safe(c['root'])
    require(root.is_relative_to(BASE) and root != BASE and not root.exists(), 'fresh run root required')
    require(isinstance(c['container'], str) and c['container'].startswith('nga-r3-eng-eval-')
            and all(x.isalnum() or x in '-_' for x in c['container']), 'container differs')
    closure = refs['closure'].parent
    manifest = read(refs['closure'])
    require(spec['code_mounts'] == manifest['mounts'], 'producer closure mounts differ')
    for entry in manifest['code'].values():
        p = safe(entry['snapshot'])
        require(p.is_relative_to(closure) and sha(p) == entry['sha256']
                and spec['files'].get(str(p)) == entry['sha256'], 'source copy differs')
    for mount in manifest['mounts'] + spec['code_mounts']:
        require(safe(mount['source']).is_relative_to(closure) and mount['readonly'] is True,
                'code mount differs')
    for file, digest in spec['files'].items():
        require(sha(safe(file)) == digest, 'spec dependency differs')
    return c, refs, tool_paths, receipt, spec, manifest, node


def relocate_spec(spec, old, new, closure, clean, source_map):
    result = json.loads(json.dumps(spec))
    for mount in result['code_mounts']:
        mount['source'] = str(clean / Path(mount['source']).relative_to(closure))
    result['files'] = {source_map.get(p, p): h for p, h in spec['files'].items()}
    command = result['command']
    for option, leaf in (('--out', 'results'), ('--round-dir', 'identity')):
        require(command.count(option) == 1, 'output flag duplicated or missing')
        i = command.index(option) + 1
        require(command[i] == str(old / leaf), 'original output differs')
        command[i] = str(new / leaf)
    return result


def prepare(path, pin):
    c, refs, tools, receipt, spec, manifest, node = inspect_config(path, pin)
    root = Path(c['root']); root.mkdir()
    for directory in ('tools', 'cpu', 'evaluation', 'source-closure'):
        (root / directory).mkdir()
    clean = root / 'source-closure'; closure = refs['closure'].parent
    source_map = {}
    for entry in manifest['code'].values():
        source = Path(entry['snapshot']); dest = clean / source.relative_to(closure)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        require(sha(dest) == entry['sha256'], 'copied source differs')
        source_map[str(source)] = str(dest); entry['snapshot'] = str(dest)
    for mount in manifest['mounts']:
        mount['source'] = str(clean / Path(mount['source']).relative_to(closure))
    write(clean / 'manifest.json', manifest)
    derived = relocate_spec(spec, refs['spec'].parent, root / 'evaluation', closure, clean, source_map)
    write(root / 'evaluation/plan.json', derived)
    for name, source in tools.items():
        shutil.copyfile(source, root / 'tools' / name)
        require(sha(root / 'tools' / name) == c['tools'][name]['sha256'], 'copied tool differs')
    launcher = module(root / 'tools/r3_posttrain_eval_launcher.py')
    execution, execution_pin = launcher.bind(root / 'evaluation/plan.json', c['chip'], c['container'])
    module(root / 'evaluation/execution-tools/r3_posttrain_eval_launcher.py').verify(execution, execution_pin)
    queue = read(refs['cpu_template'])
    queue.update(closure=str(clean), closure_sha256=sha(clean / 'manifest.json'),
                 producer_closure={'path': str(clean), 'manifest_sha256': sha(clean / 'manifest.json')})
    for field, name in [('controller', 'r3_cpu_report_queue.py'), ('report_tool', 'r3_selection_report.py')]:
        queue[field] = str(root / 'tools' / name); queue[field + '_sha256'] = sha(queue[field])
    queue['jobs'] = [{'id': c['role'] + '-formal-dev', 'kind': 'report',
                      'eval_out': str(root / 'evaluation'),
                      'output': str(root / 'evaluation/results/selection_report.json'),
                      'plan': str(root / 'evaluation/plan.json'),
                      'plan_sha256': sha(root / 'evaluation/plan.json'),
                      'execution': str(execution), 'execution_sha256': execution_pin,
                      'terminal_gate': 'full_posttrain_v1'}]
    queue['event_wake_paths'] = [str(root / 'evaluation' / x) for x in
                               ('ENGINEERING_EVAL_EXIT.json', 'attempts/1/SUPERVISOR_DONE.json')]
    write(root / 'cpu/queue.json', queue)
    module(root / 'tools/r3_cpu_report_queue.py').verify(root / 'cpu/queue.json', sha(root / 'cpu/queue.json'))
    write(root / 'DERIVATION.json', {'schema': 'r3-formal-dev-relocation-v1',
          'configuration': {'path': str(Path(path).resolve()), 'sha256': pin},
          'original_spec': c['spec'], 'original_closure': c['closure'],
          'source_map': source_map, 'source_files_copied': len(source_map),
          'changes_only': ['readonly source copy paths', 'results and identity output paths'],
          'launch_dependencies': node['depends_on'], 'test_read': False,
          'scientific_acceptance': False, 'launch_authorized': False})
    facts = {'schema': 'r3-formal-dev-preparation-receipt-v1', 'role': c['role'],
             'chip': c['chip'], 'root': str(root), 'spec_sha256': sha(root / 'evaluation/plan.json'),
             'execution_sha256': execution_pin, 'cpu_queue_sha256': sha(root / 'cpu/queue.json'),
             'derivation_sha256': sha(root / 'DERIVATION.json'),
             'status': 'PREPARED_PENDING_EXACT_REVIEW_AND_PREDECESSOR_GUARD',
             'launch_dependencies': node['depends_on'], 'launch_authorized': False,
             'npu_started': False, 'cpu_started': False, 'test_read': False,
             'scientific_acceptance': False}
    write(root / 'PREPARATION.json', facts)
    return facts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('op', choices=('verify', 'prepare'))
    p.add_argument('--config', required=True); p.add_argument('--sha256', required=True)
    a = p.parse_args()
    if a.op == 'verify':
        inspect_config(a.config, a.sha256)
        print(json.dumps({'status': 'CONFIG_VERIFIED', 'launch_authorized': False}))
    else:
        print(json.dumps(prepare(a.config, a.sha256), indent=2))


if __name__ == '__main__':
    main()
