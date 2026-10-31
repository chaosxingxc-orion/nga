# NGA — Overall Program Design

> Updated: 2026-10-31 (America/New_York).
> Role: program vision, project boundaries and established principles.
> Architecture source of truth: [07 — NGA Architecture and Minimum Java SDK Proposal](../achitecture%20design/07-nga-architecture-proposal.md). Detailed architecture and implementation scope are maintained there.
> Status: a research and engineering program; proposed SDK/runtime behavior is not an implemented or verified guarantee.

## 1. Purpose

**NGA means Next Generation Agent.** It addresses a central barrier to enterprise adoption: a generative agent may reconsider a consequential decision differently even when its material business basis has not changed.

The preceding agent-loop paradigm uses an agentic model for planning, acting, reflection and replanning. NGA develops an approach that combines Jev-like typed semantic decisions, generative reasoning and explicit framework control. Its objectives are consistent business decisions, idempotent repeated requests and effects, replayable/auditable execution and business-configurable behavior.

These properties require different evidence. A cache can preserve a repeated request without understanding a changed rule; a consistent model cannot prevent duplicate external writes; an event timeline cannot establish executable replay. Each obligation must be qualified independently while measuring useful outcomes.

## 2. Three connected projects

| Project | Responsibility | Main outputs |
| --- | --- | --- |
| **1. Decision-model research and engineering** | Translate business consistency/idempotence objectives into falsifiable tasks, synthesize data, reproduce relevant Jev engineering and develop a suitable model. | Tasks, semantic definitions for research fixtures, datasets/provenance, model/readout implementations and paired consistency/discrimination evaluations. |
| **2. S1 + S2 agent framework** | Combine available Jev capabilities with Agentic Models on openJiuwen while controlling decision adoption, requests, effects and continuation. | The Java SDK/adapter/Starter, execution contracts, credit reference application, recovery/replay and conformance evidence specified in the architecture proposal. |
| **3. Enterprise workbench and knowledge engineering** | Maintain business semantics and turn the framework into usable enterprise development, runtime and operations experiences. | Governed specifications, definitions/releases, authoring, task/case views, qualification, intervention and evolution workflows. Reuse existing openJiuwen/enterprise capabilities. |

These projects proceed together. Reproduction is a baseline within project 1, not NGA's final objective. Project 2 may use an assumed capable model or explicit test doubles while the research continues; those tests do not certify model readiness. Project 3 can begin with maintained specifications and programmatic lifecycle operations before a full graphical workbench exists.

Business semantic gray areas belong to explicit knowledge-engineering governance: definitions, units, time windows, boundaries, precedence, coverage and exception behavior. Decision execution must not silently let a model fill in missing conventions. Unknown/unresolved is distinct from refusal unless an authorized specification defines otherwise.

## 3. Established principles

The identifiers below retain their program-level meanings. Concrete implementation mechanisms are specified as proposals in document 07.

| ID | Principle |
| --- | --- |
| P1 | Three connected projects serve decision/business-result idempotence, traceability and useful enterprise outcomes. |
| P2 | Jev/S1 targets semantic consistency and business-configurable definition following; equivalent inputs and material distinctions both matter. |
| P3 | Semantic judgment, framework adoption and external execution are separate events with separate authority. |
| P4 | Published business meaning and current governance authority constrain both models; neither may grant itself permission. |
| P5 | Decisions retain the actual evidence, semantic, model, readout and decision-policy versions used. |
| P6 | Material adaptation creates explicit revisions and lineage rather than overwriting adopted history. |
| P7 | Semantic consistency, repeated-request idempotence and action idempotence are distinct obligations. |
| P8 | Evaluation excludes degenerate behavior: invariance requires discrimination and an accuracy/usefulness floor. |
| P9 | openJiuwen remains the engineering foundation; public Java Core/Runtime are the current integration reference. Specific compatible versions and supporting infrastructure require qualification. |
| P10 | Project 3 manages semantic specifications and gray areas through knowledge engineering; execution follows declared unresolved handling. |
| P11 | Preserve useful V0 contracts and original source history while correcting invalid assumptions. Original implementation claims do not become NGA evidence. |
| P12 | Decision chains require audit and executable control replay, including consequential work inside loops and workflows. |
| P13 | Development/runtime/operations states and user/runtime/management/control planes are integrated by agent evolution; they are not deployment environments or a required service topology. |
| P14 | Reuse existing components first; necessary custom work remains modular and pluggable through qualified contracts. |

## 4. Organizational and authority boundaries

**Agent evolution** connects business outcomes and reviewed cases to candidate changes, independent evaluation, authorized activation and subsequent observations. Improvement can affect semantics, evidence, models, prompts, workflows, primitives, integrations or interaction behavior. Immediate task recovery and reusable release improvement are separate paths.

The four planes distinguish intent/interaction, maintained artifacts, execution and effective control. Management owns definition and publication proposals; control admits scoped activation and consequential transitions; runtime supplies actual observations and performs admitted work; user views report that same state. They can coexist in one application.

NGA integrates with business capability APIs. Existing IT systems own their domain data, internal constraints and transaction outcomes. Jev may answer an explicitly delegated semantic question; it does not replicate hidden banking rules. Cancellation, retry and compensation depend on the actual provider contract.

The architecture proposal makes these boundaries concrete through agent definitions, immutable releases, scoped activations, tasks, decisions, business requests and operational cases. It also specifies the initial Spring Boot-driven Java SDK scope and its acceptance gate. This program overview does not maintain a second set of competing runtime contracts.

## 5. Research evidence and limitations

The [survey](../survey/README.md) and [PDF](../survey/nga-survey.pdf) analyze Jev-class research, defects and evidence. They do not determine NGA's business objectives or constitute a training recipe. The [research proposal](../proposal/00-research-proposal.md) and experiment protocols remain the sources for rounds, gates, tasks, metrics and amendments.

Model tasks must distinguish following supplied business definitions from memorizing labels, wording or generator structure. The existing typed-readout research vocabulary includes boolean, nominal and ordinal levels, exclusive or stackable candidate sets, and declared unknown handling. A particular model family, scorer or training experiment does not freeze the final architecture.

Reproducing a recipe, matching a benchmark and reproducing native typed readout remain different claims. Aggregate accuracy is not a substitute for paired decision-consistency evaluation. A model observation is not an adopted framework decision or confirmed business effect.

This documentation consolidation does not amend research protocols, reinterpret experimental results, select a production model or assert that the required Jev gates have passed. Consult the latest qualified experiment records for research readiness.

## 6. Delivery focus

The immediate architecture target is a small embeddable implementation: **NGA SDK + openJiuwen adapter + Spring Boot Starter + credit reference application + acceptance suite**. It must demonstrate useful decision handling, durable wait/recovery, no duplicate effects within qualified provider guarantees, audit and isolated executable replay.

A full workbench, marketplace, distributed control service and universal engine interoperability are not required for that first delivery. Their responsibilities remain represented by interfaces and lifecycle contracts. The [canonical proposal](../achitecture%20design/07-nga-architecture-proposal.md) defines scope, component boundaries, implementation sequence and the remaining decisions needed for qualification.

Original [V0 brief](../achitecture%20design/05-architecture-brief-and-decisions.md) and [V0 diagrams](../achitecture%20design/06-architecture-diagrams-md.md) are retained as contextual source inputs. Use the current proposal for collaborator review and implementation planning.

