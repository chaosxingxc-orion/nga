#!/usr/bin/env python3
"""Durable ownership for one final-test execution, not scientific authorization.

A future final evaluator must hold execution() across authorization, scoring,
receipt verification and test-read logging, then call complete(). Existing
FINAL/test-ticket/provenance checks remain required. A crash leaves a reservation;
only the exact same pinned run can resume it. No data is opened by this module.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def safe_path(value):
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts, 'absolute non-traversing path required')
    require(not any(p.is_symlink() for p in (path,*path.parents)), 'symlink path refused')
    return path


def pin(value):
    require(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None, 'invalid SHA256')
    return value


def atomic(path, value):
    fd,tmp = tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


class Reservation:
    def __init__(self, path, value):
        self.path,self.value,self.active = path,value,True

    def complete(self, result_sha256):
        require(self.active, 'execution lock is not held')
        pin(result_sha256)
        require(json.loads(self.path.read_text()) == self.value, 'reservation changed while locked')
        require(self.value['state'] == 'reserved', 'test execution already complete')
        value={**self.value,'state':'completed','verified_result_sha256':result_sha256}
        atomic(self.path,value);self.value=value


@contextmanager
def execution(round_dir, *, model_sha256, suite, run_dir, execution_sha256, final_sha256):
    """Reserve before issuing any test ticket; keep this context for the whole run.

    Pins bind the final selection, exact executable plan and output directory.
    They must come from the independently verified final launcher. This helper
    checks neither that approval nor dataset/model hashes itself.
    """
    root = safe_path(round_dir)
    run = safe_path(run_dir)
    require(suite in ('decision-v7','transfer-v4'), 'unregistered test suite')
    key={'model_sha256':pin(model_sha256),'suite':suite,'partition':'test'}
    owner={'run_dir':str(run),'execution_sha256':pin(execution_sha256),'final_sha256':pin(final_sha256)}
    directory=root/'test-execution-reservations';safe_path(directory);directory.mkdir(parents=True,exist_ok=True)
    record=directory/(digest(key)+'.json');lock=record.with_suffix('.lock')
    safe_path(record);safe_path(lock)
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    reservation=None
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise ValueError('test execution already active') from error
        if record.exists():
            value=json.loads(record.read_text())
            require(value.get('schema') == 'r3-test-execution-reservation-v1' and value.get('key') == key,
                    'invalid test reservation')
            require(value.get('state') == 'reserved', 'test execution already completed or invalid state')
            require(value.get('owner') == owner, 'test partition reserved for another execution; no new run allowed')
        else:
            value={'schema':'r3-test-execution-reservation-v1','key':key,'owner':owner,'state':'reserved'}
            atomic(record,value)
        reservation=Reservation(record,value)
        yield reservation
    finally:
        if reservation is not None:reservation.active=False
        os.close(fd)
