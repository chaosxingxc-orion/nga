# AQ-01 / AQ-02: Credit Scope, Identity, and Decision Revisions

> Date: 2026-10-30.
> Status: adversarial discussion draft. AQ-01 and AQ-02 remain OPEN; the recommended boundaries below are not yet approved business conventions or implemented guarantees.
> Sources: [discussion register](16-architecture-discussion-register.md), [credit walkthrough](10-credit-decision-walkthrough.md), [control review](15-graph-loop-workflow-control-review.md), and [replay contract](12-replay-and-audit-contract.md).
> Premise: Jev meets its declared semantic judgment contract. This review concerns business identity, changes of basis, and execution correctness around that model.

## 1. Proposed first business boundary

The proposed first slice is:

**Receive an identified unsecured-credit application → obtain the required evidence → judge eligibility and the approved limit → adopt the decision → register the initial limit for the intended credit relationship → confirm the external result and expose the decision and execution status.**

This exercises both decision idempotence and external-effect handling. Eligibility advice alone cannot demonstrate the latter. Pricing, agreement execution, disbursement, repayment and collection are separate business procedures. Their omission from this first slice is a scope proposal, not a statement that they are unnecessary in a real product.

The original three rules remain unchanged. Use the illustrative R1 conventions and A001 fixture in document 10: assets of 40 million in the approved unit, no overdue condition in the required recent window, adequate historical coverage and no historical veto. The expected initial judgment is USD 50,000. Currency conventions, exact duration definitions and uncovered asset bands still belong to the governed specification.

### 1.1 The target of the grant must be decided

There are two different business interpretations:

| Interpretation | Consequence for two applications |
| --- | --- |
| One credit relationship for the customer under the relevant product/business scope | A new application does not automatically entitle the caller to create a second relationship or add another USD 50,000. Existing credit and concurrent applications need an explicit eligibility/uniqueness rule. |
| Each independently authorized application can establish a separate credit relationship | Multiple facilities may legitimately coexist. They still need application-level deduplication and any applicable aggregate exposure controls. |

**Proposed starting scope:** one intended credit relationship in an explicitly identified institution/tenant, customer and product scope, initially demonstrating creation when no conflicting relationship exists. The exact business uniqueness scope remains to be agreed; customer/product fields alone are not declared universally sufficient.

The operation must say whether it **creates an initial limit**, **sets an existing limit to a target**, or **adds an amount**. These are not interchangeable. In particular, "grant USD 50,000" must not silently become "increase available credit by USD 50,000 on every successful run." For this draft, the operation is initial registration of the intended relationship with a USD 50,000 limit. Changing an existing limit needs a separate amendment contract.

Deduplicating one application does not enforce all customer-level exposure constraints. Two valid applications can each execute once and still violate a business rule about total credit. Any claimed customer/product guarantee requires its own cross-application admission and resource contract.

### 1.2 Completion has two distinct outcomes, plus unresolved work

| Case | Business decision | External operation | Closure of this initial slice |
| --- | --- | --- | --- |
| Valid refusal | Adopted refusal under its recorded basis | No grant dispatched | Refusal completed, with an attributable basis and visible status. |
| Valid grant | Adopted grant under its recorded basis | Intended initial limit authoritatively confirmed | Grant execution completed. |
| Missing evidence or undefined business meaning | No eligible final adoption, or an explicit hold/review state | No newly admitted grant | Waiting/resolution path; do not label this a completed valid refusal unless the business policy explicitly defines refusal. |
| Grant adopted, delivery outcome unknown | Historical adoption remains identifiable; current validity/holds are separate | Unresolved | Reconciliation remains open even if a worker or workflow run has stopped. |
| Withdrawal or expiry | Treatment specified by the applicable policy | Outstanding effects still require reconciliation | Can close only under that policy, without claiming an in-flight effect disappeared. |

Keep application/work status, decision status and external execution status distinguishable. "The workflow stopped," "the decision was withdrawn" and "no credit exists externally" are different assertions.

Later evidence can trigger a linked review after the initial slice completes. A completed initial registration does not make future corrections impossible; it changes their business purpose and authority. Continuous monitoring and the corrective process need separate contracts and cannot silently rerun initial registration.

## 2. Identity: one application can contain several decision revisions

| Logical identity | What it identifies | What does not create another one |
| --- | --- | --- |
| Submission/request identity | A particular transport command and its immutable request parameters within a declared scope | Network redelivery of that command. |
| **Application A001** | An authoritative instance of business intent in its customer, product and institutional scope | A new browser channel, worker, model call, plan shape, retry or supplement to this same application. |
| Decision purpose within A001 | The question being decided, such as initial eligibility/limit | A different implementation of the same question. Reviewing an existing facility is a different purpose. |
| **Frame F1** | The immutable judgment basis: relevant application inputs, effective specification/adoption contract, consumed evidence, reference time and validity conditions | Merely receiving another document that is not admitted as a replacement of the basis. |
| **Decision D1** | An adopted result for a purpose and frame, with its observations, authority and effective-state history | A second model response or explanatory rewrite. |
| **Plan P1 / P2** | How admitted work is organized and performed | No new business entitlement follows just because its version changes. |
| **Operation OP1** | A particular intended external business effect, bound to its target, purpose and material parameters | A retry, restarted workflow or new graph node requesting that same effect. |
| **Attempt ATT1 / ATT2** | One delivery/execution attempt for an operation | Attempts do not acquire independent entitlement to create a second effect. |

These are logical distinctions, not a frozen schema or requirement for eight services. Framework-owned identity resolution and transition rules must make the distinctions enforceable.

### 2.1 What counts as the same application?

The primary criterion is continuity of the authoritative business intent, not similarity of text or equality of input data.

- Reopening a page, changing channel, retrying submission or supplementing A001 continues A001 when an authoritative link identifies it.
- A new transport key does not prove a new application. Prefer the upstream application identity or an explicit lookup/resume relationship.
- If two channels submit similar requests without a shared authoritative identifier, treat duplicate detection as a resolution problem. Jev/S2 can assist matching, but similarity alone cannot silently merge them or authorize a second grant. A published business rule may serialize or restrict active applications in a defined scope; that rule is still to be chosen.
- A legitimately new application is created through an explicit authorized new-intent operation under the business policy. Similar evidence or an identical expected amount does not make it a duplicate automatically.
- Same transport key with changed command parameters is a conflict. A supplement or amendment is a new command linked to A001, not a mutation of the original submission receipt.
- Withdrawal, appeal, renewal and reopening require declared relationships. S2 cannot create A002 merely to escape a refusal, hold or unresolved OP1.

The candidate key `(customer, product, date)` is insufficient as a universal answer: two distinct applications can occur on one day, and a retry can cross midnight. An arbitrary new UUID is also insufficient because it creates uniqueness without establishing continuity.

### 2.2 What counts as the same decision?

Distinguish three meanings:

1. **Same decision purpose:** initial eligibility/limit for A001. It may be evaluated under several frames.
2. **Same decision revision:** the adopted D1 tied to F1. Repeating the unchanged request resolves to this revision and its current lifecycle status; it does not create D2 just because the model ran again.
3. **Same outcome:** both D1 and a later D2 say USD 50,000. Equal amounts do not prove identical evidence, meaning, authority or revision.

For one purpose, the proposed contract permits one current effective adopted revision, or an explicit unresolved/held/expired state. Supersession preserves D1 and its history; it does not edit D1's original amount or basis. The authoritative record must distinguish a new observation, an evaluated candidate and an adopted decision.

Historical retrieval of D1 returns D1. A current-status query can report that D1 has been superseded and show D2. A duplicate request must not present a new revision as though it were the original result, nor present an obsolete approval as current executable authority.

**A changed decision is not automatically a new effect.** The initial-registration purpose for the intended credit relationship remains protected across decision revisions. If it already completed, adopting or evaluating another grant does not authorize another initial registration.

## 3. Classify changes before changing identity or authority

**New artifact → admitted change of basis → evaluated result → adopted revision → admitted external effect** are separate transitions. None automatically implies the next.

| Incoming event | Same application? | Judgment/frame handling | Execution handling |
| --- | --- | --- | --- |
| Same submission arrives again | Yes, once identity is resolved | Reuse the original eligible result/status; no mandatory model invocation | Return/reconcile OP1; do not create another grant. |
| Same evidence arrives in a different format | Normally yes | Record provenance; retain F1 if the approved equivalence rules establish that the effective basis is unchanged | No new effect. A hash mismatch alone is not a material-change rule. |
| New material evidence is admitted | Normally yes | Preserve F1; bind F2 for the changed basis and reestablish adoption eligibility | Assess hold/revision against OP1's actual phase. |
| Supporting document is stored but not consumed as a new basis | Yes | Link it as an observation/supporting artifact; do not rewrite F1 | No automatic execution change. Its relevance/freshness still needs the declared intake policy. |
| R2 is published but does not apply to A001 | Yes | Keep the applicable R1 binding; publication alone does not require reevaluation | Continue only if existing validity and current execution conditions hold. |
| A new applicable rule is admitted for A001 | Yes | Bind a new rule/basis revision and apply its migration/hold policy | No blind reuse of old executable authority or creation of another grant. |
| S2 changes collection order or workflow layout | Yes | P2 can retain F1/D1 when protected inputs, meaning and conditions are unchanged | Preserve OP1 and its parameters. |
| A plan patch changes required sources, candidate meanings or the effective time | Yes unless a genuinely new business intent is separately admitted | It is not merely a plan edit; require the relevant evidence/semantic/revision path | Reject a disguised bypass or hold for resolution. |
| A model/readout implementation changes | Yes | Qualify the implementation under release policy; a comparison run alone cannot replace D1 | No new business entitlement. Historical replay uses the recorded output. |
| An execution attempt times out | Yes | This is not new business evidence and is not a credit refusal | Mark completion unresolved; preserve OP1 and reconcile. |
| A genuinely new business application is admitted | No; create its own A002 | Establish its own purpose and valid basis, even if its outcome matches A001 | Check existing credit/exposure and the intended target; a new application ID alone does not authorize duplicate credit. |

Materiality and equivalence belong to the published business/evidence contract. S2 cannot declare its own change irrelevant in order to bypass admission. A changed exact input value can preserve the output while still requiring a new frame when it is consumed as the revised factual basis. Conversely, a formatting-only change need not cause endless reevaluation.

## 4. New evidence: when it arrived is not when the fact occurred

Use three illustrative cases under unchanged R1:

- **Duplicate/corroborating material:** another rendering of the same covered asset/history evidence. Record it without automatically adopting a new decision.
- **A changed consumed fact with the same outcome:** an authoritative update from 40 million to 45 million is admitted as the new asset basis. Preserve F1, evaluate F2 as required, and expect the same USD 50,000 band under the fixture. If D2 is adopted, its distinct basis does not justify another initial credit registration.
- **A changed consumed fact with a different outcome:** a verified correction from 40 million to 0.8 million moves the fixture to the USD 10,000 band, assuming the historical veto remains false. Newly established historical overdue satisfying R1's veto instead requires the corresponding refusal judgment. Both are legitimate distinctions, not failures of consistency.

The last two are assessment examples. The original three rules do not specify how to reduce, cancel or otherwise correct an already registered facility; no correction permission is invented here.

An old overdue event discovered today may belong inside the original historical decision scope. An overdue event that actually occurred after F1's reference time may not belong inside the original judgment, although a current execution-validity policy may still require a hold or review. Preserve source/event time, observation time and the frame's reference time as applicable. Do not insert today's knowledge into a historical replay as though it was known then.

Late discovery can also reveal that the earlier source or its claimed coverage was wrong. Record the source/coverage correction and its effect on reliance; a consistent model does not establish the truth of external evidence, and the old coverage assertion must not be silently replaced in history.

### 4.1 Apply the change at the actual execution boundary

| Phase when material evidence is admitted | Required distinction and proposed handling |
| --- | --- |
| Before adoption | Invalidate stale adoption eligibility, bind F2 and evaluate. A worker returning O1 cannot adopt against an obsolete frame generation. |
| D1 adopted, OP1 not yet dispatched | A valid hold/revision must arbitrate with dispatch. If the hold wins, prevent stale delivery, evaluate F2 and adopt a permitted revision. Preserve D1. |
| OP1 in flight or result unknown | New assessment and investigation may proceed, but do not start a conflicting replacement operation on the assumption that OP1 failed. Establish external completion/cancellation and follow the resource contract. |
| OP1 confirmed | Preserve the initial decision and receipt. Open a linked post-completion review/correction purpose under its own authority; do not rerun initial registration. |

A provisional concern may trigger a hold if an authorized intake policy provides for it. An unsupported S2 assertion is not itself an adopted refusal or proof that an external operation has been canceled. The required verification and provisional-hold thresholds remain with AQ-04/AQ-06/AQ-11.

### 4.2 The same new amount has different operation consequences

If F2 still supports USD 50,000, retain the protected initial-registration purpose. An unchanged operation may proceed only after a permitted revalidation/authorization binding; if the adapter requires a different material request or does not support safe rebinding, keep it held and follow an explicit amendment protocol. Do not silently edit OP1's immutable request history.

If F2 supports USD 10,000 and OP1 was prepared for USD 50,000, do not send the same key with a changed amount. A replacement intent is admissible only after the old intent is demonstrably unable to execute and the application/target admission makes the two mutually exclusive. A local "canceled" flag alone is insufficient if an old worker or external request can still commit.

If OP1 already registered USD 50,000, a later USD 10,000 eligibility result does not mean "add another USD 10,000." It requires a distinct, authorized decision about the existing facility. Its correction identity links to OP1 without overwriting OP1 or borrowing a fresh initial-application identity.

## 5. Rule changes: publication, applicability and migration are separate

Changing a rule is not a technical retry. It is also not automatically a new application.

| Rule-change policy | A001 handling | Cost or unresolved requirement |
| --- | --- | --- |
| R2 applies only to new applications | A001 remains under the eligible R1 binding, subject to validity and live permissions | Define the authoritative application cutoff and handling of delayed/duplicate submissions. |
| R2 applies to pending, not-yet-adopted decisions | Bind F2 under R2; stale R1 candidates cannot win adoption | Define readiness invalidation and arbitration. |
| R2 applies to adopted but unexecuted grants | Hold/migrate/reassess under the declared policy before further dispatch | Define the adoption/dispatch cutoff and how existing intents are safely retained or superseded. |
| R2 requires review of existing facilities | Create linked review work for the already established facility | A new initial refusal label is not a revocation or correction of an external grant. Define that separate business procedure. |

These policies are alternatives to specify by change category, not defaults all enabled together. The owner must determine the scope of R2; S2 cannot choose R1 or R2 according to which gives a preferred outcome. "Use latest" and "pin forever" are both incomplete general rules.

Published time, effective time, application eligibility cutoff and execution-validity cutoff can differ. Moving the date of a retry must not silently reset the meaning of "past six months." Keep F1's reference time fixed; if the result expires or a required freshness check fails, enter an explicit renewal of the basis under the policy.

A permission revocation is also distinct from a changed credit rule. It may block execution of a still-valid business judgment without turning the customer into a credit refusal. Preserve the reason for the block.

## 6. Replanning and retrying: retain business meaning and operation continuity

### 6.1 Replanning

Replacing P1 with P2 may be legitimate when it changes how evidence is collected or invokes another qualified workflow while preserving the decision contract. It cannot reset the application, decision purpose, historical-veto obligation, adoption state or external-operation identity.

Moving a model call to a different node does not create a new decision. A workflow child and a parent loop requesting the same initial registration must converge on the same governed business intent. If P2 changes a material source, reference time, question meaning, candidate set or target resource, admit the relevant change explicitly rather than hiding it behind a new graph version.

The same operation key sent to a different institution or independent resource is not automatically deduplicated. Adapter or target changes require proof that the original effect cannot still occur and that the new path preserves the intended business effect and recovery scope.

### 6.2 Retrying

| Retry kind | Identity/basis to preserve | Allowed result |
| --- | --- | --- |
| Submission response lost | Original command and A001 linkage | Return the original receipt/result plus clearly labeled current status; do not create A002. |
| Model invocation fails | Same bound question/frame for a technical retry; new invocation/attempt record | Obtain a usable observation under the declared retry policy. Do not re-ask until the answer becomes favorable. |
| Adoption response lost | Same purpose, frame and expected revision | Read the existing adoption or explicit conflict; do not adopt a second independent grant. |
| Worker/child workflow restarts | Stable root/child/operation identities and consumed result bindings | Resume admitted unfinished work; confirmed steps stay confirmed. |
| External request acknowledgement lost | Same OP1 and immutable material parameters | Query/reconcile, or redeliver only within the resource's supported idempotency contract and current checks. |
| Old request retried after decision expiry or supersession | Preserve its historical identity and receipt | Show expired/superseded status and follow the authorized revision path; no blind dispatch under stale authority. |

The lifetime and scope of the resource's deduplication record must cover redelivery. A repeated OP1 after the resource has forgotten its key can be dangerous. A confirmed local result should be returned, not resent; an unresolved result beyond the supported window needs explicit reconciliation. A lagging "not found" response is not proof that an old request cannot still complete.

## 7. Adversarial cases that the earlier proposal must cover

These are proposed acceptance cases, not executed tests.

| Counterexample | Failure exposed | Required behavior / positive counterpart |
| --- | --- | --- |
| Same customer submits through two channels with unrelated transport keys | Per-request deduplication misses one business intent | Resolve authoritative application linkage or a declared conflict path. Still admit genuinely distinct applications when policy permits them. |
| Same customer/product submits again months later | An overbroad key permanently suppresses valid new work | Recognize a qualified new intent; inspect existing credit and current basis rather than reusing D1 blindly. |
| Assets change 40 → 45 million and both judgments are USD 50,000 | Same outcome is confused with same revision, or D2 creates OP2 automatically | Preserve the new admitted basis while preventing a second initial registration. |
| Corrected assets change 40 → 0.8 million | A cache suppresses a relevant distinction | Reevaluate the changed basis; the fixture's USD 10,000 result follows the appropriate phase-specific operation/review path. |
| Old historical overdue arrives while O1 is ready to adopt | A stale worker wins with an obsolete frame | Current-frame arbitration blocks stale adoption; a valid F2 can proceed. |
| Rule publication occurs between adoption and dispatch | Either latest-version drift or permanent stale-rule privilege | Apply the explicit effective-scope/migration policy and record which transition won. |
| A retry crosses the six-month boundary or a validity expiry | A hidden clock change is treated as unchanged replay | Preserve original reference time; explicit expiry/refreshed-basis handling governs live continuation. |
| A new graph or child workflow creates a new operation key | Structural novelty bypasses business deduplication | Preserve the intended effect and constrain duplicate initial registration across execution paths. |
| OP1 succeeds but its receipt is lost; D2 now recommends refusal | The UI says "no grant" while a facility exists | Display judgment and execution state separately; reconcile OP1 before choosing a conflicting correction path. |
| A locally canceled USD 50,000 intent is replaced by USD 10,000 while an old worker remains active | Two immutable keys still permit conflicting effects | Establish that the old intent cannot commit and enforce the target's conditional/uniqueness contract before replacement. |
| Two distinct A IDs each execute once against the same protected credit relationship | Request idempotence is mistaken for customer-level business correctness | Enforce the separately declared relationship/exposure constraint; legitimate separate facilities remain possible under their own policy. |
| A resource's deduplication record expires | Stable keys are mistaken for permanent external guarantees | Return confirmed results or enter explicit reconciliation; do not claim unsupported exactly-once behavior. |
| An operator's authority is revoked | Authorization failure is mistaken for customer ineligibility | Block unauthorized execution while preserving the business judgment and the actual reason for the hold. |
| A new model produces an attractive reevaluation result | A model release silently rewrites adopted history | Keep it in a separately identified evaluation/revision path; do not reset the business operation. |

## 8. S1, S2 and framework responsibilities in these changes

| Responsibility | Jev / S1 | Agentic / S2 | Framework and governed business contract |
| --- | --- | --- | --- |
| Application identity | May assist a declared semantic matching task | May request lookup/resume or clarification | Authoritatively resolve/link the application; neither model invents continuity or a new entitlement. |
| Evidence change | Judge semantic relevance or the business outcome where required | Locate evidence, identify possible conflicts and propose new inputs | Validate provenance/coverage, classify/admit the change, bind F2 and control stale eligibility. |
| Rule selection | Apply the supplied applicable definitions | Identify candidate applicable rules or flag uncertainty | Resolve effective applicability under publication policy; models cannot shop for a favorable version. |
| Plan revision | Optional specified checks on a proposed plan | Construct P2 within the admitted scope | Protect obligations, identities, active operations and revision boundaries. |
| Adoption and effects | Supply a required typed judgment | Request work, challenge or explain | Commit allowed revisions and operation intent, enforce current rights, reconcile receipts and preserve history. |
| Post-completion review | Evaluate a bound review question | Investigate and propose a permitted correction workflow | Separate original registration from review/correction purposes and admit the actual corrective effect if defined. |

The same division supports the three lifecycle states: development defines these contracts and adversarial cases; runtime applies them to A001; operations investigates late evidence, reconciles uncertain effects and proposes improvements. The user plane expresses intent and challenges, management maintains definitions/versions, runtime executes admitted work and control governs effectiveness. Evolution cannot erase an earlier basis or replay a real effect while testing an improved model or workflow.

## 9. Proposed resolutions and remaining owner choices

The following are **recommended answers for discussion**, not a closure of AQ-01/AQ-02:

1. Use eligibility plus initial registration of an identified credit relationship as the first complete slice, with refusal as a valid completed outcome and unknown execution kept explicit.
2. Identify the application by authoritative business intent and lineage, not by wording, channel, model run, graph node or arbitrary request UUID.
3. Distinguish one decision purpose from its frames, observations and adopted revisions. New material basis may require reevaluation even when the amount remains unchanged.
4. Treat new evidence and applicable rule changes as explicit basis/revision events; keep pure replanning and technical retries within the existing business identities.
5. A new decision revision does not automatically create a new external effect. Protect the initial-registration purpose and use phase-specific supersession or correction.

To settle these questions, the owner still needs to choose:

- **Credit relationship scope:** one relationship under the relevant customer/product scope, or independently permitted facilities per application; specify existing-credit and concurrent-application treatment.
- **Application continuity:** what creates a new intent, what resumes/reopens an old one, and how cross-channel submissions without an authoritative link are resolved.
- **Rule/validity migration:** which publication changes affect pending, adopted-unexecuted and completed work, and when the initial decision expires.
- **Post-completion correction:** who may review and correct an existing facility and what business operations are allowed. The original three eligibility rules do not define these permissions.

The last two choices require AQ-03/AQ-04/AQ-06/AQ-11/AQ-12/AQ-16 inputs. No new currency convention, exposure limit, correction permission or rule-effective-date policy is selected by the framework in this draft.
