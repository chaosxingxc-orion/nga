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

## 18:34 UTC — full preflight accepted, actual NPU inference launched

Both CPU preflights completed exited/0 with 15,920 rows and 49,227 candidate
prompts, maximum 742 tokens, zero overlength. Parent verified actual CPU
container/command/config/wrapper/terminal bindings and all 15,920 length receipts
for each size, including exact row identity and aggregated lengths.
Preflight reports: 2B `62f756e5d054a0cd1799328675674704cf7289a31f26f2fa14ef7cbff8e62adc`;
9B `7cd00a263e4a4d6e14a34ff6ca980463be8292dc5456b2c93de18d169c26a197`.

2B inference launched chip 4 at 18:30:29 UTC, container
`981ac8b2584284fe12918bb62ce62f6516e2f236788c00710e5078e302b64242`;
finisher `aa5ff9a8052bfd404946e1bac5b5b3e8f8ba166ead279c0ceef9569ac6e86f12`.
After independently checking E24's completed 2B supplement and exact original
join, parent explicitly released chip 2 under allocation lock with live-device
checks. 9B OOD then launched on chip 2, container
`370d251b216baa8d6ecb8030d1fd8419c07e4a9158161e55d15170325a470f0b`;
finisher `c62f4476bc164de5eab5dbf8201cfda79117fd61c17e418a9347b2736eccbb52`.
Both actual containers and CPU finishers were running at final verification.
No final OOD metrics, training gain or substantive Astra approval yet.

## 2026-10-31 — 2B completed and accepted (175 host times)

The complete 2B OOD inference wrote terminal rc 0 at 2026-10-30 21:08:45 UTC
for 15,920/15,920 rows. Its wrapper and retained inference container exited 0
at 21:08:49 UTC. The independent CPU finisher completed at 21:09:41 UTC and
its retained container also exited 0. Audit status is `VERIFIED_SCOPED`,
102 frozen / 89 required files, all 15,920 records, 15,446 hard and 474 soft,
with zero native main-panel review flags. This does not certify every selective
coverage subcell or supply an Astra result review.

Detailed serving/T=1 metrics and source denominators are in
[the 2B OOD results](../experiments/OPENJEV-ORIGINAL-OOD-RESULTS-2026-10-31.md).
Hard accuracy is 13,288/15,446 = 86.028745%; expected accuracy is 84.616890%
over all 15,920. Serving NLL / Brier / expected Brier / ECE15 are
0.802074062 / 0.246288900 / 0.263619640 / 0.105578241.
Report SHA256 is `35f4f3bd824f435aa2813e60de0e41f7af863a3d2ced96783d394bd624906e07`;
audit SHA256 is `36e65d8c398902fcfe4fd0b3ce1c829ad28212f27d7072625289f3db7038de58`.

`reference_inference/e37_ood2_acceptance_20261031/` stores the complete receipt
manifest, actual container exit and output bindings, and release evidence.
The receipt manifest was rechecked after audit completion. Physical chip 4 was
explicitly released under the allocation lock after live Docker and empty-device
checks, to permit guarded E37 preparation. No 9B completion or new training
benefit is claimed by this 2B entry.
