#!/usr/bin/env python3
"""Bind augmentation and CPU LoRA evidence to a new plan; no formal approval."""
import hashlib
import json
from pathlib import Path

CONTROL_MODELS = {
    'K1-QO': Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'),
    'K1-PT': Path('/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'),
}
# This checker tests the drop transformation, not scientific eligibility. Its
# training-only sentinel checks preserve every non-prompt field and compare the
# remaining prompt byte-for-byte, using the actual augmentation and renderer.
CONTROL_DATA_CHECKER_SHA256 = 'b8393f58e5130e22a7537270fe8ed50a63a9d95caf48882f3202c084c04c88fd'


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


def validate(path, pin, code, model, train, image, *, control_arm=None, input_mode='full'):
    path, code, model, train = map(Path, (path, code, model, train))
    require(sha(path) == pin, 'training evidence pin differs')
    doc = load(path)
    schema = doc.get('schema')
    require(schema in ('r3-training-evidence-pack-v1', 'r3-training-evidence-pack-v2') and
            doc.get('scientific_acceptance') is False and doc.get('test_read') is False, 'training evidence scope differs')
    if schema == 'r3-training-evidence-pack-v1':
        require(control_arm is None and input_mode == 'full' and
                doc.get('control_arm') is None and doc.get('input_mode', 'full') == 'full',
                'legacy training evidence only supports full-input K1')
    else:
        require(control_arm in CONTROL_MODELS and
                doc.get('control_arm') == control_arm and
                input_mode == ('drop' if control_arm == 'K1-QO' else 'full') and
                doc.get('input_mode') == input_mode, 'control/input-mode evidence differs')
        require(model == CONTROL_MODELS[control_arm] and doc.get('model') == str(model),
                'control model evidence differs')
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
        require(Path(target).name not in mapped, 'ambiguous augmentation source name')
        mapped[Path(target).name] = digest
    require(mapped.get('train_r3.py') == doc['training_code_sha256'], 'training code evidence differs')
    require(aug['inputs'].get(str(train)) == sha(train), 'training data differs from augmentation check')
    if control_arm == 'K1-QO':
        checker = doc.get('control_data_checker')
        require(checker in files and files[checker] == CONTROL_DATA_CHECKER_SHA256,
                'QO transformation checker not bound')
        transformation = bound(doc.get('control_data_contract'))
        require(transformation.get('schema') == 'r3-control-data-contract-v1' and
                transformation.get('status') == 'PASS' and transformation.get('seed') == 2 and
                transformation.get('test_read') is False and
                transformation.get('scientific_acceptance') is False,
                'QO transformation evidence scope differs')
        epochs = transformation.get('epochs')
        require(isinstance(epochs, list) and len(epochs) == 2 and
                all(isinstance(row, dict) and row.get('epoch') == epoch and
                    row.get('base_questions') == 20 and
                    type(row.get('examples_checked')) is int and row['examples_checked'] >= 20
                    for epoch, row in enumerate(epochs)), 'QO transformation population differs')
        sources = transformation.get('source_sha256', {})
        require(sources.get(str(train)) == sha(train), 'QO transformation training data differs')
        observed = {}
        for original, digest in sources.items():
            target = doc['byte_identical_local_snapshot_map'].get(original, original)
            require(files.get(target) == digest, 'QO transformation source not bound')
            require(Path(target).name not in observed, 'ambiguous QO transformation source name')
            observed[Path(target).name] = digest
        require(set(observed) == {'train_r3.py', 'build_kev_sft.py', 'kev_aug.py', 'prompt.py', train.name},
                'QO transformation source inventory differs')
        require(all(observed.get(name) == mapped.get(name) for name in observed),
                'QO transformation code differs from augmentation evidence')
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
