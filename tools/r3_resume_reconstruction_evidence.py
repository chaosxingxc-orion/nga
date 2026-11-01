"""Bind a separately reconstructed restart report to a proposed training recipe.

CPU reconstruction is executed again during consumption through pinned source.
PyTorch is required; missing runtime dependencies fail closed. This verifies
numerical content, not training/reviewer authorship or historical execution.
No test data, launch, FINAL or scientific approval is involved.
"""
import json
import math
from pathlib import Path

VERIFIER_SHA256 = '0b3963432140b0860dad92f14f5f8079b884d9d4e6e5114d7cd902f10254803e'
VALIDATOR_SHA256 = '5a00d2cff57d82ffe533bf7b10ddaffafbfd4b61651aac9c6d59ecaff97dbd84'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def trusted_module(filename, pin, name):
    # Execute the verified source bytes directly: never cached bytecode or a
    # pre-existing module merely claiming the same __file__.
    import hashlib
    import types
    path = Path(__file__).with_name(filename)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe verifier source')
    source = path.read_bytes()
    require(hashlib.sha256(source).hexdigest() == pin, 'verifier implementation differs')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def validator():
    return trusted_module('r3_resume_evidence.py', VALIDATOR_SHA256,
                          'reconstruction_receipt_validator')


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
    verifier = trusted_module('r3_resume_recompute.py', VERIFIER_SHA256,
                              'reconstruction_tensor_verifier')
    reconstructed = verifier.verify(Path(resume_plan).parent, actual)
    for key in ('replicas', 'resumed', 'controls', 'bars', 'resume_pass', 'controls_rejected', 'pass'):
        require(reconstructed[key] == doc.get(key), 'CPU reconstructed report differs: '+key)
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
    return {**actual, str(Path(__file__).with_name('r3_resume_recompute.py')):VERIFIER_SHA256,
            str(Path(path)):pin,
            str(Path(reconstruction_target)):reconstruction_target_sha256}
