#!/usr/bin/env python3
"""CPU-only full R0 report from pinned, provenance-verified instruct readouts.

No scoring, model loading, Kev test reads, candidate selection or formal PASS.
The legacy full verifier runs after report construction; success markers appear
only after all roles and source/code identities have been verified.
"""
import argparse
import copy
import fcntl
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROLES = ('primary', 'empty_input', 'question_only')
EXPECTED_COUNT = 102654


def require(ok, why):
    if not ok:
        raise ValueError(why)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path); temporary = path.with_suffix('.pending')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')
    temporary.replace(path)


def frozen_modules(preparation):
    root = Path(preparation['out'])
    roots = [root / name for name in ('code', 'r0_code', 'r1_code')]
    pinned = {Path(p).resolve() for p in preparation['files'] if Path(p).suffix == '.py'}
    names = {p.stem for p in pinned}
    require('torch' not in sys.modules, 'CPU report requires a clean process without torch')
    for name in names:
        if name in sys.modules:
            require(Path(sys.modules[name].__file__).resolve() in pinned, 'preloaded foreign module: ' + name)
    sys.path[:0] = [str(p) for p in roots]
    importlib.import_module('core_r3')
    # core_r3 inserts a historical live directory; remove it before importing
    # scientific modules, then verify the origin of every loaded local module.
    live = '/mnt/cephfs/xingchao/experiments/jev/'
    sys.path[:] = [str(p) for p in roots] + [p for p in sys.path if p not in {live + x for x in ('r0_code', 'r1_code', 'r3_code')} and p not in map(str, roots)]
    modules = {name: importlib.import_module(name) for name in ('core_r3', 'track_t_r3', 'selection_evidence_r3', 'provenance_r3', 'common', 'prompt', 'r0rescore_verify')}
    for name in names & sys.modules.keys():
        require(Path(sys.modules[name].__file__).resolve() in pinned, 'module escaped closure: ' + name)
    require('torch' not in sys.modules, 'CPU consumer unexpectedly imported torch')
    return modules


def check_header(receipt, preparation, deps):
    require(receipt.get('schema') == 'r3-scoring-receipt-v1' and receipt.get('scientific_acceptance') is False, 'producer receipt scope differs')
    h = receipt['header']; p = deps['prompt']; pv = deps['provenance_r3']
    require(h.get('stages') == 't_score' and h.get('track_t_config') == 'r0' and h.get('arm') == 'K0', 'full R0 scoring required')
    require(set(h.get('partitions', [])) == {'dev', 'calibration'}, 'candidate test forbidden')
    require(h.get('limit') == 0 and h.get('limit_groups') == 0 and not h.get('dry_run_warnings'), 'partial or diagnostic producer refused')
    require(h.get('primary_input_mode') == 'full' and h.get('render') == 'record_name', 'input/render differs')
    require(h.get('dtype') == 'float32' and not pv._scorer_problems(h.get('scorer')), 'scorer not of record')
    require(h.get('prompt_version') == p.PROMPT_VERSION and h.get('prompt_format') == p.PROMPT_FORMAT, 'prompt differs')
    require(set(h.get('track_t_sources', '').split(',')) == {'typed-decisions', 'openjev-synth', 'akhilaaa3'}, 'sources differ')
    identity = preparation['model']
    require(h.get('model') == {k: identity[k] for k in ('path', 'sha256', 'kind', 'base_path', 'base_revision')}, 'producer model differs from freshly verified weights')
    expected_data = {k: v for k, v in preparation['data'].items() if Path(k).name != 'manifest.json'}
    require(h.get('data_files') == expected_data, 'producer data differs')
    return h


def verify_execution(run, pin, preparation):
    """Bind CPU evidence to a caller-pinned execution and its guarded release."""
    path = run / 'execution.json'
    require(sha(path) == pin, 'execution pin differs')
    execution = load(path)
    require(execution.get('schema') == 'r3-engineering-posttrain-execution-v1'
            and execution.get('out') == str(run)
            and execution.get('scientific_acceptance') is False
            and execution.get('test_read') is False, 'execution scope differs')
    require(sha(execution['spec']) == execution['spec_sha256'], 'execution specification differs')
    spec = load(execution['spec'])
    require(spec.get('evaluation_profile') == 'track_t_r0' and spec.get('model') == preparation['model']['path'], 'not R0 execution')
    require(spec.get('image_sha256') == preparation['image_sha256'], 'image differs')
    for filename, digest in {**execution['tools'], **spec['files']}.items():
        p = Path(filename)
        require(not any(x.is_symlink() for x in (p, *p.parents)) and sha(p) == digest, 'execution dependency differs: ' + filename)
    for filename, digest in {**preparation['data'], **preparation['model_files']}.items():
        require(spec['files'].get(filename) == digest, 'producer dependency not bound: ' + filename)
    # Every scientific source must be the one actually mounted for scoring,
    # not merely an unused good copy next to a different execution closure.
    mounts = {m['destination']: m for m in spec['code_mounts']}
    base = '/mnt/cephfs/xingchao/experiments/jev/'
    for name in ('code', 'r0_code', 'r1_code'):
        destination = base + ('r3_code' if name == 'code' else name)
        require(destination in mounts and mounts[destination].get('readonly') is True, 'scientific code mount missing')
        root = Path(mounts[destination]['source'])
        for filename, digest in preparation['files'].items():
            rel = Path(filename).relative_to(preparation['out'])
            if rel.parts[0] == name:
                require(spec['files'].get(str(root / Path(*rel.parts[1:]))) == digest, 'producer scientific code differs')
    terminal = load(run / 'ENGINEERING_EVAL_EXIT.json')
    require(type(terminal.get('exit_code')) is int and terminal['exit_code'] == 0, 'scoring execution incomplete')
    number = terminal['attempt']; require(type(number) is int and number > 0, 'invalid attempt')
    attempt = run / 'attempts' / str(number)
    require(load(attempt / 'EXIT.json') == terminal, 'attempt terminal differs')
    release = load(attempt / 'RELEASE.json')
    require(type(release.get('exit_code')) is int and release['exit_code'] == 0
            and release.get('container_id') == load(attempt / 'LAUNCH_RECEIPT.json')['id']
            and release.get('chip') == execution['chip'] and release.get('run') == execution['run'], 'scoring release evidence differs')
    return execution


def rebuild(run, preparation, deps):
    run = Path(run); out = run / 'instruct'
    C, T, E, PV, RC = (deps[x] for x in ('core_r3', 'track_t_r3', 'selection_evidence_r3', 'provenance_r3', 'common'))
    receipt = load(out / 'SCORING_RECEIPT.track_t_r0.json')
    h = check_header(receipt, preparation, deps)
    identity = load(out / 'RUN_IDENTITY.json')
    require(identity.get('arm') == 'K0' and identity.get('track_t_config') == 'r0' and identity.get('prompt_version') == h['prompt_version'] and identity.get('model_path') == h['model']['path'], 'run identity differs')
    readouts = out / 'trackt/readouts'
    provenance = PV.verify(str(out), str(readouts), preparation['model']['sha256'])
    require(all(x['scorer'] == h['scorer'] for x in provenance['manifests'].values()), 'producer scorer descriptors differ')
    records = []
    # Preserve the evaluator's task/source traversal as well as its exact
    # population; do not let sorted manifest keys reorder threshold inputs.
    for task in ('T1', 'T2', 'T3'):
        for source in RC.SOURCE_FILES:
            if task == 'T3' and source != 'typed-decisions':
                continue
            filename = RC.task_path(str(Path(next(p for p in preparation['data'] if Path(p).name == 'manifest.json')).parent), task, source)
            require(filename in preparation['data'], 'missing required task input')
            records.extend(RC.load_records(filename))
    needed = T.records_needed(records, T.CONFIG_R0)
    require(len(needed) == EXPECTED_COUNT and len({r['key'] for r in needed}) == EXPECTED_COUNT, 'full R0 population differs')
    by_role = {role: [] for role in ROLES}
    for path in sorted(readouts.glob('*.jsonl')):
        role = path.name.split('__')[0]
        require(role in by_role, 'unexpected readout role')
        by_role[role].extend(C.read_jsonl(str(path)))
    counts = {}
    for role in ROLES:
        ordered = E.validate_population(by_role[role], needed, lambda r: r['key'])
        counts[role] = len(ordered)
        by_role[role] = [T.make_readout(row, saved['s']) for row, saved in zip(needed, ordered)]
    by_role.update(T.constant_and_uniform_rows(records, needed))
    block = T.build_track_t(by_role, records, T.CONFIG_R0)
    require(block.get('config') == 'r0' and not block.get('missing_roles'), 'R0 report incomplete')
    lines = block['decision_lines']['all']['B-2']
    statuses = {x['level_type']: x['status'] for x in lines if x['source'] == 'typed-decisions'}
    require(set(statuses) == {'boolean', 'nominal', 'ordinal'}, 'R0 gating population incomplete')
    report = {'header': copy.deepcopy(h), 'track_t': block, 'scientific_acceptance': False,
              'cpu_rebuild': {'producer_receipt_sha256': sha(out / 'SCORING_RECEIPT.track_t_r0.json'), 'per_role': counts,
                              'provenance': provenance, 'scope': 'full R0 gating evidence; no candidate acceptance or test read'}}
    return report, statuses


def verify_code_record(run, preparation):
    spec = load(run / 'plan.json')
    record = run / 'SHA1SUMS'
    require(spec['files'].get(str(record)) == sha(record), 'unbound executed code record')
    entries = {}
    for line in record.read_text().splitlines():
        digest, name = line.split(None, 1); name = name.strip()
        require(name not in entries and not Path(name).is_absolute() and '..' not in Path(name).parts,
                'unsafe or duplicate code record')
        entries[name] = digest
        path = run / name if name.startswith(('r0_code/', 'r1_code/')) else run / 'code' / name
        require(spec['files'].get(str(path)) == sha(path), 'code record source not bound')
        require(hashlib.sha1(path.read_bytes()).hexdigest() == digest, 'code record digest differs')
    for filename in preparation['files']:
        rel = Path(filename).relative_to(preparation['out'])
        if rel.parts[0] in ('code', 'r0_code', 'r1_code'):
            name = str(Path(*rel.parts[1:])) if rel.parts[0] == 'code' else str(rel)
            require(name in entries, 'scientific source absent from code record')


def execute(a):
    run = Path(a.run).resolve(); preparation_path = Path(a.preparation).resolve()
    helper = Path(__file__).with_name('r3_r0_prepare.py')
    spec = importlib.util.spec_from_file_location('r0_preparation', helper); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
    P.validate(preparation_path, a.sha256); preparation = load(preparation_path)
    with (run / 'r0_report.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not any((run / p).exists() for p in ('R0RESCORE_COMPLETE.json', 'R0RESCORE_VERIFIED.json', 'instruct/report.json')), 'report/terminal exists; inspect before retry')
        verify_execution(run, a.execution_sha256, preparation)
        require(load(run / 'instruct/EVAL_COMPLETE.track_t_r0.json').get('exit_code') == 0, 'producer terminal failed')
        # Exported code record must have been present before execution and is
        # independently compared with the pinned preparation here.
        verify_code_record(run, preparation)
        for filename, digest in preparation['files'].items():
            rel = Path(filename).relative_to(preparation_path.parent)
            if rel.parts[0] in ('code', 'r0_code', 'r1_code'):
                require(sha(run / rel) == digest, 'execution snapshot differs: ' + str(rel))
        deps = frozen_modules(preparation)
        report, statuses = rebuild(run, preparation, deps)
        save(run / 'instruct/report.json', report)
        checked = deps['r0rescore_verify'].check(str(run))
        require(not checked['problems'] and checked['records_needed_R0'] == EXPECTED_COUNT, 'legacy full verifier refused: ' + str(checked['problems']))
        P.validate(preparation_path, a.sha256)
        checked['cpu_report_sha256'] = sha(run / 'instruct/report.json'); checked['statuses'] = statuses
        save(run / 'R0RESCORE_VERIFIED.json', checked)
        complete = {'exit_code': 0, 'run_of_record': True, 'limit_groups': 0, 'utc': deps['core_r3'].utc_now(),
                    'verified': str(run / 'R0RESCORE_VERIFIED.json'), 'verified_sha256': sha(run / 'R0RESCORE_VERIFIED.json'),
                    'report_sha256': checked['cpu_report_sha256'], 'preparation_sha256': a.sha256,
                    'execution_sha256': a.execution_sha256,
                    'scientific_acceptance': False, 'candidate_test_read': False}
        save(run / 'R0RESCORE_COMPLETE.json', complete)
        print(json.dumps({'output': str(run / 'R0RESCORE_COMPLETE.json'), 'statuses': statuses, 'scientific_acceptance': False}))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', required=True); ap.add_argument('--preparation', required=True); ap.add_argument('--sha256', required=True)
    ap.add_argument('--execution-sha256', required=True)
    a = ap.parse_args(); marker = Path(a.run) / 'R0REPORT_EXIT.json'
    invocation_lock = (Path(a.run) / 'r0_report_invocation.lock').open('a')
    fcntl.flock(invocation_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    require(not marker.exists(), 'prior CPU report terminal exists; explicit repair required')
    result = {'exit_code': 1, 'scientific_acceptance': False, 'candidate_test_read': False}
    try:
        execute(a)
        result['exit_code'] = 0
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)[:500]
        raise
    finally:
        result['utc_seconds'] = time.time()
        save(marker, result)


if __name__ == '__main__':
    main()
