# E19 — Original Nimble seven public test subsets

Preregistered 2026-10-30 before model test inference. Defect 12 (measurement validity) and 16 (comparable evidence). This fixed-checkpoint reproduction can be optimized by memorizing exposed labels; it does not establish unseen generalization or NGA training benefit. Candidate-order and changed-probability negative tests complement a valid receipt. Aggregate accuracy is not consistency.

## Data and setup

Seven original true-test subsets, 1,884 rows: MASSIVE en-US/de-DE 350 each, PAWS 250, Civil Comments 300, Aegis2 250, SummEval relevance 240 and consistency 144. Every `all.jsonl` matches the exact published `dataset_sha256` and ordered manifest IDs. Data restoration lives in `reference_inference/nimble_public_restore_20261030_v2/`; its terminal is rc 0. Aegis raw JSON serialization differs from the original exported JSONL, explicitly recorded; converted fixed selected data is byte-identical. Other raw inputs also match original export hashes. No resampling, silent substitution or whole-family splitting.

Original adapter revision `594dfdcfb6f94e3d0c0db7535180d3c71689169a`, verified SHA256 `ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b`, Qwen3.5-9B Instruct revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. V1 prompt/schema, BF16 CPU safe merge and SDPA backbone, FP32 candidate-token projection, original candidate order and T=1.0. Full token preflight uses original prompt builder at 2048; overlong records fail, never truncate.

## Metrics

Use original `evaluate_public.evaluate_records` and `summarize_rows`: per-subset accuracy, one-hot multiclass sum-squares Brier, binary Brier for noul, NLL with floor 1e-15, top-candidate ECE10 with native bin edges, score expected-index MAE; Civil Comments separately reports Jensen–Shannon bits and total variation against human distribution. Preserve native score argmax classification and expected-score MAE separately. No mixed 3,880-row total is claimed. Independent recomputation remains an acceptance step.

## Execution

175 only, retained detached `nga-reference-nimble-public-test`, physical chip 3 after allocation lock/live map checks, existing immutable Ascend image. Run `reference_inference/nimble_public_test_20261030/`. Freeze all sources/model/tokenizer/data/manifests/executables before launch. Whole-test token preflight precedes model loading. Atomic item receipts bind config, input, candidate and prompt; corruption and noncontiguous prefix fail. CephFS logs, 15-second heartbeat, per-chip throughput/reserved memory, final hash-bound terminal, wrapper EXIT and exact relaunch survive connection loss. No automatic retry over a terminal; review and preserve old evidence first.

## Results and verdict

Pending full inference and independent verification. No new training or Astra approval.

2026-10-30 launch update: 149 files frozen before launch; five CPU tests passed (valid receipt,
changed input, changed candidate order, changed prompt and hash-consistent wrong probabilities).
Allocation was claimed under lock after checking live Docker mappings. Retained container
`723fa1b508d2a702d6d4084555267158d421563713920435812ce2ed5ce1150c` launched with exact image,
command, entrypoint, config and wrapper captured in `LAUNCH_RECEIPT.json`. Whole-test prompt
preflight and inference are pending; launch alone is not full success.

Same-day post-launch review note: the frozen fresh run predates stricter resume receipt checks.
It must **not be resumed** using its frozen driver. Repository code now checks ordered score/logit
keys, record index and recomputes stored student/distribution metrics from raw probabilities;
it preserves the original config-file hash in failure terminals and excludes reused rows from
throughput. Twelve CPU tests cover these corrections, including hash-consistent forged student
metrics. The running fresh inference is left unchanged; final acceptance requires independent
recomputation from raw scores, never trust in saved student fields alone. If interrupted, preserve
this directory and perform a reviewed migration to a corrected new frozen run.

Data-restoration operational correction: the first restore job produced structured rc 1 after
CA/timeout failures, despite its original wrapper exiting 0. It is retained and is not accepted.
The separate v2 job adds the environment's trusted CA bundle (no verification bypass), returns
nonzero on incomplete restoration, and completed all seven exact dataset hashes. Both attempts
are recorded; v2 is the only accepted restoration input.
