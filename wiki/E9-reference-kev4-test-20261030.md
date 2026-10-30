# E9 — Native Kev-4B test reproduction

Status: preregistered 2026-10-30 before launch. Host 175; physical chip 2.

## Purpose and hypothesis

Extend E7's native reference inference to released Kev-4B on the same official decision-v7
and transfer-v4 test sets. Defect registry rows 12 and 16 motivate valid measurement and
comparable candidate evidence. E8 established loading and four development records on
the existing image; it did not establish full-suite performance or numerical equivalence.

The unconstrained perfect test model could memorize labels, so this reproduction does not
establish generalization or training benefit. Preserve original checkpoint, pointer readout,
prompt, option order and temperature; no fitting or checkpoint selection on these test scores.
The evidence verifier must accept genuine complete results and reject foreign/corrupt or
incomplete outputs. E7's independent synthetic counterexamples remain applicable.

## Frozen setup and metrics

Reuse the E7 driver without modifying its numeric policy: float32, eager attention, transformers
reference Gated DeltaNet, HF32 disabled, merged LoRA, native encoder/context and pointer head.
The Kev-4B checkpoint's Qwen3.5-4B-Base revision must equal the local mirror's
`1001bb4d826a52d1f399e183466143f4da7b741b`. Serving temperature comes from the checkpoint;
E8 observed 2.406050072164233, no new fitting. Exact model/config/tokenizer/code/data/launcher
hashes and image ID are recorded before running.

Automatic sequence: input verification -> model load -> each suite's two-record development
preflight -> full test -> complete denominator and report checks. All 1,176 decision records /
1,440 questions and 764 transfer records/questions are inferred. Primary clean denominators:
1,200 and 656, excluding permuted/NOTA variants. Original native summary preserves separate
task/variant results; report question accuracy, one-hot sum-squares Brier, ECE10 and NLL at
serving temperature and reconstructed raw temperature one. No aggregate accuracy is called
consistency. No cross-device equivalence threshold or significance claim is invented.

## Execution and acceptance

Run directory: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev4_test_20261030/`.
Container: `nga-reference-kev4-test`, detached and retained after exit, on confirmed free chip 2.
CephFS holds frozen source, pre-registration snapshot, exact launch and guarded restart commands,
15-second status/heartbeat, per-record atomic receipts, reports, DONE/FAILED and structured
terminal. Per-chip throughput, chip count (one) and reserved memory are recorded.

The driver validates saved input/config/content identities on resume, rejects duplicate or
unexpected records and refuses missing headline rows. The independent stdlib verifier recomputes
native/raw main metrics from all records and checks terminal/report bindings. A successful
container exit alone is insufficient. Descriptive comparisons to Kev-4B's release values retain
any discrepancy; no calibration or sample exclusion is adjusted to improve agreement.

Recovery uses `resume_reference_kev.py` after verifying ownership and container/device identity;
completed runs are not restarted. It archives stale terminal markers. Actual kill/restart
validation is a separate E10 engineering experiment, not evidence of model quality.

## Results

**2026-10-30 launch update:** container
`aec456d10b52a87736289e7ed186c7239b8d885e49df3f67c00915491c350140` was launched after
allocation and live device checks; 72 inputs/executable files are frozen. At 14:51:31 UTC,
the structured heartbeat reported decision-v7 test 244/1,176 records, 2.3026 questions/s/chip,
one chip, 16.7559 GiB reserved. No final score is claimed.

A subsequent code review found a potential STATUS writer race and insufficient container
binding in the original recovery helper. The running frozen code is unchanged. Completion
must agree across structured terminal, wrapper and Docker state. Any recovery must use the
corrected repository helper with container identity, entrypoint and exact-device binding,
not the helper frozen before the finding. `LAUNCH_RECEIPT.json` was captured from the original
live container and labels itself as post-launch evidence. See
`experiments/REFERENCE-INFERENCE-REVIEW-2026-10-30.md` for the issue and fixes.

Independent Astra substantive review remains pending; acknowledgments of rules are not review
verdicts. No training or locked NGA candidate test is involved.

## Verdict

Pending complete inference and evidence review.
