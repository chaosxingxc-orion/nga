#!/usr/bin/env python3
"""Host-side guarded restart of an existing reference container on npu/175.

Does not infer chip availability from utilization. Never restarts a successful run.
Use instead of the first run's minimal RESUME_EXACT.sh after allocation changes.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time


def check_restart(config, allocation, container, running, marker, receipt):
    if marker and type(marker.get('rc')) is int and marker['rc'] == 0:
        raise ValueError('Successful run: verify outputs instead of restarting')
    if container['State']['Status'] != 'exited':
        raise ValueError('Container must be confirmed exited')
    chip = config['physical_chip']
    owner = [x for x in allocation['allocation'] if x['chip'] == chip]
    if len(owner) != 1 or not str(config['out']).endswith('/' + owner[0]['run']):
        raise ValueError('Chip ownership no longer belongs to this run; reclaim explicitly first')
    device = '/dev/davinci' + str(chip)
    mapped = [d['PathOnHost'] for d in container['HostConfig'].get('Devices') or []]
    physical = {d for d in mapped if d.startswith('/dev/davinci') and d[len('/dev/davinci'):].isdigit()}
    if physical != {device}:
        raise ValueError('Container physical chip set differs from owned chip')
    if container['Image'] != config['image']:
        raise ValueError('Unexpected container image')
    expected_cmd = ['bash', str(Path(config['out'])/'run.sh')]
    if container['Config']['Cmd'] != expected_cmd:
        raise ValueError('Container command does not match this run wrapper')
    if container['Config'].get('Entrypoint') != receipt['entrypoint']:
        raise ValueError('Container entrypoint differs from launch receipt')
    if container['Id'] != receipt['container_id'] or receipt['command'] != expected_cmd:
        raise ValueError('Container launch receipt mismatch')
    if receipt['image'] != config['image']:
        raise ValueError('Launch receipt image mismatch')
    for c in running:
        if device in [d['PathOnHost'] for d in c['HostConfig'].get('Devices') or []]:
            raise ValueError('Chip mapped by a running container')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', required=True, type=Path)
    ap.add_argument('--container', required=True)
    ap.add_argument('--allocation', type=Path, default=Path('/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json'))
    a = ap.parse_args()
    if socket.gethostname() != 'k8s-node1':
        raise ValueError('Run on authorized host npu/175 (k8s-node1)')
    config = json.loads(a.config.read_text())
    out = Path(config['out'])
    # Caller-supplied run paths are not enough: require a receipt captured at launch.
    receipt = json.loads((out/'LAUNCH_RECEIPT.json').read_text())
    def digest(path):
        h = hashlib.sha256()
        with Path(path).open('rb') as f:
            for chunk in iter(lambda: f.read(4 << 20), b''):
                h.update(chunk)
        return h.hexdigest()
    if digest(a.config) != receipt['config_sha256']:
        raise ValueError('Run config differs from launch receipt')
    for filename, expected in config['files'].items():
        if digest(filename) != expected:
            raise ValueError('Frozen file changed: ' + filename)
    wrapper = str(out/'run.sh')
    if wrapper not in config['files'] or digest(wrapper) != receipt['wrapper_sha256']:
        raise ValueError('Unbound or changed run wrapper')
    with Path(str(a.allocation)+'.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        allocation = json.loads(a.allocation.read_text())
        container = json.loads(subprocess.check_output(['docker', 'inspect', a.container], text=True))[0]
        ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
        running = json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True)) if ids else []
        marker_path = out/'REFERENCE_COMPLETE.json'
        marker = json.loads(marker_path.read_text()) if marker_path.exists() else None
        check_restart(config, allocation, container, running, marker, receipt)
        # Archive stale terminal files while the old container is known stopped.
        for name in ['DONE', 'FAILED', 'REFERENCE_COMPLETE.json']:
            p = out/name
            if p.exists():
                p.rename(out/(name + '.before_restart_' + str(time.time_ns())))
        subprocess.run(['docker', 'start', a.container], check=True)


if __name__ == '__main__':
    main()
