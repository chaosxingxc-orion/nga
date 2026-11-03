#!/usr/bin/env python3
"""Explain two original K0 release records; never amend them or grant admission.

The old writer did not emit claim_sha256. A derived in-memory view allows the
unchanged ownership checker to test remaining predicates. It is not a historical
receipt and cannot be passed to the campaign consumer as original evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

QUALIFIER_SHA = '89fa709d4f830f38ebbc7bd449d89a8e3c527ed3e986dc71ff6faa64f755df4f'
WRITER_SHA = 'ccfa064a365e6f1c29f1f19ddfb47ed7e94864d9ef5c802e8a8a98d2e322f1fa'
ORIGINALS = {
    'k0_base': {
        'execution': 'fcfe5b4bde340497712ea79a045b02ddac1270b0f19c9d9eb623c46ab660c2df',
        'claim': '09ab982fb5a140c1701dd3a7cc7a5cfd52412a59f8778fac95eda7f3db610222',
        'release': '212aeb4c23b89e2244f2537e7476cf08e37387fe4cd70d937ec10ae24663a0e2'},
    'k0_instruct': {
        'execution': '4261e76402ff9b61fee41c98067fcecdaddb7af9a2b28964ea6d2a2203b2441b',
        'claim': '2843296e50f160a573ca9961e8d10770fd6b0e60b309aea1c9b1b0e2f42c619c',
        'release': '050df7bc2d2f6399a982b0a33964ea6a4c7c5dd9011f96db009acee361ac5e37'},
}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def raw(path, pin):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe evidence path')
    data = p.read_bytes()
    require(hashlib.sha256(data).hexdigest() == pin, 'evidence pin differs')
    return data


def loaded(path, pin):
    return json.loads(raw(path, pin))


def verify_relationship(checker, execution, claim, release, claim_pin,
                        release_path, container):
    require('claim_sha256' not in release, 'only original missing-field format')
    require('successor_precondition' not in claim, 'guarded claims not legacy K0')
    # This view is deliberately never serialized as a release or adjudication.
    view = dict(release, claim_sha256=claim_pin)
    return checker.ownership(execution, claim, view, claim_pin, release_path, container)


def explain(config_path, config_pin, capture_path, capture_pin, member):
    require(member in ORIGINALS, 'only two original K0 members supported')
    fixed = ORIGINALS[member]
    config = loaded(config_path, config_pin)
    m = config['members'][member]
    require(m['arm'] == 'K0' and 'plan' not in m, 'untuned K0 required')
    execution_path = Path(m['execution'])
    execution = loaded(execution_path, fixed['execution'])
    attempt = Path(execution['out']) / 'attempts/1'
    claim_path, release_path = attempt / 'CLAIM.json', attempt / 'RELEASE.json'
    for p, h in [(execution_path, fixed['execution']), (claim_path, fixed['claim']),
                 (release_path, fixed['release'])]:
        require(config['immutable_files'].get(str(p)) == h, 'original not previously pinned')
    claim = loaded(claim_path, fixed['claim'])
    release = loaded(release_path, fixed['release'])
    writer_path = execution['resource_adapter']
    require(execution['tools'].get(writer_path) == WRITER_SHA, 'legacy writer differs')
    raw(writer_path, WRITER_SHA)
    capture = loaded(capture_path, capture_pin)
    require(capture['member'] == member and capture['execution'] == str(execution_path)
            and capture['execution_sha256'] == fixed['execution'], 'capture identity differs')
    observations = capture['evaluation_observations']
    for ref in observations.values():
        require(capture['files'].get(ref['path']) == ref['sha256'], 'unbound observation')
        raw(ref['path'], ref['sha256'])
    actual = loaded(observations['container']['path'], observations['container']['sha256'])
    require(len(actual) == 1, 'single retained generation required')
    actual = actual[0]
    state = actual['State']
    require(state['Status'] == 'exited' and state['Running'] is False and
            type(state['ExitCode']) is int and state['ExitCode'] == 0 and
            not state.get('OOMKilled') and not state.get('Error') and
            not actual['HostConfig']['AutoRemove'], 'successful retained container required')
    qref = config['qualifier']
    require(qref['sha256'] == QUALIFIER_SHA, 'frozen ownership checker differs')
    source = raw(qref['path'], QUALIFIER_SHA)
    checker = types.ModuleType('frozen_ownership')
    checker.__file__ = qref['path']
    exec(compile(source, qref['path'], 'exec'), checker.__dict__)
    timing = verify_relationship(checker, execution, claim, release,
                                 fixed['claim'], release_path, actual)
    # A fresh read verifies this operation did not amend historical evidence.
    raw(claim_path, fixed['claim']); raw(release_path, fixed['release'])
    return {'schema': 'r3-original-k0-release-evidence-v1', 'member': member,
            'status': 'RELATIONSHIP_VERIFIED_PENDING_INDEPENDENT_COMPATIBILITY_REVIEW',
            'original_pins': fixed, 'original_writer_sha256': WRITER_SHA,
            'qualifier': qref, 'capture': {'path': str(capture_path), 'sha256': capture_pin},
            'timing': timing, 'historical_files_modified': False,
            'derived_release_persisted': False, 'independent_review': None,
            'scientific_acceptance': False, 'candidate_eligibility_granted': False,
            'test_read': False,
            'limitation': 'Structural compatibility only. Does not establish contemporary '
                          'claim-hash recording or producer authenticity. Frozen qualifier '
                          'still rejects originals; separate reviewed integration required.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'config-sha256', 'capture', 'capture-sha256', 'member', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = explain(args.config, args.config_sha256, args.capture, args.capture_sha256, args.member)
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps({'member': args.member, 'status': result['status']}))
