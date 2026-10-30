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
