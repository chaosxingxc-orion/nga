# Stable configuration-driven engineering base

Status: engineering requirement and partially implemented migration, 2026-11-03. The native single-card configuration, runtime and lifecycle components have passed the v3 component review; final dispatch binding and actual NPU validation remain separate gates. This document records the owner's requirement that experiment changes enter through configuration and the core follows dependency inversion. It does not amend frozen metrics, numerical protocols, or running experiments.

The stable core owns task state, dependencies, lifecycle, item persistence, resume, logs, monitoring and result handoff. It depends on interfaces for data, prediction, validation, resource execution and scoring. Concrete implementations depend on those interfaces; the core must not select behavior by model names, dataset paths, chip numbers or experiment-specific branches. Configuration selects registered adapter identifiers and compatible versions. Arbitrary configuration strings are not executable code.

## Configuration boundary

A versioned experiment configuration declares these groups. This table is the target boundary across the engineering base, not a claim that one production schema already supports every group. The current narrow native schemas are `native-experiment-config-v1`, `native-capability-registry-v1` and `native-config-execution-v1`.

| Group | Configuration inputs | Core validation |
| --- | --- | --- |
| Identity | schema version, run ID, immutable configuration digest | known schema, exact types, unknown fields rejected |
| Sources | model manifest, input population and split, protocol contract | source hashes and compatible adapter versions |
| Adapters | predictor, arithmetic validator, data reader, scorer and executor registry identifiers | approved identifier/version; fixed dependency closure |
| Numerical protocol | dtype, batching, padding, length limit, readout mode, registered tolerances | protocol consistency; no retrospective changes |
| Resources | device count, allocation policy and shard assignments | resource transaction confirms ownership, release and applicable queue precedence under the allocation lock |
| Dependencies | predecessors and required terminal/artifact references | exact generation; missing or failed predecessor cannot become success |
| Outputs | output root, item storage and report destinations | isolated generation, single writer, retained failed attempts |
| Operations | attempt/resume policy, log fields, monitor interval | safe bounds; current approximately 600-second policy retained |

A new model, task, dataset, resource assignment or monitoring registration within existing capabilities changes only versioned configuration and its pinned registry/manifests. Configuration is validated before work or reservation starts; unknown identifiers, incompatible protocols and unsupported values fail explicitly. A configuration change creates a new immutable run identity or an explicitly compatible resume attempt, not an edit to a live experiment. New capabilities require an adapter or a versioned interface extension and contract tests; they do not require rewriting the generic launcher. Configuration cannot authorize numerical or scientific acceptance merely by setting a boolean.

The user's idle-device/no-ready-queue condition governs opportunistic new multicard tasks. It is not a global-empty-queue prerequisite for an already authorized single-card successor. That successor must still prove its exact predecessor's release, current device ownership and applicable priority reservations under the resource transaction. Other devices' queued work must remain intact. The current v1 registry field `requires_idle_and_no_ready_queue` must not be read as evidence that the entire cluster queue is empty; actual admission is a separately bound resource policy.

## Stable interfaces and composition

The composition root validates the configuration, resolves adapter identifiers, verifies implementation/source hashes, and injects adapter objects into the core. It must verify the complete executable dependency closure before claiming devices. The current shard core already accepts `predictor(request)`, `validator(prediction, request, binding)` and `metadata()` callbacks; these are dependency seams, not authenticated production adapters. Its `run_shard` API alone does not establish the callback implementation identity, model loading, device ownership or actual arithmetic equivalence.

A production adapter should provide preparation/readiness, one-item prediction, arithmetic validation, metadata and cleanup. A resource executor supplies claim/start/terminal/release operations. A scorer consumes immutable committed records only after required lifecycle checks. Data adapters preserve registered population identity and global ordinals. Monitoring consumes declared artifact paths and schemas independently of model implementations. The composition root owns adaptation and binding; the core does not import a concrete model to decide how an experiment should execute.

## Implemented boundary and evidence

The committed native configuration implementation (`ba970ab`) separates contract validation, runtime composition, detached host lifecycle and resource admission into `tools/bev_native_config_contract.py`, `bev_native_config_runtime.py`, `bev_native_config_host.py` and `bev_native_config_resource.py`. Model identity, chip, input requests, output and source references come from configuration/registry. The runtime currently resolves a fixed registered full-label fp32, HF32-off, batch-one adapter combination; it is not a universal plugin loader or a complete migration of all experiments.

The v3 independent component review passed 13 tests and 21 additional probes. These cover configuration and registry rejection, source/plan binding, exact host terminal types and identity, and compatibility with a real runtime-generated terminal using substituted model calls. The two committed test modules include configuration-only model selection and configuration-generated command changes. They prove the tested component seam, not actual model equivalence or NPU performance. The precise review verdict is `PASS_REPAIRED_COMPONENTS_PENDING_DISPATCH_BINDING_AND_PREFLIGHT`; its report is retained locally as `.local/reports/native-config-v3-independent-current.md` with pinned evidence in the JSON companion.

The v4 exact-predecessor admission policy has separate independent dispatch acceptance for its exact single-card attempt; it is not covered by the v3 acceptance. Its final-package target-image CPU preflight completed with exit 0 in a retained container without devices. The 19 component tests and 16 independent rejection probes passed. Actual long-input inference and lifecycle verification remain necessary. This document grants none of those acceptances. The earlier target-image v2 CPU preflight remains historical evidence; the v4 preflight is bound to plan SHA-256 `d107c91ba0ee97326a025f2681833a911db1040196387ab5033ea64e4222b516`.

## Current gaps and ordered migration

| Existing implementation | Gap | Migration and acceptance check |
| --- | --- | --- |
| `bev_native_panel_runner.py` | Explicit model family names, selected chip numbers, count 46320, length 8192 and two scope branches | Keep frozen copies intact. Move constraints to registered protocol/data/resource adapters and validated configuration. Demonstrate a second existing-capability cell with configuration-only changes. |
| `bev_native_shard_runner.py` | Concrete parent native schema, two-shard range, population module import and length bound | CPU component remains narrowly scoped. Introduce a population contract interface and explicit protocol adapter before broader task reuse; never silently widen the current accepted contract. |
| Shard predictor/validator callbacks | Caller-owned code is not pinned by the core | Composition root binds registry IDs, code hashes and model manifest; reject mismatched predictor/validator/protocol combinations before reservation. |
| Configured single-card host lifecycle | Component review passed; final resource admission, actual NPU forward and lifecycle acceptance remain | Complete the exact configured successor's admission and target-image preflight, then verify real retained-container execution and release. Do not migrate frozen running copies. |
| Multi-card host lifecycle | New multi-card claim, partial launch, retained containers and release integration absent | Implement one reusable executor with configuration-generated commands and per-shard states; test partial launch and recovery without duplicate computation. |
| Monitoring | Registry is configuration driven, with explicit legacy heartbeat adapter and fixed operational constraints | Retain declared roots/schema adapters and log cursor state; unknown schemas fail visibly. A new task registers configuration, not an ad hoc polling agent. |
| Resume | Handled exceptions produce EXIT and allow next-attempt committed-item reuse | Abrupt death without EXIT still requires host reconciliation. Torn item records are rejected, not automatically repaired or overwritten. |

Functional acceptance comes first: startup rejection must produce a log and terminal once a safe output directory and writer lock exist; exact identity and false authority scope must survive retries; committed records must preserve original ordinals; scientific acceptance remains external. Invalid output paths, existing attempts and contention cannot safely receive a new terminal at the contested location and must be reported by the host launch envelope.

Only after these interfaces and behaviors pass should throughput, batching, cache strategy or concurrent scheduling be optimized under a fixed representative load. Required numerical equivalence and unchanged metric definitions remain independent conditions. No new NPU execution or multi-card launch is authorized by this document.

## Acceptance and change discipline

1. For an existing capability, add a second model/task configuration and demonstrate the same launcher and adapter source hashes. Validate configuration changes, input order, source identities and output isolation before reservation. A new capability instead supplies an explicit adapter/interface version and compatibility tests.
2. Lock functional behavior first: strict validation, deterministic readout/scoring contracts, detached retained execution, durable logs and terminal markers, exact claim/release, item-level resume and asynchronous CPU result handoff. Successful startup alone is not acceptance.
3. Optimize nonfunctional behavior against that baseline: device utilization and queue handoff delay, per-chip throughput with chip count and reserved memory, restart recovery, monitoring cost and failure visibility. Ordinary monitoring remains script driven, reading logs as well as heartbeats and terminal/report artifacts at approximately 600-second intervals or explicit events.
4. Preserve the registered numerical protocol, population, split, metric definitions and thresholds. A speed-only change must pass the applicable numerical-equivalence checks. A changed scientific protocol needs a prospective amendment; an old result is never silently relabeled.
5. Promote a reviewed configuration/adapter version prospectively. Keep active runs and their executable dependency closures frozen. Record reproducible commands and immutable evidence; retain failed attempts for diagnosis. Latest conclusions may summarize these checks, but process logs remain local/Ceph evidence.

NPU queue execution and CPU review/analysis must remain asynchronous. A completed result can await independent acceptance while the next already admitted experiment runs; an analysis task must not hold a released device. Only a concrete dependency, failed admission or explicit experimental gate should block its successor.
