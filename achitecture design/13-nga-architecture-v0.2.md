# NGA Architecture V0.2 — Three States, Four Planes, Agent Evolution

> Date: 2026-10-30.
> Established direction: development, runtime, and operations states; user, runtime, management, and control planes; agent evolution as the integrating whole across the four planes.
> Status: the organizing dimensions are owner-defined. The responsibilities, contracts, and evolution lifecycle below are proposed for review, not implemented guarantees.
> Supersedes the three-view organization in [V0.1](08-nga-architecture-v0.1.md). The [V0 adversarial review](14-v0-adversarial-review.md) explains corrections rather than treating all inherited mechanisms as commitments.
> Current integration review: [document 22](22-integrated-lifecycle-and-plane-review.md) applies these dimensions to extensible primitives, API waiting/recovery and the full customer lifecycle. It adds concrete object lineage, cross-plane handoffs and twelve acceptance cases without claiming the detailed architecture is complete.
> Engineering foundation: [document 24](24-openjiuwen-reuse-and-evolution.md) maps this design onto public openJiuwen Java Core/Runtime and existing workbench capabilities. openJiuwen and reuse-first, pluggable extension are established requirements; the mappings and migration stages remain proposals requiring qualification.

## 1. The dimensions have different meanings

**Three lifecycle states × four responsibility planes, connected through agent evolution**, is a multidimensional organization.

- **Development state:** define, build, configure, train, test, and evaluate agent capabilities and business behavior.
- **Runtime state:** carry out identified business tasks using admitted versions, evidence, authority, and execution contracts.
- **Operations state:** assess adoption, business outcomes, quality, cost, exceptions, and risk over time; investigate problems and govern improvement.

Operations means business operation and continuous improvement, not only infrastructure maintenance. These are activity/lifecycle views, not three mutually exclusive statuses of a task or simply three deployment environments. One agent can have a production release executing tasks, a candidate under development, and an operations team analyzing both at the same time.

The **four planes** assign responsibilities within each state. The runtime plane therefore also executes development evaluations and operational replays; it is not restricted to the runtime lifecycle state.

**Agent evolution is the integrating whole:** coordinated improvement of the agent's business behavior through all four planes and all three states. It includes models, semantic specifications, knowledge/context, skills, graphs/workflows, decision operators, interaction patterns, and governance mechanisms. It is not limited to model training, a feedback dashboard, or an extra plane with privileged write access.

Tie this whole to an accountable business objective and maintained agent definition in its owning scope. Default and imported/custom control primitives are part of that definition. The common lineage connects definitions/releases, actual tasks and provider outcomes, reviewed operational cases and subsequent candidates; it does not require a single global agent or unrestricted sharing of records.

## 2. The three-state / four-plane matrix

| Plane | Development state | Runtime state | Operations state |
| --- | --- | --- | --- |
| **User** | Business experts and developers express goals, author examples, inspect simulations, and review candidate behavior. | Users initiate tasks, supply information, inspect status/evidence, and approve or challenge where authorized. | Owners and operators inspect outcomes, resolve complaints/exceptions, curate feedback, and compare versions. |
| **Runtime** | Execute model experiments, simulations, workflow tests, and isolated replay/reevaluation. | Execute S1/S2 capabilities, graphs, local loops, workflows, tools, and admitted external operations. | Collect operational observations; execute authorized replay, diagnosis, evaluation, and recovery jobs. |
| **Management** | Maintain versioned definitions, semantic specifications, models, datasets, capabilities, workflows, and candidate release manifests. | Resolve the published versions and applicable configuration for a task; expose inventory and provenance. | Maintain ownership, issue/case collections, release history, rollout/retirement declarations, and reviewed evaluation evidence. |
| **Control** | Admit build/evaluation jobs; enforce data/effect boundaries; validate publication and compatibility conditions. | Enforce task and transition admission, decision adoption, authority, budgets, live preconditions, holds, and idempotent execution contracts. | Enforce operational interventions, rollout/revocation/rollback policy, recovery authority, and audit/replay isolation. |

A cell describes responsibility, not a required separate application or service. Start from openJiuwen's existing execution, extension and workbench capabilities. Compatible component versions, UI/API integration, model serving and policy/storage mechanisms remain to be qualified; these choices do not reopen the engineering foundation.

## 3. Four planes and their control boundaries

| Plane | Owns | Proposed interfaces | Boundary |
| --- | --- | --- | --- |
| **User plane** | Expressing intent; interaction; review, explanation, approval, appeal, and feedback experiences. | Task requests, evidence submissions, review decisions, feedback cases, authorized query views. | A click, message, or generated explanation does not itself publish policy or make a business decision effective. |
| **Runtime plane** | Performing admitted computational and external work; proposing plans/results; reporting observations, progress, and receipts. | Capability invocations/results, workflow child calls, model observations, tool requests, checkpoints. | Execution workers cannot grant authority, silently publish definitions, or bypass authoritative transition/effect admission. |
| **Management plane** | Maintained definitions, ownership, versioned artifacts, catalogs, release manifests, and lifecycle records. | Artifact resolution, candidate registration, publication/retirement requests, evidence and evaluation references. | Declaring a policy or release does not make it effective until the required control transition succeeds. |
| **Control plane** | Effective admission, state changes, adoption, effect permission, lifecycle transitions, and enforcement obligations. | Admission/transition decisions, bound execution grants, adoption records, operation intents, release/hold/recovery decisions. | Control consumes published semantics and model observations; it cannot invent business meaning or treat a model score as permission. |

The framework spans these responsibilities; it is not synonymous with one plane. An execution scheduler may physically live beside the graph engine in the runtime plane, while eligibility, authority, and committed transitions remain controlled by the authoritative contract. Execution adapters perform admitted calls; the control boundary establishes whether the intended call is effective and permitted.

Management owns maintained definitions and publication proposals; control admits the effective scoped activation, and registry/routing/user views reflect that same record. This is not a requirement for a central round trip on every token or local computation. Bounded admitted execution and distributed placement remain possible while preserving the authoritative transition contract per governed object.

Proposed external-system boundary: NGA's control plane governs its own agent state, local/delegated decision adoption and capability invocations. Existing business systems remain authoritative for their domain data, internal risk/consistency rules and transaction commits. An NGA adoption is not automatically external business approval or completion. [Document 19](19-business-system-capability-boundary.md) specifies this distinction and the business-capability integration proposal; it does not prescribe the provider's internal implementation.

Specify one authoritative transition path for each state change even when planes share a process or database. Four planes must not create four unrelated copies of task truth or four independent meanings of "latest."

The user plane serves business users, developers, reviewers, and operators in their respective roles. It includes programmatic interaction as well as visual interfaces. Roles acquire permissions through explicit policy, not merely by which screen they use.

## 4. Agent evolution as the integrating whole

A proposed evolution cycle is:

**business intent and observed outcomes → attributable issue and hypothesis → candidate changes → evaluation and replay → authorized promotion → bounded deployment and observation → further improvement or withdrawal.**

Every step coordinates the planes:

1. The user plane captures business goals, experience, and corrections with accountable contributors.
2. The runtime plane supplies actual behavior and executes candidate evaluations or comparisons.
3. The management plane maintains the artifacts, evidence, ownership, and candidate/release lineage.
4. The control plane enforces the conditions under which experiments, publication, rollout, intervention, or recovery become effective.

This describes one evolving agent across its lifecycle. An implementation may have services that assist evolution, but those services receive no exemption from the four-plane contracts.

The structure applies to each logical agent and their cooperation; it does not require a single enterprise-wide agent instance or identity.

Feedback is evidence to assess. User dissatisfaction with a valid credit refusal is not automatically a new training label. Delayed outcomes and selective observation of approved applications cannot directly label every intermediate judgment or the unobserved outcomes of rejected applications. Curate cases and label provenance before training or changing rules.

Promotion may be automatic under an authorized, validated policy or may require a named review. The architecture does not impose manual approval on every change; it requires explicit authority and evidence for whichever promotion mode is chosen.

### 4.1 Different changes require different contracts

| Change | Required distinction |
| --- | --- |
| S1/S2 model or prompt improvement | Evaluate behavior under the intended business specification, including consistency, discrimination, accuracy, calibration/unknown handling where used, and operational cost. |
| Business semantic change | Record an intentional change of meaning, owner, effective scope, and affected cases; do not disguise it as a model optimization. |
| Graph/workflow or decision-operator change | Check protected business obligations, composition, recovery, and replay compatibility; a changed threshold can alter business behavior. |
| Knowledge/context or memory change | Preserve source and version lineage, relevance/freshness conditions, and the material inputs actually consumed. |
| Authorization or enforcement change | Define current enforcement, revocation cutoffs, in-flight behavior, and appropriate failure handling. |
| Interaction or explanation change | Preserve decision status and material commitments; measure whether users can understand and act on the actual outcome. |

Runtime adaptation within a declared task scope is distinct from changing reusable behavior. A local S2 plan revision can be admitted under the current contract. Persistently changing a model, rule, workflow, memory policy, or adoption operator requires an identified candidate/release path.

Keep operational recovery and reusable improvement as two linked paths. An authorized resume/status/cancel/compensation action may use an existing release immediately, while a lasting primitive, workflow or model correction follows candidate/evaluation/publication. Attribute the observed problem before choosing what to improve; a callback, evidence or presentation defect is not automatically a Jev training case. [Document 22](22-integrated-lifecycle-and-plane-review.md) makes these handoffs explicit.

## 5. Version continuity across the dimensions

The proposed minimum linking structure is:

**business objective and owning scope → agent definition → sealed release manifest → scoped activation binding → task/run and decision revisions → operation attempts/outcomes → reviewed case/evaluation → candidate and subsequent release/activation.**

A release manifest references compatible model/readout versions, semantic/adoption specifications, capability/workflow/graph definitions, default/customer primitive packages and their implementation/configuration dependencies, context policies, and controller/enforcement contracts. Resolve namespaces and applicability explicitly. References may point to independently managed artifacts; a release is not necessarily one deployment unit.

A task records the release and material dependency versions actually consumed. Candidate promotion never silently rewrites an adopted decision or the artifacts used to replay it.

The [core object contracts](23-core-objects-and-plane-handoffs.md) separate immutable release content from its evaluation records and scoped activation. Management maintains definitions, manifests and evidence; control admits ACT1 for a particular scope/generation. A release's presence or display label in a catalog is not task-admission authority. The same document specifies task/case fields, command receipts and the management/control permission boundary.

Rollout policy must state which new tasks receive a release and what happens to in-flight work. Available choices include completing under pinned compatible definitions, an explicit state migration, or a hold/revision process. Live permission revocation still applies where required; version pinning cannot preserve revoked rights.

A rollback can change routing for new work or trigger explicit handling of active work. It cannot undo a confirmed credit registration. External effects require their business correction/compensation contract.

A release can be technically compatible and still fail business acceptance. Keep version compatibility, policy conformance, and measured business improvement as separate evidence.

## 6. Place the earlier S1/S2 and graph work inside this structure

The [Jev/agentic orchestration proposal](11-jev-agentic-orchestration.md) mainly develops runtime work and its control contracts. It is one part of this architecture.

- The user plane makes intent, progress, evidence, approvals, and outcomes usable.
- The management plane supplies governed questions, models, candidate sets, workflows, and release definitions.
- The runtime plane executes S1 judgments, S2 planning, typed graphs, local loops, and workflow subgraphs.
- The control plane binds the basis of judgment and commits allowed transitions, adopted decisions, and operations.

S1 and S2 may assist activities in all three states. For example, S2 can draft a workflow in development or investigate an operational exception, while S1 can evaluate declared semantic criteria. Their computations use runtime capabilities; their outputs gain authority only through the relevant publication/adoption contract.

The three repository projects do not map one-to-one to planes. Project 1 supplies decision-model tasks and capabilities; project 2 develops cooperation and runtime/control contracts; project 3 realizes the enterprise workbench across all four planes, including semantic knowledge engineering and operational evolution.

## 7. Credit example across the three states

**Development:** a business owner resolves the rule conventions and completion promise; developers construct R1/AP1, the credit workflow/graph, required evidence bindings, configured/imported primitives and demonstration cases. Runtime executes isolated evaluations. Control checks candidate admission/publication; management records the compatible release and evidence; user-plane views support review.

**Runtime:** the user initiates NGA task T1, linked explicitly to a provider application reference when available. Management resolves the applicable release and definitions. Runtime obtains evidence and calls S1/S2 as admitted. Control binds the basis, adopts D1 and admits B1 (the operation called OP1 in earlier fixtures); the adapter invokes the business capability and the framework waits for its declared result. The user sees decision, request and recovery status separately. Actual primitive/configuration versions, observations and history remain linked.

**Operations:** operators observe that a group of applications produces repeated history-coverage gaps or inconsistent source interpretation. They inspect the actual decisions and replay traces, distinguish data-quality defects from business-rule issues, and create a reviewed improvement case. Candidate changes might affect source adapters, semantic definitions, S1 behavior, the investigation workflow, or user evidence collection. The change is evaluated and promoted through the same cross-plane contracts.

An active T1 does not silently switch to a candidate model, primitive or rule because an operations dashboard now labels that version "better." A suspended wait preserves its actual implementation/configuration or follows an explicit migration/hold policy. Historical replay and candidate reevaluation remain distinguishable.

This is agent evolution in the credit case: experience changes the maintained agent through attributable, evaluated versions while preserving the identity and auditability of past decisions.

## 8. Changes to V0 and the proposed implementation sequence

The [adversarial review](14-v0-adversarial-review.md) distinguishes design defects, missing contracts, and hypotheses still needing evidence.

| Increment | Concrete work | Acceptance question |
| --- | --- | --- |
| **A. Four-plane contracts** | Specify task, artifact-publication, transition/adoption, operation, and feedback interfaces with owners. | Can each consequential change be traced to one effective authority without a UI, worker, or registry bypass? |
| **B. Execution correctness** | Complete typed budgets, effect admission, stable identities, revocation/hold ordering, and recovery contracts. | Do concurrent retries and ambiguous completion preserve the stated guarantees, including allowed counterexamples and weaker resources? |
| **C. Three-state credit slice** | Build authoring/evaluation, one live-shaped task trace, and operational case/replay views around the same release identity. | Can one business case be followed from definition through outcome and back into a reviewed improvement? |
| **D. Evolution release contract** | Candidate lineage, evaluated artifact compatibility, promotion rules, rollout selection, in-flight handling, and withdrawal. | Can an upgrade or rollback proceed without rewriting D1, replaying OP1, or silently changing an active task's semantics? |
| **E. Validate model/structure choices** | Compare useful S1 placements and graph/loop/workflow organizations on the same business and replay contract. | Do gains survive complete-task, cost, consistency, recovery, and audit evaluation? |

No runtime, storage, protocol, model topology, or deployment platform is selected here. The next binding design work is the interfaces and acceptance evidence; a visual four-plane layout alone cannot establish the guarantees.
