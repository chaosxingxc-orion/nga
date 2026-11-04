# Reusable experiment recovery and efficiency contract

These engineering requirements consolidate the owner's functional-first and asynchronous CPU/NPU constraints and the actual November 4 recovery reviews. They are acceptance criteria for new adapters, not a claim that every current launcher implements them. An already admitted frozen run is not edited to adopt this document.

## Functional baseline before optimization

First lock configuration-driven preparation, exact execution, persistent outputs, deterministic scoring and explicit completion semantics with meaningful tests. Keep task/model/data/protocol variation in configuration, injected through versioned interfaces. Add a narrow adapter only for a genuinely new lifecycle or numerical contract; do not copy a launcher for each experiment. Measure throughput improvements after the functional path and output-equivalence contract are locked. Minimum release/ownership/correctness checks remain necessary during functional development.

## Failure domains and recovery requirements

| Requirement | Acceptance evidence | Known boundary |
| --- | --- | --- |
| Detached, survivable execution | Retained container, Ceph logs, timestamped progress heartbeat, terminal marker and exact relaunch command | Launch transport return is not container liveness or completion |
| One-shot launch | Durable exclusive intent before external effect, followed by bound receipt; uncertain outcome inspected by exact process/container generation | Never retry merely because SSH timed out or an observation failed |
| All entrypoints enforce the same contract | Direct start, internal supervise and explicit recovery routes reject absent/stale activation and changed imports | A direct supervise route must not bypass checks performed only by a watcher |
| Resource generation checked atomically | Under the allocation lock: exact predecessor release/claim/container generation and matching free-ledger lineage; reject foreign owner or later free generation | Checking predecessor release before acquiring the lock leaves a race |
| Separate dependency meanings | Own training success controls adapter/data validity; predecessor physical release controls resource availability | A failed but genuinely released unrelated predecessor need not block a release-only edge |
| Preserve failed history | Original failed outputs/terminals immutable; source-labelled reconciliation only where independently justified | Reconstructed host terminal is not an invented runtime success |
| Resume committed work | Exact byte/prefix/identity inventory in an independent new output; reject overlap, mutated imports, foreign rows or uncommitted tail | Imported rows require provenance in final independent result/member evidence |
| Training continuation | Parameter order, shapes/dtypes, optimizer, scheduler, step/data cursor and RNG mechanism bound; working checkpoint rechecked at final start boundary | CPU state reload is not newly measured long-horizon NPU numerical equivalence |
| Service failure observable | Persistent heartbeat, terminal and relaunch record on every normal/error exit; uncertain starts retain ownership | Missing terminal is unknown, not successful completion or proof of no launch |
| Async CPU/NPU | Release NPU after authentic execution terminal; independent CPU queue performs scoring/review and prepares successors concurrently | CPU report formatting and unrelated scientific analysis cannot hold the device |

November 4 evidence: independently accepted 9B fixed-panel recovery and diffchip DEV prefix recovery; QO release-only adapter with separate own-training dependency. PT2 recovery v1 was rejected because its direct-supervise path bypassed readiness/import checks, its locked resource transaction accepted a foreign free generation, and its service error path omitted a terminal. PT2 v2 must demonstrate the repair; v1 passing CPU verifier and nine tests did not cover those cases.

## Monitoring and efficiency

Use scripts to consume logs, heartbeat, progress, result/terminal and release records; events wake them, approximately 600-second polling is the fallback. The orchestrator reads bounded digests. Escalate pointed slices only for exceptions; do not turn routine monitoring into agent polling. Keep numerical suspicious-success checks, including exact zero/one rates and insufficient samples, separate from lifecycle success.

Monitor replacement itself follows a generation contract: validate new configuration and source pins, start once, verify its process generation and first complete digest, then stop only the revalidated old monitor. Do not stop experiment guards or CPU consumers while replacing monitoring. A script status-model mismatch such as a guard's launch_requested marker is a monitor issue; it does not authorize an experiment restart.

Report throughput per chip with chip count and reserved memory. Distinguish partial-cell throughput, complete-run wall time, total chip-hours and useful completed experiments. Segmented sequential loops do not establish multicard acceleration. A full queue means executable admitted work, not merely planned nodes. Maintain useful task depth; do not rerun completed work solely to occupy devices.

## Test and review expectations

Exercise real resource transactions on isolated temporary ledgers, and mutate predecessor identity, free lineage, command, source pins, working imports, duplicate attempts and uncertain-start receipts. Test actual entrypoint dispatch as well as helpers. Positive tests alone cannot establish that bypass paths fail closed. Fixtures must never touch the production allocation ledger or fabricate result evidence.

Independent package review grants only its explicit scope. Execution acceptance, physical release, result reconstruction, campaign membership and scientific acceptance remain distinct. Save detailed HANDOFF records and parent acceptance locally; publish current conclusions/status in the GitHub Wiki, replacing existing rows in place. Preserve original metrics and protocol boundaries. Process records follow the three-day archive policy while protecting active/frozen evidence references.
