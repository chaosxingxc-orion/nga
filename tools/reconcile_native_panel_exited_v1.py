#!/usr/bin/env python3
"""Reconcile one failed, retained native-panel-v2 generation; never launch/retry.

Uses the frozen resource module's release transaction. Runtime EXIT remains
absent; a reconstructed host EXIT explicitly records retained-container evidence.
Partial transactions require a separately reviewed repair, never blind replay.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import types


def need(ok, message):
    if not ok:
        raise ValueError(message)


def exact(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def raw(path):
    p = Path(path)
    need(p.is_absolute() and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    return p.read_bytes()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def pinned(ref):
    need(set(ref) == {'path', 'sha256'}, 'invalid reference')
    value = raw(ref['path'])
    need(digest(value) == ref['sha256'], 'reference changed: ' + ref['path'])
    return value


def module(ref):
    value = pinned(ref)
    m = types.ModuleType('reconcile_' + Path(ref['path']).stem)
    m.__file__ = ref['path']
    exec(compile(value, ref['path'], 'exec'), m.__dict__)
    return m


def observed_generation(a):
    return {k: a[k] for k in ('Id', 'Name', 'Image', 'Created', 'RestartCount', 'State')}


def validate_container(c, d, a, cmd):
    need(a is not None and exact(observed_generation(a), c['generation']), 'container generation changed')
    s = a['State']
    need(s['Status'] == 'exited' and s['Running'] is False and s['Restarting'] is False
         and type(s['ExitCode']) is int and s['ExitCode'] != 0 and s['Pid'] == 0,
         'failed exited container required')
    need(type(a['RestartCount']) is int and a['RestartCount'] == 0, 'restarted container refused')
    need(a['Name'] == '/' + d['container'] + '-a' + str(c['attempt']) and a['Image'] == d['image'], 'container identity differs')
    need(a['Config']['Cmd'] == cmd[cmd.index(d['image']) + 1:], 'container command differs')
    host = a['HostConfig']
    need(host.get('AutoRemove') is False and host.get('Privileged') is False, 'unsafe retained container')
    devices = sorted((x['PathOnHost'], x['PathInContainer'], x['CgroupPermissions']) for x in host['Devices'])
    expected = sorted(('/dev/' + x, '/dev/' + x, 'rwm') for x in ('davinci_manager', 'devmm_svm', 'hisi_hdc', 'davinci' + str(d['chip'])))
    need(devices == expected, 'device bindings differ')
    need(exact({k: a[k] for k in ('Config', 'HostConfig')},
               {k: c['effective_configuration'][k] for k in ('Config', 'HostConfig')}), 'effective configuration changed')
    need(exact(sorted(a['Mounts'], key=lambda x: x['Destination']),
               sorted(c['effective_configuration']['Mounts'], key=lambda x: x['Destination'])), 'effective mounts changed')
    actual_mounts = sorted((x['Source'], x['Destination'], x['RW']) for x in a['Mounts'])
    need(actual_mounts == sorted((x['source'], x['destination'], not x['readonly']) for x in d['mounts']), 'mount bindings differ')


def absent_supervisor(service, host_path, plan_path):
    need(type(service['pid']) is int and service['pid'] > 0, 'supervisor PID invalid')
    need(not Path('/proc', str(service['pid'])).exists(), 'supervisor PID still present; explicit identity review required')
    # Also reject a replacement supervisor launched under another PID.
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():
            continue
        try:
            argv = (p / 'cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:
            continue
        need(not all(x.encode() in argv for x in (host_path, plan_path, 'supervise')), 'replacement supervisor present')


def load_configuration(path, pin):
    data = raw(path)
    need(digest(data) == pin, 'reconciliation configuration changed')
    c = json.loads(data)
    need(c['schema'] == 'reconcile-native-panel-exited-v1' and c['scientific_acceptance'] is False, 'unsupported reconciliation')
    need(type(c['attempt']) is int and c['attempt'] == 1, 'v1 only admits attempt 1')
    need(pinned(c['implementation']) == raw(str(Path(__file__).resolve())), 'reconciliation implementation differs')
    d = json.loads(pinned(c['plan']))
    need(d['schema'] == 'native-panel-execution-v2' and d['scope'] == 'public_fixed_base_test'
         and d['scientific_acceptance'] is False and d['candidate_test_authority'] is False, 'unregistered experiment schema')
    need(type(d['chip']) is int and 0 <= d['chip'] < 8, 'invalid chip')
    need(socket.gethostname() == d['host_name'], 'wrong host')
    h = Path(d['out']) / 'host_attempts' / str(c['attempt'])
    need(set(c['receipts']) == {'CLAIM.json', 'LAUNCH_SPEC.json', 'LAUNCH_RECEIPT.json', 'SERVICE.json'}, 'receipt set differs')
    receipts = {}
    for name, ref in c['receipts'].items():
        need(ref['path'] == str(h / name), 'receipt path differs')
        receipts[name] = json.loads(pinned(ref))
    for name in ('host', 'resource', 'resource_base'):
        need(d['files'][d['modules'][name]['path']] == d['modules'][name]['sha256'], 'module not bound to plan')
        pinned(d['modules'][name])
    host = module(d['modules']['host'])
    cmd = host.command(dict(d, image_sha256=d['image'], runtime=d['modules']['runtime']), c['plan']['path'], c['plan']['sha256'], c['attempt'])
    spec, receipt = receipts['LAUNCH_SPEC.json'], receipts['LAUNCH_RECEIPT.json']
    need(spec['command'] == cmd and spec['plan_sha256'] == c['plan']['sha256'], 'launch spec differs')
    need(receipt['plan_sha256'] == c['plan']['sha256'] and type(receipt['attempt']) is int
         and receipt['attempt'] == c['attempt'] and receipt['scientific_acceptance'] is False
         and receipt['container_id'] == c['generation']['Id'] and receipt['command'] == cmd[cmd.index(d['image']) + 1:], 'launch receipt differs')
    claim = receipts['CLAIM.json']
    need(claim['schema'] == 'r3-resource-claim-v1' and claim['run'] == d['run']
         and exact(claim['chip'], d['chip']) and claim['allocation'] == d['allocation'], 'claim identity differs')
    need(type(claim.get('successor_precondition')) is dict, 'v1 requires guarded claim generation')
    service = receipts['SERVICE.json']
    expected = [d['host_python'], '-B', '-P', d['modules']['host']['path'], 'supervise', '--plan', c['plan']['path'], '--sha256', c['plan']['sha256']]
    need(service['command'][:len(expected)] == expected and service['command'][-2:] == ['--attempt', str(c['attempt'])], 'supervisor command differs')
    return c, d, h, receipts, cmd


def run(path, pin, execute=False, review=None):
    c, d, h, receipts, cmd = load_configuration(path, pin)
    R = module(d['modules']['resource_base'])
    root = Path(d['out'])
    original_inspect = R.docker_inspect
    name = d['container'] + '-a' + str(c['attempt'])
    terminal = root / 'attempts' / str(c['attempt']) / 'EXIT.json'

    def check_missing():
        for p in (terminal, h / 'EXIT.json', h / 'RELEASE.json', h / 'RELEASE.json.intent'):
            need(not p.exists() and not p.with_name(p.name + '.pending').exists(), 'partial/existing terminal transaction requires separate review')

    def checked_inspect(requested):
        need(requested == name, 'unexpected release container request')
        # This function is also called by the original release inside its lock.
        load_configuration(path, pin)
        check_missing()
        absent_supervisor(receipts['SERVICE.json'], d['modules']['host']['path'], c['plan']['path'])
        a = original_inspect(requested)
        validate_container(c, d, a, cmd)
        return a

    with contextlib.ExitStack() as stack:
        for lockpath in (root / 'start.lock', root / 'host.lock'):
            need(lockpath.exists() and not lockpath.is_symlink(), 'original lifecycle lock missing/unsafe')
            lock = stack.enter_context(lockpath.open('r+'))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checked_inspect(name)
        need(not R.live_chip_conflict(d['chip'], None), 'live chip conflict')
        with R.locked(d['allocation']):
            ledger = R.load(d['allocation']); R.validate_doc(ledger)
            need(exact([x for x in ledger['allocation'] if x['chip'] == d['chip']], [receipts['CLAIM.json']['entry']])
                 and not any(x['chip'] == d['chip'] for x in ledger['free']), 'claim generation / owner differs')
        if not execute:
            return {'status': 'VERIFIED_READ_ONLY', 'config_sha256': pin, 'scientific_acceptance': False}
        need(review is not None, 'independent execution review required')
        r = json.loads(pinned(review))
        need(r.get('verdict') == 'PASS' and r.get('approved_config_sha256') == pin
             and r.get('release_authorized') is True and r.get('scientific_acceptance') is False, 'execution review differs')
        R.docker_inspect = checked_inspect
        # Existing frozen release owns the allocation lock, intent and ledger transaction.
        # Permit its own newly written intent on the final revalidation, but never
        # accept a preexisting transaction at entry.
        def during_release_check():
            for p in (terminal, h / 'EXIT.json', h / 'RELEASE.json'):
                need(not p.exists(), 'terminal appeared during release')
        check_missing = during_release_check
        args = types.SimpleNamespace(alloc=d['allocation'], run=d['run'], chip=d['chip'], container=name,
                                     container_id=c['generation']['Id'], claim=str(h / 'CLAIM.json'), proof=str(h / 'RELEASE.json'))
        R.release(args)
        release = R.load(args.proof)
        need(release['claim_sha256'] == c['receipts']['CLAIM.json']['sha256']
             and release['container_id'] == c['generation']['Id'] and release['exit_code'] != 0, 'release proof differs')
        need(not terminal.exists() and not (h / 'EXIT.json').exists(), 'terminal appeared after release')
        R.write_atomic(h / 'EXIT.json', {
            'schema': 'native-panel-reconciled-host-exit-v1', 'exit_code': 1,
            'container_exit_code': c['generation']['State']['ExitCode'], 'runner_terminal_matches': False,
            'runtime_terminal_present': False, 'runtime_terminal_provenance': 'missing; not reconstructed',
            'source': 'retained-container-exit', 'container_id': c['generation']['Id'],
            'container_started_at': c['generation']['State']['StartedAt'], 'container_finished_at': c['generation']['State']['FinishedAt'],
            'plan_sha256': c['plan']['sha256'], 'attempt': c['attempt'], 'reconciliation_config_sha256': pin,
            'reconciliation_review': review, 'release_sha256': digest(raw(args.proof)),
            'scientific_acceptance': False, 'reconciled_utc': R.utc(),
        })
        return {'status': 'FAILED_GENERATION_RELEASED', 'scientific_acceptance': False, 'automatic_retry': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('op', choices=['verify', 'reconcile-exited'])
    p.add_argument('--config', required=True); p.add_argument('--sha256', required=True)
    p.add_argument('--review'); p.add_argument('--review-sha256')
    a = p.parse_args()
    review = {'path': a.review, 'sha256': a.review_sha256} if a.review and a.review_sha256 else None
    print(json.dumps(run(a.config, a.sha256, a.op == 'reconcile-exited', review)))


if __name__ == '__main__':
    main()
