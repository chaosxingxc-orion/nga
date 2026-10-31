"""Bind JSON and digest to one immutable, no-symlink evidence snapshot."""
import hashlib
import json
import os
from pathlib import Path
import stat


def require(value, message):
    if not value:
        raise ValueError(message)


def open_regular(path):
    path = Path(os.path.abspath(path))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nxt
        result = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    except OSError as exc:
        raise ValueError('Evidence path is missing, symlinked or inaccessible: ' + str(path)) from exc
    finally:
        os.close(fd)
    if not stat.S_ISREG(os.fstat(result).st_mode):
        os.close(result)
        raise ValueError('Evidence is not a regular file: ' + str(path))
    return result


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


class Snapshot:
    def __init__(self, path):
        self.path = Path(os.path.abspath(path))
        with os.fdopen(open_regular(self.path), 'rb') as f:
            self.identity = identity(os.fstat(f.fileno()))
            keep = self.identity[2] <= 64 * 2**20
            parts = []; digest = hashlib.sha256()
            for block in iter(lambda: f.read(4 << 20), b''):
                digest.update(block)
                if keep: parts.append(block)
            require(identity(os.fstat(f.fileno())) == self.identity, 'Evidence changed while reading')
        self.data = b''.join(parts) if keep else None
        self.sha256 = digest.hexdigest()
        self.verify(metadata_only=True)

    def json(self):
        require(self.data is not None, 'JSON evidence exceeds bounded size')
        value = json.loads(self.data)
        self.verify(metadata_only=True)
        return value

    def verify(self, metadata_only=False):
        with os.fdopen(open_regular(self.path), 'rb') as f:
            require(identity(os.fstat(f.fileno())) == self.identity, 'Evidence object changed: ' + str(self.path))
            if not metadata_only:
                digest = hashlib.sha256()
                for block in iter(lambda: f.read(4 << 20), b''): digest.update(block)
                require(digest.hexdigest() == self.sha256, 'Evidence bytes changed: ' + str(self.path))
            require(identity(os.fstat(f.fileno())) == self.identity, 'Evidence changed during verification')


class Evidence:
    def __init__(self, delegate=None):
        self.delegate = delegate
        self.snapshots = {}

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def snapshot(self, path):
        key = os.path.abspath(path)
        if key not in self.snapshots: self.snapshots[key] = Snapshot(key)
        return self.snapshots[key]

    def load(self, path): return self.snapshot(path).json()
    def sha(self, path): return self.snapshot(path).sha256
    def frozen(self, files):
        for path, digest in files.items():
            require(self.sha(path) == digest, 'Frozen file changed: ' + str(path))
    def verify(self, metadata_only=False):
        for item in list(self.snapshots.values()): item.verify(metadata_only=metadata_only)

    def docker(self, method, *args, **kwargs):
        if method != 'GET': self.verify(metadata_only=True)
        return self.delegate.docker(method, *args, **kwargs)

    def atomic(self, path, value):
        self.verify(metadata_only=True)
        if Path(path).name in {'COMPLETE.json', 'FAILURE.json', 'report.json'}:
            result = publish_new(path, value)
        else:
            result = self.delegate.atomic(path, value)
        self.snapshots.pop(os.path.abspath(path), None)
        return result


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def durable_mkdir(path):
    """Persist every directory entry from / to path, including existing links.

    This deliberately does not rely on fsync of a new child directory to persist
    its name in its own parent. All traversal rejects symlinks.
    """
    path = Path(os.path.abspath(path))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            try: os.mkdir(part, 0o755, dir_fd=fd)
            except FileExistsError: pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                os.fsync(child)
                os.fsync(fd)
            except BaseException:
                os.close(child)
                raise
            os.close(fd); fd = child
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_move(source, target):
    """Preserve a historical artifact; persist both sides and destination chain.

    Files use a no-overwrite hard link committed before removing the old name.
    A crash between those actions leaves two recoverable copies, never zero.
    Directory moves are used only under the CPU task's exclusive lock into a
    unique previously absent history path.
    """
    source, target = Path(source), Path(target)
    require(not source.is_symlink() and not target.is_symlink(),
            'Historical move source/target differs')
    durable_mkdir(target.parent)
    durable_mkdir(source.parent)
    if target.exists():
        require(source.is_file() and target.is_file(), 'Historical directory target already exists')
        left, right = Snapshot(source), Snapshot(target)
        require(left.identity[:2] == right.identity[:2] and left.sha256 == right.sha256,
                'Ambiguous historical duplicate: source and target are not the same committed link')
        left.verify(); right.verify()
        sync_directory(target.parent)
        source.unlink(); sync_directory(source.parent)
        return
    if source.is_dir():
        os.rename(source, target)
        sync_directory(target.parent)
        sync_directory(source.parent)
    else:
        with os.fdopen(open_regular(source), 'rb') as stream:
            os.fsync(stream.fileno())
        os.link(source, target, follow_symlinks=False)
        sync_directory(target.parent)
        source.unlink()
        sync_directory(source.parent)


def publish_new(path, value):
    """Durably publish without replacing any existing artifact or stale temp."""
    path = Path(path)
    durable_mkdir(path.parent)
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()
    tmp = path.with_name(path.name + '.pending')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    os.link(tmp, path, follow_symlinks=False)
    tmp.unlink()
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def fail_generation(out, reason):
    """Preserve all original evidence and append a fail-closed generation marker."""
    path = Path(out) / 'FAILED_GENERATION.json'
    if not path.exists():
        publish_new(path, dict(status='FAILED_GENERATION', reason=reason,
                    new_forward_allowed=False, forensic_receipts_preserved=True))


def publication_gate(out):
    out = Path(out)
    if (out / 'report.json').exists() and not (out / 'COMPLETE.json').exists():
        fail_generation(out, 'Report publication without terminal; CPU forensic reconstruction only')
    require(not any((out / name).exists() for name in
            ['COMPLETE.json', 'FAILURE.json', 'FAILED_GENERATION.json', 'report.json']),
            'Terminal, failed generation or publication gap preserved; new reviewed generation required')
