# E2 — scorer admissibility: the bf16 table that failed, and the fp32 verdict that replaced it

> Status: done · Round: R3 round 1, before any readout of record (`R3-SFT-PREREG.md` §14.5 item 7, §14.6)
> Date (UTC): 2026-10-30, bf16 table 03:26Z, fp32 runs 04:18Z to about 05:00Z · Written after the fact, see the
> note at the top of section 1 · Pre-registration: §14.2 (superseded in part), §14.5 item 7 (the rule
> as first written), §14.6 items 1 to 4 and 7 (the ruling this work caused)
> Run dir: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/scorer_r3/` (bf16 in `data/`, fp32 in `fp32/`) ·
> Code: `/mnt/cephfs/xingchao/experiments/jev/r3_code/` (frozen copy used for the fp32 runs:
> `fp32/code2/`, `SHA1SUMS` beside it)

## 1. Purpose

> **Record, not a pre-registration.** CLAUDE.md §8 asks for sections 1 to 3 before the run. This work
> ran in two stages and the rule it ended on did not exist when it started: the bf16 measurement
> ran under the §14.5 item 7 rule (fixed before that table was read), the table failed, and the
> fp32 bar of §14.6 item 3 was ruled afterwards. Sections 1 to 3 below are written after both
> stages, from the amendments and the run files; nothing is backdated. Where a statement was only
> known afterwards, it says so.

Decide which scorer may produce a readout of record for R3 round 1, and in which precision. The
trigger was §14.2: the R0 scorer left-pads and carries no `position_ids`, a second implementation
found a 0.157-nat score shift on one row, and so every R3 readout had to come from an unpadded or
right-padded scorer admitted by measurement. Nothing in this work trains a model or reads a test
partition. It feeds no gate; it is a precondition of every number the round reports (K0, the
degenerate arms, the R0 re-score, the erratum).

Defect-registry row: the measurement-validity rows around score reproducibility (survey §2.2.4); no
row of the model-behaviour kind. It also produced the R0 padding measurement that §14.5 item 1 (ii)
and the erratum use.

## 2. Hypothesis

What was expected, as it can be reconstructed from §14.2 and the §14.5 item 7 text:

- **H1 (bf16, as pre-registered).** A right-padded scorer (`rp`) and a prompt-sharing scorer (`fast`)
  match the unpadded layout (`exact`, one row per forward) within the batch-composition noise of the
  admitted layout itself: (i) max |Δ| from `exact` not above the layout's own replicate floor, (ii) no
  argmax differs under either tie rule, (iii) headline accuracy equal under both. *If reversed:* a
  scorer fails, is fixed, and the bound is not relaxed (§14.5 item 7).
- **H2 (written into the item as the reason for the rule, unverified).** The padding defect moves
  scores by more than the batch-composition floor, so the R0 published readouts are not comparable.
  *If reversed* the padding diagnosis falls and only the noise floor remains.

**Unconstrained optimum and discrimination counterpart.** Admissibility by equality with `exact` is
satisfied by `exact` itself and by any copy of it, so the rule needs a counterpart that a correct
scorer passes and a wrong one fails. Three were used. (1) A null control, `eq`: the unpadded layout
batched only with rows of exactly equal length, so no padding anywhere; a rule that fails it cannot
distinguish padding from batching. (2) A synthetic +0.01 nats per option perturbation of `exact`,
which the bar must fail. (3) The pre-fix bf16 scores, which the fp32 bar must fail. The null control
was added by this work, not by the pre-registration; it is the reason the bf16 verdict means what it
means.

## 3. Setup

**Samples (fixed before any score was read; n counts questions).** `decision-v7` dev 192 (12 sources
x 16, lowest sha256 of kev id and qindex), `transfer-v4` dev 192 (8 x 24), and three Track T files:
`T1/typed-decisions` 64, `T1/openjev-synth` 64, `T1/akhilaaa3` 64 for the adapter tag and 128 each
for the `Qwen3.5-0.8B` tag (`r0model`), the first two chunks of 64 of R0 shard 0 of 6. Model of
record: unmerged LoRA adapter on `Qwen3.5-0.8B-Base`; `base` and `r0model` rows are controls
(§14.5 item 5). Sample sha1s (first 12 hex, of key, gold, cell, prefix length and candidate lengths
per item): decision-v7 `28a5afe8629d`; transfer-v4 `f28839363b3c`; typed-decisions `032858fb4e92`
(adapter) and `d246e177bc4f` (r0model); openjev-synth `81dbe69fb939` and `2f86da8ab800`;
akhilaaa3 `6a37da094c8f` and `0c01752539c4`.

**Modes.** `exact` (one row per forward); `eq_a/b/c` (equal-length-only batches of 64, 8, 3 rows);
`rp_a/b` (right-padded, token budget 16384 and 2048); `fast_a/b` (prompt once, options continued from
the cache; default and 4096 tokens, 16 prompt rows, 64 continuation rows); `rp_chunk/rp_rev`,
`fast_chunk/fast_rev` (chunks of 64 questions in stored and reversed order); `r0` (the published
behaviour: cross-question batching, left padding, no position ids) and `r0_item`.

**Stage 1, bf16, sequential**, one process per chip, chips 0 to 2, 02:03Z to about 04:15Z. **Stage 2,
fp32 with HF32 matmul and conv disabled**, `--no-hf32`, float32, `dedup` on, after the bf16 table
failed: four containers, one per chip (0 to 3), `exact` sharded over items (4 processes per chip,
8-question slices, per-shard part files), the other modes as concurrent processes; plans
`fp32/plan2_w*.json`, relaunch commands in each `run2_w*/RELAUNCH.txt`. No composition of any mode
was changed by the concurrency. 140 score files, every one `float32`, `hf32=false`, `dedup=true`,
sample sha1 and keys matching the per-tag sidecar (0 refused, 0 legacy).

**Harness changes made on the way** (a real data loss caused them): per-tag `sample.json` sidecars,
per-item keys and the sample sha1 in every score file, a loader that refuses a file whose sha1 or
keys differ (`sample_r3.py`); candidates with identical token sequences scored once
(`scorer_r3.dedup_enc`); `exact` shardable over items.

**Declared differences from the pre-registration.**
- The §14.5 item 7 floor was first written as the exact layout's own replicate floor, which is 0
  (one row per forward replicates bit for bit), so every scorer failed by construction. Review
  corrected it to the admitted layout's own floor; the corrected text is what was applied. The bound
  was not relaxed.
- The primary floor pair was `_a` against `_b`; a second floor over every available composition
  (`_chunk`, `_rev`, `_c7`) was computed beside it and never substituted. Both gave the same verdict
  in every cell.
- The fp32 bar τ_s = 1e-3 nats and the null gate were ruled (§14.6 item 3) after a smaller fp32
  probe had been seen (n = 32 to 64, max |Δ| 2.4e-5 to 7.1e-5); §14.6 item 3 declares that
  probe as already seen.
- The T1 `r0model` samples (128 questions) were lost from disk by an overwrite and reconstructed from
  the deterministic sampling code (verified two ways: the same code reproduced the 64-question adapter
  samples exactly, and every score-vector length matched the rebuilt candidate counts). The fp32
  runs re-fixed them with per-tag sidecars. No gold-dependent bf16 number is published from a
  reconstructed sample.

## 4. Results

### 4.1 bf16, the rule as written (n per cell as above)

No bf16 batched scorer passes in any measured cell: `rp` and `fast` fail in every cell with data.
The null control `eq` (no padding anywhere) fails the same rule: **10 of 10 cells overall, (i) in
8, (ii) in 10, (iii) in 10**. `exact` against `exact2` is bit-identical in all 9 cells that have one
(32 questions each). The batch composition alone moves per-candidate scores by up to 0.83 nats
and flips 2 to 9 argmaxes per 64 to 192 questions. Criterion (i) therefore compares one draw of
bf16 composition noise with another and cannot discriminate (§14.6 item 1). Three cells never
completed and no decision depends on them: decision-v7 adapter `exact`, transfer-v4 merged `rp_b`
(merged is not the model of record), and, until it finished, akhilaaa3 `r0model` `r0`.

**Ties, string level.** In bf16 the `exact` layout has 67 questions with a tied maximum across the 11
cells (1 to 12 per cell). **0 of them are between candidates with identical option strings**; they
are distinct strings with exactly equal scores (` no`/` yes`, ` reject`/` accept`, ` true`/` false`,
` c`/` d`, ` 3`/` 4`). The census of the whole source partitions finds no question with a repeated
option string (decision-v7 0 of 1,264; transfer-v4 0 of 656; typed-decisions 0 of 24,000;
openjev-synth 0 of 30,720; akhilaaa3 0 of 2,216). In fp32 there are **no ties at all** (0 in 10
cells). §14.6 item 4 as first written ("every tied maximum is between identical token sequences")
was false; the reviewer's correction is in 4.4.

### 4.2 fp32 with HF32 off, the bar of §14.6 item 3 (n = 1,344 question-scorings per mode over 10 cells)

- **(a) Null gate.** Max |Δ| over `exact`, `eq_a`, `eq_b`, `eq_c`: 2.5e-5 to 1.26e-4 across the 10
  cells, against τ_s = 1e-3. PASS in 10 of 10.
- **(i′)** Max |Δ| of `rp_a/rp_b/fast_a/fast_b` from `exact`: at most 1.13e-4. PASS in 20 of 20
  cell-by-candidate rows.
- **(ii′)** 0 argmax disagreements under either tie rule, on every item whose `exact` top-2 gap
  exceeds τ_s (n evaluated = n, except decision-v7 base 191 of 192 and akhilaaa3 `r0model` 127 of
  128).
- **(iii′)** Headline accuracy equal to `exact` under both tie rules in every row.
- **Items at or below τ_s:** 2 in 1,344 (decision-v7 base `yelp/test/46076/0`, gap 9.8e-5;
  akhilaaa3 `r0model` item `9dfbbc6897f28960d80bbdbc`, gap 6.5e-4). No candidate differs from
  `exact` on either.
- **`exact` against `exact2`** bit-identical in 10 of 10 cells (32 questions each).
- **Published R0 scorer (`r0`, left padding, no position ids) against fp32 `exact`:** max |Δ| ≤ 9.6e-5
  and 0 argmax disagreements in all 10 cells. In fp32 the padding defect is not measurable.
- **Discrimination counterparts.** The synthetic perturbation exceeds τ_s in every cell (0.04 to
  0.77 nats). The pre-fix bf16 scores, matched by item key, are 0.10 to 0.66 nats from fp32 `exact`
  with 0 to 10 argmax disagreements per cell; bf16 `exact` itself is one of them.
- **Scorer of record (ruled in §14.6 item 3 from this table):** `R3Scorer` `rightpad`, token budget
  16384, float32, HF32 off, dedup on, unmerged adapter; `fast` retained as the check.

### 4.3 Cost and throughput (per chip, chip counts stated)

Median seconds per item from the `seconds` fields: fp32 `fast_a` 0.097, fp32 `rp_a` 0.33, against
bf16 `exact` 2.5 (bf16 `exact` is single-row and was the layout the original rule required). Sequential
first pass, one process per chip: about 1,000 to 1,300 real tokens/s and 0.15 to 0.42 questions/s per
chip. Item-sharded and concurrent fp32 run, workers on chips 3, 1 and 2: 6.7k to 8.5k real tokens/s and
1.3 to 3.9 questions/s per chip (token currency: prefix plus unique candidate, no padding counted).
Chip AICore mean 52% to 63% over 30 samples, peak HBM about 33 to 54 GB of 65 GB. The chips sat at 9 to 22%
during the sequential pass because `exact` is single-row forwards and cannot be batched. The wall-clock
floor of a large cell is about 9 minutes, set by `eq_c` (3 rows per batch, a pre-registered
composition). The whole fp32 run took 35 to 41 minutes on 4 chips; the worker for chip 0 is not in the
throughput table (it hit an out-of-memory error, below).

### 4.4 Corrections made to this work's own claims

- **Tie mechanism.** The first report said the bf16 ties come from bf16 *score* quantisation. That is
  wrong: scores are fp32 (the log-softmax is taken after a float cast) and bf16 gaps reach 1.675e-4,
  far below bf16 resolution. The reviewer's check on data already on disk: single-token-candidate
  top-2 gaps are an exact power-of-two multiple in **888 of 926 bf16 cases against 0 of 719 in
  fp32**, and the bf16 ties are composition-fragile, which rules out an indexing defect. The
  mechanism is **bf16 logit quantisation**. Scope: verified for single-token candidates, **not**
  individually verified for the 31 multi-token ties. The fp32 zero was checked for being a
  by-construction zero: the same code finds ties in bf16, and fp32 resolves near-ties at 9.8e-5.
- **"Zero near-ties."** The first R0 padding table counted disagreements involving a top-2 gap below
  1e-3, which is vacuous when the noise is 0.2 to 0.8 nats. The table now gives, per disagreeing
  item, its `exact` top-2 gap against the cell's noise floor; every `r0` and `r0_item` disagreement
  sits at a gap no larger than 0.25 nats.
- **"Nearly all disagreements involve exact ties"** held under the R0 rule, not Kev's (decision-v7
  base `r0`: 4 Kev-rule disagreements, 1 involving a tie).
- A "6x slower on CPU" figure was dropped; cost is quoted from the `seconds` fields only.
- **0.157 nats.** The R0 padding figure that triggered §14.2 is one bf16 composition draw. In
  bf16 the left-padded `r0` differs from `exact` by 0.74 nats on decision-v7, the same as the
  unpadded controls (0.74 for `rp_a`, 0.81 for `eq_a`).

## 5. Verdict

**Passed or failed against the pre-registered lines.** §14.5 item 7, as written: **failed**, in
every bf16 cell, including the null control, so the rule is non-diagnostic in bf16 and bf16 is
removed from the admissible precisions for readouts of record (§14.6 items 1 and 2). §14.6 item 3,
the fp32 bar: **passed** by both `rp` and `fast` on all five suites, for the adapter and for the
`base` or `r0model` control.

### Limits the clean pass does not show

An entry that reports only the passes is not the record. These are the limits, found by review and
re-derived here from the sidecars (`fp32/layout_audit.md`, produced by `layout_audit.py`):

1. **Two vacuous cells in criterion (i′).** In **akhilaaa3 adapter** the second `rp` composition
   (`rp_b`, token budget 2048) puts every one of the 276 rows alone in its batch, so `rp_b` is the
   `exact` layout and is bit-identical to it (max |Δ| 0); (i′) passes by construction for that run.
   In **akhilaaa3 `r0model`** `rp_b` has 91% of rows alone (batch size 1) and the cell's `rp_b`
   deviation (2.15e-5) is that of a layout that is mostly the `exact` layout. Neither pass is evidence about `rp`; the same
   cells' other runs (`rp_a`, and `fast_a/fast_b`) and the other eight cells carry the verdict, and no
   suite's verdict rests on a vacuous cell. (`akhilaaa3` adapter `fast_b` also has 25% of rows alone.)
2. **`rp` is a weak padding test.** Because `_rightpad` length-sorts, the share of forwarded positions
   that are padding is 0.4% to 2.6% in eight of ten cells for `rp_a` (the two transfer-v4 cells are
   the exception at 13.7%) and 0.0% to 0.2% for `rp_b` (1.7% in transfer-v4); the chunked `rp`
   compositions reach 28% in transfer-v4. So (i′) for `rp` is a strong **batch-composition** test and a weak **padding** test.
   The padding evidence in the table is `fast` (left padding with explicit `position_ids`: 3.7% to
   41.8% padded positions for `fast_a`) and `r0` (the same batches as `rp_chunk`, left padded without
   position ids: 0.4% to 28%). Right padding is also exact by construction for a causal model, which
   is the stronger argument for `rp` than this measurement.
3. **Fewer than four independent results.** `exact` against `exact2` bit-identity is nearly a
   tautology for single-row forwards; (iii′) is implied by (ii′) (equal argmax implies equal
   accuracy), so it is not an independent third result; and the null gate contains no padding at
   all. The independent evidence is (a) the size of the batch-composition noise in fp32 (≤ 1.3e-4),
   (i′) and (ii′).
4. **The census of near ties is thin.** Only 2 of 1,344 question-scorings sit at or below τ_s, so
   (ii′) was tested on items that are almost all well separated. That is a statement about the
   samples, not a defect, and it is why the near-tie census of §14.9 item 5 is reported with every
   headline of record from now on.
5. **n and scope.** Samples are 64 to 192 questions per cell, one model checkpoint (the smoke-test
   adapter), one set of compositions, one NPU generation. A different adapter, a longer prompt or a
   different kernel is a new measurement; the table says nothing about the training-time kernel
   (§14.7).
6. **What the work does not support.** It does not show that padding is harmless in bf16 (it shows
   that bf16 noise swamps the question), and it does not show `fast` is admissible for training-time
   use.

### What went wrong in the run itself (kept because the directory names say it)

- The first three fp32 workers could not start (`run_w{1,2,3}_failed_startup_npu_busy`): a second
  container cannot open a chip another container holds, and the bf16 chains still held chips 0 to 2.
- `run2_w1_oom_with_extra_procs`: three extra processes added by hand to speed up the slow modes
  pushed one chip past 65 GB (22 GiB reserved by one process). No number changed (a score file is
  written only after its mode completes); the missing modes were re-run in `run2_w1b`.
- `dedup_test_run`: the first version of the duplicate-candidate test was wrong, not the scorer
  (it prepended a copy, which re-orders the reduced question and so changes the composition).
- Chips were allocated from instantaneous `npu-smi` readings by the orchestrator, and a chip read as
  free between shards was handed out; `CHIP-ALLOCATION.json` is now the source of truth. Worker to chip
  map: `fp32/CHIP-MAP.json`.

### Follow-ups that exist because of this entry

- `test_scorer_r3.py::test_bf16_fast_within_measured_two_order_floor` asserted the §14.5 item 7 bf16
  rule and failed (a known-red test in the scorer of record's file). It is **replaced** (not skipped)
  by `test_fp32_candidates_meet_the_amendment6_bar`, which applies the §14.6 item 3 bar in fp32 and
  fails bf16 as its counterpart, plus `test_s14_6_2_hf32_is_off_for_the_precision_of_record_and_a_readout_header_says_so`.
  Rerun on one chip (fp32 and bf16 cases, 05:29Z to about 05:50Z, run directory
  `r3_runs/scorer_r3/test_rerun`, `DONE`): **8 of 8 tests pass**. The new bar test, n = 25 fixed rows, 25 evaluated:
  max |Δ| from `exact` 7.1e-5 (`eq_a`), 3.9e-5 (`eq_c`), 5.8e-5 and 7.7e-5 (`rp_a`, `rp_b`), 5.2e-5 and 5.7e-5
  (`fast_a`, `fast_b`); the counterpart bf16 `eq` (3 rows per batch) against bf16 `exact` is 0.356 nats, so the bar
  fails bf16 as it should. The chip-free suites that touch the evaluation harness also pass after the census
  change: `test_full_eval_r3` 10, `test_track_t_r3` 14, `test_variants_r3` 11, `test_prechecks_r3` 13,
  `test_harness_identity_r3` 9, `test_sample_r3` 5 (`test_select_r3` needs numpy, which the login host lacks, and
  was not run).
- The near-tie census of §14.9 item 5 (`core_r3.near_tie_census`, listed items carry their top-2 candidates) and the string-level duplicate audit
  (`core_r3.duplicate_option_audit`) ride with every Track K headline and every Track T cell in
  `full_eval_r3.py`; the duplicate-candidate rule is kept as a declared-vacuous safeguard whose
  vacuity is audited (0 duplicate option strings in any source partition read so far; the scorer
  also counts what it removes and the report header carries the count).
- An open question: whether the batch-composition noise in fp32 (≤ 1.3e-4) stays that small for a
  fine-tuned model's sharper distributions; K0 is the first test of that on a model other than the
  smoke adapter.

## Artifacts

All under `/mnt/cephfs/xingchao/experiments/jev/r3_runs/scorer_r3/` (not committed). sha256, first 16
hex: `fp32/fp32_verdict.json` `fdb5b0bd897b2aef`, `floor_table.json` `c3ea5e331a49f02d`,
`tie_audit_bf16.json` `f68641753ad44953`, `tie_audit_fp32.json` `88aaeea700bed5e1`,
`fp32/layout_audit.json` `c86d2a6076980205`. Readable tables: `fp32/fp32_verdict.md`,
`floor_table.md`, `tie_audit_bf16.md`, `tie_audit_fp32.md`, `fp32/fp32_throughput.md`,
`fp32/layout_audit.md`.
