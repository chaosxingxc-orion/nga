# Unified event service v1

Engineering integration component; not a release, scientific acceptance, physical resource observation, or authorization to start an experiment. The checked-in engineering release policy currently holds new dispatch. Do not start a production service under that policy as a release exercise.

During the consumer call a worker writes `workers/<node>/heartbeat.json` every ten seconds. Its phase covers both validation and waiting: it proves only that the worker heartbeat thread was scheduled, not that the consumer or container made progress. The worker terminal remains the outcome evidence. This heartbeat is independent of the service supervisor heartbeat and does not establish consumer progress.

## Configuration and trust

Supply an absolute path and SHA-256 for a JSON object with exactly these keys:

```json
{"schema":"unified-event-service-v1", "graph":{"path":"/absolute/graph.json","sha256":"<64 hex>"}, "policy":{"path":"/absolute/policy.json","sha256":"<64 hex>"}, "state_dir":"/absolute/private-state", "socket":"/absolute/private-state/event.sock", "review_pins":[{"path":"/absolute/review.json","sha256":"<64 hex>"}], "python":"/absolute/resolved/python", "fallback_seconds":600}
```

The supplied service-config pin and review pins are the trust root and must be provisioned by a trusted operator; hashing an unreviewed file does not make it trusted. Protect the state directory, policy, socket parent, config and reviews from untrusted writers. For a mutable control policy set `policy` to `{"path":"/absolute/policy.json"}`. All writers of that path must use the `policy-update` command below or acquire an exclusive `flock` on the stable sibling `<policy-path>.lock`, atomically replace and fsync the policy file and parent directory while holding that lock. Direct writes, including replacement without the lock, invalidate the concurrency guarantee. Missing, malformed or any dispatch value other than `allow` means HOLD. A legacy `{path,sha256}` policy remains supported as a fixed pin; a changed file is HOLD. The DAG journal binds the graph hash and refuses a different graph in the same state directory.

For a mutable pointer, update using the pinned service configuration and a complete local JSON policy source:

```
/absolute/resolved/python -B -P /absolute/repo/tools/unified_event_service_v1.py policy-update --config /absolute/service.json --sha256 <service-config-sha256> --policy-source /absolute/new-policy.json
```

The update and CPU admission take the same lock. Inside it, admission checks the current policy and durably records the complete allow snapshot, its canonical digest, graph, action, node and intent token before spawning. Recovery checks that snapshot without reopening the mutable policy. An intent denied under HOLD has no authorization and cannot recover. The private state directory is the authority for authorization history; protect it from unauthorized modification. Version 1 authorizations without embedded snapshots fail closed and require a separately reviewed migration; do not rewrite existing records. The service source hash has changed, so new trusted graph and CPU review pins must be independently provisioned before use.

Graph policy must use 600 seconds. Registered adapter names are `unified_cpu_v1` and `unified_npu_v1`; their implementation pins must respectively name this service and `tools/unified_dag_adapter_v1.py`. DAG graph nodes, typed dependencies, action pins, priority and sources follow `experiment_dag.py`. NPU bindings and reviews follow `unified_dag_adapter_v1.py`. The trusted review pins must include each used review.

A CPU node binding has exactly `{"schema":"unified-event-cpu-binding-v1","consumer_config":{"path":"/absolute/consumer.json","sha256":"<64 hex>"}}`. Its reviewed JSON has exactly `schema`, `decision`, `node`, `binding_sha256`, `components`; values are `unified-event-cpu-review-v1`, `accept`, the node id, DAG canonical digest of the binding, and `cpu_components()` from the service respectively. This pins repository modules in the CPU composition and the engineering schema; the interpreter and installed dependencies remain ambient and require separate provenance control. The consumer config follows `unified_cpu_consumer_v1.py`; its controller must equal `<state_dir>/cpu-controller`, and its slots must equal the DAG `cpu_slots`. All CPU work sharing capacity must use this controller. Its image, stage, paths and event ancestry are checked by the consumer. No arbitrary executable or command is accepted in the configuration.

## Operation and recovery

Run the service using a durable external supervisor and private persistent storage:

```
/absolute/resolved/python -B -P /absolute/repo/tools/unified_event_service_v1.py serve --config /absolute/service.json --sha256 <service-config-sha256>
```

Send an advisory wake after publishing a durable event: use the same invocation with `wake` in place of `serve`, or send any datagram to the protected Unix socket. Wake contents have no authority; repeated or missed events are harmless to the DAG intent journal. The service runs one initial iteration, then blocks for a datagram or 600 seconds. It holds a single-writer lock. It records the DAG state and heartbeat under `state_dir`; consumer workers are detached and use `workers/<node>/worker.log`, `TERMINAL.json`, `RELAUNCH.json`, and an inherited lifetime lock. The relaunch argv reacquires the worker lock before spawning and requires durable authorization. The consumer records its slot, container identity and receipts, but does not persist full container logs. A worker exception is recorded as uncertain and requires investigation. Previously authorized v2 workers can recover under HOLD even if the original policy is overwritten; a denied intent is not authority. A failure before terminal publication is not proof that no container exists.

The worker terminal records physical consumer exit only when an ACK is returned. The service checks the pinned action, authorization, owner, binding, terminal and ACK before supplying a `success` fact for exit zero. This does not establish numerical equivalence, artifact validity or scientific admission. Uncertain failures hold their DAG CPU slot pending reconciliation. A hard crash after a side effect is recovered through the consumer's own durable identity and retained container; a consumer exception terminal requires operator diagnosis and a reviewed recovery procedure. The service can be run with the local durable supervisor described below.

## Production boundary

The executable has no physical snapshot provider. Its default snapshot marks all eight devices unknown; therefore NPU dispatch cannot occur through `serve`. `iteration` exposes a code-injected provider seam for integration tests or a separately reviewed composition; it accepts a DAG snapshot, requires `adapter_observations`, a current epoch `as_of` and no more than five seconds elapsed before dispatch, and the NPU host performs its own lease checks. The seam is not selectable from configuration and must not be exposed to an untrusted caller. Before production, implement and review a provider that authenticates live allocation and container/device observations, establishes ownership of external/frozen tasks, freshness, clock behavior and synchronization with the physical lease authority; prove crash/restart behavior and event publishing at the actual host. The five-second check alone is not proof of an observation's truth. HOLD can change concurrently after a service check; the NPU host's own lock-held admission is authoritative. CPU synchronization relies on the cooperative writer protocol above and requires independent review before activation.

The service does not discover or consume unconfigured historical handoffs: graph nodes and pinned CPU configs must already describe them. A score node whose config depends on a future export receipt needs a separately reviewed configuration-generation and graph-version workflow; this service does not invent that provenance. Provisioning, end-to-end production recovery, real Docker and NPU qualification, and independent release review remain integration work.

## Local durable supervisor

`tools/unified_service_supervisor_v1.py` provides a Linux same-host supervisor. Provision a private persistent directory and a trusted, absolute, resolved JSON config with exactly these keys:

```json
{"schema":"unified-service-supervisor-v1","service":"unified_event_service_v1","entry":{"path":"/absolute/repo/tools/unified_event_service_v1.py","sha256":"<sha256>"},"python":{"path":"/absolute/resolved/python","sha256":"<sha256>"},"service_config":{"path":"/absolute/service.json","sha256":"<sha256>"},"supervisor":{"path":"/absolute/repo/tools/unified_service_supervisor_v1.py","sha256":"<sha256>"},"state_dir":"/absolute/private-supervisor-state"}
```

The `entry` is checked against the supervisor's fixed registry and the argument list is fixed to `serve --config ... --sha256 ...`; the config cannot supply a command. A synthetic registered entry exists solely for local functional tests. Hashes are operator-provisioned trust roots, not evidence of review or a complete dependency closure. Protect the config, pinned files and state directory against unauthorized writers. The service and its own pinned dependencies retain their existing authorization requirements.

Start with `/absolute/resolved/python -B -P /absolute/repo/tools/unified_service_supervisor_v1.py start --config /absolute/supervisor.json --sha256 <config-sha256>`. It returns after launching a detached monitor, with a single-owner lock. The state directory contains an executable `relaunch.sh` with the exact resolved invocation; running it in a clean process reacquires ownership and revalidates pins. The monitor revalidates before launching attempts. The attempt runner survives monitor death, retains its lifetime lock, and publishes its actual child exit before releasing that lock. After monitor death, run `relaunch.sh` to resume monitoring; a confirmed nonzero exit causes a new numbered attempt, while confirmed zero ends supervision. Attempt directories preserve separate appended stdout and stderr, process identities and generation-specific terminal records. `heartbeat.json` records monitor liveness; `status.json` records completion or a blocked/unconfirmed outcome. An absent terminal after the runner loses its lock is unconfirmed and stops recovery: investigate the retained process and side effects before any new start. The identity helper checks boot ID and Linux process starttime, and uses a pidfd before signaling; it refuses mismatches. Neither a stale root terminal nor a prior generation's terminal confirms a later attempt.

This supervisor does not automatically launch after host reboot; arrange for the exact relaunch script to be run by the host's startup facility. Its guarantees require local filesystem `flock`, atomic rename and durable fsync semantics, a trusted private state directory, and Linux `/proc` and pidfd support for identity-safe signaling.
