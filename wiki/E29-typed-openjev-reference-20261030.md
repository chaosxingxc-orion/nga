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
