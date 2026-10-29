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

### 11.8 Reporting conventions that follow from this amendment

Three conventions, fixed here so the implementation cannot drift from §11.2 and so no reader can get
the wrong column by accident.

1. **No bare key names a metric that has two operators.** Where a metric is reported both on argmax
   and on the thresholded operator, **neither** lives at a bare `overall` or `per_pair`. Both sit
   under an explicit parent: `argmax_reference` for the primary column and `thresholded` for the
   secondary. A consumer that asks for the bare name gets an error rather than a number. This is
   deliberate: the defect in §11 was a silently wrong number read from a plausible key, and this
   project has now had three such defects, so failing loudly is worth more than backward
   compatibility. Every bucket keeps its `scored_on` label saying which operator it is and whether
   it is a statement about the model or about the harness.

2. **"Decisive τ" requires commitment on most rows.** §11.3 requires reporting the utility of the
   best decisive τ. A τ that commits on a single fitting row is not meaningfully decisive: in the
   smoke cell τ = 0.60 abstained on 95.8% of rows and still counted. Frozen: a grid τ is **decisive**
   when its abstain rate on the fitting rows is at most **0.5**. The reported `best_decisive_tau` is
   the best such τ, and is **null** when no grid τ qualifies, which is itself the clearest statement
   of a collapse. The abstain rate is reported beside it, and the utility at every grid τ is reported
   in full so the curve can be inspected without re-running the fit. This is a **reporting**
   definition only and changes no fitted value; the §11.3 prohibition on altering the grid, the
   utility or the tie rule stands.

3. **A pre-registered amendment is not in force until a test asserts it.** §8.2 moved the T2 move
   rate to argmax and was never implemented; the code carried only the thresholded rate, so every
   B-3 number produced before amendment 4 was thresholded while this file said otherwise. The same
   had happened to B-2's T3 extension (§9.2), which existed in prose and not in the decision lines.
   Frozen: each amendment clause that changes a number carries a test naming the clause, and a
   clause with no such test is reported as **not in force** in the report header rather than assumed.

### 11.9 Runtime note: the §8.6 guard was probably never crossed, and my own estimate was wrong twice

**Superseded by §11.10 below.** The text of §11.9 is kept unaltered because the decision it records
was actually taken on the information available at the time, and rewriting it would hide that the
reasoning was wrong. Read §11.10 for what the measurement showed.

Recorded for transparency, because §8.6's threshold was crossed and I chose not to apply it.

The full pass was launched on an estimate of about 3 hours, derived from the smoke runs. Measured
from the run itself it needs about **6.5 hours**, which is over the 6-hour threshold at which §8.6
says to subsample instead. The run was allowed to continue on the full 119,690 records.

**Why the estimate was wrong.** Scoring rate falls roughly as the **square** of prompt length here.
Batching is by token budget, so tokens per batch stay about constant and the linear-attention layers
cost about the same per batch at any length, while the 6 full-attention layers are quadratic in
length and therefore grow linearly in cost per batch at a fixed budget. `akhilaaa3` prompts are
about 7x longer than `typed-decisions` ones, which accounts for the measured 40x gap in rows per
second between those sources. A smoke sample weighted toward the short source flatters the estimate.
**Any future runtime estimate on this stack must be computed per source and weighted by each
source's share of the work, never pooled into one rate.**

**Why §8.6 was not applied.** §8.6 exists as a guard against an impractically long run, not as a
methodological constraint on the evidence. The run is detached, survivable and resumable at item
granularity, so 6.5 hours is practical. Subsampling at this point would have replaced better
evidence with a smaller sample and discarded completed work, since a subsample is a different record
set and only partially overlaps what had already been scored. Full data was judged worth the extra
time for the artifact this stage rests on.

This note changes no metric, threshold, split or equivalence class, and §8.6 stands unaltered for
future runs. It records a judgement call and its reason so that the decision is auditable rather
than invisible.


### 11.10 Correction to §11.9: measured per source, the pass needs about 2.2 hours

§11.9 recorded a 6.5-hour estimate, said the §8.6 six-hour guard was crossed, and recorded a
decision to continue anyway. Measurement from the run itself says the estimate was wrong and the
guard was probably never crossed. Both of my errors are recorded here rather than edited away.

**Error 1: the cost model.** §11.9 said scoring rate falls "roughly as the square of prompt length".
It does not. The measured exponent is **about 1.45**, consistent across all three source pairs. Cost
per row fits a mixed linear-plus-quadratic model, `row seconds ~= 2.0e-4·L + 1.8e-7·L²`, which is
about 30% quadratic at L = 336 tokens, 40% at L = 711 and 66% at L = 2,224. Only the 6 full-attention
layers are quadratic; the linear-attention layers and the MLPs are linear in tokens and, under
token-budget batching, cost about the same per batch at any length. That is why the exponent sits
between 1 and 2 rather than at 2. Measured rows/s/chip for the primary scorer: **11.4** at L = 336
(`typed-decisions`), **4.0** at L = 711 (`openjev-synth`), **0.75** at L = 2,224 (`akhilaaa3`). The
40x gap quoted in §11.9 came from comparing the smoke run's `akhilaaa3` T2 figure, which has 7 levels
and warmup mixed in, against a short-source figure; the real ratio is about 15x.

**Error 2: rows are not a measure of work.** The 11% progress reading that produced the 6.5-hour
figure divided completed rows by the declared total of all scorers' rows. Those rows are not
equal in cost. The constant and uniform classifiers cost essentially nothing, and the empty-input and
question-only scorers drop the input and so carry much shorter prompts. At the same moment the
**primary** scorer was about 60% complete. Re-estimated per source with the fitted model, the pass
needs about **2.2 hours** in total rather than 6.5.

**Consequences, frozen.**

1. Any runtime estimate on this stack is computed **per source with the fitted cost model, weighted
   by each source's share of the work**. A single pooled rate is wrong in both directions: a sample
   weighted toward short prompts flatters it, and counting rows overstates the work remaining.
2. A row count is a valid **progress** signal and an invalid **work** signal. Where a completion
   estimate is derived from a row count, it carries the assumption that cost per row is uniform, and
   that assumption is false here and must be stated wherever such an estimate is shown.
3. §8.6 stands unaltered and was, on the corrected estimate, never actually triggered. The override
   recorded in §11.9 was therefore unnecessary. It is left in the file because a decision log that
   quietly deletes the decisions that turned out to rest on bad numbers is worth nothing.
---

## 12. Amendment 5, 2026-10-29, after the first scored run

The full pass was scored and then interrogated. One of my own hypotheses died, the dominant mechanism
turned out to be something else, and two defects were found that qualify the published numbers. The
run is **not** void: the readouts are sound and the verdicts stand as measured. What changes is what
two of the cells are **measuring**.

### 12.1 The candidate-length confound was tested and is not material. Do not retest it.

Candidates are scored by the unnormalized sum of the log-probabilities of their identifier tokens,
so a name tokenizing into more pieces could in principle be disfavoured. I suspected this drove the
T1 flip rate. It does not, on three independent grounds:

1. On **73.97%** of all 56,936 T1 rows every candidate in the prompt has the **same** token count, so
   the missing normalization adds an identical constant to every candidate and cannot change the
   argmax. On those rows it is an exact no-op, not an approximation.
2. Restricting each cell to pairs where length cannot discriminate leaves the flip rate **equal or
   slightly higher**, never lower. Three of the six variant pairs are length-fair at full sample size
   on `openjev-synth` and `typed-decisions`, and that is where the flip mass lives.
3. The mechanical length effect has the **wrong sign**: measured with position controlled on the
   semantics-free `random` labels, longer identifiers score *higher*, by +0.154 nats per token on
   `openjev-synth` and +0.44/+0.49 on akhilaaa3, against a within-item score spread of 2 to 3 nats.

Per-token mean normalization is therefore **not** adopted, and §12.6 records the better fix. Note
that normalization would make measured name sensitivity **worse**, not better: sweeping the
unrecoverable softmax constant moves the pooled T1 flip rate up from 56.91% to between 58.83% and
65.50%.

### 12.2 The dominant mechanism is a prior over identifier tokens, not a reading of names

Argmax concentrates on one position far above chance, and **which** position depends on the name
variant rather than on the input. On `openjev-synth` ordinal, where 5 levels give 20% chance, the
modal position takes 99.97% of items under `letters` (label `a`, position 0), 87.25% under `digits`
(label `3`, position 2), 60.65% under `original` and 56.15% under `random`.

The decisive evidence is the empty-input arm, which has no business situation to read at all. It
flips at 44.18% / 47.52% / 57.44% on `typed-decisions` boolean / nominal / ordinal and 57.24% on
`openjev-synth`, against the primary's 29.23% / 54.24% / 53.22% / 66.06%. **A model that reads
nothing flips as much as the real one, and on `typed-decisions` boolean it flips more.** Primary and
empty-input choose the same level on 63.16% of all T1 items against 25.55% chance agreement.

**Consequence, frozen.** The T1 flip rate as measured here is predominantly a statement about the
identifier set, not about the model's reading of names in context. Identifier choice is therefore a
**harness design decision** for most of T1, not a training problem, with two exceptions below.

### 12.3 `openjev-synth` ordinal T1 is a label/definition conflict, not a renaming. Its T1 numbers do not measure invariance.

The question is *"How many of the four requirements are established for this candidate?"* and the
`original` level names are literally the counts `0`–`4`. The `digits` variant relabels them `1`–`5`
while leaving definitions untouched, so the rendered prompt contains lines such as

```
- 1: Exactly 0 of the 4 numbered requirements are established.
```

The identifier contradicts its own definition, in a task whose answer **is** a number. Verified
directly in the frozen data.

**Frozen.** For this source T1 is not a renaming manipulation and its T1 flip rate, accuracy and
invariance numbers **may not be reported as name invariance**. They are reported separately and
labelled as a label/definition conflict. This covers **7,680 of 14,234 T1 units, 54%**, so it is not
a corner case. A weaker form of the same problem exists in every ordinal cell, where `original`
names are rank indices. Rebuilding this source's T1 requires choosing identifiers that are not
themselves the answer; relabelling alone cannot fix it, because the identifier is semantically
load-bearing. Until then no name-invariance claim rests on this source.

### 12.4 The single B-2 pass rests on a cell with a constant arm

`typed-decisions` boolean, the one cell that passes B-2, chose `true` on **1,800 of 1,800** rows in
its `original` variant, and the question-only control agrees with the primary on **100.00%** of them.
That arm is a constant classifier wearing the primary's name, so the cell's 29.23% flip rate is
produced entirely by the other three variants.

**Frozen.** The B-2 pass is reported **with this caveat attached**, never as a bare pass. A constant
arm is exactly the suspicious-success case §7.1 of `CLAUDE.md` exists to catch, and it was found by
asking what the number would be if the model were replaced by a constant, which is the check §9.4
already says belongs before every scored run.

### 12.5 A tie in the reference column is an abstention, not a vote for the first option

Under bf16, **5.21%** of all T1 rows have two or more candidates tied at exactly the top
probability, rising to 14.10% on `openjev-synth` `original` and 16.00% on `typed-decisions` ordinal
`digits`. `argmax` breaks those ties to the lowest index, which inflates `openjev-synth` `original`'s
position-0 rate by about 5.95 points.

**Frozen.** Where the argmax reference column is computed, an exact tie at the top counts as an
**abstention**, not as a choice of the first-listed candidate, and the tie rate is reported per cell.
Silently resolving a tie toward position 0 manufactures a position effect that is an artifact of
numerical precision.

### 12.6 Readouts must store the raw per-candidate score

The readout stores only post-softmax probabilities. The softmax constant is not recoverable when
candidates differ in length, so no normalization question can be answered without a rescore.

**Frozen.** Every readout row stores the **raw summed log-probability per candidate** alongside the
probabilities. One extra float per candidate would have answered §12.1 without touching an NPU.
Within-item differences are already exact, since `log p_i − log p_j = s_i − s_j`; only the absolute
level is lost, and that is what a length question needs. Additionally, where a prompt's candidates
can be made to tokenize to an equal number of tokens, they **should** be, which removes the length
dimension rather than correcting for it; this already holds on 74% of rows.

### 12.7 `akhilaaa3` is the exception, and is where name rendering is a real question

Unlike the other sources, `akhilaaa3` carries a genuine input-dependent component: the primary flips
at 33.86% / 70.99% / 61.11% against an empty-input baseline of 7.94% / 50.00% / 33.89%. Its
`original` names are real business words. **Frozen:** any claim that name rendering is a training
problem rather than a harness decision must be supported on this source, not on the others. Its
held-out cells are small (27 to 34 units) and 26 primary values were flagged below the minimum
sample count, so those numbers are noisy and must carry their sample sizes.

### 12.8 The two input ablations are not ordered the way their names suggest

Question-only agrees with the primary on **72.03%** of T1 items while empty-input agrees on
**63.16%**. The empty-input arm, which keeps an `Input:` header above an empty body, is therefore the
**more** aggressive ablation of the two. **Frozen:** neither is described as the weaker control, and
both are reported with their agreement rates, so no reader infers an ordering from the names.
