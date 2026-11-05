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
    if storage._read_bounded(directory, 'CENSUS.json', len(census)) != census:
        raise ValueError('census mismatch')
    terminal = storage._canonical({'census_sha256': hashlib.sha256(census).hexdigest()})
    if storage._read_bounded(directory, 'COMPLETE.json', 4096) != terminal:
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

# Fixture qualification v2: an externally supplied topology is the authority.
# This remains CPU-only and is not a production model identity or input/RNG gate.
def _typed(value):
    import base64, math
    storage._require_little_endian()
    if isinstance(value, torch.Tensor):
        if value.device.type != 'cpu' or not value.is_contiguous() or not bool(torch.isfinite(value).all()):
            raise ValueError('finite contiguous CPU tensor required')
        return {'type': 'tensor', 'dtype': str(value.dtype), 'shape': list(value.shape),
                'bytes': base64.b64encode(value.detach().numpy().tobytes()).decode('ascii')}
    if value is None or type(value) in (bool, int, str):
        return {'type': type(value).__name__, 'value': value}
    if type(value) is float:
        if not math.isfinite(value): raise ValueError('nonfinite scalar')
        return {'type': 'float', 'value': value.hex()}
    if type(value) in (tuple, list):
        return {'type': type(value).__name__, 'items': [_typed(x) for x in value]}
    if type(value) is dict:
        return {'type': 'dict', 'items': [[_typed(k), _typed(v)] for k, v in value.items()]}
    raise ValueError('unsupported typed state: ' + type(value).__name__)


def _state(trainable, opt, sched):
    return {'parameters': {n: p.detach() for n, p in trainable},
            'optimizer': opt.state_dict(), 'scheduler': sched.state_dict()}


def _event_names(start, end):
    names = []
    if start:
        names += [f'{start}/checkpoint_decoded', f'{start}/checkpoint_restored']
    names += [f'{start}/' + ('postresume' if start else 'initial')]
    for step in range(start + 1, end + 1):
        names += [f'{step}/loss', f'{step}/preclip', f'{step}/postclip',
                  f'{step}/postupdate', f'{step}/optimizer_scheduler']
    names += [f'{end}/checkpoint_presave', f'{end}/checkpoint_saved']
    return names


def validate_state_attempt(directory, topology, start, end):
    import hashlib
    directory = Path(directory)
    census = storage._canonical({'version': 3, 'contract': 'cpu-torch-2.10.0-adamw-onecycle-3116-le', 'schedule': 3116, 'topology': topology,
                                  'start': start, 'end': end, 'events': _event_names(start, end)})
    if storage._read_bounded(directory, 'CENSUS.json', len(census)) != census:
        raise ValueError('state census mismatch')
    raw = storage._read_bounded(directory, 'EVENTS.json', 64 * 1024 * 1024)
    terminal = storage._canonical({'census_sha256': hashlib.sha256(census).hexdigest(),
                                   'events_sha256': hashlib.sha256(raw).hexdigest()})
    if storage._read_bounded(directory, 'COMPLETE.json', 4096) != terminal:
        raise ValueError('state terminal mismatch')
    events = json.loads(raw)
    if [e['name'] for e in events] != _event_names(start, end):
        raise ValueError('state event census mismatch')
    for event in events:
        _check_event(event, topology)
    if {p.name for p in directory.iterdir()} != {'CENSUS.json', 'EVENTS.json', 'COMPLETE.json'}:
        raise ValueError('extra state artifact')
    return events


def _untyped(value):
    import base64, math
    storage._require_little_endian()
    if not isinstance(value, dict) or 'type' not in value: raise ValueError('invalid typed value')
    typ = value['type']
    if typ == 'tensor' and set(value) == {'type', 'dtype', 'shape', 'bytes'}:
        dtype = {'torch.float32': torch.float32, 'torch.float64': torch.float64}.get(value['dtype'])
        shape = value['shape']
        if dtype is None or not isinstance(shape, list) or any(type(n) is not int or n < 0 for n in shape): raise ValueError('invalid tensor schema')
        raw = base64.b64decode(value['bytes'], validate=True)
        if len(raw) != math.prod(shape) * torch.empty((), dtype=dtype).element_size(): raise ValueError('invalid tensor bytes')
        tensor = torch.frombuffer(bytearray(raw), dtype=dtype).clone().reshape(shape) if raw else torch.empty(shape, dtype=dtype)
        if not bool(torch.isfinite(tensor).all()): raise ValueError('nonfinite tensor')
        return tensor
    if typ in ('list', 'tuple') and set(value) == {'type', 'items'}:
        items = [_untyped(x) for x in value['items']]
        return tuple(items) if typ == 'tuple' else items
    if typ == 'dict' and set(value) == {'type', 'items'}:
        result = {}
        for k, v in value['items']:
            key = _untyped(k)
            if key in result: raise ValueError('duplicate typed key')
            result[key] = _untyped(v)
        return result
    if set(value) != {'type', 'value'}: raise ValueError('invalid typed scalar')
    v = value['value']
    if typ == 'float':
        v = float.fromhex(v)
        if not math.isfinite(v): raise ValueError('nonfinite scalar')
    elif typ == 'NoneType':
        if v is not None: raise ValueError('invalid none')
    elif typ not in ('str', 'int', 'bool') or type(v).__name__ != typ: raise ValueError('invalid scalar')
    return v


def _recipe(step, count):
    """Frozen CPU torch 2.10.0 AdamW/OneCycleLR state, derived from the recipe."""
    import math
    if torch.__version__ != '2.10.0+cpu' or type(step) is not int or step not in (1, 2):
        raise ValueError('unsupported CPU torch state contract or step')
    initial, maximum = 1e-4 / 25.0, 1e-4
    minimum = initial / 10000.0
    end = 0.1 * 3116 - 1
    cosine = math.cos(math.pi * (step / end)) + 1
    lr = maximum + (initial - maximum) / 2.0 * cosine
    beta = 0.85 + (0.95 - 0.85) / 2.0 * cosine
    group = {'lr': lr, 'betas': (beta, 0.999), 'eps': 1e-8,
             'weight_decay': 0.01, 'amsgrad': False, 'maximize': False,
             'foreach': None, 'capturable': False, 'differentiable': False,
             'fused': None, 'decoupled_weight_decay': True,
             'initial_lr': initial, 'max_lr': maximum, 'min_lr': minimum,
             'max_momentum': 0.95, 'base_momentum': 0.85,
             'params': list(range(count))}
    phases = [{'end_step': end, 'start_lr': 'initial_lr', 'end_lr': 'max_lr',
               'start_momentum': 'max_momentum', 'end_momentum': 'base_momentum'},
              {'end_step': 3115, 'start_lr': 'max_lr', 'end_lr': 'min_lr',
               'start_momentum': 'base_momentum', 'end_momentum': 'max_momentum'}]
    scheduler = {'total_steps': 3116, '_schedule_phases': phases,
                 '_anneal_func_type': 'cos', 'cycle_momentum': True, 'use_beta1': True,
                 'base_lrs': [initial], 'last_epoch': step, '_step_count': step + 1,
                 '_is_initial': False, '_get_lr_called_within_step': False, '_last_lr': [lr]}
    return group, scheduler


def _exact(actual, expected):
    if type(actual) is not type(expected): return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(_exact(actual[k], v) for k, v in expected.items())
    if type(expected) in (list, tuple):
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _check_event(event, topology):
    if set(event) != {'name', 'value'}: raise ValueError('invalid event')
    value = _untyped(event['value'])
    step_text, stage = event['name'].split('/', 1)
    step = int(step_text)
    if stage in ('checkpoint_saved', 'checkpoint_decoded', 'checkpoint_restored'):
        if set(value) != {'digest', 'state'} or not isinstance(value['digest'], str) or len(value['digest']) != 64: raise ValueError('checkpoint binding')
        value = value['state']
        if stage != 'checkpoint_restored':
            if set(value) != {'step', 'lora', 'opt', 'sched', 'identity', 'topology', 'parent_sha256', 'cursor'} or type(value['step']) is not int or value['step'] != step: raise ValueError('checkpoint fields or step')
            value = {'parameters': value['lora'], 'optimizer': value['opt'], 'scheduler': value['sched']}
    if stage in ('checkpoint_saved', 'checkpoint_decoded', 'checkpoint_restored', 'checkpoint_presave', 'optimizer_scheduler'):
        if set(value) != {'parameters', 'optimizer', 'scheduler'}: raise ValueError('state fields')
        params, opt, sched = value['parameters'], value['optimizer'], value['scheduler']
        if list(params) != [n for n, _ in topology]: raise ValueError('parameter census')
        if set(opt) != {'state', 'param_groups'} or len(opt['param_groups']) != 1: raise ValueError('optimizer groups')
        group = opt['param_groups'][0]
        required_group, required_scheduler = _recipe(step, len(topology))
        if not _exact(group, required_group): raise ValueError('optimizer group contract')
        if list(opt['state']) != list(range(len(topology))): raise ValueError('optimizer parameter census')
        for i, (name, shape) in enumerate(topology):
            if not isinstance(params[name], torch.Tensor) or params[name].dtype != torch.float32 or list(params[name].shape) != shape: raise ValueError('parameter shape or dtype')
            state = opt['state'][i]
            if set(state) != {'step', 'exp_avg', 'exp_avg_sq'}: raise ValueError('Adam field census')
            if not isinstance(state['step'], torch.Tensor) or state['step'].dtype != torch.float32 or list(state['step'].shape) != [] or state['step'].item() != step: raise ValueError('Adam step')
            for field in ('exp_avg', 'exp_avg_sq'):
                if not isinstance(state[field], torch.Tensor) or state[field].dtype != torch.float32 or list(state[field].shape) != shape: raise ValueError('Adam moment shape or dtype')
            if bool((state['exp_avg_sq'] < 0).any()): raise ValueError('negative Adam variance')
        if not _exact(sched, required_scheduler): raise ValueError('scheduler contract')
    elif stage in ('initial', 'postresume', 'preclip', 'postclip', 'postupdate'):
        if list(value) != [n for n, _ in topology]: raise ValueError('tensor names census')
        for n, shape in topology:
            if not isinstance(value[n], torch.Tensor) or value[n].dtype != torch.float32 or list(value[n].shape) != shape: raise ValueError('tensor shape or dtype census')
    elif stage == 'loss' and type(value) is not float: raise ValueError('invalid loss')


class _StateObserver:
    def __init__(self, parent, attempt_id, topology, start, end, load_checkpoint):
        import re
        parent = Path(parent)
        if not parent.is_absolute() or parent.resolve() != parent or not parent.is_dir():
            raise ValueError('canonical existing parent required')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', attempt_id): raise ValueError('invalid attempt id')
        if not topology or len({n for n, _ in topology}) != len(topology): raise ValueError('invalid topology')
        self.directory = parent / attempt_id
        self.directory.mkdir(mode=0o700)
        self.topology, self.start_step, self.end = topology, start, end
        self.load_checkpoint = load_checkpoint
        self.events = []
        self.finished = False
        self.census = storage._canonical({'version': 3, 'contract': 'cpu-torch-2.10.0-adamw-onecycle-3116-le', 'schedule': 3116, 'topology': topology,
                                          'start': start, 'end': end, 'events': _event_names(start, end)})
        storage._publish(self.directory, 'CENSUS.json', self.census)

    def event(self, name, value):
        expected = _event_names(self.start_step, self.end)
        if len(self.events) >= len(expected) or expected[len(self.events)] != name:
            raise ValueError('unexpected state stage or step')
        self.events.append({'name': name, 'value': _typed(value)})

    def check_topology(self, trainable):
        actual = [(n, list(p.shape)) for n, p in trainable]
        if actual != self.topology or any(p.device.type != 'cpu' or p.dtype != torch.float32 or not p.is_contiguous() for _, p in trainable):
            raise ValueError('fixture topology mismatch')

    def start(self, trainable, step, total):
        if step != self.start_step or total != 3116: raise ValueError('invalid qualification start or schedule')
        self.check_topology(trainable)
        self.event(f'{step}/' + ('postresume' if step else 'initial'), {n: p.detach() for n, p in trainable})

    def checkpoint_decoded(self, path, state):
        import hashlib
        self.checkpoint_digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        verified = self.load_checkpoint(Path(path), self.checkpoint_digest)
        if _typed(verified) != _typed(state): raise ValueError('native and family decoded checkpoint differ')
        self.event(f'{self.start_step}/checkpoint_decoded', {'digest': self.checkpoint_digest, 'state': state})

    def checkpoint_restored(self, path, step, trainable, opt, sched):
        self.check_topology(trainable)
        self.event(f'{step}/checkpoint_restored', {'digest': self.checkpoint_digest, 'state': _state(trainable, opt, sched)})

    def preclip(self, step, loss, trainable):
        self.event(f'{step}/loss', loss)
        self.event(f'{step}/preclip', {n: p.grad for n, p in trainable})

    def postclip(self, step, trainable): self.event(f'{step}/postclip', {n: p.grad for n, p in trainable})
    def updated(self, step, trainable): self.event(f'{step}/postupdate', {n: p.detach() for n, p in trainable})
    def optimizer_updated(self, step, trainable, opt, sched):
        self.event(f'{step}/optimizer_scheduler', _state(trainable, opt, sched))
    def checkpoint_presave(self, step, trainable, opt, sched):
        self.event(f'{step}/checkpoint_presave', _state(trainable, opt, sched))
    def checkpoint_saved(self, out, step):
        import hashlib
        path = Path(out) / 'ckpt' / f'step_{step:06d}.pt'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        decoded = self.load_checkpoint(path, digest)
        self.event(f'{step}/checkpoint_saved', {'digest': digest, 'state': decoded})
    def finish(self):
        import hashlib
        if [e['name'] for e in self.events] != _event_names(self.start_step, self.end):
            raise ValueError('incomplete state event census')
        for event in self.events:
            _check_event(event, self.topology)
        raw = storage._canonical(self.events)
        storage._publish(self.directory, 'EVENTS.json', raw)
        storage._publish(self.directory, 'COMPLETE.json', storage._canonical({
            'census_sha256': hashlib.sha256(self.census).hexdigest(), 'events_sha256': hashlib.sha256(raw).hexdigest()}))
        self.finished = True
    def fail(self, exc):
        if not self.finished:
            storage._publish(self.directory, 'FAILED.json', storage._canonical({'error_type': type(exc).__name__, 'error': str(exc)[:1024]}))


def run_cpu_state_plan(trainer, args, parent, attempt_id, topology, plan, load_checkpoint):
    """Run actual native loop(s); load_checkpoint uses the trusted family.load_v2 seam."""
    if plan not in ('continuous2', 'split1+1'): raise ValueError('unknown fixed plan')
    count = 2 if plan == 'continuous2' else 1
    fixed = trainer.parse_args(['--out', args.out, '--model-path', args.model_path,
                                '--device', 'cpu', '--stop-after', str(count), '--no-merge'])
    if vars(args) != vars(fixed): raise ValueError('fixed CPU qualification settings required')
    if plan == 'continuous2':
        return [trainer.run(args, _qualification_observer=_StateObserver(parent, attempt_id, topology, 0, 2, load_checkpoint))]
    first = trainer.run(args, _qualification_observer=_StateObserver(parent, attempt_id + '-1', topology, 0, 1, load_checkpoint))
    second = trainer.run(args, _qualification_observer=_StateObserver(parent, attempt_id + '-2', topology, 1, 2, load_checkpoint))
    return [first, second]


def validate_split_state_attempts(parent, attempt_id, topology):
    """Bind the two authenticated attempt receipts to the actual checkpoint lineage."""
    first = validate_state_attempt(Path(parent) / (attempt_id + '-1'), topology, 0, 1)
    second = validate_state_attempt(Path(parent) / (attempt_id + '-2'), topology, 1, 2)
    def get(events, name):
        return _untyped(next(e['value'] for e in events if e['name'] == name))
    saved = get(first, '1/checkpoint_saved')
    decoded = get(second, '1/checkpoint_decoded')
    restored = get(second, '1/checkpoint_restored')
    last = get(second, '2/checkpoint_saved')
    if _typed(saved) != _typed(decoded) or saved['digest'] != restored['digest']:
        raise ValueError('checkpoint attempt lineage mismatch')
    state = saved['state']
    if _typed({'parameters': state['lora'], 'optimizer': state['opt'], 'scheduler': state['sched']}) != _typed(restored['state']):
        raise ValueError('checkpoint restore mismatch')
    if last['state']['parent_sha256'] != saved['digest']:
        raise ValueError('checkpoint parent mismatch')
    return first, second
