#!/usr/bin/env python3
"""Versioned config entrypoint for reviewed BEV and native DEV packages (host-local).

Configuration and reviewed executable packages are trusted operator inputs, not a
sandbox. No shell commands, remote execution, scientific approvals or automatic
retries are inferred. Existing host supervisor owns claims, detachment and resume.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SCHEMA = 'nga-experiment-entrypoint-v1'
RUNTIME_SCHEMA = 'nga-experiment-entrypoint-v2'
SHA = re.compile(r'[0-9a-f]{64}')


def require(value, message):
    if not value:
        raise ValueError(message)


def safe(path):
    require(isinstance(path, str), 'path must be a string')
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts, 'absolute normalized path required')
    require(not any(q.is_symlink() for q in (p, *p.parents)), 'symlink path refused')
    return p


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    require(path.stat().st_size <= 8 * 1024 * 1024, 'JSON exceeds size bound')
    return json.loads(path.read_text())


def pinned(entry):
    require(isinstance(entry, dict) and set(entry) == {'path', 'sha256'}, 'pin fields differ')
    require(isinstance(entry['sha256'], str) and SHA.fullmatch(entry['sha256']), 'invalid SHA256')
    p = safe(entry['path'])
    require(digest(p) == entry['sha256'], 'pinned content changed: ' + str(p))
    return p


def load_config(path, expected_sha=None):
    path = safe(str(path))
    if expected_sha is not None:
        require(SHA.fullmatch(expected_sha) and digest(path) == expected_sha, 'config SHA256 differs')
    config = read_json(path)
    fields = {'schema', 'kind', 'plan', 'review', 'attempt'}
    require(isinstance(config, dict), 'config must be an object')
    explicit_runtime = config.get('schema') == RUNTIME_SCHEMA
    require(set(config) == fields | ({'host_runtime'} if explicit_runtime else set()),
            'config fields differ')
    require((config['schema'] == SCHEMA and config['kind'] in ('bev-dev-v1', 'bev-public-test-v1'))
            or (explicit_runtime and config['kind'] == 'native-config-dev-v1'), 'unsupported schema/kind')
    if explicit_runtime:
        host_runtime(config)
    require(type(config['attempt']) is int and config['attempt'] >= 1, 'positive integer attempt required')
    plan_path, review_path = pinned(config['plan']), pinned(config['review'])
    plan, review = read_json(plan_path), read_json(review_path)
    if explicit_runtime:
        return load_native(config, plan, review, plan_path)
    public = config['kind'] == 'bev-public-test-v1'
    require(plan.get('schema') == ('bev-public-test-plan-v1' if public else 'bev-dev-plan-v1')
            and plan.get('scientific_acceptance') is False
            and plan.get('test_read') is public
            and plan.get('source_split') == ('public_release_test' if public else 'train_derived_dev'),
            'unsupported experiment scope')
    if public:
        require(plan.get('candidate_selection_allowed') is False and plan.get('expected_questions') == 6518
                and review.get('scope') == 'public_release_test'
                and review.get('candidate_selection_allowed') is False, 'public TEST admission differs')
    require(review.get('activation_authorized') is True and review.get('scientific_acceptance') is False
            and review.get('approved_plan_sha256') == config['plan']['sha256'], 'activation review differs')
    require(config['attempt'] in review.get('attempts', []), 'attempt not approved')
    require(review.get('hashes', {}).get(str(plan_path)) == config['plan']['sha256'], 'review plan binding missing')
    for group in ('code', 'inputs', 'model_files'):
        require(isinstance(plan.get(group), dict) and plan[group], 'missing pinned ' + group)
        for entry in plan[group].values():
            p = pinned(entry)
            require(review.get('hashes', {}).get(str(p)) == entry['sha256'], 'dependency outside review: ' + str(p))
    host = safe(plan['code']['host']['path'])
    runner = safe(plan['code']['runner']['path'])
    require(host.name == ('bev_public_test_host.py' if public else 'bev_host.py')
            and runner.name == ('bev_public_test_runner.py' if public else 'bev_runner.py'), 'unsupported executable adapter')
    out = safe(plan['out'])
    require(host.parent == runner.parent and host.parent.parent == plan_path.parent,
            'package code placement differs')
    require(out.parent == plan_path.parent, 'output must belong to package')
    return config, plan


def host_runtime(config):
    """Explicit host dependency context; never infer it from NPU environment."""
    value = config['host_runtime']
    require(type(value) is dict and set(value) == {'python', 'environment', 'imports'}, 'host runtime fields differ')
    safe(value['python'])
    env = value['environment']
    require(type(env) is dict and all(type(k) is str and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', k)
            and type(v) is str and '\0' not in v for k, v in env.items()), 'invalid host environment')
    require(env.get('PYTHONDONTWRITEBYTECODE') == '1', 'host runtime must disable bytecode writes')
    imports = value['imports']
    require(type(imports) is list and bool(imports) and len(imports) == len(set(imports))
            and all(type(x) is str and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*', x)
                    for x in imports), 'invalid host imports')
    return value


def load_native(config, plan, review, plan_path):
    require(plan.get('schema') == 'native-config-execution-v1' and plan.get('test_read') is False
            and plan.get('scientific_acceptance') is False, 'unsupported native DEV scope')
    require(review.get('verdict') == 'PASS' and review.get('activation_authorized') is True
            and review.get('scientific_acceptance') is False and review.get('test_read') is False
            and review.get('approved_plan_sha256') == config['plan']['sha256'], 'activation review differs')
    require(config['attempt'] in review.get('attempts', []), 'attempt not approved')
    require(type(plan.get('files')) is dict and bool(plan['files']), 'missing dependency closure')
    for name, pin in plan['files'].items():
        pinned({'path': name, 'sha256': pin})
        require(review.get('hashes', {}).get(name) == pin, 'dependency outside review: ' + name)
    for name in ('host', 'runtime'):
        ref = plan['modules'][name]
        pinned(ref)
        require(plan['files'].get(ref['path']) == ref['sha256'], 'module outside dependency closure')
    require(Path(plan['modules']['host']['path']).name == 'bev_native_config_host.py', 'unsupported native host')
    require(safe(plan['out']).parent == plan_path.parent, 'output must belong to package')
    return config, plan


def runtime_environment(config):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    if config.get('schema') == RUNTIME_SCHEMA:
        env.update(host_runtime(config)['environment'])
    return env


def commands(config, plan):
    common = ['--plan', config['plan']['path'], '--sha256', config['plan']['sha256']]
    if config.get('schema') == RUNTIME_SCHEMA:
        runtime = host_runtime(config)
        prefix = [runtime['python'], '-B', '-P']
        host = plan['modules']['host']['path']
        return {
            'imports': prefix + ['-c', 'import importlib,json,sys; [importlib.import_module(n) for n in json.loads(sys.argv[1])]', json.dumps(runtime['imports'])],
            'verify': prefix + [host, 'verify', *common],
            'preflight': prefix + [host, 'preflight', *common],
            'start': prefix + [host, 'start', *common, '--review', config['review']['path'],
                              '--review-sha256', config['review']['sha256'], '--attempt', str(config['attempt'])],
        }
    return {
        'verify': [sys.executable, '-B', '-P', plan['code']['runner']['path'], 'verify', *common],
        'start': [sys.executable, '-B', '-P', plan['code']['host']['path'], 'start', *common,
                  '--review', config['review']['path'], '--review-sha256', config['review']['sha256'],
                  '--attempt', str(config['attempt'])],
    }


def status(config, plan):
    out = safe(plan['out'])
    host = out / 'host_attempts' / str(config['attempt'])
    runner = out / 'attempts' / str(config['attempt'])
    names = {'host_exit': host / 'EXIT.json', 'runner_exit': runner / 'EXIT.json',
             'release': host / 'RELEASE.json', 'launch': host / 'LAUNCH_RECEIPT.json',
             'service': host / 'SERVICE.json', 'heartbeat': host / 'heartbeat.json',
             'complete': out / 'COMPLETE.json', 'error': host / 'SUPERVISOR_ERROR.json'}
    evidence = {key: {'path': str(path), 'value': read_json(safe(str(path)))}
                for key, path in names.items() if path.exists()}
    if 'error' in evidence or any(evidence[k]['value'].get('exit_code') != 0
                                for k in ('host_exit', 'runner_exit') if k in evidence):
        state = 'failed_or_needs_reconciliation'
    elif all(k in evidence for k in ('host_exit', 'runner_exit', 'release', 'complete')):
        state = 'terminal_artifacts_present_requires_result_validation'
    elif 'launch' in evidence:
        state = 'launched_live_state_not_checked'
    elif 'service' in evidence:
        state = 'supervisor_requested_live_state_not_checked'
    else:
        state = 'not_started_or_no_receipts'
    return {'status': state, 'evidence': evidence, 'scientific_acceptance': False,
            'note': 'Receipt snapshot only; no Docker, device ownership or result validation inferred.'}


def execute(op, config_path, expected_sha=None):
    require(op != 'start' or expected_sha is not None, 'start requires --config-sha256')
    config, plan = load_config(config_path, expected_sha)
    command = commands(config, plan)
    if op == 'status':
        return status(config, plan)
    if op == 'dry-run':
        return {'status': 'validated_dry_run', 'commands': command, 'writes_performed': False}
    # The existing runner performs its actual protocol and request validation.
    # No run/start API is called by validate.
    env = runtime_environment(config)
    for stage in ('imports', 'preflight'):
        if stage in command:
            check = subprocess.run(command[stage], env=env, capture_output=True, text=True, timeout=180)
            require(check.returncode == 0, 'host runtime ' + stage + ' failed before start: ' + check.stderr[-1500:])
    result = subprocess.run(command['verify'], env=env, capture_output=True, text=True, timeout=180)
    require(result.returncode == 0, 'existing runner verification failed: ' + result.stderr[-1500:])
    if op == 'validate':
        return {'status': 'validated', 'runner_verification': result.stdout[-500:], 'writes_performed': False}
    require(op == 'start', 'unsupported operation')
    # Recheck config and pins before invoking the original guarded start API.
    config, plan = load_config(config_path, expected_sha)
    require(not (safe(plan['out']) / 'host_attempts' / str(config['attempt'])).exists(),
            'attempt already exists; inspect status, do not launch again')
    result = subprocess.run(commands(config, plan)['start'], env=env, capture_output=True, text=True, timeout=180)
    require(result.returncode == 0, 'guarded launcher failed; inspect receipts before retry: ' + result.stderr[-1500:])
    return {'status': 'guarded_start_returned', 'launcher_output': result.stdout[-1500:],
            'scientific_acceptance': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('validate', 'dry-run', 'start', 'status'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256')
    args = parser.parse_args(argv)
    try:
        result = execute(args.op, args.config, args.config_sha256)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'rejected', 'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
