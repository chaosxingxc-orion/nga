#!/usr/bin/env python3
"""Construct fixed supervisor configuration for an authenticated CPU binding.

This API only prepares configuration; its caller is responsible for scheduling
and recording capture startup and recovery. Paths are derived from the consumer
output so repeated calls reuse the same supervisor and follower lock domains.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

try:
    from . import unified_cpu_consumer_v1 as C
    from . import unified_container_log_follower_v1 as F
    from . import unified_service_supervisor_v1 as S
except ImportError:
    import unified_cpu_consumer_v1 as C
    import unified_container_log_follower_v1 as F
    import unified_service_supervisor_v1 as S


def file_pin(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def immutable(path, value):
    if path.exists():
        C.need(F.typed_equal(C.read(path), value), 'existing capture configuration differs')
    else:
        C.write(path, value)
    return file_pin(path)


def prepare(consumer_ref, controller, python, heartbeat_seconds=10, max_retries=2, retry_backoff_seconds=1):
    """Return pinned config and state paths, after validating the actual binding.

    ``controller`` must be the event service's fixed CPU controller, and the
    interpreter is supplied by its already-validated service configuration.
    No container ID or executable command comes from the caller's config.
    """
    c, _, _, job, _, _, ident = F.authorize(consumer_ref)
    C.need(str(C.safe(controller)) == c['controller'], 'consumer controller differs')
    C.need(type(heartbeat_seconds) is int and 10 <= heartbeat_seconds <= 30, 'invalid heartbeat')
    C.need(type(max_retries) is int and 0 <= max_retries <= 100, 'invalid retry budget')
    C.need(type(retry_backoff_seconds) is int and 1 <= retry_backoff_seconds <= 3600, 'invalid retry backoff')
    executable = C.safe(python)
    C.need(str(executable.resolve()) == str(executable) and executable.is_file() and os.access(executable, os.X_OK), 'invalid interpreter')
    output = C.safe(c['output'] + '.log-capture-v1')
    control = C.safe(c['output'] + '.log-supervisor-v1')
    for path in (output, control):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        C.need(path.is_dir() and path.stat().st_uid == os.geteuid() and path.stat().st_mode & 0o077 == 0, 'capture directory is not private')
    capture = {'schema':'unified-log-capture-v1', 'consumer_config':consumer_ref,
               'output':str(output), 'heartbeat_seconds':heartbeat_seconds,
               'code_pins':F.pins()}
    with C.lock(control/'config.lock'):
        capture_ref = immutable(control/'capture.json', capture)
        supervisor = {'schema':'unified-service-supervisor-v1', 'service':'unified_container_log_follower_v1',
                      'entry':file_pin(F.__file__), 'python':file_pin(executable),
                      'service_config':capture_ref, 'supervisor':file_pin(S.__file__),
                      'state_dir':str(control/'state'), 'heartbeat_seconds':heartbeat_seconds,
                      'max_retries':max_retries, 'retry_backoff_seconds':retry_backoff_seconds}
        config_ref = immutable(control/'supervisor.json', supervisor)
        S.load(config_ref['path'], config_ref['sha256'])
    return {'supervisor_config':config_ref, 'state_dir':supervisor['state_dir'],
            'capture_dir':str(output), 'consumer_job':str(job), 'container_id':ident}
