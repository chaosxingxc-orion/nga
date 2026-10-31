# NGA and Enterprise IT: Business Capability and Authority Boundaries

> Date: 2026-10-30.
> Status: the business-capability/IT-authority boundary is the owner-accepted working premise for the resumed identity discussion. Detailed mechanisms, provider guarantees and integration implementations remain proposals requiring qualification.
> Premise: the existing enterprise IT system owns its business data and enforces its domain rules, including authoritative credit/exposure controls in the supplied example.
> References: [V0.2](13-nga-architecture-v0.2.md), [framework core](18-framework-core-and-case-coverage.md), and [discussion register](16-architecture-discussion-register.md).

> Subsequent owner direction: use this business-capability/IT-authority boundary as the basis for the resumed AQ-01/AQ-02 discussion. [Document 20](20-task-decision-request-identity.md) develops task, decision and request continuity within it. The general boundary is now the working premise; detailed mechanisms and provider guarantees still require qualification.

## 1. Recommended default: invoke business capabilities

NGA should normally invoke **authorized, semantically defined business operations** exposed by the enterprise system. It should not use a generative model to edit the system's underlying fields as a substitute for those operations.

For example, submitting an application or a qualified decision artifact through a defined operation preserves the system's validation, authority and execution path. Setting an approval field and reducing a balance directly can bypass that path. The important distinction is the business capability boundary, not HTTP versus SQL: a generic field-update API can bypass business invariants too.

The owning system may expose synchronous commands, asynchronous jobs, events or another supported integration. Protocol selection remains open. An agent embedded inside that system can still invoke its controlled application/domain services; shared deployment does not transfer unrestricted data-write authority to the model.

Authorized database administration, migration or repair is a separate governed capability with a different contract. NGA's own task, judgment and trace storage is also distinct from an external system's authoritative business records. These distinctions do not imply that every possible agent use case must be read-only or remote.

This recommendation follows the principle that a service owns its domain data and exposes the relevant capabilities while preserving a source of truth; it does not require NGA or its integrations to adopt a particular microservice deployment. See [Microsoft's data ownership guidance](https://learn.microsoft.com/en-us/azure/architecture/microservices/design/data-considerations).

## 2. Opaque implementation, explicit contract

The agent does not need the business system's table layout, lock strategy, internal service topology or complete risk algorithm. It needs a contract sufficient to choose and use the capability correctly.

| Contract information needed by NGA | Implementation detail that can remain internal |
| --- | --- |
| Business meaning of the operation; intended effect and scope | Tables, field layout and internal mutation sequence |
| Material inputs, evidence/decision requirements and caller authority | Internal policy-engine organization and storage mechanisms |
| Accepted, pending, rejected, completed and unresolved result semantics as applicable | Internal queues, threads, locks and transaction structure |
| Request/operation correlation, retry rules, deduplication scope and status lookup | How the server persists or coordinates those guarantees |
| Supported cancellation, amendment or correction requests and their limits | The owner's internal recovery implementation |
| Versioned public behavior and observable audit references | Undisclosed proprietary rules or internal execution traces |

The complete internal logic need not be visible, but an operation cannot be an unexplained name plus arbitrary text if NGA is expected to use it reliably. Where the contract does not provide needed status or retry guarantees, expose that limitation. NGA cannot infer missing guarantees by inspecting a successful example.

An acknowledgement that a request was accepted is not automatically a business approval or a completed effect. Consume the provider's declared states. A timeout does not establish either success or failure.

## 3. Allocate authority by layer

| Layer | Owns | Does not acquire automatically |
| --- | --- | --- |
| **Jev / S1** | Typed semantic judgment under a specified, supported and delegated question. | Authority to edit external business data, override system rejection or commit the provider's transaction. |
| **Agentic model / S2** | Interpretation, investigation, candidate plans and adaptation within admitted capabilities. | Permission to bypass an API refusal, invent an alternative write path or make generated claims authoritative. |
| **NGA framework** | Agent task/run state, bound judgment basis, local/delegated decision adoption, capability admission, request identity, invocation/recovery policy and trace. | Ownership of the provider's hidden rule engine, aggregate allowance ledger or authoritative external business state. |
| **Business IT system** | Its business records, authoritative domain constraints, caller validation, transaction commit, server-side duplicate handling and operation outcomes under its contract. | Proof that every caller's interpretation of a business request was semantically correct. |

NGA's adoption record establishes the effective local/delegated decision at its own boundary. It must not be presented as an external approval or completed transaction unless the authority contract and provider response support that claim. Agent run identity can link to a provider-owned application identity without becoming a competing system of record for that application.

### 3.1 Two legitimate judgment arrangements

**The business system already owns the decision.** NGA prepares admissible inputs and invokes the decision/application capability. Jev can help with evidence interpretation, semantic routing or another useful declared question; duplicating a complete deterministic decision engine in Jev is not a requirement.

**The business system explicitly delegates a semantic judgment to NGA.** Jev can supply an authoritative typed input or delegated decision artifact under that contract. NGA binds its evidence, specification, model and adoption authority. The business system consumes the artifact, verifies the delegated scope and remaining conditions, and owns the business-state commit. S2 cannot silently reinterpret the adopted Jev result into another decision.

The second arrangement gives Jev a substantive decision role, not merely an advisory score. Which questions are delegated must be explicit. It does not follow that every business rule moves into the model, or that an existing risk system must be reproduced inside NGA.

### 3.2 Why API integration does not eliminate NGA's decision problem

When an API accepts several business-valid alternatives, two inconsistent model interpretations may produce two different requests that both pass server validation. Server-side data integrity does not by itself prove adherence to the user's intent or consistency of the delegated judgment.

NGA therefore still needs bound semantics, stable observation consumption, constrained request formation and a trace from intent/evidence to the actual request. The business system's final checks and the model/framework's semantic obligations solve different parts of the problem.

## 4. Correct the shared-constraint ownership in document 18

The owner's shared-preapproval example establishes that separate cases can be related through a business constraint. It does not imply that NGA should create a second allowance engine or coordinate all banking writers.

If the business system owns the aggregate limit, it must enforce that limit across its supported agent, human and batch callers. NGA can read an exposed view for planning, but a local snapshot or a lock around NGA workers cannot protect against another caller changing the authoritative state.

**Revised boundary:** NGA routes admitted requests through the owning capability and respects its outcomes; the business system enforces its shared business constraints at its authoritative execution boundary. NGA retains its own agent-level budgets, permissions and concurrency controls. Those are not a replica of the customer's credit allowance.

If a new application has no domain component capable of enforcing a required invariant, that is a business-service/integration gap. It may require engineering a qualified domain capability, but must not be treated as something an agent framework or model score automatically guarantees. Cross-system operations likewise require declared composition and recovery contracts rather than an assumed transparent transaction.

## 5. Idempotence, status and replay cross a contract boundary

| Property | NGA responsibility | Business-system responsibility |
| --- | --- | --- |
| Decision consistency | Bind the delegated question, evidence and actual judgment; prevent ungoverned reinterpretation or answer-shopping. | Supply/consume its declared domain semantics and recognize the decision authority it delegates. |
| Request continuity | Preserve the operation identity and material request across supported retries; distinguish genuinely new intent. | Detect duplicates within the promised scope/window and handle conflicting material parameters according to its contract. |
| Effect integrity | Do not bypass admission or resend a confirmed effect as new intent; reconcile uncertain responses. | Enforce domain conditions and commit authoritative state with the promised server-side consistency and duplicate handling. |
| Outcome visibility | Distinguish request admission, business decision and execution completion; retain provider references. | Return declared status/results or a supported operation-query/event mechanism. |
| Replay/audit | Reproduce NGA control behavior with recorded model and provider responses; intercept live effects. | Own internal business audit and any internal replay capability; expose authorized correlation/evidence where supported. |

Safe retry requires both the caller's continuity and the service's guarantees. An idempotency key generated by NGA alone does not create a server-side guarantee. [AWS's idempotent API discussion](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) describes request identifiers, service-side handling and the difference between duplicate delivery and new intent.

NGA can replay why it chose an operation, the request sent and the response consumed. It cannot claim to replay an opaque provider's internal transaction just because it has an API log. Full cross-system investigation joins the respective records through supported correlation; missing internal evidence must remain an explicit scope limit.

## 6. Implications for Graph, Agent Loop and Workflow

The composable unit is an admitted capability with a meaningful contract. A graph may include semantic judgment, bounded investigation, workflow invocation, a business-system command, waiting for completion or querying status. It need not expand a provider's internal workflow into NGA nodes.

An agent loop can discover/select a registered capability and propose a call. A published workflow can compose these calls. The framework enforces invocation authority and continuity, while the provider retains control over its business operation. An API business refusal follows the declared handling path; S2 cannot evade it by selecting a generic database-write tool.

In development, register and test capability contracts and delegated judgment scopes. In runtime, execute admitted calls and preserve actual responses. In operations, correlate agent traces with provider outcomes and evaluate improvements. Across the four planes, management owns NGA's capability definitions, runtime executes calls, control admits them and the user plane reports their real status. Agent evolution cannot silently change the provider's business policy or widen a capability's authority.

## 7. Proposed adversarial checks

These are design checks, not executed integration tests:

| Counterexample | Required distinction |
| --- | --- |
| A tool exposes arbitrary approval/balance field updates over HTTP | API transport alone is insufficient; require a business operation that preserves the owner's enforcement path. |
| Two NGA workers see available allowance while a human channel consumes it | The provider's authoritative commit must arbitrate; NGA's cached view cannot guarantee the aggregate invariant. |
| Two semantically inconsistent but individually valid requests pass API validation | Preserve the independent need for Jev/NGA judgment and request consistency. |
| The provider accepts a job and later rejects the application | Record accepted/pending separately from approved/completed; do not announce success on acceptance. |
| An effect commits and the acknowledgement is lost | Use the provider's declared duplicate/status contract; never treat timeout as permission for a fresh operation. |
| An authorized Jev judgment is consumed by the business system | Preserve its decision role and provenance while keeping final business-state commit in the owning system. |
| Historical NGA replay reaches a business-system call | Supply the recorded response and block real dispatch; do not imply visibility into provider internals. |

The next design focus should be the **business capability contract and delegated decision boundary**: what NGA may decide, what it may request, what the provider guarantees and how outcomes are observed. Detailed domain ledger design and low-level field manipulation are outside the default agent-runtime scope.
