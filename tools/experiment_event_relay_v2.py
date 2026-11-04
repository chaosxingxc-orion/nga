"""Versioned relay requiring a consumer readiness handshake before SIGUSR1.

Retains v1 event evidence/publication/state semantics. Never deploy against a
launcher-authored identity receipt alone. The ready receipt must be written by
the consumer after installing its handler; kernel SigCgt independently checks
that SIGUSR1 is caught at the moment of observation, not its handler semantics.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import signal
import threading

BASE_SHA = 'e70193477b98c236b78fdf92bb403a4c05a108cf1d460bc9cb8b0d31db52821c'
_path = Path(__file__).resolve().with_name('experiment_event_relay_v1.py')
if hashlib.sha256(_path.read_bytes()).hexdigest() != BASE_SHA:
    raise ValueError('unreviewed relay v1 dependency')
_spec = importlib.util.spec_from_file_location('event_relay_v1_dependency', _path)
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)


def handshake(target):
    """Check the exact ready receipt, without treating existence as readiness."""
    data = V.raw(target['service']['path'])
    V.need(hashlib.sha256(data).hexdigest() == target['service']['sha256'],
           'service receipt changed')
    # V.read additionally refuses ambiguous duplicate keys/non-finite JSON.
    receipt = V.read(target['service']['path'])
    V.need(V.raw(target['service']['path']) == data, 'ready receipt changed during read')
    expected = V.normalized(target['identity'])
    V.need(isinstance(receipt.get('process'), dict) and
           V.normalized(receipt['process']) == expected, 'service identity differs')
    V.need(receipt.get('signals', {}).get('wake') == 'SIGUSR1',
           'consumer ready handshake absent')
    return expected


def kernel_handler_present(pid):
    """Linux process-level signal disposition, not pending or ignored signals."""
    rows = (Path('/proc') / str(pid) / 'status').read_text().splitlines()
    caught = [row.split(':', 1)[1].strip() for row in rows if row.startswith('SigCgt:')]
    V.need(len(caught) == 1, 'kernel signal disposition unavailable')
    V.need(int(caught[0], 16) & (1 << (signal.SIGUSR1 - 1)),
           'consumer SIGUSR1 handler not installed')


def check_target(target, send=False):
    expected = handshake(target)
    fd = os.pidfd_open(expected['pid'])
    try:
        V.need(V.identity(expected['pid']) == expected, 'stale process identity')
        kernel_handler_present(expected['pid'])
        V.need(handshake(target) == expected, 'ready receipt changed before wake')
        V.need(V.identity(expected['pid']) == expected, 'stale process identity')
        if send:
            signal.pidfd_send_signal(fd, signal.SIGUSR1)
    finally:
        os.close(fd)
    return expected


def wake(target):
    check_target(target, send=True)


def validate(config, live=False):
    V.need(config['schema'] == 'experiment-event-relay-v2', 'relay v2 contract required')
    V.validate(dict(config, schema='experiment-event-relay-v1'))
    for event in config['events']:
        handshake(event['target'])
        if live:
            check_target(event['target'])
    return config


def tick(config, state, save):
    return V.tick(config, state, save, signaler=wake)


def run(config, pin, once=False, preflight=False):
    V.need(V.sha(config) == pin, 'config changed')
    c = validate(V.read(config), live=preflight)
    if preflight:
        return {'status': 'READY_OBSERVED', 'targets': len(c['events']),
                'signals_sent': 0, 'npu_launched': False}
    root = V.safe(c['output'])
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'relay.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state_path = root / 'STATE.json'
        state = V.read(state_path) if state_path.exists() else dict(config_sha256=pin, events={})
        V.need(state['config_sha256'] == pin, 'state generation differs')
        V.need(set(state['events']) <= {e['id'] for e in c['events']}, 'foreign events')
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        V.put(root / 'SERVICE.json', dict(process=V.identity(os.getpid()), config_sha256=pin))
        V.put(root / 'RELAUNCH.json', dict(command=[os.sys.executable, '-B', '-P',
              str(Path(__file__).resolve()), '--config', str(Path(config).resolve()),
              '--sha256', pin], resume='Same config/state only; blocked events need reconciliation.'))
        rc = 1
        try:
            while not stop.is_set():
                V.need(V.sha(config) == pin, 'config changed while live')
                tick(c, state, lambda d: V.put(state_path, d))
                V.put(root / 'digest.json', dict(utc_seconds=V.time.time(),
                      states={k: v['state'] for k, v in state['events'].items()},
                      pending=len(c['events'])-len(state['events']), npu_launched=False))
                if once:
                    break
                stop.wait(c['poll_seconds'])
            rc = 0
        finally:
            V.put(root / 'EXIT.json', dict(exit_code=rc, utc_seconds=V.time.time(), npu_launched=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    result = run(args.config, args.sha256, args.once, args.preflight)
    if result is not None:
        print(V.json.dumps(result))
