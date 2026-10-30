# E29 — Native Open-Jev Typed Decisions interface and CPU preflight

## Purpose and hypothesis

Defects 12/16. Evaluate native mapping of all 400 original test states / 2,000 typed questions without gold leakage or denominator changes. Constant output is degenerate; candidate order/content discrimination accompanies metadata invariance. Protocol: [E29](../experiments/TYPED-OPENJEV-REFERENCE-2026-10-30.md).

## Setup

Existing 175 immutable image; exact E14/E18 checkpoints and base revisions, original native compiler and chat template. CPU-only token preflight, maximum 4,096 per candidate without truncation. Five questions supplied together to the compiler, which natively isolates their prompts; no joint-schema claim.

## Execution

Before launch: freeze full dependency manifests, per-state resumable receipts, retained detached CPU containers, CephFS heartbeat/log/terminal and exact relaunch command. No NPU allocation changes; public test and original-test supplement continue independently.

## Results and verdict

Pending full token execution. Eight adapter tests use the actual frozen native API, with synthetic tokenization for identity/shape/overflow behavior. These tests do not prove real token lengths or model quality. Formal inference requires separate forward admission and independent verification.

2026-10-30 execution: both CPU preflights are now launched on 175 with no NPU
mapping. Output directories `reference_inference/typed_openjev{2,9}_preflight_20261030/`.
2B freezes 88 files, config SHA256 `4a14645d9bc3a341e12241763611270849a7e8a180d6e52094027286181ec235`,
container `3d7b6c9c801f39d284200157e1adb15082a34202dd8e7bf89175aa68dd3b8372`.
9B freezes 91 files, config SHA256 `bd5fd80a154dc3308bec5afbf84f41423720032c068cf118ad01e3c1d4116ef5`.
Their exact image, config and container identity receipts are saved alongside
launch/resume scripts. Completion remains pending until terminal, wrapper and
actual retained Docker exit are checked.

17:44 UTC results: both full CPU runs completed with structured terminal, wrapper
and retained Docker exit 0. Each covers 400 states / 2,000 questions / 6,500 native
candidate prompts; maximum 586 tokens, no overlength. Both synthetic candidate
order/content discrimination and gold isolation checks passed. 2B completed at
17:43:21 UTC (wrapper 17:43:22), 9B at 17:43:57 (wrapper 17:43:58).
9B container ID `338f3ce380182be2bd1763d2e90d8d614bb13624ba0fe2982ed4e4bcf5e3f0ce`.
Reports: 2B SHA256 `620581fc545ca3db31ccd7dc2dcd72c81c97e0373c1cd2e7105be4cd7ad92fd0`;
9B SHA256 `eb47f2b37863d53f649cd85fa80d34c1dbcfb9183075eb3cb3a1fbd4473aa56a`.
A separate bounded artifact audit rehashes dependencies, complete item coverage,
counts, report/terminal bindings and actual container identity/exit. It does not
independently re-tokenize prompts or establish model accuracy. Formal native NPU
forward/recovery/independent scoring remains unimplemented for E29; no test model
performance or Astra approval is claimed.

Native inference preparation update: added separate execution driver, independent
prompt/metric verifier, retained CPU finisher, and locked identity-bound launcher/
resume. Actual forward token IDs are observed and compared with preflight;
original wire is preserved. Unit/CLI/real-finisher subprocess tests use full
400-state / 2,000-question fixtures and reject forged metrics, prompts, missing/
extra receipts, wrong runtime/temperature, stale terminal and foreign devices.
These are engineering checks, not model inference. No NPU run has launched yet.

Execution implementation tests: 38 passed (8 adapter, 16 execution/resume,
10 complete verifier CLI and 4 real finisher subprocess checks). Probe configs
are prepared but unlaunched: `typed_openjev2_probe_20261030` on intended chip 0,
93 frozen / 90 required files, config SHA256
`12bbfa1ef3ecf0ce7465e686796537a19c4948b5b68e286f5e691b1b484c2952`;
`typed_openjev9_probe_20261030` on intended chip 5, 96 / 93 files, config SHA256
`3884e565ab5e218f6a660fb83fdcfc705f30b6dba24a2e49e3ee9c6c22640cd8`.
Resource transfer requires reviewed completed E26 predecessors and live-device
checks. Full formal inference remains unlaunched pending real probe evidence.

17:58 UTC actual execution update: both synthetic native probes completed with
matching terminal/output/config hashes, wrappers and actual retained Docker exit 0.
Both had two five-question passes with probability delta 0. Second-pass speed was
3.250166 / 2.730244 questions/s/chip, one chip each, reserved 4.146484 / 17.587891
GiB (2B / 9B). These are admission timings, not whole-test speed claims.

Parent implementation review then admitted full inference and separate CPU
finishers. Formal configurations freeze 93 / 96 files and are bound to SHA256:
2B `6f1f678c728a912e5f249c273389e248100aa26bdbafeaadb28361c58ca2c728`;
9B `ecbb6411a67f59d18300962d8549eca33c9ac74bf74e651f9a8ea61874b6d4bb`.
Retained inference IDs:

- 2B, physical chip 0: `17336bc6b669a1b1e4fd75ea27c8f4a6ca13327e55cef75d94ba207251fcd1d5`.
- 9B, physical chip 5: `521e4874a1cd84f8f5d426c98710e7577f37032ddc6bcf17b67d83d120e73f1d`.

Exact image/command/receipt/device bindings were inspected after launch. 2B had
entered actual inference at 25/400 states; 9B was starting. Outputs live in
`reference_inference/typed_openjev{2,9}_inference_20261030/`, CPU audits in sibling
`_finish/` directories. Complete metrics await actual terminal and independent
verification. Original public/supplement runs on chips 1/2 were not modified.

## 2026-10-30 18:23 UTC — 2B completion

2B completed 400 states / 2,000 valid questions, native accuracy .5825,
KL .41091064355455525, soft Brier .19381650185339677, ECE10 .08100331926223044.
Raw T=1: KL .659782228909835, Brier .24502752374840706, ECE10 .15923499307814587.
Independent prompt retokenization/wire reconstruction/scoring passed with zero
flags and 93 frozen / 90 required files. Actual inference and finisher Docker
and wrappers exit 0. Report SHA256
`0bb139be0026fb72fe9b4c7d512a8443645ccbeefb5ca95d355d77030cdac9f5`; audit
`8481faf3d2ef4f0e58aaf5c76fa3221a9dc2dc650e6d4b82ca802b36c6626341`.
Parent checked config/terminal/output hashes and actual container exits.
9B still running; no six-model final table or Astra approval claim.
