"""Bounded incoming-gradient and scoring-reduction observations, no optimizer.

Hooks return None. CPU copies synchronize and may suppress differences. Equality
under instrumentation is inconclusive; tensors remain in memory only.
"""
import hashlib
import json


class BoundaryTrace:
    def __init__(self, torch, trainable, max_bytes=2*1024**3, max_events=4096, backend_format=None):
        self.torch = torch
        self.trainable = list(trainable)
        self.max_bytes = max_bytes
        self.max_events = max_events
        self.backend_format = backend_format
        self.phase = 0
        self.question = 0
        self.reference = {}
        self.bytes_retained = 0
        self.peak_bytes = 0
        self.sequence = []
        self.reference_sequence = None
        self.comparisons = []
        self.active = False
        self.counts = {}
        self.handles = []
        self.events = 0
        self.failed = False
        self.chunk_counts = [0, 0]

    def install(self):
        if self.handles:
            raise ValueError('hooks already installed')
        for name, parameter in self.trainable:
            self.handles.append(parameter.register_hook(self.hook(name)))

    def close(self):
        for handle in self.handles:
            handle.remove()
        self.handles = []

    def hook(self, name):
        def observe(gradient):
            if self.active and self.question == 1:
                count = self.counts.get(name, 0)
                self.counts[name] = count+1
                self.capture(('incoming', name, count), gradient)
            return None
        return observe

    def metadata(self, value):
        result = {'shape': list(value.shape), 'dtype': str(value.dtype),
                  'stride': list(value.stride()), 'storage_offset': value.storage_offset(),
                  'contiguous': value.is_contiguous(), 'device': str(value.device)}
        result['backend_format'] = self.backend_format(value) if self.backend_format else None
        return result

    def capture(self, key, value):
        self.events += 1
        if self.events > self.max_events:
            self.failed = True
            raise ValueError('boundary event budget exceeded')
        self.sequence.append(key)
        metadata = None if value is None else self.metadata(value)
        tensor = None
        if value is not None:
            size = value.numel()*value.element_size()
            if self.bytes_retained+size > self.max_bytes:
                self.failed = True
                raise ValueError('boundary memory budget exceeded')
            tensor = value.detach().cpu().clone()
            if not bool(self.torch.isfinite(tensor).all()):
                self.failed = True
                raise ValueError('nonfinite boundary tensor')
        if self.phase == 0:
            if key in self.reference:
                raise ValueError('duplicate boundary key')
            self.reference[key] = (metadata, tensor)
            if tensor is not None:
                self.bytes_retained += tensor.numel()*tensor.element_size()
                self.peak_bytes = max(self.peak_bytes, self.bytes_retained)
        else:
            if key not in self.reference:
                raise ValueError('extra boundary event')
            prior_metadata, prior = self.reference.pop(key)
            same_presence = (prior is None) == (tensor is None)
            same_shape = same_presence and (prior is None or prior.shape == tensor.shape)
            same_dtype = same_shape and (prior is None or prior.dtype == tensor.dtype)
            equal = same_dtype and (prior is None or self.torch.equal(prior, tensor))
            mismatch = maximum = None
            if same_shape and prior is not None:
                mismatch = int((prior != tensor).sum())
                maximum = float((prior.double()-tensor.double()).abs().max()) if prior.numel() else 0.
            self.comparisons.append({'key': list(key), 'values_equal': equal,
                'metadata_equal': prior_metadata == metadata, 'reference_metadata': prior_metadata,
                'repeat_metadata': metadata, 'mismatched_elements': mismatch, 'max_abs_difference': maximum})
            if prior is not None:
                self.bytes_retained -= prior.numel()*prior.element_size()

    def before(self, scores):
        if self.question in (0, 1):
            for name, parameter in self.trainable:
                self.capture(('prior', self.question, name), parameter.grad)
        if self.question == 5:
            self.capture(('scores_before_backward',), scores)
        self.active = True

    def after(self):
        self.active = False
        if self.question in (0, 1):
            for name, parameter in self.trainable:
                self.capture(('post', self.question, name), parameter.grad)
        self.question += 1

    def reduction(self, stage, owners, tensor):
        if self.question != 5:
            return
        key = ('reduction', stage)
        count = self.counts.get(key, 0)
        self.counts[key] = count+1
        owner_pin = hashlib.sha256(json.dumps(owners, separators=(',', ':')).encode()).hexdigest()
        self.capture(('reduction', stage, count, owner_pin), tensor)

    def chunk(self):
        if self.question == 5:
            self.chunk_counts[self.phase] += 1

    def coverage(self, sequence, phase):
        keys = set(sequence)
        required = {('scores_before_backward',)}
        for name, parameter in self.trainable:
            for question in (0, 1):
                required.update({('prior', question, name), ('post', question, name)})
        incoming = {name: sum(k[0] == 'incoming' and k[1] == name for k in sequence)
                    for name, parameter in self.trainable}
        before = [k for k in sequence if k[0:2] == ('reduction', 'before')]
        after = [k for k in sequence if k[0:2] == ('reduction', 'after')]
        count = self.chunk_counts[phase]
        reductions = count > 0 and len(before) == len(after) == count
        reductions = reductions and [(k[2], k[3]) for k in before] == [(k[2], k[3]) for k in after]
        reductions = reductions and [k[2] for k in before] == list(range(count))
        return {'required_records_present': required <= keys,
                'incoming_counts': incoming, 'missing_incoming_leaves': sorted(n for n,c in incoming.items() if c == 0),
                'observed_chunks': count, 'paired_reductions_complete': reductions,
                'complete': required <= keys and bool(incoming) and all(incoming.values()) and reductions}

    def begin_repeat(self):
        if self.phase != 0 or self.question < 6 or not self.reference:
            raise ValueError('missing complete reference boundaries')
        self.reference_sequence = self.sequence
        self.sequence = []
        self.phase = 1
        self.question = 0
        self.counts = {}
        self.events = 0

    def summary(self):
        incoming = [x for x in self.comparisons if x['key'][0] == 'incoming']
        coverage = [self.coverage(self.reference_sequence or self.sequence, 0),
                    self.coverage(self.sequence, 1) if self.phase == 1 else None]
        return {'schema': 'r3-k2-boundary-trace-v1',
                'complete': self.phase == 1 and self.question >= 6 and not self.reference and not self.failed
                            and all(x and x['complete'] for x in coverage),
                'coverage': coverage,
                'questions_observed': self.question, 'peak_reference_bytes': self.peak_bytes,
                'event_order_equal': self.sequence == self.reference_sequence,
                'incoming_events': len(incoming), 'comparisons': self.comparisons,
                'scientific_acceptance': False, 'test_read': False,
                'scope': 'observed incoming/accumulated gradients and reduction boundaries; no causal or numerical acceptance'}
