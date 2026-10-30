"""K2 option-restricted loss (R3-SFT-PREREG §7.3).

    loss(question) = -log softmax(s)_gold ,  s_i = sum of log-probs of option i's identifier tokens
                      given the shared prompt (r0_code/scorer.py HFScorer's s_i, R3 prereg §3.2).

The brief requires computing this by scoring all options from ONE forward pass over the shared
prompt prefix (cache reuse) OR as separate rows, "correctness over speed," and a test asserting
training-time ``s`` equals the evaluation scorer's ``s`` on fixed rows to within 1e-3 nats.

This module provides exactly that scoring primitive, decoupled from any training step, so it can
be validated standalone (test_k2_loss.py) before any attempt to wire it into verl's trainer. It is
NOT wired into launch_sft.py (see that file's docstring: `k2` arm raises). Why: verl's SFTTrainer
loss function operates on ONE padded/nested batch of (input_ids, loss_mask) rows that each
contribute a token-level cross-entropy term (`verl.workers.utils.losses.sft_loss`); it has no
concept of "these N rows are the candidates of one question, reduce them with a softmax before the
loss." Building that cleanly needs either editing verl's loss call site (not allowed) or a
candidate-group id threaded through the whole data pipeline (custom collator + a replacement
`loss_fn` installed by a VERL_USE_EXTERNAL_MODULES patch on `SFTTrainer._build_engine`, which *is*
an available extension point). The second is the correct no-edit path forward and is sketched in
`k2_loss_patch.py`'s docstring, but was not run end-to-end in this task's time budget; reported as
an open item rather than shipped untested.

Scoring primitive, model-framework-agnostic (works given raw per-position log-softmax tensors):

    option_scores(logp, prefix_len, cand_ids)     -> list of s_i (sum log-prob per option)
    k2_loss(logp, prefix_len, cand_ids, gold_idx)  -> scalar -log softmax(s)_gold
"""
import math


def option_scores(logp_rows, prefix_len, cand_ids):
    """logp_rows[t] = log-softmax over the vocabulary at sequence position t, for a row that is the
    shared prompt followed by nothing (cand_ids are scored by reading positions prefix_len-1 ..
    prefix_len-1+len(c)-1, i.e. the standard "logits at position t predict token t+1" convention,
    identical to r0_code/scorer.py HFScorer.score). One row, many candidates (cache/prefix reuse).
    cand_ids: list of token-id lists (one per option). Multi-token candidates need logp_rows to
    extend past the prefix for THEIR OWN continuation (handled by the caller: for Qwen3.5 the
    hybrid recurrent state means candidates after the first token are NOT visible from the shared
    prefix alone and must come from a second forward pass per multi-token candidate branch, exactly
    the shared_prefix fallback r1_code/scorer.py already implements for evaluation. This function
    only does the position bookkeeping; it does not call a model.
    """
    out = []
    for c in cand_ids:
        total = 0.0
        pos = prefix_len - 1
        for q, tok in enumerate(c):
            total += logp_rows[pos + q][tok]
        out.append(total)
    return out


def softmax_nll(scores, gold_idx):
    m = max(scores)
    z = math.fsum(math.exp(s - m) for s in scores)
    return -(scores[gold_idx] - m - math.log(z))


def k2_loss_from_scores(scores, gold_idx):
    """-log softmax(s)_gold, the K2 per-question loss (prereg §7.3), given the already-summed s_i."""
    return softmax_nll(scores, gold_idx)
