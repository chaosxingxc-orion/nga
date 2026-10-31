# Integrated NGA Review: Agent Evolution, Three States and Four Planes

> Date: 2026-10-30.
> Status: adversarial architecture review and proposed refinements, not an implemented architecture or closure of the AQ register.
> Established: agent evolution is the integrating whole; development/runtime/operations are three lifecycle states; user/runtime/management/control are four responsibility planes. Customer primitives are configurable, importable and extensible. The provider retains authoritative business execution.
> Basis: [V0.2](13-nga-architecture-v0.2.md), [prior adversarial review](14-v0-adversarial-review.md), [task and request identity](20-task-decision-request-identity.md), [extensible primitives and API contracts](21-runtime-primitives-and-capability-contracts.md), and [discussion register](16-architecture-discussion-register.md).

## 1. Assessment and interpretation of the dimensions

The organizing axes in V0.2 remain useful. Recent work makes runtime control more concrete: identity, waiting, retries, cancellation, compensation, Graph/Workflow composition and customer extensions. The remaining integration gap is how these capabilities become maintained agent behavior across authoring, publication, operation and improvement. A catalog of runtime nodes alone is not the complete NGA framework.

**Agent evolution is the integrating whole: coordinated improvement of maintained agent capabilities toward accountable business objectives.** Its change targets include semantic specifications, models/readouts, context policy, default/customer primitives, workflows, API adapters/contracts and interaction/control definitions. Different agents and customer scopes can have their own objectives and compatible versions; this does not require one enterprise-wide agent or one global policy.

**The three states describe kinds of work.** A candidate can be under development while a published release serves tasks and operators investigate earlier outcomes. They are neither three exclusive task statuses nor simply development/test/production environments.

**The four planes describe responsibilities in every state.** The runtime plane executes development evaluations and operational recovery as well as business tasks. The management plane maintains definitions; control determines effective admission/publication/transitions; user interaction expresses intent and presents outcomes. Planes need not be separate services, products or screens.

Evolution connects these responsibilities through attributable changes and observed outcomes. It is not a fifth privileged controller. Data, identity and audit requirements cross the four planes; they do not introduce a replacement fifth plane.

## 2. A common object lineage makes the whole concrete

The proposed backbone is:

**business objective and owning scope → maintained agent definition → compatible release manifest → task/decision/request history → observed outcome and reviewed case → candidate change and evaluation → admitted release or withdrawal.**

| Object | Required relationship across the dimensions |
| --- | --- |
| **Objective and semantic contract** | State intended business behavior, delegated judgment scope, completion promise and what a proposed improvement would preserve or intentionally change. Meaning has an accountable owner. |
| **Agent definition and capability catalog** | Reference models, semantics, context, primitives, Graph/Workflow definitions and API contracts. Distinguish platform defaults, industry packages and customer definitions/configuration by explicit namespace, ownership and dependency resolution. |
| **Release manifest** | Bind a compatible set of actual artifacts/configuration, qualification evidence, publication scope and treatment of active tasks. References can point to independently maintained components; this is not a monolithic deployment requirement. |
| **Task and execution history** | T1/J1/D1/B1, plans, child scopes, waits/timers, attempts, provider observations and recovery records point to the actual definitions consumed. |
| **Reviewed operational case** | Link a reported outcome to the relevant task/provider evidence and original release, with an attribution hypothesis, limitations and accountable handling. It is not automatically a training example. |
| **Candidate and evaluation** | State the proposed changed component, preserved obligations, expected distinction/improvement, comparison evidence and affected scopes. Promotion requires the applicable policy, which may be automatic. |

A shared lineage does not mean every model, user or customer can read every record. Views and contextual inputs remain scoped. If required history or provider evidence is unavailable, preserve the declared audit/replay limitation rather than fill it with generated explanations.

## 3. Review all twelve responsibility cells

Each cell below has an observable output, not just a feature label.

| Plane | Development state | Runtime state | Operations state |
| --- | --- | --- | --- |
| **User** | Experts/developers express goals, author examples, configure/import controls and inspect simulations → attributable requirements and review requests. | Callers initiate/resume tasks, provide evidence and request supported interruption → authorized intent and understandable task/decision/request status. | Owners/operators inspect outcomes, adoption, complaints and effort → reviewed feedback, recovery requests and improvement objectives. |
| **Runtime** | Execute model/semantic evaluations, extension conformance checks and workflow simulations → observations and qualification evidence under declared effect isolation. | Execute admitted Jev/S2, custom primitives, Graphs/Workflows/Loops and API waits/recovery → actual task transitions, model outputs and provider receipts. | Execute authorized diagnosis, replay, reevaluation and recovery → attributed findings or confirmed/partial recovery outcomes. |
| **Management** | Maintain namespaced artifacts, semantic definitions, package dependencies and candidate manifests → reproducible candidate sets. | Resolve published definitions and actual configuration for the admitted scope → a pinned dependency view, not a moving latest-version lookup. | Maintain case collections, owners, retained artifacts, compatibility and rollout/retirement declarations → evidence-backed lifecycle proposals. |
| **Control** | Admit evaluation jobs and candidate activation under authority, compatibility and effect policies → explicit allowed/rejected/held publication or evaluation outcomes. | Admit tasks/decisions/effects, enforce identities and authority, arbitrate waits/interruption → effective NGA state and accountable recovery ownership. | Admit operator interventions, promotion/withdrawal and active-task migration → attributable changes without replaying external effects or erasing history. |

Business operations includes whether users can complete useful work, understand results, resolve exceptions and obtain the intended outcomes. Infrastructure uptime and token cost alone do not establish that an agent is useful. Define workload-specific outcome and quality targets before comparing releases; this review selects no numerical target or new research protocol.

## 4. Four-plane ownership and the business-system boundary

| Item | Definition/evidence owner | Effective authority and execution boundary |
| --- | --- | --- |
| Business meaning and delegated question | Accountable business/knowledge owner through user and management capabilities. | Publication/adoption follows control policy; models apply admitted meaning rather than publishing their own conventions. |
| Primitive or Workflow package | Management maintains source, versions, dependencies and qualification evidence. | Control admits scope/version activation; runtime executes the bound implementation, including customer extensions. |
| Task, decision and request eligibility | Runtime supplies observations/proposals; user plane submits commands. | One authoritative NGA transition contract per governed object. Read views or catalog declarations cannot independently make that change effective. |
| External business outcome | Provider supplies authoritative receipts/status under its public capability contract. | NGA records/uses that result; it does not become the provider's transaction or domain-rule engine. |
| Promotion, migration or retirement | Management maintains the proposed release/change and evidence. | Control admits the change; management's published view and runtime routing reflect that same attributable transition. |
| Operational case and proposed improvement | User/operations contributors supply feedback; runtime supplies actual traces; management preserves the case. | Live recovery, evaluation and reusable publication each use their applicable authority; none follows automatically from a model-generated diagnosis. |

This is logical ownership, not a demand for a central service on every model token or local calculation. Work can execute inside an admitted scope, with its required effect and transition boundaries enforced. Distributed implementation is possible if the authoritative object contracts and evidence remain coherent.

Configurable control policies and custom handlers can participate in these contracts. Extensibility does not mean each package creates an independent authoritative task state or edits a provider's fields to simulate a missing capability. Conversely, the kernel must not hardcode every industry predicate or require all customer states to fit six built-in node types.

## 5. Adversarial findings and refinements

These findings concern document gaps or likely misreadings, not demonstrated implementation defects. Existing principles that already address a risk must be preserved and made concrete rather than claimed as absent.

| ID | Finding and counterexample | Refinement |
| --- | --- | --- |
| A01 | **Runtime detail outruns lifecycle integration.** A customer can import a node but cannot connect its qualification, production tasks and later upgrade to the same maintained agent. V0.2 states lineage; document 21 elaborates execution more deeply. | Make the object chain in section 2 the common cross-state contract. Qualification and operational impact belong to the imported package's lifecycle, not an unrelated plugin screen. |
| A02 | **Plane names can become product silos.** A development evaluation has no control boundary because control is implemented only in the production console. | Exercise all four planes in each lifecycle state. User-plane functionality includes programmatic calls; authorization is not determined by the screen used. |
| A03 | **Management and control can both claim publication authority.** A catalog marks E2 active while runtime still executes E1 and another console reports E2 as effective. | Use one admitted activation record with scope/version applicability. Catalog, routing and user views reflect that record; they do not create independent meanings of published. |
| A04 | **Extensibility can be either cosmetic or an escape hatch.** A new industry state is rejected because it is not one of the defaults, or a custom handler bypasses all effect history. | Permit qualified custom semantics and implementations under the shared kernel contract. Explicitly resolve namespaces, dependency versions, invocation scope and actual enforcement/replay coverage. |
| A05 | **Evolution can mean automatic promotion of anecdotes.** A complaint about a valid refusal becomes a positive approval label, or a timeout display bug triggers model retraining. | Separate operational observations, reviewed attribution and qualified improvement candidates. Preserve unknown/delayed outcomes and distinguish semantic, model, context, workflow, primitive, integration and interaction defects. |
| A06 | **Control can be misread as a synchronous bottleneck for every step.** Every token or harmless calculation requires a global round trip, while customer handlers maintain their own competing truth. | Retain one logical authority per governed object and bounded admitted execution. Decide physical scheduling and enforcement placement later; do not equate logical control with one universal service. |
| A07 | **Immediate recovery and reusable evolution can be conflated.** A task-specific resume changes the published workflow, or fixing a reusable defect is treated as an untracked local patch. | Keep the two paths in section 6 separate but linked. Existing-authority recovery can proceed without waiting for a new release; lasting behavior changes need candidate/evaluation/publication lineage. |
| A08 | **An upgrade can invalidate the evidence needed to judge it.** E2 replaces the calendar/checkpoint semantics of a suspended E1 task; replay under E2 is labeled reproduction of E1. | Bind implementation/configuration/artifacts per invocation. Distinguish historical replay from candidate reevaluation; apply explicit pin/migrate/hold/retire handling and retain declared recovery/replay dependencies. |

The review therefore does not replace the organizing axes. It strengthens their shared objects, handoffs and acceptance evidence.

## 6. Two related paths through the integrating whole

### 6.1 Operational recovery of an existing task

**Observed issue → authorized diagnosis/status inquiry → admitted resume/cancel/compensate/handoff → recorded task/provider outcome.**

This uses existing qualified capabilities and may include a bounded S2 investigation or a delegated Jev judgment. It is operational work executed through runtime capabilities under control policy. It does not necessarily change the maintained agent definition or require a new release. A repeated recovery request retains its operation identity.

### 6.2 Reusable improvement of the agent

**Observed outcome or new business objective → reviewed case/hypothesis → candidate artifact change → isolated evaluation → admitted publication/rollout → observed outcomes.**

| Attributed problem | Candidate change to consider; not an automatic diagnosis |
| --- | --- |
| A semantic term or boundary is undefined | Knowledge/semantic specification and examples, with intended meaning change explicit. |
| A model violates a well-defined judgment contract | Model/readout/task/data work under the existing research process. |
| Evidence is incomplete or incorrectly bound | Source adapter, context/coverage policy or evidence-collection workflow. |
| A wait resets its deadline or loses a callback | Primitive implementation, state binding or execution integration. |
| An accepted API request is shown as approved | API status mapping and/or user-facing state presentation. |
| A business process cannot recover using the exposed APIs | Capability contract or qualified recovery composition; possibly an external-system integration request, not an invented model guarantee. |
| A sound procedure is repeatedly rediscovered by S2 | Candidate reusable Workflow/primitive with applicability and counterexample evaluation. |

The actual evidence must support attribution. Changing business meaning is distinguishable from improving adherence to unchanged meaning. Historical replay can reproduce a defect faithfully; candidate reevaluation may legitimately diverge to correct it. These are different evaluation purposes.

Automatic promotion is permitted under a declared policy and evidence contract. The integrating whole does not give S2 or Jev standing authority to publish model, semantic, primitive or permission changes. The three repository projects remain connected: operations informs model tasks in project 1, execution/composition changes in project 2 and semantic/workbench improvements in project 3. Registered experiments still require their normal amendment process.

## 7. Proposed cross-plane handoffs

These are logical exchanges, not a final network API:

| Handoff | Required inputs → observable result |
| --- | --- |
| **RegisterCandidate** | Namespaced artifacts/configuration, owner, scope and dependencies → candidate identity and unresolved qualification requirements; no implicit live activation. |
| **EvaluateCandidate** | Candidate, fixture/comparison definition, data/effect scope and authority → actual evaluation observations, limits and attributable verdict evidence. |
| **ActivateRelease** | Qualified manifest, applicable policy, rollout scope and active-task treatment → one effective activation/rejection/hold record consumed by registry and execution views. |
| **StartOrResumeTask** | Authorized intent/reference, target and completion scope → T1 bound to applicable definitions or an explicit identity/scope conflict. |
| **AdmitAndObserveWork** | Current revision, model/work proposal or recorded event, dependencies and authority → effective transition or conflict; external effects still use the capability contract. |
| **OperateTask** | Identified task/request, requested action, authority and qualified recovery procedure → an attributable recovery invocation, known outcome or owned unresolved state. |
| **RecordCaseAndProposeChange** | Feedback/outcome, actual release and trace references, attribution hypothesis and limitations → reviewed case/candidate lineage, not an automatic training label or release. |

Compatibility, authority and declared business acceptance are separate admission questions. A syntactically valid package is not necessarily behaviorally compatible; a compatible package is not automatically an improvement; a useful candidate is not automatically authorized for every customer scope.

## 8. Credit fixture through the complete structure

### Development

The business owner defines the delegated eligibility/amount question and task completion promise. Developers configure the evidence route, Jev contract, application Workflow and provider capability, and import a customer waiting primitive E1 if the fixture needs it. The management plane records compatible definitions in release L1. Runtime executes isolated fixtures; control governs evaluation effects and activation. The user plane exposes the definitions and actual evidence for review.

The business-system internals remain outside this fixture. E1 can have customer-specific timing semantics without transferring authority over credit records to NGA.

### Runtime

T1 resolves L1 and its actual model/semantic/primitive/API dependencies. Jev supplies the admitted judgment, the framework adopts D1, and B1 invokes the provider. The normal path waits for the declared result. User views distinguish the local judgment, provider outcome and any recovery status.

Importing E2 during the wait creates a candidate or a newly scoped release according to policy; it does not silently rebind T1. Explicit migration, current permission checks and interruption policies remain available when required. Graph, Workflow and Agent Loop implementations preserve the same task/request and extension contracts.

### Operations and evolution

Suppose an operator finds that a resumed wait has an unexpectedly extended deadline. Review the recorded timer, E1 configuration and resume events before attributing the problem. If the evidence identifies an extension/restart defect, the candidate targets that component; the case does not automatically become Jev training data.

An authorized operational path handles T1 and B1 using their actual status. In parallel, development qualifies E2. Historical replay of L1/E1 preserves the original behavior; isolated reevaluation of E2 checks the proposed correction and counterexamples. Publication can route new tasks to L2 while active L1 tasks follow the explicit policy. Retiring L1 does not undo a provider effect or erase the artifacts required for retained replay.

This is one evolution path crossing all twelve cells, with immediate recovery and lasting improvement separately identifiable.

## 9. Cross-dimensional acceptance cases

These are proposed design checks, not executed tests. Each includes a valid-progress counterpart; blocking all work or refusing all decisions cannot pass.

| ID | Primary cell | Adversarial case and expected distinction |
| --- | --- | --- |
| D01 | Development / user | An expert's ambiguous draft cannot silently become effective policy; a complete authorized definition can enter qualification. |
| D02 | Development / runtime | A candidate evaluation cannot send live business effects under replay credentials; explicitly admitted integration tests have their own scoped execution contract. |
| D03 | Development / management | Two customer packages share a display name; namespace/dependency resolution preserves the intended definition without blocking legitimate reuse. |
| D04 | Development / control | Import alone cannot activate privileged behavior; a qualifying candidate can be automatically published under the existing policy. |
| D05 | Runtime / user | The UI must distinguish accepted from approved and local stop from confirmed cancellation; it can still expose a supported cancel request. |
| D06 | Runtime / runtime | A worker or child restart resumes T1/B1 and the original wait; it cannot create a fresh submission or reset its total deadline. |
| D07 | Runtime / management | A new package appears in the catalog during a suspended task; retain the actual binding or apply declared migration instead of resolving latest on wake. |
| D08 | Runtime / control | Hold, callback and dispatch races have one effective local transition per scope/generation while preserving actual provider observations and recovery obligations. |
| D09 | Operations / user | A complaint about a valid refusal is recorded as feedback, not automatically an approval label; evidence of a real defect can initiate a qualified change. |
| D10 | Operations / runtime | Replay uses historical artifacts/events without live dispatch; separately authorized recovery can perform a supported business operation. |
| D11 | Operations / management | A retirement request cannot delete artifacts needed by active tasks or promised replay without explicit treatment; unused versions can still be retired under policy. |
| D12 | Operations / control | Withdrawing a release changes admitted routing/migration, not a completed business effect; a separately authorized compensation remains possible when supported. |

The counts are a coverage aid, not proof that one test per cell establishes correctness. Combine these cases with the execution and extension cases in document 21 and identity cases in document 20.

## 10. Priorities and remaining choices

Proposed next design order:

1. Specify the shared agent/candidate/release/task/case references and the seven handoffs above, including scoped package resolution and active-task treatment.
2. Walk one imported/custom primitive through development qualification, normal waiting/recovery, operational diagnosis and compatible upgrade using the credit fixture.
3. Define the smallest workbench experience that exposes those same objects and real statuses across all states, without making twelve unrelated screens or services.
4. Use the resulting business and framework evidence to choose meaningful Jev/S2 placements and runtime implementation options.

Remaining discussions include the authority owners for publication/intervention, version/namespace composition policy, migration/retirement and recovery ownership, supported audit/replay scope, and the evidence that qualifies an improvement. They extend AQ-08/AQ-11/AQ-14–AQ-18 rather than closing them.

No engine, host topology, programming language, storage, package format, mandatory human-approval process or model topology is selected. The source V0 snapshots remain unchanged; the refinement updates NGA's own integration design.
