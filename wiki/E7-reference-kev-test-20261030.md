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

Pending execution and evidence review. No new formal training or locked NGA test is involved.
