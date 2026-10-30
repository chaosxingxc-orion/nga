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

2026-10-30 execution implementation amendment, before any E28 NPU launch:
new dedicated inference, independent verifier, guarded preparation/resume and CPU
finisher code is under review. The independent verifier reconstructs the five-field
schema and re-tokenizes every prompt, rather than only comparing two saved hashes.
Repeated synthetic admission and exact full item receipts precede formal results.
Original runtime, safe merge and candidate projection remain fixed. Runtime and
recovery tests are engineering evidence; no NPU probe or formal test score is
claimed by this amendment. Frozen CPU-preflight artifacts were not changed.

17:45 UTC pre-probe correction: execution now hashes the exact configuration bytes
that it parses and rechecks the on-disk hash before any dependency/model work.
A controlled read-then-mutate test rejects execution and proves the failure terminal
retains the original byte hash. All 31 execution/verifier/finisher tests pass.
The unlaunched probe preparation is archived and freshly frozen; the original CPU
preflight and its evidence are unchanged. Parent conditional admission permits this
corrected synthetic-only probe after closure, configuration and resource checks;
formal test inference still requires the real probe evidence.

17:45 UTC synthetic-only NPU probe launched on physical chip 3 after the locked
free-allocation/live-device checks. Corrected config SHA256:
`2cee3876f1c98b44bb6c07662d72ff343f0e3b78dd62d4365261acd8b13e4a10`.
All 141 required dependencies are frozen and independently rehashed. Retained
container `nga-typed-nimble-probe` ID:
`eca65a16f75ec696429510650952aefa5e8fd85224f212e9434fd808296cd1b9`.
Actual image, command, entrypoint, configuration receipt and device mapping match.
The observed initial heartbeat is dependency verification; successful NPU forward
completion and formal test inference are not yet claimed.

17:47 UTC probe completion: structured terminal at 17:47:18, wrapper at 17:47:22,
and retained container all exited 0. All 400 states / 2,000 prompts again passed
the unchanged 2,048-token limit (maximum 1,312). Two synthetic five-field native
forwards took 3.153544 and 2.067974 seconds; maximum probability delta was 0.
Second-pass throughput is 2.417826 questions/s/chip, one chip, reserved memory
18.23828125 GiB. These are tiny synthetic admission figures, not test throughput
or model quality. Terminal/config/output hashes, wrapper chronology and actual
container identity/image/command/exit were checked. PROBE SHA256:
`a2d1a8de544239086ce6788d681623bf711cf9c3dc58f28726a0d64b698fc393`.
Formal test inference remains unlaunched and subject to parent acceptance of this
probe plus its separately frozen configuration.

17:51 UTC formal execution: after the real probe and 31 driver/verifier/finisher
tests passed, parent review admitted a new 141-file frozen inference configuration
SHA256 `90aea1118abcead77a37c67d59526d2044d5b5be5a726dbc9d2a605ea477eaeb`.
Retained `nga-typed-nimble-inference` launched on chip 3 with ID
`c3c20de30cce60132476936cbc3bdc1a95b6ae434f55fdf8718bddba41068f71`.
CPU finisher ID `03d69c9e01a53e5f640c641d8eb89cebc527b318daa823e42d9a13abc0462277`;
actual image, command, config receipt and device maps were checked. Initial stage
is dependency verification. Full inference and scores remain pending. Outputs are
`reference_inference/typed_nimble_inference_20261030/` and sibling `_finish/`.
