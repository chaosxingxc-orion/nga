#!/usr/bin/env python3
"""Finite engineering handoff: release evidence -> next detached supervisor.

No scientific acceptance, test evaluation or allocation mutation. CPU analysis
does not gate these predeclared engineering jobs. Uncertain observations retry.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def load(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inspect(name):
    r = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=30)
    if r.returncode:
        if 'no such' in r.stderr.lower():
            return None
        raise RuntimeError('Docker observation unavailable')
    return json.loads(r.stdout)[0]


def ready(job):
    out = Path(job['previous_out'])
    release = out / 'attempts/1/RELEASE.json'
    if not release.exists():
        return False
    proof = load(release)
    terminal = load(out / 'TRAIN_EXIT.json')
    receipt = load(out / 'attempts/1/LAUNCH_RECEIPT.json')
    actual = inspect(job['previous_container'])
    if not actual or actual['Id'] != receipt['id'] or actual['Id'] != proof['container_id']:
        raise RuntimeError('previous container identity differs')
    if actual['State']['Status'] != 'exited':
        raise RuntimeError('previous container not exited')
    if terminal['exit_code'] != actual['State']['ExitCode'] or proof['exit_code'] != terminal['exit_code']:
        raise RuntimeError('previous terminal mismatch')
    if proof['chip'] != job['chip'] or proof['scientific_acceptance'] is not False:
        raise RuntimeError('previous release scope mismatch')
    # Release means resource handoff, not success. Preserve failures for CPU analysis.
    return True


def tick(job):
    p = load(job['plan'])
    normalized = dict(p, review_sha256='PENDING')
    pin = hashlib.sha256((json.dumps(normalized, sort_keys=True, indent=2)+'\n').encode()).hexdigest()
    if pin != job['plan_sha256'] or p['schema'] != 'r3-engineering-k1-plan-v1' or p['chip'] != job['chip']:
        raise RuntimeError('next engineering plan changed')
    out = Path(p['out'])
    if (out / 'attempts/1/SUPERVISOR_FAILED.json').exists():
        return 'needs_repair'
    receipt = out / 'attempts/1/LAUNCH_RECEIPT.json'
    if receipt.exists():
        actual = inspect(p['container']+'-a1')
        if actual is None or actual['Id'] != load(receipt)['id']:
            raise RuntimeError('next retained container differs')
        return 'handed_off' if actual['State']['Status'] in ('running','exited') else 'starting'
    supervisor = out / 'SUPERVISOR_RECEIPT.json'
    if supervisor.exists():
        pid = load(supervisor)['pid']
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return 'needs_repair'
        return 'supervisor_starting'
    if not ready(job):
        return 'waiting_release'
    alloc = load(p['allocation'])
    if not any(x['chip'] == job['chip'] for x in alloc['free']):
        return 'waiting_resource'
    with (out/'queue-launch.log').open('ab') as log:
        subprocess.run([sys.executable, '-P', p['launcher'], 'start', '--plan', job['plan'],
                        '--sha256', pin], stdout=log, stderr=subprocess.STDOUT, timeout=45, check=True)
    return 'launch_requested'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--sha256',required=True)
    a=ap.parse_args();path=Path(a.manifest);out=path.parent
    if socket.gethostname()!='k8s-node1':raise RuntimeError('host 175 only')
    with (out/'queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            if sha(path)!=a.sha256:raise RuntimeError('queue manifest changed')
            doc=load(path)
            if sha(__file__) != doc['controller_sha256']:
                raise RuntimeError('queue controller changed')
            states={}
            for job in doc['jobs']:
                try:states[job['id']]={'status':tick(job)}
                except Exception as exc:states[job['id']]={'status':'observation_or_launch_uncertain','error':str(exc)[:300]}
            value={'utc_seconds':time.time(),'jobs':states,'scientific_acceptance':False}
            tmp=out/'digest.pending';tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,out/'digest.json')
            if all(x['status']=='handed_off' for x in states.values()):
                (out/'DONE.json').write_text(json.dumps(value,indent=2)+'\n');return
            time.sleep(10)


if __name__=='__main__':main()
