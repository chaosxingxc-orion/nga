"""Bounded, reference-only observers for K2 repeatability diagnosis.

No optimizer updates or candidate acceptance. Observers synchronize and may
suppress timing-sensitive differences; agreement is therefore inconclusive.
The original trainer function is retained except for one post-backward observer.
"""
import ast
import hashlib
import json
import math
import types
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def instrument(trainer, observer, chunk_observer=None, before_backward=None, reduction_observer=None):
    tree = ast.parse(Path(trainer.__file__).read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'step_loss')
    matches = [n for n in ast.walk(function) if isinstance(n, ast.For)
               and isinstance(n.target, ast.Name) and n.target.id == 'e'
               and isinstance(n.iter, ast.Name) and n.iter.id == 'exs']
    if len(matches) != 1:
        raise ValueError('unexpected K2 question loop')
    loop = matches[0]
    expected = ast.parse('total += float(lq.detach())').body[0]
    if ast.dump(loop.body[-1]) != ast.dump(expected):
        raise ValueError('question accumulation boundary differs')
    original = ast.dump(function)
    loop.body.append(ast.parse('_trace_observer(e, seqs, starts, s, lq, total)').body[0])
    # Removing the observer must reproduce the exact original AST.
    inserted = loop.body.pop()
    if ast.dump(function) != original:
        raise ValueError('instrumentation altered reference computation')
    loop.body.append(inserted)
    if before_backward is not None:
        boundaries = [n for n in loop.body if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Name) and n.test.id == 'backward']
        if len(boundaries) != 1 or len(boundaries[0].body) != 1:
            raise ValueError('backward boundary differs')
        call = ast.parse('_trace_before(s)').body[0]
        boundaries[0].body.insert(0, call)
    module = types.ModuleType('k2_observed_reference')
    module.__dict__.update(trainer.__dict__)
    module._trace_observer = observer
    module._trace_before = before_backward
    if chunk_observer is not None:
        rows = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'row_logprob_sums')
        boundaries = []
        for node in ast.walk(rows):
            for field, value in ast.iter_fields(node):
                if isinstance(value, list):
                    for index, item in enumerate(value):
                        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'bi_t' for t in item.targets):
                            boundaries.append((value, index))
        if len(boundaries) != 1:
            raise ValueError('scoring index boundary differs')
        body, index = boundaries[0]
        body.insert(index, ast.parse('_trace_chunk(chunk, ids, mask, bi, ti, tg, owner)').body[0])
        module._trace_chunk = chunk_observer
        if reduction_observer is not None:
            reductions = []
            for node in ast.walk(rows):
                for field, value in ast.iter_fields(node):
                    if isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'sums' for t in item.targets):
                                reductions.append((value, i))
            if len(reductions) != 1:
                raise ValueError('score reduction boundary differs')
            body, i = reductions[0]
            body.insert(i+1, ast.parse("_trace_reduction('after', owner, sums)").body[0])
            body.insert(i, ast.parse("_trace_reduction('before', owner, tok_lp)").body[0])
            module._trace_reduction = reduction_observer
        exec(compile(ast.fix_missing_locations(ast.Module(body=[rows], type_ignores=[])),
                     trainer.__file__, 'exec'), module.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 trainer.__file__, 'exec'), module.__dict__)
    return module.step_loss


class ReferenceTrace:
    """Retain at most a fixed number of questions and bytes of CPU gradients.

    Tensor values remain in memory. Public output contains only fingerprints,
    finite aggregate differences and up to eight names at the first divergence.
    """
    def __init__(self, torch, trainable, rng_snapshot, gradient_diagnostic,
                 max_questions=32, max_bytes=2 * 1024**3):
        self.torch = torch
        self.trainable = trainable
        self.rng_snapshot = rng_snapshot
        self.gradient_diagnostic = gradient_diagnostic
        self.max_questions = max_questions
        self.max_bytes = max_bytes
        self.reference = []
        self.bytes_retained = 0
        self.phase = 0
        self.index = 0
        self.first_difference = None
        self.comparisons = []
        self.truncated = False
        self.chunks = []

    def observe_chunk(self, chunk, ids, mask, bi, ti, tg, owner):
        if len(self.chunks) >= 4096:
            self.truncated = True
            raise ValueError('trace chunk budget exceeded')
        self.chunks.append(fingerprint({'chunk': chunk, 'ids': ids.detach().cpu().tolist(),
                                       'mask': mask.detach().cpu().tolist(),
                                       'bi': bi, 'ti': ti, 'tg': tg, 'owner': owner}))

    def begin_repeat(self):
        if self.phase != 0 or not self.reference:
            raise ValueError('reference phase missing or repeat already started')
        self.phase = 1
        self.index = 0

    def observe(self, example, seqs, starts, scores, loss, total):
        if self.index >= self.max_questions:
            self.truncated = True
            raise ValueError('trace question budget exceeded')
        self.torch.npu.synchronize()
        gradients = {n: p.grad.detach().cpu().clone() for n, p in self.trainable if p.grad is not None}
        if len(gradients) != len(self.trainable):
            raise ValueError('missing accumulated gradient')
        if not all(self.torch.isfinite(g).all().item() for g in gradients.values()):
            raise ValueError('nonfinite accumulated gradient')
        score_values = scores.detach().float().cpu().tolist()
        if not all(math.isfinite(v) for v in [*score_values, float(loss.detach()), total]):
            raise ValueError('nonfinite question record')
        record = {
            'question': self.index,
            'input_sha256': fingerprint({'example': example, 'seqs': seqs, 'starts': starts}),
            'scores_sha256': fingerprint(score_values),
            'chunks_sha256': fingerprint(self.chunks),
            'chunks': len(self.chunks),
            'loss': float(loss.detach()), 'cumulative_loss': total,
            'gradient_metadata_sha256': fingerprint([
                [n, str(g.dtype), list(g.shape)] for n, g in sorted(gradients.items())]),
            'rng': self.rng_snapshot(self.torch),
        }
        self.chunks = []
        if self.phase == 0:
            size = sum(g.numel() * g.element_size() for g in gradients.values())
            if self.bytes_retained + size > self.max_bytes:
                self.truncated = True
                raise ValueError('trace memory budget exceeded')
            self.bytes_retained += size
            self.reference.append((record, gradients))
        else:
            if self.index >= len(self.reference):
                raise ValueError('repeat has extra question')
            prior, old_gradients = self.reference[self.index]
            metric = {'loss': prior['loss'], 'stats': {}}
            current = {'loss': record['loss'], 'stats': {}}
            delta = self.gradient_diagnostic(self.torch, metric, old_gradients, current, gradients)
            flags = {k: record[k] == prior[k] for k in record if k != 'question'}
            same = all(flags.values()) and delta['exact']
            self.comparisons.append({'question': self.index, 'equal': same, 'components_equal': flags})
            if not same and self.first_difference is None:
                self.first_difference = {'question': self.index, 'components_equal': flags,
                                         'gradient_diagnostic': delta}
            self.reference[self.index] = (prior, {})
        self.index += 1

    def summary(self):
        complete = self.phase == 1 and self.index == len(self.reference) and self.index > 0 and not self.truncated and not self.chunks
        return {'schema': 'r3-k2-reference-trace-v1', 'complete': complete,
                'truncated': self.truncated, 'reference_questions': len(self.reference),
                'repeat_questions': self.index if self.phase == 1 else 0,
                'peak_reference_bytes': self.bytes_retained,
                'comparisons': self.comparisons, 'first_difference': self.first_difference,
                'scientific_acceptance': False, 'test_read': False,
                'scope': 'first observed question-boundary divergence; instrumentation may suppress mismatch; no timing or acceptance'}
