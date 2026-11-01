#!/usr/bin/env python3
"""Validate the bounded CPU runtime used to consume resume evidence.

This is a provenance check only. It never runs a model and never grants
training or scientific acceptance. The runtime receipt must describe a fixed
container, a CPU-only Torch import guard, immutable input mounts and a
successful pinned reconstruction output.
"""
import hashlib
import json
from pathlib import Path

RUNTIME_SCHEMA = 'jev-cpu-reviewer-runtime-v1'
EXIT_SCHEMA = 'jev-cpu-reviewer-runtime-exit-v1'
IMAGE = 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe runtime path')
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe runtime receipt')
    return json.loads(p.read_text())


def validate(contract_path, contract_pin, *, plan, plan_pin, target, target_pin,
             validator, validator_pin, verifier, verifier_pin):
    require(sha(contract_path) == contract_pin, 'runtime contract hash differs')
    contract = load(contract_path)
    require(contract.get('schema') == RUNTIME_SCHEMA, 'runtime schema differs')
    require(contract.get('image') == IMAGE and contract.get('image_requested') == IMAGE,
            'runtime image differs')
    require(contract.get('network_mode') == 'none', 'runtime network is enabled')
    require(contract.get('status') == 'exited' and contract.get('exit_code') == 0,
            'runtime did not finish successfully')
    require(contract.get('env') == ['TORCH_DEVICE_BACKEND_AUTOLOAD=0'],
            'Torch backend autoload guard missing')
    require(contract.get('torch_version') == '2.10.0+cpu', 'unexpected CPU Torch runtime')
    scope = contract.get('scope', {})
    require(scope.get('pass') is True and scope.get('scientific_acceptance') is False
            and scope.get('test_read') is False, 'runtime output scope differs')
    require(contract.get('output') and contract.get('output_sha256')
            and sha(contract['output']) == contract['output_sha256'],
            'runtime output hash differs')
    require(contract.get('log') and contract.get('log_sha256')
            and sha(contract['log']) == contract['log_sha256'], 'runtime log hash differs')
    exit_path = Path(contract_path).with_name('RUNTIME_EXIT.json')
    require(exit_path.exists(), 'runtime exit receipt missing')
    exit_doc = load(exit_path)
    require(exit_doc.get('schema') == EXIT_SCHEMA and exit_doc.get('exit_code') == 0
            and exit_doc.get('scientific_acceptance') is False
            and exit_doc.get('test_read') is False,
            'runtime exit scope differs')
    require(exit_doc.get('runtime_contract') == str(Path(contract_path))
            and exit_doc.get('runtime_contract_sha256') == contract_pin,
            'runtime exit binding differs')
    for name, path, pin in (
        ('plan', plan, plan_pin), ('target', target, target_pin),
        ('validator', validator, validator_pin), ('verifier', verifier, verifier_pin)):
        require(scope.get(name + '_sha256') == pin,
                'runtime '+name+' pin differs')
    # Return all artifacts that the launcher must hash again before launch.
    return {
        str(Path(contract_path)): contract_pin,
        str(exit_path): sha(exit_path),
        str(contract['output']): contract['output_sha256'],
        str(contract['log']): contract['log_sha256'],
    }
