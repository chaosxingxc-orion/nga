#!/usr/bin/env python3
"""Small CPU-only receipt-driven wrapper for the unmodified DEV comparison CLI."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone

LANES = tuple(f'q{size}-s{seed}' for size in ('0p8b', '2b', '4b', '9b') for seed in (2, 3))
RECEIPTS = tuple(f'{phase}-{kind}.json' for phase in ('infer', 'score') for kind in ('LAUNCH', 'BINDING', 'EXIT'))


def emit(message):
    print(f'{datetime.now(timezone.utc).isoformat()} {message}', flush=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(tmp, p)


def fingerprint(root):
    # Receipt/stat metadata only; never scan weights, readouts or TEST.
    rows = []
    for lane in LANES:
        parent = Path(root) / ('full-' + lane)
        for relative in (*RECEIPTS, 'result/INFERENCE-READY.json', 'result/report.json'):
            p = parent / relative
            try:
                s = p.stat()
                rows.append((lane, relative, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns))
            except FileNotFoundError:
                pass
    return rows


def failed_exit(root):
    for lane in LANES:
        for phase in ('infer', 'score'):
            p = Path(root) / ('full-' + lane) / (phase + '-EXIT.json')
            try:
                data = json.loads(p.read_text())
            except FileNotFoundError:
                continue
            except (ValueError, OSError) as e:
                return f'{p}: unreadable/invalid exit receipt: {e}'
            if not isinstance(data, dict) or any(type(data.get(k)) is not int or data[k] != 0 for k in ('exit_code', 'container_exit_code')):
                return f'{p}: failed or invalid phase exit: {data}'
    return None


def gate(c):
    p = Path(c['verdict'])
    try:
        v = json.loads(p.read_text())
    except FileNotFoundError:
        return False
    except (ValueError, OSError) as e:
        raise RuntimeError(f'invalid verdict {p}: {e}') from e
    if v.get('verdict') != 'PASS_FOR_CONDITIONAL_DEV_CONSUMPTION':
        raise RuntimeError(f'independent verdict is not PASS_FOR_CONDITIONAL_DEV_CONSUMPTION: {v.get("verdict")}')
    expected = c['consumer_sha256']
    if v.get(c['verdict_sha_field']) != expected or sha(c['consumer']) != expected:
        raise RuntimeError('independent verdict/source SHA mismatch (or configured SHA field absent)')
    return True


def inotify_setup(root, verdict):
    # Linux inotify is a latency improvement only; Ceph can miss remote events.
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            return None
        for p in [Path(root), Path(verdict).parent, *[Path(root) / ('full-' + x) for x in LANES], *[Path(root) / ('full-' + x) / 'result' for x in LANES]]:
            if p.is_dir():
                libc.inotify_add_watch(fd, os.fsencode(p), 0x00000fce)
        return fd
    except (OSError, AttributeError):
        return None


def wait(root, verdict, seconds):
    fd = inotify_setup(root, verdict)
    if fd is None:
        time.sleep(seconds)
        return
    try:
        select.select([fd], [], [], seconds)
    finally:
        os.close(fd)


def run(c):
    out = Path(c['output'])
    out.mkdir(parents=True, exist_ok=True)
    last = None
    while True:
        if not gate(c):
            emit('PENDING independent review verdict')
            wait(c['run_root'], c['verdict'], c['fallback_seconds'])
            continue
        failure = failed_exit(c['run_root'])
        if failure:
            raise RuntimeError('REFUSED_CONTRADICTION ' + failure)
        fp = fingerprint(c['run_root'])
        if fp != last:
            last = fp
            # Check even an inference-only terminal: a known contradiction must
            # not be masked by missing scoring evidence in other phases/lanes.
            if not any(row[1] in ('infer-EXIT.json', 'score-EXIT.json') for row in fp):
                emit('PENDING no phase exit receipt')
            else:
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                packet = out / ('packet-' + stamp)
                cmd = [sys.executable, '-B', c['consumer'], '--reference-catalog', c['catalog'],
                       '--run-root', c['run_root'], '--receipt-layout', 'phased', '--output', str(packet)]
                emit('starting comparison packet=' + str(packet))
                packet.mkdir()
                with (packet / 'COMMAND.sh').open('x') as command_file:
                    command_file.write(shlex.join(cmd) + '\n')
                code = subprocess.run(cmd, check=False, cwd='/work' if Path('/work').is_dir() else None).returncode
                if code not in (0, 1, 2):
                    raise RuntimeError(f'consumer process failed exit={code}; inspect log and packet {packet}')
                result = json.loads((packet / 'comparison.json').read_text())
                atomic(out / 'latest.json', {'packet': str(packet), 'status': result.get('status'), 'consumer_exit_code': code})
                emit(f'comparison exit={code} status={result.get("status")} packet={packet}')
                if code == 1:
                    raise RuntimeError('REFUSED_CONTRADICTION: inspect ' + str(packet / 'comparison.json'))
                if code == 0:
                    return 0
        else:
            emit('heartbeat inputs unchanged; comparison skipped')
        wait(c['run_root'], c['verdict'], c['fallback_seconds'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).read_text())
        return run(config)
    except Exception as e:
        emit(f'STOP {type(e).__name__}: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
