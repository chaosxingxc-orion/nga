# Event consumer readiness

A successful process launch is not a ready consumer. A launcher can know the PID
before that process installs its signal handler. Sending SIGUSR1 in that interval
terminates the process under the default Linux disposition.

`experiment_event_relay_v2.py` retains the reviewed v1 event and approval semantics
and adds a mandatory readiness contract. Use a fresh `experiment-event-relay-v2`
configuration and output directory. The pinned v1 sibling file is still required;
deploy both files without changing the existing v1 source or active relay.

Each target's pinned service receipt must be written by that consumer after it
installs its handler, and contain:

```json
{
  "process": {
    "pid": 123,
    "boot_id": "actual-host-boot-id",
    "start_ticks": "actual-process-start-ticks",
    "argv": ["actual", "command"]
  },
  "signals": {"wake": "SIGUSR1"}
}
```

The configuration binds this exact receipt under `files` and
`events[].target.service`, with the same process under `target.identity`. Obtain
the hash after the consumer publishes its final ready receipt. Do not promote a
launcher receipt by adding a readiness field externally. Preparequeue v3 already
publishes this handshake after installing its handlers. Other consumer types must
publish the same field before migration; missing fields deliberately fail closed.

`--preflight` verifies all target receipts, live PID/boot/start-time/argv identity
and the kernel's caught-signal mask without creating output or sending signals.
At each wake v2 repeats those checks, opens a pidfd before checking the current
identity, rechecks the receipt, and only then sends SIGUSR1. A missing, changed or
stale receipt blocks the event. Its state needs explicit reconciliation; it does
not automatically restart a consumer or NPU experiment. Existing600second
fallback consumers stay in place.

Tests: `python3 -B -m unittest tools.test_experiment_event_relay_v2
tools.test_experiment_event_relay_v1`. The v2 suite exercises actual processes
before/after handler readiness, false ready metadata before a handler, stale
identity, changed receipt, failed readiness publication, and intent persistence
failure. It also runs the actual preparequeue v3 lifecycle with only its work
provider replaced by a small fixture, proving a ready signal advances that queue.

This checks a cooperative consumer's startup contract. SigCgt proves a handler is
installed, not that it has correct business semantics or will remain installed.
A consumer must retain its handler throughout its advertised ready lifetime;
replacing the handler immediately after the check remains a process-level race.
This is not a signed authorship scheme, universal crash proof or utilization
measurement. The parent independently reviewed this component and reran all21 tests. V2 has
not been deployed; exact consumer configurations still require migration checks.

For other engineering projects, keep launch and ready receipts distinct, publish
readiness only after required handlers/dependencies are active, bind readiness to
one process generation, persist delivery intent before notifying, and test the
real startup interval rather than only mocked successful calls. Keep wake
delivery separate from work acceptance and completion.

## Queue signal handling and progress

`bev_successor_prepare_queue_v4.py` preserves the v3 preparation configuration
schema and scientific/resource checks. It replaces Event-based signal wakeups
with scalar handler flags and CPython's nonblocking wakeup pipe. The main loop
uses select with the existing 600-second fallback. Deploy it only in a fresh,
explicitly configured queue generation; existing pinned runs remain unchanged.

A Python signal handler must not acquire a lock held by the interrupted main
thread. The isolated reproducer demonstrates Event/Condition reentry deadlock;
it does not establish the historical production stack. Readiness proves the
handler is installed, while `PROGRESS.json` and heartbeat pass counters show
whether work advances. Fresh heartbeats alone cannot rule out a stuck builder.
SIGTERM waits for owned builders, so a builder that never exits still requires
progress-age detection and identity-bound reconciliation.

Verification: 51 tests in `python3 -B -m unittest
tools.test_bev_successor_prepare_queue_v4`, plus an independent two-node fixture
using actual binder/builder subprocesses and simulated Docker observations.
The second node starts after its exact release and SIGUSR1; each builder executes
once. These are preparation-controller checks, not NPU throughput or scientific
admission. The component is reviewed; production migration is separate.

Reusable operating rules:

- Separate process liveness, dependency progress, readiness, execution and result
  acceptance. Give each its own timestamp and terminal evidence.
- Use event wakeups with fallback polling, and reconcile uncertain child ownership
  before retrying; never infer a restart is safe from a missing observation alone.
- Refill ready work by estimated chip-hours. Planned/prepared work cannot satisfy
  a ready-stock target, and CPU result analysis must not block unrelated NPU jobs.
- A working queue cannot compensate for incomplete adapters or admission. Track
  preparation, review and launch latency independently to expose that bottleneck.

## Reviewed dispatcher signal handling

`reviewed_successor_dispatch_v2.py` applies the same lock-free signal mechanism
to the execution dispatcher. The preparation queue fix does not fix a separate
dispatcher process. Configuration schema, admission, resource checks, commands,
launch intents and reconciliation remain unchanged. A separate heartbeat thread
reports liveness; pass counters and completion timestamps report actual progress.

Deploy only after the old dispatcher is verified terminal or explicitly reconciled.
Preserve its configuration and durable launch state, and pin the new source in a
new service generation. Do not send relay signals to the old Event-based dispatcher.
An existing reviewed `--once` dispatch can supply a first wave while the persistent
replacement is independently verified. No signal repair grants scientific approval
or permits replay of an uncertain launch.

Validation includes unchanged admission/dispatch AST, a real signal delivered
while an Event lock is held, and a real child process launched exactly once across
repeated wake signals. A slow synchronous verification can still delay the loop;
the repair removes the signal-lock hazard, not all sources of dispatch latency.

## Host runtime configuration

`experiment_entrypoint.py` v2 (`nga-experiment-entrypoint-v2`,
`native-config-dev-v1`) accepts an explicit `host_runtime` containing the Python
path, environment overlay and module imports. Import checks, host preflight,
verification and guarded start use that same runtime. Missing dependencies fail
before resource claims or attempt creation. This fixes a real activation failure
where system Python lacked numpy while a different Python had passed preflight.
CPU consumers also need their explicit dependency environment: the reviewer
Python path alone did not provide numpy without its configured PYTHONPATH.

The v1 entrypoint behavior is retained. V2 currently covers synthetic native DEV,
not arbitrary TEST or training launchers. The host still owns exact command
approval, resource reconciliation and detachment. Configured import availability
is not a hermetic or binary-pinned Python environment; model and scientific code
pins remain enforced by the existing execution package. A returned start request
is not proof of a live container.

Verification includes 16 tests, independent negative scope/dependency checks and
an actual175 validate-only invocation against a completed plan. All115 existing
output JSON files stayed byte-identical; no NPU task was restarted.
