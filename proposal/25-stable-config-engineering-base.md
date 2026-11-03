# Stable configuration-driven engineering base

Status: prospective interface and migration plan, 2026-11-03. This document records the owner's requirement that experiment changes enter through configuration and the core follows dependency inversion. It does not amend frozen metrics, numerical protocols, or running experiments.

The stable core owns task state, dependencies, lifecycle, item persistence, resume, logs, monitoring and result handoff. It depends on interfaces for data, prediction, validation, resource execution and scoring. Concrete implementations depend on those interfaces; the core must not select behavior by model names, dataset paths, chip numbers or experiment-specific branches. Configuration selects registered adapter identifiers and compatible versions. Arbitrary configuration strings are not executable code.

## Configuration boundary

A versioned experiment configuration declares these groups; the following is an interface proposal, not an implemented production schema:

| Group | Configuration inputs | Core validation |
| --- | --- | --- |
| Identity | schema version, run ID, immutable configuration digest | known schema, exact types, unknown fields rejected |
| Sources | model manifest, input population and split, protocol contract | source hashes and compatible adapter versions |
| Adapters | predictor, arithmetic validator, data reader, scorer and executor registry identifiers | approved identifier/version; fixed dependency closure |
| Numerical protocol | dtype, batching, padding, length limit, readout mode, registered tolerances | protocol consistency; no retrospective changes |
| Resources | device count, allocation policy and shard assignments | resource transaction confirms idle devices and ready queue precedence |
| Dependencies | predecessors and required terminal/artifact references | exact generation; missing or failed predecessor cannot become success |
| Outputs | output root, item storage and report destinations | isolated generation, single writer, retained failed attempts |
| Operations | attempt/resume policy, log fields, monitor interval | safe bounds; current approximately 600-second policy retained |

A new model×dataset cell within existing capabilities changes only configuration. New capabilities require an adapter or a versioned interface extension and contract tests; they do not require rewriting the generic launcher. Configuration cannot authorize numerical or scientific acceptance merely by setting a boolean.

## Stable interfaces and composition

The composition root validates the configuration, resolves adapter identifiers, verifies implementation/source hashes, and injects adapter objects into the core. It must verify the complete executable dependency closure before claiming devices. The current shard core already accepts `predictor(request)`, `validator(prediction, request, binding)` and `metadata()` callbacks; these are dependency seams, not authenticated production adapters. Its `run_shard` API alone does not establish the callback implementation identity, model loading, device ownership or actual arithmetic equivalence.

A production adapter should provide preparation/readiness, one-item prediction, arithmetic validation, metadata and cleanup. A resource executor supplies claim/start/terminal/release operations. A scorer consumes immutable committed records only after required lifecycle checks. Data adapters preserve registered population identity and global ordinals. Monitoring consumes declared artifact paths and schemas independently of model implementations. The composition root owns adaptation and binding; the core does not import a concrete model to decide how an experiment should execute.

## Current gaps and ordered migration

| Existing implementation | Gap | Migration and acceptance check |
| --- | --- | --- |
| `bev_native_panel_runner.py` | Explicit model family names, selected chip numbers, count 46320, length 8192 and two scope branches | Keep frozen copies intact. Move constraints to registered protocol/data/resource adapters and validated configuration. Demonstrate a second existing-capability cell with configuration-only changes. |
| `bev_native_shard_runner.py` | Concrete parent native schema, two-shard range, population module import and length bound | CPU component remains narrowly scoped. Introduce a population contract interface and explicit protocol adapter before broader task reuse; never silently widen the current accepted contract. |
| Shard predictor/validator callbacks | Caller-owned code is not pinned by the core | Composition root binds registry IDs, code hashes and model manifest; reject mismatched predictor/validator/protocol combinations before reservation. |
| Host lifecycle | New multi-card claim, partial launch, retained containers and release integration absent | Implement one reusable executor with configuration-generated commands and per-shard states; test partial launch and recovery without duplicate computation. |
| Monitoring | Registry is configuration driven, with explicit legacy heartbeat adapter and fixed operational constraints | Retain declared roots/schema adapters and log cursor state; unknown schemas fail visibly. A new task registers configuration, not an ad hoc polling agent. |
| Resume | Handled exceptions produce EXIT and allow next-attempt committed-item reuse | Abrupt death without EXIT still requires host reconciliation. Torn item records are rejected, not automatically repaired or overwritten. |

Functional acceptance comes first: startup rejection must produce a log and terminal once a safe output directory and writer lock exist; exact identity and false authority scope must survive retries; committed records must preserve original ordinals; scientific acceptance remains external. Invalid output paths, existing attempts and contention cannot safely receive a new terminal at the contested location and must be reported by the host launch envelope.

Only after these interfaces and behaviors pass should throughput, batching, cache strategy or concurrent scheduling be optimized under a fixed representative load. Required numerical equivalence and unchanged metric definitions remain independent conditions. No new NPU execution or multi-card launch is authorized by this document.
