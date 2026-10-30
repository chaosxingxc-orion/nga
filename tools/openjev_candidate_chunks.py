"""Bound Open-Jev backbone batch memory without altering its padded inputs.

The native DecisionModel still creates prompts, globally pads, runs its FP32 head,
and formats responses. Only independent backbone batch rows are partitioned.
This requires empirical numerical admission; mathematical independence alone does
not establish identical floating-point results.
"""
from contextlib import contextmanager
from types import SimpleNamespace


@contextmanager
def candidate_chunks(backbone, chunk_rows=8, observer=None):
    import torch
    if type(chunk_rows) is not int or chunk_rows < 1:
        raise ValueError("positive integer chunk_rows required")
    original = backbone.forward

    def forward(*args, **kwargs):
        if args or set(kwargs) != {"input_ids", "attention_mask", "use_cache", "return_dict"}:
            raise ValueError("unexpected backbone call; refuse implicit slicing")
        ids, mask = kwargs["input_ids"], kwargs["attention_mask"]
        if ids.ndim != 2 or ids.shape != mask.shape or kwargs["use_cache"] is not False or kwargs["return_dict"] is not True:
            raise ValueError("unsupported backbone shape/cache/return protocol")
        outputs = []
        for start in range(0, ids.shape[0], chunk_rows):
            end = min(start + chunk_rows, ids.shape[0])
            # Preserve the *global* padded sequence length and every mask position.
            part = dict(kwargs, input_ids=ids[start:end], attention_mask=mask[start:end])
            if observer is not None:
                observer(start, end, int(ids.shape[1]))
            result = original(**part)
            hidden = result.last_hidden_state
            if tuple(hidden.shape[:2]) != (end - start, ids.shape[1]):
                raise ValueError("backbone changed batch/sequence shape")
            outputs.append(hidden)
        if not outputs:
            raise ValueError("empty candidate batch")
        return SimpleNamespace(last_hidden_state=torch.cat(outputs, dim=0))

    backbone.forward = forward
    try:
        yield
    finally:
        backbone.forward = original
