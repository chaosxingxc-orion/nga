# E15 — Independent Open-Jev public-test audit and automatic completion

Preregistered 2026-10-30 before this CPU post-processing job starts. E14 inference is
already running with its unchanged frozen protocol. This entry adds independent artifact
verification; it does not alter its predictions, metrics, split or acceptance thresholds.

## Purpose, hypothesis and counterpart

Defect registry row 12: measurement validity. Establish that E14's final report follows
from exactly its 10,356 public test records and frozen native readout configuration.
A degenerate verifier could accept any successful marker, or reject all artifacts. The
counterparts are a complete valid fixture versus missing/extra/duplicate records, changed
candidate order, hash-consistent false reports/probabilities, omitted executable dependencies,
wrong model token counts, failure markers and stale wrapper completion. This audit is not
an invariance measurement and does not equate aggregate accuracy with consistency.

## Frozen setup

Input run: `reference_inference/openjev2_test_20261030_v3/`, retained inference container
`nga-reference-openjev2-test-v3` on authorized host 175. Native public test has 10,356 rows:
9,995 hard and 361 soft. Preserve original data/config/model/code files; no inference restart,
new model run, truncation, sampling or threshold fitting occurs here.

Independent stdlib verifier `tools/verify_reference_openjev.py` imports neither the inference
driver nor native metrics. It checks required dependency coverage derived from filesystem
roots and executable names, every frozen hash before/after audit, config/launch/terminal/
wrapper/report identity, all input/receipt/length identities and order, complete IDs and
source/kind counts, logits-to-probabilities, and model token counts against length receipts.

Recompute serving-temperature and raw T=1 hard accuracy, expected accuracy, NLL with 1e-15
floor, distribution Brier, expected one-hot Brier, ECE15 and fixed coverage thresholds
0.5/0.7/0.8/0.9/0.95/0.99; also source/kind serving panels. Exact-hard one-hot denominator,
first-argmax tie, distribution normalization and probability-bin boundaries follow E14's
published native definitions. Arithmetic comparison tolerance is 1e-10 relative / 1e-12
absolute for independent CPU double recomputation, not a cross-device equivalence gate.

Any exact 0/1 metric, identical source-cell metric, or cell below 30 rows produces a pointer
in `review_flags`. Thirty is a triage threshold only, not a minimum for excluding a row or
changing a metric. Flags force a `REVIEW_REQUIRED` status; no automatic scientific approval.

## Execution and acceptance

CPU-only retained detached container `nga-reference-openjev2-finish-v3`, existing immutable
Ascend image SHA256 `8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.
Output: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_test_20261030_v3_finish/`.
No NPU devices. Freeze verifier, test, finisher, registration, launch/wrapper, inference
config and launch receipt. Store exact launch/relaunch command, log, 15-second timestamped
heartbeat, atomic terminal and wrapper EXIT on CephFS.

The finisher uses only Docker HTTP GET inspect to verify inference container ID, image,
command/entrypoint, physical device map and authoritative exited/0 state. It waits for both
that state and successful E14 terminal/wrapper, then invokes the independent verifier. It
rechecks completion after audit and hashes its output. Missing Docker handle or contradictory
terminal fails, never launches/restarts inference. Transient observation errors are recorded
as a failed observer, not as proof that inference failed; inference is left untouched.

Completion is a scoped artifact/metric verification. It cannot establish contamination-free
training, unseen generalization, old 10,532-row test equivalence, model-quality improvement,
or Astra approval. Its suspicious-result flags require separate diagnosis.

## Results

Before launch, 16 CPU tests passed, including the actual verifier subprocess success and
hash-consistent forged-report failure. Full E14 output is not yet available; no test score
or successful full audit is claimed.

2026-10-30 15:53 UTC execution update: nine finisher inputs were frozen before launch.
Retained CPU container `727565c3f84276f868a416455eedb0d8833387051c077919052f8cc747c8f1b4`
is running; its 15:53:13Z heartbeat reports
`waiting_for_inference_terminal_and_container_exit`, progress 0/2, chips 0. Actual image,
command, entrypoint and plan hash are in its `LAUNCH_RECEIPT.json`. E14 is untouched.

## Verdict

Pending E14 completion and the independent audit. Astra review remains separate.
