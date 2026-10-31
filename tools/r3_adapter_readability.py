#!/usr/bin/env python3
"""Make completed adapters readable to the CPU queue, preserving byte hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import time


def repair(root):
    terminal = root / 'TRAIN_EXIT.json'
    if not terminal.exists():
        return {'status': 'waiting_training'}
    end = json.loads(terminal.read_text())
    if end['exit_code'] != 0:
        return {'status': 'training_failed', 'exit_code': end['exit_code']}
    adapter = root / 'adapter'
    if not (adapter / 'adapter_model.safetensors').is_file():
        raise ValueError('successful training lacks adapter')
    rows = []
    for p in sorted(adapter.iterdir()):
        if p.is_symlink() or not p.is_file():
            raise ValueError('unexpected adapter entry')
        before = hashlib.sha256(p.read_bytes()).hexdigest()
        mode = stat.S_IMODE(p.stat().st_mode)
        p.chmod(mode | 0o044)
        after = hashlib.sha256(p.read_bytes()).hexdigest()
        if before != after:
            raise ValueError('adapter bytes changed during permission repair')
        rows.append({'path': str(p), 'before_mode': oct(mode),
                     'after_mode': oct(mode | 0o044), 'sha256': after})
    return {'status': 'readable', 'bytes_unchanged': True, 'files': rows,
            'scientific_acceptance': False}


def save(path, data):
    temp = path.with_suffix('.pending')
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--runs', nargs='+', required=True)
    ap.add_argument('--out', required=True); a = ap.parse_args()
    out = Path(a.out); out.mkdir(exist_ok=True)
    states = {}
    while True:
        for value in a.runs:
            if states.get(value, {}).get('status') in ('readable', 'training_failed', 'repair_failed'):
                continue
            try:
                states[value] = repair(Path(value))
            except Exception as e:
                states[value] = {'status': 'repair_failed', 'error': str(e)[:300]}
        save(out / 'digest.json', {'utc_seconds': time.time(), 'jobs': states})
        if all(x['status'] != 'waiting_training' for x in states.values()):
            rc = int(any(x['status'] == 'repair_failed' for x in states.values()))
            save(out / 'EXIT.json', {'exit_code': rc, 'utc_seconds': time.time()})
            return rc
        time.sleep(10)


if __name__ == '__main__':
    raise SystemExit(main())
