# NGA Architecture Workspace

This directory holds the owner-supplied enterprise architecture baseline and NGA's subsequent analysis and revisions. The directory spelling is retained so existing local references continue to work.

**Current organizing view:** [V0.2 — three states, four planes, agent evolution](13-nga-architecture-v0.2.md). Read it with the [V0 adversarial review](14-v0-adversarial-review.md), which challenges both the supplied source and our earlier proposals. Development/runtime/operations are lifecycle states; user/runtime/management/control are responsibility planes; agent evolution coordinates the whole.

**Current discussion:** [Graph, Agent Loop, and Workflow control review](15-graph-loop-workflow-control-review.md) challenges their composition, decision-basis ownership, nested execution, and the S1/S2/framework authority boundaries. Its refinements are proposals, not a replacement of the established organizing axes or an implemented guarantee.

**Discussion agenda:** [Architecture discussion register](16-architecture-discussion-register.md) consolidates 18 open questions with options, proposed starting positions, closure evidence, dependencies and a suggested discussion order. Recommendations remain open until explicitly decided.

**Current design direction:** [Framework logic first, case coverage second](18-framework-core-and-case-coverage.md) records the owner's correction: define NGA's general invariants and configurable contracts, then test different cases. Independent cases may share constraints. The [credit review](17-credit-scope-identity-and-revision-review.md) remains an illustrative analysis; its earlier single-relationship starting scope is not a framework prerequisite.

**Current integration proposal:** [NGA and enterprise IT capability boundaries](19-business-system-capability-boundary.md) places NGA over authorized business operations while the owning IT system retains its domain rules, data and commit authority. It distinguishes delegated semantic judgment, request continuity and agent replay from provider-internal execution.

**Current AQ-01/AQ-02 discussion:** [Task, decision and business-request identity](20-task-decision-request-identity.md) applies the accepted integration boundary to task completion, question/revision identity, fixed requests and changes. Following owner feedback, normal execution waits for the API result; concurrent revision is an explicit branch, and cancellation/reversal requires native capabilities or qualified composition. Its eighteen adversarial cases keep provider internals outside NGA's design; detailed mechanisms remain proposals.

**Current runtime contract proposal:** [Framework primitives and API capability contracts](21-runtime-primitives-and-capability-contracts.md) separates execution primitives from provider guarantees and model judgments. It defines Graph/Workflow expressions for waiting, timeout, retry, cancellation and compensation, with twenty proposed adversarial cases and no engine selection.

## Reading order and document status

| Document | Role | Status |
| --- | --- | --- |
| [05 — Architecture brief and decisions](05-architecture-brief-and-decisions.md) | Original agent-festival architecture brief and nine decision requests. | Archived V0 source, retained as supplied in Chinese. |
| [06 — Architecture diagrams](06-architecture-diagrams-md.md) | Original overview, task walkthrough, and mechanism inventory. | Archived V0 source, retained as supplied in Chinese. |
| [07 — NGA architecture analysis](07-nga-architecture-analysis.md) | What survives the assumed availability of a capable Jev-like model; gaps and proposed corrections. | Analysis, 2026-10-30. |
| [08 — NGA architecture V0.1](08-nga-architecture-v0.1.md) | Earlier S1/S2/framework responsibilities, decision lifecycle, and contracts. | Earlier draft; its three-view organization is superseded by V0.2. Mechanisms require review and validation. |
| [09 — NGA architecture diagrams](09-nga-architecture-diagrams.md) | Current four-plane/evolution view, lifecycle matrix, and decision/recovery views. | Companion to V0.2; detailed mechanisms remain proposed. |
| [10 — Credit decision walkthrough](10-credit-decision-walkthrough.md) | Complete credit example: S1 participation, S2 change boundaries, adoption, retries, new evidence, and reconstruction. | Demonstration fixture and proposed contracts; no execution claimed. |
| [11 — Jev and agentic orchestration](11-jev-agentic-orchestration.md) | Compare loops, graphs, and workflows; typed nodes, semantic transitions, local S1/S2 cooperation, and architecture-driven model tasks. | Proposed reference organization; alternatives remain under evaluation. |
| [12 — Replay and audit contract](12-replay-and-audit-contract.md) | Historical inspection, executable control replay, reevaluation, live recovery, and audit evidence. | Replay/audit are required; mechanisms and acceptance contracts are proposed. |
| [13 — NGA architecture V0.2](13-nga-architecture-v0.2.md) | Three-state/four-plane matrix, integrated agent evolution, release continuity, and the credit lifecycle. | Current organizing proposal; axes are owner-defined, detailed mechanisms are proposed. |
| [14 — V0 adversarial review](14-v0-adversarial-review.md) | Source-linked findings, counterexamples, corrections, and acceptance obligations for V0 and our own drafts. | Design review; no implementation tests claimed. |
| [15 — Graph, Agent Loop, and Workflow control review](15-graph-loop-workflow-control-review.md) | Eight adversarial findings; decision-basis ownership, common execution contracts, three-state/four-plane responsibilities, logical interfaces, and governed evolution. | Discussion proposal; technology and topology choices remain open. |
| [16 — Architecture discussion register](16-architecture-discussion-register.md) | Eighteen open architecture questions, discussion sequence, decision evidence, three-state/four-plane coverage and deferred technical choices. | All items OPEN; recommendations are not approved decisions. |
| [17 — AQ-01 / AQ-02 credit scope and identity review](17-credit-scope-identity-and-revision-review.md) | Credit-fixture boundary, application and decision identity, material changes, rule applicability, replanning, retries and fourteen adversarial cases. | Corrected after owner feedback; business-specific scope is not a prerequisite for framework design. AQ-01 and AQ-02 remain OPEN. |
| [18 — Framework logic and case coverage](18-framework-core-and-case-coverage.md) | Stable core versus business contracts, independent cases with shared constraints, S1/S2/control roles and eight coverage patterns. | Framework-first method is owner-established; mechanisms and coverage expectations remain proposed. |
| [19 — Business-system capability boundary](19-business-system-capability-boundary.md) | Business-operation interfaces, delegated decisions, authoritative IT-system state, idempotent invocation and bounded replay visibility. | General boundary is the owner-accepted working premise; detailed guarantees, protocols and provider implementations remain open. |
| [20 — Task, decision and business-request identity](20-task-decision-request-identity.md) | Current AQ-01/AQ-02 proposals: task completion, decision questions/revisions, provider-request continuity, phase-specific changes and eighteen adversarial cases. | Working business-system boundary accepted; detailed identity/lifecycle policies remain OPEN and unimplemented. |
| [21 — Runtime primitives and API capability contracts](21-runtime-primitives-and-capability-contracts.md) | Primitive families, capability fields, Graph/Workflow operators, model participation, race/recovery semantics and twenty adversarial cases. | Proposed contracts; technologies and implementation guarantees remain open. |

The [NGA overall design](../design/nga-overall-design.md) remains the program-level source for the three projects and established principles. This directory develops the architecture for project 2 and its integration into project 3.

## Scope and source boundaries

For this architecture exercise, **assume a Jev-like model already meets the required semantic consistency, business-definition following, typed-output, and declared unresolved-case behavior within its supported scope**. This is a design premise, not a new experiment result or a claim that the repository's current models pass those requirements.

The original documents describe a different project context. Their statements about implemented schemas, tested examples, named hosts, external repositories, industry comparisons, and prior approvals retain their original scope. Those artifacts and evidence are not imported by archiving these two files. This revision does not independently verify their external-product claims. In particular, a mechanism drawn in 06 may still be pending in 05; the diagram does not resolve the decision.

S1 and S2 in the new NGA documents mean decision and reasoning capabilities. Do not infer those meanings from stage labels in the source roadmap.

## Maintenance

- Preserve 05 and 06 as source snapshots. Record corrections or departures in the NGA analysis and revision documents with source-section references.
- Keep new NGA artifacts in English. The two owner-supplied Chinese snapshots are a source-preservation exception.
- Separate established principles, assumptions, proposed mechanisms, and unresolved decisions. An architecture draft does not amend experiment protocols.
- Keep the explanation and diagrams aligned. Use an explicit revision when a change affects decision meaning, authority, adoption, execution, or reconstruction.
- Keep technologies open until requirements and integration evidence justify a choice. No host, model-serving topology, language, storage engine, authorization protocol, or token lifetime is selected here.
