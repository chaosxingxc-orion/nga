# E34 — explicit JEVal inference execution queue

> Status: planned · Date: 2026-10-30 UTC
> Pre-registration: [E34 protocol](../experiments/JEVAL-QUEUE-2026-10-30.md)

## 1. Purpose

Defects 12/16: complete explicitly approved JEVal reference inference and independent
acceptance without hand-operated transitions between model entries. No training gate.

## 2. Hypothesis

A deterministic immutable queue can survive controller interruption at Docker
create/receipt/finisher boundaries without duplicating execution or accepting
foreign artifacts. A fake completion counter is rejected by actual Docker and
full-population evidence requirements. Negative tests and a CPU Docker SIGKILL
fixture distinguish real recovery from simple counter updates.

## 3. Setup

Code: `tools/jeval_reference_queue.py`, focused tests and real-fixture driver in
`tools/test_jeval_reference_queue.py`. Same immutable 175 image as E33. Model plans
name a reviewed ordered subset; planned chip 1 only. Open-Jev additionally requires
candidate-batch admission. The queue uses frozen native NPU specifications and
wrappers through Docker API because host-only launchers cannot run inside its CPU
container. Model, data and metric protocols remain E33.

The actual CPU seam fixture uses retained names `nga-e34-seam-fixture-worker` and
`nga-e34-seam-fixture-worker-finish`, no devices and a private resource JSON. It
kills controller children at inference-create, receipt-before-start and finisher-
create boundaries. Model results and production resource-release correctness are
not inferred from this fixture.

## 4. Results

Pending actual fixture and parent review. Fifteen focused local tests pass,
including changed outputs, missing audit marker, preserved flags and identity
mismatches. No queue/model launch is claimed here.

## 5. Verdict

Pending. This is orchestration admission, not reference metric acceptance or Astra
approval. Failures remain visible and stop dependent entries for reviewed action.

## 19:28 UTC — actual CPU seam evidence

The first fixture completed at 19:24:38 UTC. An independent v2 fixture exercised
the updated create/receipt reconciliation source and completed at 19:27:40 UTC:
`reference_inference/e34_queue_seam_fixture_20261030_v2/fixture/FIXTURE_COMPLETE.json`,
SHA256 `3b7cb60c90ac1a7fae7ea92496b8051c5ab74a5fb6a0014f617fae7bdf660f0d`.
Three real controller-child SIGKILL exits were -9 at inference-create,
inference-receipt and finisher-create. The two intended containers were retained
and exited 0, with no NPU devices:

- worker: `22a78af449ce5bd6e9b7bcbc086ead47cab074ea6e07048916a6a2ec336d0f7b`
- finisher: `df6daa48d26b31099f5ce1f21bcbd701317ae1950bae488d6af22cea75f97057`
- fixture driver: `002b03004b89d198c0e9e69d551679a203b8e796be537b084e0ed9ba4ff53e3f`

The driver wrapper also exited 0. Actual Docker inspection independently checked
all three states/devices. Nineteen focused local tests pass, including hardened
audit requirement/flags, changed entry config, full spec rejection and a release-
receipt interruption. Later edits after the v2 snapshot only strengthen completed
receipt and preparation-closure checks; they do not change the exercised seam
reconciliation. Full production NPU queue execution remains pending parent review
and per-model admission; this fixture does not certify NPU workload recovery.

## Read-only automatic hardened finishers prepared

`tools/jeval_hardened_waiter.py` waits for the existing immutable inference and
native finisher containers to exit successfully, revalidates their receipts and
terminal/output hashes, then runs the separately frozen E35 auditor. It performs
Docker GET operations only: no source launch, restart, adoption or allocation
release. Eight focused tests reject false completion and changed source evidence.

Three plans are prepared, not launched, under
`reference_inference/jeval_{kev08,kev4,kev9}_hardened_waiter_20261030/plan.json`:

| Model | Plan SHA256 | Frozen files |
| --- | --- | ---: |
| Kev0.8 | `5f1dc075ff7e442e966f9f3ec45ad746597b7b785ad1d4f5ce244edba9ff1000` | 12 |
| Kev4 v2 | `0d58fc9e5b9c3e07c5fd0ddb6443bb1e25f8fff7afed96486cc46769b51bc263` | 12 |
| Kev9 | `5ae8027d2d8fbad393777bcdc30a04c76f4be57ba2f9a6c1105f6487ed2ba6d1` | 12 |

Auditor SHA256 is
`04ecdebe1ea117c24fe1f0a66c6adb077902ef599606703a008cb902d8865b44`.
Every plan binds its actual source container IDs, complete source configuration,
receipts and config hash; CPU waiter source, wrapper, spec and exact launch/resume
commands are frozen. Parent approval is still required before launching. A
successful source marker while its actual container is still running does not
start the audit. Final audit reports/flags are bound to the source config and
report. These prepared plans have not yet produced final-model acceptance.

### Prelaunch correction — retained invalid launcher generations

Parent review found shell quoting had removed string quotes from the generated
v1 `launch.py`; those three configurations were never launched and remain intact
as failed preparation evidence. New v2 paths/containers were generated using a
separate local Python file transferred verbatim, not a nested shell string.
Every generated Python file was compiled, and every shell wrapper passed `bash -n`.
Resume now checks exact plan/files/receipt/container specification and absence of
COMPLETE/HARDENED_AUDIT/EXIT; running is observed only, created may start, and only
an interrupted nonzero exit without terminal evidence may restart.

Final prepared, unlaunched plans are under
`reference_inference/jeval_{kev08,kev4,kev9}_hardened_waiter_20261030_v2/plan.json`:

| Model | v2 plan SHA256 |
| --- | --- |
| Kev0.8 | `589d31523e7233c36881c5b96cdf3af23d8abfc9a41fd89a7c684436475f9f53` |
| Kev4 | `e249912d8d387c9422b83691a86ad176b71ad20d377844f97e95a6eec3b45880` |
| Kev9 | `79d1c2b573a98f61eb8cd6ecd6cc338caf60b32d552bf82bf12a4c5941fd73c7` |

Each freezes 12 files. Generator evidence is retained at
`reference_inference/jeval_hardened_waiter_sources_20261030/prepare_waiter_v2.py`.
These replace the earlier prepared-plan references for future launch only; no
frozen source run or old waiter plan was rewritten to hide the preparation fault.

## 19:49 UTC — three corrected read-only waiters actually running

Parent independently checked all v2 frozen files, generated Python compilation,
Shell syntax and exact plan hashes, then launched the three CPU waiters:

- Kev0.8: `d1fc508d706e38d24c79def07791ba3e783534d3f7735871dce3343ba45e9494`
- Kev4: `d9769d5a66bead3a40759670446c3d4f7c691cdd2450de2f285d6102d199a067`
- Kev9: `4d9708dce49e64491ed835d0624c180842c43d87113219e3a7a4a6e8d385e193`

Actual Docker states were running; digests at 19:49:48–49 UTC showed
`waiting_native_finish`. They wait for the original inference/finisher terminal
and actual exit, then execute the frozen supplemental auditor. They do not mutate
model runs or release NPU resources. Full-test hardened results remain pending.

## 19:50 UTC — Nimble-only production queue prepared, not launched

A separate immutable one-entry queue is ready at
`reference_inference/jeval_nimble_queue_20261030/plan.json`, SHA256
`b69ae7f2d1e4b84689302fa3178611a797fd027ce98fba4d41022d43d3f835d7`.
Its 15 small frozen files bind queue/preparer/auditor/test sources, protocol,
controller CPU spec and exact wrappers, plus the approved Nimble config,
native NPU spec and model wrapper. Native 151-file closure was fully rehashed
in read-only dry entry admission, not included in each 10-second queue poll.
The entry config remains
`b310b6271a7174f7efad1ba435fa2ad9ac53fecab3aec0f1944ee2f5fd703156`.
Model approval was recorded under the parent's explicit engineering instruction;
queue approval is absent and must be written by parent review before launch.

All generated Python files compiled and shell wrappers passed `bash -n`.
`Queue` construction and `check_entry` passed a dry read-only admission, simulating
only the absent queue-level approval without writing it. The actual CPU preparation
container `69fb6a233acc447416ed5e211094fd0dd125f0feac9aff23409c9117116efc0e`
exited 0 with no NPU devices; terminal 19:50:35 UTC was rc 0, 1/1.
Preparation evidence is in `reference_inference/e34_nimble_queue_prepare_20261030`.
No production queue or model launch, resource claim or release was performed.

`tools/prepare_jeval_reference_queue.py` now provides reproducible preparation,
guarded launch and guarded resume. Launch records plan/spec intent before create;
only matching created-container gaps can acquire a launch receipt. Existing
terminal/failure/wrapper evidence is preserved. Running is a no-op; interrupted
nonzero exits without terminal evidence require `RESUME_REVIEW.json` bound to
plan, container ID and exact `FinishedAt` before restart. Six focused guard tests
pass, covering terminal preservation, unknown created containers, matching receipt
gaps, running no-op, interrupted generation binding and literal shell arguments.

## 19:53 UTC — Nimble production queue actually started

Parent reran six preparer guard tests, checked all 15 frozen queue files and
compiled every generated Python/shell file, verified the approved single Nimble
entry and independently checked chip 1 was explicitly free with no live mapping.
Approved plan `b69ae7f2d1e4b84689302fa3178611a797fd027ce98fba4d41022d43d3f835d7`.
Retained CPU queue container actually started:
`8ebde745a776a896a37dc46c61292daa77b282975b5b631d7657b1f02b469082`.
The queue will launch exact frozen Nimble inference and its native finisher, then
the separately frozen hardened audit before release/acceptance. No Open-Jev entry
is present, because its E36 numerical-equivalence admission failed.
Queue launch does not establish model completion or a JEVal test score.

19:53 UTC actual dependency launch confirmed: the queue created and started
Nimble formal inference `7d5d8d2497267db92587b2029cd5043a2627fb6cf2b0fd46b2db70eed1f2cf15`
and native finisher `77bb77d600e54aa6b4ae3131d26ea5adcaa6437e13d9b0050b0eacc6aa811509`.
Both actual states were running; model digest was `load_model`, 0/11,257.

## F4 recovery fixture pre-registration — before launch

Astra F4 identified the audit-output-before-waiter-terminal interruption gap.
The new waiter revision keeps a persistent audit attempt with authenticated
supervisor argv/PID/start ticks/boot identity and an inherited flock. Completed
attempts bind exit status and report hash; partial attempts remain in their own
directories. Recovery checks source identities and the complete receipt manifest
before atomically publishing a no-clobber report and committing the waiter terminal.
A nonzero wrapper EXIT requires exact reviewed interruption identity and is archived.
Existing production waiters and their frozen inputs are not modified.

A retained, CPU-only fixture on 175 will use the immutable E33 image, CephFS
log/heartbeat/terminal/exact relaunch and no NPU devices. It performs two actual
SIGKILL cases: (1) kill the controller after publishing the successful audit but
before its terminal, let the shell preserve EXIT 137, then review/resume and require
one audit attempt with byte-identical published output; (2) kill the audit supervisor
while its child has written a partial JSON, retain the partial attempt and require
a separate successful attempt. Synthetic source checks are explicit fixture controls;
this does not certify model correctness, NPU recovery or production handover.

## F4 recovery fixture v1 result and v2 pre-registration — 2026-10-30 20:12 UTC

The retained CPU fixture `nga-astra-f4-waiter-recovery-fixture`, container
`db9b25e1d3167ec87884c1f9dc585caf462fc8f2d42f90c3442dc35567a2b1d5`,
exited 0 with no device mappings. Its inner fixture report confirms publication
SIGKILL/EXIT 137 resumed with unchanged output and one attempt; partial auditor
output was preserved and a second attempt completed. Evidence is under
`reference_inference/astra_f4_waiter_recovery_fixture_20261030`. Root-owned mode
0600 inner evidence was read using Docker copy; contents were not changed.

A new frozen v2 fixture repeats those cases after making future metadata readable
and adding recovery for interruption between abandonment marker/state commit,
and between attempt-directory creation/state commit. Untracked live attempts
remain locked and cannot be renamed or duplicated. Local 21-test suite passes.
V1 files remain preserved. V2 will use a new CPU-only retained container and output
directory suffixed `_v2`, with identical scope and acceptance conditions.

### 2026-10-31 amendment: actual controller Python SIGKILL / shell EXIT137 fixture (pre-registration)

Purpose: reproduce the F3 recovery gap using a real retained CPU-only Docker container on 175, then verify guarded restart of that same container. This fixture does not launch inference, consume an NPU, or change chip allocation. It does not establish host-process occupancy safety.

Setup: immutable image `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`; fixed container name `nga-e34_controller_exit137_fixture_20261031`; output `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e34_controller_exit137_fixture_20261031`; source snapshot in sibling directory ending `_source`. The child Python process kills itself with SIGKILL on its first invocation. Its real shell wrapper must retain `EXIT` with `rc=137`. The guard is first invoked without a resume review and must reject without changing that marker. The fixture then writes a review bound to plan hash, exact container ID, actual FinishedAt, and EXIT hash. The guard archives EXIT137 and restarts the retained container. A one-time sentinel permits the child to exit successfully after restart. This is a short integration check expected to finish within one minute; the child Docker container stays retained, with Ceph log, heartbeat, terminal, and relaunch command.

Acceptance: actual initial Docker exit 137 and matching wrapper marker; unreviewed resume rejected; exactly the same container ID after reviewed restart; actual resumed Docker exit 0 and fresh EXIT0; archived EXIT137 content hash unchanged; no NPU mapping or allocation mutation. `FIXTURE_COMPLETE.json` records structured evidence. A real queue `FAILURE.json` or `QUEUE_COMPLETE.json`, a successful original EXIT, identity change, and mismatched review remain rejection cases in unit tests. Results must be appended after execution; they must not replace this pre-registration.

Fixture result (2026-10-30 20:11:00 UTC / 2026-10-31 local): PASS. Retained container `be69f98f66193976c8285ef0df0340ecf397714b5ceacb3f9100fdb1e14e34fc` first exited 137 and then exited 0 after reviewed same-ID resume. Unreviewed resume was rejected. Archived EXIT137 SHA256 is `abad43b6b3bc7288d0e8bdd8eb7a63062fd5d0f3eb286010906ea52023845559`; structured evidence is the preregistered output directory's `FIXTURE_COMPLETE.json`. This closes the tested shell-EXIT137 recovery seam only; production migration remains a separately reviewed action.

### Reviewed production handover procedure (prepared, not executed by fixture)

The new preparer accepts `--handover-plan OLD_PLAN`. It never stops anything. It requires the old controller to be actually exited, checks its frozen plan/spec/receipt/wrapper, binds its exact ID and FinishedAt, and records existing inference/finisher IDs and receipt hashes. The new controller preserves the original queue labels for adopted roles; it uses a fresh hardened-audit directory and a new controller plan/hash. It does not rewrite the original configuration, wrappers, receipts, or labels. Unit tests reject a still-running old controller, changed old plan/spec/receipt, foreign role labels, and changed model identity. The production handover is not claimed complete by the CPU recovery fixture.

Parent execution sequence, after accepting the code and fixture evidence:

1. Stage the five files `jeval_reference_queue.py`, `prepare_jeval_reference_queue.py`, `audit_jeval_inference_hardened.py`, `test_jeval_reference_queue.py`, and `test_prepare_jeval_reference_queue.py` into a new Ceph source directory; retain its hashes. Do not overwrite the running queue's frozen directory.
2. Read-only bind old plan `/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_nimble_queue_20261030/plan.json` to SHA256 `b69ae7f2d1e4b84689302fa3178611a797fd027ce98fba4d41022d43d3f835d7`, controller receipt/spec/wrapper, old controller ID `8ebde745a776a896a37dc46c61292daa77b282975b5b631d7657b1f02b469082`, inference ID `7d5d8d2497267db92587b2029cd5043a2627fb6cf2b0fd46b2db70eed1f2cf15`, and native finisher ID `77bb77d600e54aa6b4ae3131d26ea5adcaa6437e13d9b0050b0eacc6aa811509`. Check current statuses before proceeding. A mismatch requires investigation, never substitution by container name alone.
3. Stop **only** the bound old CPU controller by ID (`docker stop --time 20 8ebde745a776a896a37dc46c61292daa77b282975b5b631d7657b1f02b469082` on 175). Retain its container and original evidence. Re-inspect it and require exited; capture exact FinishedAt. Re-inspect model and native finisher and require the same IDs. Neither is stopped/restarted.
4. On 175, invoke the new staged preparer (host `python3 -I`) with `--source NEW_SOURCE --preregistration REVIEWED_PREREG --config /mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_nimble_inference_20261030/config.json --out NEW_OUTPUT --name NEW_FIXED_CONTROLLER_NAME --handover-plan /mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_nimble_queue_20261030/plan.json`. Use new absent source/output/container names. This writes an immutable new plan and dry preparation audit but no approval and launches nothing. Configuration SHA256 remains `b310b6271a7174f7efad1ba435fa2ad9ac53fecab3aec0f1944ee2f5fd703156`.
5. Parent reviews the exact new `plan.json`, `PREPARATION_AUDIT.json`, source hashes, adopted IDs/receipt hashes, old stopped-generation binding, and fresh hardened audit target. Parent writes `PARENT_REVIEW.json` bound to the **new** plan SHA256, then executes the generated `LAUNCH_EXACT.sh` on 175. The launch script creates/starts only the CPU controller; ordinary queue reconciliation adopts existing inference and finisher receipts without another model launch.
6. Verify actual new controller ID/receipt, its bounded `digest.md`, and unchanged inference/finisher IDs. Confirm original queue labels remain. Preserve old controller exit evidence and both plans. Final acceptance/restart/release independently rehash all 11,257 raw receipt files against the new auditor's manifest; a mutation stops acceptance. Do not describe a running controller as completed inference or accepted metrics.

Recovery of the new controller after Python SIGKILL uses `RESUME_REVIEW.json` with exact `approved_plan_sha256`, `container_id`, `finished_at`, and `exit_sha256` for any EXIT marker. The generated `RESUME_EXACT.sh` archives that interrupted EXIT under `resume_history/<generation-hash>/EXIT` and starts the same retained controller. Existing real queue success/failure terminals cannot be bypassed with this route.

## 20:15 UTC — F4 chronology correction, final recovery evidence and prepared handover

Correction to the preceding “20:12 UTC” heading: that clock value was manually
estimated and is not a valid pre-registration timestamp. The v2 launch actually
started at 20:10:53 UTC and completed at 20:10:57 UTC. Treat the preceding v2 note
as an undated preparation/result note; the original F4 pre-registration above
governs both unchanged SIGKILL scenarios. This correction does not change results.

The v2 retained CPU fixture `nga-astra-f4-waiter-recovery-fixture-v2`, container
`c6b06a62258fc6d94cc32320f4df9b20fa1936d2c6aca2cbe3b8de55148f0c86`,
has Docker exit 0, wrapper EXIT 0, COMPLETE rc 0, inner FIXTURE_COMPLETE rc 0,
and no device mappings. Evidence lives under
`reference_inference/astra_f4_waiter_recovery_fixture_20261030_v2`. Publication
interruption resumed without changing the report or duplicating its one attempt;
partial audit attempt remained preserved and the second attempt completed.

The final waiter additionally rejects privileged/device/mount/namespace exposure
at its own admission. Its 21 local tests pass. Nine launcher guard tests pass,
including existing publication recovery, exact FinishedAt/EXIT review, terminal
preservation, unknown container ownership, unexpected device/namespace exposure,
and Docker daemon error versus proven missing container. Recovery fixture scope
is CPU subprocess interruption; it does not certify model scores or NPU recovery.

Fresh waiter v4 plans for Kev 0.8B/4B/9B are prepared with 13 verified frozen
files each, preserving their live v2 plans’ original inference and finisher IDs.
No approval receipt, launch receipt, or terminal exists yet. V3 preparations are
preserved and superseded without launch. V4 guarded scripts are `LAUNCH_EXACT.sh`
and `RESUME_EXACT.sh` in each `jeval_kev*_hardened_waiter_20261030_v4` directory.
All prior production waiters and model runs remain untouched by this change.

V4 plan SHA256: Kev 0.8B
`f4f19f8e8cbdee41162d69101c5bb6a1f998e9fd016bb3e8564d3784180c6717`;
Kev 4B `240f656f6680c37fc5e486452e64b9762461b8e14dc609293141b11f3ab66b89`;
Kev 9B `9733a6fb09075c1583fb8854f3b20fb6a7b4c88905fd63e19769fe569f279cad`.
The separately frozen auditor is
`6d61edd54b1c8023c617214ea33593ad5ac160365a11560f9751dbca8a6e21ee`.
Parent review must independently accept these artifacts before launch. Any old
waiter stop is a separate handover decision; it must never stop the model or
finisher, release their chip, or rewrite previous audit status.

### 2026-10-31 amendment: manager-only process-observer feasibility fixture (pre-registration)

Purpose: close F1's remaining host-process visibility gap, without changing model runs. A short retained Docker fixture on 175 uses the same immutable image, host PID namespace, no network, read-only `npu-smi` binary and driver-library mounts, and only `/dev/davinci_manager` (no `/dev/davinciN` mappings). It queries fixed physical card 1 using `npu-smi info -t proc-mem -i 1`; its Ceph output retains log, marker, exact relaunch command and the container. Acceptance is successful real command exit with recognizable NPU ID 1 / chip count 1 / chip ID 0 and process records matching a contemporaneous host query. Failure does not permit production use. If feasible, frozen observer code/spec will bind a fresh request nonce and fail closed on command/parse errors; existing inference allows only host PIDs in that exact container's Docker top output, while new claim/release require no reported process. Docker exposure checks remain independently enforced. This fixture does not claim a race-free guarantee against noncooperating external schedulers.

Manager-only feasibility fixture v1 result: FAILED (retained container `4259751c7e62a126b7dae68ab59efb5fc7cd70dfcfc4ee554a2c2bc0828306b4`, actual exit 187, `dcmi module initialize failed. ret is -8005`). Evidence is `e34_manager_observer_fixture_20261031/FIXTURE_COMPLETE.json`. Before rejecting the container route, v2 will add read-only full driver metadata and `/etc/ascend_install.info`, retain only `/dev/davinci_manager`, and enforce a 15-second subprocess timeout. Acceptance remains unchanged; failure requires a tracked host observer rather than a claim of process visibility.

Manager-only v2 result: FAILED (retained `2ba1f1e676a3437099f98e1736e311529bf98e4909dd7e2968354a7ba9bc2ca6`, timeout exit 124). The next preregistered v3 feasibility check adds the native generic control devices `/dev/devmm_svm` and `/dev/hisi_hdc` alongside `/dev/davinci_manager`, while still exposing no `/dev/davinciN`, retaining full read-only driver/install/binary binds, host PID namespace, no network, and 15-second timeout. This tests whether the missing generic control devices caused initialization failure. No persistent host service is launched.

Generic-control-device v3 result: FAILED (retained `1c4312f56976e68d3a30a33f907a4094f7b6067af12d99e25848485dab2b5a4a`, exit 187, same DCMI initialization error). Evidence is `e34_manager_observer_fixture_20261031_v3/FIXTURE_COMPLETE.json`. Host-process F1 closure remains open; no host service was launched and no production model/container was stopped. A strict parser is implemented, but parsing code alone does not establish live process visibility.

### 2026-10-31 amendment: bounded chip-1 process query (pre-registration)

The reviewed next feasibility check adds exactly physical `/dev/davinci1` to the three native generic control devices; no other chip is exposed. It remains a retained immutable-image container, no network, read-only native driver/install/sbin binds, and a fixed `npu-smi info -t proc-mem -i 1` command with a 15-second timeout and no model load. Acceptance requires actual exit 0 and strict card-1 process-list parsing. The intended production guard runs this helper only under the existing allocation lock immediately before allocation claim/release, never as a persistent observer. Each request has a persisted nonce and a unique retained container, frozen exact spec/code, nonce-bound report/terminal, and actual exit verification. All other Docker exposure checks run before and after it; no live-container exemption remains when allocation changes. If host processes are present, claim/release is denied. Existing running reconciliation does not launch repeated helpers.

Chip-1 feasibility v4 result: FAILED CLOSED while chip 1 is occupied (retained `1a6a3229b46632f7c07828ec18930829a7a61a0e0ca47920d71a94203e491e4f`, actual exit 172, `dcmi model initialized failed, because the device is used. ret is -8020`). This confirms the bounded query does not silently return an empty list on this busy device; it does not establish a successful empty-device query. All model runs remain unchanged.

### 2026-10-31 amendment: actual nonce-bound boundary-guard rejection fixture (pre-registration)

The implemented boundary helper is now tested on the still-busy physical chip 1 using its frozen Python entrypoint, fixed query command, persisted nonce/spec/receipt, structured report and terminal, and actual retained Docker identity. This fixture never reads or writes the production allocation file and does not invoke claim/release. It calls the isolated query guard directly, expecting rejection on busy-chip/DCMI failure or a nonempty process list. Acceptance: no ACCEPTED marker, retained helper/spec/request/receipt/report/COMPLETE, a specific GUARD_FAILURE marker pointing to evidence, and a fixture result explicitly reporting that the idle success path is still unverified. Production guard calls occur only before allocation mutations under the allocation lock, with live-container exposure checks before and after. Existing running reconciliation adds no repeated helper.

Nonce-bound boundary-guard fixture result: PASS for expected busy rejection only (2026-10-30 20:22:25 UTC). Retained helper `64e8b90d02e6dd44e30631152776cb72696f828de9e6f157777ef20f9217b4ca`, request nonce `9ee17a3bf935406187958df702df2835`, helper COMPLETE rc 1, no ACCEPTED marker, retained GUARD_FAILURE. Structured evidence: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e34_process_guard_fixture_20261031/FIXTURE_COMPLETE.json`; it explicitly sets `idle_success_path_verified=false` and `allocation_accessed=false`. The production idle-chip success path remains to be tested when physical chip 1 becomes free. Failure of that eventual query keeps allocation owned and emits the evidence pointer; it cannot release the chip silently. Chips 6/7 were not used.

The prepared handover now additionally includes frozen `PROCESS_QUERY_SPEC.json`. Parent review must inspect its exact three generic control devices plus physical chip 1, host PID mode, no network, full command/environment, and read-only native driver/install/sbin mounts. These helpers are one-shot retained queries, not persistent observers. The actual empty-device result is not claimed by the busy fixture or mocked unit tests.

## F4 production-path recovery extension — pre-registration before launch

The actual Astra re-review final message was recovered from item_20 in the bounded
event tail despite runner timeout rc 124; the timeout record is unchanged. V4
is explicitly NOT approved and no v4 migration is executed. Its six findings
require authenticated final public bytes, no-clobber production terminal,
post-terminal wrapper recovery, auditor-signal recovery, PID-reuse-safe waiting,
and enforced source-read-only/output-only-write mounts. Docker socket permissions
remain privileged; operational GET-only code is not a capability security sandbox.

Before launch, register a new retained CPU fixture using the unchanged immutable
E33 image, no NPU devices, Ceph log/heartbeat/terminal and exact commands. The new
fixture executes the actual production `run()` commit path, with explicitly
synthetic Docker inspection/source/metric controls. Four injected subprocess
faults are: kill controller immediately after public report publication; kill
controller immediately after successful production COMPLETE publication; kill
only auditor after partial output; kill auditor supervisor after partial output.
The first two must yield wrapper EXIT 137 then reviewed recovery to EXIT 0 with
identical report, exactly one audit attempt, and (for post-terminal kill) identical
original COMPLETE bytes. The latter two must preserve partial attempt0 and finish
attempt1; auditor-only kill must record raw returncode -9, distinct from semantic
audit failure. Every final production terminal must hash the authenticated public
report. No model correctness, NPU recovery, or Docker capability-isolation claim
is made by this fixture. Planned directory:
`reference_inference/astra_f4_production_recovery_fixture_20261030_v5`.

### 2026-10-31 reviewed preparation helper and repeated handover correction

`tools/prepare_jeval_handover.py` prepares the replacement queue in a separate retained CPU Docker container. Its frozen HANDOVER_INTENT binds the old plan/config hashes and exact old-controller/model/finisher IDs. It requires the old controller to have already exited; it cannot stop it. It emits a heartbeat, bounded digest, terminal, and exact launch/relaunch scripts. Its only Docker start operation is for the CPU preparation container. Queue approval and launch remain later separate actions; no allocation or model/container state changes occur during preparation. Original staged v1 is retained as an obsolete pre-review snapshot, never launched; subsequent review fixes require a new version.

The second Astra review found a recursive-handover gap: a third queue must preserve the first queue's labels for roles adopted through an intermediate queue. The correction records per-role `label_hash` and authenticates every inherited label against its ancestor plan, controller spec/wrapper/receipt, role receipt/container ID, and unchanged formal config. Only the immediate previous controller must be actually stopped. A failed intermediate controller's FAILURE/QUEUE_COMPLETE remains preserved. A→B→C tests verify both inference and native finisher retain original A labels and IDs, and reject forged actual or ancestral labels. This change does not change inference or metrics.

Correction to the preceding repeated-handover paragraph (2026-10-31): checking only the immediate predecessor is insufficient, because an older controller could be restarted. The final implementation re-inspects **every ancestor controller** against its exact spec/receipt/ID, requires CPU-only exposure and actual exited status, and requires the edge's original FinishedAt. Tests now reject an ancestor that is running again and one that was restarted and stopped at a different FinishedAt. A retained real failure is still allowed as long as that exact stopped generation remains unchanged.

## Production-path recovery result and unlaunched v6 preparation

The preregistered four-seam production `run()` fixture completed successfully.
Retained immutable CPU container
`20b892306a8918bab64f3da9d8a8bfd86e56f922420dbbb9db596785c153028e`
has Docker exit 0, wrapper EXIT 0, outer COMPLETE rc 0 and inner
FIXTURE_COMPLETE rc 0. Directory:
`reference_inference/astra_f4_production_recovery_fixture_20261030_v5`.
Host 175 timestamps are 20:27:22–20:27:30 UTC; host and clock-tool readings
differ, so pre-registration order is established by the write-before-launch
execution sequence rather than cross-machine timestamp comparison.

Both controller-kill cases yielded initial EXIT 137 then EXIT 0, with exactly
one audit attempt and identical public report. The post-terminal case additionally
preserved the original COMPLETE bytes. Auditor-only SIGKILL recorded raw return
code -9, preserved partial attempt0 and succeeded with attempt1. Supervisor-kill
likewise preserved partial output and completed attempt1. Synthetic source,
Docker-inspection and metric controls are explicit; actual production commit
functions and real subprocess SIGKILL/wrapper exits were exercised.

All six waiter review findings now have implementation changes and focused tests:
authenticated final public-byte hash, strict source-ro/output-rw bind allowlist
and effective mount verification, no-clobber terminal, successful-terminal wrapper
reconciliation, signal-vs-semantic auditor failure distinction, and PID-reuse-safe
lock waiting. Local suites pass: 26 waiter, 13 launcher, 26 auditor. V6 frozen
launcher tests also pass independently from their generated directory.

A subsequent Astra queue review required the auditor to bind all resource
permission channels and effective mounts for inference/probe/finisher. This
additional correction is included in v6. Read-only actual compatibility checks
pass for all 12 roles across Kev 0.8B/4B/9B and Nimble. Inference and finisher
containers remained running; these checks do not certify completion or scores.

V4 remains rejected and its rollout helper is not executed. V5 preparations are
preserved and superseded by unapproved v6 preparations, each with 17 verified
frozen files and no launch receipt or terminal. All three preserve the original
inference/finisher identities. Source directory is mounted read-only; only the
new waiter output directory is writable. Exact Docker socket mount is retained;
its privileged API means this is operational protection, not capability isolation.

V6 plan hashes: Kev 0.8B
`0cb3da20591a8a6c860339b5b4c156f2be360bff34237280aafc0bd9d54adb51`;
Kev 4B `d4368a99037a0edf974d494f486ff779442e7565b6f71fe631b4ffe733cf35e0`;
Kev 9B `20b6421d5caf92b3dd6601299fa4d8bbdc97aa82a16bdd127c96821efa9479a8`.
Auditor SHA256 `d7cb13db51c692d39a01c81f83fd0db07c833873a1845170d85b25b89490933f`.
Waiter SHA256 `403c9b43663c148d9bfdb0693f63937215f0a34953345f6e43814d71b4b2f04e`.
Launcher SHA256 `59a4ad34c68a00824fec64759373ddc3ad21b75c8c7310fea943a28a61c86754`.
These artifacts require the new scoped review; no production handover is claimed.

## V6 handover pre-registration — prepared only, before any execution

A new guarded v6 handover helper will be prepared separately from the rejected,
never-executed v4 helper. Its default action is read-only dry checking. Execution
is pending the actual scoped Astra v6 review and parent acceptance. The helper
will bind exactly the three v6 plan hashes above, their original inference and
finisher IDs, and these existing CPU v2 waiter IDs: Kev 0.8B
`d1fc508d706e38d24c79def07791ba3e783534d3f7735871dce3343ba45e9494`,
Kev 4B `d9769d5a66bead3a40759670446c3d4f7c691cdd2450de2f285d6102d199a067`,
Kev 9B `4d9708dce49e64491ed835d0624c180842c43d87113219e3a7a4a6e8d385e193`.

Before any stop, it will record a durable handover intent, prior terminal presence,
container states, source states and heartbeat. Only those exact CPU waiter IDs
may be stopped, and an existing successful/failed terminal is preserved without
a stop. It will never stop or restart models/finishers or release their chips.
Actual old Docker exit, wrapper EXIT and terminal evidence will be retained in
new handover records. Approval will be newly written for the exact v6 plan hash;
no old approval is copied. New waiter actual effective mounts and receipts must
be checked, and original source states recorded again after launch.

The host control wrapper is bounded to 55 seconds, keeps Ceph logs and an outer
EXIT, and refuses to overwrite existing terminal evidence. A failed/interrupted
handover remains evidence requiring review; it is not silently retried. Prepared
artifacts will live under `reference_inference/e34_kev_waiter_v6_handover_20261030`.
This registration and preparation do not authorize or claim a handover.

## 20:44 UTC — Nimble hardened queue handover actually running

Parent verified the exact staged 11-file handover closure and actual old controller/model/finisher IDs, preserved stop intent, then stopped only old CPU controller `8ebde745a776a896a37dc46c61292daa77b282975b5b631d7657b1f02b469082` at FinishedAt `2026-10-30T20:42:17.47902831Z`. Inference `7d5d8d2497267db92587b2029cd5043a2627fb6cf2b0fd46b2db70eed1f2cf15` and finisher `77bb77d600e54aa6b4ae3131d26ea5adcaa6437e13d9b0050b0eacc6aa811509` continued unchanged.

Retained CPU preparation `5bc7ac6697020b8600b4d29c045e1448cb8e7db10ce85e78b4893d7020dd1f2a` completed with terminal/wrapper/actual exit 0. Parent rehashed all 23 new frozen files and approved new plan `263491613ccd8276867f1a7f19bf3a790b24891a20de3ab8577167245ed6413a`, at `reference_inference/jeval_nimble_queue_hardened_20261031_v2/plan.json`. The retained new CPU controller `f9390b30565652a0e07e00936af09b0bcbeed7621e066ea608defa3257ffb6bb` actually started; its 20:44 UTC digest confirms existing Nimble inference 4732/11257. This is completed controller handover, not completed model evaluation.

The new queue preserves original role labels, uses auditor SHA `d7cb13db51c692d39a01c81f83fd0db07c833873a1845170d85b25b89490933f`, verifies full receipt manifests at acceptance/release, and requires an actual successful empty-device query before releasing chip 1. That idle helper success remains unverified until the model exits; a failed query retains allocation and evidence. Scoped Astra reviews are recorded in the queue, chain and waiter-v6 review files; no score certification is claimed.


## v6 actual handover failure and v7r2 continuation pre-registration

Parent executed the v6 handover at host 20:37 UTC. Only old Kev08 CPU waiter
`d1fc508d706e38d24c79def07791ba3e783534d3f7735871dce3343ba45e9494` was stopped;
its actual state is exited 137, FinishedAt `2026-10-30T20:37:09.71879211Z`,
with neither wrapper EXIT nor COMPLETE. This is a Docker interruption, not a
fabricated wrapper marker. Original inference and finisher remained running.
The new v6 launcher rejected Docker's lowercase `error: no such object:` output
before creating any v6 container. Kev4/Kev9 old waiters remained running.
The failed migration's rc1 COMPLETE, intent and old-state record remain preserved.

The corrected launcher establishes absence only through Docker HTTP 404; HTTP
200 returns the exact object, while permission/server/transport errors reject
without create/start. Sixteen launcher tests pass, including HTTP403/500 and socket
failure negatives. A read-only real 175 query proved HTTP404 for absent v7r2 and
HTTP200 for the exact retained old Kev08 container. Waiter and auditor bytes are
unchanged from the scoped Astra-approved v6 sources.

An initial unapproved v7 preparation retained an old output bind; prelaunch review
rejected it and appended PREPARATION_REJECTED.json. Those plans were never approved
or launched. The official reusable preparer produced fresh v7r2 generations with
17 frozen files each and correct read-only Ceph / writable own-output mounts:

| Model | v7r2 plan SHA256 |
| --- | --- |
| Kev08 | `3383fd728cfbdbded2fba370b7f3a5fb9c42ec201ec79fa67426003105d7187d` |
| Kev4 | `4f651330eb004684f20f0f6f322392ebf4e2bb5dbc2f2c214a38bdce0b58486d` |
| Kev9 | `663181055341064775e739f98d22adc11f57f375e62b5a2b9b383b2d0e85366c` |

Before any v7r2 execution, the new migration helper is preregistered to authenticate
all plan/source identities and exact CPU mount policy. Its explicit prior-review
file binds the stopped Kev08 ID, FinishedAt, exit137, absent EXIT/COMPLETE and hashes
of the v6 failed migration evidence. It never restarts the old Kev08 waiter. The
remaining stop allowlist contains only the three exact old CPU waiters; it never
stops models/finishers or changes allocations. It records intent, per-stage state,
heartbeat and terminal, and launches each v7r2 through the new guarded launcher.
The 55-second wrapper preserves logs/EXIT on Ceph. Actual read-only dry check passed;
no v7r2 approval or launch occurred during preparation. Durable package:
`reference_inference/e34_kev_waiter_v7r2_handover_20261030/`.
