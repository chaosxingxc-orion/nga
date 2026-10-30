# NGA Architecture Analysis: From Governed Execution to Stable Decisions

> Date: 2026-10-30.
> Basis: [V0 brief](05-architecture-brief-and-decisions.md), [V0 diagrams](06-architecture-diagrams-md.md), and [NGA overall design](../design/nga-overall-design.md).
> Premise: the required Jev-like decision capability is available within its declared scope.
> Status: analysis and recommendations; the corresponding architecture is a [V0.1 discussion draft](08-nga-architecture-v0.1.md).

## 1. What the model assumption changes

V0 provides a useful enterprise structure: a user initiates a task, capabilities declare contracts, the control plane limits authority and resources, and adoption and execution create an accountability trail. Keep that structure.

A capable S1 adds a reusable way to apply business semantics to evidence. It enables a faster path for decisions whose rules and evidence are already established, and a defined interface through which S2 can obtain judgments while investigating or planning.

It does not decide which business specification is authoritative, establish that all required evidence was supplied, grant permission, serialize concurrent adoptions, or make external effects idempotent. Those remain architectural responsibilities even under the favorable model premise.

The central optimization is therefore to add a **governed decision lifecycle inside V0's management/control/execution structure**. S1 is a semantic decision capability; S2 is a reasoning and planning capability; the framework controls their invocation and the transition from a judgment to an effective business decision and action.

## 2. Retain, refine, and add

| V0 element | Assessment | Proposed NGA treatment |
| --- | --- | --- |
| Capability contracts: provides / requires / effects / bounds (§4.3) | Useful execution and authority boundary. They do not fully specify business decision meaning. | Retain; reference a separate versioned semantic specification and its adoption policy where judgment is required. |
| Management / control / data views (§4.2) | Suitable organizing structure. These need not be separate services. | Retain; place semantic-specification governance in management, adoption authority in control, and model invocation in execution. |
| Deterministic control (§4.2) | Necessary for repeatable transitions and enforceable authority. It cannot supply all business semantics by itself. | Deterministic code consumes validated S1 observations under a published adoption policy; S1 cannot override an authorization denial. |
| Execution graph and delegation (§4.4) | Useful for bounded work, but data dependencies and authority lineage have different meanings. | Track the execution/evidence graph separately from delegation lineage. A shared result must not merge its producers' permissions into the consumer's grant. |
| Draft / seal / reveal and work pools (§4.6) | Useful visibility controls. Isolation alone does not establish independent errors or a correct verifier. | Retain as candidate mechanisms; record the evidence actually visible at each judgment and verification step. Changed visibility creates a new evaluation where material. |
| Adoption as an event (§4.7) | Strong starting point, but an event appended after a side effect cannot prevent duplicate execution. | Make adoption a guarded state transition with an immutable decision record; bind dispatch to that record and a stable operation identity. |
| Context interface (§4.5, §5) | V0 explicitly leaves important context work unfinished. | Define evidence requirements, source authority, freshness, visibility, and provenance before a decision frame becomes evaluable. |
| Version pinning and live authorization (§4.2, §7.1–2) | Historical attribution and current permission are distinct requirements. | Preserve evaluation versions; check current permission and action preconditions at dispatch. Old approval cannot restore revoked authority. |
| Accountability anchors (§4.7) | Actor and accountable user should remain distinct. | Also record specification author/reviewer, adoption authority, and executor. A user anchor does not erase responsibility for faulty policy or implementation. |
| Semantic gray areas | Not a complete V0 subsystem. | Project 3's knowledge engineering publishes explicit conventions and resolution paths; projects 1 and 2 consume them. |

## 3. Why a reliable S1 is insufficient on its own

| Failure path | How business behavior can still drift | Required architectural response |
| --- | --- | --- |
| S2 changes the question | A different wording can introduce a different criterion or omit an exclusion. | Bind judgments to a published question/specification identity and validated parameters. Material semantic changes require a new version or frame. |
| S2 selects different evidence | Two correct judgments over different evidence can disagree. | Specify required evidence and coverage, preserve its snapshot, and treat material additions/removals as revisions. |
| S2 decomposes a rule incorrectly | Individually correct subjudgments can omit a veto or compose incorrectly. | Use reviewed decision dependencies and an explicit composition/adoption contract; test decomposed and direct paths for agreement. |
| S2 replans after an adopted decision | A new plan can quietly reopen a settled outcome or submit it again. | Bind plans to decision dependencies; revisions cannot overwrite adoption or mint a new identity for the same business operation. |
| Two workers finish together | Both can append a plausible adoption and dispatch an action. | One guarded adoption per decision revision; losing workers read the winner or expose a conflict. |
| A timeout follows successful execution | A retry can duplicate an external effect. | Preserve operation identity, distinguish attempts, and reconcile completion before retrying when the outcome is unknown. |
| A new model or policy is deployed | Fresh inference may differ from the original decision. | Replay preserved observations and adoption rules; make fresh evaluation a separate, linked operation. |
| A rule is incomplete | The model can be asked to invent an omitted convention. | Route the issue through a declared exception path and project 3's semantic-governance workflow. |

Stability must be assessed at the effective decision and business-result boundaries. Requiring identical S2 prose or an identical plan is unnecessary when alternative plans implement the same adopted decision within the same constraints. Conversely, a repeatable S1 answer is insufficient if a plan changes the effective meaning or action.

## 4. Corrections needed before implementation

### 4.1 Budget aggregation needs units

The V0 brief (§4.4) says to sum sequential budgets and take the maximum for parallel budgets, while also discussing partitioning several resource types. A single composition rule cannot serve all of them.

- **Total cost, tokens, tool calls, and attempt allowances:** aggregate consumption across all branches, including S1, S2, verification, and retries. Two parallel calls costing 4 and 6 units consume 10 units, not 6.
- **Elapsed time:** propagate deadlines. A maximum of parallel durations describes an ideal critical path under stated scheduling assumptions; it is not a universal runtime bound.
- **Concurrent activity:** constrain simultaneously active work over the relevant scope.
- **Delegation count/depth:** enforce explicit structural limits.

Reservation, consumption, release, and retry accounting need idempotent records. Partitioning a budget at issuance does not by itself prevent duplicate grants, repeated consumption, or excessive child creation.

### 4.2 Three graphs answer different questions

The task/delegation tree answers who may authorize a child. The execution graph answers what can run next. Evidence and decision dependencies answer which facts and conclusions were consumed. Their identifiers can relate without forcing the structures to be identical.

This matters when one sealed result feeds several decisions, when a decision is revised, or when execution is resumed. Sharing evidence is not delegation of authority; reevaluating one downstream decision need not invalidate unrelated work.

### 4.3 Approval, sealing, and execution are distinct

A sealed result is immutable, not necessarily correct or adopted. Adoption makes an outcome effective under a named policy. Dispatch still requires current authorization and valid execution preconditions. A successful tool response must be linked to the intended operation before the business outcome is recorded.

The reference walkthrough's single final bookkeeping step is too coarse for recovery: durable intent and transition records are needed around adoption and dispatch, not only after the task completes.

### 4.4 A diagram cannot settle a pending decision

The V0 diagrams show short-lived tokens, while the brief lists the trust root, freshness route, and token design among pending questions. Preserve both source documents and label that discrepancy. NGA can specify current-authority checks and stable operation identity without choosing a token format or lifetime.

Likewise, an isolated verifier does not automatically become a qualified business decision-maker. Its scope, evidence, outputs, and adoption role require a contract.

## 5. Recommended first optimization

Use a **contract-bound fast path** when the task has an approved semantic specification and sufficient evidence. Invoke S1, apply the published adoption policy, then execute only the authorized action bound to that adoption.

Use an **S2-assisted path** when evidence gathering, decomposition, explanation, or planning is needed. S2 operates through admitted capabilities and returns proposed artifacts. It cannot alter the authoritative business question, remove a required veto, or turn an unresolved case into approval.

Both paths meet the same adoption and execution boundary. For a case eligible for both, equivalent evidence and the same specification should produce the same adopted business outcome. This is an acceptance requirement for the architecture, not an established result.

The [V0.1 draft](08-nga-architecture-v0.1.md) proposes the contracts and recovery behavior needed to make these paths concrete. It keeps the first business scenario, S1 insertion point, decomposition mechanism, and technologies open.
