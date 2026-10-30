# E24 — Open-Jev original-test supplement and identity-preserving join

Pre-registered 2026-10-30 before launch. Normative protocol:
[original-test supplement](../experiments/OPENJEV-ORIGINAL-TEST-SUPPLEMENT-2026-10-30.md).

## Purpose and hypothesis

Defects 12/16: close the 176-row gap between the public Open-Jev test and its original
10,532-row release. A plausible aggregate from unrelated predictions is a degenerate optimum;
wrong model, altered input, duplicate and missing receipt counterparts must fail.

## Setup and execution

Exact E14/E18 model/native interface and temperature, 175 only. Separate supplementary
176-row inference after corresponding public run completion and independent audit. Full
original test = 10,046 hard + 486 soft. Full original and public populations stay separately
named. No OOD evaluation, new training or metric fitting. Detached retained containers,
CephFS evidence, locked device transfer and item receipts are required.

## Results

Preparation only. Existing public runs remain untouched. Supplement and full-test join
have not run; original dataset restoration in E23 is not model inference evidence.

## Verdict

Pending implementation review and execution. No original-full metric, Astra approval or
training-benefit claim.

2026-10-30 preparation update: separate supplement directories, join plans and the CPU
queue were prepared on 175 without launching a container or changing chip ownership.
`tools/prepare_openjev_supplement.py` records the reproducible builder. Queue directory:
`reference_inference/openjev_original_test_queue_20261030/`; launch command is its
`LAUNCH_EXACT.sh`. Each component config freezes native model/code inputs, original data,
restoration metadata, parent config and executable dependencies. Existing public-run frozen
files remain unchanged. The controller waits, audits and transfers each size independently;
one failed dependency does not cancel the other size, and overall failure remains rc 1.

Sixteen new CPU tests passed, including a file-backed component-audit → ordered join →
report/terminal chain and a hash-consistent forged-component rejection. The integration
fixture substitutes synthetic data and Docker state; it does not claim an NPU or crash test.
The existing driver 13 tests and independent auditor 18 tests also passed after adding optional
internal dataset-validator hooks (public-path defaults unchanged). The new queue deliberately
refuses automatic continuation after interruption; its state needs review. Supplement item
receipts and guarded resume reuse the existing protocol. No real E24 restart has been tested.

Parent review at 16:45 UTC: launch remains pending. The joined report must retain
component review flags in addition to its own full-population flags; the prepared
snapshot currently retains component audit identities but does not propagate those
flags. Fix and test this before refreezing the unlaunched plans. A clean full-data
aggregate must not hide a flagged public or supplementary component.
