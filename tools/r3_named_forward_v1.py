"""Version 1: explicit phase context and actual rightpad model-forward ranges.

No tensor reads, arithmetic, device synchronization, or scorer reimplementation.
The CPU batch list is retained to bind range membership to exact token operands.
"""
import contextlib
import hashlib
import json

ADAPTER_ID = 'named_model_forward_ranges_v1'
PHASES = ('cold_reference', 'split_gate', 'warmup', 'wall_0', 'wall_1', 'wall_2', 'trace')

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

class NamedForward:
    def __init__(self, scorer, plan_sha256, attempt, record_function):
        require(len(plan_sha256) == 64 and type(attempt) is int and attempt == 1, 'invalid generation')
        self.scorer, self.plan, self.attempt = scorer, plan_sha256, attempt
        self.record_function = record_function
        self.records, self.active, self.batch, self.ordinal = [], None, None, 0

    @contextlib.contextmanager
    def scope(self, phase, cell, rows):
        require(self.active is None and phase in PHASES, 'invalid/nested scope')
        ids = [r['id'] for r in rows]
        require(len(ids) == len(set(ids)), 'duplicate question ids')
        self.active, self.ordinal = (phase, cell, ids), 0
        try:
            yield
        finally:
            self.active, self.batch = None, None

    def __enter__(self):
        self.old_batch = self.scorer._score_flat_batch
        self.target = self.scorer.lm.model
        self.old_forward = self.target.forward
        def batch_call(batch, width, out, right_pad=True):
            require(self.active is not None and self.batch is None and right_pad is True, 'missing or nested batch context')
            self.batch = (batch, width)
            before = len(self.records)
            try:
                answer = self.old_batch(batch, width, out, right_pad=right_pad)
                require(len(self.records) == before + 1, 'batch must contain exactly one true forward')
                return answer
            finally:
                self.batch = None
        def forward(*args, **kwargs):
            require(self.active is not None and self.batch is not None, 'forward outside bound batch')
            phase, cell, ids = self.active
            batch, width = self.batch
            self.ordinal += 1
            name = f'nga.forward/{self.plan}/{self.attempt}/{phase}/{hashlib.sha256(cell.encode()).hexdigest()}/{self.ordinal}'
            members = []
            for i, j, tokens, candidate_length in batch:
                require(type(i) is int and 0 <= i < len(ids), 'batch question index differs')
                members.append(dict(question_id=ids[i], question_index=i, candidate_index=j, input_ids=list(tokens), candidate_length=candidate_length))
            row = dict(name=name, phase=phase, cell=cell, ordinal=self.ordinal, width=width, members=members, status='entered')
            context = self.record_function(name) if phase == 'trace' else contextlib.nullcontext()
            try:
                with context:
                    result = self.old_forward(*args, **kwargs)
                row['status'] = 'returned'
                return result
            finally:
                self.records.append(row)
        self.scorer._score_flat_batch, self.target.forward = batch_call, forward
        return self

    def __exit__(self, *exc):
        self.scorer._score_flat_batch, self.target.forward = self.old_batch, self.old_forward
        self.active, self.batch = None, None

    def manifest(self):
        require(self.active is None and len(self.records) == 21, 'forward population incomplete')
        for phase in PHASES:
            records = [r for r in self.records if r['phase'] == phase]
            require(len(records) == 3 and [r['ordinal'] for r in records] == [1, 2, 3], 'phase forward count differs')
            require(all(r['status'] == 'returned' for r in records), 'forward exception')
        require(len({r['name'] for r in self.records}) == 21, 'duplicate forward identity')
        return dict(schema='named-forward-manifest-v1', adapter=ADAPTER_ID, plan_sha256=self.plan, attempt=self.attempt, records=self.records, total_forwards=21, named_trace_forwards=3, scientific_acceptance=False, test_read=False)
