# R0 baseline run: pre-registration

> 2026-10-29 · Committed **before** the run. After the run only results are filled in; no definition,
> split or threshold in this file is changed afterwards (proposal `00-research-proposal.md` §0 rule 3).
>
> Scope: this is a **subset of R0**, not all of it. It covers what the surviving local data can
> measure. It does **not** close gate G1. See §7 for what it cannot claim.

---

## 1. What this run is

The first baseline on NPU host `npu` (100.100.135.175): an **untuned** decoder read out as a typed
decision, measured on the jev task files that survive locally, followed by a first training run on
the same interface. No result here is a model-selection conclusion.

**Model.** The goal named `Qwen3.5-0.3B`. **That model does not exist.** The Qwen3.5 family's
published sizes are 0.8B, 2B, 4B, 9B, 27B, 35B-A3B, 122B-A10B and 397B-A17B (HuggingFace API,
checked 2026-10-29). The substitution is **`Qwen/Qwen3.5-0.8B`**, the smallest member of the family
the goal named. It is also the hybrid half of the defect-11 control pair (survey §2.2.4 row 11).

**Readout.** The model is a plain decoder, not a Jev-class typed model. The readout is therefore the
**same-backbone label log-probability** over the declared level set: for each item, score every
level, normalize over the level set, and take the resulting distribution as the typed readout. This
is checklist item 1 of survey §7.1, with which only 5 of 26 papers comply, and it is proposal task
`E-0.3`. Levels are rendered as **neutral identifiers plus definitions**, with the harness mapping
back to business names (the rendering fix, survey §2.2.4 row 1).

**Decision operator.** Cumulative-mass thresholding with the residual going to C, per P3″. `argmax`
is recorded **only as a reference column** and is explicitly **not** the harness operator. No
expectation is computed anywhere (P3″).

---

## 2. Data, frozen

All counts verified against `/mnt/cephfs/xingchao/experiments/jev/manifest.json` and the files
themselves on 2026-10-29.

| File | Records | Groups | Role |
| --- | --- | --- | --- |
| `T1_level_names/typed-decisions.jsonl` | 24,000 | 1,200 | invariance |
| `T1_level_names/openjev-synth.jsonl` | 30,720 | 3,840 | invariance |
| `T1_level_names/akhilaaa3.jsonl` | 2,216 | 554 | invariance |
| `T2_definition_swap/typed-decisions.jsonl` | 14,400 | 1,200 | discrimination |
| `T2_definition_swap/openjev-synth.jsonl` | 23,040 | 3,840 | discrimination |
| `T2_definition_swap/akhilaaa3.jsonl` | 1,314 | 586 | discrimination |

**T1** holds four variants per group: `original`, `digits`, `letters`, `random`. Only the level
**names** change; input, question and definitions are identical. The readout **must not move**.

**T2** holds `base`, `swap_i_j` and `reversed` variants. The level **definitions** are swapped or
reordered. The readout **must move, and move with the swap**.

**T3 is unavailable.** Its directory is empty; the source datasets it was derived from are gone from
cephfs. Question-set add/remove invariance is therefore **not measured in this run**.

### 2.1 Splits, frozen before the run

- Split unit is `group_id`, so all variants of a group land on the same side. A group never
  straddles the split.
- 70 / 30 train / held-out, split by a SHA-256 hash of `group_id` so it is reproducible and does not
  depend on file order.
- Thresholds are fitted **only** on the train side and applied unchanged to the held-out side
  (survey §2.2.4 row 5; proposal R0 protocol).
- A **question-disjoint** split is additionally reported **only for `akhilaaa3`** (545 distinct
  questions). It is **not possible** for `openjev-synth`, which has **one** distinct question across
  30,720 records, and is near-meaningless for `typed-decisions`, which has 15. This is the local form
  of the rule-diversity gap recorded in survey §6.1.4.3.

---

## 3. Metrics, defined before the run

Reported per source and per `level_type` (`boolean` / `nominal` / `ordinal`), never pooled into one
headline number. Aggregate accuracy as a consistency metric is **forbidden** (proposal R0 protocol).

1. **Accuracy floor (P2″).** Accuracy on the `original` (T1) and `base` (T2) variants against `gold`,
   under the cumulative-mass operator, with the argmax reference column beside it. Reported
   decision-level, with the cumulative failure set, not as a single mean.
2. **T1 flip rate (invariance).** Over each group, the fraction of the 6 unordered variant pairs
   whose decisions differ. Lower is better. Reported overall and per variant pair, so that
   `random`-name effects are separable from `digits` and `letters`.
3. **T2 move rate (discrimination).** For a `swap_i_j` item whose `base` decision was level `i`, the
   swap is **followed** if the decision becomes `j`. Reported as: followed, unmoved, moved elsewhere.
   `reversed` items are scored the same way against the reversed mapping.
4. **Margin distribution.** The share of decisions whose distance from cumulative mass to τ exceeds
   the within-group score variance (P3″, proposal R2 core metric). Needs no new labels.
5. **C-branch rate.** Share of decisions where neither side clears τ.
6. **Calibration.** ECE on the held-out side against gold.

### 3.1 Decision lines, set now

| # | Expectation | If it fails |
| --- | --- | --- |
| B-1 | The untuned readout beats the majority-class constant classifier by at least 10 points of accuracy on every source | The readout carries no signal on that source; that source is excluded from training claims |
| B-2 | T1 flip rate for the real model is at least 10 points below the empty-input degenerate baseline | The invariance number is an artifact of the degenerate solution and **all T1 numbers in this run are void** (proposal R0 degenerate check) |
| B-3 | T2 followed-rate is above 30% and clearly above the T1 flip rate on the same groups | Names dominate definitions, which is survey §2.2.4 row 1 confirmed locally; symbol tuning becomes load-bearing for any later stage |
| B-4 | Training on the train split improves held-out accuracy without raising the T1 flip rate by more than 2 points | Training bought accuracy by breaking invariance; the recipe is rejected regardless of its accuracy gain |

B-4 is the **only** claim this run may make about training. Anything else requires data this run
does not have.

---

## 4. Degenerate baselines, mandatory

Run and reported alongside every number above, never omitted:

1. **Empty input.** The input is replaced by an empty string, everything else identical. If its T1
   flip rate is within 5 points of the real model's, the invariance result is void (B-2).
2. **Question wording only.** Input dropped, question and level set kept. Seals the "read only the
   question, ignore the input" degenerate optimum (P2″).
3. **Constant classifier.** Always the majority level per question. The accuracy floor must clear it
   (B-1).
4. **Uniform.** Equal mass on every level, as the calibration and margin reference point.

---

## 5. Training run

Purpose is to show the pipeline trains and optimizes, not to claim a tuned model.

- Framework verl, FSDP backend, on the Ascend 910b image, 2 NPUs per instance.
- Objective: cross-entropy on the level distribution, which for a pure readout shares its optimum
  with a proper scoring rule (survey §6.3.4). **No RL**, per the registry reading that RL is the
  first-choice fix for no row.
- Train split only. Level sets vary across samples by construction, since T1 carries four name
  variants per group; this is the minimum form of the condition in survey §6.3.2.
- Report the before and after of every §3 metric, not accuracy alone.

---

## 6. Environment, pinned

Host `npu` (100.100.135.175), 910B3. Image: the official Ascend verl 910b image with the
`ascend910b` kernel set. The earlier custom image cannot execute any Ascend op on this silicon and
is not used. 2 NPUs per container instance. Exact image id recorded in `ENV-VERL.md`.

---

## 7. What this run cannot claim

Stated now so the result is not over-read later.

1. **It does not close G1.** G1 needs the cross-question re-partition denominator, which is zero
   locally (proposal R1). This run measures within-question invariance and the floor only.
2. **Its equivalence classes are mechanical, not business classes.** Level-name substitution is a
   substitute for business equivalence, exactly the substitution flagged in proposal §6 item 1.
3. **Three of the four consistency denominators are not measured.** Only the pre-registered
   equivalence class is. Byte-level rerun is trivial under greedy decoding; order permutation and
   answer-preserving adversarial variants need data that no longer exists locally.
4. **Rule diversity is near zero on the largest source.** One question across 30,720 records means
   any `openjev-synth` generalization claim is a claim about one question.
5. **No hybrid versus attention-only control.** That needs `Qwen3-0.6B` alongside, which is also gone
   from cephfs. Defect 11 stays measurement-blocked.
6. **T3 is missing**, so question-set add/remove invariance is unmeasured.

---

## 8. Amendment 1, 2026-10-29, before any scored run

No scored number has been produced. Building the harness exposed one logical error and several
under-specifications in §1 to §7. They are corrected here rather than silently in code. Everything
below is frozen on the same terms as the rest of this file.

### 8.1 Correction: the baseline renders level **names**, not neutral identifiers

§1 said the readout renders levels as neutral identifiers plus definitions. Applied to T1 that is
**self-defeating**. T1's four variants differ **only** in each level's `name`; `id` and `definition`
are byte-identical across them, which I verified directly. Rendering by neutral id therefore makes
all four prompts identical, the flip rate is 0 by construction, it equals the empty-input baseline,
and decision line B-2 can never pass.

The deeper error: neutral rendering **is the mitigation** for defect 1 (names override definitions,
survey §2.2.4 row 1). A baseline that applies the mitigation cannot measure the defect.

**Corrected.** The baseline renders the level `name` as written in the record, plus the definition.
This is the unmitigated model, and it is what R0-3 asks for. Neutral rendering becomes a **separate,
later arm** measuring the rendering fix as an intervention (proposal R2-1), not part of this
baseline. The rendering mode is recorded in every report header.

### 8.2 The move metric is scored on argmax, not on the thresholded decision

The cumulative-mass operator for ordinal levels is a two-tail quantile rule along the declared
order. It is **not permutation-equivariant**, so a model that follows a definition swap correctly
can still be scored "unmoved" purely as an artifact of the operator.

**Corrected.** The T2 move rate (§3 metric 3) is primarily scored on **argmax**, which is the honest
measure of whether the readout distribution tracks the definitions. It is a statement about the
model, not a harness decision, and is labelled as such. The thresholded version is reported beside
it as a secondary column. P3″ is unaffected: the **accuracy floor** remains the cumulative-mass
operator, and no expectation is computed anywhere.

### 8.3 Threshold fitting constants, frozen now

§2.1 required fitting on train only but gave no objective or grid. Frozen: grid τ from 0.50 to 0.95
in steps of 0.05; utility +1 correct, −1 wrong, 0 for C; ties resolved to the **larger** τ. When a
(question, level-set version) cell has fewer than **20** fitting rows, fall back in order to
(question), then (source, level type, number of levels), then τ = 0.5. Tier usage is reported.
"Question" means the record's `qname` field; the diversity counts in §2.1 are counts of `qname`.

### 8.4 Known defects in the task files, and what they force

Found while building the harness, and confirmed as defects in the 2026-10-28 builder, not in the
harness:

1. On `reversed` T2 items the level ids are reversed but `gold` was **not** updated.
2. On akhilaaa3 boolean swap items the gold map misses capitalised `True` / `False`, so 256 items
   keep a stale gold.

Therefore **gold on T2 `swap_*` and `reversed` items is not trusted**. Consequences, frozen: τ is
fitted only on T1 and on T2 `base` rows; the move metric is computed from **level list positions**,
never from gold; and T2 swap and reversed items are decided under their own unit's base τ. These
files should be rebuilt when the source datasets are restored, and until then no accuracy claim may
be made on T2 swap or reversed rows.

### 8.5 Decision line B-3 gets a number

§3.1 left "clearly above" unquantified. Frozen: B-3 passes when the T2 followed-rate exceeds 30%
**and** exceeds the T1 flip rate on the same groups by at least 10 points.

### 8.6 Subsampling rule

Scoring cost is roughly item count times number of levels, for each of the three model-backed roles.
If the measured throughput from the smoke run implies the full 95,690 records cannot be scored for
all roles within the available window, a subsample is drawn **before** scoring and frozen: sample
whole `group_id`s, never individual variants, with a fixed seed, stratified per source and per
`level_type`, and use the **same frozen group list for every scorer** so all arms stay comparable.
The group list and seed are written into the report header. All sources that fit entirely are taken
whole. No number is produced before the sample is frozen.

### 8.7 Prompt is shared and versioned

The prompt builder is a single pure function with a version constant, shared by the baseline and by
any later training run, and locked by a test against stored expected strings. The version is written
into every report header. Baseline and post-training reports whose prompt versions differ **cannot**
be compared, which makes decision line B-4 void if the prompt changes. Whether the chat template is
applied, or scoring runs on a raw completion prompt, is recorded in the header.

---

## 9. Amendment 2, 2026-10-29, before any scored run

Still no scored number. This amendment corrects a factual error in §2 and adds a task.

### 9.1 Correction: T3 exists and is in scope

§2 states "T3 is unavailable. Its directory is empty". **That is wrong.** I misread a truncated
directory listing. The file is present and matches the manifest:

| File | Records | Groups | Variants |
| --- | --- | --- | --- |
| `T3_question_set/typed-decisions.jsonl` | 24,000 | 1,200 | `prefix_1q`, `prefix_3q`, `prefix_5q`, `prefix_5q_shuffled` |

Level types split 7,200 nominal, 7,200 boolean, 9,600 ordinal. The total frozen data for this run is
therefore **119,690 records**, not 95,690.

T3 holds the same input, the same target question and the same gold across its four variants, and
varies **only the number and order of unrelated prefix questions**, carried in an extra
`prefix_questions` field. It is an invariance task along the question-set axis, and it is the new
invariance item of P1″ ("adding, removing or reordering unrelated questions in the prefix").
Limitation 6 of §7 is withdrawn.

### 9.2 T3 in the metrics

- **T3 flip rate** is defined exactly as the T1 flip rate of §3 metric 2, over each group's six
  unordered variant pairs, reported per source and per `level_type`, with the per-variant-pair
  breakdown. The pair `prefix_5q` against `prefix_5q_shuffled` isolates the **pure ordering effect**
  and is reported separately.
- T3 `gold` is **trustworthy**, unlike T2 `swap_*` and `reversed` rows (§8.4). T3 therefore
  contributes to the accuracy floor and may be used for threshold fitting on the same terms as T1.
- The degenerate baselines of §4 apply to T3 unchanged. B-2 extends to T3: if the empty-input
  baseline's T3 flip rate is within 5 points of the real model's, the T3 invariance result is void.

### 9.3 The prefix questions must be rendered

The prompt builder must render `prefix_questions` into the prompt, preserving their given order. If
that field is ignored, the four T3 variants render identically and the T3 flip rate is **0 by
construction**, which is the same defect as §8.1. Two tests guard this: the four variants of a group
must produce four different prompt strings, and records without the field must render
byte-identically to before, so T1 and T2 are unaffected. The prompt version becomes
`r0-prompt-v2`; nothing is invalidated because no scored run has occurred.

### 9.4 A note on how both errors were found

§8.1 and §9.1 are the same kind of mistake: a measurement that would have returned a clean,
publishable zero for a reason that has nothing to do with the model. Both were caught by asking what
the number would be if the model were replaced by a constant. That check is cheap and belongs before
every scored run in this project, not only this one.

---

## 10. Amendment 3, 2026-10-29, before any scored run

Still no scored number. Three choices made while implementing T3 were not covered by §9 and are
ratified here so they are fixed in this file rather than only in code.

1. **T3's accuracy-floor variant is `prefix_1q`.** §9.2 put T3 into the accuracy floor without
   naming which variant carries it. `prefix_1q` is the least-confounded condition, holding the
   fewest unrelated questions, so it is the floor for T3 exactly as `original` is for T1 and `base`
   for T2.
2. **Prefix layout, frozen in `r0-prompt-v2`.** The unrelated questions render as a numbered block
   headed "Other questions about this input (not asked now):", placed between the input and the
   target question, in the order given by the record. The target question itself is excluded from
   that block. This relies on a property I verified over all 24,000 T3 records: the target question
   always appears in `prefix_questions` and is always its **last** entry.
3. **Prompt version `r0-prompt-v2`** is written into every report header. Records without
   `prefix_questions` render byte-identically to `v1`, which a test asserts against the full string,
   so T1 and T2 are unaffected by the bump.

A `mock-prefix-driven` scorer was added so that the T3 metric can be shown to respond at all. On the
held-out side it gives flip rates of 0.39 to 0.56 against exactly 0.000 for the invariant mock,
which demonstrates the pipeline is sensitive to the prefix. That is a statement about the harness,
not about any model.

---

## 11. Amendment 4, 2026-10-29, before any scored run

The smoke run produced its first numbers and one of them was false. `flip_T1` for the **primary**
scorer read exactly 0.0 on `openjev-synth` / ordinal and on `typed-decisions` / ordinal, which reads
as perfect name invariance. It is not. Rendering is correct and compliant with §8.1: the four T1
prompts for a group hash to four distinct values, and within the flagged cell all 24 units produce
four different probability vectors with four different argmax positions. The model is strongly name
sensitive. Measured on argmax, the T1 flip rate in that cell is **0.625** overall and runs from
0.458 to 1.000 across variant pairs.

The zero comes from the threshold stage. With the §8.3 objective (+1 correct, −1 wrong, 0 for C,
ties to the larger τ), every decisive τ scored negative utility for this untuned model, so the fit
selected τ = 0.95 and the operator abstained on 96 of 96 rows. Every `cum_id` was the constant `"C"`,
so all six variant pairs agreed trivially and the flip rate was 0.0 by construction. `openjev-synth`
carries exactly one `qname`, so one τ covers the whole cell and the collapse is cell-wide.

This is the third time this project has reported a perfect number that came from a broken
measurement rather than a good model, and the first time the error pointed the dangerous way: defect
1 was maximally present and the baseline read as if it were absent.

### 11.1 A flip rate with no decisions to flip is undefined, not zero

**Frozen.** Any flip rate (T1 or T3) computed over a cell whose abstention rate is 1.0 is reported
as **null**, never as 0.0. More generally every reported flip rate carries the cell's C-branch rate
beside it, so a degenerate regime is visible at the point of reading rather than two metrics away.
A rate whose denominator of actual decisions is zero is undefined. The harness already returns null
rather than 0.0 when a denominator is empty; that convention extends to this case, where the
denominator is non-empty in rows but empty in decisions.

### 11.2 The T1 and T3 flip rates are scored on argmax, extending §8.2

§8.2 already moved the T2 move metric to argmax, because the ordinal cumulative-mass operator is not
permutation-equivariant and can score a correct model as unmoved purely as an artifact. The same
reasoning applies to the flip rate, with a second mechanism on top: when threshold fitting selects
total abstention the operator output is constant, so the operator-level flip rate measures the
harness rather than the model. That principle was never extended to metric 2, which is why this run
could report a harness artifact as a model property.

**Frozen.** The T1 flip rate and the T3 flip rate (§3 metric 2, §9.2) are **primarily scored on
argmax**, labelled as a statement about the model. The thresholded version is reported beside them
as a secondary column, labelled as a statement about the operator. **Decision line B-2 and its T3
extension are evaluated on the argmax-scored flip rate.** P3″ is unaffected and the accuracy floor
remains the cumulative-mass operator, exactly as in §8.2. No expectation is computed anywhere.

**B-3 follows.** §8.5 quantified B-3 as the T2 followed-rate exceeding 30% and exceeding the T1 flip
rate by at least 10 points. §8.2 already scores the T2 move rate on argmax, so with this amendment
both sides of that comparison are argmax-scored and B-3 is evaluated that way. Comparing an
argmax-scored move rate against a thresholded flip rate would have compared two different operators
and is not what §8.5 intended.

### 11.3 The threshold objective is not changed, and the collapse is a result

**Frozen, and this is a prohibition.** §8.3's grid, utility and tie rule stand unaltered. It is
explicitly forbidden to refit, reweight or re-grid the objective in order to avoid total abstention.

The reason is that the collapse is itself one of this baseline's findings. For the untuned
Qwen3.5-0.8B readout on these tasks, every decisive threshold in the grid scores **negative**
utility and abstaining on everything scores zero. A system that is better off refusing to answer
than answering is the honest baseline result, and it is the motivation for the training program
rather than an obstacle to measuring one. It must be reported as a headline finding of the run, per
cell, with the fitted τ and the utility of the best decisive τ beside it. Tuning the objective until
the operator commits would convert that finding into a worse number that looked better.

### 11.4 The margin metric counts rows, not decisions

`margin_distribution` increments its denominator for every variant row without checking whether the
operator actually decided, and the ordinal operator returns a distance even when it abstains. The
flagged cell therefore reported `n_decisions: 96` and a margin quality statistic in a cell whose
C-branch rate was 1.0: a share computed over zero actual decisions. §3 metric 4 says "share of
decisions", so the code did not match this file.

**Frozen.** The margin distribution counts only rows that produced a decision. `n_decisions` and
`n_rows` are reported separately, and the statistic is null when `n_decisions` is 0. This is a
conformance fix to §3 metric 4, not a change to it, and it affects every cell with a nonzero
C-branch rate.

### 11.5 The C-branch rate is uninformative at the grid's ends

At τ = 0.50 and a two-level candidate set the operator requires top mass > 0.5 + ε to decide, which
holds for every input except an exact tie, so abstention is **arithmetically impossible** and a
C-branch rate of 0.0 says nothing about the model. At τ = 0.95 on a weak readout the converse
occurs. **Frozen.** A cell whose C-branch rate is 0.0 or 1.0 is flagged as forced by the fitted τ
rather than reported as a property of the model, and the fitted τ is reported with it.

### 11.6 Re-deriving metrics from frozen readouts is not a rerun

The readouts are sound: the probability vectors vary correctly across variants and are the frozen
evidence of this run. Recomputing metrics from the existing `readouts/*.jsonl` under this amendment
is therefore permitted and does **not** constitute a new scored run, provided the readout files,
the prompt version, the splits and the fitted thresholds are unchanged. The model is not re-invoked.
Any recomputation records the amendment level it was produced under.

### 11.7 How this one was found

The watchdog flagged `identical_across_cells` on a primary-scorer flip rate, which escalated to a
bounded read rather than to a rerun. The decisive evidence cost nothing on the hardware: render one
group's four variants with the harness's own renderer and hash the strings, then compare the
argmax positions in the readouts already on disk. Both checks are cheap and belong before any
invariance claim.

Note also that §3.1's B-2 would have caught the consequence without catching the cause. With the
primary and the empty-input baseline both abstaining, the primary's flip rate is not 10 points below
the baseline's, B-2 fails, and all T1 numbers in the run are void. The protocol would have refused
the false claim and discarded a real finding along with it. The argmax column in §11.2 is what keeps
the finding.
