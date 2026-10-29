# Work Plan: Four Exploration Directions as Assignable Work Packages

> 2026-10-29 · This file turns the four exploration directions the user set on 2026-10-29 into work packages for human engineers. It **assigns and sequences**; it does not replace the pre-registrations in [`00-research-proposal.md`](00-research-proposal.md). Where an item here repeats one from that file (R0-1 to R8-3), the short form below is a pointer and the wording in `00` governs. Where this file adds new pre-registered items, they are numbered **R3S1-n, R3S2-n, R3S3-n** (direction 3, stages 1 to 3) and **R4A-n** (direction 4). The prefix names the direction, not proposal round R3 or R4.
>
> Upstream basis: proposal §0 to §6; survey §2.2.1, §2.2.4, §2.2.5, §2.3, §5.1.4, §6.3.2, §6.5, §8.2.4, with single citations elsewhere where a number lives there. This file adds no claims about the literature. Every number is cited to the survey section or proposal round it comes from. Where the survey has no source for a claim, the text says so.
>
> The three hard rules of the proposal (§0) are admission conditions for every work package below:
>
> 1. **Registry row**: every measure names a row of the defect registry (survey §2.2.4), or it does not enter the plan.
> 2. **Unconstrained optimum**: every measure writes down its unconstrained optimum and the degenerate solution it must seal with a discrimination counterpart.
> 3. **Pre-registration**: every metric, equivalence class, held-out split and threshold is committed before the run; after the run only results are filled in.

---

## 1. Direction-to-round map

| Direction | Proposal rounds | Registry rows | Gate it feeds | What blocks it |
| --- | --- | --- | --- | --- |
| **1 Baseline report across the Qwen ladder** | R0 (all of it), R6-1 (`E-6.1`) | 6 (control), 11, 12, 16, 17, plus 1 via R0-3 | **G1**, partially: within-question invariance and the P2″ floor only | Block 1 (0.8B needs transformers 5.x); Block 2 (NPUs) for T4 to T7; the re-partition denominator is zero locally, so G1 cannot close here |
| **2 Missing objectives, synthetic data, configurable generalization** | R1, R3, R4 | 12, 17, 3, 1, 8, 5, 14 | **G1** (denominator data, `D-1.1`), **G2** | Block 3 (business annotation hours); Block 2 for R3 onward; no consistency-targeted training before G1 |
| **3 Intermediate typed states before the final judgment** | R5 (all of it), plus R2 for cost, R7-3 for the template contract | 10, 2, 11, 13, plus 4 | None directly; feeds the R6 endgame verdict and G3 (authors write intermediate questions) | Direction 1's T4 result (defect 11); G2 (semantics read at all); Block 2 |
| **4 Agentic Jev: agent integration and agentic RL on the interface** | R2 (`B-2.1`), R7 (`B-7.x`, R7-3, R7-4), R8 | 18, 13, 5, 7, 16, plus omission 2 | **G3** | The S1 position (open decision, §7); the RL half waits on direction 3 Stage 2; the verl environment (WP-0.1) |

---

## 2. Direction 1: baseline report across the Qwen ladder

**Objective.** Before any weight update, measure what the untuned backbones do on the interface fixed in survey §2.2.1. The output is **four consistency denominators side by side** (byte-level rerun, order permutation, answer-preserving adversarial variants, pre-registered equivalence classes; `E-0.2`), two degenerate baselines (empty input; question wording only), and the P2″ accuracy floor, all under the decision-level paired protocol. The ladder is Qwen3-0.6B (attention-only) against Qwen3.5-0.8B (hybrid), then Qwen3.5-2B / 4B / 9B. It is a **testbed for structural effects, not a scaled-down endgame** (survey §6.1.5; proposal §1).

**What the orchestrator changed relative to the user's framing, and why.**

- "Baseline report" is not an accuracy leaderboard. Aggregate accuracy hides the failure: across eight orderings accuracy moves less than 2 pp while the cumulative failure set grows 27% to 29% (proposal R0 protocol). Accuracy enters only as the P2″ floor (survey §2.2.5).
- Every invariance number is reported next to its degenerate baseline. A model that reads only the question wording passes both items of P1″ (survey §2.2.1, third exposure; §2.2.5 P2″).
- The ladder answers one question: do structural effects keep their **direction** across scale (R6-1)? At 27B the decision-tuning gain is 2.3 points and the new-schema gain about zero (survey §6.1.5), so small-model magnitudes do not transfer by assumption.
- **Limit stated up front.** The cross-question re-partition denominator is zero locally (survey §2.3 omission 1; §6.1.4.3). Direction 1 covers within-question invariance and the floor. **G1 closes only when direction 2 delivers the denominator data (`D-1.1`, WP-2.1).**

**Pre-registered conclusions** (all carried from `00`; no new items):

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R0-1 | Spread of consistency across the four denominators is at least 30 pp | If below 10 pp, the denominator dispute in P1″ is downgraded |
| R0-2 | Typed readout is more consistent than same-backbone label log-probability readout | **The motivation of P0″ / P1″ falls** (survey §8.2.4 item 1); pure cost route |
| R0-3 | Changing level names moves the readout distribution (flip rate above 5%) | Defects 1 and 17 do not hold on our backbone; R3 symbol tuning is cancelled |
| R0-4 | 0.8B hybrid is below 0.6B attention-only on low-salience bins, and the gap widens as salience drops | Defect 11 dissolves; direction 3's evidence states lose their reason (§4) |
| R0-5 | The union bound is not overturned in any cell | The foundation of P2″ / P3″ collapses (survey §8.2.4 item 3) |
| R0-6 | Untuned readout reaches 76% to 97% of decision-tuned | The SFT budget in direction 2 must grow |
| R6-1 | Structural effects keep their direction from 0.6B / 0.8B to 2B / 4B / 9B, magnitude shrinking | The ladder strategy fails; trials run directly at the large tier |

**Protocol and thresholds.**

- Equivalence classes are R0's two mechanical kinds only: eight irrelevant perturbations (T1, T3) and the Open-Jev synthetic counterfactual pairs. Business equivalence classes are not claimed (proposal §6 item 1).
- Consistency uses the decision-level paired protocol: cumulative failure set, equivalence-class flip rate, axiom violations. **Aggregate accuracy is never reported as a consistency metric.**
- Thresholds τ are fitted on held-out labels per (question, level-set version, rule version) triple, never on the test set (P3″).
- Every rung runs the **same frozen task files** (sha256 in `experiments/manifest.json`) and the same protocol commit.
- R6-1 direction test, to be committed in `E-0.2` before WP-1.8 runs: an effect "keeps its direction" at a rung when the paired difference has the same sign as at 0.6B / 0.8B. It is a **reversal** only when the 95% bootstrap interval excludes zero on the opposite side. An interval that includes zero counts as "no evidence", not as agreement.

**Degenerate-solution check.** Unconstrained optimum of every invariance check here: read only the question wording and ignore the input. Seal: report the empty-input and question-only baselines next to every consistency number. If a degenerate baseline's consistency is within 5 pp of the real model, that number is void (proposal R0). The discrimination counterpart of T1 is T2: after definition swap or level reorder the distribution **must move**.

**Work packages.**

| WP id | title | role | inputs | outputs | acceptance check | depends on | size (S/M/L) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-1.1 | Decision-level paired evaluation harness (`E-0.1`) | evaluation engineer (E) | record format in `experiments/README.md`; T1 to T3 files | harness code; cumulative failure set, flip rate, margin distribution | on a fixture with a known answer, every metric matches a hand count; a byte-level rerun gives identical output | none (CPU) | M |
| WP-1.2 | Four-denominator protocol, committed (`E-0.2`) | evaluation engineer (E) | proposal R0; this section | protocol file under `experiments/R0/` with equivalence classes, splits, τ fitting, the R6-1 sign rule | committed and tagged before the first scored run; later commits touch only result files | none | S |
| WP-1.3 | Same-backbone label log-probability baseline (`E-0.3`) | evaluation engineer (E) | WP-1.1; 0.6B and 0.8B weights | log-probability readout scored under the same protocol | same inputs, same τ procedure, same tables as the typed readout; decides R0-2 | WP-1.1, WP-0.1 for 0.8B | M |
| WP-1.4 | Degenerate baselines and P2″ floor (`E-0.5`, T5) | evaluation engineer (E) | typed-decisions, akhilaaa3, kev `binding-v1`, Open-Jev synthetic, bev | empty-input and question-only results; floor table | every consistency number in the report has its degenerate twin in the same row | WP-1.1 | M |
| WP-1.5 | T4 defect-11 control set (`D-0.4`) | data engineer (D) | typed-decisions; akhilaaa3; kev `binding-v1` | same input × N candidates, binned by salience of the required aspect | salience bins defined and frozen before scoring; at least three bins with enough items for a paired test | none | M |
| WP-1.6 | T1 to T3 runs on 0.6B / 0.8B (`D-0.1` to `D-0.3` data) | evaluation engineer (E) | built T1 to T3 files; WP-1.1; WP-1.2 | R0-3 and T3 invariance tables | runs on CPU or NPU with identical numbers within fp tolerance; T2 discrimination reported beside T1 | WP-1.1, WP-1.2; 0.8B needs WP-0.1 | M |
| WP-1.7 | Four-pillar reproduction (`E-0.4`) | evaluation engineer (E) | WP-1.1; proposal R0 | one-page reproduction status per pillar | the union bound is measured with the plainest threshold protocol **before** the harness is designed from it (proposal §6 item 5) | WP-1.1, WP-0.1 | L |
| WP-1.8 | Ladder sweep 2B / 4B / 9B and cross-scale direction (`E-6.1`, untuned part of `M-6.1`) | evaluation engineer (E) with training engineer (M) | WP-1.6 results; frozen protocol | per-rung tables; R6-1 verdict per structural effect | same task sha256 and protocol commit at every rung; the sign rule applied as pre-registered | WP-1.6, WP-0.1 | L |
| WP-1.9 | Baseline report and partial G1 memo | evaluation engineer (E) | WP-1.3 to WP-1.8 | report in `experiments/R0/`; memo stating which half of G1 is met | the memo says explicitly that G1 is open until WP-2.6 passes | WP-1.3 to WP-1.8 | S |

---

## 3. Direction 2: missing objectives, synthetic data, training for configurable generalization

**Objective.** Build the objectives that have a zero local denominator, then train for **configurable generalization**: the model reads a task definition that varies across training samples and generalizes to held-out rule families (survey §6.3.2). The missing objectives are three: same-input competing-rule pairs (cross-question re-partition), rule diversity, and rule-silent unknown (survey §2.3 omissions 1 and 3). This direction realizes R1 and R3, and R4 for ordinal and unknown structure.

**What the orchestrator changed relative to the user's framing, and why.**

- **Ordering decision: configurable generalization is the objective; per-task performance is the P2″ floor, not the target.** If every training sample has a fixed task definition, the optimum is to burn the task into the weights and ignore the context (survey §6.3.2). The local mix has 147,139 rows but only 4,101 distinct question strings (survey §2.3 omission 1).
- "Train the ability" has one testable form: **no regression on held-out rule families** against untuned readout (survey §2.3 input 3; R3-5). At 27B the new-schema SFT gain is about zero (survey §6.1.5), so at endgame size the question is whether tuning **preserves** what the base reads.
- Synthetic data has a degenerate optimum: **learning the generator grammar** (survey §2.2.6 round 7). Hold out by grammar family, not only by rule. Every synthetic gain counts only after confirmation on the natural-language convention set, whose labels only the business side can give (proposal Block 3). Typed-decisions shows 35% annotator argmax disagreement under the same criteria (survey §6.1.4.3).
- Rule-silent unknown has no code-label source (R1-3). Only the rule author can say that a question does not cover an input.

**Pre-registered conclusions** (carried from `00`; short forms):

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R1-1 | Rule text + code evaluation yields competing-rule pairs whose code labels agree with human spot checks above 95% | Synthetic labels are untrustworthy; P1″'s discrimination item moves to human annotation |
| R1-2 | Annotator disagreement on natural-language conventions is of the order of 35% | The P2″ floor must be declared as agreement with the convention, not correctness |
| R1-3 | Rule-silent unknown has no code-label source | If it can be generated, R4's native unknown moves earlier |
| R3-1 | After rendering fix + symbol tuning, name-definition swap AUC exceeds 60% (baseline 23.2%) | **G2 fails**; survey §8.2.4 item 4 fires |
| R3-3 | The k-shot curve does not flatten after decision tuning | Survey §8.2.4 item 5 fires; G3 warning |
| R3-4 | A varying level set is necessary for R3-1; the fixed-level-set control misses the line | Survey §6.3.2 does not hold in our setting |
| R3-5 | No regression on held-out rule families against untuned readout | The testable form of "train an ability" fails |
| R4-2 | Native unknown beats R2's held-out threshold on rule-silent inputs | Unknown stays at the interface layer |

**Protocol and thresholds** (from proposal R1, R3, R4; unchanged):

- Re-partition denominator: same input × at least 3 competing conventions × at least 2,000 inputs. Discrimination metric: share of inputs whose level distributions under two competing rules differ by total variation above 0.5.
- Rule diversity: hundreds to thousands of phrasings per input. Held-out split cut along three axes: rule family, grammar family, level-set version (`D-1.5`). Open-Jev v1.1 `ood` has 5,120 rows locally (survey §2.3 input 3).
- Three datasets are accounted separately and never mixed: synthetic rules (code labels), natural-language conventions (human labels), rule-silent (human labels).
- G2 reports three groups together: name-definition swap AUC, accuracy change after deleting definitions, k-shot curves at 1 / 2 / 4 / 8 / 16 shots before and after tuning.
- Training means: LoRA, data composition, structural isolation, temperature. **No RL in this direction** (survey §2.2.4 reading 1).
- Unknown is two-sided: unknown rate on the decidable set below 5% while the unknown rate on the silent set is high (R4).

**Degenerate-solution check.**

| Measure | Unconstrained optimum | Seal |
| --- | --- | --- |
| Synthetic rule training | Learn the generator grammar | Held-out grammar families; confirmation on the natural-language set; the synthetic set is never P1″'s business denominator |
| Symbol tuning / rendering fix | Ignore names entirely | Definition swap and level reorder must move the distribution (T2) |
| Native unknown | Answer unknown to every hard question | Unknown below 5% on the decidable set |
| Ordinal loss | Prior by level position | Adjacent-level confusion above distant-level confusion; middle level not over-filled |
| Competing-rule pairs | Different views of the same rule, not different partitions | `E-1.1`: competing rules must induce different partitions |

**Work packages.**

| WP id | title | role | inputs | outputs | acceptance check | depends on | size (S/M/L) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-2.1 | Competing-convention generator (`D-1.1`) | data engineer (D) | Open-Jev synthetic generator (visible rules, three-valued logic, abstain, family hold-out) | same-input × competing-rule pairs, at least 3 rules × 2,000 inputs | code labels agree with a human spot check above 95% (R1-1) | none (CPU) | L |
| WP-2.2 | Rule-rewrite diversity by grammar family (`D-1.2`) | data engineer (D) | WP-2.1 rules | N phrasings per rule (negation, exceptions, nesting), tagged by grammar family | at least one grammar family never seen in training exists in the held-out split | WP-2.1 | L |
| WP-2.3 | Natural-language convention labels with disagreement (`D-1.3`) | business-author liaison (B) with data engineer (D) | typed-decisions and akhilaaa3 dialogue inputs; WP-2.7 spec | convention labels; per-item annotator disagreement | disagreement recorded per item, not averaged away; label protocol signed by the business side | WP-2.7; Block 3 | M |
| WP-2.4 | Rule-silent set (`D-1.4`, later `D-4.1`) | business-author liaison (B) | WP-2.1 inputs; business rules | questions written not to cover the input; gold = unknown | each item signed off by the rule author as "not covered" | Block 3 | M |
| WP-2.5 | Held-out split and immutable manifest (`D-1.5`) | data engineer (D) | WP-2.1 to WP-2.4 | manifest cut by rule family, grammar family, level-set version | sha256 manifest committed; a test asserts zero overlap on all three axes | WP-2.1 to WP-2.4 | S |
| WP-2.6 | Denominator sanity (`E-1.1`) | evaluation engineer (E) | WP-2.1, WP-2.5 | partition-difference report | share of pairs with total variation above 0.5 reported; pairs that are views of one rule removed; **closes G1 together with WP-1.9** | WP-2.5 | S |
| WP-2.7 | Level and type declaration spec, first draft (`B-1.1`) | business-author liaison (B) | survey §2.2.1 levels row | spec: name, definition, type all required; level cap | a validator rejects any level set missing one of the three fields | none | S |
| WP-2.8 | Resample so the level set varies (`D-3.1`) | data engineer (D) | WP-2.5 training split | training mix where K, names and definitions vary across samples; a fixed-set control mix | per-sample level-set diversity reported; control differs only in that variable | WP-2.5 | S |
| WP-2.9 | Symbol tuning, fixed-set control, ablations (`M-3.1`, `M-3.2`, `M-3.3`) | training engineer (M) | WP-2.8; R2 harness (WP-4.2) | LoRA checkpoints for 0.6B / 0.8B | training config and data hash logged; no RL term in the loss | WP-2.8, WP-4.2, G1, WP-0.1 | L |
| WP-2.10 | G2 evaluation (`E-3.1`, `E-3.2`, `E-3.3`) | evaluation engineer (E) | WP-2.9 checkpoints; WP-2.3 natural-language set | swap AUC, delete-definition delta, k-shot curves, held-out-family table; G2 memo | all three groups reported together; synthetic gains shown only next to the natural-language confirmation | WP-2.9, WP-2.3 | M |
| WP-2.11 | Ordinal and native-unknown structure (`M-4.1` to `M-4.3`, `E-4.1` to `E-4.3`) | training engineer (M) with evaluation engineer (E) | WP-2.9 recipe; WP-2.4 | K−1 cumulative boolean head; ordinal loss; native unknown class | two-sided unknown check and ordinal discrimination check both pass on held-out data | G2, WP-2.4 | L |

---

## 4. Direction 3: intermediate typed states before the final judgment

**Objective.** Let the model emit a few intermediate typed states, defined by the template, before the composite judgment, so that decisions needing an intermediate step become reachable without free-text chain of thought. This direction realizes R5 and adds three pre-registered stages. It runs **typed intermediate states first** and keeps latent reasoning and distillation as pre-registered comparisons.

**What the orchestrator changed relative to the user's framing, and why.**

The user's observation: prefill may run to hundreds of thousands of tokens while the output is a single state, which leaves no room to reason; free-text chain of thought costs too many tokens; so let the model first emit a few prompt-defined intermediate state readouts, then a composite judgment.

- **The phenomenon survives.** Letting the same untuned 27B reason beats its readout 96.9 vs 89.1 (survey §6.1.5). Decisions an LLM needs intermediate steps for fall to 74%, against 97.5% for the rest (survey §6.5.4.5; defect 10). Rules are read but executed only 22% to 72% (defect 2).
- **The mechanism does not survive as stated.** What is missing is not output room. It is **serial depth, and the ability to write an intermediate result down and read it back**. Running uniformly more passes buys calibration but almost no accuracy (survey §6.5.5.2). The only zero-token route with depth-extrapolation evidence adds depth, not output (layer recurrence, §6.5.4.3). Failure grows with the number of state updates an answer depends on, 53% to 80% at sixteen updates (§6.5.4.5). More output slots without a read-back path should therefore add nothing; R3S1-1 tests exactly this.
- **Reframing for very long prefill.** At hundreds of thousands of tokens on the hybrid backbone, the likely first failure is **lossy question-conditioned reading** (defect 11): the longer the input, the more heavily it is compressed through the recurrent layers (survey §2.3 omission 9). So the first intermediate states should be **evidence states** ("which parts of the input bear on this question"). That is a retrieval step, not a reasoning step. T4 (WP-1.5) measures the underlying effect; if R0-4 reverses, evidence states lose their reason.

**Three candidate fixes, with different costs.**

| Fix | What it is | Survey status | Inference cost | Auditable | Role here |
| --- | --- | --- | --- | --- | --- |
| (a) Typed intermediate states in the template | The question graph (**the report's own construct**, survey §6.5.5.1, §8.1.2); R5-1, R5-2 | Execution-rate gain untested on our backbone; compositional calibration measured by no one (defect 2 residual) | a few branch readouts plus one short pass | yes: each state is a typed readout | **runs first**, Stages 1 to 3 |
| (b) Latent reasoning | Looped computation; pause or thought tokens | Looped readout needs a loop-pretrained backbone; converting a hybrid backbone is a zero hit (§6.5.4.3; §6.5.6 blind spot 4). **Pause and thought tokens are not covered by the survey; this plan cites nothing for them** | layer recompute or a few extra positions | no typed intermediate object | pre-registered comparison (R3S3-3) |
| (c) Reasoning-to-readout distillation | `M-5.2`; R5-3 | 27B on par with Jev at about 0.1 s (§6.5.4.1); cannot break the one-pass limit (§6.5.4.5) | zero | no | pre-registered comparison (R3S3-3) |

"Loses auditability" for (b) is this plan's reasoning (there is no intermediate readout to inspect), not a survey finding.

**Design decisions fixed by the user.** (i) The context is whatever the agent harness loads. Its content is a pre-designed task, or the model is trained to a template so that the calling syntax is stable. (ii) Direction 3 proceeds in **three stages**: Stage 1, a standard template whose intermediate-state slots are filled by the business author (fixed intermediate questions; the model only reads out states). Stage 2, the template fixes the syntax and the model synthesizes the intermediate content within it (grammar fixed, content free). Stage 3, the model learns to decompose and the template becomes the trained calling convention.

**Cost accounting.** Intermediate states cost a few branch readouts or decode steps, **not a second prefill of the input**: task definition and input are encoded once and cached (fixed order, survey §2.2.1), and on the hybrid backbone the cache is reused by prefix forking (8 to 19 times faster than one pass per branch, survey §1.3.3). But under the fixed order (task definition → input → one branch per candidate) the branches are isolated. **A later state that reads an earlier one breaks branch isolation** (defect 6 is solved only by isolation). Stage 1 therefore needs one of two mechanisms:

1. **Second pass (default).** Pass 1 reads all intermediate states in isolated branches. The harness thresholds them and writes the resulting levels, as text, into the composite branch. Pass 2 runs only that branch on the cached prefix. This is "write down and read back" with the harness doing the writing; every state stays auditable and editable.
2. **Decode loop.** The model emits states one after another inside one branch, each conditioned on the previous ones. Fewer passes, but the states are re-coupled and the counterfactual edit test needs teacher forcing.

Training through a forked recurrent cache has no literature (survey §1.3.6, §1.3.7 blind spot 1); Stage 1 training, if needed, uses one row per branch.

### 4.1 Stage 1: authored intermediate questions, model reads out states

**Registry rows**: 2 (rules read but not executed), 10 (multi-step / stateful), 11 (evidence states on the hybrid backbone), 13 (business authors write the intermediate questions).

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R3S1-1 | **Intermediate states are causally used.** When the harness writes the opposite level into one state the rule depends on, the composite judgment moves in at least 90% of items; when it edits a state the rule does not depend on, the composite moves in at most 5% | States are decorative. Stage 1 buys cost and no depth; Stages 2 and 3 are suspended until a variant passes |
| R3S1-2 | **The graph does not collapse into a chain.** For conjunctive graphs, end-to-end accuracy lies within a factor 0.8 to 1.25 of the product of node-level accuracies, and every node is evaluable alone | The graph answers only the last question; R5-2's compositional calibration cannot be measured on it |
| R3S1-3 | On the "needs an intermediate step" bin, Stage 1 beats single readout and lifts compound-rule execution above the 22% to 72% band (R5-1) | Defect 2 has no fix on this interface; supported compound-rule scope is narrowed for the business |
| R3S1-4 | **Evidence states first.** On T4's low-salience bins, an evidence-state node narrows the hybrid vs attention-only gap measured in R0-4 | Long-input failure is not lossy reading, or evidence states cannot fix it; the first state type switches to reasoning states |
| R3S1-5 | Per-decision latency of the second-pass design is at most 2 times single readout at equal input length | The second pass costs close to another prefill; Stage 1's cost case against generative chain of thought weakens |

**Degenerate-solution check.** Unconstrained optimum of Stage 1: **ignore the states and answer from the input**, which passes every accuracy check. Sealed by R3S1-1 (must-move and must-not-move edits together). Second optimum: **collapse the graph into a chain and answer only the last question** (proposal R5). Sealed by R3S1-2. Authored questions also inherit defect 13: Stage 1 is run once with researcher-written and once with business-written intermediate questions.

### 4.2 Stage 2: template fixes the syntax, the model writes the intermediate content

**Registry rows**: 10, 2, 13, plus omission 2 (runtime-generated questions).

The template declares slot types (for example: an intermediate question of at most N tokens, with levels drawn from a declared type). The model generates the content under grammar-constrained decoding, then the harness reads the states out as in Stage 1. Runtime-generated content must pass through the versioned template with slot filling (survey §2.3 omission 2; R7-3), otherwise P1″'s denominator changes on every call.

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R3S2-1 | **Idempotence is not re-imported.** Under greedy decoding, the generated intermediate content is byte-identical across reruns, and the composite flip rate under R0's eight irrelevant perturbations is at most Stage 1's flip rate plus 2 pp | Stage 2 re-imports non-idempotence. It is restricted to an offline authoring aid: the model proposes intermediate questions and an author freezes them into a Stage 1 template |
| R3S2-2 | **Generated content discriminates.** On WP-2.1's competing-rule pairs, the generated intermediate content differs between the two rules in at least 80% of pairs, and R3S1-1 still passes | The model writes one generic decomposition for everything; Stage 2 adds nothing over Stage 1 |
| R3S2-3 | On held-out rule families, Stage 2 accuracy is within 2 pp of Stage 1 on the same tasks and above single readout | The model cannot author useful states; Stage 3 is cancelled |
| R3S2-4 | Stage 2 reaches at least 90% of free chain of thought's accuracy gain over single readout with at most 20% of its decoded tokens, on the same items | The cost case against free chain of thought fails; Stage 2 is kept only where auditability is required |

**Degenerate-solution check.** Unconstrained optimum of constrained generation: **emit the same generic content for every task**, which is perfectly idempotent and passes R3S2-1. Sealed by R3S2-2. Second optimum: content that is well-formed but unused; sealed by re-running R3S1-1 on generated states.

### 4.3 Stage 3: the model learns to decompose; the template becomes the trained calling convention

**Registry rows**: 10, 2, 13; defect 1 indirectly (the decomposition must read definitions, not names).

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R3S3-1 | On held-out rule families **and** held-out grammar families, learned decomposition does not regress against Stage 2 | The model learned the template grammar, not decomposition; Stage 3 falls back to Stage 2 |
| R3S3-2 | After training, R3S1-1 and R3S1-2 still pass on learned decompositions | End-to-end training pressure made the states decorative; the Stage 3 objective must add node-level supervision |
| R3S3-3 | At equal inference compute, typed states (a) are not beaten by latent reasoning (b) or distillation (c) on the "needs an intermediate step" bin | If (c) matches at zero decode cost, Stages 2 and 3 are dropped for distillation. If (b) wins, auditability is traded for accuracy and the choice goes to the user |

**Degenerate-solution check.** Unconstrained optimum: **memorize one decomposition per rule family** (a lookup table over families). Sealed by R3S3-1's grammar-family hold-out. Distillation's optimum, learning the teacher's wording (proposal R5), is sealed the same way.

**Protocol and thresholds** (all stages).

- Data: `D-5.1` multi-step paired set (WP-3.1), binned by composition depth 1 to 4 from WP-2.1's rule generator, plus T4's salience bins for evidence states. Bins are frozen before scoring.
- The 97.5% vs 74% split in the survey comes from a reference LLM's thinking-token count (survey §6.5.4.5). Our local proxy is composition depth; it is a substitute and is labelled as such.
- Counterfactual edit protocol: the harness edits one state at a time; must-move and must-not-move edits are decided from the rule before the run.
- Node-level vs end-to-end accuracy (`E-5.3`) and compositional calibration (`E-5.1`) are reported for every graph. Decomposition multiplies consistency defects (survey §6.5.5.2), so P1″ items are re-measured on the composite, not inherited from the nodes.
- Cost is reported per decision: input prefill tokens, branch tokens, decoded tokens, number of passes, wall time, all on the same NPU instance.

**Work packages.**

| WP id | title | role | inputs | outputs | acceptance check | depends on | size (S/M/L) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-3.1 | Multi-step paired set with depth bins (`D-5.1`) | data engineer (D) | WP-2.1 generator; typed-decisions | items with rule graph, node gold labels, depth bin | every node has its own gold label; bins frozen in the manifest | WP-2.1 | M |
| WP-3.2 | Template schema with intermediate-state slots | harness/agent engineer (B) | WP-2.7 spec; `B-7.3` compiler | versioned slot schema: authored (Stage 1), syntax-only (Stage 2) | the compiler rejects a graph with a cycle or an undeclared level type | WP-2.7 | S |
| WP-3.3 | Two-pass harness with harness-written states (harness side of `M-5.1`) | harness/agent engineer (B) | WP-3.2; WP-4.2; prefix forking | pass-1 isolated state readout; pass-2 composite on cached prefix | fork vs sequential error within 1e-3 (survey §1.3.3 tolerance); latency reported per R3S1-5 | WP-3.2, WP-4.2, WP-0.1 | M |
| WP-3.4 | Evidence-state node | training engineer (M) with evaluation engineer (E) | WP-1.5 (T4); WP-3.3 | per-segment stackable relevance readout; harness copies selected segments into the composite branch | R3S1-4 scored on T4 bins for both backbones | WP-1.5, WP-3.3 | M |
| WP-3.5 | Causal-use and collapse checks (`E-5.1`, `E-5.3`) | evaluation engineer (E) | WP-3.1; WP-3.3 | R3S1-1, R3S1-2 tables; compositional calibration | edits and node tests run on every stage's outputs, untuned first | WP-3.1, WP-3.3 | M |
| WP-3.6 | Stage 1 training, only if untuned Stage 1 fails R3S1-1 or R3S1-3 (`M-5.1`) | training engineer (M) | WP-3.1 training split; one row per branch | LoRA checkpoint reading harness-written states | R3S1-1 to R3S1-3 pass on held-out rule families | WP-3.5, G2 | M |
| WP-3.7 | Business-written intermediate questions (subset of `B-7.2`) | business-author liaison (B) | WP-3.2 schema; real business rules | graphs written by non-technical authors | same R3S1-1 / R3S1-3 run on author-written and researcher-written graphs | WP-3.2; Block 3 | M |
| WP-3.8 | Stage 2 grammar-constrained generation of intermediate content | training engineer (M) | WP-3.2 syntax slots; WP-3.6 | constrained decoder; generated-state pipeline | every generated slot parses under the template grammar; content logged with template version | Stage 1 pass | L |
| WP-3.9 | Stage 2 idempotence, discrimination and cost evaluation | evaluation engineer (E) | WP-3.8; WP-2.1 pairs | R3S2-1 to R3S2-4 tables | perturbation set and competing-rule pairs frozen before the run | WP-3.8 | M |
| WP-3.10 | Stage 3 decomposition training | training engineer (M) | WP-3.9 pass; WP-2.5 split | checkpoint that writes its own graph under the calling convention | R3S3-1 and R3S3-2 pass; RL only under §5's conditions | WP-3.9 | L |
| WP-3.11 | Pre-registered comparisons (b) and (c) (`M-5.2`) | training engineer (M) | WP-3.1; teacher reasoning traces | distilled readout; one latent variant at equal compute | R3S3-3 scored on the same bins and the same cost table | WP-3.1, WP-0.1 | L |
| WP-3.12 | Cost accounting report | evaluation engineer (E) | WP-3.3 to WP-3.11 | per-decision cost table across single readout, Stages 1 to 3, (b), (c), free chain of thought | all rows measured on the same instance type and input lengths | WP-3.11 | S |

---

## 5. Direction 4: agentic Jev, agent integration and agentic RL on an interface abstraction

**Objective.** Put the model into an agent system through a stable interface, and find out whether RL on that interface pays. The interface abstraction already exists as a deliverable: **the template standard plus the harness contract** (R2, `B-2.1`, `B-7.x`; survey §2.2.1 deliverable row). The engineering half is weight-free and can start now. The RL half is conditional.

**What the orchestrator changed relative to the user's framing, and why.**

- RL is the first-choice fix for **no row** of the registry (survey §2.2.4 reading 1). For a pure readout, a proper scoring rule and an RL reward share the same optimum (survey §6.3.4; R8-1). RL pays only when **the reward depends on a sampled intermediate object** (survey §6.3.4).
- **Directions 3 and 4 are coupled.** If direction 3 gives the model intermediate states (Stage 2 or 3), RL on the model becomes defensible, because the states are the sampled object. If not, RL is restricted to scheduling: which questions to ask, loop depth, hand-off to the slow model (R8-2; on-demand depth saves 15% to 24%, survey §2.2.4 reading 1).
- Retrospective outcome labels refit thresholds but cannot supervise the readout; used as a reward, the degenerate optimum is an **outcome proxy** (R7-4; defect 18).
- Verifier rewards get gamed (R8-3; survey §6.4.1.3). When RL runs, it runs calibrate-first with a KL anchor: the policy-gradient term is 7 to 12 times larger than the readout term and "System-One collapse" follows without the anchor (survey §6.3.4).
- Integration value is measured as **cost per successful outcome**, not cost per attempt. A Jev controller raised cost per attempt by 19% at the same pass rate, and delegating tool selection without a fitted threshold cost 19.0 points of success (survey §5.2.1).

**The S1 position must be chosen (open decision).** Survey §5.1.4 lists five positions:

| Position | What S1 does | Evidence strength (§5.1.4) | Who owns the loop | Where RL could sit | Plan verdict |
| --- | --- | --- | --- | --- | --- |
| A Entry gate / cascade | decides whether to slow down | positive; routing saves 24% to 77% of API cost | S1's confidence gate | gate policy (scheduling) | viable; needs calibration and routing confidence, neither can be promised directly |
| B Process monitoring / intervention | judges whether a declared behavior occurs; a controller warns, then takes over | positive; no training needed; reasoning tokens down up to 36%, abstention 70.5% to 87.2% | **a deterministic controller outside S1** | controller policy (scheduling) | **default recommendation** |
| C Evidence / memory plane | many small yes/no judgments for S2 | positive; LoCoMo 91.7%; per-question cost 1.11× from 100K to 10M tokens | S2 (writes the queries) | which judgments to request | viable only if S2's queries pass through the template contract (omission 2) |
| D Readout of slow-model output | reads S2's possibly truncated chain and commits | positive; +4.1 pp at a 1,500-token budget; 71.3% cost saved | S2 makes the chain; the harness gates | reading budget (scheduling) | viable; cheapest S2 cooperation (R5-4) |
| E Closed-loop executor | makes consecutive decisions itself | weakest; small System-1 models at most 3.1% in closed loop (§5.2.1) | S1 | the policy itself | **excluded**: requires three properties that do not hold |

**Default recommendation: position B, with one amendment.** In B the deterministic harness owns the loop, decisions stay in the contract (P3″) and S1 decides no consequence alone (survey §5.1.4.1). The amendment: questions supplied by S2 are admitted **only through the versioned template contract with slot filling** (omission 2; R7-3). This borrows C's question channel under B's control and matches the pattern of successful domain agents, where code enumerates the action space and S2 changes it at low frequency (survey §5.2.6). Note that survey §2.2.2 places scheduling authority in S2; choosing B moves it to the deterministic controller for this plan. **The user has not chosen; this stays open (§7).**

**Pre-registered conclusions** (new items R4A-n; R7-3, R7-4, R8-1 to R8-3 carried from `00`):

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R4A-1 | Two independent agent integrations use the same contract version with **no edit** to the calling syntax or the model | The interface abstraction leaks model details; it is redesigned before any RL is run on it |
| R4A-2 | In the chosen position, adding S1 lowers **cost per successful outcome** against the same agent without S1, at a pass rate no worse by more than 1 pp | Savings are eaten by extra interactions (survey §5.2.1 pattern); integration value is not shown and direction 4 stops at the contract |
| R4A-3 | Scheduling RL saves compute at equal pass rate against the model-free deterministic controller (R8-2 on this interface) | RL has no place in this route; the budget moves to interface and SFT |
| R4A-4 | **Only if direction 3 passes Stage 2**: RL on the decomposition policy, with a proper-scoring-rule reward on the composite readout, beats SFT on decompositions on held-out rule families | Even with intermediate states RL adds nothing; RL stays scheduling-only |
| R4A-5 | Without intermediate states, readout-side RL is not better than cross-entropy plus a proper scoring rule (R8-1, falsification attempt) | If RL wins, survey §6.1 / §6.3 do not hold here and this section is rewritten |
| R4A-6 | A control that uses retrospective outcomes as reward raises outcome reward while held-out gold-label readout accuracy falls | If gold accuracy does not fall, the outcome-proxy limit of defect 18 is weaker than assumed (R7-4) |

**Protocol and thresholds.**

- Thresholds are fitted on the agent's own trajectories, never on isolated questions (survey §5.2.1 conclusion (b)).
- Every RL result is reported with cost and pass rate together, against the model-free deterministic controller (proposal R8; it solves 79% of τ²-bench telecom, survey §5.1.5).
- RL on the model uses calibrate-first plus a KL anchor; the readout's calibration (ECE on held-out gold) is reported before and after.
- Retrospective labels are used only to refit τ per (question, level-set version, rule version) under `B-7.4`; the rejected side is covered by exploration or manually reviewed samples (defect 18).

**Degenerate-solution check.**

| Measure | Unconstrained optimum | Seal |
| --- | --- | --- |
| Scheduling RL | Always the cheapest path: reject everything, or hand everything to S2 | Cost and pass rate reported together against the deterministic controller |
| Decomposition RL | Decorative states or a collapsed chain | R3S1-1 and R3S1-2 re-run after RL |
| Outcome reward | Outcome proxy | R4A-6 gold-label control |
| Verifier reward | Gaming the verifier | `E-8.2` gaming detection on held-out items |
| Agent integration | S1 placed where it decides consequences alone | Position E excluded; the contract holds decision authority |

**Work packages.**

| WP id | title | role | inputs | outputs | acceptance check | depends on | size (S/M/L) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-4.1 | Harness contract document v1 (`B-2.1`) | harness/agent engineer (B) | survey §2.2.1 harness row; P3″ | contract: operators, τ versioning per triple, margin + abstain, C residual | one reviewer outside the team implements a toy caller from the document alone | none | S |
| WP-4.2 | Cumulative-mass harness with margin and abstain (`E-2.1` to `E-2.3`) | harness/agent engineer (B) with evaluation engineer (E) | WP-4.1 | harness library; three-operator comparison; two-level IIA protocol | no argmax, no expectation path in the decision code; R2-3 scored | WP-4.1 | M |
| WP-4.3 | Template compiler and validator (`B-7.3`) | harness/agent engineer (B) | WP-2.7; WP-3.2 | compiler pinned to one judge version | rejects missing name / definition / type; compiles intermediate-state slots | WP-2.7, WP-3.2 | M |
| WP-4.4 | Agent integration adapter in the chosen position | harness/agent engineer (B) | WP-4.2; WP-4.3; S1 position decision | adapter; S2 questions accepted only through template slots | R4A-1: two integrations, one contract version, zero contract edits | WP-4.3; §7 decision | M |
| WP-4.5 | Deterministic controller baseline and cost-per-success report (`E-8.1`) | evaluation engineer (E) | WP-4.4 | model-free controller; cost and pass-rate tables | R4A-2 scored on cost per successful outcome | WP-4.4 | M |
| WP-4.6 | Retrospective-label contract (`B-7.4`) | business-author liaison (B) with harness/agent engineer (B) | defect 18; business outcome feeds | decision-level / selective / delayed handling; exploration rule for the rejected side | refit uses only outcome labels; no readout gradient path exists in the code | WP-4.1 | M |
| WP-4.7 | RL rollout environment on verl | training engineer (M) | WP-0.1; WP-4.2 | rollouts = harness + model; proper-scoring reward; KL anchor | a zero-learning-rate run reproduces the frozen model's readouts exactly | WP-0.1, WP-4.2 | L |
| WP-4.8 | Readout-side RL falsification (`M-8.1`) | training engineer (M) | WP-4.7; WP-2.9 data | RL vs cross-entropy comparison | R4A-5 scored on held-out rule families with ECE | WP-4.7 | M |
| WP-4.9 | Scheduling RL (`M-8.2`) | training engineer (M) | WP-4.7; WP-4.5 | policy over questions, depth, hand-off | R4A-3 scored against WP-4.5's controller | WP-4.5, WP-4.7 | L |
| WP-4.10 | Decomposition RL (conditional) | training engineer (M) | WP-3.9 pass; WP-4.7 | RL on Stage 2 / 3 intermediate states | R4A-4 scored; R3S1-1 and R3S1-2 re-run after RL | WP-3.9, WP-4.7 | L |
| WP-4.11 | Reward-gaming and outcome-proxy detection (`E-8.2`) | evaluation engineer (E) | WP-4.8 to WP-4.10; WP-4.6 | gaming report; R4A-6 control | held-out gold set never seen by any reward | WP-4.8 | M |

---

## 6. Sequencing

**First engineering package.**

| WP id | title | role | inputs | outputs | acceptance check | depends on | size (S/M/L) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-0.1 | Training and evaluation environment: verl + vllm-ascend image on the official Ascend 910b base, 2 NPUs per container instance; resolves Blocks 1 and 1b (`M-0.1`) | training engineer (M) | `experiments/ENV-VERL.md`; `SERVER-175.md`; `quay.io/ascend/verl:verl-8.3.rc1-910b-...` on `npu2`; the `start_pair.sh` launcher and `verl_smoke/` from the 2026-10-29 build | primary: image with verl + vllm-ascend on the pinned stack (torch 2.7.1, torch_npu 2.7.1, transformers 4.57.1), a 2-NPU pair launcher, a verl smoke run on Qwen3-0.6B; secondary: a transformers 5.x variant (separate venv or tag) with a recorded pass / fail for loading Qwen3.5-0.8B | Qwen3-0.6B loads and matches a CPU reference within fp tolerance; prefix fork vs sequential error within 1e-3; one 2-NPU instance runs a short verl job; the 5.x variant's Qwen3.5-0.8B result is recorded either way; the largest ladder rung that fits one instance is recorded | NPU window (Block 2) | M |

**Dependency list.**

1. Start now, CPU only, no weights needed: WP-1.1, WP-1.2, WP-1.5, WP-2.1, WP-2.2, WP-2.7, WP-3.2, WP-4.1, WP-4.2. T1 to T3 on 0.6B can run on CPU (proposal §5).
2. WP-1.2 (protocol committed) precedes every scored run in every direction (rule 3).
3. WP-0.1 precedes every 0.8B run and every NPU run.
4. **G1** = WP-1.9 (within-question invariance, floor) **and** WP-2.6 (re-partition denominator). No training aimed at consistency before G1.
5. Training starts only after the R2 harness (WP-4.2) exists (proposal R2). WP-2.9 needs G1 and WP-4.2.
6. **G2** = WP-2.10. Direction 3 untuned Stage 1 (WP-3.3 to WP-3.5) may run before G2; Stage 1 training (WP-3.6) waits for G2.
7. Stage 2 (WP-3.8) starts only after R3S1-1 and R3S1-2 pass. Stage 3 (WP-3.10) only after R3S2-1 to R3S2-3 pass.
8. RL on the model (WP-4.10) starts only after Stage 2 passes. Without it, RL is limited to WP-4.8 (falsification) and WP-4.9 (scheduling).
9. WP-4.4 waits for the S1 position decision. **G3** follows R7 (`B-7.2`, `E-7.1`), fed by WP-3.7 and WP-4.3.
10. WP-1.8 (ladder) re-runs for every structural change that passes on 0.6B / 0.8B, before that change is claimed at scale (R6-1).

**Blocks carried over from proposal §5.**

- **Block 1**: the RL image pins transformers 4.57.1; Qwen3.5-0.8B needs 5.x. WP-0.1 resolves it or records why not. **Update 2026-10-29**: still open. Under transformers 5.21.0 Qwen3.5-0.8B loads and runs a CPU forward pass, but verl 0.7.0 fails to import because `AutoModelForVision2Seq` was renamed; a one-line alias fixes the import and is not yet validated further (`experiments/ENV-VERL.md`).
- **Block 1b (new, 2026-10-29)**: the CANN toolkit inside `agentic-rl-ascend:20261026` ships op kernels for SoC `ascend910_93` only, while both hosts are 910B. No Ascend op can execute in that image, so the custom verl build on top of it cannot train. A matching image, `quay.io/ascend/verl:verl-8.3.rc1-910b-...`, already exists on `npu2` with the same torch / vllm / vllm-ascend pins and verl preinstalled. WP-0.1 is rebased onto it.
- **Block 2**: **largely lifted on 2026-10-29.** Both hosts now report 8 idle chips with no NPU-resident processes; the vLLM deployment that held them is gone. This has not been confirmed with the machine owner, so WP-0.1 still starts by asking for a window rather than assuming one. T1 to T3 can still run on CPU.
- **Block 3**: natural-language convention labels and rule-silent labels come only from the business side, which must commit annotation hours and accept "the floor measures agreement with the convention". WP-2.3, WP-2.4 and WP-3.7 wait on it.

---

## 7. Open decisions for the user

| Decision | Status | What waits on it |
| --- | --- | --- |
| Input modality in production | **Answered (2026-10-29)**: whatever the agent harness loads; its content is a pre-designed task, or the model is trained to a template so the calling syntax is stable | Nothing; fixes direction 3's template-first design |
| S1 position (A to E, §5) | **Open.** Default recommendation: B, with S2 questions admitted only through the versioned template contract | WP-4.4, WP-4.5, WP-4.9 |
| NPU window | **Likely resolved, needs confirmation (2026-10-29).** Both hosts now show 8 idle chips; the vLLM deployment that held them is gone. Still needs the machine owner to confirm we may use them, and how many | WP-0.1 and every NPU run |
| Business annotation hours | **Open.** Needs a commitment from the business side and acceptance of the convention-floor protocol | WP-2.3, WP-2.4, WP-3.7; half of G2's confirmation; G3 |

---

## 8. Where this plan is most likely wrong

1. **Stage 2 may re-import non-idempotence.** Letting the model write intermediate questions is exactly the case of omission 2: a runtime-generated question is a non-idempotent generation, and the denominator of P1″ moves with it (survey §2.3). Greedy decoding and a fixed grammar make reruns identical but do not make content invariant under irrelevant perturbations. If R3S2-1 fails, Stage 2 becomes an offline authoring aid and Stage 3 has no runtime form.
2. **Intermediate states on the 0.6B / 0.8B testbed may not predict 27B.** R6-1 has not been tested for any structural change. At 27B the readout already reaches 76% to 97% of tuned accuracy and reasoning still wins by about 8 points (survey §6.1.5). The gap that intermediate states fill could be different in size or in kind at 27B. Direction 3 claims at scale are void until WP-1.8 has run on them.
3. **The mechanism reframe could itself be wrong.** This plan says the missing thing is serial depth and read-back, not output room. If a latent variant (more positions, no typed states) beats typed states at equal compute (R3S3-3), capacity rather than read-back was the bottleneck and the user's original framing was closer. If R0-4 shows no defect-11 effect, evidence states are the wrong first state type.
4. **Direction 1 may be read as passing G1.** Its equivalence classes are mechanical substitutes, not business classes (proposal §6 item 1), and its re-partition denominator is zero. A clean direction 1 report is half of G1 at best.
5. **The RL half rests on one conditional chain.** RL on the model is defensible only if Stage 2 passes; scheduling RL is defensible only if it beats a model-free controller that already solves 79% in one setting (survey §5.1.5). WP-0.1 builds an RL environment before either condition is known. The sunk cost is acceptable only because the same image serves evaluation and SFT.
6. **Direction 3 is built on the report's own construct.** The question graph carries the highest overfitting risk of the eight self-made frameworks (survey §8.1.2; proposal §6 item 4), and decomposition multiplies consistency defects (survey §6.5.5.2). Three stages on top of it multiply that risk; R3S1-2 is the first place it can fail in public.
7. **Stage 1 training on the hybrid backbone may be infeasible at the planned cost.** Gradients through a forked recurrent cache have no literature (survey §1.3.6). One row per branch is correct but repeats the input encoding per branch, which at very long prefill is exactly the cost this direction was meant to avoid.
