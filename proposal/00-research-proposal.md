# Research Proposal: A Self-Training Route for Single-Pass Typed-Readout Decision Models (Jev class)

> 2026-10-28 · This file is **not part of** the survey report (chapters 1–9). The report's scope is "analysis only, no plan" (§2.3 omission 8: the strengthening plan is a separate document). This file is that separate document.
>
> Upstream basis: report §2.2.1 (the fixed structure), §2.2.4 (the 18-row defect registry), §2.2.5 (final framework P0″–P5″), §2.3 (nine omissions), §6.1.4.3 (local data check), §8.2.2 (which measurement is missing), §8.2.4 (what would overturn the framework). This file only does **task decomposition and pre-registration** on top of those conclusions; it adds no new claims about the literature.
>
> Work plan: [`01-work-plan-four-directions.md`](01-work-plan-four-directions.md) (2026-10-29) assigns and sequences these rounds as work packages along the user's four exploration directions; it does not replace the pre-registrations here.

---

## 0. Three hard rules of this proposal

The report bought three methodological rules with eleven rounds of discussion. They are not suggestions; they are the admission conditions for every task in this proposal:

1. **Every measure must point at a row of the defect registry.** A measure that cannot name a row number does not enter the plan. The registry's "type" column (interface / structure / SFT / RL / none) decides which kind of budget it may spend.
2. **Every measure must first write down its unconstrained optimum.** In seven of the eleven rounds the proposition had a degenerate optimum (lookup table, constant classifier, ignore the names, learn the generator grammar, calibrate each separately, prior by level position). A task whose degenerate solution has not been written down does not enter the plan.
3. **Metrics must be pre-registered.** §8.2.1 A2: a consistency rate is unfalsifiable when the equivalence classes are chosen after the fact. For every round, the equivalence-class definition, the held-out split, the threshold-fitting set and the decision thresholds are written into this file and committed before the run; after the run only the results are filled in, the protocol is not changed.

Two further limits come from the report's self-review and must stay attached to the proposal:

- **Each of the four load-bearing pillars rests on a single preprint less than six weeks old** (calibration-free union bound 2610.10978, cost and semantics on one knob 2609.37832, menu relativity of the metric 2610.16655, semantic generalization alive on a cheap architecture 2609.29429). The proposal may not take them as premises: one of R0's tasks is to reproduce all four on our own data, and if any reproduction fails the corresponding round is redesigned (§8.2.1 A7).
- **Eight of the frameworks in the report are the author's own constructs** (§8.1.2); the question graph, decision repetition and D4's 30 sub-dimensions carry the highest overfitting risk. This proposal uses the question graph (R5) and a D4 subset (R0's protocol); both must be labelled "this is the report's own classification" and must not be cited as literature conclusions.

---

## 1. Endgame goal and stage gates

**Endgame deliverable** (§2.2.1 last line): not a model, but **a template standard written for business authors** (how to write questions, levels, types, candidate-set types, criteria and examples) **plus a model that can read that template**, plus a deterministic harness (cumulative-mass thresholds, residual to C, margin + abstain for exclusive sets).

**Endgame size**: Qwen 27B dense, or 35B-A3B (MoE, about 3B active). The 0.6B / 0.8B / 2B / 4B / 9B ladder is **not a scaled-down endgame**; it is a testbed for structural changes (§6.1.5). The consequence of this reframing is written in R6.

**Three stage gates** (no gate passed, no next stage):

| Gate | Criterion | If not passed |
| --- | --- | --- |
| **G1 metric measurable** | On pre-registered (input, question set) equivalence classes, the consistency rate with all four denominators side by side produces numbers; "cross-question re-partition" has denominator data | Defect 12 is not cleared; the whole direction stops at a measurement block. Only P2″ floors and interface-type fixes may proceed; no training aimed at consistency may start |
| **G2 semantics repairable** | Rendering fix + symbol tuning repair "names override definitions" (criterion in R3) | §8.2.4 item 4 fires: "the core logic is semantic generalization" is downgraded to a wish. The route falls back to "cost + interface contract" and the endgame goal is rewritten |
| **G3 configurability holds** | Templates written by non-technical business experts are readable by the model (criterion in R7) | §8.1.5 blind spot 4 fires. The deliverable changes from "template standard + model" to "engineer-written templates + model"; the business value claim is rewritten |

---

## 2. Four work lines and task numbering

| Line | Scope | Task prefix |
| --- | --- | --- |
| **D data** | data-shape checks, denominator data construction, rule-diversity corpus, label sources and disagreement measurement, held-out splits | `D-*` |
| **M model** | training and tuning: rendering, symbol tuning, ordinal structure, native unknown, distillation, ladder ascent | `M-*` |
| **E evaluation** | protocol and harness: four-denominator consistency, decision-level pairing, margin distribution, threshold fitting, reproduction of load-bearing results | `E-*` |
| **B business** | template standard, declaration spec for levels and types, business-author evaluation, retrospective-label contract | `B-*` |

**Dependency spine**: `E-0 protocol` → `D-1 denominator data` → `M-2 interface` → `M-3 SFT` → `M-5 distillation` → `M-6 ladder` → `B-7 release`. `E-*` leads throughout: no round may train without a protocol.

---

## 3. Round plan (pre-registered conclusions for every round)

Every round has six fixed fields: **question / registry rows / locked conclusions (both directions) / protocol and thresholds / degenerate-solution check / task assignment**.

---

### R0 Protocol and baselines: stand the measurement up first (no weight update at all)

**Question**: Before any training, what is the consistency rate under each of the four denominators? Does typed readout have a consistency advantage over same-backbone label log-probability readout? Do the recurrent layers of the hybrid backbone really crush the aspects a candidate needs but that are not salient?

**Registry rows**: 6 (order, solved, used as control), 11 (hybrid vs attention-only, zero hits, measurement-blocked), 12 (equivalence-class consistency, defined by nobody), 16 (cross-candidate comparability), 17 (expert levels must be read).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R0-1 | The spread of consistency across the four denominators is at least 30 percentage points (the literature's two ends differ by 46 pp) | If the spread is < 10 pp, the effect size behind "consistency is only a metric once the denominator is fixed" was exaggerated, and the denominator dispute in P1″ is downgraded |
| R0-2 | Typed single-pass readout has **higher** consistency on the pre-registered equivalence classes than same-backbone label log-probability readout | **Reversal overturns the whole motivation of P0″ / P1″** (§8.2.4 item 1): the interface would then keep only its cost advantage and the proposal falls back to a pure cost route |
| R0-3 | Changing level names from {1–5} to {a–e} / business words / random strings moves the readout distribution significantly (flip rate > 5%) | If it does not move, defects 1 and 17 do not hold on our backbone and R3's symbol tuning is cancelled |
| R0-4 | The 0.8B hybrid backbone is less accurate than the 0.6B attention-only backbone on the "required aspect is not salient" bins, and the gap widens as aspect salience drops | If there is no difference, defect 11 dissolves and the residual risk of the fixed order is cleared; good news for the framework |
| R0-5 | The union bound (2610.10978) is not overturned in any cell on our data | Any cell overturning it **collapses the foundation of P2″ / P3″** (§8.2.4 item 3); the harness contract is redesigned |
| R0-6 | Untuned readout reaches 76%–97% of "decision-tuned" (the regularity in 2610.15501 reproduces on our backbone) | If untuned readout is far below, "tuning only adjusts how to read" does not hold and the SFT budget must grow |

**Protocol and thresholds**:

- Equivalence classes are **pre-registered**: R0 uses only two mechanically decidable kinds, to avoid after-the-fact selection: (i) eight irrelevant perturbations of the same input (whitespace, field order, adding / removing / reordering unrelated questions, replacing the level-name set); (ii) counterfactual pairs from the Open-Jev synthetic portion (the 86% side where flipping one field must change the label serves as discrimination, the rest as invariance). Natural-language business equivalence classes are left to D-1.
- Consistency uses the **decision-level paired protocol**: cumulative failure set, equivalence-class flip rate, axiom violations. Reporting aggregate accuracy is **forbidden** (across eight orderings accuracy moves < 2 pp while the cumulative failure set grows 27–29%).
- Threshold τ is fitted on held-out labels, separately per (question, level-set version, rule version) triple, never on the test set.

**Degenerate-solution check**: every invariance check in R0 can be passed by a degenerate model that "reads only the question wording and ignores the input". So R0 must also report the **P2″ accuracy floor** (typed-decisions, akhilaaa3, kev binding-v1, Open-Jev synthetic, bev counterfactual) and an explicit degenerate baseline: **replace the whole input with an empty string** and see how much consistency drops. If the degenerate baseline's consistency is within 5 pp of the real model, every consistency number in this round is void.

**Task assignment**:

| Task | Content | Status |
| --- | --- | --- |
| `E-0.1` | Decision-level paired evaluation harness: cumulative failure set, equivalence-class flip rate, margin distribution (distance from cumulative mass to τ ÷ within-class variance) | to do |
| `E-0.2` | Side-by-side report protocol for the four consistency denominators (byte-level rerun / order permutation / answer-preserving adversarial variants / pre-registered equivalence classes) | to do |
| `E-0.3` | Same-backbone label log-probability baseline (checklist item 1; only 5 of 26 papers comply) | to do |
| `E-0.4` | Reproduction of the four pillars: union bound, menu-relativity IIA, joint vs cacheable independent encoding, one generic question zero-shot across benchmarks | to do |
| `E-0.5` | Degenerate baselines (empty input, question wording only) and the P2″ floor | to do |
| `D-0.1` | T1 level-name invariance (built: 24,000 + 2,216 + 30,720 records) | **done** |
| `D-0.2` | T2 definition-swap / level-reorder discrimination (built: 14,400 + 1,314 + 23,040 records) | **done** |
| `D-0.3` | T3 question-set add / remove / reorder invariance (built: 24,000 records) | **done** |
| `D-0.4` | T4 defect-11 control set: same input × N candidates × binned by salience of the required aspect | to do |
| `M-0.1` | Environment: Qwen3.5-0.8B needs transformers 5.x, the RL image pins 4.57.1; must be resolved first (see §5) | **blocked** |

**Outputs**: protocol document + result tables in `experiments/R0/`, plus a one-page "reproduction status of the four pillars". **R0 produces no model weights.**

**Gate G1 is decided after this round.**

---

### R1 Data construction: build the "cross-question re-partition" denominator and rule diversity

**Question**: The discrimination item of P1″ (the same input must move under partition-different questions) has a local denominator of zero; the rule diversity needed to train "the ability to understand business requirements" is also zero (147,139 rows contain only 4,101 distinct question strings). Both are new pairings of existing components, not new task types.

**Registry rows**: 12 (primary-metric denominator), 17 (expert levels), 3 (silent scope omission, corresponding to rule-silent unknown).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R1-1 | "Rule text + code evaluation" can produce same-input × competing-rule pairs, and code labels agree with human spot checks > 95% | If < 95%, the synthetic route's labels are themselves untrustworthy; P1″'s discrimination item must switch to human annotation and the budget changes by an order of magnitude |
| R1-2 | On natural-language inputs, annotator disagreement on business-convention labels is of the same order as typed-decisions' 35% | If significantly lower, "conventions are contestable" was exaggerated; if higher, the P2″ floor itself has a ceiling and must be declared as "the floor measures agreement with the convention, not correctness" |
| R1-3 | Rule-silent unknown (the question does not cover the input) has **no** code-label source; only the rule author can provide it | If it can be generated, the gap of omission 3 becomes cheap and R4's native-unknown training moves earlier |

**Protocol and thresholds**:

- Minimum size of the "cross-question re-partition" denominator: same input × at least 3 competing conventions × at least 2,000 inputs. Discrimination metric: share of inputs whose level distributions under two competing rules have total variation > 0.5.
- Rule-diversity target: **hundreds to thousands of differently phrased rules per input**. Per §6.3.2, the variable that decides whether "defining the task in context" survives is whether the task definition varies across training samples, so the held-out split must cut by **rule family** (Open-Jev v1.1's `family_disjoint … 1 ood` is a ready-made form; 5,120 ood rows exist locally).
- Three datasets are accounted separately and never mixed: **synthetic rules** (code labels; measure the P2″ floor on formal rules), **natural-language conventions** (human labels; measure the semantic half), **rule-silent** (human labels; measure unknown).

**Degenerate-solution check**: the unconstrained optimum on synthetic-rule data is **learning the generator's rule grammar** (a parser). It generalizes to new rules in the same grammar and gives no guarantee on the "milk is a liquid" half. Therefore: (i) the held-out set must contain rules written in a **different grammar**, not merely different rules; (ii) any gain on the synthetic set only counts after independent confirmation on the natural-language convention set; (iii) the synthetic set **must not** serve as P1″'s denominator for business semantics.

**Task assignment**:

| Task | Content |
| --- | --- |
| `D-1.1` | Competing-convention generator: extend the Open-Jev synthetic generator (visible rules, three-valued logic, abstain, family-level hold-out) with a "same input, different rule" pairing layer |
| `D-1.2` | Rule-rewrite diversity: N natural-language phrasings of the same rule (negation, exceptions, nested conditions), held out by grammar family |
| `D-1.3` | Natural-language convention annotation: starting from the dialogue-type inputs of typed-decisions / akhilaaa3, the business side gives convention labels **and annotator disagreement is recorded** |
| `D-1.4` | Rule-silent set: questions deliberately written not to cover the input; the correct output is unknown |
| `D-1.5` | Held-out split and versioning: cut along three axes (rule family, grammar family, level-set version), committed as an immutable manifest |
| `B-1.1` | First draft of the declaration spec for levels and types (name / definition / type all required; harness limits the number of levels) |
| `E-1.1` | Sanity check of the denominator data: competing rules really induce different partitions (not different views of the same rule) |

**Outputs**: three datasets + immutable manifest + an "annotator disagreement measurement" report.

---

### R2 Interface and harness: everything obtainable without touching the weights

**Question**: In the registry, defects whose first-choice fix is "interface" (1, 4, 5, 7) and "structure" (6, 11) are the majority, and RL is the first choice for no row. Take all the weight-free gains first, then talk about training.

**Registry rows**: 1 (rendering fix +0.1511), 4 (outsource arithmetic; numbers through ordered bins, MAE 5.18% → 1.84%), 5 (held-out threshold lifts the rejection rate 7% → 79%), 6 (block-causal / position reset / branch isolation, solved and free), 7 (independent Noul removes menu relativity but costs −8.7 points), 16 (exclusive sets use margin + abstain).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R2-1 | The rendering fix (neutral ids + definitions, code maps back to business names) gives a positive gain on our backbone of the same order as +0.1511 | If negative or zero, one of defect 1's "only paths" breaks and all G2 pressure falls on symbol tuning |
| R2-2 | A held-out threshold lifts the correct-rejection rate on rule-silent unknown from about 7% to > 50% | If it cannot be lifted, native unknown must enter SFT (R4) and "the worst cell" stays worst |
| R2-3 | Cumulative-mass thresholding **beats** argmax and expectation: the decision flip rate when adjacent levels have similar mass is significantly lower | If no difference, P3″'s choice of operator loses its reason and the harness can be simplified |
| R2-4 | The cost of independent Noul scoring on our data is of the same order as −8.7 points; ranking-level IIA is free, probability-level is not | If probability-level IIA is also free, menu relativity (one of the four pillars) does not hold in our setting |
| R2-5 | After outsourcing arithmetic / time questions to code, accuracy on difficulty 3 returns to the difficulty 1 level (around 87.7%) | If it does not return, the failure is not in arithmetic but in "judging that this question needs arithmetic", and the model does not know its own limit (blind spot 3) |

**Protocol and thresholds**:

- Margin distribution is this round's core new metric: **what share of decisions have a distance from cumulative mass to τ that exceeds the score variance within the same equivalence class**. This quantity needs no new labels, only equivalence classes (§2.3 input 2).
- Exclusive / stackable split: exclusive uses candidate isolation + joint softmax + margin + explicit abstain; stackable uses independent Noul per candidate. Each path reports IIA separately (ranking level and probability level).
- Never **argmax**, never **expectation** (expectation hides a bimodal distribution as a middle level).

**Degenerate-solution check**: the unconstrained optimum of the rendering fix is **ignoring names entirely**, which also passes the "level-name invariance" check. So R2-1 must be paired with R0-3's discrimination item: after definition swap / level reorder the distribution **must move**. Both must pass.

**Task assignment**: `E-2.1` cumulative-mass harness with three operators compared; `E-2.2` margin-distribution report; `E-2.3` two-level IIA protocol for exclusive / stackable; `M-2.1` rendering fix; `M-2.2` arithmetic outsourcing and ordered numeric bins; `M-2.3` held-out threshold fitting and the C branch; `B-2.1` harness contract document (thresholds versioned per triple).

**Outputs**: harness implementation + contract document + a gain table "how much is obtainable without touching the weights". Training may begin only after this round.

---

### R3 First SFT round: can the semantics be read back (gate G2)

**Question**: "Names override definitions" is the weakest layer in the whole report, and it is the same thing as requirement (b) of §2.2.1 (business rules change the decision basis). So the rendering fix and symbol tuning are promoted from "optional" to **load-bearing**.

**Registry rows**: 1 (label names override definitions), 17 (expert levels must be read), 8 (ordinal compression), 14 (record vs observation).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R3-1 | After rendering fix + symbol tuning, AUC under the name-definition swap protocol is **significantly above** the 23.2% baseline (decision line: > 60%) | **Failing this fails gate G2**; §8.2.4 item 4 fires: "semantic generalization may be unreachable on this interface" |
| R3-2 | Deleting all definitions **significantly lowers** accuracy (the baseline is "unchanged", 0.8487) | If still unchanged, the model is not reading definitions and symbol tuning failed |
| R3-3 | The k-shot curve after decision tuning **does not flatten** | Flattening fires §8.2.4 item 5: the premise that business staff can configure the model is damaged; G3 warning |
| R3-4 | The level set (K, names, definitions) varying across training samples is a necessary condition for R3-1; the fixed-level-set control group does not reach the decision line | If a fixed level set also reaches it, "the task definition must vary" (§6.3.2) does not hold in our setting |
| R3-5 | On held-out **rule families**, the tuned model **does not regress** relative to untuned readout | Regression means the testable form of "train an ability" fails (criterion of §2.3 input 3) |

**Protocol and thresholds**:

- This round **must** report three groups together: name-definition swap AUC, accuracy difference after deleting definitions, k-shot curves (1/2/4/8/16-shot, one curve before and one after tuning). Nobody in the literature has measured the third (§3.1 blind spot 1), so it is both our decision item and a publishable measurement.
- Hold-out cuts by rule family and grammar family together (D-1.5's manifest).
- Training means are limited to LoRA, data composition, structural isolation and temperature (the four that are demonstrably effective). **No RL this round** (in the registry, RL is the first-choice fix for no row).

**Degenerate-solution check**: the unconstrained optimum of symbol tuning is **ignoring names entirely** (the same degenerate solution as R2); the unconstrained optimum of "train an ability" on synthetic rules is **learning the generator grammar**. Both must be sealed by discrimination items: the distribution must move after definition swap; no regression on held-out grammar families.

**Task assignment**: `M-3.1` symbol-tuning recipe (level set varies across samples); `M-3.2` control group (fixed level set); `M-3.3` LoRA / data composition / temperature ablations; `E-3.1` name-definition swap protocol; `E-3.2` k-shot curves (before and after tuning); `E-3.3` no-regression test on held-out rule families; `D-3.1` resample the training set so that "the level set must vary".

**Outputs**: first set of weights + G2 decision memo. **Gate G2 is decided after this round.**

**Amendment 2026-10-30 (first SFT round, `experiments/R3-SFT-PREREG.md`).** Made before any arm of that
round was trained.

1. **Full fine-tuning admitted for arm K4.** The protocol line above limits training means to LoRA,
   data composition, structural isolation and temperature. Full fine-tuning (all parameters, no LoRA)
   is added as a fifth admitted means, for the prereg's K4 arm only, so that K4's result can be cited as
   an R3 result (prereg §7.5, §12.6, ruling 9). K4 is an improvement arm outside the
   reference-alignment comparison, which is judged on the LoRA arm K1 only. No RL is admitted. Full
   fine-tuning is admitted at 0.8B only. The ladder (prereg §7.6, §14.5) trains with the adopted LoRA
   arm at every size; no full-FT run above 0.8B is admitted by this amendment.
2. **Sequencing deviation, two separate conditions.** (i)
   [`01-work-plan-four-directions.md`](01-work-plan-four-directions.md) §6 item 4, no training aimed at
   consistency before G1: satisfied, because every running arm is accuracy SFT on Kev's public data. The
   consistency-targeted symbol arm K3 is deferred until G1 is decided (prereg §14.5 item 6). (ii) §6
   item 5 and R2's output clause, training only after the R2 harness exists: **not satisfied**. This
   round proceeds on the user's direction of 2026-10-30, not on a methodological argument. The forfeit
   is recorded: Track T in this round runs R0's harness, not the R2 harness, so no result of this round
   may be cited as an R2 gain-table figure or as a harness-corrected number, and no round-1 number is
   evidence for or against G1 (WP-1.9, WP-2.6). This round does not measure R3-1 to R3-3 and does not
   decide G2 (prereg §1.2, §12.1).

---

### R4 Ordinal and unknown structure: write the order and the third truth value into the structure

**Question**: Three of the four output shapes are wrong: boolean lacks a third truth value (restoring P(U) lifts soft accuracy 0.771 → 0.978), the readout for choice is ordinal rather than probabilistic (ordinal-level error 4.2 points, probability-level 21.0 points), and ordinals are systematically compressed (40 datasets × 9 models; scale does not recover it).

**Registry rows**: 8 (ordinal compression), 5 (fallback / unknown), 3 (silent scope omission), 16 (cross-candidate comparability).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R4-1 | K−1 cumulative boolean readouts (order written into the structure) beat a nominal K-way softmax and reduce ordinal compression | If no improvement, the only fix for defect 8 is a coarser scale and the harness must cap the number of levels lower |
| R4-2 | After training a native unknown class, the correct-rejection rate on rule-silent unknown beats R2's held-out threshold | If not better, unknown stays at the interface layer and does not enter SFT, saving this round's training budget |
| R4-3 | Restoring the third truth value lifts soft accuracy on boolean questions by an amount of the same order as 0.771 → 0.978 | If the lift is small, that paper's effect size does not hold on our data |
| R4-4 | The C branch (residual that passes neither threshold) systematically inflates due to ordinal compression; the inflation is measurable and grows as the scale gets finer | If no inflation, the practical effect of ordinal compression on the harness was exaggerated |

**Degenerate-solution check**: the unconstrained optimum of native unknown is **answering unknown to every hard question**. It must be paired with discrimination: the unknown rate on the decidable set must stay low (decision line: < 5%) while the unknown rate on the silent set must be high; both at once. The degenerate solution of an ordinal loss is **a prior by level position** (seen as ordinal compression + middle bias); the discrimination item is that "adjacent-level confusion exceeds distant-level confusion" must hold while the middle level must not be systematically over-filled.

**Task assignment**: `M-4.1` K−1 cumulative boolean readout head; `M-4.2` ordinal / cumulative-link loss; `M-4.3` native unknown class; `E-4.1` ordinal-compression measurement (scale-refinement sweep); `E-4.2` two-sided unknown discrimination; `E-4.3` C-branch inflation; `D-4.1` expansion of the rule-silent set.

---

### R5 Multi-step and distillation: distil reasoning into the readout, decompose rules with the question graph

**Question**: A single-pass model cannot make decisions that are "only possible after writing out intermediate steps" (97.5% solvable in one forward pass, 74% on the rest), and **it does not know its own limit**: the only place in the whole architecture where the failure mode is more hidden than the alternative's (blind spot 3). Rules are read but executed only 22%–72% of the time.

**Registry rows**: 2 (rules read but not executed), 10 (multi-step / stateful), 4 (arithmetic / time).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R5-1 | Splitting a rule into a question graph and asking node by node raises the execution rate above the 22%–72% band | If it does not, defect 2 has no fix and the supported scope of compound rules must be explicitly narrowed for the business |
| R5-2 | **Compositional calibration** after question-graph decomposition is measurable and does not collapse (unmeasured in the whole literature) | If it collapses, decomposition buys execution rate but loses boundability, which conflicts with P3″; decomposition is downgraded to an offline tool |
| R5-3 | Reasoning-to-readout self-distillation reproduces "on par with Jev, about 0.1 s" on our backbone | If not, the main investment direction at endgame size (distillation rather than decision SFT) loses its basis and R6 is redesigned |
| R5-4 | "Reading someone else's chain" gives a positive gain in decision settings (literature: +4.1 pp under a 1,500-token budget, +8.6 pp on truncated items, 71.3% cost saved) | If no gain, the "slow model feeds the readout" cell of S1+S2 cooperation loses its cheapest implementation |
| R5-5 | The model has no signal for "inherited errors" (confidence cannot flag them) | If it can, the severity of blind spot 3 drops; good news for the framework |

**Degenerate-solution check**: the degenerate solution of question-graph decomposition is **collapsing the graph into a chain and answering only the last question**. Discrimination: every node's readout must be separately evaluable, and the product of node-level accuracies must be of the same order as end-to-end accuracy. The degenerate solution of distillation is **learning the teacher's wording rather than its reasoning**; the discrimination item is no regression on held-out rule families (same as R3-5).

**Task assignment**: `M-5.1` question-graph decomposer (labelled: the report's own construct); `M-5.2` reasoning-to-readout self-distillation; `M-5.3` reading others' chains; `E-5.1` compositional-calibration measurement; `E-5.2` signal detection for inherited errors; `E-5.3` node-level vs end-to-end consistency; `D-5.1` paired set for multi-step / stateful judgments.

---

### R6 Ladder ascent and the endgame-size verdict

**Question**: At the 27B tier, decision-tuning gain is only 2.3 points and the new-schema gain is about zero, while letting it reason still clearly beats readout (96.9 vs 89.1). At the same time a domain-tuned small model can beat a general large one (SecJev-0.8B beats Kev-9B by 20.51 pp). So "the endgame must be big" **needs an independent reason**.

**Registry rows**: 15 (expert routing × branch isolation, only if the endgame is 35B-A3B; zero hits), 11 (hybrid vs attention-only).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R6-1 | From 0.6B/0.8B to 2B/4B/9B, the structural changes of R3–R5 have **effects in the same direction**, with magnitude shrinking with scale | If the direction flips, conclusions from the small testbed cannot be extrapolated; the ladder strategy fails and trials must run directly at the large tier |
| R6-2 | At 27B, decision-SFT gain ≤ 3 points (reproducing the 2.3-point regularity) while distillation gain is significantly larger | If the SFT gain is large, "pretraining provides the representation, tuning only adjusts how to read" does not hold and investment returns to decision SFT |
| R6-3 | If 35B-A3B is chosen: per-token expert routing **does** introduce new coupling between isolated question branches | If it does not, defect 15 dissolves and the MoE route is unlocked |
| R6-4 | The endgame-size verdict rests on the gains of "the readout does not lose semantics already in the representation" + "reasoning distilled into the readout", **not** on readout accuracy | If the verdict can finally only rest on accuracy, then P0″'s "the value is in the interface, not accuracy" was never really executed in our engineering decisions |

**Task assignment**: `M-6.1` ladder ascent (2B/4B/9B); `M-6.2` 27B dense pilot; `M-6.3` expert routing × branch isolation probe for 35B-A3B (mandatory before choosing MoE); `E-6.1` cross-scale direction consistency; `E-6.2` endgame-size verdict memo.

---

### R7 Business authors and the template-standard release (gate G3)

**Question**: "Configurable by business staff" is an **assumption** in the whole literature, never a measured property (blind spot 4). Since the deliverable is the template standard, this turns from a side risk into **the product's own risk**.

**Registry rows**: 13 (business authors, zero evaluations), 18 (three properties of retrospective labels), plus omission 2 (in the agent loop the questions are machine-written).

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R7-1 | Questions / levels / criteria written by non-technical business experts following the template standard are readable by the model; the defect rate is significantly below the 91.8% of public SKILL.md files | Failing this **fails G3**: the deliverable becomes "engineer-written templates" and the business value claim is rewritten |
| R7-2 | Templates are compilable and checkable, and must be **compiled per judge** (changing the judge drops 67.70% → 47.87%); our compiler pins one judge version | If changing the judge costs nothing, "compile per judge" for rule artifacts does not hold in our setting and the template standard can be freer |
| R7-3 | Questions generated at runtime by S2 **must pass through a contract** (versioned template + slot filling); freely generated questions make P1″'s denominator change on every call | If free generation also preserves consistency, omission 2 dissolves and S1's guarantees can be passed upward directly |
| R7-4 | Retrospective labels can only refit thresholds, not supervise the readout; using them as an RL reward has the degenerate solution of learning an outcome proxy | If credit assignment is possible, the largest limit of defect 18 is lifted and a production closed loop is feasible |

**Task assignment**: `B-7.1` release candidate of the template standard; `B-7.2` real business-author trial (real people write, not researchers); `B-7.3` template compiler and validator; `B-7.4` retrospective-label contract (engineering handling of the decision-level / selective / delayed properties, including exploration on the rejected side); `E-7.1` evaluation protocol for the author variable (zero evaluations in the literature; this is a new measurement); `E-7.2` partition invariance under question paraphrase (P1″'s third item, omission 4).

**Gate G3 is decided after this round.**

---

### R8 Scheduling-side RL: the only place RL is allowed

**Question**: Across the 18 registry rows, RL is the first-choice fix for none, and no defect in the table involves an intermediate object. RL's real place is **decisions about the computation itself**: which questions to ask, how many loop iterations, when to hand off to the slow model (on-demand depth saves 15–24%). That is scheduling, not readout.

**Locked conclusions (pre-registered)**:

| # | We expect | If reversed, what falls |
| --- | --- | --- |
| R8-1 | RL on the readout is not better than cross-entropy + a proper scoring rule (with known labels both share the optimum) | If RL is significantly better, the conclusions of §6.1 / §6.3 do not hold in our setting and the whole "RL is not the first choice" argument is rewritten |
| R8-2 | RL on scheduling has positive return (saves compute without losing accuracy) | If no return, RL has **no place at all** in this route and the budget moves entirely to interface and SFT |
| R8-3 | Wherever a verifier is the reward it is systematically gamed | If not gamed, verifier rewards are usable and R8's design space grows significantly |

**Degenerate-solution check**: the degenerate solution of scheduling RL is **always choosing the cheapest path** (reject everything / hand everything to the slow model). Discrimination: cost and pass rate must be reported together, against a **model-free deterministic controller** (it solves 79% of τ²-bench telecom).

**Task assignment**: `M-8.1` readout-side RL control (expected negative; a falsification attempt); `M-8.2` scheduling-side RL; `E-8.1` joint cost / pass-rate report against the deterministic controller; `E-8.2` reward-gaming detection.

---

## 4. Round × work-line matrix

| Round | D data | M model | E evaluation | B business | Gate |
| --- | --- | --- | --- | --- | --- |
| R0 | T1–T3 done; T4 control set | environment only, no weight update | protocol + four denominators + four-pillar reproduction + degenerate baselines | — | **G1** |
| R1 | competing conventions / rule diversity / silent unknown | — | denominator sanity | level and type declaration spec | — |
| R2 | — | rendering fix / arithmetic outsourcing / thresholds | cumulative-mass harness / margin / IIA | harness contract | — |
| R3 | resample so the level set must vary | symbol tuning + LoRA ablations | name-definition swap / k-shot / held-out rule families | — | **G2** |
| R4 | silent-set expansion | K−1 cumulative boolean / ordinal loss / native unknown | ordinal compression / two-sided unknown / C inflation | — | — |
| R5 | multi-step paired set | question graph / self-distillation / reading others' chains | compositional calibration / inherited-error signal | — | — |
| R6 | — | ladder 2B–9B / 27B / MoE probe | cross-scale direction consistency | — | — |
| R7 | — | — | author-variable protocol / paraphrase invariance | template release / real-author trial / compiler / retrospective contract | **G3** |
| R8 | — | readout-side RL (falsification) / scheduling-side RL | cost–pass-rate joint report / gaming detection | — | — |

---

## 5. Resources and current blocks

**Ready** (verified 2026-10-28, two NPU hosts `npu` = 100.100.135.175 / `npu2` = 100.100.135.181). **Update 2026-10-30**: host policy since 2026-10-29 is that only `npu` (host 175) is used; `npu2` is off-limits (`experiments/ENV-VERL.md`).

- `agentic-rl-ascend:20261026`: loaded on both hosts, image ID matches the recorded sha256, import smoke test passes. This is the default environment for the initial experiments. Start it with `start_rl_container.sh` (mounts the driver and davinci devices; a bare `docker run` fails at `import torch_npu`).
- `saea-base:20261027`: built on both hosts and passes the smoke test.
- Local mirrors: 24 datasets, Qwen3-0.6B (attention-only) and Qwen3.5-0.8B / 2B / 4B / 9B (hybrid), all under `/mnt/cephfs/xingchao/models/jev`. **Update 2026-10-30**: the 24 datasets are under `/mnt/cephfs/xingchao/omni/datasets/jev/`, not `/mnt/cephfs/xingchao/datasets/jev/`; `/mnt/cephfs/xingchao/models/jev/` holds Qwen3-0.6B and the Qwen3.5 0.8B/2B/4B/9B checkpoints with their `-Base` variants (0.6B re-mirrored 2026-10-30, revision `c1899de2…`).
- T1–T3 task files generated (`/mnt/cephfs/xingchao/experiments/jev/`, with sha256 manifest).

**Block 1 (stalls R0-4, the defect-11 control)**: the RL image pins `transformers==4.57.1`, while Qwen3.5-0.8B's `model_type` is `qwen3_5`, an architecture that only exists in transformers 5.x (the local 5.21.0 wheel has `models/qwen3_5`; 4.57.1 does not). So the RL image can run 0.6B but not its hybrid control. Two options: layer a transformers 5.x venv on the RL image, or use `saea-base:20261027` (transformers 5.21.0 and torch 2.10.0+cpu inside the image) and add `torch_npu`. **One must be chosen before R0 starts.**

**Block 2 (stalls every round that needs an accelerator)**: all 8 cards on both hosts are fully occupied by a vLLM deployment (about 59 GB HBM per card, plus one `minimax_m31_flash` container running on each). T1–T3 on 0.6B/0.8B can run on CPU (256 cores, about 2 TB RAM), slow but feasible; training from R3 onward needs cards. **The machine owner must provide usable card numbers or a time window.** **Update 2026-10-30**: the deployment was gone from host `npu` on 2026-10-29, and the user authorised NPU use on host 175 for the first SFT round on 2026-10-30; its 8 chips are used for R0 scoring and R3. `npu2` stays off-limits.

**Block 3 (stalls half of R1)**: business-convention labels on natural-language inputs can only come from the business side, and typed-decisions measured 35% annotator argmax disagreement under the same criterion; this is not an annotation-budget problem. **The business side must commit annotation hours and accept the protocol "the floor measures agreement with the convention".**

---

## 6. Where this proposal itself is most likely wrong

By the rule of report §8.2.5, the proposal also carries a self-attack:

1. **G1 may fail, and the proposal treats it as the starting point.** Defect 12 (equivalence-class consistency) is "defined by nobody, measured by nobody"; R0's two mechanical equivalence classes are **substitutes**, not business equivalence classes. If conclusions on mechanical classes do not extrapolate to business classes, G1 is a false pass and every later round's primary metric is built on sand.
2. **R1's synthetic route and R3's semantic goal may undermine each other.** Synthetic rules give cheap labels and clean hold-outs, but their degenerate solution (learning the generator grammar) is exactly what R3 must exclude. If the natural-language convention set cannot be made large enough, R3's verdict will be dominated by the synthetic set and G2 will be a false pass.
3. **The round order assumes "interface → SFT → distillation → scheduling RL", and the report withdrew that order.** (§2.3 omission 8: the author withdrew it because no paper has run it.) This proposal re-adopts it on the sole basis of the registry's "type" column, which is **inference, not measurement**. At the end of every round, re-assess whether the next round is still the right next step.
4. **Three of the eight self-made frameworks entered the proposal** (question graph in R5, D4 subset in R0, decision repetition unused). The question graph in R5 carries the highest overfitting risk, and R5-2's compositional calibration has never been measured in the literature; R5 is therefore both an experiment and a validation of a classification we made ourselves.
5. **The four pillars are reproduced in R0, yet R0's conclusions depend on them.** This is a loop: we design the harness with the union bound and then measure the union bound with the harness. R0 must separate the two in time: first measure the union bound with the plainest threshold protocol, then design the harness from the result.
