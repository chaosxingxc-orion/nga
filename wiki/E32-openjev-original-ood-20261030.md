# E32 — Open-Jev original complete OOD reference evaluation

## Purpose and hypothesis

Defects 12/16: establish reference OOD performance on the exact original population;
wrong-split, partial-coverage and changed-model counterparts prevent plausible
aggregates from being accepted as evidence. No new training is part of this run.

## Setup

[Protocol](../experiments/OPENJEV-ORIGINAL-OOD-2026-10-30.md). Existing 2B/9B native
checkpoints, exact 15,920 OOD rows (15,446 hard / 474 soft), 175 existing immutable
image, full CPU token admission before separate NPU inference and CPU independent
verification. Serving and T=1 probability panels; no OOD-derived tuning.

## Execution

Implementation and immutable preparation under review. No E32 container launched,
no NPU claimed. Direct original OOD data retains `split=ood`; the shared driver and
verifier preserve their default `test` behavior for previous protocols.

## Results and verdict

Pending actual execution and independent acceptance. Data restoration, code tests
and preparation are not inference results or Astra approval.

Preparation update: 91 Open-Jev tests passed, including six OOD split/hash/identity
counterparts and all existing reference/typed tests. Both prepared configurations
passed exact full OOD dataset and parent model-dependency validation: 10 sources,
3,438 choice / 2,553 score / 9,929 noul rows. No token preflight or inference was
performed by these dataset checks.

Prepared directories are `reference_inference/openjev{2,9}_original_ood_20261030/`.
2B config SHA256 `e0922cda0415a0972375365f806eba3230607724d7a6587cb99b69577710562d`
freezes 102 files; 9B `9ec95392a5a8dfb23041cdb905d9d32ac95960601363605d4723892ec50bddd1`
freezes 105. Planned chips 4 / 2 are not claimed; launch requires prior explicit
release and current live-conflict checks. CPU preflight uses no NPU. Earlier
never-launched preparations are retained in `preparation-before-final-launch-binding/`
after stricter finish-plan and actual device/mount checks were added. Parent review
and actual launch remain pending.

## 18:26 UTC actual CPU execution

Parent reviewed code/protocol, reran OOD six tests and 47 existing native
reference tests, matched prepared source hashes and approved the two exact
configurations for CPU preflight. Both retained detached containers actually
launched, without NPU devices or allocation changes:

- 2B: `b909828c3f4cb888cb974defc1277ecb98285a8a8b52ae56714627c89de00e0e`
- 9B: `931f0ca5a9b20afde9312aeaacc444690564c6040bad044d8ac0a6cd97694686`

At 18:26:00 UTC, 2B had checked 5,535/15,920 rows; 9B was verifying
dependencies. Full eligibility and NPU inference acceptance remain pending.
NPU launch still requires separate parent review of complete preflight and
physical-chip mapping, explicit allocation release and live-conflict checks.
