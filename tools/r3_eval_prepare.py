#!/usr/bin/env python3
"""Freeze the installed modern evaluator and its local Python import closure.

Preparation is CPU-only. No model scoring, test data access or approval is implied.
Container mounts retain the evaluator's original absolute module paths.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
ROOTS = [BASE / 'r3_code', BASE / 'r0_code']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closure(entry):
    todo, found = [entry], set()
    while todo:
        path = todo.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            names = [x.name for x in node.names] if isinstance(node, ast.Import) else \
                    [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for name in names:
                for root in ROOTS:
                    candidate = root / (name.split('.')[0] + '.py')
                    if candidate.exists():
                        todo.append(candidate)
                        break
    return found


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    mapping = {}
    for src in sorted(closure(ROOTS[0] / 'eval_r3.py')):
        dst = out / src.relative_to(BASE)
        dst.parent.mkdir(exist_ok=True)
        shutil.copy2(src, dst)
        mapping[str(src)] = {'snapshot': str(dst), 'sha256': sha(dst)}
    data = [BASE / 'KEV/manifest.json', BASE / 'KEV/decision-v7/train.jsonl']
    for suite, split in [('decision-v7', 'dev'), ('decision-v7', 'calibration'), ('transfer-v4', 'dev')]:
        data.append(BASE / 'KEV' / suite / (split + '.jsonl'))
        if split == 'dev':
            data.append(BASE / 'KEV' / suite / (split + '.variants.jsonl'))
    files = {str(p): sha(p) for p in data}
    command = ['python3', '-P', str(ROOTS[0] / 'eval_r3.py'), '--full',
               '--model-path', '<FROZEN_BASE_MODEL>', '--adapter', '<COMPLETED_ADAPTER>',
               '--arm', 'K1', '--out', '<FRESH_EVAL_OUTPUT>', '--round-dir', '<FRESH_IDENTITY_CACHE>',
               '--partitions', 'dev,calibration', '--stages', 'k_score',
               '--k-only', 'decision-v7/dev/clean,decision-v7/calibration/clean,transfer-v4/dev/clean',
               '--scorer', 'rightpad', '--dtype', 'float32', '--no-hf32',
               '--token-budget', '16384', '--require-record-grade', '--device', 'npu:0']
    manifest = {'schema': 'r3-dev-evaluator-closure-v1', 'code': mapping, 'data': files,
                'command_template': command, 'test_read': False, 'scientific_acceptance': False,
                'scope': 'Track K clean dev/calibration readouts; full variants/Track T/report still separate',
                'mounts': [{'source': str(out / r.name), 'destination': str(r), 'readonly': True} for r in ROOTS],
                'pending': ['finished adapter identity', 'base weight hashes', 'exact executable launch plan',
                            'resource claim', 'independent review', 'full selection report']}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'out': str(out), 'modules': len(mapping), 'data_files': len(files),
                      'manifest_sha256': sha(out / 'manifest.json'), 'ready_to_score': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    prepare(Path(parser.parse_args().out))
