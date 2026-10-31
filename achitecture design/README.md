# NGA Architecture

Start with [07 — NGA Architecture and Minimum Java SDK Proposal](07-nga-architecture-proposal.md). This is the single current architecture proposal for collaborators and implementers.

The proposed first deliverable is an embeddable Java SDK on openJiuwen, an openJiuwen adapter, a Spring Boot Starter, a credit reference application and a conformance/failure suite. The proposal covers agent evolution across three states and four planes, S1/S2/framework authority, identities, business APIs, extensible primitives, persistence/recovery, replay and the minimum acceptance gate. It distinguishes established requirements from the implementation target and unresolved qualification choices.

| Document | Role |
| --- | --- |
| [07 — Architecture and minimum Java SDK proposal](07-nga-architecture-proposal.md) | Canonical architecture and implementation scope; update this document in place. |
| [05 — Original architecture brief](05-architecture-brief-and-decisions.md) | Preserved V0 source input in its original language and context. |
| [06 — Original architecture diagrams](06-architecture-diagrams-md.md) | Preserved V0 source diagrams; not the current NGA design. |

The [overall design](../design/nga-overall-design.md) defines NGA's three-project program. Model research protocols and results remain in their existing research directories.

## Maintenance

- Maintain one current proposal rather than adding numbered iteration documents.
- Keep exploratory drafts in the locally ignored architecture-history directory. Git history also preserves earlier published versions.
- Preserve 05/06 as source snapshots. Their implementation claims are not NGA implementation evidence.
- Keep new artifacts in English. State established requirements, proposed implementation and verified results distinctly.
- Change the proposal, its diagrams, reference application and acceptance evidence together when the public architecture changes.
