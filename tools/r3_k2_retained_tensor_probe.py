"""Prepared-only bounded q1 tensors; CPU validation never imports an NPU backend.

NPU execution requires a separately reviewed parent activation and chip release.
This module deliberately has no start/SSH/queue operation. Frozen v4 is read-only.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import types

V4 = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/k2_backward_probe_20261101_v4')
FROZEN_SHA = 'ef8a078f52164985b9a045ab05d31b848e8144a6ad5a2ed36601d4c0643ff111'
MAX_TENSOR = 16 * 1024**2
MAX_BYTES = 128 * 1024**2
MAX_RECORDS = 96
MAX_INDEX = 2 * 1024**2
TARGET = 'base_model.model.model.layers.18.mlp.up_proj'
CHECKPOINT = 'base_model.model.model.layers.18'
STAGES = ('forward', 'recompute')
BRANCH_LABELS = {'dropout_mask', 'A_mm_operands', 'B_mm_operands', 'A_mm_output', 'B_mm_output',
                 'B_cotangent', 'producer_operand', 'producer_incoming', 'producer_outgoing'}
BOUNDARIES = {('q0', 'post_B_gradient'), ('q1', 'prior_B_gradient'),
              ('q1', 'incoming_B_gradient'), ('q1', 'post_B_gradient')}
DTYPES = {'torch.float32': 'float32', 'torch.bfloat16': 'bfloat16',
          'torch.float16': 'float16', 'torch.float64': 'float64',
          'torch.uint8': 'uint8', 'torch.bool': 'bool', 'torch.int64': 'int64'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    require(not any(x.lower() == 'test' or x.lower().startswith('test.') for x in p.parts), 'root guard: TEST forbidden')
    return p


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(safe(path).read_text())


def atomic(path, value):
    path = safe(path)
    data = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(data) <= MAX_INDEX, 'metadata budget exceeded')
    tmp = path.with_suffix('.pending')
    with tmp.open('wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)


def source(path):
    path = safe(path)
    m = types.ModuleType(path.stem); m.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), m.__dict__)
    return m


def frozen():
    path = V4/'tools/r3_k2_backward_probe.py'
    require(sha(path) == FROZEN_SHA, 'frozen v4 probe changed')
    return source(path)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identity(pair, phase, key, slot):
    require(pair in ('control', 'observed') and type(phase) is int and phase in (0, 1), 'pair/repeat identity')
    key = tuple(key)
    require(key in BOUNDARIES or (pair == 'observed' and len(key) == 5
            and key[0] == CHECKPOINT and type(key[1]) is int and key[1] == 0
            and key[2] in (*STAGES, 'backward') and key[3] == TARGET
            and key[4] in BRANCH_LABELS), 'tensor outside allowlist')
    require(slot in ('', '0', '1'), 'invalid operand slot')
    if len(key) == 2:
        require(slot == '', 'boundary slot')
        require(pair == 'observed' or key[-1] != 'incoming_B_gradient', 'control must not install incoming hook')
    else:
        require((key[-1].endswith('_operands') and slot in ('0', '1')) or
                (not key[-1].endswith('_operands') and slot == ''), 'operand slot differs')
        require((key[2] == 'backward') == (key[-1] in ('B_cotangent', 'producer_incoming', 'producer_outgoing')), 'stage differs')
        require(key[-1] != 'producer_operand' or key[2] == 'forward', 'producer operand stage')
    return dict(seed=2, step=0, question=0 if key[0] == 'q0' else 1,
                pair=pair, repeat=phase, key=list(key), slot=slot)


def metadata(value, backend=None):
    return dict(shape=list(value.shape), dtype=str(value.dtype), stride=list(value.stride()),
                storage_offset=value.storage_offset(), device=str(value.device),
                backend_format=backend(value) if backend and value.device.type != 'cpu' else None)


class Retention:
    def __init__(self, root, torch, plan_pin, backend=None):
        self.root, self.torch, self.plan_pin, self.backend = safe(root), torch, plan_pin, backend
        self.root.mkdir(exist_ok=False)
        self.entries, self.seen, self.total = [], set(), 0

    def save(self, pair, phase, key, value, slot=''):
        ident = identity(pair, phase, key, slot)
        token = hashlib.sha256(canonical(ident)).hexdigest()
        require(token not in self.seen, 'duplicate tensor identity')
        require(isinstance(value, self.torch.Tensor), 'missing retained tensor')
        size = value.numel()*value.element_size()
        require(0 < size <= MAX_TENSOR and self.total+size <= MAX_BYTES and len(self.entries) < MAX_RECORDS,
                'retained tensor budget exceeded')
        meta = metadata(value, self.backend)
        require(meta['dtype'] in DTYPES, 'unsupported dtype')
        cpu = value.detach().to('cpu').contiguous()
        require(bool(self.torch.isfinite(cpu).all()), 'nonfinite retained tensor')
        raw = cpu.reshape(-1).view(self.torch.uint8).numpy().tobytes()
        digest = hashlib.sha256(raw).hexdigest()
        filename = token+'.bin'
        with (self.root/filename).open('xb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        entry = dict(identity=ident, metadata=meta, file=filename, sha256=digest, bytes=size,
                     plan_sha256=self.plan_pin)
        self.entries.append(entry); self.seen.add(token); self.total += size
        return dict(meta, sha256=digest)

    def finish(self, events, context):
        result = dict(schema='k2-retained-tensors-v1', plan_sha256=self.plan_pin,
                      entries=self.entries, total_bytes=self.total, events=events, context=context,
                      limits=dict(tensor_bytes=MAX_TENSOR, total_bytes=MAX_BYTES, records=MAX_RECORDS),
                      scientific_acceptance=False, test_read=False)
        atomic(self.root/'INDEX.json', result)
        return sha(self.root/'INDEX.json')


def make_probe(base, torch, model, rng, store, backend=None):
    class Probe(base.BackwardProbe):
        def __init__(self):
            super().__init__(torch, model, rng, backend_format=backend, max_events=128,
                             max_tensor_bytes=MAX_TENSOR)
            self.key = None
            self.b_nodes = {}
            self.producers = [{}, {}]
            self.producer_modes = []

        def put(self, key, value):
            self.key = tuple(key)
            try:
                return super().put(key, value)
            finally:
                self.key = None

        def tensor(self, value):
            if self.key in BOUNDARIES or (len(self.key) == 5 and self.key[-1] in BRANCH_LABELS):
                return store.save('observed', self.phase, self.key, value)
            # Layout-only for redundant wrapper inputs/outputs, checkpoint inputs
            # and scores. Actual dispatch values alone get a CPU synchronization.
            return metadata(value, backend)

        def describe(self, value):
            if self.key and self.key[-1] in ('A_mm_operands', 'B_mm_operands'):
                require(isinstance(value, tuple) and len(value) == 2, 'matmul operand arity')
                return [store.save('observed', self.phase, self.key, v, str(i)) for i, v in enumerate(value)]
            return super().describe(value)

        def observe_operation(self, scope, func, args, kwargs):
            name = str(func)
            # Only known metadata/cast routes and the actual v4 matmul/dropout
            # routes are permitted. Unknown dispatch fails before computation.
            allowed = {'aten.t.default', 'aten.transpose.int', 'aten.view.default',
                       'aten._unsafe_view.default', 'aten.reshape.default', 'aten.clone.default',
                       'aten._to_copy.default', 'aten.detach.default', 'aten.empty_like.default',
                       'aten.div_.Scalar', 'aten.mul.Tensor', 'aten.bernoulli_.float',
                       'aten.native_dropout.default', 'aten.mm.default', 'aten.matmul.default'}
            require(name in allowed, 'unknown dispatch path: '+name)
            return super().observe_operation(scope, func, args, kwargs)

        def install(self):
            super().install()
            branch = dict(model.named_modules())[TARGET]
            b = branch.lora_B['default']
            old_b, old_branch = b.forward, branch.forward
            def linear(*args, **kwargs):
                out = old_b(*args, **kwargs)
                if self.question == 1 and self.context[1] == 'forward':
                    self.b_nodes[self.context[0]] = out.grad_fn
                return out
            self.wrap(b, 'forward', linear)
            def outer(*args, **kwargs):
                out = old_branch(*args, **kwargs)
                if self.question != 1 or self.context[1] != 'forward':
                    return out
                call = self.context[0]
                target = self.b_nodes[call]
                # Follow only the selected branch's output graph, at most eight
                # nodes; attach to the immediate cotangent producer, no full walk.
                todo, seen, found = [out.grad_fn], set(), []
                while todo:
                    node = todo.pop()
                    if node is None or node in seen or node is target:
                        continue
                    seen.add(node)
                    require(len(seen) <= 8, 'producer search extent exceeded')
                    edges = list(node.next_functions)
                    for i, (n, _) in enumerate(edges):
                        if n is target:
                            found.append((node, i))
                    if not found:
                        # Add's base branch can be huge: search the LoRA side
                        # first (last next_function), stop on the direct match.
                        todo.extend(n for n, _ in edges)
                    else:
                        break
                require(len(found) == 1, 'immediate producer missing/ambiguous')
                node, edge = found[0]
                require(type(node).__name__ == 'MulBackward0' and edge == 0,
                        'unsupported immediate cotangent producer: '+type(node).__name__)
                scalar = node._saved_other
                require(isinstance(scalar, torch.Tensor) and scalar.numel() == 1 and node._saved_self is None,
                        'producer must be scalar multiply')
                self.event('producer_operand', scalar)
                self.producers[self.phase][call] = dict(node=type(node).__name__, edge=edge,
                    search_nodes=len(seen), producer_input='grad_outputs[0]', producer_output='grad_inputs[0]',
                    scope='one immediate scalar-multiply VJP; no global earliest-divergence claim')
                from torch.utils._python_dispatch import TorchDispatchMode
                probe = self
                class ProducerDispatch(TorchDispatchMode):
                    def __torch_dispatch__(self, func, types, args=(), kwargs=None):
                        name = str(func)
                        require(name in ('aten.mul.Tensor', 'aten.mul.Scalar'), 'unknown producer dispatch: '+name)
                        require(len(args) == 2 and not kwargs, 'producer dispatch arity')
                        require(isinstance(args[0], torch.Tensor), 'producer input not tensor')
                        right = metadata(args[1], backend) if isinstance(args[1], torch.Tensor) else args[1]
                        result = func(*args, **(kwargs or {}))
                        probe.put((CHECKPOINT, call, 'backward', TARGET, 'producer_operator'),
                                  dict(name=name, left=metadata(args[0], backend), right=right,
                                       output=metadata(result, backend), kwargs=kwargs or {}))
                        return result
                mode = ProducerDispatch()
                active = [False]
                def prehook(outs):
                    require(not active[0], 'duplicate producer execution')
                    mode.__enter__(); active[0] = True
                    self.producer_modes.append((mode, active))
                    return None
                self.handles.append(node.register_prehook(prehook))
                def hook(ins, outs):
                    require(active[0], 'missing producer prehook')
                    mode.__exit__(None, None, None); active[0] = False
                    require(len(ins) == 2 and len(outs) == 1 and ins[1] is None, 'producer hook arity')
                    key = (CHECKPOINT, call, 'backward', TARGET)
                    self.put((*key, 'producer_incoming'), outs[0])
                    self.put((*key, 'producer_outgoing'), ins[0])
                    return None
                self.handles.append(node.register_hook(hook))
                return out
            self.wrap(branch, 'forward', outer)

        def close(self):
            for mode, active in reversed(self.producer_modes):
                if active[0]:
                    mode.__exit__(None, None, None); active[0] = False
            super().close()

        def expected(self, phase):
            keys = super().expected(phase)
            for call in range(self.chunk_counts[phase]):
                keys.add((CHECKPOINT, call, 'forward', TARGET, 'producer_operand'))
                keys.update((CHECKPOINT, call, 'backward', TARGET, x) for x in ('producer_incoming', 'producer_outgoing', 'producer_operator'))
            return keys

        def summary(self):
            result = super().summary()
            result['producer'] = self.producers
            result['scope'] = 'bounded retained q1 actual dispatch; CPU copies may perturb; no causal admission'
            result['complete'] = result['complete'] and self.chunk_counts == [1, 1] and all(len(x) == 1 for x in self.producers)
            result['complete'] = result['complete'] and all(
                (CHECKPOINT, 0, stage, TARGET, label) in records
                for records in self.records for stage in STAGES
                for label in ('A_mm_operands', 'B_mm_operands', 'A_mm_output', 'B_mm_output'))
            return result
    return Probe()


def required_identities():
    ids = []
    for pair in ('control', 'observed'):
        for phase in (0, 1):
            for key in sorted(BOUNDARIES):
                if pair == 'control' and key[-1] == 'incoming_B_gradient':
                    continue
                ids.append(identity(pair, phase, key, ''))
            if pair == 'observed':
                for stage in STAGES:
                    for label in ('dropout_mask', 'A_mm_operands', 'B_mm_operands', 'A_mm_output', 'B_mm_output'):
                        for slot in ('0', '1') if label.endswith('_operands') else ('',):
                            ids.append(identity(pair, phase, (CHECKPOINT, 0, stage, TARGET, label), slot))
                for label, stage in [('B_cotangent', 'backward'), ('producer_operand', 'forward'),
                                     ('producer_incoming', 'backward'), ('producer_outgoing', 'backward')]:
                    ids.append(identity(pair, phase, (CHECKPOINT, 0, stage, TARGET, label), ''))
    return ids


def difference(torch, a, b):
    require(a.shape == b.shape and a.dtype == b.dtype, 'tensor comparison shape/dtype differs')
    return dict(values_equal=bool(torch.equal(a, b)), mismatched_elements=int((a != b).sum()),
                max_abs_difference=float((a.double()-b.double()).abs().max()) if a.numel() else 0.)


def validate(root, expected_index, plan_pin, torch):
    root = safe(root)
    require((root/'INDEX.json').stat().st_size <= MAX_INDEX and sha(root/'INDEX.json') == expected_index,
            'index checksum/size differs')
    doc = load(root/'INDEX.json')
    require(doc['schema'] == 'k2-retained-tensors-v1' and doc['plan_sha256'] == plan_pin
            and doc['test_read'] is False and doc['scientific_acceptance'] is False, 'index provenance differs')
    require(len(doc['entries']) <= MAX_RECORDS and doc['total_bytes'] <= MAX_BYTES, 'inventory budget')
    got, tensors, total, names = set(), {}, 0, set()
    for e in doc['entries']:
        i, m = e['identity'], e['metadata']
        require(i == identity(i['pair'], i['repeat'], i['key'], i['slot']), 'identity fields differ')
        token = hashlib.sha256(canonical(i)).hexdigest()
        require(token not in got and e['plan_sha256'] == plan_pin, 'duplicate/provenance differs')
        got.add(token)
        require(e['file'] == token+'.bin', 'identity filename differs')
        p = root/e['file']; names.add(e['file'])
        require(m['dtype'] in DTYPES and len(m['shape']) <= 4 and all(type(x) is int and x >= 0 for x in m['shape']), 'tensor metadata')
        dtype = getattr(torch, DTYPES[m['dtype']])
        size = math.prod(m['shape'])*torch.empty((), dtype=dtype).element_size()
        require(0 < size == e['bytes'] <= MAX_TENSOR and p.stat().st_size == size, 'tensor byte length differs')
        require(len(m['stride']) == len(m['shape']) and all(type(x) is int and x >= 0 for x in m['stride'])
                and type(m['storage_offset']) is int and m['storage_offset'] >= 0, 'layout metadata')
        require(total+size <= MAX_BYTES, 'cumulative read budget exceeded')
        raw = safe(p).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == e['sha256'], 'tensor checksum differs')
        t = torch.frombuffer(bytearray(raw), dtype=dtype).clone().reshape(m['shape'])
        require(bool(torch.isfinite(t).all()), 'nonfinite tensor')
        tensors[canonical(i)] = t
        total += size
    expected = {hashlib.sha256(canonical(i)).hexdigest() for i in required_identities()}
    require(got == expected, 'missing/extra allowlisted identity')
    require(total == doc['total_bytes'] and total <= MAX_BYTES, 'total byte budget differs')
    require({p.name for p in root.iterdir()} == names | {'INDEX.json'}, 'extra/missing payload files')
    def get(pair, phase, key, slot=''):
        return tensors[canonical(identity(pair, phase, key, slot))]
    entry_map = {canonical(e['identity']): e for e in doc['entries']}
    def compare(pair_a, phase_a, key_a, pair_b, phase_b, key_b, slot=''):
        ea = entry_map[canonical(identity(pair_a, phase_a, key_a, slot))]
        eb = entry_map[canonical(identity(pair_b, phase_b, key_b, slot))]
        return dict(hash_equal=ea['sha256'] == eb['sha256'], metadata_equal=ea['metadata'] == eb['metadata'],
                    reference_sha256=ea['sha256'], repeat_sha256=eb['sha256'],
                    **difference(torch, get(pair_a, phase_a, key_a, slot), get(pair_b, phase_b, key_b, slot)))
    comparisons = []
    for i in required_identities():
        if i['repeat'] == 0:
            comparisons.append(dict(identity=i, **compare(i['pair'], 0, i['key'], i['pair'], 1, i['key'], i['slot'])))
    replay, vjp, observer, continuity = [], [], [], []
    for phase in (0, 1):
        for pair in ('control', 'observed'):
            continuity.append(dict(pair=pair, repeat=phase, **compare(pair, phase, ('q0', 'post_B_gradient'),
                pair, phase, ('q1', 'prior_B_gradient'))))
        prefix = (CHECKPOINT, 0, 'forward', TARGET)
        for label in ('dropout_mask', 'A_mm_operands', 'B_mm_operands', 'A_mm_output', 'B_mm_output'):
            for slot in ('0', '1') if label.endswith('_operands') else ('',):
                replay.append(dict(repeat=phase, label=label, slot=slot, **compare('observed', phase, (*prefix, label),
                    'observed', phase, (CHECKPOINT, 0, 'recompute', TARGET, label), slot)))
        x = get('observed', phase, (*prefix, 'B_mm_operands'), '0')
        w = get('observed', phase, (*prefix, 'B_mm_operands'), '1')
        g = get('observed', phase, (CHECKPOINT, 0, 'backward', TARGET, 'B_cotangent'))
        incoming = get('observed', phase, ('q1', 'incoming_B_gradient'))
        require(x.shape[-1] == w.shape[0] and tuple(g.shape) == (*x.shape[:-1], w.shape[1])
                and tuple(incoming.shape) == (w.shape[1], w.shape[0]), 'B VJP dimensions differ')
        # Float64 algebra is an interpretation reference, never the Ascend
        # accumulation/rounding oracle or a kernel nondeterminism verdict.
        require(x.numel()//x.shape[-1] * w.numel() <= 128*1024**2, 'CPU VJP work budget exceeded')
        analytical = g.double().reshape(-1, g.shape[-1]).T @ x.double().reshape(-1, x.shape[-1])
        prior = get('observed', phase, ('q1', 'prior_B_gradient'))
        post = get('observed', phase, ('q1', 'post_B_gradient'))
        p_in = get('observed', phase, (CHECKPOINT, 0, 'backward', TARGET, 'producer_incoming'))
        p_out = get('observed', phase, (CHECKPOINT, 0, 'backward', TARGET, 'producer_outgoing'))
        scalar = get('observed', phase, (*prefix, 'producer_operand'))
        require(scalar.numel() == 1, 'producer scalar differs')
        vjp.append(dict(repeat=phase, cpu_float64_B_vjp=difference(torch, analytical, incoming.double()),
                   accumulation=difference(torch, prior+incoming, post),
                   producer_edge=difference(torch, p_out, g),
                   cpu_producer_multiply=difference(torch, p_in*scalar.to(p_in.dtype), p_out)))
        for key in sorted(BOUNDARIES-{('q1', 'incoming_B_gradient')}):
            observer.append(dict(repeat=phase, key=list(key),
                **difference(torch, get('control', phase, key), get('observed', phase, key))))
    # Cross-link actual payload hashes to observed dispatch records, not just the
    # manifest: an inventory made from unrelated tensors cannot validate.
    events = doc['events']
    require(events['complete'] is True and len(events['records']) == 2, 'event coverage incomplete')
    require(len(events['producer']) == 2 and all(set(x) == {'0'} and x['0']['node'] == 'MulBackward0'
            and x['0']['edge'] == 0 and 1 <= x['0']['search_nodes'] <= 8 for x in events['producer']),
            'producer provenance differs')
    for phase in (0, 1):
        records = {tuple(e['key']): e['observation'] for e in events['records'][phase]}
        require(len(records) == len(events['records'][phase]), 'duplicate event')
        for e in doc['entries']:
            i = e['identity']
            if i['pair'] != 'observed' or i['repeat'] != phase:
                continue
            o = records.get(tuple(i['key']))
            if i['slot']:
                require(isinstance(o, list) and len(o) == 2, 'event operand missing')
                o = o[int(i['slot'])]
            require(o == dict(e['metadata'], sha256=e['sha256']), 'event/payload provenance mismatch')
        producer_op = records.get((CHECKPOINT, 0, 'backward', TARGET, 'producer_operator'))
        require(producer_op and producer_op['name'] in ('aten.mul.Tensor', 'aten.mul.Scalar')
                and producer_op['kwargs'] == {}, 'producer dispatch missing')
        p_in = records[(CHECKPOINT, 0, 'backward', TARGET, 'producer_incoming')]
        p_out = records[(CHECKPOINT, 0, 'backward', TARGET, 'producer_outgoing')]
        require(producer_op['left'] == {k:v for k,v in p_in.items() if k != 'sha256'}
                and producer_op['output'] == {k:v for k,v in p_out.items() if k != 'sha256'}, 'producer dispatch layout mismatch')
        for stage in STAGES:
            for label in ('A', 'B'):
                op = records.get((CHECKPOINT, 0, stage, TARGET, label+'_mm_operator'))
                require(op and op['name'] in ('aten.matmul.default', 'aten.mm.default') and op['kwargs'] == {}, 'actual matmul coverage missing')
            require(records.get((CHECKPOINT, 0, stage, TARGET, 'dropout_mask_op')) in
                    ('aten.native_dropout.default', 'aten.bernoulli_.float'), 'actual mask coverage missing')
            exit_kind = records.get((CHECKPOINT, 0, stage, TARGET, 'checkpoint_exit_kind'))
            require(exit_kind == ('returned' if stage == 'forward' else '_StopRecomputationError'), 'replay extent differs')
    context = doc['context']
    require(context['full_step_questions'] == 12 and context['q1_chunks'] == [1, 1]
            and context['seed'] == 2 and context['q0_prefix_preserved'] is True
            and context['full_step_denominator_preserved'] is True, 'question context differs')
    return dict(schema='k2-retained-cpu-validation-v1', index_sha256=expected_index,
                plan_sha256=plan_pin, tensors=len(tensors), bytes=total, cross_repeat=comparisons,
                forward_recompute=replay, selected_observer_control=observer, q0_q1_continuity=continuity, cpu_vjp_interpretation=vjp,
                scientific_acceptance=False, test_read=False,
                limitation='CPU algebra does not reproduce NPU rounding/layout/kernel order; no local nondeterminism or global root-cause claim')


def verify_plan(path, pin):
    path = safe(path)
    require(sha(path) == pin, 'prepared plan checksum differs')
    p = load(path)
    require(p['schema'] == 'k2-retained-plan-v1' and p['test_read'] is False
            and p['scientific_acceptance'] is False and p['activated'] is False, 'prepared scope differs')
    base = frozen()
    old = base.verify_plan(V4/'plan.json', p['v4_plan_sha256'])
    require(p['protocol'] == old['protocol'] and p['model'] == old['model'] and p['trainer'] == old['trainer'],
            'frozen recipe differs')
    require(p['expected_questions'] == 12 and p['expected_q1_chunks'] == 1 and p['attempt'] == 1,
            'q1 scope differs')
    require(p['limits'] == dict(tensor_bytes=MAX_TENSOR, total_bytes=MAX_BYTES, records=MAX_RECORDS,
                               index_bytes=MAX_INDEX), 'retention budget differs')
    require(p['files'] == dict(old['files'], **{str(Path(__file__).resolve()): sha(__file__)}), 'input inventory differs')
    for f, h in p['files'].items():
        require(sha(f) == h, 'dependency changed: '+f)
    require(Path(p['out']) == path.parent/'results' and path.name == 'plan.json', 'output identity differs')
    for f, h in p['evidence'].items():
        require(sha(f) == h, 'frozen evidence changed: '+f)
    return p


def activation_guard(root, pin):
    root = safe(root)
    a = load(root/'ACTIVATION.json')
    require(a.get('schema') == 'k2-retained-parent-activation-v1' and a.get('plan_sha256') == pin
            and a.get('authorized_by') == 'parent' and a.get('allow_npu') is True
            and a.get('test_read') is False and a.get('no_TEST') is True
            and a.get('independent_prepared_review_passed') is True, 'parent activation required')
    review = safe(a['review_path'])
    require(sha(review) == a['review_sha256'], 'prepared review changed')
    verdict = load(review)
    require(verdict.get('plan_sha256') == pin and verdict.get('prepared_accepted') is True
            and verdict.get('reviewer') != 'retained-tensor-preparer', 'independent prepared review required')
    predecessor = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_k0_chip3_20261101_v1')
    for name in ('ENGINEERING_EVAL_EXIT.json', 'attempts/1/RELEASE.json', 'execution.json'):
        require(sha(predecessor/name) == a['predecessor_pins'][name], 'Instruct K0 release pin differs')
    terminal = load(predecessor/'ENGINEERING_EVAL_EXIT.json')
    release = load(predecessor/'attempts/1/RELEASE.json')
    execution = load(predecessor/'execution.json')
    require(release['chip'] == 3 and release['run'] == execution['run']
            and type(terminal['exit_code']) is int and type(release['exit_code']) is int
            and release['exit_code'] == terminal['exit_code'] and terminal['attempt'] == 1
            and release['container'] == execution['container']+'-a1', 'Instruct K0 not durably released')
    receipt = load(predecessor/'attempts/1/LAUNCH_RECEIPT.json')
    require(sha(predecessor/'attempts/1/LAUNCH_RECEIPT.json') == a['predecessor_pins']['attempts/1/LAUNCH_RECEIPT.json']
            and release['container_id'] == receipt['id'] and receipt['sha256'] == a['predecessor_pins']['execution.json'], 'released container identity differs')
    require(a.get('automatic_rerun') is False, 'automatic rerun forbidden')
    return a


def run(path, pin):
    p = verify_plan(path, pin)
    root, out = Path(path).parent, Path(p['out'])
    activation_guard(root, pin)  # before importing any device backend
    require(not out.exists() and not (root/'RUN_INTENT.json').exists(), 'fresh run only; no automatic rerun')
    atomic(root/'RUN_INTENT.json', dict(plan_sha256=pin, test_read=False))
    base = frozen()
    out.mkdir()
    atomic(out/'RUN.json', dict(plan_sha256=pin, scientific_acceptance=False, test_read=False))
    import torch
    import torch_npu
    store = Retention(out.parent/'retained', torch, pin, torch_npu.get_npu_format)
    old_source = base.source
    traces = []
    def patched_source(filename):
        module = old_source(filename)
        if Path(filename).name == 'train_r3.py':
            original_data = module.Data
            class Data(original_data):
                def step_units(self, step):
                    result = super().step_units(step)
                    require(step == 0 and hashlib.sha256(canonical(result[1])).hexdigest() == p['step_units_sha256'],
                            'frozen seed2 step0 question context differs')
                    return result
            module.Data = Data
        if Path(filename).name == 'r3_k2_reference_trace.py':
            original = module.ReferenceTrace
            class Trace(original):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.pair_index = len(traces)
                    traces.append(self)
                def observe(self, *args):
                    q = self.index
                    super().observe(*args)
                    if self.pair_index == 0 and q in (0, 1):
                        parameter = dict(self.trainable)[TARGET+'.lora_B.default.weight']
                        if q == 0:
                            store.save('control', self.phase, ('q0', 'post_B_gradient'), parameter.grad)
                            store.save('control', self.phase, ('q1', 'prior_B_gradient'), parameter.grad)
                        else:
                            store.save('control', self.phase, ('q1', 'post_B_gradient'), parameter.grad)
            module.ReferenceTrace = Trace
        return module
    base.source = patched_source
    base.verify_plan = lambda unused_path, unused_pin: p
    # Keep the original class outside the replaced constructor's namespace.
    probe_class = frozen().BackwardProbe
    factory_base = types.SimpleNamespace(BackwardProbe=probe_class)
    base.BackwardProbe = lambda t, model, rng, **kwargs: make_probe(factory_base, t, model, rng, store, kwargs.get('backend_format'))
    rc = 1
    try:
        result = base.run(path, pin)
        require(result['reference_questions'] == 12 and result['backward_probe']['complete'], 'actual q1 coverage differs')
        context = dict(full_step_questions=12, q1_chunks=result['backward_probe']['coverage'], seed=2,
                       q0_prefix_preserved=True, full_step_denominator_preserved=True,
                       protocol=p['protocol'], source_pins=p['files'], q1_reference_context=[])
        context['q1_chunks'] = [c['chunks'] for c in result['backward_probe']['coverage']]
        for trace in traces:
            context['q1_reference_context'].append(trace.reference[1][0])
        index_pin = store.finish(result['backward_probe'], context)
        report = validate(store.root, index_pin, pin, torch)
        atomic(out/'CPU_RECONSTRUCTION.json', report)
        result['retained_index_sha256'] = index_pin
        result['cpu_reconstruction_sha256'] = sha(out/'CPU_RECONSTRUCTION.json')
        result['observer_control_note'] = 'Both pairs retain frozen question-boundary synchronization; only observed pair adds branch copies/hooks. Selected control deltas in CPU_RECONSTRUCTION. Equality cannot rule out observer suppression.'
        atomic(out/'TRACE.json', result)
        rc = 0
        return result
    finally:
        if out.exists():
            atomic(out/'EXIT.json', dict(exit_code=rc, plan_sha256=pin, scientific_acceptance=False, test_read=False))


def launcher(path, pin):
    path = safe(path); root = path.parent
    require(sha(path) == pin, 'execution checksum differs')
    e = load(path)
    require(e['schema'] == 'r3-k2-reference-trace-execution-retained-v1' and e['chip'] == 3
            and e['out'] == str(root) and e['test_read'] is False and e['scientific_acceptance'] is False,
            'execution scope differs')
    for f, h in e['tools'].items():
        require(Path(f).parent == root/'tools' and sha(f) == h, 'launcher dependency changed')
    helper = root/'tools/r3_k2_benchmark_launcher.py'
    require(sha(helper) == frozen().FROZEN_LAUNCHER_SHA256, 'lifecycle helper changed')
    L = source(helper)
    original_atomic = L.atomic
    def runtime_atomic(filename, data):
        return original_atomic(root/'SUPERVISOR_RELAUNCH.json' if Path(filename) == root/'RELAUNCH.json' else filename, data)
    L.atomic = runtime_atomic
    def verify(filename, expected):
        require(Path(filename) == path and expected == pin and sha(path) == pin, 'execution changed')
        require(e['image'] == L.IMAGE and e['allocation'] == str(L.BASE/'CHIP-ALLOCATION.json')
                and root.is_relative_to(L.BASE/'r3_runs') and e['run'] == str(root.relative_to(L.BASE)), 'resource binding differs')
        require(e['launcher'] == e['benchmark'] == str(Path(__file__).resolve()), 'entrypoint binding differs')
        require(set(e['tools']) == {str(root/'tools'/n) for n in (*L.TOOLS, 'r3_k2_retained_tensor_probe.py')}, 'launcher inventory differs')
        for f, h in e['tools'].items():
            require(sha(f) == h, 'launcher changed')
        p = verify_plan(e['benchmark_plan'], e['benchmark_sha256'])
        require(e['benchmark_plan'] == str(root/'plan.json') and e['container'] == 'nga-k2-retained-'+e['benchmark_sha256'][:16], 'plan binding differs')
        return e, p
    def spec(execution, p, filename, expected):
        K = source(root/'tools/r3_final_container.py')
        mounts = {str(root): True, str(root/'tools'): False, str(root/'plan.json'): False,
                  str(path): False, str(root/'ACTIVATION.json'): False,
                  str(V4/'code'): False, str(V4/'tools/r3_k2_backward_probe.py'): False,
                  str(V4/'plan.json'): False, p['model']: False, L.TRAIN: False}
        # Activation/release proofs and frozen evidence are read-only mounts.
        a = activation_guard(root, e['benchmark_sha256'])
        mounts[a['review_path']] = False
        predecessor = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_k0_chip3_20261101_v1')
        for n in a['predecessor_pins']:
            require(n in ('execution.json', 'ENGINEERING_EVAL_EXIT.json', 'attempts/1/RELEASE.json', 'attempts/1/LAUNCH_RECEIPT.json'), 'unexpected predecessor file')
            mounts[str(predecessor/n)] = False
        for f in p['evidence']:
            mounts[f] = False
        return dict(name=e['container']+'-a1', image=L.IMAGE,
                    cmd=['-B', '-P', e['benchmark'], 'run', '--plan', str(root/'plan.json'), '--sha256', e['benchmark_sha256']],
                    mounts=mounts, devices=['/dev/davinci_manager', '/dev/devmm_svm', '/dev/hisi_hdc', '/dev/davinci3'],
                    environment={**K.ENV, 'NGA_R0_CODE': str(V4/'code/r0_code')})
    original_load = L.load
    def checked_load(filename):
        value = original_load(filename)
        if Path(filename) == root/'results/TRACE.json':
            require(value['backward_probe']['complete'] and value['control']['complete']
                    and sha(root/'retained/INDEX.json') == value['retained_index_sha256']
                    and sha(root/'results/CPU_RECONSTRUCTION.json') == value['cpu_reconstruction_sha256'], 'retained output incomplete')
        return value
    L.verify, L.spec, L.load = verify, spec, checked_load
    verify(path, pin)
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('op', choices=('verify', 'validate', 'run', 'start', 'supervise'))
    ap.add_argument('--plan', required=True); ap.add_argument('--sha256', required=True)
    ap.add_argument('--index-sha256'); ap.add_argument('--attempt', type=int, default=1)
    args = ap.parse_args()
    require(args.attempt == 1, 'one attempt only')
    if args.op == 'validate':
        os.environ['TORCH_DEVICE_BACKEND_AUTOLOAD'] = '0'
        import torch
        print(json.dumps(validate(Path(args.plan), args.index_sha256, args.sha256, torch), indent=2))
    elif args.op == 'verify':
        launcher(args.plan, args.sha256)
        print('PREPARED_VERIFIED_NOT_ACTIVATED')
    elif args.op == 'run':
        from contextlib import redirect_stdout, redirect_stderr
        root = Path(args.plan).parent
        activation_guard(root, args.sha256)
        require(not (root/'RUN_INTENT.json').exists(), 'no rerun after run intent')
        rc = 1
        try:
            with (root/'probe-container.log').open('a', buffering=1) as log:
                with redirect_stdout(log), redirect_stderr(log):
                    try:
                        run(args.plan, args.sha256); rc = 0
                    except BaseException:
                        import traceback
                        traceback.print_exc()
                        raise
        finally:
            if (root/'results/RUN.json').exists() and not (root/'results/EXIT.json').exists():
                atomic(root/'results/EXIT.json', dict(exit_code=rc, plan_sha256=args.sha256, scientific_acceptance=False, test_read=False))
    else:
        L = launcher(args.plan, args.sha256)
        e = load(args.plan)
        activation_guard(Path(args.plan).parent, e['benchmark_sha256'])
        print(json.dumps(L.start(args.plan, args.sha256) if args.op == 'start' else L.supervise(args.plan, args.sha256)))


if __name__ == '__main__':
    main()
