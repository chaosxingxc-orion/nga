# NGA Architecture Discussion Register

> Date: 2026-10-30.
> Status: open discussion register. All 18 questions below are **OPEN**; recommendations are starting positions, not owner-approved decisions or implemented guarantees.
> Purpose: consolidate unresolved architecture questions, identify additional gaps, and make subsequent discussions produce reviewable decisions.
> Basis: [overall design](../design/nga-overall-design.md), [V0.2](13-nga-architecture-v0.2.md), [Graph / Agent Loop / Workflow review](15-graph-loop-workflow-control-review.md), and the earlier [adversarial review](14-v0-adversarial-review.md).

## 1. What is already established

The discussion does not reopen these owner requirements:

- Three lifecycle states: development, runtime and operations.
- Four responsibility planes: user, runtime, management and control.
- Agent evolution as the integrating whole across the states and planes.
- Decision consistency, decision/business-result idempotence, replay and audit as objectives.
- Business-configurable behavior and governed semantic specifications; semantic gray areas require explicit resolution paths rather than silent model invention.
- Configurable/importable control primitives and customer extensions: the framework may provide defaults, but industry-specific control semantics must not be restricted to a closed built-in vocabulary.
- Three related projects: decision-model research and engineering, S1 + S2 framework design, and an enterprise agent workbench.
- For this architecture exercise, assume a Jev-like model satisfies the required capabilities within its declared scope. That premise does not assert that current repository models have passed those gates.
- Owner correction after the AQ-01/AQ-02 discussion: design the framework's general logic first, then challenge it with varied cases. Detailed banking semantics are not prerequisites to that design. Independent cases can remain distinct while sharing a business constraint; see [document 18](18-framework-core-and-case-coverage.md).

The owner has accepted the business-capability/IT-authority boundary as the working premise for the resumed AQ-01/AQ-02 discussion: NGA invokes qualified operations while the existing IT system owns its domain records, internal rules and execution. See [document 20](20-task-decision-request-identity.md).

What remains open is the precise scope of each promise, its enforcement and composition contracts, and the evidence needed to adopt an implementation. Requiring replay, for example, does not yet settle replay granularity, retention or access.

Role labels below identify proposed participants, not named assignees. A recommendation becomes a decision only through the recording procedure in section 7. No numerical service target, risk threshold, storage technology or model topology is selected here.

Current cross-cutting proposal: [document 21](21-runtime-primitives-and-capability-contracts.md) specifies default primitive families, customer configuration/import/custom implementations, API contracts and Graph/Workflow recovery expression, with twenty execution cases and eight extension cases. It advances model, composition, recovery and release questions; detailed mechanisms remain OPEN. Customer extensibility itself is an owner requirement.

Current integrated review: [document 22](22-integrated-lifecycle-and-plane-review.md) rechecks those proposals across the whole, three states and four planes. It proposes shared agent/release/task/case lineage and seven cross-plane handoffs, distinguishes immediate task recovery from reusable evolution, and adds twelve acceptance cases. This develops AQ-08/AQ-11/AQ-14–AQ-18 without declaring them closed.

Current object-contract proposal: [document 23](23-core-objects-and-plane-handoffs.md) specifies AgentDefinition, immutable ReleaseManifest, scoped ActivationBinding, Task and OperationalCase; their authority/mutation boundaries; seven handoff envelopes; and sixteen adversarial cases. The illustrative credit trace covers development through evolution. AQ-02/AQ-11/AQ-14–AQ-18 remain OPEN pending agreement and qualification of these details.

## 2. The 18 questions and suggested discussion order

| ID | Decision to discuss | Kind | Proposed participants |
| --- | --- | --- | --- |
| [AQ-01](#aq-01) | What outcome closes an NGA task, and which case patterns test that promise at the business-capability boundary? | Coverage / product contract | Business owner, framework and workbench leads |
| [AQ-02](#aq-02) | What counts as the same task, decision question/revision and business request across changes and retries? | Intent / identity contract | Business/knowledge owner, framework lead |
| [AQ-03](#aq-03) | What is the minimum publishable semantic specification and who may change it? | Semantic governance | Knowledge owner, model and framework leads |
| [AQ-04](#aq-04) | Who constructs the effective evidence basis, and when must it be refreshed? | Evidence / temporal contract | Data owner, knowledge owner, framework lead |
| [AQ-05](#aq-05) | What is Jev's judgment contract, and which placements should be evaluated first? | Interface plus empirical choice | Model and framework leads, business owner |
| [AQ-06](#aq-06) | How are unresolved cases, fallback judgments and human exceptions handled? | Business / authority contract | Business/risk owner, knowledge and framework leads |
| [AQ-07](#aq-07) | How far may S2 change a running plan automatically? | Adaptation / authority contract | Framework lead, business owner |
| [AQ-08](#aq-08) | Do we need one graph representation, or compatible execution contracts across engines? | Architecture hypothesis | Framework and integration leads |
| [AQ-09](#aq-09) | How do multiple judgments compose into one business decision? | Semantic composition plus evaluation | Knowledge, model and framework leads |
| [AQ-10](#aq-10) | What must nested loops, workflows and collaborating agents inherit and preserve? | Composition / resource contract | Framework and integration leads |
| [AQ-11](#aq-11) | Which component is authoritative for each effective state change, and how are races resolved? | State / consistency contract | Framework lead, business owner |
| [AQ-12](#aq-12) | Which external effects can we safely execute, retry, reconcile and correct? | Integration / guarantee contract | Business-system owner, framework lead |
| [AQ-13](#aq-13) | What is the trust, permission and context-sharing boundary? | Enforcement contract | Resource/security owner, framework lead |
| [AQ-14](#aq-14) | What replay/audit fidelity, retention and access do we support? | Evidence / operations contract | Business/audit/data owners, framework lead |
| [AQ-15](#aq-15) | What can operators do, and what happens when dependencies or budgets are unavailable? | Operations / user contract | Operations owner, workbench and framework leads |
| [AQ-16](#aq-16) | What constitutes a release, and how do promotion, rollback and active-task migration work? | Lifecycle contract | Release owner, framework/model/knowledge leads |
| [AQ-17](#aq-17) | What evidence qualifies a model, rule or workflow change as agent improvement? | Evolution / evaluation contract | Business owner and all three project leads |
| [AQ-18](#aq-18) | What is the smallest workbench slice and the end-to-end acceptance package? | Product / validation contract | Business owner and all three project leads |

**Revised discussion order after owner feedback:** first define general case/decision/operation identity and effective-state contracts (AQ-02/AQ-11), then plan composition, effects and shared-constraint boundaries (AQ-07/AQ-10/AQ-12). Use AQ-01/AQ-18 to select small, explicit coverage fixtures rather than requiring a detailed credit-product design. [Document 18](18-framework-core-and-case-coverage.md) provides the proposed core and eight case patterns. This replaces the earlier banking-scope-first interpretation of the agenda.

Then close the execution boundaries in AQ-10–AQ-13; compare model placement and execution organization in AQ-05/AQ-08/AQ-09; define the lifecycle and operational acceptance in AQ-14–AQ-18. This is a discussion agenda, not a waterfall delivery plan. Retention, operator needs and release behavior must inform interfaces early, and AQ-18's evaluation design precedes comparative experiments.

## 3. Question cards

<a id="aq-01"></a>
### AQ-01 — Task completion and coverage promises

Current focused discussion: [document 20](20-task-decision-request-identity.md) defines task completion at the business-capability boundary and exercises it with credit cases. [Document 17](17-credit-scope-identity-and-revision-review.md) is earlier fixture analysis; [document 18](18-framework-core-and-case-coverage.md) establishes the framework-first method. Status remains OPEN; no production banking scope is selected.

- **Question:** what outcome does an NGA task promise, and which small case portfolio tests that promise? Distinguish local judgment completion, submission/receipt, provider terminal outcome, waiting, recovery handoff and later review.
- **Why it matters:** a judgment-only demo does not establish request/effect recovery, and a provider acknowledgement does not establish its terminal business result. One domain-specific success does not prove the core is general.
- **Options and tradeoff:** one happy-path example is easy to demonstrate but hides architectural gaps; complete products across many domains demand too much detail at this stage. A small portfolio of distinct case patterns tests the core without first specifying every business process.
- **Starting recommendation:** declare task scope and completion before execution. The end-to-end credit fixture uses a correlated framework wait for the provider's terminal application outcome; a submission-only task may close earlier only under its explicit contract. Incoming evidence does not automatically replace an in-flight request: record it for the next boundary or use an explicit interruption policy. Track local decision, request outcome and recovery separately without importing provider internals.
- **To close:** a small coverage portfolio, each with declared intent, effect, constraints, expected states and positive/counterexample outcomes. Develop it with AQ-02/AQ-12/AQ-18; detailed production domain semantics are a later binding requirement.

<a id="aq-02"></a>
### AQ-02 — Identity, equivalence and revision

Current focused discussion: [document 20](20-task-decision-request-identity.md) distinguishes NGA task, decision question/revision and business-operation request, with plan/run/attempt records beneath them. It refines the earlier application-centered treatment in [document 17](17-credit-scope-identity-and-revision-review.md). Status remains OPEN; NGA task identity is not automatically the provider's application identity.

- **Question:** what establishes continuity of an NGA task, one delegated decision question and one business request? Which evidence/rule/time changes create a decision revision, and which changes only revise a plan or add an attempt?
- **Failure case:** a new graph node or user-channel request creates a fresh operation key and repeats a grant; the opposite mistake caches an obsolete decision and prevents a legitimate new application.
- **Options and tradeoff:** upstream application identity is precise when available but needs conflict handling; governed business keys can join channels but need domain-specific definitions. Text similarity or a payload hash alone cannot establish business equivalence.
- **Starting recommendation:** bind T1 to admitted objective/scope, J1/D1 to a delegated question and immutable basis, and B1 to one provider operation with fixed material parameters. Map provider application references explicitly. New evidence or applicable rules can create D2 without creating T2 or B2; pure replanning preserves these identities, and retries add attempts. Unknown external completion blocks an assumed-safe conflicting replacement.
- **To close:** a general identity/lineage contract, then paired fixtures for duplicate submission, legitimate new cases, shared constraints, changed evidence, new reference time and later amendment. Bind the AQ-03/AQ-04 semantics/evidence assumptions needed by each fixture without making a full production business model a prerequisite.

<a id="aq-03"></a>
### AQ-03 — Publishable business semantics

- **Question:** which fields, examples and checks make a semantic specification consumable by a model and framework, and who may author, approve, publish and amend it?
- **Failure case:** the credit rule leaves asset currency, equality boundaries, uncovered bands, historical coverage or overdue duration conventions unstated; a model or developer supplies a convenient default.
- **Options and tradeoff:** prose is accessible but insufficient alone for executable controls; a fully formal language can be restrictive. A structured contract with business-authored definitions and examples offers a middle path, but still needs explicit validation and ownership.
- **Starting recommendation:** require scope, definitions, candidate outcomes, precedence/veto rules, source/coverage conditions, reference-time conventions, unresolved routes, effective version and accountable authority. For the first slice, use an owner-reviewed fixture; the full knowledge-engineering workbench remains project 3's work.
- **To close:** a semantic-contract example and publication/change protocol, with both rejected incomplete drafts and admissible complete ones. Do not select a final authoring language or business convention through this register. Feeds AQ-04/AQ-05/AQ-06/AQ-09.

<a id="aq-04"></a>
### AQ-04 — Evidence ownership, context and freshness

- **Question:** who determines required sources, coverage, precedence and reference time; how are conflicting, late or corrected facts handled; what may S2 select, summarize or retain as memory?
- **Failure case:** S2 presents only a recent clean statement and omits older overdue history. Another run uses the full history. Jev is consistent on each submitted question, while the agent's business result changes because its basis was uncontrolled.
- **Options and tradeoff:** one task-start snapshot simplifies replay but may become stale; unrestricted live reads improve freshness while changing the basis mid-decision. Declared evidence frames with validity checks expose both the historical basis and reasons for reevaluation.
- **Starting recommendation:** bind a versioned evidence manifest with source coverage and evaluation time. Distinguish authoritative facts from model assertions and derived summaries. Material changes create a new bound basis; current permissions and effect preconditions still require live enforcement. Specify handling when multiple sources cannot provide a consistent snapshot.
- **To close:** an evidence-authority/coverage table, temporal rules and fixtures for conflict, missing history, late veto and changed source. Link these to adoption/dispatch races in AQ-11 and release changes in AQ-16.

<a id="aq-05"></a>
### AQ-05 — Jev's interface and initial placements

- **Question:** what exactly does a judgment request bind and return? Where does Jev first add useful semantic work: business readout, evidence support, workflow applicability, routing or progress assessment?
- **Failure case:** a raw score is treated as permission, or an exact receipt is sent to a model for reinterpretation. Conversely, relegating Jev to an optional opinion lets S2 silently determine every consequential outcome.
- **Options and tradeoff:** a business-readout insertion is easy to attribute; process/evidence insertions may reduce S2 work but introduce more composition obligations. A uniform model call on every edge adds complexity without demonstrating benefit.
- **Starting recommendation:** define question/specification, admitted evidence, candidate meanings, model/readout version and consumption policy as the contract. Start comparisons with a business-judgment boundary and one genuinely semantic evidence/applicability boundary. Keep exact arithmetic and authoritative state checks deterministic. Scores, if exposed, need a separately defined interpretation policy.
- **To close:** request/result examples, supported/unsupported scope, unresolved outputs and an end-to-end placement comparison. Model conformance is a premise here; placement benefit remains empirical. Coordinate AQ-03/AQ-06/AQ-09/AQ-18 without amending frozen model experiments implicitly.

<a id="aq-06"></a>
### AQ-06 — Unresolved cases, fallback and exceptions

- **Question:** which unresolved cases permit more investigation, which require semantic clarification, and which allow an alternate judgment or authorized human exception? Who can make that exception effective?
- **Failure case:** an undefined asset band is escalated to S2, which invents an amount; repeated rephrasing continues until Jev returns approval; a timeout is interpreted as a failed grant and retried under a fresh identity.
- **Options and tradeoff:** universal abstention is simple but can prevent valid completion; universal S2 fallback undermines the decision contract. Distinct evidence, semantic, capability and execution-resolution routes preserve the reason for being unresolved.
- **Starting recommendation:** use explicit unresolved categories and their business-authorized routes. Do not silently convert unknown to grant or refusal. A fallback judge or human override, if permitted, has a separate qualified contract, scope and recorded authority. Automatic adoption remains possible when its declared conditions hold.
- **To close:** a resolution/override matrix, retry/aggregation limits and examples where legitimate new evidence changes the result. Semantic gaps remain with the knowledge/business owner, not the runtime planner. Depends on AQ-01/AQ-03/AQ-05; informs AQ-11/AQ-15.

<a id="aq-07"></a>
### AQ-07 — S2's adaptation envelope

- **Question:** may S2 only choose parameters/order, compose registered workflows, patch bounded subgraphs, or generate arbitrary executable structure? Which changes require new admission, a decision revision or reusable release publication?
- **Failure case:** a graph patch preserves the veto node visually but adds a path that bypasses it. A repaired node also resets operation identity or resumes with stale evidence.
- **Options and tradeoff:** fixed templates simplify assurance but constrain novel work; bounded composition adds flexibility with explicit obligations; arbitrary graph generation requires substantially stronger validation and recovery evidence.
- **Starting recommendation:** begin with registered workflow composition and bounded plan patches. Keep protected business obligations, authority limits and effect identity outside the planner's editable scope. Preserve completed history; make affected dependencies and treatment of active children explicit. A layout change alone does not create a new business decision.
- **To close:** an allowed-change matrix by lifecycle moment, patch request/admission examples and bypass/race counterexamples. Depends on AQ-02/AQ-03; works with AQ-09/AQ-10/AQ-11. Broader generation remains a hypothesis until justified by a business case.

<a id="aq-08"></a>
### AQ-08 — Graph representation and engine interoperability

- **Question:** must every executable procedure use one graph representation, or may several engines expose compatible control, event and recovery contracts? What is the minimum visibility required from an integrated engine?
- **Failure case:** one engine treats child completion as decision adoption while another treats it as a proposal; an opaque agent-loop node performs unaudited tool calls. A common diagram format does not remove these disagreements.
- **Options and tradeoff:** one representation simplifies inspection and compilation but can restrict existing capabilities; adapters reduce migration work but must demonstrate compatible semantics. One implementation does not itself prove one authoritative state model.
- **Starting recommendation:** first define common identities, invocation/result semantics, transition authority, effect admission and replay coverage. Use [document 21](21-runtime-primitives-and-capability-contracts.md) to compare typed Graph nodes/edges with Workflow steps and recovery handlers. Both must resolve configurable/imported/custom primitive types without a closed built-in vocabulary. A graph is not an enforcement boundary, and every edge need not call Jev. Following the owner's foundation decision, start from existing openJiuwen Java execution facilities; [document 24](24-openjiuwen-reuse-and-evolution.md) maps the relevant source and extension points. Representation mapping, package details and qualified interoperability remain open.
- **To close:** a conformance contract and comparison using the same credit task through an openJiuwen workflow and a bounded loop, including recovery and hidden-action attempts. Depends on AQ-10/AQ-11/AQ-14; informed by AQ-18. The base is settled; compatible version and integration guarantees remain to be demonstrated.

<a id="aq-09"></a>
### AQ-09 — Composition of judgments and branches

- **Question:** which business judgments can be decomposed, and how do results combine across exclusive choices, stacked conditions, vetoes, unknowns, parallel branches and repeated checks?
- **Failure case:** the high-asset branch grants before the historical-veto branch finishes, or two local judgments with different evidence frames are combined as though they described one case.
- **Options and tradeoff:** one complete semantic judgment minimizes orchestration but can be harder to diagnose; decomposition exposes intermediate conditions while adding semantic and synchronization obligations. Neither is universally superior.
- **Starting recommendation:** publish the composition operator and required basis for each decision. Preserve veto/priority and unresolved behavior; require all necessary observations before grant adoption. Compare direct and decomposed forms on equivalent and distinguishing cases. Do not infer global correctness or calibrated joint probabilities from locally correct outputs.
- **To close:** a composition specification and paired cases covering delayed veto, conflicting outputs, missing prerequisites and a valid straightforward grant. Depends on AQ-03/AQ-04/AQ-05 and feeds AQ-07/AQ-11.

<a id="aq-10"></a>
### AQ-10 — Nested work and collaborating agents

- **Question:** what identities, rights, context, budgets, cancellation obligations and results must a child loop/workflow/agent preserve? When is a child result usable by its parent?
- **Failure case:** a parent retry creates a new child, repeating a confirmed operation; each child assumes it owns the full remaining budget; parent cancellation is reported as proof that an external write stopped.
- **Options and tradeoff:** opaque calls are easy to integrate but cannot support detailed guarantees; native subgraphs expose fine-grained events but increase coupling; adapters can expose a declared intermediate contract with explicit limits.
- **Starting recommendation:** stable child-call identity, root business correlation, bounded delegation, material-parameter binding, typed statuses and one-time result consumption. Declare join/sibling handling, outstanding effects and recovery ownership: a local first-success result or parent exit cannot erase a child's external work. Add consumable costs; model concurrency and deadlines separately. Share evidence only with independently admitted access, without merging the consumers' authority.
- **To close:** a child-invocation contract and tests specified for duplicate delivery, suspend/resume, budget exhaustion, recursion limits and cancellation races. Requires AQ-02/AQ-07/AQ-11/AQ-13. Allocation algorithms and physical schedulers remain open.

<a id="aq-11"></a>
### AQ-11 — Authoritative state and competing transitions

- **Question:** which logical owner makes a plan revision, decision adoption, hold, dispatch or release effective? How are concurrent changes ordered, and what durable evidence accompanies the transition?
- **Failure case:** the UI, graph worker and operations console each maintain a different effective decision; a hold and a dispatch both claim to have won.
- **Options and tradeoff:** one centralized controller is easy to reason about but may create unnecessary coupling; authority per governed object permits distribution but needs explicit cross-object and external-effect contracts. Independent engine-local truth cannot establish a shared guarantee.
- **Starting recommendation:** one authoritative transition contract per governed object, expected-revision checks and durable correlation between effective state and audit evidence. Management maintains definitions/proposals; control admits scoped activation and state changes; catalog, routing and user views reflect that same record. Runtime executes within admitted scopes without requiring a global round trip for every calculation. Distinguish NGA state from provider-owned business commits; see [documents 19](19-business-system-capability-boundary.md) and [22](22-integrated-lifecycle-and-plane-review.md).
- **To close:** agree and qualify the [document 23 object/command/receipt proposal](23-core-objects-and-plane-handoffs.md), including scoped activation generation, publication authority, lost/duplicate receipts and stale projections, alongside decision/dispatch/child races. Depends on AQ-02/AQ-06/AQ-07/AQ-09 and co-designs the operation boundary with AQ-12.

<a id="aq-12"></a>
### AQ-12 — External effects, recovery and correction

- **Question:** what does each target resource guarantee about duplicate requests, payload binding, querying completion, conditional writes and correction? What can NGA promise when any capability is missing?
- **Failure case:** the resource registers credit, loses the acknowledgement and cannot answer a status query. Repeating a non-idempotent request may duplicate the effect; refusing to retry may leave progress unresolved.
- **Options and tradeoff:** require a strong integration contract for automatic execution, accept a documented weaker guarantee with explicit reconciliation, or keep the resource outside automated effect execution. A framework label cannot remove the tradeoff.
- **Starting recommendation:** invoke semantically defined business capabilities and wait for their declared result. The owning IT system enforces its internal rules and commits its data. Separate normal waiting, local deadline expiry and explicit interruption. Qualify native cancellation/reversal or compose a recovery capability from supported operations with a defined outcome, preconditions and recovery for partial failure. Compensation is not automatically atomic rollback; absent a qualified path, declare reversal unsupported. Preserve original/request-recovery lineage and never substitute arbitrary field writes. See [document 20, section 4](20-task-decision-request-identity.md#4-normal-waiting-explicit-interruption-and-qualified-recovery).
- **To close:** qualify the [document 21 capability matrix and operators](21-runtime-primitives-and-capability-contracts.md) against synchronous/asynchronous, native-cancel, composite-compensation and unsupported-reversal fixtures. Verify normal completion, early/late/duplicate responses, deadline and retry-budget continuity, cancellation races and partial compensation failure. Depends on AQ-01/AQ-02/AQ-11; determines AQ-15 recovery behavior.

<a id="aq-13"></a>
### AQ-13 — Trust, permission and context sharing

- **Question:** which workers/adapters are trusted, where are protected reads/writes enforced, how does revocation affect in-flight work, and what intermediate context may collaborators or verifiers see?
- **Failure case:** an in-process hook is bypassed; a task-start permission snapshot survives revocation; two isolated prompts use the same biased evidence but are treated as independent verification.
- **Options and tradeoff:** trusted workers simplify integration but narrow the threat model; resource-side enforcement or isolated brokers can strengthen boundaries at greater integration cost. Context isolation and independent evidence are different requirements.
- **Starting recommendation:** state the trust model explicitly and enforce every protected access through a suitable trusted path, including reads and reversible writes. Define delegation and revocation cutoffs; separate historical evidence of authorization from current permission to act. Make evidence-sharing and verifier-independence requirements explicit.
- **To close:** a trust/access diagram, context visibility matrix and allowed/forbidden-path examples including revoked permissions and shared evidence consumers. Informs AQ-04/AQ-10/AQ-11/AQ-14. Protocol, token format and isolation technology remain open.

<a id="aq-14"></a>
### AQ-14 — Replay fidelity, audit and retention

- **Question:** which execution boundaries must be replayable, for how long, by whom, and with which preserved artifacts? How is replay capability reported when evidence is unavailable or retention expires?
- **Failure case:** a timeline exists but consumed evidence or model outputs do not; a digest is mistaken for recoverable content; a replay button reissues a real grant.
- **Options and tradeoff:** event inspection costs less but is not executable control replay; preserved control artifacts and recorded inputs support stronger reproduction at greater retention/access cost. Retention must be reconciled with the applicable data policy without silently overstating replay coverage.
- **Starting recommendation:** preserve the distinction between inspection, control replay, reevaluation and live recovery. Define a bounded replay package, access policy and comparison contract. Report historical fidelity and contract conformance separately. Historical model outputs suffice for control replay; hidden internal reasoning is not required. NGA replays its own control path with recorded provider responses; provider-internal audit/replay is separately owned and requires supported correlation/evidence.
- **To close:** a replay/retention matrix, complete and incomplete package examples, integrity/access requirements and isolated replay acceptance. Depends on AQ-04/AQ-08/AQ-11/AQ-13 and applies to release/evolution actions as well as runtime tasks.

<a id="aq-15"></a>
### AQ-15 — Operator actions, availability and user-visible status

- **Question:** what do pause, hold, cancel, resume, retry, reevaluate and correct actually mean? Who can request them? What happens when a model, policy service, evidence source or external resource is unavailable or a budget is exhausted?
- **Failure case:** the console says "canceled" while credit registration remains in flight; a degraded service silently routes decisions to an unqualified model; a UI retry resets the business identity.
- **Options and tradeoff:** blocking preserves some boundaries but reduces availability; approved waiting, queueing, resumption or fallback paths can preserve progress. Each path must preserve its declared decision and effect guarantees rather than promise that every failure can be transparent.
- **Starting recommendation:** typed, authorized operator commands with idempotent results; expose decision state separately from operation state. Define dependency-specific waiting/degradation/recovery behavior and escalation ownership. Select latency, availability, queue and cost targets from the intended business workload, not an arbitrary number here.
- **To close:** an operator command matrix, status/notification examples, service-target draft and outage/budget scenarios that include successful recovery. Depends on AQ-06/AQ-10/AQ-11/AQ-12; informs AQ-18's user experience.

<a id="aq-16"></a>
### AQ-16 — Release compatibility and active tasks

- **Question:** which models, rules, prompts, workflows, adapters, operators and context policies form a compatible release? Which changes affect new tasks, active tasks, cached judgments or adopted decisions?
- **Failure case:** a running task combines a new rule with an old adoption operator and an untested model; deployment rollback is treated as reversal of a confirmed business effect.
- **Options and tradeoff:** pinning versions simplifies continuity but needs explicit handling of urgent changes; task migration permits updates but requires state/dependency compatibility. Independently selecting every component's latest version is not an evaluated release.
- **Starting recommendation:** a dependency manifest with compatibility and business-acceptance evidence, including imported primitive packages, implementation/configuration versions and checkpoint dependencies. Select definitions explicitly for new tasks and pin/migrate/hold active ones; installing a package cannot silently replace a suspended control's semantics. Enforce current revocation where required. Preserve original decision/effect records and evaluate cache invalidation against actual semantic dependencies.
- **To close:** a change-impact matrix and rollout/withdrawal traces for immutable manifests plus scoped activation bindings, including policy authority, readiness, package/model/workflow changes and active B1. [Document 23](23-core-objects-and-plane-handoffs.md) provides the concrete starting contract. Depends on AQ-02/AQ-03/AQ-11/AQ-14; supports AQ-17.

<a id="aq-17"></a>
### AQ-17 — Evidence for agent evolution

- **Question:** which observations become improvement cases or labels, how are model defects separated from rule/evidence/process defects, and when may an agent-loop trace become a reusable workflow?
- **Failure case:** popular approvals become positive labels despite violating a veto; only successful approvals yield outcome data; a successful trace with hidden exceptions is automatically promoted to production.
- **Options and tradeoff:** manual review offers accountable curation at an operational cost; bounded automatic qualification can scale selected changes but needs explicit evidence and authority. Unconditional self-update bypasses the existing release contract.
- **Starting recommendation:** attributed cases → hypothesis → candidate → independent, predeclared evaluation → authorized promotion → observed outcomes. Attribute semantic, model, context, workflow, primitive, integration or interaction defects before choosing a change target. Keep immediate operational recovery separate from reusable improvement; historical replay and candidate reevaluation have different comparison purposes. Automatic promotion is a policy choice, not a privilege of the model. See [document 22](22-integrated-lifecycle-and-plane-review.md).
- **To close:** an evolution case/release record, label-provenance rules, change-specific acceptance gates and an example that rejects a superficially successful candidate. Depends on AQ-03/AQ-14/AQ-16/AQ-18. Preserve unknown counterfactual outcomes and the existing experiment amendment process.

<a id="aq-18"></a>
### AQ-18 — Workbench slice and end-to-end acceptance

- **Question:** what minimum development, runtime and operations experience demonstrates one coherent agent lifecycle across all four planes? What evidence would make us accept or reject the proposed orchestration?
- **Failure case:** a dashboard visualizes a graph but cannot trace a result to a rule version, reproduce its control path or recover a lost acknowledgement. Another prototype always refuses and appears perfectly consistent.
- **Options and tradeoff:** a runtime-only demo is faster but leaves lifecycle guarantees untested; a broad enterprise workbench spreads effort before the contracts are established. A narrow complete lifecycle tests both architecture and user needs.
- **Starting recommendation:** one semantic-definition and imported/custom-primitive qualification flow, one complete credit task using normal API waiting, and one operations recovery/replay/improvement flow tied to the same agent, release, task and case lineage. Exercise all twelve cells without requiring twelve separate applications. Compare workflow, governed agent loop and typed graph with selected Jev placements under equal business/recovery obligations; use [document 22](22-integrated-lifecycle-and-plane-review.md) as the integrated fixture.
- **To close:** a workbench story map and predeclared acceptance package: valid grant/refusal, unresolved rules, equivalent inputs, relevant changes, delayed veto, duplicate submissions, revoked access, lost acknowledgement, nested resume, replay and release change. Report useful completion, consistency, recovery, cost/latency and audit coverage together. Requires outputs from the preceding contracts; define comparisons before executing them.

## 4. Coverage of three states, four planes and the integrating whole

| Plane | Development discussions | Runtime discussions | Operations discussions |
| --- | --- | --- | --- |
| User | AQ-01, AQ-03, AQ-18: express requirements, author cases, inspect candidates. | AQ-06, AQ-15: supply evidence, understand outcomes, exercise authorized interventions. | AQ-14, AQ-15, AQ-17: inspect history, resolve cases, assess improvement. |
| Runtime | AQ-05, AQ-08, AQ-09, AQ-18: execute isolated comparisons and composition checks. | AQ-07, AQ-10, AQ-12: execute admitted plans, child work and effects. | AQ-14, AQ-15, AQ-16: run replay, recovery and release transition workloads. |
| Management | AQ-02, AQ-03, AQ-08: define identities, specifications and executable artifacts. | AQ-04, AQ-05, AQ-10, AQ-16: resolve actual evidence/capability/workflow/release dependencies. | AQ-14, AQ-16, AQ-17: maintain retained artifacts, change history and reviewed cases. |
| Control | AQ-03, AQ-07, AQ-13, AQ-18: enforce publication, adaptation and evaluation boundaries. | AQ-02, AQ-06, AQ-09, AQ-11–AQ-13: enforce effective decisions, composition, authority and effects. | AQ-14–AQ-17: enforce replay isolation, intervention, rollout and evolution admission. |

The agent-evolution whole links these cells through case and release lineage. It has no separate authority to bypass them. The matrix identifies responsibilities, not twelve services or a mandated UI layout.

## 5. Traceability to earlier open questions

This register refines existing questions; it does not silently close or replace the program-level questions or their model-research scope.

| Earlier source | Architectural discussion here |
| --- | --- |
| Overall design O1 / O12 — first scenario and integrated iteration | AQ-01, AQ-05, AQ-18 |
| O2 — S2 adaptation | AQ-07, AQ-10 |
| O3 — S1 placement | AQ-05 |
| O4 — rules, decomposition and computation | AQ-03, AQ-05, AQ-09 |
| O5 — identities, validity and reopening | AQ-02, AQ-04, AQ-11, AQ-12 |
| O6 — unknown, thresholds and overrides | AQ-05, AQ-06 |
| O7 — execution structure and enforcement | AQ-08, AQ-10, AQ-11, AQ-12, AQ-13 |
| O8 — context sharing | AQ-04, AQ-13 |
| O9 — reconstruction and retention | AQ-14 |
| O10 — implementation selection | AQ-08 and section 6; model architecture still belongs to project 1's evidence process. |
| O11 — semantic-specification lifecycle | AQ-03, AQ-16 |
| Document 15 §10 items 1–3 — graph, adaptation and placement | AQ-08; AQ-07/AQ-10; AQ-05/AQ-09 |
| Document 15 §10 items 4–6 — identity, unresolved and evolution | AQ-02/AQ-04; AQ-03/AQ-06; AQ-16/AQ-17 |
| V0.2 release/evolution gaps and document 12 replay contract | AQ-14–AQ-18 |
| Adversarial review A2–A8 — budgets, enforcement, concurrency and lineage | AQ-02, AQ-04, AQ-10–AQ-14 |

New emphasis in this register includes explicit operator-command semantics and service degradation, the weakest external resource's guarantee, workbench acceptance across the three states, and the evidence needed to close rather than merely discuss a question.

## 6. Technical choices intentionally deferred

**Settled constraint:** openJiuwen remains the engineering base; the owner has selected the public Java line for this analysis. Reuse existing components first and keep necessary custom work pluggable. [Document 24](24-openjiuwen-reuse-and-evolution.md) provides pinned source evidence, eight review findings and twelve proposed integration cases. This narrows implementation choices without closing the eighteen AQ contracts or claiming integration validation.

| Choice | Evidence needed first |
| --- | --- |
| Compatible openJiuwen Graph/Workflow version, representation mapping and extension points | AQ-07–AQ-11 execution/composition contracts, document 24's source mapping and AQ-18 comparison on the existing base. |
| Extension placement/language, service decomposition and deployment topology around the Java base | Workload, authority boundaries, isolation and service targets from AQ-11/AQ-13/AQ-15; no requirement for a service per logical object. |
| State store, event transport and consistency mechanism | AQ-02 identities, AQ-11 arbitration, AQ-12 external effects and AQ-14 replay requirements. |
| Authorization protocol, credential mechanism and isolation technology | AQ-13 trust model, resources and revocation semantics. |
| Model serving, caching, batching and routing implementation | AQ-04/AQ-05 contracts, AQ-15 targets, AQ-16 invalidation and measured workload. |
| Workbench UI stack and authoring interface technology | AQ-03 authoring needs, AQ-15 operational commands and AQ-18 story map. |

Deferring a product choice does not defer the underlying contract. For example, state-store selection can wait; the required behavior when adoption races with a hold cannot remain implicit in the implementation.

## 7. How to record answers without losing the discussion

For each AQ item, maintain its ID and record:

| Field | Required content |
| --- | --- |
| Status | OPEN, DECIDED, DEFERRED or SUPERSEDED, with date. All items start OPEN. |
| Question and scope | The exact business cases and guarantee to which the answer applies. |
| Decision and authority | The selected option, explicit owner authorization or delegated decision policy, and rationale. An assistant recommendation is not that authorization. |
| Alternatives and counterexample | Rejected alternatives, tradeoffs and the adversarial case the decision addresses. |
| Evidence | Reviewed artifact, experiment or acceptance result; distinguish proposed checks from executed evidence. |
| Consequences | Affected interfaces, semantic/evidence basis, graph/workflow behavior, release handling, audit and dependencies. |
| Follow-up | Remaining uncertainty, implementation/verification work, and conditions for reopening. |

A design decision can be recorded before implementation evidence exists, provided it says what remains to be demonstrated; DECIDED never means IMPLEMENTED or VERIFIED. If an item is only partly resolved, keep it open and state the settled portion or split a linked subquestion. A deferred item needs a reason and a concrete revisit trigger. Superseding a decision preserves its earlier reasoning and applicability.

Once a discussion settles a contract, update the relevant architecture/interface document and link the decision record here. Amend experiment protocols only through their existing process. Keep the GitHub discussion artifacts and mirrored repository aligned through the repository synchronization workflow.
