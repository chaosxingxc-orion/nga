# Control training to DEV handoff

`tools/r3_control_dev_handoff.py` composes the existing pinned formal-wave
capture/review machinery and posttrain DEV binder for QO seed2 and PT seeds2/3.
It has no resource claim, container, inference launch, adoption or TEST operation.
Exact independent review and parent authorization must precede production use.

The immutable prepared configuration is
`.local/preparations/control-dev-handoff-20261102-v4/CONFIG.json`, with its pin in
`CONFIG-PIN.json`. V1/v2/v3 remain preparation history. This generation has not been
started; `ACTUAL-INSPECT.json` is a read-only inspection of current controls.

## Exact existing inputs

The config binds the actual control-successor v3 queue, all three original
prospective control plans and their attached exact reviews. It binds the current
combined Track KT closure and immutable copies of the accepted qualifier, formal
wave handoff, posttrain binder and CPU queue event helper. The outputs match the
qualification integration reservation:

`/mnt/cephfs/xingchao/experiments/jev/r3_runs/qualification_control_dev_prospective_20261102_v1/{qo_s2,pt_s2,pt_s3}`

These now have a concrete producer configuration, pending its exact review. No
output directory or plan is created until successful training is captured and a
genuine independent postrun review has been explicitly injected. DEV execution
review and live resource assignment remain separate.

## Reuse and two narrow interface adapters

The four-role handoff cannot directly configure controls: it requires a formal
K1 schedule and exactly four role identities. This composition reuses its
unchanged capture, capture equality, independent review verification, atomic
publication and per-job failure handling.

The control queue places prerequisite evidence in the original resource claim;
the actual control plans have no `successor_guard` and do not emit K1's
`SUCCESSOR_PRECONDITION.json`. That one file is excluded from the reused capture
list. Genuine claim/release, launch, supervisor, full3116 manifest, driver/attempt
terminal and adapter evidence remain required. Actual retained-container reality
still requires independent postrun verification; saved receipt hashes alone do
not prove it.

The existing binder expects a top-level `arm` absent from the real control plans.
The accepted qualifier first validates the exact command objective and semantic
control contract. Only the binder's `semantic_arm` call receives an in-memory
view with that validated objective. The unchanged binder reads and hashes the
original plan throughout; no frozen bytes, manifest values or output labels are
rewritten. QO remains Base seed2/drop-state, PT remains Instruct seeds2/3/full-state.

## CPU lifecycle

Use the frozen generation's executable with `validate` or `inspect`, supplying
`--config ABSOLUTE_CONFIG --sha256 INDEPENDENT_CONFIG_PIN`. Inspect names missing
completion files and does not create state or outputs.

After exact source/config review and parent authorization, `watch` can run in a
detached CPU process with durable CephFS state and log redirection. It captures
completed training at item granularity, writes `CAPTURE.json`, and waits at
`REVIEW_REQUIRED`. A separate authorized caller uses `inject-review --role ROLE
--review ABSOLUTE_REVIEW --review-sha256 INDEPENDENT_REVIEW_PIN`. Review files must
be external to training/state, bind exact capture/queue/config inventories, and
provide all genuine postrun checks and evidence pins required by the reused
verifier. No watcher fabricates those checks.

The watcher then invokes the actual binder, writes an exclusive prepare intent,
revalidates capture/config afterward and writes a pinned `PREPARED.json`. The
resulting plan leaves `execution_review` and `chip_assignment` as PENDING and
does not create `execution.json`. Existing outputs are never adopted; uncertain
intents and failures stop that item for explicit repair. Other controls continue.

Filesystem notifications on training terminals, release receipts and injected
review references request ordinary revalidation; a 600-second fallback handles
missed or remote Ceph events. Heartbeat/digest carry progress and exact missing
paths. RELAUNCH and terminal EXIT files are durable. Terminal watchers are not
restarted; a detached invocation must redirect stdout/stderr to a durable log.

## Verified scope

Sixteen CPU tests use real control-plan shapes and the actual unchanged binder with
synthetic completion/review files. They cover all three semantic controls, repeat
consumption, missing release, failed training, independent lanes, wrong control
manifest, missing/invalid review, changed adapter, uncertain intent, 600-second
event fallback and terminal/relaunch artifacts.

Actual read-only inspection finds QO seed2 and PT seed2 waiting with eleven
completion artifacts missing each, and live PT seed3 waiting with six missing.
Training remains untouched. Complete real postrun review and plan preparation
cannot be demonstrated before those actual completions exist. No live watcher,
DEV launch, NPU action, claims, TEST read, commits or pushes occurred.

## V4 review fixes and exact deployment (prepared, not deployed)

The embedded claim guard is mandatory: exact queue/config/job/canonical plan,
pinned predecessor, successful terminal/ownership chain and the precise free
entry saved in the predecessor release are verified before capture. Historical
release state is used; today's allocation is deliberately not used. All
predecessor evidence hashes join CAPTURE. Independent external review must also
explicitly set control_prerequisite_identity_and_release true.

Run on the current orchestration CPU host, where /usr/bin/python3.11 and the
frozen local package exist. The config pin is
24358a35cdffc5900279467f35f0ace3a7d2ee371d9fb15f29694dd9f2de23ea.
The exact detached command is in DEPLOYMENT.json and LAUNCH.sh. After independent
review and parent acceptance, execute:

    bash /home/xingchao/workspace/nga/.local/preparations/control-dev-handoff-20261102-v4/LAUNCH.sh

The script runs nohup /usr/bin/python3.11 -B -P with the fixed controller,
config and hash, stdin from /dev/null, stdout/stderr appended to Ceph
r3_runs/control_dev_handoff_20261102_v4/state/watch.log.
The same directory holds watch.lock (exclusive service identity), heartbeat.json,
digest.json, RELAUNCH.json and EXIT.json. RELAUNCH includes the exact detached
command, log and terminal locations. Never restart a terminal watcher or replay
uncertain preparation. Reconcile retained PID/lock and absence of terminal before
resuming the exact invocation; failures require a separately reviewed generation.
No automatic reboot service is installed. The watch lock prevents duplicate
active consumers. All jobs terminal writes EXIT.json; failed items do not block
independent lanes. This service never launches NPU work.

V4 adds negative coverage for omitted guard, wrong queue/job/canonical identity,
internally inconsistent or forged free entry, foreign predecessor path,
missing/mutated predecessor inventory, wrong control claim and omitted explicit
external prerequisite check. The actual PT seed3 claim's 76 predecessor hashes
pass the new saved-proof validator. This read-only check is not an independent
retained-container observation or campaign completion.
