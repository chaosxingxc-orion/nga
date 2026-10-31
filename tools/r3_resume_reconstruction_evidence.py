"""Bind a separately reconstructed restart report to a proposed training recipe.

CPU-only artifact validation, not tensor reconstruction or review authorship.
The exact-plan reviewer must establish that the pinned reconstruction executed.
No test data, torch, launch, FINAL or scientific approval is involved.
"""
import importlib.util
import json
import math
from pathlib import Path

VERIFIER_SHA256 = '0b3963432140b0860dad92f14f5f8079b884d9d4e6e5114d7cd902f10254803e'
VALIDATOR_SHA256 = 'ea8e367417bb1b0990e9c67f4d2cecfb8c70c2c7589c9850e298d7d36c3c1be3'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def validator():
    path = Path(__file__).with_name('r3_resume_evidence.py')
    import hashlib
    require(hashlib.sha256(path.read_bytes()).hexdigest() == VALIDATOR_SHA256,
            'receipt validator implementation differs')
    spec = importlib.util.spec_from_file_location('reconstruction_receipt_validator', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def validate(path, pin, *, resume_plan, resume_pin, target, reconstruction_target,
             reconstruction_target_sha256):
    """Require exact reconstructed inputs and compatible source/target recipe.

    The reconstruction target is the immutable plan used by the CPU verifier.
    The proposed target may change seed/output but must pass the same actual
    receipt validator, which binds code, model, data and every recipe argument.
    """
    R = validator()
    require(R.sha(path) == pin, 'reconstruction report pin differs')
    require(R.sha(reconstruction_target) == reconstruction_target_sha256,
            'reconstruction target pin differs')
    doc = R.load(path)
    require(doc.get('scientific_acceptance') is False and doc.get('test_read') is False
            and doc.get('pass') is True and doc.get('resume_pass') is True,
            'reconstruction not a successful engineering report')
    require(doc.get('plan_sha256') == resume_pin
            and doc.get('target_sha256') == reconstruction_target_sha256
            and doc.get('validator_sha256') == VALIDATOR_SHA256
            and doc.get('verifier_sha256') == VERIFIER_SHA256,
            'reconstruction execution bindings differ')
    actual = R.validate(resume_plan, resume_pin, target)
    original = R.validate(resume_plan, resume_pin, R.load(reconstruction_target))
    require(actual == original == doc.get('inputs'), 'reconstruction input inventory differs')
    claimed = R.load(Path(resume_plan).parent/'CONTRACT_RESULT.json')
    replicas, resumed, controls = doc['replicas'], doc['resumed'], doc['controls']
    require(isinstance(replicas, list) and len(replicas) == 3, 'reconstruction replicas differ')
    for row in replicas:
        R.judge(row['loss'], row['weight_relative_l2'], 0., 0., controls)
    verdict = R.judge(max(r['loss'] for r in replicas),
                      max(r['weight_relative_l2'] for r in replicas),
                      resumed['loss'], resumed['weight_relative_l2'], controls)
    require(verdict['pass'] and all(doc.get(k) == v for k,v in verdict.items()),
            'reconstruction numerical verdict differs')
    rows = [*replicas, resumed, controls['zero_moments'], controls['no_update']]
    expected = [*claimed['replicas'], claimed['resumed'],
                claimed['controls']['zero_moments'], claimed['controls']['no_update']]
    for a,b in zip(rows, expected):
        require(all(math.isclose(a[k], b[k], rel_tol=1e-9, abs_tol=1e-12)
                    for k in ('loss','weight_relative_l2')), 'reconstruction distances differ')
    # Recheck after all consumers: no cached inventory can hide changed inputs.
    for filename,digest in actual.items():
        require(R.sha(filename) == digest, 'reconstruction dependency changed')
    require(R.sha(path) == pin and R.sha(reconstruction_target) == reconstruction_target_sha256,
            'reconstruction artifact changed during validation')
    return {**actual, str(Path(path)):pin,
            str(Path(reconstruction_target)):reconstruction_target_sha256}
