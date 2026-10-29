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
