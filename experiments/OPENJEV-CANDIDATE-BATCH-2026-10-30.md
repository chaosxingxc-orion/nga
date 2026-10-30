# E36 — Open-Jev candidate batch memory and numerical admission

Pre-registered before new forwards, 2026-10-30. Defects 12/16: preserve task
identity and measurement while making the native candidate workload executable.
Unconstrained memory optimum is to discard candidates; forbidden. Discrimination
counterpart checks all ordered candidates, token masks, logits and actual outputs.
No gold-dependent selection, test score, training or architecture decision.

## Fixed engineering change

Existing E33 longest-sequence probe has 30 × 4096 padded tokens. E31 contains
243 eligible items with more padded tokens; index 633/637 has 255 × 2156 = 549780.
Do not intentionally run this larger unchunked workload into OOM. An external
context manager partitions only the backbone's batch axis into fixed 8-row chunks.
The native tokenizer still creates the complete batch with its original global
padding length. Masks, positions, candidate order, dtype, attention, native FP32
head, temperature and response formatting are unchanged. Last hidden states are
concatenated in original order. No per-chunk local repadding or candidate truncation.
Existing frozen sources/runs and unused formal configurations remain untouched.

## Selection and numerical thresholds

Choose engineering inputs only from preflight metadata, before predictions:
maximum sequence length, maximum candidate width, maximum padded-token count,
and maximum batch × length²; lowest original index breaks ties. Deduplicate.
The three fixed E33 synthetic types and the maximum-length input each receive
original-original and chunked-chunked forwards. Other selected workloads get two
chunked forwards only. Full original worst-batch equivalence is not claimed.

Record logits, native probabilities, full native response, selected decision and
consumed-token identity, timing, peak allocated/reserved and final reserved memory.
Each repeat probability delta must be <=1e-5, with identical token identity and
selected decision. Cross-mode logits/probability/wire deltas are compared against
the corresponding measured original-repeat delta, without enlarging the observed
noise floor. If any cross-mode delta exceeds original repeat noise (including a
zero-noise original), mark candidate_batch_admission=false and stop formal
admission even if the difference is <1e-5. Record the difference for parent review;
do not silently amend this criterion. Numerical evidence is workload-scoped.

## Execution and acceptance

Open-Jev2 then Open-Jev9 use only 175, existing immutable image and chip 1, after
allocation-lock and actual-live-device checks. Fixed retained detached containers,
CephFS logs/heartbeats/terminal, per-forward identity-bound receipts and exact
relaunch. Free chip only after actual container exit and terminal/output checks.
No formal inference launches in E36. Input envelope records all 9704 eligible
items, chunk rows, max chunk padded tokens and maximum retained hidden-state size.
Unit checks cover global padding, candidate order/tail, mask identity, unsupported
call arguments and cache refusal. Actual probe evidence is required beyond tests.
