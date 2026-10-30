# NGA Architecture Workspace

This directory holds the owner-supplied enterprise architecture baseline and NGA's subsequent analysis and revisions. The directory spelling is retained so existing local references continue to work.

## Reading order and document status

| Document | Role | Status |
| --- | --- | --- |
| [05 — Architecture brief and decisions](05-architecture-brief-and-decisions.md) | Original agent-festival architecture brief and nine decision requests. | Archived V0 source, retained as supplied in Chinese. |
| [06 — Architecture diagrams](06-architecture-diagrams-md.md) | Original overview, task walkthrough, and mechanism inventory. | Archived V0 source, retained as supplied in Chinese. |
| [07 — NGA architecture analysis](07-nga-architecture-analysis.md) | What survives the assumed availability of a capable Jev-like model; gaps and proposed corrections. | Analysis, 2026-10-30. |
| [08 — NGA architecture V0.1](08-nga-architecture-v0.1.md) | Proposed S1/S2/framework responsibilities, decision lifecycle, contracts, and engineering work packages. | Discussion draft; proposed mechanisms are not approved or implemented. |
| [09 — NGA architecture diagrams](09-nga-architecture-diagrams.md) | Views of the proposed architecture and its normal, revision, and recovery paths. | Companion to 08, with the same status. |

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
