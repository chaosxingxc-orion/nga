# E7 — Native Kev-0.8B test evaluation with resumable automatic execution

Status: preregistered before launch, 2026-10-30. This is inference, not training.

## Purpose and hypothesis

Reproduce the published native Kev-0.8B decision-v7 and transfer-v4 test measurements
on host 175 in the existing Ascend image. Defect registry row 12 (measurement validity)
and row 16 (comparable evidence) motivate input identity, complete denominators and
native-interface preservation. No training benefit, consistency gate, or device equivalence
is inferred from accuracy alone.

An unconstrained perfect classifier could memorize test labels. These tests measure released
checkpoint performance, not proof of semantic generalization. The checkpoint, prompt,
temperature and all test records are fixed before running; no fitting or checkpoint selection
uses these scores. Published reference values and local reproduction remain separate.
For the evidence verifier, the degenerate optimum of rejecting everything is ruled out by
valid restart cases; corrupt payloads, wrong inputs, foreign stamps, incomplete question sets,
invalid probabilities and changed inputs must fail. A constant valid probability vector is
not a semantic success: these structural tests do not admit a consistency/generalization claim.

## Setup frozen before test inference

- Host `npu` (175), existing `nga-verl-qwen35-v030:20261029` image, one physical chip 1.
- Released Kev-0.8B adapter/head on its pinned Qwen3.5-0.8B-Base revision.
- Original `LocalPredictor`, native encoder and pointer head, checkpoint serving temperature,
  float32, eager attention, transformers reference Gated DeltaNet, HF32 off, merged LoRA.
- Original suite contexts; no truncation, omitted overlong records or fallback readout.
- Development first two records per suite are run twice before that suite's test. Probability
  coverage, finite logits and softmax arithmetic are checked (absolute 1e-5, an implementation
  arithmetic check, not a cross-device equivalence threshold). Repeat delta is diagnostic.
- Official complete `test.jsonl` partitions, verified against manifest hashes and counts.
  decision-v7 headline is 1,200 clean questions; transfer-v4 headline is 656. All stored variants
  are inferred, with permuted/NOTA statistics separate from clean headline.
- Native `prediction_rows` and `summarize`: question micro accuracy, one-hot sum-of-squares
  Brier, ECE10, NLL, selective metrics and task/variant breakdowns. Native heldout-source
  reporting follows the checkpoint. No overall accuracy is called consistency.
- Two temperature panels: native serving temperature and raw T=1 reconstructed from native
  returned logits by undoing the checkpoint temperature once. No temperature fitting.
- Exact image identity, runtime versions, executable code, checkpoints, base configuration,
  tokenizer files, development/test partitions and manifests are bound in frozen config.

## Execution and acceptance

Run directory `/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev08_test_20261030/`.
Fixed detached Docker name `nga-reference-kev08-test`, retained on exit. The automatic driver
executes input verification, model loading, each suite's preflight, full inference, scoring and
terminal publication in sequence. A failure prevents downstream execution and leaves a
nonzero terminal marker. `LAUNCH_EXACT.sh` and `RESUME_EXACT.sh` identify the launch/restart.

An exclusive driver lock prevents concurrent writers. Each record is atomically stored with
input identity, configuration identity and payload hash; resume validates content and native
option coverage, then recomputes aggregate reports. The driver refuses changed frozen files,
wrong runtime versions, duplicate IDs, unexpected files, incomplete rows and headline count
differences. Hash receipts detect accidental corruption; they are not signatures against a
malicious writer who can alter both content and receipts. CephFS holds logs and 15-second
status heartbeat, progress, questions/s/chip (one chip), reserved memory, reports and terminal.

`REFERENCE_COMPLETE.json` rc 0 plus verified report/rows hashes establishes computational
completion. Publication still requires review of the result provenance and discrepancies.
Neither process exit alone nor two development records establishes benchmark correctness.
Report differences from literature without tuning to erase them. Astra review remains pending
until an actual substantive audit is delivered; rule acknowledgments do not count.

## Results

**2026-10-30 launch update:** six CPU falsification tests passed before launch. Container
`b5bc4f66fffd9c2a7777ef5fd81f1adc36feb61317dc242136c28ee1c305d55b`
(`nga-reference-kev08-test`) was launched detached after checking chip 1's allocation and
the device mappings of all running containers. The run uses the immutable image ID
`sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.

At **14:24:27 UTC**, the structured heartbeat reported decision-v7 test progress 83/1,176
records, 2.2158 questions/s/chip (one chip), reserved memory 3.3574 GiB. These are live
progress figures, not a completed benchmark. Test output files were advancing and the
container was running; no final score is reported yet. The queue contains 1,440 decision-v7
questions and 764 transfer-v4 questions, including variants. The original pre-launch wiki
snapshot is preserved as `PREREGISTRATION.md` in the run directory.

## Verdict

**Completion update, 2026-10-30 14:39:25 UTC.** The driver terminal and wrapper DONE both
record rc 0; the retained container independently reports exited/0. The complete run contains
1,176 decision-v7 records (1,440 questions) and 764 transfer-v4 records/questions. A separate
stdlib verifier, which imports neither the driver nor upstream metrics, checked all 66 frozen
files, input and prediction identities, terminal/report bindings, full record/question coverage,
and recomputed native/raw clean accuracy, Brier, ECE10 and NLL. It returned
`VERIFIED_SCOPED` in `INDEPENDENT_AUDIT.json`; 15 synthetic audit tests passed, including
forged metrics after updating their file hashes. This does not independently validate every
upstream diagnostic or constitute Astra review.

| Official test | Clean n | Local accuracy | Published accuracy | Local serving Brier | Published serving Brier | Local ECE10 | Published ECE10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| decision-v7 | 1,200 | 0.837500 | 0.837500 | 0.230501236 | 0.230489268 | 0.018980717 | 0.018159859 |
| transfer-v4 | 656 | 0.696646341 | 0.696646341 | 0.396638059 | 0.396631916 | 0.046375031 | 0.044841305 |

Raw-temperature-one Brier/ECE10 are 0.261037402/0.100331076 for decision and
0.416444911/0.099264052 for transfer. Temperature was not fitted or modified.
`PUBLISHED_COMPARISON.json` preserves exact deltas and source hashes. The transfer upstream
predictions align on all 764 question keys and metadata; among 656 clean questions there are
zero argmax disagreements, maximum absolute probability delta 0.002194709, and two changed
confidence bins. No equivalence threshold was preregistered for that cross-hardware difference;
therefore this is a descriptive comparison, not a numerical-equivalence pass. Decision upstream
per-question rows are absent in the mirror, so its calibration discrepancy cannot yet be
localized. Identical aggregate accuracy alone does not prove identical predictions there.

After terminal, independent audit and container exit were checked, chip 1 was released.
No new formal training or locked NGA test was involved. **Astra review remains incomplete.**

**Recovery correction, same date:** the first frozen `RESUME_EXACT.sh` checks only container
exit and must not be used after resource reassignment. The repository now provides
`tools/resume_reference_kev.py`, which refuses successful-run restarts and checks allocation,
running-device mappings and image identity before starting a failed/interrupted run; it archives
stale terminal files first. This correction does not alter the completed run's frozen files.
Failure injection against a real interrupted inference run remains to be exercised separately.
