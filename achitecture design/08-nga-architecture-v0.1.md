# NGA Architecture V0.1 — Discussion Draft

> Date: 2026-10-30.
> Scope: project 2's S1 + S2 collaboration and its integration into project 3's enterprise workbench.
> Status: earlier logical architecture draft, not an implementation or approved mechanism set. Its three-view organization is superseded by [V0.2](13-nga-architecture-v0.2.md). Interpret retained contracts with the corrections and validation obligations in the [adversarial review](14-v0-adversarial-review.md).
> Read with: [analysis](07-nga-architecture-analysis.md), [diagrams](09-nga-architecture-diagrams.md), and [program principles](../design/nga-overall-design.md).

## 1. Design premise and status

Assume an available Jev-like model can apply supplied business definitions, preserve the required semantic distinctions and equivalences, produce typed judgments, and honor declared unresolved outcomes within its supported scope. This premise sets model research aside for the architecture exercise; it does not establish that current repository checkpoints have those capabilities.

Established direction remains: decision and business-result idempotence, traceability, business-configurable semantics, separate proposal/adoption/execution authority, project 3 ownership of semantic governance, V0 continuity, and open technology choices. The contracts, paths, and state transitions below are proposals for discussion.

The owner additionally requires replayable and auditable decision chains. The [replay and audit contract](12-replay-and-audit-contract.md) distinguishes historical inspection, executable control replay, reevaluation, and live recovery. The [orchestration analysis](11-jev-agentic-orchestration.md) extends the first S1 insertion into a proposed typed graph with local agent loops and workflow invocation; it does not finalize the topology.

A reliable model still requires reliable task framing, evidence, composition, adoption, and execution. The framework must preserve these dependencies across retries and changes.

## 2. Logical organization and authority

Retain V0's three views:

| View | Responsibilities | Authoritative artifacts |
| --- | --- | --- |
| **Management** | Publish capabilities, semantic specifications, adoption and authorization policies; manage versions, ownership, reviews, and exceptions. | Catalog entries, policy/specification versions, and their publication records. |
| **Control** | Admit tasks; bind specifications and evidence; validate proposals; invoke capabilities; adopt decisions; schedule bounded work; admit actions; recover and reconcile. | Recorded task, decision, and operation transitions under published policy. |
| **Execution/data** | Run S1, S2, skills, and tools with bounded context and authority; return observations, proposals, evidence, and receipts. | Outputs remain attributed artifacts until accepted at the appropriate control boundary. |

These are responsibilities, not deployment units. Execution workers do not publish authoritative policy. Durable records serve operational coordination and historical reconstruction; calling them a ledger does not select event sourcing or a database.

| Participant | May do | May not do on its own |
| --- | --- | --- |
| Business/knowledge owner | Define semantics, precedence, defaults, coverage, and exception conventions; approve a specification release. | Retroactively rewrite a historical decision by changing a definition. |
| S1 | Produce a typed business judgment or a declared unresolved outcome for a bound specification and evidence frame. | Grant permission, change specifications, commit authoritative state, or dispatch business effects. |
| S2 | Interpret the task, request evidence, propose a plan or decomposition, explain outcomes, and propose revisions. | Redefine the effective decision question, bypass a veto/adoption gate, broaden authority, or reopen a decision as an ordinary retry. |
| Framework | Enforce contracts and current authority; manage identities, snapshots, state transitions, adoption, dispatch, and recovery. | Invent missing business conventions or treat a valid output schema as proof of semantic completeness. |
| Execution adapter/resource | Carry out admitted operations; enforce supported preconditions and deduplication; report receipts and reconciliation evidence. | Treat an unknown outcome as confirmed failure or infer a fresh business operation from a new attempt. |

S1 and S2 are logical capability roles, not new identity principals. They may be exposed as skills or model services behind existing capability contracts. Record the executing agent identity and the actual model/artifact version separately.

Business semantics and authorization remain separate. A positive S1 classification can satisfy a published business condition; it cannot override a permission denial.

## 3. Contracts and artifacts

Retain V0's capability contract fields: provides, requires, effects, and bounds. Add references to the following logical information without yet choosing schemas or wire protocols.

| Artifact | Minimum meaning | Responsible boundary |
| --- | --- | --- |
| **Semantic specification** | Business question and output states; definitions, units, time conventions, precedence, coverage and exception behavior; examples; evidence requirements; version and effective scope. | Project 3's authorized publication process; consumed by S1 and the framework. |
| **Adoption policy** | Which judgments/checks are required, how they compose, any thresholds, approval obligations, and permitted actions for unresolved outcomes. | Authorized policy owner publishes; framework applies and records. |
| **Decision frame** | Identified business subject/operation scope, requested decision, immutable specification and adoption-policy references, evidence snapshot, evaluation time/freshness conditions, and revision relationship. | Framework validates and binds for one evaluation revision; S2 may propose inputs. |
| **Evidence manifest** | Required and supplied sources, source authority and versions, visibility, freshness, provenance, completeness checks, and unresolved gaps. | Admitted source adapters and framework assembly; model-generated assertions remain distinguishable. |
| **S1 observation** | Frame reference, typed values/outcome, model/readout configuration, status, and supported evidence/diagnostic references. | S1 returns; framework verifies binding and contract compliance. |
| **Plan revision** | Goal, frame/decision dependencies, requested capabilities, data dependencies, proposed actions, resource envelope, stop conditions, and parent revision. | S2 proposes; framework admits within published scope. |
| **Adopted decision** | Business outcome, exact observations/checks consumed, adoption policy, authority/approval basis, frame reference, and supersession relationship. | Guarded framework transition; immutable historical record. |
| **Operation intent and receipt** | Stable business-operation identity, adopted-decision dependency, target and material parameters, preconditions, attempts, actual result, and recovery links. | Framework admits; execution boundary enforces its declared guarantees and reports. |

An evidence manifest makes coverage requirements inspectable. It cannot mechanically prove arbitrary natural-language completeness. Verification must combine source-specific checks and validated judgment within the approved contract. A model alone cannot certify that an omitted authoritative source does not exist.

The framework, not unconstrained S2 text, resolves authoritative specification versions and identities. Approved template parameters may vary within declared semantics. New criteria or an unreviewed composition require the specification/revision path.

## 4. Two paths with one adoption boundary

### 4.1 Contract-bound fast path

A published task contract already identifies the decision, required evidence, permitted outcome states, and action mapping.

1. Resolve the request identity and current task state.
2. Admit required evidence reads under the capability and authorization contracts.
3. Build and validate the decision frame; route unresolved specification or evidence gaps.
4. Invoke S1 and bind the observation to that frame.
5. Perform required checks and apply the published adoption policy.
6. Commit the adopted decision once for that revision.
7. If an action is due, admit and dispatch its stable operation under current permission and preconditions.
8. Record confirmed results or enter reconciliation.

No generative planning is required when this path fully satisfies the contract. Omitting S2 is a proposed optimization, not a rule that every task should be forced onto this path.

### 4.2 S2-assisted investigation and planning

S2 receives the goal, admitted capability set, relevant specifications, current task state, and bounded context. It may propose evidence collection, a plan, or additional questions. Each request passes the framework's contracts and authority checks.

Additional questions must preserve the original business decision's meaning and required conditions. The framework may use a reviewed decomposition contract; a new decomposition is a proposal to validate, not automatically equivalent to the original rule. Exact calculations and time comparisons may use deterministic capabilities where their semantics are defined.

S2 does not directly call business-effecting tools outside the framework. Evidence reads and preparatory actions can occur before final business adoption when their own contracts allow them. Consequential effects depend on the applicable adopted decision and action contract.

Both paths converge on the same adoption boundary. S2's free-form explanation accompanies the recorded outcome; it cannot replace its amount, conditions, status, or other material fields.

### 4.3 Bounded adaptation

A plan may change without changing the business question. Record the plan revision and retain unaffected decision dependencies.

A material evidence, rule, outcome, or action-parameter change requires the corresponding new frame, decision revision, or operation amendment process. It is not a retry. S2 cannot obtain a desired result by repeatedly rewriting the question, removing evidence, or treating a refusal as permission to start a fresh identity.

Route semantic-definition gaps to project 3's knowledge workflow; route evidence gaps to admitted acquisition; route capability limits to a declared alternative or review. These are distinct causes even if they share a workbench queue.

## 5. State, identity, and idempotence

### 5.1 Distinguish identities

| Identity | Stable meaning |
| --- | --- |
| Business request | The accountable user's identified business request and material input, within a declared tenant/business scope. |
| Decision frame/revision | One immutable question/specification/evidence basis for evaluation. |
| Adopted decision | The effective business outcome for that revision and its adoption basis. |
| Plan revision | One admitted organization of work and its dependencies. |
| Business operation | One intended external business effect; independent of inference count, retry count, and model version. |
| Attempt | One delivery or execution try for that operation. |
| Execution grant | The current bounded authority used by an attempt; renewal does not create a new business operation. |

The framework derives or validates these identities under the business contract. Hashing arbitrary prompt text is insufficient. Distinct customers or legitimate transactions must not be collapsed merely because their S1 judgments match.

### 5.2 Guarded adoption and dispatch

A proposed task lifecycle is: admitted → evidence ready → assessed → adopted → action pending → confirmed. Waiting for evidence, semantic resolution, approval, or reconciliation are explicit alternatives. An adopted rejection may complete without any external action. These are logical states, not a frozen enumeration.

Adoption must validate the current revision and commit one effective result with its consumed dependencies. Concurrent attempts either observe that result or expose a defined conflict. Recording two contradictory adoptions and resolving them later is insufficient if both can dispatch.

Dispatch has a second gate: the adopted-decision dependency, operation identity, current authorization, material parameters, and execution preconditions must still hold. Record durable intent before losing the ability to determine what was attempted. The atomicity/outbox/storage mechanism remains open.

A read-before-write freshness check alone may race with a resource change. Where the guarantee requires it, the execution boundary needs an enforced conditional operation or equivalent contract. Where this is unavailable, state the weaker guarantee and reconciliation path.

An admitted execution hold or decision supersession must also be ordered against dispatch using the relevant current state. If dispatch has already started, a local hold does not prove that the external effect stopped. The [credit walkthrough](10-credit-decision-walkthrough.md) develops the pre-adoption, pending-action, in-flight, and completed-effect cases separately.

### 5.3 Recovery

| Event | Required behavior |
| --- | --- |
| Same request and material content | Return the existing effective revision or pending state; resume needed work without reopening settled decisions. Expose an authorized revision explicitly rather than presenting it as an unchanged historical response. |
| Same identity with changed material content | Surface a conflict or explicit amendment; do not silently overwrite. |
| Crash before adoption | Resume from recorded inputs; repeated inference must not create multiple effective decisions. |
| Crash after adoption, before dispatch | Reuse the adopted decision and the same operation identity, subject to current execution checks. |
| Timeout or crash around external completion | Reconcile using the operation identity and resource evidence; an unknown result does not authorize a blind new operation. |
| Retry with new credentials | A new grant/attempt still refers to the same intended business operation. |
| Rule, evidence, or model update | Preserve history; create an explicit reevaluation/revision if required. A model update alone does not create a new external effect. |
| Authorization revoked after adoption | Preserve the historical decision; block unauthorized dispatch and record why. |
| Correction after a confirmed effect | Use a business-defined correction or compensation operation linked to the original; do not replay it as if it never happened. |

An external service without deduplication, conditional execution, or reliable outcome lookup limits the guarantee. NGA must expose that limitation rather than claim universal exactly-once effects.

## 6. Context, composition, and resources

Keep separate the delegation lineage, execution dependencies, and evidence/decision provenance. Shared evidence carries provenance and access conditions, not the producer's authority. A consumer may read it only under its own admitted access.

V0's draft/seal/reveal and cooperative pool mechanisms remain candidates. A sealed result is a versioned artifact, not automatic business adoption. Record which versions were visible to S1, S2, and any verifier. If an independent verification path receives the conclusion it was meant to assess independently, its contract must account for that exposure.

A decomposition must preserve required vetoes, coverage, and composition order. Correct individual S1 judgments do not establish that an arbitrary S2-generated graph implements the business rule. The decomposition and adoption contract need their own validation.

Resource accounting is typed:

- Add total cost, tokens, calls, and attempts across branches; include S1, S2, verification, retries, and dynamic children.
- Propagate deadlines and measure elapsed time; do not treat maximum parallel duration as a general hard bound.
- Enforce concurrency and delegation limits over the full admitted scope.
- Record reservations, consumption, and release idempotently. Child reservations must fit the parent's available envelope.

Concrete graph syntax, expression language, budget scheduler, context store, and enforcement topology remain open.

The proposed comparison now includes a graph whose nodes can be tools, S1 judgments, bounded S2 loops, workflow invocations, or adoption/effect operations. Semantic transitions can consume Jev observations; mechanical transitions use authoritative state and deterministic checks. Consequential work inside a node shares the same control and replay contract. See the [node and transition design](11-jev-agentic-orchestration.md).

## 7. Workbench and traceability

Project 3 should expose five connected views:

1. **Task and outcome:** request, owner, current decision, action status, and pending obligations.
2. **Decision basis:** effective specification, required/supplied evidence, actual S1 observations, adopted outcome, and approvals or overrides.
3. **Plan and execution:** S2 proposals, admitted revisions, capability use, operation attempts, receipts, and unresolved completion.
4. **Semantic issues:** ambiguous terms, uncovered cases, conflicting rules, assigned owner, resolution, and publication impact.
5. **History and comparison:** reconstruct the original outcome, compare an explicit reevaluation, or initiate authorized recovery/compensation.

An approval view must show the material decision and effect, evidence gaps, relevant changes, and authority being requested. Approval after those material inputs change must be revalidated under its contract; an old approval cannot silently authorize different parameters.

Historical reconstruction uses preserved observations, specification/adoption versions, and recorded dependencies. Fresh model evaluation creates a separate comparison. Reconstruction must not dispatch live effects, and access to historical evidence remains authorized. Traceability does not require exposing hidden model reasoning.

## 8. Illustrative credit-rule walkthrough

The credit example is selected for the next architecture exercise. The [complete decision walkthrough](10-credit-decision-walkthrough.md) provides a concrete main path, a phase-by-phase S2 change matrix, proposed S1 insertion points, retry and new-evidence branches, and reconstruction obligations.

This uses the owner's example to exercise boundaries, not to publish a complete lending policy. Project 3 must first settle asset denomination/valuation, exact time and overdue conventions, evidence authority, and uncovered bands.

The stated business requirements are:

- Assets above 30 million and no overdue loan within the last six months: USD 50,000 credit.
- Assets below 1 million: USD 10,000 credit.
- The historical "more than three months overdue" condition overrides both and denies credit.

The following assumes the approved specification has made those predicates unambiguous:

| Evidence pattern | Required decision behavior |
| --- | --- |
| Upper asset band; six-month condition satisfied; historical veto false | Adopt USD 50,000 eligibility, subject to the published adoption requirements. |
| Lower asset band; historical veto false | Adopt USD 10,000 eligibility. Do not silently import the upper band's six-month condition. |
| Historical veto true | Deny credit regardless of the asset-band result. |
| Evidence cannot establish a required predicate | Follow the declared evidence-gap path; unknown is not automatically false. |
| Exactly at a cutoff, between bands, or otherwise uncovered | Follow the published unresolved-case convention; do not interpolate an amount. |

S2 may help collect evidence or explain the result. It may not choose a more favorable rule version, omit the historical veto, or change the adopted amount. An approved eligibility decision and an actual credit-grant operation are distinct. Dispatch still needs authorization and valid action preconditions.

If the application is retried, reuse its adoption and operation identity. If new evidence changes eligibility before dispatch, create the appropriate revision and block the stale pending action. If the grant already occurred, follow the correction process instead of treating a new inference as a second grant.

## 9. Engineering work packages and acceptance evidence

These packages are proposed implementation work, not changes to current experimental pre-registrations.

| Package | Concrete artifact | Essential acceptance case |
| --- | --- | --- |
| **E1. Semantic and evidence binding** | Logical contracts, specification resolver, evidence-manifest validator, decision-frame examples. | S2 paraphrases preserve the selected rule; omitted required evidence or a veto cannot silently pass. Complete valid cases still proceed. |
| **E2. Decision adoption** | S1 adapter contract, decision-policy boundary, guarded adoption/state interface. | Concurrent workers produce one effective adoption; a material revision is distinct from a duplicate. |
| **E3. S2 collaboration** | Bounded plan/revision contract, tool routing, validated decomposition examples. | Fast and S2-assisted paths agree for equivalent frames; S2 can gather missing evidence without changing the business criterion. |
| **E4. Execution and recovery** | Stable-operation contract, intent/receipt records, reconciliation interface, replay isolation. | Crash before/after dispatch, ambiguous timeout, changed parameters, and renewed credentials do not duplicate the intended effect; a genuinely new operation can proceed. |
| **E5. Context and resource control** | Visibility/provenance contract, typed budget rules, reservation accounting. | Unauthorized context remains unavailable; parallel cost is additive; duplicate grants/releases cannot expand the envelope. |
| **E6. Workbench integration** | V0 task/decision views, semantic-issue workflow, historical reconstruction and comparison. | Reviewers can identify the effective rule and effect; resolved semantics create versions; reconstruction never triggers live effects. |
| **E7. Composed orchestration and replay** | Typed node/transition contracts, workflow invocation and child-instance records, captured nondeterministic inputs, and an isolated control replayer. | Replay nested loops/workflows and hold/dispatch races; detect divergent guards or intents; prevent live effects; compare S1 placements on equal business contracts. |

Begin with one bounded workflow through E1, E2, E4, and a minimal E6 view; add the E3 comparison and E5 cases needed by that workflow. Project 3's full knowledge platform need not be complete to exercise reviewed, versioned specifications. Track task success, decision consistency, duplicate effects, recovery correctness, latency, cost per successful outcome, and trace completeness together.

## 10. Open decisions

| Decision | Proposed direction or remaining choice |
| --- | --- |
| First S1 insertion and scenario | The credit example is selected for the walkthrough. Its proposed first required S1 role is the full business judgment feeding adoption. Production-pilot scope, auxiliary S1 checks, and unresolved business conventions still require decisions. |
| Decision composition | Select the approved decomposition/composition contract and allowed S2 variation. Do not assume question-graph equivalence. |
| Reopening and freshness | Define which evidence changes invalidate a pending decision/action, when decisions expire, and who may reopen them. |
| Trust root and enforcement (V0 questions 1–2) | Preserve live authority checks and per-property enforcement obligations; registry design, token lifetime/format, and revocation mechanism remain open. |
| Execution structure (V0 question 3) | Compare the proposed typed graph with local S2 loops and workflow subgraphs against loop and fixed-workflow controls. S1 handles declared semantic judgments, not every transition. Graph revisions and workflow execution retain common admission, identity, and replay contracts. |
| Build/certification and host integration (V0 questions 4 and 7) | Verify artifact identity, execution isolation, and that each declared restriction is actually enforced; select no host in this draft. |
| Peer collaboration and external actors (V0 questions 5–6) | The delegation lineage covers subordinate work. Peer authority and externally initiated tasks need their own explicit contracts. |
| Prototype and implementation (V0 questions 8–9) | Choose the scenario and required guarantees before languages, storage, runtimes, or protocols. Documentation and contract examples can advance now. |

Each resolution should record the rationale, affected contracts, acceptance evidence, and version impact. The inherited nine questions are not automatically approved by publishing this draft.
