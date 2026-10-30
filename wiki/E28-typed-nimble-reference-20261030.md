# E28 — Initial Nimble Typed Decisions native adapter and preflight

Preregistered before execution: [E28 protocol](../experiments/TYPED-NIMBLE-REFERENCE-2026-10-30.md).

## Purpose and hypothesis

Defects 12/16: map all 400 states / 2,000 questions to the original Nimble v1 prompt without label leakage or changing candidate identity. Gold-invariance has candidate-order discrimination counterparts; missing fields and widths over 26 must fail.

## Setup

Original adapter 594dfdc / base c202236, full five-field schema, T1, 2,048-token limit. State JSON serialization and question/candidate order preserved. Initial CPU run performs tokenization only. No NPU allocation or model scoring occurs.

## Execution

175 only, immutable image and retained CPU container, frozen inputs, CephFS logs/heartbeat/terminal and exact relaunch command. Source code permits only `preflight_only` CLI execution. Forward helper is a draft requiring separate runtime admission.

## Results and verdict

Seven CPU mapping/identity tests pass. Full-token preflight pending. No model performance, six-model coverage, Astra approval or training benefit is claimed.

2026-10-30 17:17 UTC execution: retained CPU container
`nga-typed-nimble-preflight` launched with ID
`b268c089bd04d3d75c5921440f143064f7c9533d6a86e85dd24cf993b052f197`.
All 136 independently required paths are in the 136-file frozen manifest, including
base config, original adapter/tokenizer, native source and exact input parquet.
Config SHA256 `2a81db03747dabfe52ecc17f3d95c07d8fc55a4e0e9808b525569dd8b799a359`.
No NPU device is mapped; output is `reference_inference/typed_nimble_preflight_20261030/`.
Exact launch, config/wrapper/image/container identity and dependency closure are retained.
The observed initial heartbeat was verifying inputs; this is not completion.

2026-10-30 17:18 UTC completion: all 400 states / 2,000 field prompts completed,
maximum native prompt length 1,312 tokens under the frozen 2,048 limit. All five
fields remain present in each request schema. Synthetic gold isolation and
candidate-order discrimination passed; no overlength rows were removed.
Structured terminal at 17:18:32, wrapper at 17:18:34 and retained CPU container
all exited 0. PREFLIGHT SHA256:
`0683f8430a19beb239f35665879d7984c4e15cecc167b8994f06fe5a520ad26c`.
Post-completion hash/identity/count checks are in `PRECHECK_AUDIT.json`; they do not
claim independently re-tokenized prompts. Formal NPU inference, synthetic forward
throughput, item-resume/finish wiring and Nimble-specific independent metric
acceptance remain pending. No performance or training-benefit result exists yet.
