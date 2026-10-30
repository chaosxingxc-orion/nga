# E8 — Native Kev scale compatibility and throughput probes

Status: preregistered 2026-10-30 before launch. Initial target: released Kev-4B on 175,
physical chip 2, existing immutable image used by E6/E7. Kev-9B paths are inventoried;
no 9B launch or resource claim is implied by this registration.

## Purpose and hypothesis

Check that native pointer-head inference on the larger local checkpoint is executable,
and measure loading time, repeated inference time and reserved memory before full test
evaluation. Defect registry row 12 (measurement validity). This is development instrumentation,
not a test score, generalization result or training benefit.

The unconstrained degenerate output of valid constant probabilities is insufficient for a
model-quality claim. Keep logits, probability distributions, option IDs and repeat deltas;
finite complete outputs and valid provenance establish execution only. Inspect differing
inputs and returned distributions, but do not treat output variation as semantic correctness.
No invariance target or numerical parity threshold is inferred from repeated execution.

## Frozen setup

Use the first four decision-v7 development records, each twice in fixed order. Selection is
fixed before execution. Native `LocalPredictor`, pointer head, checkpoint temperature and
original encoder; fp32, eager attention, merged LoRA, transformers reference GDN, HF32 off.
Resolve the checkpoint's exact base ID/revision to the local mirror; refuse mismatch.
No test records, new calibration, training or label-logprob substitution.

The new script parameterizes expected base identity and physical chip. Before launch, freeze
all model/base JSON, weight, tokenizer/text/template files and `.complete`, the development
partition and manifest, Python source and launcher/wrapper. Verify hashes before and after
the probe. An exclusive lock prevents duplicate writers; saved record payloads carry hashes
and input/run provenance for restart. Model loading time is separate from first and repeated
pass timing. Report questions/s/chip with chip count 1 and reserved GiB. Four records are
too few for a general steady-state throughput claim; repeated-pass rates are observations.

## Execution

After allocation-file and live Docker device checks, claim chip 2 atomically. Use detached
fixed container `nga-reference-kev4-probe`, never `--rm`. Keep frozen code outside downloaded
trees and preserve CANN `PYTHONPATH` via `python3 -P`. CephFS run directory:
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev4_probe_20261030/`.
Keep 15-second heartbeat, exact launch/restart commands, logs, structured report and terminal
marker. The marker plus wrapper exit and retained container state determine completion;
release chip only after terminal and container exit are checked. No E7 artifacts are modified.

## Results

Pending. Both mirrors contain Kev-4B and Kev-9B and their base models. The local 4B base revision
is `1001bb4d826a52d1f399e183466143f4da7b741b`; the 9B base mirror revision is
`68c46c4b3498877f3ef123c856ecfde50c39f404`. Checkpoint metadata must match at runtime.

**2026-10-30 executed update:** Kev-4B completed all four development records, each twice,
in container `19996fa4e6caebd5c6a73ef562ab73d8e2e6b0cc19c45922d23bd7cf99bb6d11`.
`REFERENCE_PROBE_COMPLETE.json` records rc 0, records 4 and test_metrics false; wrapper
`DONE` and Docker exit both record 0. Chip 2 was released only after these checks.
Runtime checkpoint identity matched the local 4B base revision. The frozen manifest covers
66 files; record receipt hashes were independently rechecked after completion.

Model load took 9.8386 seconds, excluding prior file hashing. Native serving temperature was
2.406050072164233. All four repeated-pass probability deltas were 0. Reserved memory was
16.7559 GiB on one chip. Repeated-pass rates were 1.7315, 1.6593, 1.6935 and 1.7292
questions/s/chip, from individual passes lasting 0.578–0.603 seconds. These are a tiny
development sample, not a full-suite throughput benchmark or device-equivalence finding.
Input IDs retain upstream `banking77/test/...` names, but the actual hashed source is Kev's
`development.jsonl`, not its official test partition. The pre-launch snapshot remains in
the run directory; no test metric was produced.

## Verdict

Native Kev-4B inference is executable with the existing image and the tested fixed settings.
No full test evaluation or cross-device equivalence is claimed. The 9B probe remains unrun;
its model paths alone do not establish compatibility or memory fit.
