#!/usr/bin/env python3
"""Build a pinned QO/PT training-evidence pack from retained CPU artifacts.

This is preparation only: it never reads test data, starts Docker, or grants
scientific/formal acceptance. The final validator is run before the pack is
published.
"""
import argparse, hashlib, importlib.util, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
TRAIN = Path('/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl')
CODE_NAMES = ('train_r3.py', 'build_kev_sft.py', 'kev_aug.py')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def require(ok, why):
    if not ok:
        raise ValueError(why)


def load(path):
    return json.loads(Path(path).read_text())


def add(files, path, digest=None):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), 'missing evidence dependency: '+str(path))
    files[str(path)] = digest or sha(path)


def module():
    path = ROOT / 'tools/r3_training_evidence.py'
    spec = importlib.util.spec_from_file_location('r3_training_evidence', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def build(arm, lora_root, augmentation, control_contract, model, out):
    require(arm in ('K1-QO', 'K1-PT'), 'unsupported control arm')
    lora_root, augmentation, control_contract, model, out = map(Path, (lora_root, augmentation, control_contract, model, out))
    require(model.is_dir() and TRAIN.is_file(), 'model/train path missing')
    require(not out.exists(), 'output already exists; use a new evidence generation')
    out.mkdir(parents=True)
    code_root = lora_root / 'code'
    prompt = code_root / 'r0_code/prompt.py'
    code = {name: code_root / name for name in CODE_NAMES}
    require(all(p.is_file() for p in (*code.values(), prompt)), 'CPU code closure incomplete')

    # Normalize the CPU verification record into absolute, immutable paths.
    raw = load(lora_root / 'VERIFICATION.json')
    if arm == 'K1-QO':
        lv = dict(image=raw['image'], exit_code=raw['exit_code'], state=raw['state'],
                  npu_devices=raw['npu_devices'], model_mount_readonly=raw['model_mount_readonly'],
                  digest_sha256=raw['digest_sha256'], terminal_sha256=raw['terminal_sha256'],
                  code=dict(raw['code']), model_hashes_after_run=dict(raw['model_hashes_after_run']))
    else:
        rawd = raw['digest']
        lv = dict(image=raw['image'], exit_code=raw['exit_code'], state=raw['state'],
                  npu_devices=raw['devices'], model_mount_readonly=raw['model_readonly'],
                  digest_sha256=sha(lora_root/'results/digest.json'),
                  terminal_sha256=sha(lora_root/'results/EXIT.json'),
                  code=dict(rawd['code_sha256']), model_hashes_after_run=load(lora_root/'POSTRUN_MODEL_VERIFICATION.json')['model_hashes'])
        lv['code']['prompt.py'] = sha(prompt)

    lora = out / 'lora'; results = lora / 'results'; results.mkdir(parents=True)
    shutil.copy2(lora_root/'results/digest.json', results/'digest.json')
    shutil.copy2(lora_root/'results/EXIT.json', results/'EXIT.json')
    lv['digest_sha256'] = sha(results/'digest.json'); lv['terminal_sha256'] = sha(results/'EXIT.json')
    absolute_code = {}
    for name, digest in lv['code'].items():
        absolute_code[str(prompt if Path(name).name == 'prompt.py' else code_root / Path(name).name)] = digest
    lv['code'] = absolute_code
    verification = lora / 'VERIFICATION.json'; verification.write_text(json.dumps(lv, indent=2, sort_keys=True)+'\n')

    files = {}
    for p in (*code.values(), prompt, TRAIN, augmentation, control_contract, verification, results/'digest.json', results/'EXIT.json'):
        add(files, p)
    for p, digest in lv['code'].items(): add(files, p, digest)
    for p, digest in lv['model_hashes_after_run'].items(): add(files, p, digest)
    # Bind every augmentation input. Unknown auxiliary source files are copied
    # into the pack so the output is self-contained and immutable.
    source_map = {}
    aug = load(augmentation)
    for index, (source, digest) in enumerate(aug['inputs'].items()):
        source = Path(source)
        if source == TRAIN:
            target = TRAIN
        elif source.name in CODE_NAMES or source.name == 'prompt.py':
            target = prompt if source.name == 'prompt.py' else code[source.name]
        else:
            target = out/'deps'/f'augmentation-{index}-{source.name}'
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        source_map[str(source)] = str(target); add(files, target, digest)
    # Bind the control transformation sources with the same mapping.
    contract = load(control_contract)
    for index, (source, digest) in enumerate(contract['source_sha256'].items()):
        source = Path(source)
        if source == TRAIN: target = TRAIN
        elif source.name in CODE_NAMES: target = code[source.name]
        elif source.name == 'prompt.py': target = prompt
        else:
            target = out/'deps'/f'contract-{index}-{source.name}'
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        source_map[str(source)] = str(target); add(files, target, digest)
    doc = dict(schema='r3-training-evidence-pack-v2', scientific_acceptance=False, test_read=False,
               control_arm=arm, input_mode='drop' if arm == 'K1-QO' else 'full', model=str(model),
               files=files, augmentation_digest=str(augmentation), byte_identical_local_snapshot_map=source_map,
               training_code_sha256=sha(code['train_r3.py']), lora_verification=str(verification))
    if arm == 'K1-QO':
        checker = ROOT/'tools/r3_control_data_contract.py'
        doc['control_data_checker'] = str(checker); doc['control_data_contract'] = str(control_contract)
        add(files, checker)
    path = out/'EVIDENCE.json'; path.write_text(json.dumps(doc, indent=2, sort_keys=True)+'\n')
    pin = sha(path); (out/'EVIDENCE_SHA256').write_text(pin+'\n')
    validator = module()
    validator.validate(path, pin, code_root, model, TRAIN, IMAGE, control_arm=arm, input_mode=doc['input_mode'])
    return path, pin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True, choices=('K1-QO', 'K1-PT'))
    ap.add_argument('--lora-root', required=True, type=Path)
    ap.add_argument('--augmentation', required=True, type=Path)
    ap.add_argument('--control-contract', required=True, type=Path)
    ap.add_argument('--model', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    path, pin = build(a.arm, a.lora_root, a.augmentation, a.control_contract, a.model, a.out)
    print(json.dumps({'status':'PASS', 'arm':a.arm, 'evidence':str(path), 'sha256':pin}))

if __name__ == '__main__': main()
