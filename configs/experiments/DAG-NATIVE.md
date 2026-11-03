# Native guarded-host DAG composition

This narrow adapter composes the accepted experiment_dag.py policy with existing immutable native long-DEV and full-label-panel launchers. It does not implement a generic shell action, replace external formal queues, or confer scientific admission.

## Configuration and trust boundary

- experiment_dag_native.py registers two capabilities: native_long_dev_v1 (native-config-execution-v1) and native_panel_v2 (native-panel-execution-v2). Service configuration pins the adapter, planner, service itself and allowed frozen host implementation hashes.
- A binding pins an exact plan and review, attempt, model-manifest hash, ordered-input hash, protocol, host interpreter and restricted host environment. Node split and chip must match. The action binding itself must equal the pinned binding, and the reviewed Docker command must equal the frozen host's generated command.
- Admission verifies module hashes and accepted manifest membership without re-hashing model weights at every tick. Actual launch passes through the existing host; full closure validation, predecessor checks, pending-priority guard, live hardware checks and the allocation transaction remain authoritative. The DAG adapter never writes allocation ownership.
- Source hashes and review JSON are integrity/scope bindings within the repository's trusted operator workflow, not cryptographic proof of external review authority. Production activation needs independent review of the exact composition.
- Unknown workloads require a new reviewed adapter version. Additional tasks of the supported two kinds use configuration and bindings; frozen execution code is not rewritten.

## Service operations

Invocation: python3 -B -P tools/experiment_dag_native_service.py OP --config /absolute/SERVICE-CONFIG.json --sha256 SHA256

| Operation | Effect |
|---|---|
| dry-run | Validates pinned files and binding commands; no Docker query, resource query, output directory creation or launch. |
| once | On the configured physical host, reads allocation under its lock and retained runtime receipts, writes snapshot/plan/heartbeat; never launches, even with dispatch configuration. |
| start | On the physical host, starts one detached service with inherited exclusive lock, exact configuration identity, PID/boot/start-ticks, durable log and relaunch record. |
| restart | Explicitly reconciles a prior service of the same configuration: old PID/boot/start-ticks must no longer be live, then old SERVICE/EXIT are archived and a new detached service starts. Existing controller intents are retained. |
| watch | Internal operation requiring inherited lock. Re-verifies configuration each 600 seconds; dispatch occurs only in explicit dispatch mode with exact activation receipt. |

Plan mode requires activation null. Dispatch mode requires a pinned nga-native-dag-activation-v1 receipt containing PASS, activation_authorized true, scientific_acceptance false, canonical graph hash, exact modules/capabilities/host/allocation/output and the complete managed action map. Changed graphs cannot resume the old dispatch journal. A new graph/service output needs explicit reconciliation of existing owners. A start against an existing SERVICE identity refuses; RELAUNCH.json records the explicit restart command.

The supplied actual-package example is plan only, with 9B panel v6 and 0.8B configuration-reuse attempt1 both marked external_frozen. Both may be observed; neither can be started by this service. Dry-run state is deliberately not live NPU status. Do not change these nodes to DAG ownership merely to enlarge a queue count.

## Dependency and concurrency semantics

The planner preserves typed resource_release, artifact, numerical_equivalence, scientific_admission, and success edges. This adapter emits only authenticated operational resource_release and success; a failed released run emits release plus failed success. Physical release is independent of runtime validity: crashed or malformed result terminals retain authenticated release, while success stays absent or failed. Completion never implies numerical equivalence or scientific admission.

This composition accepts NPU nodes only. The existing full-panel native host performs asynchronous CPU handoff after durable release; CPU scoring does not hold the NPU queue. The existing tier-0 watchdog continues reading logs, heartbeats, terminal markers and reports. This controller adds no agent polling or raw-log consumption.

Running, uncertain and unreleased work reserves its declared devices. Missing receipts, incomplete physical release proof, changed retained runtime identity, uncertain launch, and observation failures all block device reuse. Independent chips remain eligible. Dispatch writes intent before effect and never blindly retries an uncertain start. Launches invoke a fixed native-host Python entrypoint in a detached envelope; arbitrary command text is not accepted from configuration.

## Add a future task

1. Prepare and freeze a native package with the existing builder/protocol; obtain exact package execution review and document the pre-run experiment.
2. Write immutable binding, graph node and typed dependencies. Pin actual model/input/protocol/device identities. Use external_frozen for work owned by another service.
3. Run dry-run, compare commands with package review, and verify meaningful tests. Independently review the new composition and action map.
4. For activation, create an independently approved dispatch configuration/receipt on the physical host. Start once. Retain output and let the script run at 600-second cadence; intervene on flagged digests.

Pending proposals, unavailable adapters and absent review receipts remain blocked. Reserve depth is not executable depth. This two-kind adapter does not make the entire 45-node research graph runnable.
