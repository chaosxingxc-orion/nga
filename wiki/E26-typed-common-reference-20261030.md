# E26 — Typed Decisions common reference interface and inference

Preregistered before execution: [protocol](../experiments/TYPED-COMMON-REFERENCE-2026-10-30.md).

## Purpose and hypothesis

Defects12/16: preserve all 400 states / 2,000 typed decisions and original metric arithmetic while obtaining native raw probabilities. Constant outputs or gold leakage are degenerate optima. Label-only input invariance is paired with candidate-content/order discrimination; malformed and foreign receipts must fail.

## Setup

175, immutable existing image, native Kev0.8/4/9 pointer fp32/eager/merged released checkpoints. Full joint five-question input, no labels in model requests; serving temperature independently bound to head.pt, T1 recomputed. Open-Jev and Nimble adapters remain future work within the six-model common comparison. Exact population/formulas/context in protocol.

## Execution

Preparation only. CPU full-token preflight may run detached after configs freeze; no NPU inference until implementation/preflight review. Preserve retained containers, logs, heartbeat, terminal, exact relaunch and frozen dependencies. No old reference predictions reused.

## Results and verdict

Pending. Interface/preflight success is not model-performance evidence, new training benefit or Astra approval.

2026-10-30 17:01 UTC execution: three CPU-only retained token-preflight containers
were launched on 175, no NPU devices or allocation changes. Configs freeze 67/72/70
files, covering independently derived 66/71/69 required dependencies for 0.8/4/9B.
Exact commands and wrapper terminals live in `reference_inference/typed_kev{08,4,9}_preflight_20261030/`.
IDs: 0.8B `dc588a6f4a5a9a5bd8f6d54192f38bc4231e8b9186b8b17dff68ed127a21ec8b`;
4B `a1288c55222798136c0f689823db9c219f1914be658d942f0f1c77d4d4bd89b6`;
9B `8e93c75469c88ff6d962ba4123156df89842a537c32d2039d39fc198e99ee94e`.
Eleven CPU tests pass, including original frozen score_one arithmetic checks and
label-leakage/candidate-order/invalid-receipt counterparts. This does not yet test
the full inference-container → independent verifier CLI acceptance chain.

2026-10-30 17:02 UTC results: all three CPU preflights completed with structured
terminal, wrapper and retained Docker exited/0. Each covers all 400 states / 2,000
questions, maximum packed length 836 and state length 500; no overlength rows.
Synthetic five-question compilation preserves boolean/nominal/ordinal keys and
rejects candidate-order invariance through different token sequences. Subsequent
source checks revalidate all frozen files and exact launch/terminal/report bindings;
`PRECHECK_AUDIT.json` records that bounded evidence. No NPU inference or throughput
probe has run. Next acceptance work: full verifier CLI artifact integration,
synthetic repeated native forward, frozen runtime checks, resource/launch/finish
wiring. These checks cannot be replaced by the successful token-only preflight.

After preflight, repository inference scoring was clarified to consume stored
native probabilities for serving metrics; only T1 is reconstructed from scaled
logits. Repository also refuses inference from a `preflight_only` configuration.
The completed token-preflight snapshots remain immutable; neither change affects
lengths, and future inference must freeze the reviewed repository versions anew.

17:07 UTC repository correction: capture the original config byte hash before
execution and reject a changed config before success; failure terminal retains
the original hash. A controlled mid-preflight config alteration is rejected.
A near-tie regression separately verifies serving scores use saved probabilities
while T1 is reconstructed from logits. Thirteen CPU tests pass. Frozen completed
preflights remain unchanged; formal inference readiness remains pending.

17:14 UTC preparation amendment: add a separate probe-only mode, actual native
encoder token identity checks and exact runtime versions. Two synthetic passes
must agree within 1e-5; their positive timing and per-chip throughput are recorded.
The initial inference report does not claim expected-score MAE. No formal test
inference has launched at this point.

17:19 UTC real NPU probe results: all three retained synthetic-only probes
completed with structured terminal/wrapper/container exit 0. Two native passes per
model, one chip each. 0.8B second pass 14.5496 questions/s/chip, reserved 3.2754 GiB;
4B 10.6426 questions/s/chip, reserved 16.7559 GiB; 9B 11.3549 questions/s/chip,
reserved 31.1094 GiB. These tiny synthetic timings are admission diagnostics, not
formal-test throughput or model accuracy. Probe folders are
`typed_kev{08,4,9}_probe_20261030/`. 0.8B froze 70 files, 4B 75, 9B 73;
actual source/input/temperature/runtime checks and repeat probability tolerance
are enforced. Formal test inference still waits for full verifier-chain acceptance.

The new guarded launcher validates prior completed E22 artifacts and real Docker
identity/maps before locked chip transfer. Failed-run resume checks original
container/config/wrapper identity and current allocation; success/live runs are
refused, old terminal evidence is archived before resuming item receipts. Three
focused wrong-container/successful-run/duplicate-launch checks pass; no E26 real
crash/resume has yet been tested.

17:22 UTC formal preparation: three inference configurations freeze 70/75/73
files, independently covering 66/71/69 required dependencies. The guarded launcher
also requires the preceding probe's model/base/code hashes, temperature, runtime,
context and image to equal the intended inference protocol. An earlier unlaunched
preparation snapshot is archived before adding this check. Formal launch requires
a parent implementation-review receipt bound to the exact config hash; this is
an engineering admission record, not a new request for user authorization.

17:35 UTC launch-guard hardening: allocation metadata now distinguishes a synthetic
probe's completion from formal inference plus independent audit. Nine launcher tests
pass, including failed-run resume with old terminal/status archived and item bytes
retained, wrong-device/live-conflict rejection, predecessor identity/protocol
rejection, and inference-specific release metadata. These use temporary artifact
trees and mocked Docker calls; they are not a real E26 crash-recovery experiment.
Only unlaunched formal preparations are archived and freshly frozen after this
change; completed probes and token preflights stay unchanged. The bounded code
review found no necessary blocker to the first normal launch, but interruption
between allocation/create/receipt/start and automatic replacement of a failed
finisher remain recovery gaps. Full automatic recovery is not claimed.

17:37 UTC execution: parent implementation review was recorded against the three
fresh configuration hashes, then all three retained formal containers and CPU
finishers were actually launched. Exact image, command, configuration receipt and
physical chip bindings were checked against Docker. 0.8B on chip 0 reached 41/400
states, 4B on chip 4 reached 10/400; 9B on chip 5 was completing token preflight.
Every population remains 400 states / 2,000 questions. No completed test score is
claimed at launch. Inference container IDs:

- 0.8B: `57758df86bd0c97f2321139a768186f2b111cbbefdd2e165fbc22130b256bbe6`
- 4B: `7a02cd865ef69cce0ae90cdc6339ab3e52c82f90c430aa5989fffa4f57caefa7`
- 9B: `da0d8f073cfb05a30e4a7f46c5c250c05979fbba323c082701a35ecf5ad14576`

Outputs: `reference_inference/typed_kev{08,4,9}_inference_20261030/`, with sibling
`_finish/` CPU audit directories. This admission is a bounded implementation review,
not substantive Astra approval. The completed tests comprise 35 driver/verifier
chain checks and 9 launcher checks; 7 separate Nimble adapter tests also passed.

17:44 UTC completion: all three formal 400-state / 2,000-question runs and CPU
audits completed. Both retained containers per size and both wrappers exited 0;
all audits are `COMPLETED_SCOPED` with zero flags. Exact output hashes were checked
against terminal/audit bindings. Overall accuracy is 45.95% / 66.45% / 68.05%;
serving and T1 probability panels, typed breakdown and provenance are recorded in
[the common-test results](../experiments/TYPED-REFERENCE-RESULTS-2026-10-30.md).
These are reference measurements, not new training gains or substantive Astra approval.
