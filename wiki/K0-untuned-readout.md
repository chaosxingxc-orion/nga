# K0 — untuned readout of the Qwen3.5 checkpoints on Kev's suites and our task set

> Status: planned · Round: R3 SFT round 1, step 1 (`R3-SFT-PREREG.md` §14.5 item 4 step 1)
> Date written (UTC): 2026-10-30, before the run · Pre-registration: `experiments/R3-SFT-PREREG.md`
> §7.1 (arm), §4 (Track K metrics), §5 (degenerate arms), §6 (Track T), §10.4 (pre-number checks)
> Run dir: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/k0_*` · Code:
> `experiments/r3_sft/r3_code/` (snapshot; working copy on cephfs)

## 1. Purpose

Fix the **untrained end** of every comparison this round will make. Nothing is trained here: each
checkpoint is read out as it ships, so that every later trained number has a same-model, same-prompt,
same-scorer baseline to be measured against.

It supplies four things the round cannot proceed without:

- the before-side of **B-4** (§6.3): training must improve held-out accuracy without raising the T1
  flip rate by more than 2 points;
- the comparator for **K-floor** (§9.2), together with the constant and question-only arms;
- the only arm whose permutation and none-of-the-above numbers may be read as invariance and
  unknown-handling results at all, since no trained arm's may be (§4.8, §14.5 item 6);
- the **R0 erratum** measurement (§14.5 item 1), by re-scoring `Qwen3.5-0.8B` under the R0
  configuration with an admissible scorer and differencing it against the published R0 report.

Registry rows (survey §2.2.4): 1 and 17 (level names override definitions; expert levels must be
read) via the accuracy floor; 8 (ordinal compression) via Kev's `score` questions; 6 via the
permutation flip rate; 5 and 16 via the none-of-the-above pair. Gate it feeds: **none directly.**
Round 1 does not decide G2 (§1.2, §12.1), and no round-1 number is evidence for or against G1
(§14.5 item 6).

## 2. Hypothesis

Stated before the run, both directions.

**H1 (the floor).** The untuned readout does **not** clear B-1 on Kev's suites either: accuracy stays
below the majority-class constant plus 10 points on most sources. R0 measured 0 of 20 entries passing
on our own task files; Kev's suites are easier (4 options median, many binary) so some sources may
pass. *If it is reversed* — if the untuned readout already clears the floor broadly — then the
accuracy gap this round is trying to close is smaller than R0 implied, and R0's floor failure was
partly a property of our task files rather than of the readout.

**H2 (what the input contributes).** The question-only arm (`input_mode = drop`) scores close to the
real model, as it did on our task files (72.03% agreement there). *If it is reversed* on Kev's data —
if dropping the input costs a lot — then Kev's suites measure something our task files do not, and
the "the model barely reads the input" finding does not generalise beyond our data.

**H3 (the erratum).** The padding defect moves individual scores but does **not** overturn R0's large
effects (49-point floor gaps, 20–27-point flip gaps), while the marginal ones (the +4.22 void cell,
B-2 nominal at −6.72, the exact 0.00 tie on `akhilaaa3-medium`) sit inside the floor and do not
survive. *If it is reversed* — if the large effects move too — then R0's conclusions need rewriting,
not annotating, and the round pauses for that.

**Unconstrained optimum and its discrimination counterpart** (CLAUDE.md §4 rule 2). The
unconstrained optimum of "score well on a level set" is a **lookup of the majority option per
(source, question)**, ignoring the input entirely; the degenerate solution of the invariance metrics
is a **constant arm**, which cannot flip and so scores a perfect flip rate. Both are sealed by
reporting the constant, uniform, question-only and empty-input arms **beside every number**
(§5, §10.4 a), and by K-floor requiring a 5-point margin over the two that can be fitted. R0 showed
this is not a formality: its single B-2 pass rested on an arm that answered `true` on 1,800 of 1,800
rows.

## 3. Setup

- **Checkpoints** (§2.1, all < 10B as the goal requires), from the unified mirror
  `/mnt/cephfs/xingchao/models/jev/`: `Qwen__Qwen3.5-0.8B-Base` (rev `dc7cdfe2…`) and
  `Qwen__Qwen3.5-0.8B` (rev `2fc06364…`) first; 2B, 4B and 9B Base when the ladder reaches them
  (§14.5 item 4 step 4).
- **Data.** Track K: Kev `decision-v7` dev (n = 1,264) and `transfer-v4` dev (n = 656), converted by
  `r1_code/convert_kev.py` and verified against `KEV/manifest.json`; row counts checked by the
  orchestrator. Track T: the T1/T2/T3 files exactly as R0 froze them, held-out `group70` side, split
  into selection and report halves by the `r3sel:` hash (§2.5); τ fitted only on the `r3tau:`
  carve-out (§2.6).
- **Readout.** Prompt `r0-prompt-v2`; summed identifier log-probability per option (§3.2); Kev's
  first-maximal-index tie rule for the Track K headline with the R0 convention and tie count beside
  it (§4.2); R0's rule on Track T (§6.1).
- **Scorer.** The admissible unpadded/right-padded scorer only (§14.2), after its floor table is
  filled and its verdict rule met (§14.5 item 7). **Pre-amendment K0 numbers are void and are not
  reused.** The one admitted use of the old padded scorer is the §6.5 (i) harness-identity check,
  whose output goes to `harness_identity/` and may not be cited.
- **Degenerate arms** computed first (§10.4 a): constant (fitted on decision-v7 train per
  (source, `qname`) with the position fallback tiers of §5.1), uniform, question-only, empty-input.
- **Compute.** Host 175 (`npu`), 8 × Ascend 910B3, image `nga-verl-qwen35-v030:20261029`,
  `python3 -P`. No training runs concurrently (§14.5 item 4 step 2); chip assignment recorded.
  Detached per CLAUDE.md §7, marker file is the truth.
- **Pre-number checks that must pass before any number is read** (§10.4): the gold-position
  distribution per suite and partition; distinct rendered-prompt hashes across clean, permuted and
  both NOTA variants on one record per source; argmax recomputed from the stored `s_i` on 20 rows.

## 4. Results

Not run yet. To be filled from the run's own `report.json` files, every rate with its n, accuracies
with tie counts, flip rates with dropped-pair counts and C-branch rates (§10.1), degenerate arms
beside every number, and per-chip throughput with the chip count (§10.2).

## 5. Verdict

Not run yet. Will state, per pre-registered line only: B-1 / B-2 / B-2(T3) / B-3 pass, fail or void
on the report half; K-floor comparators; the erratum's measured padding effect; and which of H1, H2
and H3 survived. The §6.5 (i) check is a hard stop: any difference the tie rule does not explain
halts the round until it is explained.
