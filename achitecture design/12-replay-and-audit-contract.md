# NGA Decision-Chain Replay and Audit Contract

> Date: 2026-10-30.
> Requirement: decision chains must be replayable and auditable.
> Status: proposed information, execution, and acceptance contracts; no replay engine or audit certification is claimed.
> Applies to: graphs, agent loops, nested workflows, and the [credit decision walkthrough](10-credit-decision-walkthrough.md).

Under [V0.2](13-nga-architecture-v0.2.md), the same contract applies to development evaluations, business execution, and operational interventions across the four planes. Candidate evaluation, publication, rollout, and withdrawal are also attributable lifecycle actions. Replaying them must not publish a real release or alter live routing.

## 1. Separate four operations

| Operation | What runs | Treatment of original history | Live effects |
| --- | --- | --- | --- |
| **Historical inspection** | Reconstruct the recorded graph/loop path, evidence, judgments, authority, and outcomes. | Read the preserved history; expose gaps explicitly. | None. |
| **Executable control replay** | Run the preserved controller, graph/workflow definitions, and decision operators with recorded nondeterministic inputs. | Verify that the same transitions, adoptions, and operation intents result; report divergence. | None. |
| **Model/policy reevaluation** | Replace a declared model, graph, rule, evidence, or policy in an isolated comparison. | Create a separate run linked to the original. Differences are results, not corrections to history. | None. |
| **Live recovery/resumption** | Continue a real task under its operation identities, current authorization, validity, and reconciliation contract. | Append real attempts, transitions, and outcomes. | Only those newly admitted under the live execution contract. |

The first two are complementary replay capabilities. The third is a controlled experiment; the fourth is live execution. They must not be interchangeable UI buttons or implicit modes.

The proposed first engineering target includes **executable control replay**, not only a visual event timeline. Fresh inference need not return identical tokens or raw scores to reconstruct the actual past: the replay consumes the S1/S2 outputs used then. Reproducibility of a new model run is a separate capability with its own artifact and environment requirements.

## 2. Replay boundary and required records

All consequential work must cross an instrumented framework boundary, including inside a local agent loop or a child workflow. A top-level "node completed" event is insufficient if that node made unrecorded decisions or tool calls.

| Record family | Information required for its supported replay/audit scope |
| --- | --- |
| Definitions | Agent/release identity and dependency manifest; semantic specifications, candidate meanings/order, graph/workflow versions, admitted patches, capability contracts, decision operators, threshold/calibration policies, and their retrievable contents. |
| Initial and changing state | Request/business identities, frame and node-activation identities, initial snapshot, state revisions, consumed dependency versions, and before/after transition references. |
| Evidence and context | Actual supplied content or preserved retrievable versions, source authority/coverage/freshness, visibility, provenance, and distinctions between source facts and model assertions. |
| Model invocations | S1/S2 request context, visible prompts/inputs, candidate set, model/configuration identity, actual returned observations/proposals, invocation identity, and input digest. Hidden internal reasoning is not required. |
| Tools and external reads | Requests, material parameters, responses, failures, timeout observations, external authorization results where applicable, and request/result correlation. |
| Time and competing events | Clock/deadline inputs actually consumed, timer firings, relevant randomness/identifiers, admitted cancellation/hold events, and recorded arbitration order for competing state transitions. |
| Decisions and transitions | Guard outputs actually used, selected and rejected/ineligible branches with recorded reasons, dependency checks, adoption/override basis, committed state version, and effective authority. |
| Operations | Stable business-operation identity, immutable material parameters or explicit amendment history, attempt identities, grants by reference, receipts, unresolved outcomes, and reconciliation/correction links. |
| Parent/child execution | Workflow and loop instance identities, call/return correlation, inherited authority and budget, consumed child results, and suspend/resume relationships. |
| Evolution lineage | Reviewed issue/case provenance, candidate changes, evaluation runs, publication/promotion authority, actual rollout selection, and declared handling of active tasks and withdrawals. |
| Executable artifacts | Retrievable controller/operator code or equivalent executable version, schemas/serialization behavior, compatibility information, and runtime dependencies needed for control replay. |

Record grant references and relevant attributes, not reusable credentials. Preserve data only within the declared access/retention contract; a deployment must state the interval over which full replay is supported.

Digests identify content and help detect changes; they do not reconstruct missing content. A model version name is not a substitute for its actual recorded output. If an executable artifact is unavailable, historical inspection may remain possible, but executable replay must report its limitation.

## 3. Proposed executable control-replay procedure

1. Select a historical task/revision and verify the completeness and integrity of its required replay package.
2. Start an isolated replay context using the preserved definitions, controller/operator behavior, and initial state.
3. Replace external/model adapters with recorded-response adapters and a controlled clock/event source. Live credential issuance, resource writes, and dispatch remain disabled at the execution boundary.
4. Match each requested invocation by identity, input/material-parameter digest, and dependency version. Supply the recorded response only for a matching request.
5. Recompute control decisions, guard consumption, state transitions, adoption, and operation-intent creation. Do not replay committed transitions as unquestioned outputs and then call that verification.
6. Deliver timer events, evidence updates, and race outcomes in the recorded relevant order. Require consistent state revision checks and parent/child relationships.
7. Compare the resulting node activations, selected paths, decision/adoption revisions, and operation identities/material parameters with the recorded sequence under a declared comparison contract.
8. Stop at the first material divergence, missing record, unexpected invocation, or unconsumed required event; report the evidence. Do not fill gaps with fresh model guesses.

Report two separate verdicts: **historical fidelity** (did the control run reproduce the recorded behavior?) and **contract conformance** (did that behavior satisfy the registered control invariants?). A replay can faithfully reproduce a duplicate adoption, a premature dispatch, or another defect and still fail conformance. Check invariants such as one effective adoption per revision, action dependencies, material-parameter binding, bounded authority, and stable operation identity independently of sequence matching.

This procedure verifies control behavior given the historical inputs. It does not prove that the business specification was correct, the evidence was truthful, or the model's judgment was accurate.

Replay uses a separate run/state namespace and cannot update the live task or its authoritative history. Compare business outcomes, consumed dependencies, semantic transitions, operation identities, and material parameters under the declared contract; replay-specific run identifiers and display offsets need not equal the original. Replay records reference the original identities for comparison rather than acquiring live dispatch rights.

An adapter may replay a historical external authorization response, but the controller's own checks still execute. Live resumption instead needs current authorization. Offline replay never turns an old grant into permission for a real external call.

## 4. Reevaluation when the path changes

A reevaluation can deliberately replace one S1 judgment, an S2 planner, a policy, or a graph revision. Preserve the original and mark the comparison boundary.

Recorded responses are usable only where their request and dependency contracts still match. If a new S2 plan calls a different tool or supplies different arguments, the old response from "step 7" cannot be reused merely because it occupies the same position.

At an unobserved branch, stop with an explicit coverage limit or use a separately identified offline fixture/simulator. Such results are counterfactual evaluation data, not observations of the original business world. Reevaluation has no live-effect path.

## 5. Replay the credit case

For application A001, the replay package includes R1/AP1, the graph/workflow version, E1/F1, the S1 output O1, S2 proposals actually consumed, D1, OP1/ATT1, and the resource observations.

- **Normal case:** feed the original evidence and O1; verify that the controller adopts D1 and creates the same USD 50,000 intent for the same customer. Intercept dispatch and compare the intent; do not register a limit.
- **Response lost after external completion:** deliver the original timeout and later reconciliation receipt. Verify the unresolved state followed by confirmation of OP1, with no second credit operation.
- **New evidence before dispatch:** deliver the evidence/hold event in its recorded order. Verify that stale dispatch is blocked when the hold won. If dispatch won, replay the in-flight reconciliation path rather than inventing a successful cancellation.
- **Nested history-reconciliation workflow:** restore its child instance and consumed results. Verify that resume does not restart confirmed child effects.
- **Model replacement:** run a separate evaluation under a named new model. A different business judgment is reported against D1 and cannot rewrite it or modify the actual credit limit.

Historical inspection should let a reviewer traverse each of these paths with its actual evidence and authority. Executable replay should detect a changed branch, omitted veto/dependency, duplicate operation identity, or mismatched amount before any live effect is possible.

## 6. Auditability is an operational obligation

The audit view must explain:

- What business request and meaning were in force, and which graph/workflow or plan revision executed.
- Which sources and context were actually supplied, including coverage limits and material omissions detected.
- Which S1 judgment and S2 proposal influenced each consequential transition, and which policy consumed them.
- Why a branch became effective, including candidate/priority rules and hard authorization or dependency denials.
- Who authored or approved relevant definitions, who adopted or overrode a decision, who executed it, and who owned the business task.
- What effect was intended, what was attempted, what was confirmed externally, and what remains unresolved.
- Which later revision, compensation, or reevaluation relates to the decision without replacing the original history.

Do not manufacture reasons for branches whose guards were never evaluated; mark them unevaluated or unreachable as appropriate. A generated explanation is a view over evidence, not a replacement for evidence.

Authoritative transitions and their audit records must be durably correlated under a defined failure contract. Best-effort debug logs are insufficient. An external effect may still precede its observed receipt, so durable intent and reconciliation remain essential.

The design must provide access control, integrity protection, and explicit version/correction history for audit artifacts. Append-only records alone do not demonstrate resistance to tampering; the storage, signing, verification, and retention mechanisms remain open. Auditability enables examination of mistakes as well as successful behavior; it is not proof that every recorded decision was correct.

## 7. Acceptance cases

These are proposed engineering checks, not executed tests.

| Case | Required result |
| --- | --- |
| Replay a normal graph and the equivalent bounded loop | Reproduce the declared control outcomes with identical operation identities/parameters and no live effects. |
| Replay concurrent adoption or hold/dispatch | Honor the recorded arbitration and state revisions; expose any duplicate or stale transition. |
| Faithfully replay a recorded control-contract violation | Historical fidelity can pass while contract conformance fails; do not label reproduction of the defect a valid business execution. |
| Change an operator so that a recorded transition differs, or omit a recorded required guard | Report the first material divergence or missing required invocation, rather than silently accepting the old history. |
| Missing evidence, model output, graph version, or controller artifact | Report the precise replay limit; do not invent the missing data. |
| Unexpected tool arguments or changed workflow version | Refuse to match an unrelated recorded response. |
| Child workflow resume and duplicate completion delivery | Preserve parent/child identity and consume the intended result once. |
| Replay context attempts a real write or credential issuance | Execution-boundary isolation prevents the effect. |
| Authorized reevaluation takes an unrecorded branch | Stop or use an explicitly labeled offline fixture; preserve the original run. |
| Authorized live recovery | Use current checks and original operation identity; remain distinguishable from replay. |
| Audit correction or artifact alteration | Preserve original history and correction provenance; the chosen integrity mechanism exposes unauthorized alteration within its stated guarantees. |

Before implementation, decide replay granularity, retained artifacts and duration, the comparison contract, controlled scheduling/event semantics, and the storage/execution isolation mechanism. These choices apply to loops and workflows as well as graph edges.
