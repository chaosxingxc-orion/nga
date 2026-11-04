# Subagent task records and parent acceptance

Owner clarification, 2026-11-04: every delegated task must leave a detailed,
self-contained record of its goal, method and results for the parent agent to
analyse. A status label, final chat answer or communication message is not a
handoff. This applies to implementation, execution, analysis and review tasks.

## Record location and authority

Maintain `HANDOFF.md` in the task's existing local preparation/review directory
or its Ceph task directory. Existing REPORT/DELIVERY/ACCEPTANCE artifacts may
supply sections by exact links; do not duplicate large evidence inventories.
Messages announce progress, blockers and record locations. They never replace
recorded evidence. Keep process records local/Ceph; publish only accepted current
conclusions to the GitHub Wiki. This reusable contract may be tracked in Git.

Write the goal and acceptance criteria at task start. Update on material findings,
failed checks, changed methods, execution milestones and completion, rather than
on every tool call. Before ending, ensure another agent can understand what was
actually done and what remains without reconstructing the conversation. If a
record is reconstructed later, say so and identify the source artifacts; do not
invent a contemporaneous log or claim it was written by the original agent.

## Required handoff content

1. **Identity and goal:** task ID, agent role, UTC update, requested outcome,
   relationship to the main objective, scope and explicit non-goals.
2. **Inputs and constraints:** exact source/config versions, relevant paths and
   hashes, dependencies, user constraints, prohibited actions and initial
   acceptance criteria. Record model identity only when actually evidenced.
3. **Actual method:** steps performed, key implementation/analysis choices and
   their reasons, alternatives ruled out and why, departures from the brief.
4. **Actions and changes:** files changed, commands or reproducible entry points,
   external effects, runs/services started, and actions intentionally pending.
5. **Findings and evidence:** meaningful observations with paths/hash references;
   distinguish measured facts, interpretation, hypotheses and unknowns. Link
   bounded log pointers rather than copying raw logs into the handoff.
6. **Verification:** tests/checks actually run, coverage and outcomes, failures,
   limitations, skipped checks and why. Test counts alone are insufficient.
7. **Results and scope:** deliverables, exact result counts/denominators where
   applicable, what the evidence proves and does not prove, and explicit
   distinction between author completion, independent review and parent acceptance.
8. **Open work and decisions:** blockers, outstanding issues, recommended next
   steps and dependencies, and decisions the parent must make. State none if none.
9. **Execution continuity:** exact live handles/generations, terminal/heartbeat/
   digest locations, remaining work, relaunch/recovery instructions and uncertain
   starts. State not applicable for tasks without background execution.

Do not report an absent review or unrun test as passed. Keep frozen receipts and
experiment inputs unchanged; add dated corrections or a new version. A fresh
handoff must not inherit stale running/completed state from a prior task.

## Parent acceptance

The parent reads the handoff and referenced decisive evidence, checks the original
acceptance criteria against actual outputs, and records its judgment locally:
accepted scope, verification performed, rejected/uncertain claims, corrections
requested and next assigned action. Delegate completion is not parent acceptance.
Missing material records are returned to the same author for completion; do not
rebuild the author's reasoning from messages and call it an independent record.

Maintain a bounded latest local handoff index with task ID, goal, record path,
acceptance state and next action. Historical process records follow the owner's
three-day archive policy; preserve active/frozen evidence references and a lookup
index. Archival does not change authoritative experiment results. Never mark the
archive timer deployed merely because this policy exists.

Documentation is produced alongside work. Do not pause already admitted NPU jobs
for this recordkeeping. Existing experiment launch/review requirements remain in
force; this contract adds no user approval step.
