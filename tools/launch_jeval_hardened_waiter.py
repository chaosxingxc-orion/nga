#!/usr/bin/env python3
"""Guarded launch/resume for a frozen waiter directory.

Operational read-only source protection does not isolate Docker API capabilities.
The waiter uses inspect GET requests; the socket remains a privileged interface.
"""
from pathlib import Path
import fcntl
import http.client
import importlib.util
import json
import re
import socket
import subprocess
import sys

s = importlib.util.spec_from_file_location('waiter', Path(__file__).with_name('jeval_hardened_waiter.py'))
w = importlib.util.module_from_spec(s)
s.loader.exec_module(w)


def lookup_container(name):
    """Only an HTTP 404 establishes absence; CLI wording is not a protocol."""
    w.require(re.fullmatch(r'[A-Za-z0-9_.-]+', name), 'Invalid container name')
    connection = http.client.HTTPConnection('localhost', timeout=30)
    connection.sock = socket.socket(socket.AF_UNIX)
    connection.sock.settimeout(30)
    try:
        connection.sock.connect('/var/run/docker.sock')
        connection.request('GET', '/containers/' + name + '/json')
        response = connection.getresponse()
        payload = response.read()
        if response.status == 404:
            return None
        w.require(response.status == 200, 'Docker lookup failed; absence not established')
        return json.loads(payload)
    finally:
        connection.close()


def launch(p, resume=False):
    plan = w.load(p / 'plan.json'); ph = w.sha(p / 'plan.json')
    spec = w.load(p / 'CONTAINER_SPEC.json')
    with (p / 'launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        w.require(w.load(p / 'PARENT_REVIEW.json')['approved_plan_sha256'] == ph, 'Plan approval differs')
        for fp, expected in plan['files'].items():w.require(w.sha(fp) == expected, 'Frozen dependency changed: ' + fp)
        terminal = w.load(p / 'COMPLETE.json') if (p / 'COMPLETE.json').exists() else None
        w.require(terminal is None or terminal.get('rc') == 0, 'Existing failed terminal preserved; use a reviewed new generation')
        intent = dict(plan_sha256=ph, container=plan['container'], spec_sha256=w.sha(p / 'CONTAINER_SPEC.json'))
        ip = p / 'LAUNCH_INTENT.json'
        if ip.exists():w.require(w.load(ip) == intent, 'Launch intent differs')
        else:w.no_clobber_json(ip, intent)
        d = lookup_container(plan['container'])
        if d is None:
            w.require(not (p / 'LAUNCH_RECEIPT.json').exists(), 'Recorded container missing')
            w.require(not resume, 'Cannot resume absent container')
            args = ['docker', 'create', '--name', plan['container'], '--label', 'nga.waiter.plan=' + ph, '--network', 'none', '--shm-size', '67108864', '--entrypoint', 'bash']
            for b in spec['HostConfig']['Binds']:args += ['-v', b]
            for e in spec['Config']['Env']:args += ['-e', e]
            args += [plan['image']] + spec['Config']['Cmd']
            cid = subprocess.check_output(args, text=True).strip()
            d = lookup_container(cid)
            w.require(d is not None, 'Created container missing')
        expected = dict(spec, container_id=d['Id']); w.binding(d, expected)
        w.cpu_mount_binding(d, p)
        w.require(d['Name'] == '/' + plan['container'] and not d['HostConfig'].get('Devices') and d['Config']['Labels'].get('nga.waiter.plan') == ph, 'Waiter ownership differs')
        receipt = dict(container_id=d['Id'], plan_sha256=ph, wrapper_sha256=w.sha(plan['wrapper']))
        rp = p / 'LAUNCH_RECEIPT.json'
        if rp.exists():w.require(w.load(rp) == receipt, 'Launch receipt differs')
        else:
            w.require(d['State']['Status'] == 'created', 'Cannot adopt already-started container')
            w.no_clobber_json(rp, receipt)
        status = d['State']['Status']
        if status == 'running':print('already running');sys.exit(0)
        if status == 'exited':
            if d['State']['ExitCode'] == 0:
                w.require(terminal is not None and terminal['plan_sha256'] == ph, 'Successful container lacks matching terminal')
                print('already completed; original evidence preserved');sys.exit(0)
            w.require(resume and d['State']['ExitCode'] != 0, 'Interrupted resume required')
            review = w.load(p / 'RESUME_REVIEW.json')
            w.require(review['approved_plan_sha256'] == ph and review['container_id'] == d['Id'] and review['finished_at'] == d['State']['FinishedAt'], 'Interrupted container review differs')
            if (p / 'EXIT').exists():
                w.require(review['exit_sha256'] == w.sha(p / 'EXIT') and re.fullmatch(r'rc=(?:[1-9][0-9]*|-[1-9][0-9]*) utc=\S+\n?', (p / 'EXIT').read_text()), 'Interrupted EXIT review differs')
            else:w.require(review.get('exit_sha256') is None, 'Missing EXIT differs from review')
        else:w.require(status == 'created', 'Unexpected container state')
        subprocess.check_call(['docker', 'start', d['Id']]); print(d['Id'])


if __name__ == '__main__':
    launch(Path(__file__).resolve().parent, '--resume' in sys.argv)
