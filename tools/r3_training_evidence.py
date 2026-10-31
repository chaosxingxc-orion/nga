#!/usr/bin/env python3
"""Bind augmentation and CPU LoRA evidence to a new plan; no formal approval."""
import hashlib
import json
from pathlib import Path


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    p = Path(path)
    require(p.is_absolute() and p.is_file() and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe evidence path')
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def validate(path, pin, code, model, train, image):
    path, code, model, train = map(Path, (path, code, model, train))
    require(sha(path) == pin, 'training evidence pin differs')
    doc = load(path)
    require(doc.get('schema') == 'r3-training-evidence-pack-v1' and
            doc.get('scientific_acceptance') is False and doc.get('test_read') is False, 'training evidence scope differs')
    files = doc['files']
    for filename, digest in files.items():
        require(sha(filename) == digest, 'training evidence dependency changed: '+filename)
    def bound(p):
        require(str(p) in files, 'unbound evidence: '+str(p))
        return load(p)
    aug = bound(doc['augmentation_digest'])
    require(aug.get('status') == 'PASS' and aug.get('mismatches') == [] and
            aug.get('records') == 20 and aug.get('comparisons') == 80 and
            aug.get('seeds') == [2, 3] and aug.get('epochs') == [0, 1], 'augmentation evidence incomplete')
    mapped = {}
    for original, digest in aug['inputs'].items():
        target = doc['byte_identical_local_snapshot_map'].get(original, original)
        require(files.get(target) == digest, 'augmentation input not bound')
        mapped[Path(target).name] = digest
    require(mapped.get('train_r3.py') == doc['training_code_sha256'], 'training code evidence differs')
    require(aug['inputs'].get(str(train)) == sha(train), 'training data differs from augmentation check')
    lv = bound(doc['lora_verification'])
    require(lv.get('image') == image and lv.get('exit_code') == 0 and lv.get('state') == 'exited'
            and lv.get('npu_devices') == [] and lv.get('model_mount_readonly') is True, 'LoRA execution evidence differs')
    lr = Path(doc['lora_verification']).parent / 'results'
    require(files.get(str(lr/'digest.json')) == lv['digest_sha256'] and
            files.get(str(lr/'EXIT.json')) == lv['terminal_sha256'], 'LoRA result not bound')
    result, terminal = bound(lr/'digest.json'), bound(lr/'EXIT.json')
    require(type(terminal.get('exit_code')) is int and terminal['exit_code'] == 0, 'LoRA check failed')
    require(result.get('status') == 'PASS' and result.get('pairs') == 186 and
            result.get('trainable_tensors') == 372 and result.get('trainable_parameters') == 10822656
            and result.get('trainable_dtype') == 'float32' and result.get('device') == 'cpu'
            and all(result.get(k) is True for k in ('frozen_non_lora','frozen_embeddings_lm_head','gradient_checkpointing')),
            'LoRA construction contract differs')
    require(all(files.get(p) == h for p,h in lv['code'].items()), 'LoRA code not bound')
    for name in ('train_r3.py','build_kev_sft.py','kev_aug.py','prompt.py'):
        current = code / ('r0_code/prompt.py' if name == 'prompt.py' else name)
        tested = [h for p,h in lv['code'].items() if Path(p).name == name]
        require(len(tested) == 1 and tested[0] == mapped.get(name) == sha(current), 'planned code not the checked code: '+name)
    actual = {str(p):sha(p) for p in model.rglob('*') if p.is_file()}
    require(actual and actual == lv['model_hashes_after_run'], 'planned model not the checked model')
    require(all(files.get(p) == h for p,h in actual.items()), 'model evidence not bound')
    return {**files, str(path):pin}
