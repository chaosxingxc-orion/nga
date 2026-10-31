#!/usr/bin/env python3
"""Freeze Track T scoring only; no model execution, selection or report-half metrics.

The existing scorer needs both held-out halves to validate the complete readout
population later. Raw report-half readouts must remain sealed from decisions.
This is deliberately a separate schema from the Track K execution contract.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
TASKS = {'T1': 'T1_level_names', 'T2': 'T2_definition_swap', 'T3': 'T3_question_set'}
SOURCES = ('typed-decisions', 'openjev-synth', 'akhilaaa3')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def regular(path):
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('missing regular dependency or symlink: ' + str(path))
    return path


def python_closure(entry, roots):
    pending, found = [entry], set()
    while pending:
        path = regular(pending.pop())
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for name in names:
                for root in roots:
                    candidate = root / (name.split('.')[0] + '.py')
                    if candidate.exists():
                        pending.append(candidate)
                        break
    return found


def builder_identity(path):
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n') or line == b'\n':
                raise ValueError('Track T task has malformed line framing')
            digest.update(line[:-1]); count += 1
    return {'sha256': digest.hexdigest(), 'records': count}


def prepare(out, base=BASE):
    base, out = Path(base).resolve(), Path(out).absolute()
    roots = [base / 'r3_code', base / 'r0_code']
    manifest_path = regular(base / 'manifest.json')
    manifest = json.loads(manifest_path.read_text())
    files = {str(manifest_path): sha(manifest_path)}
    task_files = []
    for task, directory in TASKS.items():
        for source in SOURCES if task != 'T3' else ('typed-decisions',):
            path = regular(base / directory / (source + '.jsonl'))
            digest = sha(path)
            expected = manifest['tasks'][directory][source]
            identity = builder_identity(path)
            if identity != {k: expected[k] for k in ('sha256', 'records')}:
                raise ValueError('Track T task differs from normative manifest: ' + str(path))
            files[str(path)] = digest
            task_files.append(str(path))
    code = python_closure(roots[0] / 'eval_r3.py', roots)
    # Include the actual selection consumer even if future scorer imports change.
    code |= python_closure(roots[0] / 'selection_evidence_r3.py', roots)
    out.mkdir(parents=True, exist_ok=False)
    mapping = {}
    for src in sorted(code):
        dst = out / src.relative_to(base)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        mapping[str(src)] = {'snapshot': str(dst), 'sha256': sha(dst)}
    command = ['python3', '-P', str(roots[0] / 'eval_r3.py'), '--full',
               '--model-path', '<FROZEN_BASE_MODEL>', '--adapter', '<COMPLETED_ADAPTER>',
               '--arm', '<TRAINING_ARM>', '--out', '<SEALED_READOUT_OUTPUT>',
               '--round-dir', '<FRESH_IDENTITY_CACHE>', '--partitions', 'dev,calibration',
               '--stages', 't_score', '--track-t-config', 'r3', '--data-root', str(base),
               '--track-t-sources', ','.join(SOURCES), '--shard', '0', '--num-shards', '1',
               '--scorer', 'rightpad', '--dtype', 'float32', '--no-hf32',
               '--token-budget', '16384', '--require-record-grade', '--device', 'npu:0']
    result = {'schema': 'r3-track-t-scoring-closure-v1', 'code': mapping, 'data': files,
              'task_files': task_files, 'command_template': command,
              'mounts': [{'source': str(out / r.name), 'destination': str(r), 'readonly': True} for r in roots],
              'candidate_test_read': False, 'scientific_acceptance': False, 'ready_to_score': False,
              'split_policy': {'config': 'r3', 'scored_population':
                  'unchanged records_needed: tau carve-out + group70 heldout + akhilaaa3 question70 heldout',
                  'report_half_raw_readouts_scored': True, 'report_half_metrics_computed': False,
                  'raw_readout_access': 'sealed evaluation storage; not an input to candidate decisions',
                  'selection_consumer': 'selection_evidence_r3.load_selection_report(require_track_t=True, report_half=False)',
                  'report_half_release': 'only after candidate selection is locked'},
              'pending': ['completed adapter and base-weight identity', 'guarded Track T execution adapter',
                          'selection-only header/report assembly with verified Track K evidence',
                          'exact-artifact independent review', 'actual NPU scoring']}
    path = out / 'manifest.json'
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return {'out': str(out), 'manifest_sha256': sha(path), 'task_files': len(task_files),
            'data_files': len(files), 'modules': len(mapping), 'ready_to_score': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--base', default=str(BASE))
    args = parser.parse_args()
    print(json.dumps(prepare(Path(args.out), Path(args.base))))
