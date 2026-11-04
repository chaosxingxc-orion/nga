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
