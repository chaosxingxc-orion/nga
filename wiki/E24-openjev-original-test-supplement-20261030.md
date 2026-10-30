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

2026-10-30 16:50 UTC execution update: component review flags now propagate unchanged
into the joined report, each bound to component name, audit identity and source report
hash. Any such flag keeps the combined status REVIEW_REQUIRED even with clean full-data
metrics. The regression executes the artifact audit/join/report chain with a clean
aggregate; 47 Open-Jev tests pass. Direct execution of the supplement test file now
includes its integration and queue cases, as discovery already did.

The never-launched prepared snapshot was revised before execution; prior code, configs
and plans remain in `preparation-before-component-flags/`. The two component manifests
were rebound before the join plans and queue plan. All hashes passed; 2B / 9B configs
freeze 111 / 114 files covering all 89 / 92 required dependencies, plus supplement
protocol/execution bindings. Exact 176-row content/model mappings passed independently.

Retained CPU controller `nga-openjev-original-test-queue` was launched, ID
`4c3fd7a3759cdfcd3b7bae368f30521a7f625da82927bf4bec7d28a16edad55a`.
Its plan SHA256 is `e42b87f44da235bc9cb8800cdc822e60b20c01ce6ab7659c12f16d5d88c0552d`;
all 19 queue frozen inputs were rechecked after launch. The actual Docker identity,
image, command, CPU-only mapping and wrapper hash are in `LAUNCH_RECEIPT.json`.

17:48 UTC verified update: the queue actually completed the 2B path. Public
inference was independently checked, the retained 176-row supplement container
`f6f621435fdc767c3a598af4c1e8284441544ad7f9e14336f3e86d6087951554`
completed exited/0, and the exact 10,532-row join finished at 17:42:33 UTC.
Hard correct is 9,507/10,046 (94.634680%); expected accuracy is 91.876577% over
all 10,532. The original component flags propagate and keep REVIEW_REQUIRED.
Detailed original-test comparison, temperatures and hashes are in
[the results](../experiments/OPENJEV-ORIGINAL-TEST-RESULTS-2026-10-30.md).
9B remains waiting for its public run. The queue as a whole is not complete.
At 16:50:06 both sizes were `waiting_public`. Supplement inference and full-test
metrics remain pending; CPU queue launch is not their completion. Existing public
runs and their chip ownership remain unchanged until the guarded dependency transfer.
