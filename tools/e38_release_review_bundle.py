#!/usr/bin/env python3
"""Build a self-contained CPU-only E38 release review snapshot; never launch jobs.

Run with python3 -B -P. Source files are copied before tests, and compared byte for
byte afterwards. Review creation is separate from any release authorization.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

SUITES = ('test_e38_evidence', 'test_e38_astra_v4_regressions',
          'test_release_openjev_path_trace', 'test_e38_release_review_runner')
PLAN_HASHES = {'2': '2a859fe2ba77ac431e2e5c62408c964bb15a5794e07c8981be625bf626a0e66d',
               '9': 'fae8ac8368b7a98fad32e07acc1b54b1dded55c1812f95ec4cdb136b92ef3593'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Not a regular input: ' + str(path))
    if path.stat().st_size > 32 * 2**20:
        raise ValueError('Oversized review input: ' + str(path))
    return path.read_bytes()


def write_json(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())


def inventory(root):
    result = []
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Symlink in review bundle: ' + str(p))
        if p.is_file():
            raw = read_regular(p)
            result.append(dict(path=str(p.relative_to(root)), size=len(raw), sha256=sha(raw)))
    return result


def test_module(folder, name):
    spec = importlib.util.spec_from_file_location(name, folder / (name + '.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def tests(folder):
    ids = []
    def visit(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite): visit(item)
            else: ids.append(item.id())
    for name in SUITES:
        visit(unittest.defaultTestLoader.loadTestsFromModule(test_module(folder, name)))
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError('Duplicate or empty test population')
    return sorted(ids)


def one_test(folder, test_id):
    name, cls, method = test_id.split('.')
    if name not in SUITES:
        raise ValueError('Unregistered CPU suite')
    mod = test_module(folder, name)
    suite = unittest.defaultTestLoader.loadTestsFromName(cls + '.' + method, mod)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.testsRun == 1 and result.wasSuccessful() and not result.skipped else 1


def build(repo, evidence_root, out, extra):
    out.mkdir(parents=False, exist_ok=False)
    current = out / 'current'; current.mkdir()
    sources = []
    def copy(src, relative):
        raw = read_regular(src); dest = out / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as f: f.write(raw)
        sources.append(dict(source=str(src), path=str(relative), sha256=sha(raw), size=len(raw)))
    # Complete local tool/fixture closure: copied, not recursively imported or executed.
    for src in sorted((repo / 'tools').rglob('*')):
        if src.is_file() and '__pycache__' not in src.parts and src.suffix in ('.py', '.json'):
            copy(src, Path('current') / src.relative_to(repo / 'tools'))
    # CPUWorkflow resolves its real preregistration relative to the copied
    # tools directory. Preserve that layout rather than substituting a fixture
    # or depending on the checkout being available outside the bundle.
    prereg = Path('experiments/OPENJEV-PATH-TRACE-E38-2026-10-31.md')
    copy(repo / prereg, prereg)
    for relative in ['experiments/OPENJEV-PATH-TRACE-E38-RELEASE-2026-10-31.md',
                     'wiki/E38-openjev-path-trace-20261031.md']:
        copy(repo / relative, Path('protocol') / Path(relative).name)
    for size in PLAN_HASHES:
        root = evidence_root / ('openjev_path_trace_openjev' + size + '_20261031_v7')
        if sha(read_regular(root / 'plan.json')) != PLAN_HASHES[size]:
            raise ValueError('Wrong frozen v7 plan')
        for src in sorted(root.rglob('*')):
            if src.is_file() and '__pycache__' not in src.parts and (src.suffix in ('.py', '.json', '.sh', '.md') or src.name == 'EXIT'):
                copy(src, Path('evidence') / root.name / src.relative_to(root))
    root = evidence_root / 'e38_openjev2_verify_20261031_v8'
    for src in sorted(root.rglob('*')):
        if src.is_file() and '__pycache__' not in src.parts and (src.suffix in ('.py', '.json', '.sh', '.md') or src.name == 'EXIT'):
            copy(src, Path('evidence') / root.name / src.relative_to(root))
    review = evidence_root / 'astra_reviews/e38_release_astra_20261031_v2'
    for name in ('review.md', 'PROCESS.json', 'digest.json', 'runner.py'):
        copy(review / name, Path('prior_review_v2') / name)
    for i, src in enumerate(extra):
        copy(src, Path('additional_evidence') / (str(i) + '-' + src.name))
    write_json(out / 'SOURCE_MAP.json', sources)
    source_before = inventory(current)
    test_out = out / 'cpu_tests'; test_out.mkdir()
    driver = current / Path(__file__).name
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    # Modules are explicitly loaded from the trusted copied code; cwd is /tmp.
    listing = subprocess.run([sys.executable, '-B', '-P', str(driver), '--list-tests', str(current)],
                             cwd='/tmp', env=env, capture_output=True, text=True, timeout=60, check=True)
    ids = json.loads(listing.stdout); records = []
    for i, test_id in enumerate(ids):
        started = time.time(); log = test_out / (str(i).zfill(4) + '.txt')
        with log.open('xb') as f:
            proc = subprocess.run([sys.executable, '-B', '-P', str(driver), '--one-test', str(current), test_id],
                                  cwd='/tmp', env=env, stdout=f, stderr=subprocess.STDOUT, timeout=60)
        records.append(dict(id=test_id, rc=proc.returncode, seconds=time.time()-started,
                            log=str(log.relative_to(out)), log_sha256=sha(log.read_bytes())))
    if inventory(current) != source_before:
        raise ValueError('Test execution changed copied sources')
    write_json(test_out / 'report.json', dict(tests=len(ids), passed=sum(r['rc']==0 for r in records),
               all_passed=all(r['rc']==0 for r in records), records=records))
    if not all(r['rc']==0 for r in records):
        raise ValueError('CPU regression failed; retain incomplete generation')
    write_json(out / 'SCOPE.json', dict(scope='release-tool only; no resource authorization',
        v7_plan_hashes=PLAN_HASHES, sources_unchanged=True,
        prior_review='v2 substantive BLOCK text retained; no child/runner exit reconstructed',
        omissions='External weights, raw logs and noncopied dependencies are not revalidated. '
                  'This bundle does not contain a fresh live Docker observation unless supplied as additional evidence.'))
    for entry in sources:
        if sha(read_regular(Path(entry['source']))) != entry['sha256']:
            raise ValueError('Source changed during bundle preparation: ' + entry['source'])
    entries = inventory(out)
    write_json(out / 'MANIFEST.json', dict(schema='e38-release-review-bundle-v3', files=entries))
    return dict(bundle=str(out), manifest_sha256=sha((out/'MANIFEST.json').read_bytes()), tests=len(ids))


def main():
    p=argparse.ArgumentParser(); p.add_argument('--repo',type=Path); p.add_argument('--evidence-root',type=Path)
    p.add_argument('--out',type=Path); p.add_argument('--extra',type=Path,action='append',default=[])
    p.add_argument('--list-tests',type=Path); p.add_argument('--one-test',nargs=2)
    a=p.parse_args()
    if a.list_tests: print(json.dumps(tests(a.list_tests))); return
    if a.one_test: raise SystemExit(one_test(Path(a.one_test[0]),a.one_test[1]))
    if not all((a.repo,a.evidence_root,a.out)): p.error('build needs --repo --evidence-root --out')
    print(json.dumps(build(a.repo.resolve(),a.evidence_root.resolve(),a.out.absolute(),a.extra),indent=2))

if __name__=='__main__': main()
