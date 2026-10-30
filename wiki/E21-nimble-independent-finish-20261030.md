# E21 — Independent Nimble public-test verification and automatic finish

Preregistered 2026-10-30 before the observer launches. Engineering verification; no model inference or training.

## Purpose and counterpart

Defects 12 and 16: prevent accepting incomplete or mis-scored reference evidence. A degenerate verifier could trust saved student scores or reject every artifact. Valid fixtures must pass, while hash-consistent forged student metrics, outputs, candidate ordering, identities and probabilities must fail. Accuracy is not a consistency measure.

## Frozen setup and scope

Observe E19 at `reference_inference/nimble_public_test_20261030/`, retained inference container `nga-reference-nimble-public-test`, 175 chip 3. Do not change or restart its frozen code. Seven exact upstream-manifest subsets total 1,884 rows; initial adapter revision `594dfdcfb6f94e3d0c0db7535180d3c71689169a`, T=1, original candidate-token readout.

The stdlib verifier imports neither the driver nor upstream metric functions. It independently derives required frozen dependencies, checks all dataset hashes/ordered IDs and receipt coverage, recomputes softmax consistency, typed predictions, student metrics and aggregate tables. It checks accuracy, NLL, binary/multiclass Brier, ECE10, score MAE, human-distribution JS bits/TV/entropy, domain summaries and selected code counts. Candidate token IDs are checked against the frozen tokenizer vocabulary. Prompt metadata is provenance-bound and range-checked, **not independently retokenized**; no broader prompt-equivalence claim is made. Saved timing arithmetic can be checked, but this does not independently measure hardware performance.

Final acceptance requires report/preflight hashes, successful structured terminal and wrapper, exact inference container identity/image/entrypoint/device map, and Docker exited/0. Missing-terminal wrapper failures fail immediately. Review flags identify extreme accuracy or small groups; independent verification is not Astra approval, contamination analysis or training benefit.

## Execution

CPU-only retained detached container `nga-reference-nimble-finish`, existing immutable Ascend image. Output `reference_inference/nimble_public_test_20261030_finish/`; frozen verifier, observer, tests, preregistration, launch/wrapper and inference config/launch receipt. Logs, heartbeat, bounded digest, terminal and wrapper EXIT persist on CephFS. Exact launch command is stored. Docker socket access is powerful; observer code issues GET inspection only, and allocates no NPU.

## Results

Pending whole-test completion and independent audit. Unit tests cover arithmetic and failure counterparts; completed per-subset artifacts are separately checked during development without claiming the entire run finished.

## Verdict

Pending. No new training or substantive Astra approval claimed.

2026-10-30 16:23 UTC execution: retained CPU observer
`0e67a6ebb7bc86d1b9f6c112d359b2c35ce277d2ba39f0021f5b3b3d0071e023`
was launched as `nga-reference-nimble-finish`; all eight frozen inputs were verified after
launch. Its bounded digest observed the actual inference container running at 1,116/1,884
rows, 2.1229 questions/s/chip, one chip, reserved 18.4199 GiB. This is not completion.
The independent implementation also verified all rows and aggregate tables in the three
already completed MASSIVE en-US, MASSIVE de-DE and PAWS subsets. Whole-run acceptance
remains pending.

Nineteen CPU tests now pass, including full 1,884-row synthetic artifact acceptance and
rejection of missing/extra receipts, omitted executable dependencies and a forged aggregate
whose terminal hash was recomputed. The launched frozen test snapshot contains the first
14 arithmetic/receipt/terminal tests; five artifact-integration cases were added to the
repository afterward. Production verifier and observer code were not changed by this test
addition, and no frozen running files were overwritten. The fixture bypasses only the
published adapter-weight hash inside the unit-test process; production has no bypass flag.

2026-10-30 16:33 UTC audit amendment, before the revised audit runs: repository
verification now pins the original base revision
`c202236235762e1c871ad0ccb60c8ee5ba337b9a` independently of the config/marker agreement.
Review flags cover every defined numeric metric equal to zero or one, small domain
cells, and identical metric values across distinct suites. The all/type aliases
within one suite are not treated as independent cells. Flags are review requests,
not automatic evidence of a model defect or numerical failure.

The revised code passes 21 verifier tests and three real subprocess chain tests:
full 1,884-row artifacts pass the actual finisher and verifier CLI through a Unix
Docker inspection fixture; a forged aggregate fails even after its terminal hash
is rebound; an incorrect device fails before audit; retry preserves a successful
terminal. Test launchers inject only fixture adapter identity and socket location;
production has no bypass option.

The original eight-file frozen observer remains unchanged. A new CPU-only snapshot
at `reference_inference/nimble_public_test_20261030_finish_v2/` is being prepared for
`nga-reference-nimble-finish-v2`; it will re-audit the same immutable E19 output.
Preparation is not launch or completion. The original observer's result, if it
finishes first, retains its original narrower anomaly-detection scope. No test
metrics, model weights, inference protocol or training decisions are amended.

2026-10-30 16:34 UTC failure diagnosis: E19 inference completed all 1,884 rows at
16:33:44 UTC, wrapper rc 0 at 16:33:49 and retained inference container exited 0.
The original E21 observer then exited 1 at 16:33:52 during independent audit.
The verifier correctly rejected an omitted required dependency: the E19 149-file
freeze does not include the base model's `config.json`, although the driver loads
that base with `from_pretrained`. The bounded diagnostic is
`nimble_public_test_20261030_finish/audit.log` lines 8–13. This is an artifact
provenance failure, not evidence of failed inference or invalid metric arithmetic.
No independently accepted full Nimble score is claimed.

The omitted file currently hashes to
`d0883072e01861ed0b2d47be3c16c36a8e81c224c7ffaa310c6558fb3f932b05`.
Earlier `nimble_initial_probe_20261030/config.json` and
`openjev9_test_20261030/config.json` contain this same path/hash. That is potential
external provenance evidence, not a retroactive correction to the E19 frozen
manifest. The prepared v2 observer is **not launched**: its strict verifier would
also reject the missing dependency. Resolution must preserve original artifacts
and explicitly choose a new fully frozen inference or a separately reviewed
external-provenance supplement; silently adding the hash is not acceptable.
