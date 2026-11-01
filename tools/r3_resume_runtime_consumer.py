#!/usr/bin/env python3
"""Run the pinned CPU resume reconstruction consumer in a bounded runtime.

The caller supplies the immutable verifier, plan and target pins. This wrapper
only creates heartbeat/terminal evidence in a separate output directory; it
never writes the evidence inputs and never grants experiment approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True)
    ap.add_argument('--plan-sha256', required=True)
    ap.add_argument('--target', required=True)
    ap.add_argument('--target-sha256', required=True)
    ap.add_argument('--validator', required=True)
    ap.add_argument('--validator-sha256', required=True)
    ap.add_argument('--verifier', required=True)
    ap.add_argument('--verifier-sha256', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--log', required=True)
    ap.add_argument('--heartbeat', required=True)
    ap.add_argument('--exit', dest='exit_path', required=True)
    args = ap.parse_args(argv)

    output = Path(args.output)
    log = Path(args.log)
    heartbeat = Path(args.heartbeat)
    terminal = Path(args.exit_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    for p in (output, log, heartbeat, terminal):
        if p.exists():
            raise FileExistsError(str(p))
    expected = {
        'plan': (args.plan, args.plan_sha256),
        'target': (args.target, args.target_sha256),
        'validator': (args.validator, args.validator_sha256),
        'verifier': (args.verifier, args.verifier_sha256),
    }
    for name, (path, digest) in expected.items():
        if sha(path) != digest:
            raise RuntimeError(name + ' hash mismatch before consumer start')
    cmd = [sys.executable, '-B', '-P', args.verifier,
           '--plan', args.plan, '--plan-sha256', args.plan_sha256,
           '--target', args.target, '--target-sha256', args.target_sha256,
           '--validator', args.validator, '--validator-sha256', args.validator_sha256,
           '--output', str(output)]
    started = time.time()
    write(heartbeat, {'schema': 'jev-cpu-reviewer-heartbeat-v1', 'status': 'running',
                      'started_utc': started, 'pid': os.getpid(),
                      'scientific_acceptance': False, 'test_read': False})
    rc = 125
    try:
        with log.open('wb') as stream:
            proc = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.STDOUT)
            write(heartbeat, {'schema': 'jev-cpu-reviewer-heartbeat-v1', 'status': 'running',
                              'started_utc': started, 'pid': proc.pid,
                              'scientific_acceptance': False, 'test_read': False})
            rc = proc.wait()
    except BaseException as exc:
        with log.open('ab') as stream:
            stream.write((type(exc).__name__ + ': ' + str(exc) + '\n').encode())
        rc = 125
    result_hash = sha(output) if rc == 0 and output.exists() else None
    record = {'schema': 'jev-cpu-reviewer-exit-v1', 'exit_code': rc,
              'started_utc': started, 'finished_utc': time.time(),
              'command': cmd, 'plan_sha256': args.plan_sha256,
              'target_sha256': args.target_sha256,
              'validator_sha256': args.validator_sha256,
              'verifier_sha256': args.verifier_sha256,
              'output': str(output), 'output_sha256': result_hash,
              'log': str(log), 'log_sha256': sha(log),
              'scientific_acceptance': False, 'test_read': False}
    write(terminal, record)
    write(heartbeat, {'schema': 'jev-cpu-reviewer-heartbeat-v1',
                      'status': 'done' if rc == 0 else 'failed',
                      'finished_utc': record['finished_utc'], 'exit_code': rc,
                      'scientific_acceptance': False, 'test_read': False})
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
