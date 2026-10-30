"""E38 draft: passive per-candidate byte fingerprints for native short-input paths.

This helper neither launches models nor changes E36 admission. A separately frozen
driver must compare traced/untraced predictions before accepting its localization.
Only the fixed E37 short-tail input (15 candidates, width 186) is supported here.
"""
from contextlib import contextmanager
import hashlib


MAX_TENSOR_BYTES = 128 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def compare_traces(left, right):
    """Require exact observed populations; report byte differences, not tolerances."""
    for trace in (left, right):
        validate_trace(trace)
    require(left['candidates'] == right['candidates'] == 15, 'Candidate population differs')
    require(left['width'] == right['width'] == 186, 'Global padding differs')
    require(left['order'] == right['order'], 'Observed module order differs')
    require(set(left['events']) == set(right['events']), 'Observed event set differs')
    differences = []
    for name in left['order']:
        a, b = left['events'][name], right['events'][name]
        require(a['dtype'] == b['dtype'] and a['row_shape'] == b['row_shape'],
                'Per-candidate metadata differs: ' + name)
        require(set(a['rows']) == set(b['rows']) == {str(i) for i in range(15)},
                'Missing or extra observed candidate: ' + name)
        changed = [i for i in range(15) if a['rows'][str(i)] != b['rows'][str(i)]]
        if changed:
            differences.append({'event': name, 'changed_candidates': changed})
    require(left['order'], 'Empty observation is not success')
    return {'exact': not differences,
            'first_differing_observed_event': differences[0] if differences else None,
            'differences': differences,
            'scope': 'Byte fingerprints of observed tensors; earliest observed difference is not a kernel cause.'}


def validate_trace(trace):
    order, events = trace['order'], trace['events']
    require(order and len(order) == len(set(order)) and set(order) == set(events),
            'Missing, repeated or unlisted observation event')
    require(set(trace['expected_events']) == set(events), 'Expected hooks did not all execute')
    seen = set()
    for chunk in trace['chunks']:
        start, end, width = chunk['range']
        require(type(start) is int and type(end) is int and 0 <= start < end <= 15
                and width == 186, 'Invalid recorded chunk')
        require(not seen.intersection(range(start, end)), 'Overlapping recorded chunks')
        seen.update(range(start, end))
        require(chunk['order'] == order, 'Observed event order differs across chunks')
    require(seen == set(range(15)), 'Incomplete recorded chunk population')
    for name in order:
        require(set(events[name]['rows']) == {str(i) for i in range(15)},
                'Missing or extra observed candidate: ' + name)


class Recorder:
    def __init__(self, torch, trace):
        self.torch, self.trace = torch, trace
        trace.update(candidates=15, width=186, events={}, order=[], expected_events=[], chunks=[])
        self.start, self.end, self.width = 0, 15, 186
        self.active = None

    def chunk(self, start, end, width):
        require(type(start) is int and type(end) is int and 0 <= start < end <= 15
                and width == 186, 'Unexpected chunk identity')
        self.start, self.end, self.width = start, end, width
        self.active = None

    def record(self, name, tensor, folded=False):
        t = self.torch
        require(t.is_tensor(tensor), 'Expected tensor: ' + name)
        require(tensor.numel() * tensor.element_size() <= MAX_TENSOR_BYTES,
                'Observation exceeds bounded tensor size: ' + name)
        batch = self.end - self.start
        if folded:
            require(tensor.ndim == 2 and tensor.shape[0] % (batch * self.width) == 0,
                    'Unexpected folded layout: ' + name)
            view = tensor.reshape(batch, self.width, -1, tensor.shape[-1])
        else:
            require(tensor.ndim >= 1 and tensor.shape[0] == batch,
                    'Unexpected batch axis: ' + name)
            view = tensor
        # Row-at-a-time copies bound retained host memory and preserve BF16 and
        # signed-zero bits. Reading synchronizes but never mutates model storage.
        row_shape = list(view.shape[1:])
        if self.active is None:
            self.active = {'range': [self.start, self.end, self.width], 'order': []}
            self.trace['chunks'].append(self.active)
        self.active['order'].append(name)
        cell = self.trace['events'].get(name)
        if cell is None:
            cell = self.trace['events'][name] = dict(dtype=str(view.dtype), row_shape=row_shape, rows={})
            self.trace['order'].append(name)
        require(cell['dtype'] == str(view.dtype) and cell['row_shape'] == row_shape,
                'Event layout changed across chunks: ' + name)
        for local, global_row in enumerate(range(self.start, self.end)):
            key = str(global_row)
            require(key not in cell['rows'], 'Repeated candidate observation: ' + name)
            cpu = view[local].detach().contiguous().cpu()
            raw = cpu.view(t.uint8).numpy().tobytes()
            cell['rows'][key] = hashlib.sha256(raw).hexdigest()


@contextmanager
def trace_path(backbone, torch, trace):
    """Trace fixed native module boundaries; yield candidate_chunks observer.

    Call inside evaluation/inference mode. Caller must validate the returned
    prediction against untraced execution, and freeze this helper with runtime.
    """
    require(not backbone.training, 'Training observation is not authorized')
    recorder = Recorder(torch, trace)
    handles, replaced = [], []
    layers = [(name, mod) for name, mod in backbone.named_modules()
              if type(mod).__name__ == 'Qwen3_5DecoderLayer']
    require(len(layers) in (24, 32), 'Unsupported or missing decoder layers')
    observed = []

    def hooks(name, module, folded=False):
        trace['expected_events'].extend([name + ':input', name + ':output'])
        def before(_module, args, kwargs):
            value = args[0] if args else kwargs.get('hidden_states')
            recorder.record(name + ':input', value, folded)
        def after(_module, args, kwargs, output):
            value = output[0] if isinstance(output, tuple) else output
            recorder.record(name + ':output', value, folded)
        handles.extend((module.register_forward_pre_hook(before, with_kwargs=True),
                        module.register_forward_hook(after, with_kwargs=True)))
        observed.append(name)

    def wrap_core(name, module):
        trace['expected_events'].extend([name + ':input:' + s for s in ['query', 'key', 'value', 'g', 'beta']])
        trace['expected_events'].append(name + ':output')
        original = module.chunk_gated_delta_rule
        require(getattr(original, '__name__', None) == 'torch_chunk_gated_delta_rule',
                'Runtime core is not the inspected native torch fallback')
        def wrapped(query, key, value, **kwargs):
            for suffix, tensor in [('query', query), ('key', key), ('value', value),
                                   ('g', kwargs['g']), ('beta', kwargs['beta'])]:
                recorder.record(name + ':input:' + suffix, tensor)
            result = original(query, key, value, **kwargs)
            require(isinstance(result, tuple) and len(result) == 2 and result[1] is None,
                    'Unexpected cached core output')
            recorder.record(name + ':output', result[0])
            return result
        module.chunk_gated_delta_rule = wrapped
        replaced.append((module, original))

    try:
        for lname, layer in layers:
            hooks(lname, layer)
            hooks(lname + '.input_layernorm', layer.input_layernorm)
            hooks(lname + '.post_attention_layernorm', layer.post_attention_layernorm)
            for suffix in ['gate_proj', 'up_proj', 'down_proj']:
                hooks(lname + '.mlp.' + suffix, getattr(layer.mlp, suffix))
            if layer.block_type == 'linear_attention':
                attn = layer.linear_attn
                for suffix in ['in_proj_qkv', 'in_proj_z', 'in_proj_b', 'in_proj_a', 'conv1d', 'out_proj']:
                    hooks(lname + '.linear_attn.' + suffix, getattr(attn, suffix))
                hooks(lname + '.linear_attn.norm', attn.norm, folded=True)
                wrap_core(lname + '.linear_attn.core', attn)
            elif layer.block_type == 'full_attention':
                for suffix in ['q_proj', 'k_proj', 'v_proj', 'o_proj']:
                    hooks(lname + '.self_attn.' + suffix, getattr(layer.self_attn, suffix))
            else:
                raise ValueError('Unsupported attention block: ' + str(layer.block_type))
        trace['observed_modules'] = observed
        yield recorder.chunk
        validate_trace(trace)
    finally:
        for handle in handles:
            handle.remove()
        for module, original in replaced:
            module.chunk_gated_delta_rule = original
