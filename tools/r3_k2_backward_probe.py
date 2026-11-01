"""One-branch q1 replay falsifier. Observations never authorize speed admission.

The frozen trainer, RNG schedule, dropout, autocast, checkpoint implementation,
scoring reduction and optimizer policy are unchanged. Only read-only wrappers
and tensor hooks are added. CPU copies synchronize: agreement is inconclusive.
No tensor values are published. Unsupported mask dispatch fails closed.
"""
import argparse
from contextlib import contextmanager
import functools
import hashlib
import json
from pathlib import Path
import time
import types

TARGET = 'base_model.model.model.layers.18.mlp.up_proj'
CHECKPOINT = 'base_model.model.model.layers.18'
PROTOCOL = dict(seed=2, step=0, question=1, target=TARGET, checkpoint=CHECKPOINT,
                dropout=0.05, use_reentrant=False, micro_tokens=12000, max_len=4096,
                reference_evaluations=4, max_events=8192, max_tensor_bytes=512*1024**2,
                diagnostic_only=True, chips=1)
FROZEN_LAUNCHER_SHA256 = 'f69399487769400eea23ed44ee4e7655a2ac5074554623597e6ea8cdb2d6c8e9'
V2_PREDECESSOR = dict(
    kind='evaluation',
    out='/mnt/cephfs/xingchao/experiments/jev/r3_runs/k2_backward_probe_20261101_v2',
    execution_sha256='fb8d157e46a5123525738e81cfba0ad639cdab4b33e8faf19fd0bde6c9faf1c7',
    container_id='40e8d51f71f8bc7f96517ab9a20d5bf47409356a87777f2faaa6d64233d23d89')

# Recovery authorization is narrower than successful-predecessor admission.
# It preserves the failed scientific/diagnostic outcome and pins its proof.
V2_RECOVERY_PREDECESSOR = dict(V2_PREDECESSOR,
    expected_exit_code=1, expected_container_exit_code=1,
    authorization='coverage-repair-engineering-only',
    terminal_sha256='95996cd1b577ddff3d46360d8709aec2ad35d99b379f74cf1bf4cef6ea48b76c',
    release_sha256='0ff784ee23430c3231805a8c1534b34df495b7ba86c855da0067b9fd6ec4022e')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def source(path):
    path = Path(path).resolve()
    module = types.ModuleType(path.stem)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


def atomic(path, data):
    import os
    path = Path(path)
    tmp = path.with_suffix('.pending')
    with tmp.open('w') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)


class BackwardProbe:
    """Trace one checkpointed LoRA branch across all q1 chunks, twice.

    IDs are (checkpoint module, checkpoint-call ordinal, stage, branch module,
    event). Recompute uses the closure of the original checkpoint invocation,
    never a backward-order counter. All coverage is derived from actual calls.
    """
    def __init__(self, torch, model, rng, target=TARGET, checkpoint=CHECKPOINT,
                 backend_format=None, max_events=8192, max_tensor_bytes=512*1024**2):
        self.torch, self.model, self.rng = torch, model, rng
        self.target, self.checkpoint = target, checkpoint
        self.backend_format = backend_format
        self.max_events, self.max_tensor_bytes = max_events, max_tensor_bytes
        self.records = [{}, {}]
        self.order = [[], []]
        self.chunk_counts = [0, 0]
        self.question_counts = [0, 0]
        self.calls = [0, 0]
        self.phase = self.question = 0
        self.context = None
        self.handles, self.restore = [], []
        self.failed = False
        self.peak_tensor_bytes = 0

    def tensor(self, value):
        size = value.numel()*value.element_size()
        require(size <= self.max_tensor_bytes, 'tensor byte budget exceeded')
        self.peak_tensor_bytes = max(size, self.peak_tensor_bytes)
        metadata = dict(shape=list(value.shape), dtype=str(value.dtype), stride=list(value.stride()),
                        storage_offset=value.storage_offset(), device=str(value.device),
                        backend_format=self.backend_format(value) if self.backend_format else None)
        cpu = value.detach().cpu().contiguous()
        require(bool(self.torch.isfinite(cpu).all()), 'nonfinite observation')
        metadata['sha256'] = hashlib.sha256(cpu.reshape(-1).view(self.torch.uint8).numpy().tobytes()).hexdigest()
        return metadata

    def describe(self, value):
        if isinstance(value, self.torch.Tensor):
            return self.tensor(value)
        if isinstance(value, (list, tuple)):
            return [self.describe(x) for x in value]
        if isinstance(value, dict):
            return {str(k): self.describe(v) for k, v in sorted(value.items())}
        require(value is None or isinstance(value, (bool, int, float, str)), 'unsupported checkpoint operand')
        return value

    def put(self, key, value):
        try:
            key = tuple(key)
            records = self.records[self.phase]
            require(len(records) < self.max_events, 'event budget exceeded')
            require(key not in records, 'duplicate observation')
            records[key] = self.describe(value)
            self.order[self.phase].append(key)
        except Exception:
            self.failed = True
            raise

    def event(self, label, value):
        require(self.context is not None, 'branch outside checkpoint')
        call, stage = self.context
        self.put((self.checkpoint, call, stage, self.target, label), value)

    def wrap(self, obj, name, replacement):
        # Restore instance ownership, including attributes originally inherited.
        owned = name in obj.__dict__
        previous = getattr(obj, name)
        self.restore.append((obj, name, owned, previous))
        setattr(obj, name, replacement)
        return previous

    def install(self):
        require(not self.restore, 'already installed')
        modules = dict(self.model.named_modules())
        require(self.target in modules and self.checkpoint in modules, 'target/checkpoint absent')
        branch, layer = modules[self.target], modules[self.checkpoint]
        require(self.target.startswith(self.checkpoint+'.'), 'branch outside selected layer')
        drop = branch.lora_dropout['default']
        a, b = branch.lora_A['default'], branch.lora_B['default']
        require(drop.training and drop.p == .05 and not drop.inplace and layer.training
                and layer.gradient_checkpointing, 'recipe differs')
        original = layer._gradient_checkpointing_func
        require(isinstance(original, functools.partial) and original.keywords.get('use_reentrant') is False
                and original.keywords.get('preserve_rng_state', True) is True
                and 'context_fn' not in original.keywords, 'checkpoint recipe differs')
        self.parameter = b.weight
        self.handles.append(b.weight.register_hook(self.leaf))

        def checkpoint_call(function, *args, **kwargs):
            if self.question != 1:
                return original(function, *args, **kwargs)
            call = self.calls[self.phase]
            self.calls[self.phase] += 1
            visits = 0
            # HF binds non-positional checkpoint inputs into a partial.
            bound_kwargs = function.keywords if isinstance(function, functools.partial) else {}
            def observed(*values, **named):
                nonlocal visits
                visits += 1
                require(visits <= 2, 'extra checkpoint recomputation')
                stage = 'forward' if visits == 1 else 'recompute'
                prior = self.context
                self.context = (call, stage)
                status = 'returned'
                try:
                    self.event('checkpoint_rng_entry', self.rng())
                    self.event('checkpoint_inputs', dict(args=values, kwargs=named, bound_kwargs=bound_kwargs))
                    return function(*values, **named)
                except BaseException as exc:
                    status = type(exc).__name__
                    raise
                finally:
                    self.event('checkpoint_rng_exit', self.rng())
                    self.event('checkpoint_exit_kind', status)
                    self.context = prior
            return original(observed, *args, **kwargs)
        self.wrap(layer, '_gradient_checkpointing_func', checkpoint_call)

        drop_forward = drop.forward
        def dropout(value):
            if self.question != 1:
                return drop_forward(value)
            self.event('dropout_rng_entry', self.rng())
            self.event('dropout_input', value)
            with self.dispatch('dropout'):
                output = drop_forward(value)
            self.event('dropout_output', output)
            self.event('dropout_rng_exit', self.rng())
            return output
        self.wrap(drop, 'forward', dropout)

        for label, module in [('A', a), ('B', b)]:
            old = module.forward
            def linear(value, old=old, label=label, module=module):
                if self.question != 1:
                    return old(value)
                self.event(label+'_input', value)
                self.event(label+'_weight', module.weight)
                try:
                    with self.dispatch(label):
                        output = old(value)
                except BaseException as exc:
                    from torch.utils.checkpoint import _StopRecomputationError
                    if type(exc) is _StopRecomputationError and self.context[1] == 'recompute':
                        self.event(label+'_early_stop', True)
                    raise
                self.event(label+'_output', output)
                if label == 'B' and self.context[1] == 'forward':
                    call = self.context[0]
                    require(output.requires_grad, 'B output not differentiable')
                    def cotangent(gradient):
                        self.put((self.checkpoint, call, 'backward', self.target, 'B_cotangent'), gradient)
                        return None
                    self.handles.append(output.register_hook(cotangent))
                return output
            self.wrap(module, 'forward', linear)

    def observe_operation(self, scope, func, args, kwargs):
        name = str(func)
        # Exactly one invocation, including unsupported routes. Observation
        # failures cannot trigger a second kernel or manufacture coverage.
        result = func(*args, **kwargs)
        if scope == 'dropout':
            # Never infer a mask by dividing output by input (zeros hide it).
            if name == 'aten.native_dropout.default':
                self.event('dropout_mask', result[1])
                self.event('dropout_mask_op', name)
            elif name == 'aten.bernoulli_.float':
                self.event('dropout_mask', result)
                self.event('dropout_mask_op', name)
        elif name in ('aten.mm.default', 'aten.matmul.default'):
            # Fixed-image Ascend evidence: 3D x 2D aten.matmul after bf16
            # casts. Capture dispatched operands, not Linear input/weight.
            self.event(scope+'_mm_operator', dict(name=name, kwargs=kwargs))
            self.event(scope+'_mm_operands', args)
            self.event(scope+'_mm_output', result)
        return result

    @contextmanager
    def dispatch(self, scope):
        from torch.utils._python_dispatch import TorchDispatchMode
        probe = self
        class Observe(TorchDispatchMode):
            def __torch_dispatch__(self, func, types, args=(), kwargs=None):
                return probe.observe_operation(scope, func, args, kwargs or {})
        with Observe():
            yield

    def leaf(self, gradient):
        if self.question == 1:
            self.put(('q1', 'incoming_B_gradient'), gradient)
        return None

    def before(self, scores):
        if self.question == 1:
            self.put(('q1', 'prior_B_gradient'), self.parameter.grad)
            self.put(('q1', 'scores'), scores)

    def chunk(self, *unused):
        if self.question == 1:
            self.chunk_counts[self.phase] += 1

    def after(self):
        if self.question in (0, 1):
            self.put(('q'+str(self.question), 'post_B_gradient'), self.parameter.grad)
        self.question += 1
        self.question_counts[self.phase] = self.question

    def begin_repeat(self):
        require(self.phase == 0 and self.question >= 2, 'reference incomplete')
        self.phase, self.question = 1, 0

    def close(self):
        for handle in self.handles:
            handle.remove()
        self.handles = []
        for obj, name, owned, old in reversed(self.restore):
            if owned:
                setattr(obj, name, old)
            else:
                delattr(obj, name)
        self.restore = []

    def expected(self, phase):
        keys = {('q0', 'post_B_gradient'), ('q1', 'prior_B_gradient'), ('q1', 'post_B_gradient'),
                ('q1', 'incoming_B_gradient'), ('q1', 'scores')}
        labels = ['checkpoint_rng_entry', 'checkpoint_inputs', 'checkpoint_rng_exit', 'checkpoint_exit_kind',
                  'dropout_rng_entry', 'dropout_input', 'dropout_mask', 'dropout_mask_op',
                  'dropout_output', 'dropout_rng_exit']
        labels += [part+'_'+field for part in ('A', 'B') for field in
                   ('input', 'weight', 'output', 'mm_operator', 'mm_operands', 'mm_output')]
        for call in range(self.chunk_counts[phase]):
            for stage in ('forward', 'recompute'):
                keys.update((self.checkpoint, call, stage, self.target, label) for label in labels)
            prefix = (self.checkpoint, call, 'recompute', self.target)
            # PyTorch can stop before executing B's mm once saved inputs exist.
            # This is a distinct, explicit coverage outcome, never invented output.
            if self.records[phase].get((*prefix, 'B_early_stop')) is True:
                for label in ('B_output', 'B_mm_operator', 'B_mm_operands', 'B_mm_output'):
                    keys.discard((*prefix, label))
                keys.add((*prefix, 'B_early_stop'))
            keys.add((self.checkpoint, call, 'backward', self.target, 'B_cotangent'))
        return keys

    def summary(self):
        coverage = []
        for phase in range(2):
            actual, expected = set(self.records[phase]), self.expected(phase)
            # Non-null gradients are required, not just their dictionary keys.
            gradients = all(self.records[phase].get(k) is not None for k in expected if len(k) == 2 and 'gradient' in k[1])
            coverage.append(dict(chunks=self.chunk_counts[phase], checkpoint_calls=self.calls[phase],
                missing=[list(k) for k in sorted(expected-actual, key=repr)],
                extra=[list(k) for k in sorted(actual-expected, key=repr)],
                complete=actual == expected and gradients and self.chunk_counts[phase] > 0
                         and self.calls[phase] == self.chunk_counts[phase] and self.question_counts[phase] >= 2))
        comparisons = [dict(key=list(k), equal=self.records[0][k] == self.records[1][k])
                       for k in self.order[0] if k in self.records[0] and k in self.records[1]]
        replay = []
        for phase in range(2):
            for k, v in self.records[phase].items():
                if len(k) == 5 and k[2] == 'forward':
                    other = (*k[:2], 'recompute', *k[3:])
                    if other in self.records[phase]:
                        replay.append(dict(phase=phase, key=list(k), equal=v == self.records[phase][other],
                                           comparable_full_extent=k[-1] not in ('checkpoint_rng_exit', 'checkpoint_exit_kind')))
        return dict(schema='r3-k2-backward-probe-v1', complete=not self.failed and all(x['complete'] for x in coverage),
                    coverage=coverage, comparisons=comparisons, replay_comparisons=replay,
                    records=[[dict(key=list(k), observation=v) for k,v in d.items()] for d in self.records],
                    order_equal=self.order[0] == self.order[1], peak_tensor_bytes=self.peak_tensor_bytes,
                    scientific_acceptance=False, test_read=False,
                    scope='one q1 branch; hashes only; checkpoint exit may be early-stop; equality inconclusive')


def verify_plan(path, pin):
    require(sha(path) == pin, 'probe plan changed')
    plan = load(path)
    require(plan['schema'] == 'r3-k2-backward-probe-plan-v1' and plan['protocol'] == PROTOCOL
            and plan['scientific_acceptance'] is False and plan['test_read'] is False, 'probe scope differs')
    for filename, expected in plan['files'].items():
        p = Path(filename)
        require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe dependency')
        require(not any(x == 'test' or x.startswith('test.') for x in p.parts), 'test input forbidden')
        require(sha(p) == expected, 'probe dependency changed: '+filename)
    code = Path(plan['trainer']).parent
    required_code = {'train_r3.py', 'candidate_train_r3.py', 'build_kev_sft.py', 'kev_aug.py',
                     'r0_code/prompt.py', 'r3_k2_deferred_sync.py', 'r3_k2_sync_benchmark.py',
                     'r3_k2_reference_trace.py', 'r3_k2_reference_trace_run.py', 'r3_k2_boundary_trace.py'}
    expected_files = {str(code/n) for n in required_code} | {str(Path(__file__).resolve()),
        '/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl'} | {
        str(p) for p in Path(plan['model']).iterdir() if p.is_file()}
    require(set(plan['files']) == expected_files, 'probe input inventory differs')
    require(plan['files'].get(str(Path(__file__).resolve())) == sha(__file__), 'probe executable not pinned')
    for name in ('train_r3.py', 'r3_k2_reference_trace.py', 'r3_k2_sync_benchmark.py'):
        require(str(Path(plan['trainer']).with_name(name)) in plan['files'], 'helper not pinned')
    return plan


def run(path, pin):
    plan = verify_plan(path, pin)
    out = Path(plan['out'])
    out.mkdir(exist_ok=True)
    identity = {'plan_sha256': pin, 'scientific_acceptance': False, 'test_read': False}
    if (out/'RUN.json').exists():
        require(load(out/'RUN.json') == identity, 'resume identity differs')
        require(not (out/'EXIT.json').exists(), 'terminal run cannot be overwritten')
    else:
        require(not list(out.iterdir()), 'unowned output')
        atomic(out/'RUN.json', identity)
    atomic(out/'heartbeat.json', dict(identity, utc_seconds=time.time(), state='loading', completed_questions=0))
    import torch
    import torch_npu
    import transformers
    code = Path(plan['trainer']).parent
    B = source(code/'r3_k2_sync_benchmark.py')
    T = source(code/'train_r3.py')
    R = source(code/'r3_k2_reference_trace.py')
    args = T.parse_args(['--out', str(out), '--arm', 'k2', '--seed', '2', '--model-path', plan['model'],
                        '--kernel', 'ref', '--grad-ckpt', '--micro-tokens', '12000', '--max-len', '4096',
                        '--expect-pairs', '186', '--no-merge'])
    tok = transformers.AutoTokenizer.from_pretrained(args.model_path)
    data = T.Data(args)
    model, trainable, pairs = T.build_model(args, torch)
    model.to(args.device); model.train()
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    units = data.step_units(0)[1]
    expected_questions = sum(len(u) for u in units)
    require(2 <= expected_questions <= 32 and pairs == 186, 'question/pair inventory differs')
    pair_results = []
    for pair in range(2):
        artifact = out/('CONTROL.json' if pair == 0 else 'OBSERVED.json')
        # Pair is the smallest safe resume item: checkpoint graphs and the q0
        # accumulation/RNG prefix must be rebuilt together, never serialized.
        if artifact.exists():
            saved = load(artifact)
            require(saved['plan_sha256'] == pin and saved['complete'], 'invalid completed pair')
            pair_results.append(saved)
            continue
        trace = R.ReferenceTrace(torch, trainable, B.rng_snapshot, B.equality_diagnostic)
        probe = BackwardProbe(torch, model, lambda: B.rng_snapshot(torch),
                              backend_format=torch_npu.get_npu_format) if pair else None
        endpoints = []
        def observe(*values):
            trace.observe(*values)
            if probe:
                probe.after()
            atomic(out/'heartbeat.json', dict(identity, utc_seconds=time.time(), pair=pair,
                   phase=trace.phase, completed_questions=trace.index, questions=expected_questions,
                   chips=1, reserved_bytes_per_chip=torch.npu.memory_reserved()))
        def chunk(*values):
            trace.observe_chunk(*values)
            if probe:
                probe.chunk()
        try:
            if probe:
                probe.install()
            fn = R.instrument(T, observe, chunk, probe.before if probe else None)
            for phase in range(2):
                if phase:
                    trace.begin_repeat()
                    if probe:
                        probe.begin_repeat()
                before = B.seed_and_snapshot(torch, 2, 0)
                model.zero_grad(set_to_none=True)
                loss, stats = fn(torch, model.base_model.model, tok, units, 'k2', args.device,
                                 pad, 4096, 12000, {}, backward=True)
                endpoints.append(dict(loss=loss, stats=stats, rng_before=before, rng_after=B.rng_snapshot(torch)))
            result = dict(trace.summary(), **identity, endpoints=endpoints)
            require(result['complete'] and result['reference_questions'] == expected_questions, 'trace incomplete')
            if probe:
                result['backward_probe'] = probe.summary()
                require(result['backward_probe']['complete'], 'backward instrumentation coverage incomplete')
            atomic(artifact, result)
            pair_results.append(result)
        finally:
            if probe:
                probe.close()
                atomic(out/'PROBE_PARTIAL.json', dict(probe.summary(), **identity))
    result = dict(pair_results[1], control=pair_results[0], source_pins=plan['files'],
                  runtime={name: {'version': getattr(mod, '__version__', None), 'source': mod.__file__,
                                  'source_sha256': sha(mod.__file__)}
                           for name, mod in [('torch', torch), ('torch_npu', torch_npu), ('transformers', transformers)]})
    atomic(out/'TRACE.json', result)
    return result


def verify_predecessor(previous, base):
    # Legacy PT preparations remain identifiable; new evaluation predecessors
    # are restricted to the exact already-running v2, never an arbitrary run.
    if previous.get('kind', 'training') == 'training':
        required = str(base/'r3_runs/pt_retained3000_resume_contract_20261101_chip3_v1/seed2')
        require(previous['out'] == required
                and previous['plan_sha256'] == '370ac30495eaaa43102d7108ebca11b5cbf0709285af3be57179b5834c15c248'
                and sha(Path(required)/'plan.json') == previous['plan_sha256'], 'PT predecessor changed')
    else:
        require(previous in (V2_PREDECESSOR, V2_RECOVERY_PREDECESSOR), 'exact v2 predecessor required')
        if 'expected_exit_code' in previous:
            require(type(previous['expected_exit_code']) is int
                    and type(previous['expected_container_exit_code']) is int, 'invalid expected exit type')
            require(sha(Path(previous['out'])/'ENGINEERING_EVAL_EXIT.json') == previous['terminal_sha256']
                    and sha(Path(previous['out'])/'attempts/1/RELEASE.json') == previous['release_sha256'],
                    'v2 recovery terminal/release changed')
        require(sha(Path(previous['out'])/'execution.json') == previous['execution_sha256'],
                'v2 predecessor changed')


def released_predecessor(p, successor, base):
    previous = p['predecessor']
    verify_predecessor(previous, base)
    result = successor.predecessor(dict(previous_kind=previous.get('kind', 'training'),
                                        previous_eval=previous['out'], chip=3))
    expected_exit = previous.get('expected_exit_code', 0)
    require(result is not None and type(result['exit_code']) is int and result['exit_code'] == expected_exit,
            'exact predecessor terminal/release differs')
    if 'expected_exit_code' in previous:
        require(type(result.get('container_exit_code')) is int
                and result['container_exit_code'] == previous['expected_container_exit_code']
                and result['release_sha256'] == previous['release_sha256'],
                'v2 recovery retained exit/release differs')
    if previous.get('kind') == 'evaluation':
        require(result['attempt'] == 1 and result['container_id'] == previous['container_id'],
                'v2 retained predecessor identity differs')
    return result


def launcher(path, pin):
    """Reuse the frozen retained-container/resource supervisor without editing it.

    The new plan/spec validators below bind this probe. Lifecycle, ownership,
    detached launch, retained identity and durable release are the frozen code.
    """
    p = load(path)
    root = Path(p['out'])
    require(sha(path) == pin, 'execution changed')
    for filename, digest in p['tools'].items():
        require(Path(filename).parent == root/'tools' and sha(filename) == digest, 'launcher source changed')
    helper = root/'tools/r3_k2_benchmark_launcher.py'
    require(sha(helper) == FROZEN_LAUNCHER_SHA256, 'unsupported lifecycle helper')
    L = source(helper)
    # Bind this one-path adaptation to the reviewed helper's exact bytes.
    # Keep its start()/locking/detach/receipt implementation unchanged.
    original_atomic = L.atomic
    def runtime_atomic(filename, data):
        if Path(filename) == root/'RELAUNCH.json':
            filename = root/'SUPERVISOR_RELAUNCH.json'
        return original_atomic(filename, data)
    L.atomic = runtime_atomic
    def verify(execution, expected):
        require(sha(execution) == expected, 'execution changed')
        doc = load(execution)
        require(doc['schema'] == 'r3-k2-reference-trace-execution-backward-v1'
                and doc['chip'] == 3 and doc['image'] == L.IMAGE
                and doc['test_read'] is False and doc['scientific_acceptance'] is False, 'execution scope differs')
        require(Path(execution) == root/'execution.json' and doc['out'] == str(root)
                and root.is_relative_to(L.BASE/'r3_runs') and doc['run'] == str(root.relative_to(L.BASE))
                and doc['allocation'] == str(L.BASE/'CHIP-ALLOCATION.json'), 'execution paths differ')
        require(doc['launcher'] == str(Path(__file__).resolve())
                and doc['benchmark'] == doc['launcher'], 'entrypoint differs')
        names = set(L.TOOLS) | {'r3_k2_backward_probe.py', 'r3_eval_successor.py'}
        require(set(doc['tools']) == {str(root/'tools'/n) for n in names}, 'frozen tool inventory differs')
        for f,h in doc['tools'].items():
            require(L.sha(f) == h, 'frozen launcher changed')
        q = verify_plan(doc['benchmark_plan'], doc['benchmark_sha256'])
        require(q['out'] == str(root/'results') and q['model'] == L.MODEL
                and doc['container'] == 'nga-k2-backward-'+doc['benchmark_sha256'][:16], 'probe binding differs')
        verify_predecessor(doc['predecessor'], L.BASE)
        return doc, q
    def spec(doc, q, execution, expected):
        K = source(root/'tools/r3_final_container.py')
        mounts = {str(root): True, str(root/'tools'): False, str(root/'code'): False,
                  q['model']: False, L.TRAIN: False, str(execution): False, doc['benchmark_plan']: False}
        return dict(name=doc['container']+'-a1', image=L.IMAGE,
                    cmd=['-B', '-P', doc['benchmark'], 'run', '--plan', doc['benchmark_plan'], '--sha256', doc['benchmark_sha256']],
                    mounts=mounts, devices=['/dev/davinci_manager', '/dev/devmm_svm', '/dev/hisi_hdc', '/dev/davinci3'],
                    environment={**K.ENV, 'NGA_R0_CODE': str(root/'code/r0_code')})
    original_load = L.load
    def checked_load(filename):
        value = original_load(filename)
        if Path(filename) == root/'results/TRACE.json':
            require(value.get('backward_probe', {}).get('complete') is True
                    and value.get('control', {}).get('complete') is True, 'backward result incomplete')
        return value
    L.verify, L.spec, L.load = verify, spec, checked_load
    verify(path, pin)
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('op', choices=('run', 'verify', 'start', 'supervise'))
    ap.add_argument('--plan', required=True); ap.add_argument('--sha256', required=True)
    ap.add_argument('--attempt', type=int, default=1)
    args = ap.parse_args()
    require(args.attempt == 1, 'only retained attempt one; no implicit retries')
    if args.op == 'run':
        plan = verify_plan(args.plan, args.sha256)
        out = Path(plan['out'])
        require(not (out/'EXIT.json').exists(), 'terminal output already exists')
        rc = 1
        try:
            from contextlib import redirect_stdout, redirect_stderr
            with (out.parent/'probe-container.log').open('a', buffering=1) as log:
                with redirect_stdout(log), redirect_stderr(log):
                    try:
                        run(args.plan, args.sha256); rc = 0
                    except BaseException:
                        import traceback
                        traceback.print_exc()
                        raise
        finally:
            if out.exists() and (out/'RUN.json').exists():
                atomic(out/'EXIT.json', dict(exit_code=rc, plan_sha256=args.sha256,
                       scientific_acceptance=False, test_read=False))
    else:
        L = launcher(args.plan, args.sha256)
        if args.op == 'verify':
            print('BACKWARD_PROBE_VERIFIED'); return
        # The queue and direct start both enforce this exact released predecessor.
        p = load(args.plan)
        S = source(Path(p['out'])/'tools/r3_eval_successor.py')
        released_predecessor(p, S, L.BASE)
        print(json.dumps(L.start(args.plan, args.sha256) if args.op == 'start' else L.supervise(args.plan, args.sha256)))


if __name__ == '__main__':
    main()
