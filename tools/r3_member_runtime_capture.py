#!/usr/bin/env python3
"""Capture retained DEV runtime evidence; never author member adjudication."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shlex
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def observe(host, argv):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o',
                             'ConnectTimeout=15', host, shlex.join(argv)],
                            capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('runtime observation failed; no retry or launch authorized')
    return json.loads(result.stdout)


def validate_container(actual, execution, launch):
    if len(actual) != 1:
        raise ValueError('single retained container required')
    item = actual[0]
    state = item['State']
    if (item['Id'] != launch['id'] or
            item['Name'] != '/' + execution['container'] + '-a1' or
            state.get('Status') != 'exited' or state.get('Running') is not False or
            type(state.get('ExitCode')) is not int or state['ExitCode'] != 0 or
            state.get('OOMKilled') or state.get('Error') or
            item['HostConfig'].get('AutoRemove')):
        raise ValueError('retained successful execution identity differs')


def capture(config_path, config_pin, names, output, host='npu'):
    if host != 'npu' or sha(config_path) != config_pin:
        raise ValueError('host/config pin differs')
    config = json.loads(Path(config_path).read_text())
    if len(names) != len(set(names)) or any(n not in config['members'] for n in names):
        raise ValueError('unknown or duplicate member')
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    for name in names:
        member = config['members'][name]
        execution_path = Path(member['execution'])
        execution = json.loads(execution_path.read_text())
        root = Path(execution['out'])
        attempt = root / 'attempts/1'
        end = json.loads((root / 'ENGINEERING_EVAL_EXIT.json').read_text())
        if type(end.get('exit_code')) is not int or end['exit_code'] != 0:
            raise ValueError('successful driver terminal required')
        launch = json.loads((attempt / 'LAUNCH_RECEIPT.json').read_text())
        actual = observe(host, ['docker', 'inspect', launch['id']])
        validate_container(actual, execution, launch)
        image = observe(host, ['docker', 'image', 'inspect', actual[0]['Image']])
        daemon = observe(host, ['docker', 'info', '--format', '{{json .}}'])
        directory = output / name
        directory.mkdir()
        observations = {}
        for key, value in [('container', actual), ('image', image), ('daemon', daemon)]:
            path = directory / (key + '.json')
            put(path, value)
            observations[key] = {'path': str(path), 'sha256': sha(path)}
        paths = [execution_path, Path(execution['spec']), root / 'ENGINEERING_EVAL_EXIT.json']
        paths += [attempt / f for f in ('EXIT.json', 'CLAIM.json', 'RELEASE.json',
                                       'LAUNCH_RECEIPT.json', 'SUPERVISOR_DONE.json')]
        inventory = {str(p): sha(p) for p in paths}
        inventory.update({r['path']: r['sha256'] for r in observations.values()})
        record = {'member': name, 'execution': str(execution_path),
                  'execution_sha256': inventory[str(execution_path)],
                  'evaluation_observations': observations, 'files': inventory,
                  'independent_adjudication': None, 'scientific_acceptance': False,
                  'test_read': False}
        put(directory / 'CAPTURE.json', record)
        records[name] = {'path': str(directory / 'CAPTURE.json'),
                         'sha256': sha(directory / 'CAPTURE.json')}
    put(output / 'INDEX.json', {'schema': 'r3-member-runtime-capture-v1',
        'config_sha256': config_pin, 'members': records,
        'captured_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'scientific_acceptance': False, 'test_read': False,
        'scope': 'Observed runtime only; unchanged qualifier replay and independent adjudication required'})
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--member', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = capture(args.config, args.sha256, args.member, args.output)
    print(json.dumps({'captured_members': list(result), 'scientific_acceptance': False}))
