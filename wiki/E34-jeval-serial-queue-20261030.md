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
