"""Fixed CPU-only two-update native-loop qualification; not a production capture route."""
import json
from pathlib import Path

import torch

import capture_storage as storage


def required_records(topology):
    """Fixed independent stage/step/name/dtype census from supplied model topology."""
    def group(stage, step):
        return [{'name': f'{step}/{stage}/{n}', 'shape': shape, 'dtype': 'float32'} for n, shape in topology]
    records = group('initial', 0)
    for update in (1, 2):
        records += [{'name': f'{update}/loss/returned', 'shape': [], 'dtype': 'float64'}]
        records += group('preclip', update) + group('postclip', update) + group('postupdate', update)
    return records


def validate_attempt(directory, topology):
    import hashlib
    directory = Path(directory)
    expected = required_records(topology)
    census = storage._canonical({'schedule': 3116, 'updates': [1, 2], 'records': expected})
    if (directory / 'CENSUS.json').is_symlink() or (directory / 'COMPLETE.json').is_symlink():
        raise ValueError('invalid terminal')
    # Bound metadata before reading, even if an attempt has been corrupted.
    if (directory / 'CENSUS.json').stat().st_size != len(census) or (directory / 'COMPLETE.json').stat().st_size > 4096:
        raise ValueError('invalid census or terminal size')
    if (directory / 'CENSUS.json').read_bytes() != census:
        raise ValueError('census mismatch')
    terminal = storage._canonical({'census_sha256': hashlib.sha256(census).hexdigest()})
    if (directory / 'COMPLETE.json').read_bytes() != terminal:
        raise ValueError('terminal mismatch')
    if {p.name for p in directory.iterdir()} != {'CENSUS.json', 'COMPLETE.json', 'records'}:
        raise ValueError('extra attempt artifact')
    return storage.validate(directory / 'records', expected)


class _Observer:
    def __init__(self, parent, attempt_id):
        parent = Path(parent)
        if not parent.is_absolute() or parent.resolve() != parent or not parent.is_dir():
            raise ValueError('canonical existing parent required')
        import re
        if not isinstance(attempt_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', attempt_id):
            raise ValueError('invalid attempt id')
        self.directory = parent / attempt_id
        self.directory.mkdir(mode=0o700)
        storage._sync_dir(parent)
        self.writer = None
        self.expected = None
        self.finished = False

    def start(self, trainable, step, total):
        if step != 0 or total != 3116 or not trainable:
            raise ValueError('qualification requires fresh run and full 3116-step schedule')
        topology = []
        for name, p in trainable:
            if not name or p.device.type != 'cpu' or p.dtype != torch.float32 or not p.is_contiguous():
                raise ValueError('CPU float32 contiguous trainables required')
            topology.append((name, list(p.shape)))
        if len({n for n, _ in topology}) != len(topology):
            raise ValueError('duplicate trainable')
        # Constructed from the model and fixed protocol, before observing any record.
        expected = required_records(topology)
        self.topology = topology
        self.expected = expected
        storage._publish(self.directory, 'CENSUS.json', storage._canonical({'schedule': 3116, 'updates': [1, 2], 'records': expected}))
        # Hard ceiling covers this CPU fixture only; it is not an NPU staging budget.
        self.writer = storage.CPUAttempt(self.directory, 'records', expected, 64 * 1024 * 1024)
        self._group('initial', 0, trainable, False)

    def _group(self, stage, step, trainable, grad):
        for name, p in trainable:
            self.writer.tensor(f'{step}/{stage}/{name}', p.grad if grad else p.detach())

    def preclip(self, step, loss, trainable):
        if type(loss) is not float:
            raise ValueError('native returned loss must be float')
        self.writer.tensor(f'{step}/loss/returned', torch.tensor(loss, dtype=torch.float64))
        self._group('preclip', step, trainable, True)

    def postclip(self, step, trainable):
        self._group('postclip', step, trainable, True)

    def updated(self, step, trainable):
        self._group('postupdate', step, trainable, False)

    def finish(self):
        if self.writer is None:
            raise ValueError('capture never started')
        self.writer.finish()
        storage.validate(self.writer.directory, self.expected)
        storage._publish(self.directory, 'COMPLETE.json', storage._canonical({'census_sha256': __import__('hashlib').sha256((self.directory / 'CENSUS.json').read_bytes()).hexdigest()}))
        self.finished = True

    def fail(self, exc):
        if self.writer is not None:
            self.writer.fail(exc)
        if not self.finished:
            try:
                storage._publish(self.directory, 'FAILED.json', storage._canonical({'error_type': type(exc).__name__, 'error': str(exc)[:1024]}))
            except BaseException:
                pass


def run_cpu_two_updates(trainer, args, parent, attempt_id):
    """Internal fixed entry; trainer is a trusted already-imported module, never config input."""
    fixed = trainer.parse_args(['--out', args.out, '--model-path', args.model_path,
                                '--device', 'cpu', '--stop-after', '2', '--no-merge'])
    if vars(args) != vars(fixed):
        raise ValueError('fixed CPU qualification settings required')
    observer = _Observer(parent, attempt_id)
    return trainer.run(args, _qualification_observer=observer)
