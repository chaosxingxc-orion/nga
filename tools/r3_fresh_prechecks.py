#!/usr/bin/env python3
"""Rebuild K0-dependent prechecks after a provenance-verified selection report.

CPU only; no training launch, test access or formal acceptance. A failed run is
retained and requires a fresh output directory for retry.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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


def run(a):
    report_path = Path(a.k0_report).resolve()
    require(report_path.name == 'selection_report.json' and report_path.is_file(), 'completed K0 report required')
    require(sha(a.report_tool) == a.report_tool_sha256, 'report tool pin differs')
    closure = Path(a.frozen_code_dir).resolve().parent
    require(sha(closure/'manifest.json') == a.closure_sha256, 'closure pin differs')
    R = load_module(a.report_tool, 'fresh_precheck_report')
    deps = R.modules(a.frozen_code_dir)
    C, E, D, PC, V = deps
    stored = R.load(report_path)
    validate_baseline(stored, a.model)
    # Full source/model/data/population validation; a historical argmax PASS
    # or a report claiming provenance is not an alternative to reconstruction.
    actual = R.rebuild(report_path.parent, a.kev_dir, a.data_root, deps)
    canonical = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)
    require(canonical(stored) == canonical(actual), 'K0 report differs from verified readouts')
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    receipt = report_path.parent/'SCORING_RECEIPT.track_kt.json'
    inputs = {str(report_path):sha(report_path), str(receipt):sha(receipt),
              str(closure/'manifest.json'):sha(closure/'manifest.json'),
              str(Path(a.report_tool).resolve()):sha(a.report_tool),
              str(Path(__file__).resolve()):sha(__file__)}
    inputs.update(actual['header']['data_files'])
    train, train_path = C.load_partition('decision-v7','train',kev_dir=a.kev_dir)
    parts, paths = {}, [train_path]
    for suite in C.SUITES:
        rows, path = C.load_partition(suite,'dev',kev_dir=a.kev_dir)
        variants, vp = C.load_partition(suite,'dev',variants=True,kev_dir=a.kev_dir)
        parts[suite+'/dev'] = rows; paths += [path,vp]
        PC.check_b(rows, variants, str(out), name='b_'+suite+'_dev')
        readouts = C.k_readout_path(str(report_path.parent),suite,'dev','clean')
        PC.check_c(readouts, run_dir=str(out), name='c_'+suite+'_k0_dev')
        inputs[readouts] = sha(readouts)
    PC.check_a(train,parts,str(out))
    PC.check_kev_manifest(paths,str(out),kev_dir=a.kev_dir)
    # This bundle deliberately does not stand in for train-code augmentation,
    # LoRA freeze, restart or exact-plan Astra checks.
    checks = {str(p):sha(p) for p in sorted((out/'prechecks').glob('*.json'))}
    require(len(checks) == 6 and all(R.load(p).get('ok') is True for p in checks), 'prechecks incomplete')
    for p, digest in inputs.items():
        require(sha(p) == digest, 'input changed during prechecks: '+p)
    result = {'schema':'r3-fresh-k0-prechecks-v1','status':'PASS','k0_report':str(report_path),
              'model':a.model,'inputs':inputs,'checks':checks,
              'scientific_acceptance':False,'test_read':False,
              'remaining_formal_requirements':['exact frozen train-code augmentation and LoRA checks',
                    'current restart/engineering gates','independent exact-plan Astra acceptance']}
    (out/'K0_PRECHECKS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'output':str(out/'K0_PRECHECKS.json'),'checks':len(checks),'formal_ready':False}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('k0-report','report-tool','report-tool-sha256','frozen-code-dir','closure-sha256','model','out'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--kev-dir',default='/mnt/cephfs/xingchao/experiments/jev/KEV')
    p.add_argument('--data-root',default='/mnt/cephfs/xingchao/experiments/jev')
    run(p.parse_args())


if __name__ == '__main__': main()
