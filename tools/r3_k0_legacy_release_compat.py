#!/usr/bin/env python3
"""Unactivated, exact-original K0 ownership compatibility proposal.

This helper returns a relationship proof, never a replacement RELEASE. It is
not installed in the frozen qualifier and grants no member/campaign admission.
A future reviewed consumer must preserve every evaluation_runtime check before
calling this helper at its final ownership step.
"""
import argparse
import json
from pathlib import Path

from tools import r3_k0_legacy_release_evidence as E

CONFIG_SHA = '7215ac3bf4f088d4d6dae634017740d92a56c4c5a2872173c85d968b9563e6e0'
CAPTURE_SHA = {
    'k0_base': '12adc2fb85a1d9263579020753915c78c01b3c1369070d60cd7a068d69020776',
    'k0_instruct': 'c5efad9af897ef223bd47af97227399b017c76ec106948d9591cccedf19c3848',
}


def exact(left, right, message):
    # Unlike Python dict equality, canonical JSON distinguishes True from 1.
    canonical = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)
    E.require(canonical(left) == canonical(right), message)


def verify(config_path, capture_path, member, *, execution, claim, release,
           claim_pin, release_path, actual):
    """Check original on-disk proof AND exact arguments from the future caller."""
    E.require(member in CAPTURE_SHA, 'only two original K0 members supported')
    config = E.loaded(config_path, CONFIG_SHA)
    capture = E.loaded(capture_path, CAPTURE_SHA[member])
    pins = E.ORIGINALS[member]
    entry = config['members'][member]
    original_execution = E.loaded(entry['execution'], pins['execution'])
    attempt = Path(original_execution['out']) / 'attempts/1'
    E.require(str(release_path) == str(attempt/'RELEASE.json'), 'release path differs')
    E.require(claim_pin == pins['claim'], 'claim generation differs')
    exact(execution, original_execution, 'caller execution differs')
    exact(claim, E.loaded(attempt/'CLAIM.json', pins['claim']), 'caller claim differs')
    exact(release, E.loaded(attempt/'RELEASE.json', pins['release']), 'caller release differs')
    container_ref = capture['evaluation_observations']['container']
    containers = E.loaded(container_ref['path'], container_ref['sha256'])
    E.require(len(containers) == 1, 'single original container required')
    exact(actual, containers[0], 'caller container differs')
    # Authenticate the complete original producer declarations, not a subset.
    for path, pin in original_execution['tools'].items():
        E.raw(path, pin)
    E.raw(original_execution['spec'], original_execution['spec_sha256'])
    proof = E.explain(config_path, CONFIG_SHA, capture_path, CAPTURE_SHA[member], member)
    return {
        'schema': 'r3-exact-original-k0-ownership-compatibility-proposal-v1',
        'member': member, 'timing': proof['timing'],
        'original_pins': pins, 'config_sha256': CONFIG_SHA,
        'capture_sha256': CAPTURE_SHA[member],
        'compatibility_scope': 'ownership relation only; missing legacy claim_sha256',
        'active': False, 'scientific_acceptance': False,
        'candidate_eligibility_granted': False, 'test_read': False,
        'historical_files_modified': False, 'derived_release_persisted': False,
        'independent_review': None,
    }


def replay(config_path, capture_path, member):
    E.require(member in CAPTURE_SHA, 'only two original K0 members supported')
    cfg = E.loaded(config_path, CONFIG_SHA)
    cap = E.loaded(capture_path, CAPTURE_SHA[member])
    pins = E.ORIGINALS[member]
    execution = E.loaded(cfg['members'][member]['execution'], pins['execution'])
    a = Path(execution['out'])/'attempts/1'
    ref = cap['evaluation_observations']['container']
    return verify(config_path, capture_path, member, execution=execution,
                  claim=E.loaded(a/'CLAIM.json', pins['claim']),
                  release=E.loaded(a/'RELEASE.json', pins['release']),
                  claim_pin=pins['claim'], release_path=a/'RELEASE.json',
                  actual=E.loaded(ref['path'], ref['sha256'])[0])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('config', 'capture', 'member', 'output'):
        p.add_argument('--'+field, required=True)
    args = p.parse_args()
    result = replay(args.config, args.capture, args.member)
    with Path(args.output).open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'member':args.member,'active':False,'relationship_verified':True}))
