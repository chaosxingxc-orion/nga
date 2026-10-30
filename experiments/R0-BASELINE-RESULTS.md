# R0 readout baseline: results

> **Erratum pending (note added 2026-10-30, corrected the same day).** **The padding claim does not
> survive a noise floor.** `R3-SFT-PREREG.md` §14.2 and §14.5 item 10 diagnosed the left padding in
> `r0_code/scorer.py`'s `HFScorer` as a systematic perturbation of every batched row. Measurement
> withdrew that diagnosis (§14.6 item 5): in float32 with HF32 matmul disabled, the left-padded R0
> layout differs from the exact unpadded layout by **≤ 1e-4 nats with zero argmax changes** on five
> suites, so left padding itself is not the defect. The 0.157-nats figure was one draw of **bf16
> batch-composition noise**, which is what the numbers below actually carry: in bf16 the padded layout's
> difference from exact (0.74 nats on decision-v7) is the same size as that of unpadded controls (0.74
> and 0.81), and composition noise alone moves sample accuracy by up to 2.6 points. The magnitude of
> that noise in these numbers is being measured on the fixed samples recorded in `R3-SFT-PREREG.md`
> §14.5 item 7 and §14.6 item 3, and the result will be published as an erratum to this file. Until
> then the numbers stand as published with this caveat, and, per R3 §14.2, **they are not used as the
> R0 side of any comparison**. §12.1's and §7.3's "do not retest it" stays **suspended** until the
> erratum reports — but note the expected direction has changed: the retest is now expected to
> **reproduce** §12.1 ground 3's length effect at fp32 rather than overturn it, since the padding
> artifact that could have manufactured it is gone. Ground 1's "an identical constant to every
> candidate" is still not exact under this scorer, because batch composition varies per row.

> 2026-10-29. Results of the first scored pass of the R0 readout baseline, judged against
> `R0-BASELINE-PREREG.md` as it stood before the run. Numbers are taken from
> `/mnt/cephfs/xingchao/experiments/jev/r0_baseline_rederived/report.json` and were re-checked
> against it figure by figure while writing this file.
>
> The report was produced under **amendment 4**. This document is written under **amendment 5**
> (pre-registration §12), which was committed after the report and which changes what two of the
> cells are **measuring**. Where that applies it is stated at the point of reading, not in a
> footnote.
>
> The headline is that the untuned readout fails most of the bars that were fixed before the run.
> That is the measurement. It is not a verdict on the approach and it is not softened here.

---

## 1. Scope

**This is the readout baseline, not round R0.** It is one arm of R0: an untuned decoder read out as a
typed decision over a declared level set, scored on the jev task files that survive locally.

Of the proposal's six pre-registered R0 conclusions (`proposal/00-research-proposal.md` §3, R0):

| Conclusion | Status in this run |
| --- | --- |
| R0-3 — changing level names moves the readout distribution (flip rate > 5%) | **Spoken to directly.** The readout moves far more than 5%. See §3.2 and §6; what the movement *is* is the subject of §6 and §7.1. |
| R0-6 — untuned readout reaches 76%–97% of decision-tuned | **Borne on, not decided.** This run fixes the untuned end of that ratio. The tuned end does not exist yet, so no ratio is computed. |
| R0-1 — the four-denominator consistency spread is at least 30 points | **Untouched.** Only the pre-registered equivalence-class denominator is measured (pre-reg §7 item 3). |
| R0-2 — typed single-pass readout beats same-backbone label log-probability readout | **Untouched.** There is no typed readout here to compare against; this run *is* the label log-probability arm (pre-reg §1, proposal task `E-0.3`). |
| R0-4 — 0.8B hybrid is less accurate than the 0.6B attention-only control on low-salience bins | **Untouched.** `Qwen3-0.6B` is gone from cephfs; defect 11 stays measurement-blocked (pre-reg §7 item 5). |
| R0-5 — the union bound is not overturned in any cell | **Untouched.** Not computed in this run. |

**Gate G1 is therefore not reached.** G1 is decided after round R0, and four of its six pre-registered
conclusions have no numbers.

**Model.** `Qwen/Qwen3.5-0.8B`, at `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B`. The goal named
`Qwen3.5-0.3B`; **that model does not exist.** The family's published sizes start at 0.8B, so 0.8B is
the smallest member of the family the goal named (pre-reg §1). Any later size comparison must start
from 0.8B, not from 0.3B.

---

## 2. Setup and provenance

| Fact | Value |
| --- | --- |
| Host | `npu` (100.100.135.175), 910B3 |
| Chips | 6 shards on physical NPUs 0–5 |
| Start / all shards exited / terminal marker | `2026-10-29T10:33:47Z` / `12:49:34Z` / `DONE` = `rc=0 utc=2026-10-29T12:50:42Z` |
| Wall clock to the marker | 2 h 16 m 55 s |
| Frozen records | 119,690 (T1 56,936 + T2 38,754 + T3 24,000) |
| Scorers | 6: `hf`, `hf+empty_input`, `hf+question_only`, `uniform`, `constant@group70`, `constant@question70` |
| Readout rows | 601,980 = 119,690 × 5 + 3,530 (`constant@question70` covers `akhilaaa3` only) |
| Coverage | expected == got for all six scorers; `missing: []`; `incomplete_scorers: []` |
| Retried shards | none. All six shard logs end `shard N/6 done`; the watchdog reports 0 error lines for this run, only 24 warning lines (CANN `FutureWarning` ×18, one allocator padding warning ×6) |
| Image id | `sha256:4d683043e4bdb7056bf69c2064acbd535d7c9587ccf76c14f70c467e4c24e823` |
| Prompt | `r0-prompt-v2`, format `raw-completion (no chat template)` |
| Render mode | `record_name` — the level **name** as written in the record, plus its definition (pre-reg §8.1: the unmitigated model) |
| Amendment level of the report | 4 |
| Clause declaration | 13 clauses **in force**, each naming the test that asserts it; `not_in_force: []` (pre-reg §11.8 item 3) |
| dtype / device / stack | `bfloat16` / `npu` / transformers 5.14.1, Python 3.12.13 |
| Harness constants | τ grid 0.50–0.95 step 0.05; utility +1 / −1 / 0; `min_fit_items` 20; train share 0.70; ECE bins 10; fallback τ 0.5; `swap_eligible_sides: ["i"]` |

**`git_commit` reads `unknown`, and `git_dirty` reads `false` only because there is no repository to
test.** The scoring container has no `git`, so the harness could not record a commit. The **image id
carries the provenance instead**: it is written into the run log, into the relaunch command, into
every readout file header and into the report header, and it is the same value in all four places.
This is weaker than a commit — it pins the environment, not the harness source — and it is recorded
as a known gap rather than presented as equivalent.

**The report was re-derived from the frozen readouts.** `REDERIVE.md` records why: the readouts were
produced by harness code carrying amendment 4 but not the §11.8 reporting conventions that landed
after the run started. Pre-registration **§11.6** permits recomputing metrics from frozen readouts
and states that doing so is **not a new scored run**, because the model is not re-invoked; the model,
the prompts, the splits and the fitted thresholds are unchanged, and the re-derivation ran on CPU
with no model loaded. The source run's `report.json` was required to be byte-identical afterwards
(`REDERIVE.md` check 1) and was verified unchanged. The two reports differ as expected and only as
expected: the original has no `amendment_clauses` block and **no `B-2_T3` decision line at all**
(see §3.3).

**Source labels.** The report carries four source labels, not three: `akhilaaa3` arrives already split
into `akhilaaa3-hard` and `akhilaaa3-medium` by its own `source` field, 1,108 T1 records each.
`openjev-synth` carries only `ordinal` levels. That gives ten (source, level type) cells.

**Threshold fallback tiers used** (pre-reg §8.3 requires reporting tier usage; primary scorer,
`group70` splitter). Fitted keys: 54 at the (question, level-set version) tier, 29 at the
(source, level type, number of levels) tier, 16 at the (question) tier. Held-out rows decided by each
tier: 31,307 version, 4,161 question, 1,080 type_size, 137 at the default τ = 0.5 — so 0.4% of
held-out rows fell all the way through to the default.

---

## 3. The verdicts

All four decision lines were fixed in pre-registration §3.1 and quantified in §8.5. B-2, its T3
extension and B-3 are evaluated on the **argmax reference column** per §11.2 and §11.8; B-1 is
evaluated on the **cumulative-mass operator**, which §8.2 and §11.2 leave unchanged as the accuracy
floor. Every cell below is the `group70` held-out side unless stated.

| Line | What it required | Result |
| --- | --- | --- |
| B-1 | readout beats the majority-class constant by ≥ 10 accuracy points on every source | **0 of 20 entries pass** (10 cells × T1 and T2 floors) |
| B-2 | T1 argmax flip rate ≥ 10 points **below** the empty-input baseline | **1 of 10 cells passes**, and that cell has a constant arm (§7.2); 1 further cell **voided** under the 5-point rule |
| B-2 (T3) | the same, on the question-set axis | **2 of 3 cells pass**; this line's first appearance in any report |
| B-3 | T2 followed-rate > 30% **and** ≥ 10 points above the T1 flip rate in the same cell | **1 of 10 cells passes** |
| B-4 | training improves held-out accuracy without raising the T1 flip rate by > 2 points | **not evaluated.** `report.json` records `"needs a second report after training; not evaluated here"` |

### 3.1 B-1 — the accuracy floor. Fails on all cells, under the operator and on argmax.

The pre-registered bar is +10 points over the majority-class constant classifier. The primary
readout does not reach it anywhere. It does not reach **zero** points anywhere either: on the
operator column the constant beats the primary in all ten cells, and on the argmax reference column
the best the primary manages is an exact tie.

T1 floor (`original` variant), held-out, `group70`. "operator" is the cumulative-mass decision, the
pre-registered floor; "argmax" is the reference column.

| source | level type | n units | primary, operator | primary, argmax | constant | gap, operator | gap, argmax |
| --- | --- | --- | --- | --- | --- | --- | --- |
| akhilaaa3-hard | boolean | 63 | 1.59% | 49.21% | 50.79% | −49.21 | −1.59 |
| akhilaaa3-hard | nominal | 27 | 3.70% | 11.11% | 14.81% | −11.11 | −3.70 |
| akhilaaa3-hard | ordinal | 30 | 6.67% | 16.67% | 33.33% | −26.67 | −16.67 |
| akhilaaa3-medium | boolean | 31 | 3.23% | 54.84% | 54.84% | −51.61 | **0.00** |
| akhilaaa3-medium | nominal | 22 | 18.18% | 31.82% | 36.36% | −18.18 | −4.55 |
| akhilaaa3-medium | ordinal | 19 | 31.58% | 31.58% | 63.16% | −31.58 | −31.58 |
| openjev-synth | ordinal | 2,296 | 0.00% | 7.53% | 38.63% | −38.63 | −31.10 |
| typed-decisions | boolean | 561 | 43.32% | 52.05% | 66.67% | −23.35 | −14.62 |
| typed-decisions | nominal | 558 | 20.43% | 36.56% | 41.04% | −20.61 | −4.48 |
| typed-decisions | ordinal | 746 | 6.57% | 36.46% | 37.80% | −31.23 | −1.34 |

The T2 `base` floor gives the same picture; the ten T2 entries fail by −8.82 to −48.39 points on the
operator column. The T3 `prefix_1q` floor is reported in the reports but is not part of the
pre-registered B-1 list, which names T1 and T2 only; on `typed-decisions` it tracks T1 closely
(42.60% / 20.61% / 6.84% on the operator column, against the same three constants).

**Pre-registered consequence, applied.** §3.1's "if it fails" column for B-1 reads: *the readout
carries no signal on that source; that source is excluded from training claims.* B-1 fails on every
source, so **no source in this run is admissible for a training claim on accuracy grounds.** B-4
cannot be reached by adding a training run on top of these sources without first clearing B-1.

One near-miss that is **not** a claim. On the question-disjoint split, which pre-registration §2.1
reports additionally for `akhilaaa3` only, `akhilaaa3-medium` boolean is the single cell where the
primary's argmax accuracy exceeds the constant's: 55.81% against 44.19%, n = 43. It carries no
signal: the **question-only and empty-input arms score exactly the same 55.81%**, so the margin over
the constant is reproduced by a model that cannot see the input. On the operator column the same
cell reads 16.28% against 44.19%.

### 3.2 B-2 — T1 name invariance. Passes 1 of 10, and the important fact is the direction of the failure.

| source | level type | n units | primary flip (argmax) | empty-input flip (argmax) | gap (empty − primary) | pass | primary / empty C-branch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| akhilaaa3-hard | boolean | 63 | 33.86% | 7.94% | **−25.93** | no | 0.8968 / 0.9405 |
| akhilaaa3-hard | nominal | 27 | 70.99% | 50.00% | **−20.99** | no | 0.9074 / 0.8889 |
| akhilaaa3-hard | ordinal | 30 | 61.11% | 33.89% | **−27.22** | no | 0.7083 / 0.6417 |
| akhilaaa3-medium | boolean | 31 | 32.80% | 11.29% | **−21.51** | no | 0.8629 / 0.0000 (forced) |
| akhilaaa3-medium | nominal | 22 | 44.70% | 31.82% | **−12.88** | no | 0.7273 / 0.6591 |
| akhilaaa3-medium | ordinal | 19 | 53.51% | 32.46% | **−21.05** | no | 0.7237 / 0.6974 |
| openjev-synth | ordinal | 2,296 | 66.06% | 57.24% | **−8.82** | no | 0.9997 / 1.0000 (forced) |
| typed-decisions | boolean | 561 | 29.23% | 44.18% | +14.94 | **yes** | 0.4193 / 0.4826 |
| typed-decisions | nominal | 558 | 54.24% | 47.52% | **−6.72** | no | 0.8777 / 0.9996 |
| typed-decisions | ordinal | 746 | 53.22% | 57.44% | +4.22 | no — **void** | 0.8616 / 1.0000 (forced) |

The C-branch column is carried beside every flip rate per §11.1, so the degenerate regime is visible
at the point of reading. Three of those rates are flagged `forced_by_tau` under §11.5 and say nothing
about the model: `akhilaaa3-medium` boolean empty-input at 0.0000, because at τ = 0.50 with two levels
abstention is arithmetically impossible, and the `openjev-synth` and `typed-decisions` ordinal
empty-input arms at exactly 1.0000, because every row abstained under the fitted τ. Those two also
carry a **null** thresholded flip rate, per §11.1: a flip rate with no decisions to flip is undefined,
not zero. That convention is the fix for the false zero recorded in §11 of the pre-registration.

**In 8 of 10 cells the real model's argmax flip rate is higher than the empty-input baseline's.** A
model that cannot see the business situation at all is *more* invariant to level names than the model
that can. On `akhilaaa3-hard` boolean the empty-input arm flips on 7.94% of variant pairs and the
real model on 33.86%, a factor of four. This is the single most informative number in the run and it
is not a near-miss on a threshold: the pre-registered bar asked for the real model to be 10 points
**below** the baseline, and it is 6 to 27 points **above** it in eight cells.

The one void cell: `typed-decisions` ordinal, where primary and empty-input flip within 4.22 points of
each other, inside the 5-point window of pre-registration §4 item 1. The report flags it
`t1_void: true`. Its T1 numbers are not usable.

The one pass, `typed-decisions` boolean, **must not be read bare**. Its `original` arm is a constant
classifier (§7.2): the primary chose `true` on **1,800 of 1,800** rows, and the question-only control
agrees with it on **100.00%** of them. The cell's 29.23% flip rate is produced entirely by the other
three name variants, and the margin over the empty-input arm is a margin over an arm that was
*noisier*, not a margin that demonstrates invariance.

**A protocol tension to record rather than resolve.** §3.1's "if it fails" column for B-2 reads *all
T1 numbers in this run are void*; §4 item 1 voids a cell only when the empty-input flip rate is
within 5 points of the real model's. The harness implements the narrower §4 rule and voids one cell;
§11.7 reads §3.1 the wider way, as voiding the run's T1 numbers. The two readings are not reconciled
in the pre-registration and this document does not choose between them. On the wider reading every
T1 number in §3.2 and §6 is void; on the narrower reading one cell is. Either way **no T1 number here
supports a name-invariance claim**, which is the conclusion both readings share.

### 3.3 B-2's T3 extension — question-set invariance. Passes 2 of 3, and exists here for the first time.

Pre-registration §9.2 extended B-2 to the T3 question-set axis in prose. It was never implemented:
the original run's `report.json` has decision lines `B-1`, `B-2`, `B-3`, `B-4` and nothing else.
Amendment 4 §11.8 item 3 froze the rule that an amendment clause without a test is reported as not in
force, and the re-derived report is **the first report in which `B-2_T3` exists at all**, asserted by
`test_a4_b2_extends_to_t3_on_argmax`.

T3 exists only for `typed-decisions`.

| level type | n units | primary flip (argmax) | empty-input flip | gap | pass | primary / empty C-branch |
| --- | --- | --- | --- | --- | --- | --- |
| boolean | 561 | 0.71% | 31.82% | +31.11 | **yes** | 0.4603 / 0.6324 |
| nominal | 558 | 36.89% | 18.97% | −17.92 | no | 0.7679 / 0.9852 |
| ordinal | 746 | 17.58% | 28.17% | +10.59 | **yes** | 0.9028 / 0.9940 |

The pure-ordering pair required by §9.2, `prefix_5q` against `prefix_5q_shuffled`, is the *least*
sensitive of the six pairs in each cell. In the two cells whose arm is not near-constant the gap is
wide: nominal 11.83% against 26.3–56.3% for the five pairs that change the *number* of unrelated
questions, ordinal 11.13% against 13.3–25.5%. In the boolean cell every pair sits at or below 1.43%,
which is a property of the near-constant arm rather than of invariance. Reordering unrelated
questions moves this readout much less than adding them.

The boolean pass carries the same caveat as §3.2's: the arm is near-constant. Measured from the
frozen readouts, the primary chose `true` on 100.00% / 98.89% / 99.94% / 100.00% of rows across the
four prefix variants, so a 0.71% flip rate is what a constant classifier scores, not what an
invariant reader scores. The ordinal pass does not have that defect — its modal level takes 60.29%
to 76.54% of rows depending on variant — and is the one invariance pass in the run that is not
explained by a constant arm.

### 3.4 B-3 — T2 definition-swap discrimination. Passes 1 of 10.

Scored on argmax (§8.2, §11.2), on `swap_*` items whose `base` decision was the swapped-from level,
with the move read from level list positions and never from gold (§8.4). Eligibility is restricted to
side `i` (`swap_eligible_sides: ["i"]`).

| source | level type | followed / eligible | followed rate | T1 flip, same cell | followed − flip | pass |
| --- | --- | --- | --- | --- | --- | --- |
| akhilaaa3-hard | boolean | 1 / 60 | 1.67% | 33.86% | −32.20 | no |
| akhilaaa3-hard | nominal | 0 / 9 | 0.00% | 70.99% | −70.99 | no |
| akhilaaa3-hard | ordinal | 1 / 4 | 25.00% | 61.11% | −36.11 | no |
| akhilaaa3-medium | boolean | 1 / 31 | 3.23% | 32.80% | −29.57 | no |
| akhilaaa3-medium | nominal | 2 / 9 | 22.22% | 44.70% | −22.47 | no |
| akhilaaa3-medium | ordinal | 0 / 2 | 0.00% | 53.51% | −53.51 | no |
| openjev-synth | ordinal | 150 / 586 | 25.60% | 66.06% | −40.46 | no |
| typed-decisions | boolean | 186 / 188 | **98.94%** | 29.23% | +69.70 | **yes** |
| typed-decisions | nominal | 1 / 101 | 0.99% | 54.24% | −53.25 | no |
| typed-decisions | ordinal | 9 / 83 | 10.84% | 53.22% | −42.37 | no |

**Pre-registered consequence, applied.** §3.1's "if it fails" column for B-3 reads: *names dominate
definitions, which is survey §2.2.4 row 1 confirmed locally; symbol tuning becomes load-bearing for
any later stage.* In nine of ten cells the readout follows a definition swap less often than it
changes under a pure rename. Read with §6 and §7.1, the local form of that confirmation is sharper
than the row states it: what dominates the definitions is not the business meaning of the names but
the identifier tokens themselves.

**The single pass, with both of its sides stated.** It rests on a modest eligible set — 188 of 561
units, 373 ineligible because the base decision was not on the swapped-from side — and the followed
rate inside that set is 186 of 188. It is nonetheless real signal, not a counting artifact: the
empty-input control on the same cell follows **0 of 459** eligible units, and the question-only
control follows **0 of 188**. Both degenerate arms score exactly zero where the primary scores 98.94%,
so on this one cell the model is reading the definitions. That is the only cell in the run where
input-independent arms are cleanly separated from the primary on a discrimination metric.

The `reversed` items are reported beside the swaps and are weaker evidence in both directions: the
`uniform` arm scores a followed rate of exactly 1.000 on every `reversed` cell, which is a property of
the reversed mapping and the operator, not of any model. Pre-registration §8.4 already forbids
accuracy claims on `swap_*` and `reversed` rows because their `gold` is stale.

---

## 4. Degenerate baselines: the most informative part of the run

Pre-registration §4 made four degenerate arms mandatory. They are what turn the failures above into a
diagnosis.

**The constant classifier beats the primary everywhere.** Section 3.1's table is the whole statement:
on the pre-registered operator column the majority-class constant wins all ten cells, by 11.11 to
51.61 points on the T1 floor. On the argmax column it wins nine and ties the tenth.

**The question-only baseline — input deleted, question and level set kept — equals or beats the
primary on 6 of 10 cells.** On the pre-registered operator column, T1 floor: it wins
`akhilaaa3-hard` nominal (11.11% vs 3.70%), `akhilaaa3-medium` boolean (54.84% vs 3.23%) and
`akhilaaa3-medium` nominal (22.73% vs 18.18%), and ties `akhilaaa3-hard` ordinal (6.67%),
`akhilaaa3-medium` ordinal (31.58%) and `openjev-synth` ordinal (0.00%, both at the floor). It loses
the three `typed-decisions` cells and `akhilaaa3-hard` boolean. On the argmax column the count is 5 of
10: four exact ties and one win.

**Agreement rates, which say it more directly than accuracy does.** Measured from the frozen readouts
over all 56,936 T1 rows:

| comparison | agreement with the primary's argmax | chance (mean 1 / number of levels) |
| --- | --- | --- |
| question-only | **72.03%** | 25.55% |
| empty-input | **63.16%** | 25.55% |

Per cell, primary against empty-input / question-only: `akhilaaa3-hard` boolean 83.98% / 85.74%,
nominal 59.94% / 65.06%, ordinal 57.39% / 61.27%; `akhilaaa3-medium` boolean 84.77% / 86.13%,
nominal 69.23% / 70.83%, ordinal 55.63% / 63.03%; `openjev-synth` ordinal 75.03% / 75.85%;
`typed-decisions` boolean 62.82% / 83.18%, nominal 40.62% / 53.01%, ordinal 40.39% / 65.06%.

**The conclusion, plainly: the input contributes very little to this readout.** Deleting the business
situation entirely changes the decision on roughly a third of items and leaves accuracy equal or
better on most cells. A measure aimed at this readout is aimed at a system that is mostly not reading
its input.

**The two ablations are not ordered the way their names suggest** (pre-reg §12.8). Question-only
agrees with the primary on 72.03% of T1 items; empty-input, which keeps an `Input:` header above an
empty body, agrees on 63.16%. **Empty-input is the more aggressive ablation of the two**, and neither
is described here as the weaker control. B-2 is defined against empty-input, so B-2 is defined against
the harsher of the two baselines — which makes its 8-of-10 wrong-direction result harder to explain
away, not easier.

**The uniform arm** behaves as the reference point it was meant to be: 0.00% operator accuracy
wherever the operator can abstain, a followed rate of exactly 1.000 on every `reversed` cell, and a
T1 flip rate that is a property of the tie-breaking rule rather than of any model.

---

## 5. The threshold picture: this model is better off declining than answering

This is a headline finding of the run, not an operational footnote, and pre-registration §11.3
requires it to be reported as one.

Across the primary scorer's fitted entries on the **train side**, which is the side thresholds are
fitted on (`group70`, 41 entries; 39 of them have held-out rows to apply to):

| statistic | count |
| --- | --- |
| fitted entries | 41 |
| entries flagged `collapsed` | **33** |
| entries whose fitted τ is 0.95, the top of the grid | **20** |
| entries with **no decisive τ anywhere in the grid** | **6** |
| entries with a decisive τ carrying **positive** utility | **14** |
| entries with a decisive τ carrying zero or negative utility | 21 |

A τ is **decisive** only if it abstains on at most half the fitting rows (§11.8 item 2). A fitted τ of
0.95 on this grid means the operator abstains on almost everything: in 20 of 41 entries the fit chose
exactly that, because every decisive τ in the grid scored negative utility and abstaining scored
zero. The fitted-τ histogram is 0.95 ×20, 0.60 ×7, 0.55 ×5, 0.85 ×3, 0.80 ×2, and one each at 0.50,
0.65, 0.70, 0.90.

**The 14 entries that do have a decisive τ with positive utility have tiny margins.** Their utilities
run +1, +3, +3, +3, +3, +5, +5, +10, +68, +77, +78, +357, +368, +414, on 20 to 1,242 fitting rows:
**+0.025 to +0.337 of utility per fitting row**, on a scale where one correct decision scores +1 and
one wrong decision scores −1. The eight small ones sit on 20 to 55 fitting rows.

Held-out C-branch rates follow: 0.9997 on `openjev-synth` ordinal (3 actual decisions out of 2,296
units), 0.90 and 0.88 on `typed-decisions` ordinal and nominal, 0.86 to 0.91 on the `akhilaaa3`
boolean and nominal cells, and 0.42 on `typed-decisions` boolean, the only cell where the operator
commits on most rows. The share of held-out rows falling inside a collapsed fitted entry is 1.0000 on
`openjev-synth` ordinal and on both `akhilaaa3` boolean cells, 0.9655 on `typed-decisions` ordinal,
0.7333 / 0.7301 / 0.6477 / 0.6316 on four more, and lowest at 0.4925 and 0.4827.

**The objective was deliberately not retuned, and §11.3 is the reason.** That clause is a prohibition:
*"It is explicitly forbidden to refit, reweight or re-grid the objective in order to avoid total
abstention."* The collapse is one of this baseline's findings. For this untuned readout on these
tasks, under the frozen utility, a system that refuses to answer scores better than one that answers.
That is the honest baseline result and it is the motivation for the training programme, not an
obstacle to measuring one. Retuning the objective until the operator commits would have converted the
finding into a worse number that read better.

One consequence for reading §3.1: because the operator abstains on most rows in most cells, the
operator-column accuracies in that table are low partly *because* the operator declines, and the
argmax column beside them is the statement about the model. Both are reported, and neither is
reported alone, per §11.8 item 1.

---

## 6. Mechanism: a prior over identifier tokens

**This section is the project's own analysis of this run's frozen readouts, not a literature
conclusion.** The concentration figures below were computed by reading the `readouts/*.jsonl` files
directly; the empty-input and agreement figures are in the report and in pre-registration §12.2.

### 6.1 Argmax concentrates far above chance, and *which* level it concentrates on changes with the name variant

On `openjev-synth` ordinal, where 5 levels put chance concentration at 20%, the modal argmax position
takes:

| name variant | modal position | share of items | label at that position |
| --- | --- | --- | --- |
| `letters` | 0 | **99.97%** | `a` |
| `digits` | 2 | **87.25%** | `3` |
| `original` | 0 | 60.65% | `0` |
| `random` | 0 | 56.15% | a six-character random string |

Renaming the levels and changing nothing else moves the model from answering "position 0" on
essentially every item to answering "position 2" on seven items in eight. Both are near-constant
classifiers; they are near-constant on *different constants*, selected by the identifier set.

Concentration is graded elsewhere and never at chance. The weakest cell is `typed-decisions` nominal,
at **37.61% to 46.11%** across the four variants against 20% chance. `typed-decisions` ordinal runs
60.38% to 77.79% against 20%; `akhilaaa3` nominal runs 23.08% to 79.49% against 3.8% chance over 26
levels; the `akhilaaa3` boolean cells run 58.59% to 99.22% against 50%.

Position concentration and identifier concentration come apart, and the gap is itself diagnostic.
`typed-decisions` boolean `original` concentrates on **position 1 at 66.67%** but on the **identifier
`true` at 100.00%**, because the level order differs by question (1,200 rows list `false` first, 600
list `true` first). Conversely `typed-decisions` nominal concentrates on a *position* at 37.6–46.1%
while its modal *identifier* takes only 11.1–16.7%, and `akhilaaa3` nominal concentrates on position 0
at 23–79% while no identifier takes more than 5.1%. Where the identifiers are stable strings the
prior attaches to the string; where they are not, it attaches to the slot.

### 6.2 The decisive evidence: the arm that reads nothing flips as much as the arm that reads everything

| cell | primary T1 flip (argmax) | empty-input T1 flip (argmax) |
| --- | --- | --- |
| typed-decisions boolean | 29.23% | **44.18%** |
| typed-decisions nominal | 54.24% | 47.52% |
| typed-decisions ordinal | 53.22% | **57.44%** |
| openjev-synth ordinal | 66.06% | 57.24% |

The empty-input arm has no business situation to read at all. It still flips at 44 to 57 percent when
only the level names change, and on `typed-decisions` boolean and ordinal it flips **more** than the
real model. Primary and empty-input choose the same level on **63.16%** of all 56,936 T1 items against
**25.55%** chance agreement.

**Consequence, frozen in §12.2.** The T1 flip rate as measured here is predominantly a statement about
the **identifier set**, not about the model's reading of names in context. That makes identifier
choice mostly a **harness design decision** rather than a training problem — which is a cheaper fix
than a name-sensitivity finding would have implied. Two exceptions are carried through this document:
`openjev-synth`, where the identifier is semantically load-bearing and the data needs rebuilding
rather than relabelling (§7.1), and `akhilaaa3`, where the question genuinely is about names (§7.3).

### 6.3 One mechanism accounts for all three failures at once

A readout that is near-constant *per name variant* and picks a different constant for each variant
fails B-1, B-2 and B-3 simultaneously, and for the same reason:

- it **cannot beat a majority-class constant** (B-1), because it is approximately a constant
  classifier whose constant was chosen by the identifier set rather than by the label distribution;
- it **cannot be name-invariant** (B-2), because the constant it picks is a function of the names;
- it **cannot follow a definition swap** (B-3), because swapping two definitions leaves the
  identifiers in place and the identifiers are what it is responding to.

The empty-input arm reproduces much of this — the same concentration, comparable flip rates, 63.16%
agreement — which is what makes the explanation a mechanism rather than a restatement.

---

## 7. Open and settled questions

### 7.1 Settled: `openjev-synth` ordinal T1 is a label/definition conflict, not a renaming

**This is the largest defect found in the run.** The question is *"How many of the four requirements
are established for this candidate?"* and the `original` level names are literally the counts `0`–`4`.
The `digits` variant relabels them `1`–`5` while leaving the definitions untouched, so the rendered
prompt contains lines such as

```
- 1: Exactly 0 of the 4 numbered requirements are established.
```

The identifier contradicts its own definition, in a task whose answer **is** a number. Verified
directly in the frozen task file: for every group, `digits` carries names `1`–`5` against definitions
reading "Exactly 0" through "Exactly 4", while `letters` carries `a`–`e` and `random` carries
six-character strings against the same definitions.

This covers **7,680 of 14,234 T1 units, 54%**, so it is not a corner case. Pre-registration §12.3
forbids reporting this source's T1 flip rate, accuracy or invariance numbers **as name invariance**;
they are reported in §3 and §6 above as what they are, a label/definition conflict. Where it matters
most: this source's 66.06% T1 flip rate, the highest in the run, is partly the model preferring a
coherent reading of a contradictory prompt, which is not the thing B-2 was built to measure. The
87.25%-on-position-2 concentration under `digits` is the same observation from the other side — under
`digits`, position 2 carries the label `3`.

A weaker form of the same problem exists in **every** ordinal cell, where `original` names are rank
indices. Rebuilding this source's T1 requires choosing identifiers that are not themselves the answer;
relabelling alone cannot fix it. Until then **no name-invariance claim rests on this source.**

### 7.2 Settled: the single B-2 pass rests on a cell with a constant arm

`typed-decisions` boolean, the one cell that passes B-2, chose `true` on **1,800 of 1,800** rows in its
`original` variant, and the question-only control agrees with the primary on **100.00%** of them. Both
counts were verified directly from the frozen readouts. That arm is a constant classifier wearing the
primary's name, so the cell's 29.23% flip rate is produced entirely by the other three variants, and
the pass is reported with this caveat attached and never as a bare pass (§12.4). The same holds for
the T3 boolean pass (§3.3), whose arm is `true` on 100.00% / 98.89% / 99.94% / 100.00% of rows across
the four prefix variants.

This is exactly the suspicious-success case that `CLAUDE.md` §7.1 exists to catch, and it was found by
asking what the number would be if the model were replaced by a constant — the check §9.4 already says
belongs before every scored run.

### 7.3 Settled negative: the candidate-length confound was tested and is not material. Do not retest it.

Candidate levels are scored by an **unnormalized sum** of the log-probabilities of their identifier
tokens, so a name tokenizing into more pieces could in principle be disfavoured. The hypothesis that
this drove the T1 flip rate was tested and **does not hold**, on three independent grounds recorded in
pre-registration §12.1:

1. On **73.97%** of all 56,936 T1 rows every candidate in the prompt has the **same** token count, so
   the missing normalization adds an identical constant to every candidate and cannot change the
   argmax. On those rows it is an exact no-op, not an approximation.
2. Restricting each cell to pairs where length cannot discriminate leaves the flip rate **equal or
   slightly higher, never lower**. Three of the six variant pairs are length-fair at full sample size
   on `openjev-synth` and `typed-decisions`, which is where the flip mass lives.
3. The mechanical length effect has the **wrong sign**. Measured with position controlled on the
   semantics-free `random` labels, longer identifiers score **higher**: +0.154 nats per token on
   `openjev-synth` and +0.44 / +0.49 on the two `akhilaaa3` sources, against a within-item score
   spread of 2 to 3 nats.

Per-token mean normalization is therefore **not** adopted, and normalization would make measured name
sensitivity **worse**, not better: sweeping the unrecoverable softmax constant moves the pooled T1
flip rate up from 56.91% to between 58.83% and 65.50%. The question §12.1 answers is closed; the fix
§12.6 records instead is to store the raw per-candidate score and, where possible, to make candidates
tokenize to equal length so the dimension does not exist.

Two figures in this subsection — the 73.97% and the per-token nats — could not be re-verified while
writing this document, because no tokenizer library is installed on the workstation and the model's
tokenizer is only reachable from inside the scoring container. They are quoted from §12.1 as frozen
there and are flagged here as not independently re-checked.

### 7.4 `akhilaaa3` is the exception, and the only source a name-rendering claim may rest on

Unlike the other sources, `akhilaaa3` carries a genuine input-dependent component. Its `original`
names are real business words, and the primary flips far above the empty-input arm:

| cell | primary T1 flip | empty-input T1 flip | ratio | n units |
| --- | --- | --- | --- | --- |
| akhilaaa3-hard boolean | 33.86% | 7.94% | 4.3× | 63 |
| akhilaaa3-hard nominal | 70.99% | 50.00% | 1.4× | 27 |
| akhilaaa3-hard ordinal | 61.11% | 33.89% | 1.8× | 30 |
| akhilaaa3-medium boolean | 32.80% | 11.29% | 2.9× | 31 |
| akhilaaa3-medium nominal | 44.70% | 31.82% | 1.4× | 22 |
| akhilaaa3-medium ordinal | 53.51% | 32.46% | 1.6× | 19 |

Per §12.7, **any claim that name rendering is a training problem rather than a harness decision must
be supported on this source, not on the others.** And these are small, noisy cells. Held-out
`group70` cells hold **19 to 63 units**, the question-disjoint held-out cells hold 17 to 43, and the
watchdog flagged **26 primary values below the minimum sample count** in this report — the smallest
being `akhilaaa3-hard` nominal `failure_set_T1.n_units = 27`. Every `akhilaaa3` figure in this document
carries its sample size for that reason. Nothing here is a precise estimate; the direction is
consistent across all six cells, the magnitudes are not reliable.

### 7.5 Open: ties at the top, now an abstention, and the position effect they manufacture

Under bf16, **5.21%** of all T1 rows (2,966 of 56,936) have two or more candidates tied at exactly the
top probability. Measured per cell, the rate is concentrated:

| cell / variant | tie rate |
| --- | --- |
| typed-decisions ordinal `digits` | **16.00%** |
| openjev-synth ordinal `original` | **14.10%** |
| typed-decisions nominal `digits` | 11.11% |
| typed-decisions nominal `letters` | 9.67% |
| typed-decisions boolean `letters` | 8.78% |
| openjev-synth ordinal `digits` | 7.79% |
| all `akhilaaa3` cells | ≤ 2.56% |
| every `random` variant | 0.00% |

`argmax` breaks those ties to the lowest index, which inflates `openjev-synth` `original`'s
position-0 rate by about **5.95 points** — so the 60.65% in §6.1 is about 54.7% once ties are removed.
Pre-registration §12.5 now makes an exact tie at the top an **abstention** rather than a vote for the
first-listed candidate, with the tie rate reported per cell. The numbers in this document were
produced under amendment 4 and therefore still resolve ties toward position 0. What that rule changes
is bounded by the table above: it cannot touch any `random` variant or any `akhilaaa3` cell
materially, and it is largest where the concentration claims are already strongest.

**Still open, and stated as open.** The tie rule has not been applied to any number here, and
amendment 5 does not say how an item that abstains on a tie should be counted inside a *pair*-based
flip rate, a move rate, or an accuracy floor. Until that is fixed the re-derived numbers under §12.5
cannot be produced. See §9 item 1.

### 7.6 Checked and dismissed: duplicate level names

A duplicate level name inside one record would collide in the label-to-id map and could manufacture
both ties and flips. Checked directly over the task files: **0 of 56,936 T1 records have a duplicate
level name.** Not a contributor.

---

## 8. What this run may not claim

Pre-registration §7 stands as written, with two additions.

1. **It does not close G1.** G1 needs the cross-question re-partition denominator, which is zero
   locally (proposal R1). This run measures within-question invariance and the floor only.
2. **Its equivalence classes are mechanical, not business classes.** Level-name substitution stands in
   for business equivalence — the substitution flagged in proposal §6 item 1. Amendment 5 §12.2 and
   §12.3 narrow it further: on 54% of T1 units the substitution is not even a renaming (§7.1), and
   where it is, it is predominantly measuring an identifier prior (§6.2).
3. **Three of the four consistency denominators are not measured.** Only the pre-registered
   equivalence class is. Byte-level rerun is trivial under greedy decoding; order permutation and
   answer-preserving adversarial variants need data that no longer exists locally. This is why R0-1 is
   untouched.
4. **Rule diversity is near zero on the largest source.** `openjev-synth` carries exactly one distinct
   `qname` across 30,720 records, so any generalization claim on it is a claim about one question.
   `typed-decisions` has 15. The question-disjoint split exists only for `akhilaaa3`, 545 distinct
   questions, on cells of 17 to 43 held-out units.
5. **No hybrid versus attention-only control.** `Qwen3-0.6B` is gone from cephfs; defect 11 stays
   measurement-blocked, and R0-4 has no numbers.
6. **T3 is measured** (limitation 6 of §7 was withdrawn by §9.1), but only on `typed-decisions`, and
   its boolean cell's arm is near-constant (§3.3).
7. **B-4 is untouched**, because no training run has been scored against this baseline. §3.1 makes B-4
   the only claim this run family may make about training, and it needs a second report produced
   under the same prompt version (§8.7). `report.json` records B-4 as not evaluated.
8. **No accuracy claim on T2 `swap_*` or `reversed` rows**, whose `gold` is known stale (§8.4), and no
   model-selection conclusion of any kind: one model, one size, one prompt version.

What the run *does* establish, stated as narrowly as it was measured: on these six task files, this
untuned 0.8B readout fails the pre-registered accuracy floor on every source, fails name invariance in
the wrong direction on 8 of 10 cells, fails definition discrimination on 9 of 10, and is better off
abstaining than answering under the frozen utility on 33 of 41 fitted threshold entries. The
measurement itself is sound: coverage is complete, no shard was retried, and the readouts carry
probability vectors that vary correctly across variants.

---

## 9. Defects in amendment 5 found while writing this document

Written against amendment 5. Amendment 6 (`R0-BASELINE-PREREG.md` §13), committed alongside this
document in `76bc56a`, resolved five of the six; the status labels below were added 2026-10-30. This
document still changes no pre-registration, harness, data or run output.

1. **Specification fixed by amendment 6 (`R0-BASELINE-PREREG.md` §13.1); the numbers in this
   document are not re-derived under it.** **§12.5 is under-specified and cannot be
   implemented as written.** It makes an exact tie at the top an abstention in the argmax reference
   column, but does not say how an abstaining item is scored inside the metrics that consume that
   column: whether a variant pair containing one abstention counts as a flip, as an agreement, or is
   dropped from the denominator; whether an abstaining item is ineligible for the T2 move metric or
   counted as unmoved; and whether it is a failure in the accuracy floor. §11.1's "a rate whose
   denominator of actual decisions is zero is undefined" implies dropping, but that is an inference. A
   clause for each of the three metrics is needed before the numbers can be re-derived. The
   re-derivation itself is cheap and needs no NPU — ties are visible in the stored `p` vectors — so
   this is a specification gap, not a cost problem.
2. **Still open (2026-10-30): amendment 6 does not address it.** **§12.5 blurs the §11.2 label.**
   §11.2 calls the argmax column "a statement about the model"; making it abstain on ties makes it
   partly a statement about the harness, which is the distinction §11.8 item 1 exists to keep sharp.
   Worth a sentence deciding which it now is.
3. **Specification fixed by amendment 6 (§13.3); the numbers in this document are not re-derived
   under it.** **§12.6's "within-item differences are already exact" is true
   algebraically and false of the stored values.** `log p_i − log p_j = s_i − s_j` holds in exact
   arithmetic, but the 5.21% of T1 rows with exact ties are rows where that difference has already
   been lost to bf16 and to the stored precision. The raw-score field §12.6 mandates will fix this
   going forward; the sentence as written overstates what the existing readouts support.
4. **Specification fixed by amendment 6 (§13.2); the numbers in this document are not re-derived
   under it.** **§12.6's equal-tokenization requirement conflicts with §8.1 on
   T1.** §8.1 freezes the baseline to render the level `name` **as written in the record**, because
   that is the manipulation under test. §12.6 says candidates "should" be made to tokenize to an equal
   number of tokens where possible. On T1 both cannot hold: equalizing token counts means changing the
   names. The clause needs an explicit carve-out for T1, or a statement that it applies to the
   training interface and to later arms but not to this baseline.
5. **Fixed by amendment 6 (§13.4), corrected in place in §12.7.** **§12.7's sample-size range disagrees with the report.** It says
   `akhilaaa3`'s held-out cells are "27 to 34 units". `report.json` gives **19 to 63** on the
   `group70` held-out side (boolean 63 and 31, nominal 27 and 22, ordinal 30 and 19) and 17 to 43 on
   the question-disjoint held-out side. The "26 primary values flagged below the minimum sample count"
   in the same clause does match the watchdog exactly.
6. **Specification fixed by amendment 6 (§13.5); the numbers in this document are not re-derived
   under it.** **The §3.1 / §4 void rule is still ambiguous**, as recorded at
   the end of §3.2 above. §3.1 voids all T1 numbers in the run when B-2 fails; §4 item 1 voids a cell
   when the empty-input flip rate is within 5 points. The harness implements the narrower rule. Both
   readings reach the same conclusion here, so nothing in this document turns on it, but the next run
   should not have to re-derive the question.

---

## 10. Pointers

| What | Where |
| --- | --- |
| Authoritative numbers (amendment 4, §11.8 conventions) | `/mnt/cephfs/xingchao/experiments/jev/r0_baseline_rederived/report.json`, `report.md` |
| Original run report, left untouched | `/mnt/cephfs/xingchao/experiments/jev/r0_baseline/report.json`, `report.md` |
| Frozen readouts, the run's evidence | `/mnt/cephfs/xingchao/experiments/jev/r0_baseline/readouts/` |
| Operational record | `run.log`, `heartbeat.log`, `DONE`, `WATCH.json`, `logs/shard[0-5].log`, `relaunch.sh` |
| Why the report was re-derived, and its acceptance checks | `/mnt/cephfs/xingchao/experiments/jev/r0_baseline/REDERIVE.md` |
| Watchdog digest covering this run | `/mnt/cephfs/xingchao/experiments/jev/_watchdog/digest.md`, `digest.json` |
| The specification this run was held to | `experiments/R0-BASELINE-PREREG.md` |
| Round plan, R0 conclusions, gate G1 | `proposal/00-research-proposal.md` §3 |
