#!/usr/bin/env python3
"""Rebuild K0-dependent prechecks after a provenance-verified selection report.

CPU only; no training launch, test access or formal acceptance. A failed run is
retained and requires a fresh output directory for retry.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path, name, expected_pin):
    # Read once, validate those bytes, compile those same bytes. SourceFileLoader
    # could execute a timestamp-valid untrusted .pyc even with writes disabled.
    raw = safe_path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_pin, 'report tool pin differs')
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ''
    exec(compile(raw, str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def validate_baseline(report, expected_model):
    h = report['header']
    require(report.get('schema') == 'r3-selection-report-v1' and
            report.get('scientific_acceptance') is False, 'selection report scope differs')
    require(h.get('arm') == 'K0' and h['model'].get('kind') == 'checkpoint', 'untuned K0 required')
    require(h['model']['path'] == expected_model, 'K0 model differs')
    require(set(h.get('partitions', [])) == {'dev', 'calibration'} and
            h.get('track_t_config') == 'r3', 'baseline partitions/config differ')
    require('seed' not in report['selection_evidence'], 'baseline impersonates training seed')


# Executable trust anchors are reviewed code constants, never supplied by a bundle.
# Changing a consumer/closure requires a new code review and bundle generation.
REPORT_TOOL_PINS = frozenset({'6e44272fefd6fdab21540c39fd84f105386e54cfe9fd9c01a38f41fb46c3cd78'})
CLOSURE_PINS = frozenset({'1c2f7d59dc365cbe52dcffe3fd9b734a8c09dc0612d35fe192703649710261df'})


def safe_path(value):
    p = Path(value)
    require(p.is_absolute() and str(p) == str(value) and '..' not in p.parts
            and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe provenance path')
    require(p.name not in ('test.jsonl', 'test.variants.jsonl') and not
            ('test' in p.parts and p.suffix in ('.jsonl', '.parquet')),
            'test dataset dependency forbidden')
    return p


def validate_inventory(files):
    """Reject the entire dependency set before hashing any member."""
    require(isinstance(files, dict), 'dependency inventory required')
    for filename in files:
        safe_path(filename)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def configuration(a):
    config = {k: str(getattr(a, k)) for k in
              ('report_tool', 'report_tool_sha256', 'frozen_code_dir',
               'closure_sha256', 'kev_dir', 'data_root')}
    config['generator'] = str(getattr(a, 'generator', Path(__file__).resolve()))
    require(sha(safe_path(config['generator'])) == sha(__file__),
            'precheck generator implementation differs')
    tool = safe_path(config['report_tool'])
    code = safe_path(config['frozen_code_dir'])
    require(config['report_tool_sha256'] in REPORT_TOOL_PINS
            and sha(tool) == config['report_tool_sha256'], 'untrusted report tool')
    require(config['closure_sha256'] in CLOSURE_PINS
            and sha(code.parent/'manifest.json') == config['closure_sha256'],
            'untrusted reconstruction closure')
    safe_path(config['kev_dir']); safe_path(config['data_root'])
    return config


def reconstruct(report_path, model, config):
    """Recompute provenance, complete dev populations, scores and all six checks.

    No result file is written. The pinned consumer checks model bytes, row stamps,
    producer manifests, data membership and splits before returning any metrics.
    """
    report_path = safe_path(report_path)
    R = load_module(config['report_tool'], 'fresh_precheck_report', config['report_tool_sha256'])
    deps = R.modules(config['frozen_code_dir'])
    C, E, D, PC, V = deps
    stored = R.load(report_path)
    validate_baseline(stored, model)
    # The frozen provenance verifier walks manifested readouts. Preflight their
    # paths and the declared data inventory before allowing it to read bytes.
    validate_inventory(stored['header'].get('data_files', {}))
    for subtree in ('trackk', 'trackt'):
        for file in (report_path.parent/subtree).rglob('*.jsonl'):
            safe_path(file)
    for file in safe_path(model).rglob('*'):
        if file.is_file():
            safe_path(file)
    actual = R.rebuild(report_path.parent, config['kev_dir'], config['data_root'], deps)
    require(canonical(stored) == canonical(actual), 'K0 report differs from verified readouts')
    run = report_path.parent
    files = {report_path, run/'SCORING_RECEIPT.track_kt.json',
             run/'EVAL_COMPLETE.track_kt.json', run/'RUN_IDENTITY.json',
             Path(config['report_tool']), Path(config['generator']),
             Path(config['frozen_code_dir']).parent/'manifest.json',
             Path(config['kev_dir'])/'manifest.json', Path(config['data_root'])/'manifest.json'}
    manifest = R.load(Path(config['frozen_code_dir']).parent/'manifest.json')
    files.update(Path(entry['snapshot']) for entry in manifest['code'].values())
    files.update(Path(x) for x in actual['header']['data_files'])
    for subtree, pattern in [('manifests', '*.json'), ('trackk', '*.jsonl'), ('trackt', '*.jsonl')]:
        files.update((run/subtree).rglob(pattern))
    files.update(p for p in safe_path(model).rglob('*') if p.is_file())
    train, train_path = C.load_partition('decision-v7', 'train', kev_dir=config['kev_dir'])
    parts, paths, checks = {}, [train_path], {}
    for suite in C.SUITES:
        rows, path = C.load_partition(suite, 'dev', kev_dir=config['kev_dir'])
        variants, vp = C.load_partition(suite, 'dev', variants=True, kev_dir=config['kev_dir'])
        parts[suite+'/dev'] = rows; paths += [path, vp]
        checks['b_'+suite+'_dev.json'] = PC.check_b(rows, variants)
        readouts = C.k_readout_path(str(run), suite, 'dev', 'clean')
        checks['c_'+suite+'_k0_dev.json'] = PC.check_c(readouts)
    checks['a_constant_uniform_gold_position.json'] = PC.check_a(train, parts)
    checks['d_kev_files_vs_manifest.json'] = PC.check_kev_manifest(paths, kev_dir=config['kev_dir'])
    files.update(Path(x) for x in paths)
    require(len(checks) == 6 and all(x.get('ok') is True for x in checks.values()), 'prechecks incomplete')
    validated = [safe_path(p) for p in sorted(files)]
    inventory = {str(p): sha(p) for p in validated}
    return inventory, checks


def validate_bundle(path, pin, model):
    path = safe_path(path)
    require(sha(path) == pin, 'precheck bundle pin differs')
    doc = json.loads(path.read_text())
    require(doc.get('schema') == 'r3-fresh-k0-prechecks-v2' and doc.get('status') == 'PASS'
            and doc.get('scientific_acceptance') is False and doc.get('test_read') is False
            and doc.get('model') == str(model), 'precheck bundle scope differs; regenerate v1 evidence')
    validate_inventory(doc.get('inputs'))
    validate_inventory(doc.get('checks'))
    config = configuration(SimpleNamespace(**doc['reconstruction']))
    require(doc.get('k0_report') in doc.get('inputs', {}), 'unbound K0 report')
    for filename, digest in {**doc['inputs'], **doc['checks']}.items():
        require(sha(safe_path(filename)) == digest, 'precheck dependency changed: '+filename)
    inputs, checks = reconstruct(doc['k0_report'], str(model), config)
    require(inputs == doc['inputs'], 'precheck provenance inventory differs')
    require({str(path.parent/'prechecks'/name) for name in checks} == set(doc['checks']),
            'precheck inventory differs')
    for name, actual in checks.items():
        stored = json.loads((path.parent/'prechecks'/name).read_text())
        require(canonical(stored) == canonical(actual), 'precheck content differs: '+name)
    for filename, digest in {**inputs, **doc['checks']}.items():
        require(sha(safe_path(filename)) == digest, 'input changed during reconstruction: '+filename)
    require(sha(path) == pin, 'precheck bundle changed during reconstruction')
    return doc


def run(a):
    report_path = safe_path(a.k0_report)
    require(report_path.name == 'selection_report.json' and report_path.is_file(), 'completed K0 report required')
    config = configuration(a)
    inputs, results = reconstruct(report_path, a.model, config)
    out = safe_path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'prechecks').mkdir()
    for name, result in results.items():
        (out/'prechecks'/name).write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    checks = {str(out/'prechecks'/name):sha(out/'prechecks'/name) for name in results}
    for filename, digest in inputs.items():
        require(sha(filename) == digest, 'input changed during prechecks: '+filename)
    result = {'schema':'r3-fresh-k0-prechecks-v2', 'status':'PASS', 'k0_report':str(report_path),
              'model':a.model, 'inputs':inputs, 'checks':checks, 'reconstruction':config,
              'scientific_acceptance':False, 'test_read':False,
              'remaining_formal_requirements':['exact frozen train-code augmentation and LoRA checks',
                    'current restart/engineering gates', 'independent exact-plan Astra acceptance']}
    (out/'K0_PRECHECKS.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'output':str(out/'K0_PRECHECKS.json'), 'checks':len(checks), 'formal_ready':False}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('k0-report','report-tool','report-tool-sha256','frozen-code-dir','closure-sha256','model','out'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--kev-dir',default='/mnt/cephfs/xingchao/experiments/jev/KEV')
    p.add_argument('--data-root',default='/mnt/cephfs/xingchao/experiments/jev')
    run(p.parse_args())


if __name__ == '__main__': main()
