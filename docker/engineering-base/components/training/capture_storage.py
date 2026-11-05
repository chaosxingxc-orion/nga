"""CPU-only, fail-closed building block for numerical capture; not loop integration.

This module deliberately rejects accelerator tensors.  Device copy staging has not
been qualified, and this code must not be presented as a production capture gate.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import functools
import struct
import stat
import sys

MAX_SHARD = 8 * 1024 * 1024


def _require_little_endian():
    # The v1 format has no byte-order field. Its only admitted wire encoding is
    # little-endian; never silently reinterpret old files on a different host.
    if sys.byteorder != 'little':
        raise ValueError('capture storage requires little-endian host')


def _read_bounded(directory, name, limit):
    try:
        fd = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise ValueError('missing or invalid artifact') from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise ValueError('artifact integrity failure: invalid size or type')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            data = f.read(limit + 1)
        if len(data) != st.st_size or len(data) > limit:
            raise ValueError('artifact integrity failure: changed size')
        return data
    finally:
        os.close(fd)


def _canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish(directory, name, data):
    """Publish without replacing an existing artifact, including after a crash."""
    partial = directory / ('.' + name + '.partial')
    with partial.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.link(partial, directory / name, follow_symlinks=False)
    os.unlink(partial)
    _sync_dir(directory)


def fail_closed(fn):
    @functools.wraps(fn)
    def wrapped(self, *args, **kwargs):
        if self.failed or self.complete:
            raise ValueError('attempt is terminal')
        try:
            return fn(self, *args, **kwargs)
        except BaseException as exc:
            self.fail(exc)
            raise
    return wrapped


class CPUAttempt:
    """Write ordered float32 CPU tensors under a caller-frozen explicit schema."""
    def __init__(self, parent, attempt_id, expected, quota):
        _require_little_endian()
        parent = Path(parent)
        if not parent.is_absolute() or parent.resolve() != parent or not parent.is_dir():
            raise ValueError('parent must be an existing canonical directory')
        if not isinstance(attempt_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', attempt_id):
            raise ValueError('invalid attempt id')
        if type(quota) is not int or quota <= 0:
            raise ValueError('positive byte quota required')
        if not isinstance(expected, list) or not expected:
            raise ValueError('nonempty expected schema required')
        for e in expected:
            if (not isinstance(e, dict) or set(e) not in ({'name', 'shape'}, {'name', 'shape', 'dtype'}) or
                not isinstance(e['name'], str) or not e['name'] or
                e.get('dtype', 'float32') not in ('float32', 'float64') or
                not isinstance(e['shape'], list) or
                any(type(x) is not int or x < 0 for x in e['shape'])):
                raise ValueError('invalid expected schema')
        if len({e['name'] for e in expected}) != len(expected):
            raise ValueError('duplicate tensor name')
        self.failed = False
        self.complete = False
        self.expected = json.loads(_canonical(expected))
        self.quota = quota
        self.used = 0
        self.records = []
        self.directory = parent / attempt_id
        self.directory.mkdir(mode=0o700)
        _sync_dir(parent)

    def _write(self, name, data):
        if self.used + len(data) > self.quota:
            raise ValueError('capture quota exceeded')
        _publish(self.directory, name, data)
        self.used += len(data)

    def fail(self, exc):
        if self.failed or self.complete:
            return
        self.failed = True
        try:
            _publish(self.directory, 'FAILED.json', _canonical({'error_type': type(exc).__name__, 'error': str(exc)[:1024]}))
        except BaseException:
            pass  # Missing COMPLETE remains authoritative if the filesystem failed.

    @fail_closed
    def tensor(self, name, value):
        import torch
        i = len(self.records)
        if i >= len(self.expected) or self.expected[i]['name'] != name:
            raise ValueError('unexpected tensor order or name')
        if (not isinstance(value, torch.Tensor) or value.device.type != 'cpu' or
            str(value.dtype) != 'torch.' + self.expected[i].get('dtype', 'float32') or list(value.shape) != self.expected[i]['shape'] or
            not value.is_contiguous()):
            raise ValueError('tensor device, dtype, shape or layout mismatch')
        flat = value.detach().view(-1)
        shards = []
        itemsize = value.element_size()
        for offset in range(0, flat.numel(), MAX_SHARD // itemsize):
            part = flat[offset:offset + MAX_SHARD // itemsize]
            if not bool(torch.isfinite(part).all()):
                raise ValueError('nonfinite tensor')
            data = part.numpy().tobytes(order='C')
            filename = f'{i:06d}-{len(shards):06d}.bin'
            self._write(filename, data)
            shards.append({'file': filename, 'length': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            del data, part
        self.records.append({'name': name, 'shape': list(value.shape), 'dtype': self.expected[i].get('dtype', 'float32'), 'shards': shards})

    @fail_closed
    def finish(self):
        if len(self.records) != len(self.expected):
            raise ValueError('incomplete attempt')
        manifest = _canonical({'schema': 'cpu-capture-storage-experimental-v1', 'records': self.records})
        self._write('manifest.json', manifest)
        self._write('COMPLETE.json', _canonical({'manifest_sha256': hashlib.sha256(manifest).hexdigest()}))
        self.complete = True


def validate(directory, expected):
    """Authenticate exact ordering, files, finite values and all payload hashes."""
    import torch
    _require_little_endian()
    directory = Path(directory)
    if directory.resolve() != directory or not directory.is_dir():
        raise ValueError('invalid attempt directory')
    def read(name, limit):
        return _read_bounded(directory, name, limit)
    def strict(raw):
        def pairs(items):
            d = {}
            for k, v in items:
                if k in d: raise ValueError('duplicate JSON key')
                d[k] = v
            return d
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    terminal = strict(read('COMPLETE.json', 4096))
    raw = read('manifest.json', 4 * 1024 * 1024)
    if terminal != {'manifest_sha256': hashlib.sha256(raw).hexdigest()}:
        raise ValueError('invalid terminal')
    obj = strict(raw)
    if set(obj) != {'schema', 'records'} or obj['schema'] != 'cpu-capture-storage-experimental-v1' or len(obj['records']) != len(expected):
        raise ValueError('invalid manifest')
    files = {'COMPLETE.json', 'manifest.json'}
    for i, (record, spec) in enumerate(zip(obj['records'], expected)):
        if set(record) != {'name', 'shape', 'dtype', 'shards'} or record['name'] != spec['name'] or record['shape'] != spec['shape'] or record['dtype'] != spec.get('dtype', 'float32'):
            raise ValueError('topology mismatch')
        itemsize = 8 if spec.get('dtype', 'float32') == 'float64' else 4
        length = math.prod(spec['shape']) * itemsize
        count = (length + MAX_SHARD - 1) // MAX_SHARD
        if len(record['shards']) != count: raise ValueError('shard count mismatch')
        for j, shard in enumerate(record['shards']):
            filename = f'{i:06d}-{j:06d}.bin'
            size = min(MAX_SHARD, length - j * MAX_SHARD)
            if set(shard) != {'file', 'length', 'sha256'} or shard['file'] != filename or shard['length'] != size:
                raise ValueError('shard identity mismatch')
            try:
                fd = os.open(directory / filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except OSError as exc:
                raise ValueError('missing or invalid artifact') from exc
            try:
                st = os.fstat(fd)
                if not stat.S_ISREG(st.st_mode) or st.st_size != size:
                    raise ValueError('shard integrity failure')
                digest = hashlib.sha256()
                remaining = size
                while remaining:
                    data = os.read(fd, min(64 * 1024, remaining))
                    if not data or len(data) % itemsize:
                        raise ValueError('shard integrity failure')
                    digest.update(data)
                    if any(not math.isfinite(v[0]) for v in struct.iter_unpack('=d' if itemsize == 8 else '=f', data)):
                        raise ValueError('nonfinite tensor')
                    remaining -= len(data)
                if os.read(fd, 1) or digest.hexdigest() != shard['sha256']:
                    raise ValueError('shard integrity failure')
            finally:
                os.close(fd)
            files.add(filename)
    if {p.name for p in directory.iterdir()} != files:
        raise ValueError('extra artifact')
    return obj
