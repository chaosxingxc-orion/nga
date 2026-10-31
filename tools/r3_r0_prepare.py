#!/usr/bin/env python3
"""Prepare/validate a frozen full R0 gating pass; never launch or claim devices.

The legacy verifier uses absolute r0/r1 paths: execution MUST mount the pinned
snapshots at those paths. No legacy worker/launcher is included. The command
contract is an interface for a separately reviewed guarded execution adapter.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
MODEL = Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B')
REVISION = '2fc06364715b967f1860aea9cf38778875588b17'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
ROLES = ['primary', 'empty_input', 'question_only']
TASKS = {'T1_level_names': ['typed-decisions', 'openjev-synth', 'akhilaaa3'],
         'T2_definition_swap': ['typed-decisions', 'openjev-synth', 'akhilaaa3'],
         'T3_question_set': ['typed-decisions']}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def regular(path):
    require(path.is_file() and not any(x.is_symlink() for x in (path, *path.parents)), 'nonregular dependency: ' + str(path))
    return path


def sha(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with regular(Path(path)).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def closure(entries, roots):
    todo, found = list(entries), set()
    while todo:
        source = regular(todo.pop())
        if source in found:
            continue
        found.add(source)
        for node in ast.walk(ast.parse(source.read_text())):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for name in names:
                for root in roots:
                    candidate = root / (name.split('.')[0] + '.py')
                    if candidate.exists():
                        todo.append(candidate)
                        break
    return found


def commands(out, model, shards):
    common = ['python3', '-B', '-P', str(out / 'code/eval_r3.py'), '--full', '--model-path', str(model),
              '--arm', 'K0', '--out', str(out / 'instruct'), '--round-dir', str(out / 'round'),
              '--partitions', 'dev,calibration', '--track-t-config', 'r0', '--data-root', str(BASE),
              '--track-t-sources', 'typed-decisions,openjev-synth,akhilaaa3', '--scorer', 'rightpad',
              '--dtype', 'float32', '--no-hf32', '--token-budget', '16384', '--require-record-grade', '--device', 'npu:0']
    score = [common + ['--num-shards', str(shards), '--shard', str(i), '--stages', 't_score', '--unit-tag', f'R0_{i:02d}'] for i in range(shards)]
    return {'score': score, 'report': common + ['--num-shards', str(shards), '--shard', '0', '--stages', 'report'],
            'verify': ['python3', '-B', '-P', str(out / 'code/r0rescore_verify.py'), '--run', str(out)]}


def model_identity(model, hashes):
    revision = (model / '.complete').read_text().splitlines()[0]
    weights = {str(Path(p).relative_to(model)): h for p, h in hashes.items()
               if Path(p).suffix in ('.safetensors', '.bin', '.pt')
               and not any(x.startswith('.') for x in Path(p).relative_to(model).parts)}
    require(weights, 'no weights')
    payload = {'kind': 'checkpoint', 'weight_files': weights, 'revision': revision}
    return {'path': str(model), 'base_path': str(model), 'base_revision': revision,
            'kind': 'checkpoint', 'files': weights,
            'sha256': hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()}


def validate_contract(doc):
    require(doc['schema'] == 'r3-r0-gating-preparation-v1', 'schema differs')
    require(doc['model']['path'] == str(MODEL) and doc['model']['base_revision'] == REVISION, 'R0 instruct model differs')
    require(doc['image_sha256'] == IMAGE and doc['network'] == 'none', 'image/network differs')
    require(doc['roles'] == ROLES and doc['records_per_role'] == 102654, 'full R0 roles/population required')
    require(doc['track_t_config'] == 'r0' and doc['limit_groups'] == 0 and doc['limit'] == 0, 'R0 cannot be limited or reconfigured')
    require(doc['candidate_test_read'] is False and doc['scientific_acceptance'] is False and doc['ready_to_launch'] is False, 'scope differs')
    require(type(doc['num_shards']) is int and 1 <= doc['num_shards'] <= 64, 'invalid shards')
    require(doc['commands'] == commands(Path(doc['out']), MODEL, doc['num_shards']), 'command differs')
    require(doc['split_policy'] == {'tau': 'full group70 train fitting rows', 'evaluation': 'whole group70 heldout', 'halves': False, 'tie_rule': 'r0_published'}, 'split policy differs')


def validate(path, pin):
    path = Path(path)
    require(sha(path) == pin, 'manifest hash differs')
    doc = json.loads(path.read_text()); validate_contract(doc)
    require(Path(doc['out']) == path.parent, 'output differs')
    expected_data = {str(BASE / 'manifest.json')} | {str(BASE / directory / (source + '.jsonl')) for directory, sources in TASKS.items() for source in sources}
    require(set(doc['data']) == expected_data, 'data inventory differs')
    for p, digest in {**doc['files'], **doc['data'], **doc['model_files']}.items():
        require(sha(p) == digest, 'dependency changed: ' + p)
    for root in [path.parent / n for n in ('code', 'r0_code', 'r1_code')]:
        require({str(p) for p in root.rglob('*') if p.is_file()} == {p for p in doc['files'] if Path(p).is_relative_to(root)}, 'unbound code inventory')
    require({str(p) for p in MODEL.rglob('*') if p.is_file()} == set(doc['model_files']), 'model inventory differs')
    require(doc['model'] == model_identity(MODEL, doc['model_files']), 'model aggregate identity differs')
    require(set(doc['population_by_file']) == expected_data - {str(BASE / 'manifest.json')} and sum(doc['population_by_file'].values()) == 102654, 'population census differs')
    expected_mounts = [{'source': str(path.parent / name), 'destination': str(BASE / name), 'readonly': True} for name in ('r0_code', 'r1_code')]
    require(doc['required_code_mounts'] == expected_mounts, 'legacy verifier path mappings differ')
    return {'validated': True, 'manifest_sha256': pin, 'records_per_role': 102654, 'roles': ROLES, 'ready_to_launch': False}


def prepare(out, shards=32):
    out = Path(out).absolute()
    require(type(shards) is int and 1 <= shards <= 64, 'invalid shards')
    require(MODEL.joinpath('.complete').read_text().splitlines()[0] == REVISION, 'R0 model revision differs')
    normative = json.loads((BASE / 'manifest.json').read_text())
    data = {str(BASE / 'manifest.json'): sha(BASE / 'manifest.json')}
    for directory, sources in TASKS.items():
        for source in sources:
            p = regular(BASE / directory / (source + '.jsonl')); h = hashlib.sha256(); count = 0
            with p.open('rb') as f:
                for line in f:
                    require(line.endswith(b'\n') and line != b'\n', 'bad JSONL framing')
                    h.update(line[:-1]); count += 1
            entry = normative['tasks'][directory][source]
            require(h.hexdigest() == entry['sha256'] and count == entry['records'], 'builder identity differs: ' + str(p))
            data[str(p)] = sha(p)
    roots = [BASE / 'r3_code', BASE / 'r0_code', BASE / 'r1_code']
    code = closure([roots[0] / 'eval_r3.py', roots[0] / 'r0rescore_verify.py', roots[2] / 'convert_kev.py'], roots)
    out.mkdir(parents=True, exist_ok=False)
    files, sums = {}, []
    for src in sorted(code):
        folder = 'code' if src.parent == roots[0] else src.parent.name
        dst = out / folder / src.name; dst.parent.mkdir(exist_ok=True); shutil.copy2(src, dst)
        files[str(dst)] = sha(dst)
        sums.append(f"{sha(dst, 'sha1')}  {src.name if folder == 'code' else folder + '/' + src.name}\n")
    (out / 'SHA1SUMS').write_text(''.join(sums)); files[str(out / 'SHA1SUMS')] = sha(out / 'SHA1SUMS')
    model_files = {str(p): sha(p) for p in sorted(MODEL.rglob('*')) if p.is_file()}
    identity = model_identity(MODEL, model_files)
    # Run only the frozen pure-Python population logic; avoid core_r3's live
    # r0 search path and isolate this preparation process from module globals.
    program = '''import sys,json
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'code'));import core_r3
sys.path[:]=[str(root/'code'),str(root/'r0_code')]+[p for p in sys.path if p not in (core_r3.R0_CODE,str(root/'code'),str(root/'r0_code'))]
import track_t_r3 as T,common as C,prompt
paths=json.loads(sys.argv[2]);counts={};keys=[]
for p in paths:
 rows=T.records_needed(C.load_records(p),T.CONFIG_R0);counts[p]=len(rows);keys.extend(r['key'] for r in rows)
assert len(keys)==len(set(keys))==102654
print(json.dumps({'counts':counts,'prompt_version':prompt.PROMPT_VERSION}))
'''
    answer = subprocess.run([sys.executable, '-B', '-I', '-c', program, str(out), json.dumps([p for p in data if p != str(BASE / 'manifest.json')])], capture_output=True, text=True, check=True)
    population = json.loads(answer.stdout)
    (out / 'instruct').mkdir(); (out / 'round').mkdir()
    write(out / 'instruct/RUN_IDENTITY.json', {'model_sha256': identity['sha256'], 'model_path': str(MODEL), 'prompt_version': population['prompt_version'], 'track_t_config': 'r0', 'arm': 'K0'})
    files[str(out / 'instruct/RUN_IDENTITY.json')] = sha(out / 'instruct/RUN_IDENTITY.json')
    doc = {'schema': 'r3-r0-gating-preparation-v1', 'out': str(out), 'model': identity, 'model_files': model_files, 'files': files, 'data': data,
           'image_sha256': IMAGE, 'network': 'none', 'roles': ROLES, 'records_per_role': 102654, 'population_by_file': population['counts'],
           'num_shards': shards, 'track_t_config': 'r0', 'limit_groups': 0, 'limit': 0,
           'candidate_test_read': False, 'scientific_acceptance': False, 'ready_to_launch': False,
           'split_policy': {'tau': 'full group70 train fitting rows', 'evaluation': 'whole group70 heldout', 'halves': False, 'tie_rule': 'r0_published'},
           'commands': commands(out, MODEL, shards),
           'required_code_mounts': [{'source': str(out / n), 'destination': str(BASE / n), 'readonly': True} for n in ('r0_code', 'r1_code')],
           'pending': ['guarded retained-container execution adapter; no legacy in-container release', 'independent exact-plan review', 'real scoring, CPU report and legacy full verification', 'successful terminal before adoption']}
    write(out / 'PREPARATION.json', doc)
    pin = sha(out / 'PREPARATION.json'); (out / 'PREPARATION_SHA256').write_text(pin + '\n')
    return validate(out / 'PREPARATION.json', pin)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); sub = ap.add_subparsers(dest='op', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--out', required=True); p.add_argument('--shards', type=int, default=32)
    v = sub.add_parser('validate'); v.add_argument('--manifest', required=True); v.add_argument('--sha256', required=True)
    args = ap.parse_args()
    print(json.dumps(prepare(args.out, args.shards) if args.op == 'prepare' else validate(args.manifest, args.sha256)))
