#!/usr/bin/env python3
"""In-container train-only driver; always records startup failures and terminal status."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import traceback


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True)
    ap.add_argument('--attempt', type=int, required=True)
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    out = Path(plan['out'])
    attempt = out / 'attempts' / str(a.attempt)
    attempt.mkdir(parents=True, exist_ok=True)
    rc = 125
    process = None
    start = utc()
    try:
        with (attempt / 'run.log').open('ab', buffering=0) as log:
            process = subprocess.Popen(plan['command'], stdout=log, stderr=subprocess.STDOUT,
                                       cwd='/tmp', start_new_session=True)
            def stop(sig, frame):
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            while process.poll() is None:
                with (attempt / 'heartbeat.log').open('a') as hb:
                    hb.write(f'{utc()} alive pid={process.pid} attempt={a.attempt}\n')
                time.sleep(15)
            rc = process.returncode
            if rc == 0 and (out / 'adapter').is_dir():
                # safetensors may export root-owned mode 0600 even with umask 0.
                # The host CPU queue must be able to hash the completed adapter.
                for artifact in (out / 'adapter').iterdir():
                    if artifact.is_symlink() or not artifact.is_file():
                        raise RuntimeError('unexpected exported adapter entry')
                    artifact.chmod(stat.S_IMODE(artifact.stat().st_mode) | 0o044)
    except BaseException:
        rc = 125
        with (attempt / 'run.log').open('a') as log:
            traceback.print_exc(file=log)
    finally:
        terminal = {'exit_code': rc, 'started_utc': start, 'finished_utc': utc(),
                    'attempt': a.attempt, 'scientific_acceptance': False}
        atomic(attempt / 'EXIT.json', terminal)
        (attempt / ('DONE' if rc == 0 else 'FAILED')).write_text(f'rc={rc} utc={utc()}\n')
        atomic(out / 'TRAIN_EXIT.json', terminal)
    return rc


if __name__ == '__main__':
    sys.exit(main())
