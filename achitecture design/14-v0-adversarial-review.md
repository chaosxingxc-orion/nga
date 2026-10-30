# Adversarial Review of V0 and the NGA Proposals

> Date: 2026-10-30.
> Scope: the supplied [V0 brief](05-architecture-brief-and-decisions.md) and [V0 diagrams](06-architecture-diagrams-md.md), plus our [V0.1](08-nga-architecture-v0.1.md), [orchestration](11-jev-agentic-orchestration.md), and [replay](12-replay-and-audit-contract.md) proposals.
> Method: inspect stated contracts, construct counterexamples, identify corrections and acceptance cases. This is a design review, not a claim of executed penetration, fault-injection, or model tests.
> Resulting architecture: [V0.2 — three states, four planes, agent evolution](13-nga-architecture-v0.2.md).

## 1. Overall assessment

V0's capability contracts, bounded delegation, explicit adoption, provenance, and version awareness are useful foundations. It is not yet a complete enterprise-agent architecture for the owner's objectives.

The primary structural problem is that V0 assigns its three views to different times, while NGA needs four responsibility planes operating across development, runtime, and operations. The previous NGA draft retained that three-view framing too readily. Adding a user-facing box or renaming the data plane would not resolve the missing lifecycle and evolution contracts.

Several mechanisms also have concrete counterexamples or incomplete guarantees. These are not all the same kind of finding:

- **Invalid general rule or overstatement:** a stated conclusion fails under a concrete counterexample.
- **Missing contract:** the documents do not specify enough to support the desired guarantee; this does not prove that an unseen implementation is broken.
- **Unvalidated hypothesis:** a plausible design requires comparative evidence before selection.

Prior approvals and source-project test counts do not discharge these obligations for NGA. External vendor and industry-uniqueness claims in the archived documents are not used as evidence here.

## 2. Findings and required changes

### A1. Planes are conflated with execution times — structural correction

**Source:** V0 brief §4.2; V0.1 §2.

The source describes management at authoring time, control at admission/scheduling, and data at tool-call time. That is a useful scenario projection, but insufficient as the complete architecture.

**Counterexample:** an operations user starts a replay investigation. It simultaneously needs user interaction, runtime computation, versioned artifacts, and control over data access and live effects. A development evaluation needs those same four responsibilities. Neither fits a scheme in which a plane exists only at its assigned execution moment.

**Change:** use the three-state/four-plane matrix in V0.2. Treat agent evolution as coordinated change across the matrix, with version and outcome continuity.

**Acceptance:** trace a development evaluation, a business task, and an operational replay through all four planes. Identify an owner and authority for every effective change.

### A2. A single parallel-budget maximum is incorrect — confirmed rule defect

**Source:** V0 brief §4.4; its budget formula combines sequential sums and parallel maxima across an insufficiently typed budget concept.

**Counterexample:** two parallel branches costing 4 and 6 units consume 10 units, not 6. Applying the maximum to a parent cost budget of 6 admits work that exceeds it. Token, call, and attempt totals have the same problem.

**Change:** aggregate consumable totals; model concurrency separately; propagate deadlines and distinguish elapsed critical-path estimates from guaranteed wall-clock limits. Record reservation, consumption, and release idempotently. Issuance-time partitioning alone does not prevent duplicate child grants or repeated release.

**Acceptance:** parallel 4+6 cost fails a budget of 6 and fits a budget of 10, with appropriate bounds for retries. Replayed grant/consume/release events cannot enlarge the remaining budget. Legal sequential and parallel work still proceeds.

**Current NGA treatment:** earlier analysis and V0.1 propose the correction; no enforcing implementation is established.

### A3. Reversibility does not establish an authorization boundary — invalid inference

**Source:** V0 brief §4.2, invariant 4.

The source acknowledges that an in-process hook can be bypassed by a compromised worker, then reserves resource-side checks for irreversible actions and says hook-only actions must be reversible. This condition is insufficient for authority guarantees.

**Counterexample:** an unauthorized read may have no write effect, yet disclose protected information. A reversible write can still violate permission before it is reversed. The ability to compensate does not make the original access authorized.

**Change:** every security-relevant resource restriction claimed as enforced needs a trusted enforcement path covering that property. Hooks can assist validation and observability; effect classification separately determines approval, recovery, and compensation. Select the actual enforcement topology later.

**Acceptance:** attempt a forbidden read and a forbidden reversible write through each supported invocation path. They must remain denied under the chosen worker trust model; valid authorized operations must succeed. Do not claim this test has already passed.

### A4. Initial admission cannot guarantee future permission — overstatement and race gap

**Source:** V0 diagrams L2 step 4 promises that missing permission will not appear halfway through; V0 brief §4.2 and §7 questions 1–3 discuss revocation, freshness, and dynamic work.

**Counterexample:** a required permission is revoked after admission, or S2 discovers a new capability requirement inside an open task. An initially valid aggregate contract cannot guarantee that later work remains permitted. A short-lived token also does not by itself eliminate the interval between checking permission and committing an external effect.

**Change:** describe preflight admission as a check of declared requirements, then define per-operation authorization, dynamic-scope admission, revocation cutoffs, and in-flight handling. Pin historical business/configuration evidence while enforcing current permission where required. Define when resource-side conditional enforcement is necessary.

**Acceptance:** revoke authority between admission and dispatch, and race a hold/revocation with dispatch. Distinguish prevention, already-started work, and reconciliation. A newly discovered out-of-scope action cannot self-authorize.

### A5. Adoption events alone do not guarantee idempotence — missing contract

**Source:** V0 brief §4.7; V0 diagrams L2's final bookkeeping step.

An adoption event is valuable, but it does not specify single-winner adoption, durable operation intent, parameter binding, or external deduplication. The diagram may be conceptual rather than literal timing; the issue is the missing crash/concurrency contract.

**Counterexample:** two workers both record adoption and grant credit. Alternatively, the resource commits a grant, the acknowledgement is lost, and a restarted loop submits another grant.

**Change:** guard adoption against current state; distinguish decision and operation identities from attempts; durably record intent; reconcile uncertain outcomes; state the external resource's actual guarantee.

**Acceptance:** concurrent adoption, crash after adoption, lost completion response, and changed payload under the same key. Confirmed history is preserved and a legitimately new business operation remains possible.

**Current NGA treatment:** documents 08, 10, and 12 specify proposed contracts. Their existence is not evidence of runtime enforcement.

### A6. Context isolation does not prove verification independence — unvalidated inference

**Source:** V0 brief §2.2 and §4.6; V0 diagrams L2 step 8.

Separating contexts can reduce information leakage, but cannot by itself establish independent errors, trustworthy source selection, or sufficient separation of duties.

**Counterexample:** producer and verifier use the same incomplete evidence and model assumptions, so both miss the historical credit veto. A worker with effective access to both contexts can also violate a prompt-level isolation convention.

**Change:** specify what the verifier checks, which evidence it receives, its access boundary, and how its result is consumed. Use independently sourced checks or deterministic invariants where appropriate. If a process requires distinct approval authority, separate contexts under one identity do not satisfy that requirement automatically.

**Acceptance:** correlated-error fixtures, missing-source cases, and attempted reads of sealed/private contexts. Do not equate two matching answers with two independent confirmations.

### A7. One accountable user is not a complete responsibility model — scope gap

**Source:** V0 brief §3 A4 and §4.7; its claims that responsibility can later move by changing the ledger query view.

**Counterexample:** a wrong published rule affects many users; a defective model release or adapter changes results; an operational recovery or scheduled evaluation is not initiated by the employee whose task exposed the problem. A single employee anchor cannot explain those different contributions.

**Change:** retain the business owner and executing identity, and record specification author/reviewer, release authority, adoption/override authority, and operation executor as applicable. A responsibility reassignment may require new evidence and permissions, not merely a different query view. The audit must distinguish task ownership from contribution to a defect.

**Acceptance:** audit one task failure back to a rule change, one to a model/adapter release, and one to an authorized intervention, without losing the task owner.

### A8. One task tree cannot carry all dependency meanings — boundary to clarify

**Source:** V0 brief §2.2 and §4.4; subsequent NGA graph proposals.

A parent-child task tree can legitimately carry delegation. It does not follow that execution dependencies, shared evidence, and decision-revision provenance should be the same tree.

**Counterexample:** one sealed loan-history result supports two decisions. Copying or joining task authority to represent that shared evidence could unintentionally expand a consumer's rights; duplicating the source loses the fact that both decisions depended on the same version.

**Change:** keep delegation lineage, execution dependencies, and evidence/decision provenance distinct and linked by identities. Reading shared evidence requires the consumer's own admitted access. Peer collaboration needs its own authority contract.

**Acceptance:** one source feeds multiple consumers with different rights; an evidence revision identifies affected decisions without merging their permissions or invalidating unrelated work.

### A9. Feedback is not yet an evolution contract — structural gap in our proposals

**Source:** V0 brief §5's acknowledged dynamic gaps; V0.1 §7 and §9; orchestration §8.

Our earlier drafts connect outcome feedback to model tasks but do not sufficiently specify a whole-agent candidate, its release, and its treatment of running work.

**Counterexample:** operations favors model M2, management publishes rule R2, and a running task still uses adoption policy AP1. Independent "latest" references can assemble an unevaluated combination. Changing the selected version after D1 cannot erase an already registered credit limit.

**Change:** maintain an agent release manifest and evaluated compatibility/provenance across models, specifications, workflows, operators, and relevant context policies. Record actual task bindings. Define rollout and active-task migration/hold rules; distinguish deployment rollback from business-effect correction.

**Acceptance:** promote and withdraw a candidate while A001 is active. Neither event silently changes D1 or repeats OP1; replay can resolve the original dependencies. A known compatible new task can use the new release.

### A10. Operational feedback is not automatically a training target — evolution risk

**Source:** the proposed evolution use of feedback; prior survey warnings already retained in NGA's design.

**Counterexample:** users dislike valid refusals, so optimizing approval feedback weakens the veto. Only approved applications yield certain downstream observations, yet their outcomes are used as labels for all rejected alternatives or every intermediate judgment.

**Change:** curate issues, label sources, business validity, observation limits, and outcome attribution. Distinguish changed business policy from improved model adherence to the existing policy. Preserve independent evaluations and the experiment amendment process.

**Acceptance:** valid but unpopular refusals remain valid under unchanged R1; missing counterfactual outcomes remain unknown; misleading whole-task success cannot certify a faulty intermediate judgment.

### A11. Typed graphs and additional Jev calls are still hypotheses — review of our own design

**Source:** orchestration §§2–8; replay contract.

Typed graphs can expose boundaries, but do not prove better decision quality or replayability. More S1 observations can add correlated errors, composition burden, or cost. A loop can also be replayable if its consequential interactions are captured.

**Counterexample:** an entirely structured credit workflow needs no open reasoning; wrapping every node in S2 loops and judging every mechanical edge with S1 makes it more complex without adding business capability. Conversely, a graph with opaque agent-loop nodes still loses the internal basis for a decision.

**Change:** retain loop and deterministic-workflow controls; compare selected semantic S1 placements; instrument nested work; use one workflow execution contract rather than a model interpreting workflow prose alongside a second runtime implementation.

**Acceptance:** paired end-to-end cases with identical business, authority, recovery, and replay requirements. Report useful outcomes and total cost, not node counts or model-call volume.

## 3. Red-team the new three-state/four-plane organization too

V0.2 is not exempt from challenge.

| Failure in the new design | Required correction |
| --- | --- |
| Put development only in management, runtime only in the runtime plane, and operations only in a dashboard. | Use all four responsibilities in each state; test the complete credit lifecycle. |
| Create an evolution service that can silently overwrite production rules or weights. | Evolution coordinates governed candidate/evaluation/release transitions across the planes; it has no special bypass. |
| Let user actions, registry edits, and runtime workers each independently commit effective state. | Define one authoritative transition contract and durable correlation for every consequential change. |
| Assume a release manifest proves business improvement. | Separately establish compatibility, policy conformance, and measured business acceptance. |
| Freeze every task's permissions forever for reproducibility. | Preserve historical inputs while enforcing current rights and explicit revocation/in-flight semantics. |
| Call replay faithful and therefore correct. | Report historical fidelity and contract conformance separately; also evaluate business correctness where evidence supports it. |

## 4. Disposition

Retain capability contracts, bounded delegation, explicit adoption, context provenance, and version awareness. Correct the invalid budget and enforcement inferences; weaken unsupported promises about future authorization and verification independence. Complete the state/operation, release, and evolution contracts before claiming enterprise guarantees.

The three states, four planes, and agent-evolution whole are established organizing requirements. V0.2's mechanisms and the graph/loop/S1 placement choices remain proposals. The acceptance cases above have not been executed; they define what must be demonstrated before implementation claims are made.
