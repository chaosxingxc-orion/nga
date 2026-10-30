# R0S — the R0 side of record: an fp32 re-score of `Qwen3.5-0.8B` under the R0 configuration

> Status: planned · Round: R3 round 1, adoption gate (not a launch gate) · Date written (UTC): 2026-10-30, before the run
> Pre-registration: `experiments/R3-SFT-PREREG.md` §14.5 item 1, §14.11 item 4, §8.2 (c), §6.3, §14.6 item 2, §14.9 items 3 and 6 · Run dir:
> `/mnt/cephfs/xingchao/experiments/jev/r3_runs/r0_rescore_fp32/` (plan: `PLAN.md` there) · Code: `r3_code/` snapshot frozen into the run dir at launch (`r0rescore_*.py`, `provenance_r3.py`)

## 1. Purpose

`Qwen3.5-0.8B` (the model R0 scored) is re-scored with the **scorer of record** (`R3Scorer` mode `rightpad`, float32, HF32 off, token budget 16384) under the
**R0 configuration**: tau fitted on the full `group70` train side, the whole held-out side, R0's published tie rule, prompt `r0-prompt-v2`, all three model roles
(primary, empty-input, question-only), every record `records_needed(R0)` requires: **102,654 per role**, 307,962 scored rows.

What it is **for**:

- It is the **R0 side of record** of every R3 comparison (§14.5 item 1, §14.9 item 6). The published R0 readouts are bf16 and are not the R0 side of any comparison (§14.6 item 2).
- It is the **population of §8.2 (c)**. Gating cells are "the `typed-decisions` T1 cells that are not void under R0 §13.5 for either model", and those verdicts are recomputed on this
  re-score. Until it exists §8.2 (c) has no population and **no arm is adopted** (§14.11 item 4): wave 1 could train, finish and produce dev numbers that cannot become an adoption decision.
- It is the fp32 side `harness_identity_r3.erratum()` requires, and the input of §6.3's B-4 for K1-PT and of the R0 §12.1 length-effect retest (§14.9 item 6).

It is **not** a launch gate for wave 1 and it is not the erratum: the erratum (padded bf16 rerun minus fp32) is owed separately (§14.11 item 3) and is a document with no pass bar.
K-floor (§9.2) does not read it (§14.11 item 4, correction). It does not share a chip with a training run of record (§14.5 item 4 step 2 (a)).

Registry rows (survey §2.2.4): 1 and 17 (names override definitions: the accuracy floor), 6 (name/definition invariance: the T1 flip), 5 and 16 via the B-2 empty-input comparison. Gates fed: none of G1/G2/G3;
it feeds round-1 selection (§8.2 (c)).

## 2. Hypothesis

Stated before the run, in both directions. **No number of this round is compared with R0's published numbers in this entry** (§14.11 item 3): what follows are expectations about the
re-score, to be confirmed or falsified when its cells exist; the comparison itself belongs to the erratum.

Known going in (fixed-sample path, §14.6 items 1 and 5, §14.9 items 2 and 6): bf16 against fp32 differs per candidate score by 0.10 to 0.66 nats, with 0 to 10 Kev-rule argmax disagreements
per 128-item cell (0.8% to 7.8% of items); fp32 has no exact ties (0 of 1,344 items), while R0's bf16 readout carried 5.21% exact top ties in T1, between distinct levels (§14.9 item 7); left padding contributes at most 9.6e-5 nats.

- **E1 (ties).** The fp32 re-score has an exact top-tie rate below 0.5% in every T1 cell. *Falsified* by any cell above 1%: then the fp32 scorer of record has a tie mechanism the fixed samples did not show, and §14.9 item 2's "fp32 has no ties" needs reopening.
- **E2 (large effects survive).** Every R0-side cell that is a large effect in R0's report (a B-2 gap or a floor gap of 20 points or more) keeps its sign and stays above 10 points. *Falsified* by a sign reversal or a drop below
  10 points in any such cell: then the precision term is not "small against R0's large effects", the K0 wiki's H3 is reversed, and R0's conclusions need rewriting rather than annotating (the round pauses, K0 wiki §2 H3).
- **E3 (marginal cells move).** Cells near the B-2 bars (gap within 2 points of +0.10 or of the ±0.05 void trigger) can change verdict; I expect at most 2 of the T1 B-2 cells to change pass/void/fail status. *Falsified* by 4 or more changed
  verdicts: bf16 noise was then a first-order determinant of R0's B-2 table, not a marginal one.
- **E4 (the gate has a population).** At least one `typed-decisions` T1 cell is not void under R0 §13.5 on this re-score. *Falsified* by zero: §8.2 (c) is then permanently empty and adoption is unreachable under the clause as written; that would be a pre-registration defect to report at once, not a null result.
- **E5 (completeness).** The run produces exactly 102,654 keys per role, none twice, and every row carries the stamp of the R0 model. *Falsified* by anything else; then the run is refused, not annotated.

**When E2 and E3 may be read, decided 2026-10-30 before the run.** The framing above is accepted: no published cell value is quoted here. But E2 and E3 cannot be *evaluated* without
comparing this re-score against R0's published numbers, which §14.11 item 3 bars while the erratum is outstanding. They are kept, not weakened, and their verdict is **deferred to the
erratum**, which is that comparison on the same item set and is owed before the first test read (§14.11 item 3). So §5 below states E1, E4 and E5 from this run's own files, and records E2
and E3 as *pending the erratum* until it exists. If this run completes before the erratum, that is not a reason to read them early; the bar on the comparison is the reason the erratum
exists, and reading them early would be the comparison under another name.

**Unconstrained optimum and its discrimination counterpart (CLAUDE.md §4 rule 2).** The unconstrained optimum of "produce the R0 side" is a directory of numbers that *looks* like it: copy the published bf16 readouts, re-use
readouts of another model or another configuration, or finish with a partial item set. All three have been demonstrated this round to be accepted by an unguarded loader (a Base-model readout behind a `RUN_IDENTITY.json` naming the R0 model was
differenced into a plausible-looking erratum). Its degenerate solution on the *metrics* is the constant classifier, which cannot flip and so has a perfect T1 flip rate. The counterparts: (a) the constant, uniform, empty-input and question-only roles are
computed beside every cell and B-2 compares the real model with the empty-input arm; (b) `provenance_r3.py` stamps every readout row with the model sha256 and every unit writes a manifest (per-file sha256, row count, scorer descriptor), re-checked against the
sha recomputed from the weights on disk; (c) `r0rescore_verify.py` requires keys equal to `records_needed(R0)` per role, with mutation tests showing each check fails when disabled. This guards against accident, not against deliberate rewriting of rows, manifests and identity together.

## 3. Setup

- **Model.** `Qwen__Qwen3.5-0.8B` at `/mnt/cephfs/xingchao/models/jev/`, revision `2fc06364715b967f1860aea9cf38778875588b17`, weights sha256 identity `b6d66db3bef7297633944d3e3431fea5db6f1c3ff93552a0bcf66bd31fb62634`.
- **Data.** The seven Track T task files exactly as R0 froze them (T1 typed-decisions 24,000, openjev-synth 30,720, akhilaaa3 2,216; T2 8,611 / 12,272 / 835 needed of 14,400 / 23,040 / 1,314; T3 typed-decisions 24,000). Sha256s are written into the report header at run time.
- **Scorer / precision.** `R3Scorer` `rightpad`, float32, HF32 off, `token_budget` 16384, dedup on (§14.9 item 3); enforced by `--require-record-grade`.
- **Configuration.** `--track-t-config r0`, arm label K0, prompt `r0-prompt-v2`; no `--limit-groups`.
- **Units.** 32 shards, one process per shard, dynamic queue, one worker per chip (`nga-r0r-w<chip>`), image `nga-verl-qwen35-v030:20261029`, `python3 -P`, detached, no `--rm`.
- **Cost.** About 10.6 chip-hours (range 8.2 to 13.6): rates measured on the 10 completed K0 Track T units, 5 chips concurrent, windows of 52 s to 1,784 s; one rate bounded and the totals extrapolated (see `PLAN.md`). **3 chips about 3.8 h**, 2 chips 5.5 h, 5 chips 2.3 h.
- **Chips.** Recommended: 3 chips from wave 1's idle tail (§14.10 item 8: six of eight chips idle from t of about 1.9 h of a 6.76 h wave), finishing inside the wave. Claimed in `CHIP-ALLOCATION.json` before launch; chips are never read from `npu-smi`.
- **Launch / relaunch / marker.** In `PLAN.md`. Terminal marker `R0RESCORE_COMPLETE.json` (exit code is the truth); a relaunch moves, never deletes, a directory holding a terminal marker.
- **Declared differences from the pre-registration.** None. Declared differences from K0: config r0 instead of r3; provenance stamping and manifests (K0 predates them); the run's only job is Track T.
- **Launch is the coordinator's call**, after Amendment 11 is committed.

## 4. Results

Not run yet. To be filled from `instruct/report.json`, `R0RESCORE_VERIFIED.json` and the heartbeats: per cell, every rate with its n, accuracies with tie counts, flip rates with dropped-pair counts and C-branch rates, degenerate roles beside
every number, throughput per chip with the chip count and reserved GiB, and the suspicious-success checks (any exact 0.0 or 1.0, any metric identical across cells, any cell below minimum n, any tie count of exactly zero) written out before any number.

## 5. Verdict

Not run yet. Will state which of E1, E4 and E5 held, with E2 and E3 marked pending the erratum (§2), the recomputed R0 §13.5 B-2 verdict per cell, and the §8.2 (c) gating-cell list this yields. It may not claim anything about R0's published numbers (that is the erratum's), nor adopt any arm.
