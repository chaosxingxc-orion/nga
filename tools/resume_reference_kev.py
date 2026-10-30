#!/usr/bin/env python3
"""Host-side guarded restart of an existing reference container on npu/175.

Does not infer chip availability from utilization. Never restarts a successful run.
Use instead of the first run's minimal RESUME_EXACT.sh after allocation changes.
"""
import argparse
import fcntl
import json
from pathlib import Path
import socket
import subprocess
import time


def check_restart(config, allocation, container, running, marker):
    if marker and type(marker.get('rc')) is int and marker['rc'] == 0:
        raise ValueError('Successful run: verify outputs instead of restarting')
    if container['State']['Status'] != 'exited':
        raise ValueError('Container must be confirmed exited')
    chip = config['physical_chip']
    owner = [x for x in allocation['allocation'] if x['chip'] == chip]
    if len(owner) != 1 or not str(config['out']).endswith('/' + owner[0]['run']):
        raise ValueError('Chip ownership no longer belongs to this run; reclaim explicitly first')
    device = '/dev/davinci' + str(chip)
    if device not in [d['PathOnHost'] for d in container['HostConfig'].get('Devices') or []]:
        raise ValueError('Container does not map expected physical chip')
    if container['Image'] != config['image']:
        raise ValueError('Unexpected container image')
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
    with Path(str(a.allocation)+'.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        allocation = json.loads(a.allocation.read_text())
        container = json.loads(subprocess.check_output(['docker', 'inspect', a.container], text=True))[0]
        ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
        running = json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True)) if ids else []
        marker_path = out/'REFERENCE_COMPLETE.json'
        marker = json.loads(marker_path.read_text()) if marker_path.exists() else None
        check_restart(config, allocation, container, running, marker)
        # Archive stale terminal files while the old container is known stopped.
        for name in ['DONE', 'FAILED', 'REFERENCE_COMPLETE.json']:
            p = out/name
            if p.exists():
                p.rename(out/(name + '.before_restart_' + str(time.time_ns())))
        subprocess.run(['docker', 'start', a.container], check=True)


if __name__ == '__main__':
    main()
