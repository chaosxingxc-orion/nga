"""Structural completeness of a caller-verified 0.8B final campaign.

No files, checkpoints or test data are read. This consumes model identities and
``selection_evidence_r3.train_identity`` dictionaries verified by the caller.
Their SHA fields are bindings, never proof of source verification, eligibility,
selection finality or independent review. No FINAL or authorization is produced.
Larger sizes need their own reviewed membership contract and are refused here.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re

BASE = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base'
INSTRUCT = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def pin(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None,
            'invalid SHA256 identity')
    return value


def path(value):
    require(isinstance(value, str) and value.startswith('/') and not value.startswith('//')
            and '..' not in PurePosixPath(value).parts and str(PurePosixPath(value)) == value,
            'canonical absolute path required')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def verify(campaign):
    """Validate six members, without establishing the caller's factual claims.

    Input schema ``r3-final-campaign-v1`` has ``size='0.8B'``, ``selected_arm``
    (K1 or K2), and ``members``. Each member has role (candidate/baseline/control),
    arm, model (path/sha256/kind/base_path/base_inventory_sha256), and
    verified_evidence_sha256. Trained members additionally have ``training``
    exactly in the shape returned by train_identity; baseline omits training.
    Unknown auxiliary model/training fields are retained in the input digest.
    """
    require(isinstance(campaign, dict) and campaign.get('schema') == 'r3-final-campaign-v1',
            'campaign schema differs')
    require(campaign.get('size') == '0.8B', 'only reviewed 0.8B membership shape supported')
    selected = campaign.get('selected_arm')
    require(selected in ('K1', 'K2'), 'selected arm must be K1 or K2, never a control')
    members = campaign.get('members')
    require(isinstance(members, list) and len(members) == 6, 'complete six-member campaign required')
    seen_paths, seen_sha, seen_manifests = set(), set(), set()
    cells = {}
    for member in members:
        require(isinstance(member, dict), 'member must be an object')
        arm, role = member.get('arm'), member.get('role')
        require(arm in (selected, 'K0', 'K1-QO', 'K1-PT'), 'unexpected campaign arm')
        expected_role = 'candidate' if arm == selected else 'baseline' if arm == 'K0' else 'control'
        require(role == expected_role, 'control/candidate/baseline role confusion')
        pin(member.get('verified_evidence_sha256'))
        model = member.get('model')
        require(isinstance(model, dict), 'model identity required')
        model_path, model_sha = path(model.get('path')), pin(model.get('sha256'))
        require(model_path not in seen_paths and model_sha not in seen_sha, 'duplicate model path or identity')
        seen_paths.add(model_path); seen_sha.add(model_sha)
        base = INSTRUCT if arm == 'K1-PT' else BASE
        require(path(model.get('base_path')) == base, 'wrong base checkpoint')
        pin(model.get('base_inventory_sha256'))
        if arm == 'K0':
            require('training' not in member and 'seed' not in member,
                    'K0 is one checkpoint without training or synthetic seeds')
            require(model.get('kind') == 'checkpoint' and model_path == BASE, 'K0 checkpoint identity differs')
            seed = None
        else:
            require(model.get('kind') == 'lora-adapter-unmerged', 'trained member must be unmerged adapter')
            require(PurePosixPath(model_path).name == 'adapter', 'adapter must belong to training directory')
            training = member.get('training')
            require(isinstance(training, dict), 'verified training identity required')
            seed = training.get('seed')
            require(type(seed) is int and seed in ((2,) if arm == 'K1-QO' else (2, 3)),
                    'trained seed differs')
            require(training.get('arm') == arm and training.get('adapter_path') == model_path,
                    'training arm or adapter differs')
            manifest = path(training.get('training_manifest'))
            require(manifest == str(PurePosixPath(model_path).parent / 'manifest.json'),
                    'training manifest does not own adapter')
            require(manifest not in seen_manifests, 'training manifest reused')
            seen_manifests.add(manifest); pin(training.get('training_manifest_sha256'))
            recipe = training.get('training_variant')
            require(isinstance(recipe, dict) and recipe.get('model_path') == base,
                    'training recipe base differs')
            args = recipe.get('args')
            require(isinstance(args, dict) and args.get('arm') == ('k2' if arm == 'K2' else 'k1')
                    and args.get('drop_state') is (arm == 'K1-QO'), 'training recipe objective/input differs')
        key = (arm, seed)
        require(key not in cells, 'duplicate arm/seed')
        cells[key] = member
    expected = {(selected, 2), (selected, 3), ('K0', None), ('K1-QO', 2), ('K1-PT', 2), ('K1-PT', 3)}
    require(set(cells) == expected, 'missing required arm/seed')
    base_pin = cells['K0', None]['model']['base_inventory_sha256']
    for key in ((selected, 2), (selected, 3), ('K1-QO', 2)):
        require(cells[key]['model']['base_inventory_sha256'] == base_pin, 'Base checkpoint bytes differ')
    pt_pin = cells['K1-PT', 2]['model']['base_inventory_sha256']
    require(pt_pin != base_pin and cells['K1-PT', 3]['model']['base_inventory_sha256'] == pt_pin,
            'PT instruct checkpoint bytes differ or alias Base')
    for arm in (selected, 'K1-PT'):
        require(canonical(cells[arm, 2]['training']['training_variant']) ==
                canonical(cells[arm, 3]['training']['training_variant']), 'paired seeds use different recipes')
    return {'schema': 'r3-final-campaign-structure-v1', 'membership_complete': True,
            'campaign_sha256': hashlib.sha256(canonical(campaign).encode()).hexdigest(),
            'size': '0.8B', 'selected_arm': selected, 'member_count': 6,
            'candidate_seeds': [2, 3], 'controls': {'K1-QO': [2], 'K1-PT': [2, 3]},
            'scientific_acceptance': False, 'publication_authorized': False,
            'scope': 'caller-supplied identity structure only; no files or test data read',
            'remaining': ['source verification including canonical filesystem identity',
                          'semantic training eligibility and selection finality',
                          'independent review and final execution admission']}
