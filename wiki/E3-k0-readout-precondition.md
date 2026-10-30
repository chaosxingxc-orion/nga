# E3 — The precondition for reading K0: composition control, realized-call replay, provenance re-score

> Status: planned · Round: R3 round 1 · Date started (UTC): not launched (written 2026-10-30, before the run)
> Pre-registration: `experiments/R3-SFT-PREREG.md` §14.11 items 7, 17 and 19 (checklist row 10); §14.6 item 3 for the bar; §14.9 item 5 for the near-tie listing; items 15 and 21 for the mutation requirement
> Run dir: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/precondition/` (marker `PRECONDITION_DONE.json`); control inputs and report in `r3_runs/scorer_r3/c32/` · Code: `r3_code/precondition_job.py` and the modules below, frozen with sha1 in `r3_runs/scorer_r3/c32/code3/SHA1SUMS` (no git commit; `r3_code` lives on cephfs)

## 1. Purpose

K0 is the round's first readout of record. It was launched from a snapshot that stamps no provenance on its rows, and it scores in
calls of `SCORE_CHUNK = 32` questions whose boundaries shift on a resume. Two questions stand between K0 and any decision that
reads it:

1. **Composition.** The §14.6 item 3 fp32 table measured whole-sample, 2048-budget, stored-order 64 and reversed 64 calls. It holds no
   32-question call and no resume-shifted call, which is the composition K0 was actually produced in (§14.11 item 19).
2. **Provenance.** Do the stored K0 rows come from the named weights under the scorer of record? K0 is not re-run; the
   verification is a sampled re-score with a mandatory cross-model counterpart (§14.11 item 17).

The two cannot be read in the wrong order. Item 17's 64-item re-score is itself one or two calls of 32 against stored rows that
came from calls at unknown offsets, so a failure of item 17's bar could be a provenance fault or ordinary composition noise.
Item 19's control is what makes the failure attributable (the same confound §14.5 item 1 (i) exists to prevent for the erratum).
Hence **one job, one chip, one marker, in this order**.

Defect-registry rows (this entry's own mapping, not a literature claim): it is a measurement-validity control, so it points at row 12
(the consistency metric is measured by no one unless the instrument is itself checked) and row 16 (cross-candidate comparability:
the raw per-candidate scores must not depend on how candidates are grouped into forwards). Gate fed: it gates K0 being read at all,
and through K0 the first adoption decision (§8.2); it feeds no G1/G2/G3 gate directly.

## 2. Hypotheses, each with what falsifies it

All bars are §14.6 item 3's, unchanged: max |Δ| per candidate against the reference ≤ τ_s = 1e-3 nats and 0 argmax disagreements
under either tie rule on items whose reference top-2 gap exceeds τ_s; items at or below τ_s are counted and listed. Bit-identity
is not a requirement anywhere in this job. Rule 3: bars, samples, seeds and consequences below are fixed now.

**Step 1 — c32 control (item 19).** *H1:* the scorer of record, called on stored-order groups of 32 on the ten fixed fp32 cells,
agrees with fp32 `exact` at the bar, for the unshifted grid (`rp_c32`) and for two resume-shifted grids (`rp_c32s5`, first call 5
items; `rp_c32s16`, first call 16 items), in all ten cells (30 cell-compositions). Expectation: pass with roughly a factor-nine
margin (worst measured composition spread 1.13e-4 against 1e-3). *Falsified* by any cell-composition above the bar; then K0's
readouts are void for the affected suites and the bar is not relaxed (item 19). An expected pass is why this is cheap, not a reason
to skip it. *Unconstrained optimum / degenerate solution:* a control in which every call is one row would equal `exact` and
measure nothing. The report therefore prints, per cell, whether the new composition is bit-identical to `exact` on every item
(`vacuous`) and the job marker carries the list; a vacuous cell is reported as such, never as a pass. *Discrimination counterpart:*
the bar's power to fail on this kind of data is the fp32 table's (synthetic +0.01 per candidate: 0.04 to 0.77; bf16 vs fp32: 0.0989
to 0.657, §14.9 item 4); and `c32_report.py` was run on a copy with a planted +2e-3 error, which it reports as FAIL.

**Step 1b — realized-call replay (this entry's addition, not in item 19 or 17).** K0's call boundaries can be derived from its own
files (§3 below). *H1b:* re-running a sample of K0's own stored 32-row calls as the **same** calls through the same entry point
reproduces the stored scores within the bar (bit-identity is expected on the same chip type and composition but is an
observation, not a gate), and one realized call per cell scored by `exact` also meets the bar against the stored scores.
*Falsified* by a replayed call outside the bar. Because the composition is identical there, a failure is not composition noise: it
points at provenance or at non-determinism of the scorer on that composition. *Status:* diagnostic for attribution. It gates
nothing unless an amendment says so; if step 1 passes and step 2 fails, step 1b is what separates "K0's rows are not from these
weights" from "re-scoring in a different grouping drifted". 20 realized calls (2 per checkpoint and cell), seed 20261031, drawn
after K0 finishes, sample and sha1 written before any scoring.

**Step 2 — provenance re-score with counterpart (item 17).** *H2:* 64 items per (checkpoint, suite) cell over decision-v7 dev,
transfer-v4 dev and the three T1 sources, drawn from K0's finished readouts by `numpy.random.default_rng(20261030)` over sorted
keys, re-scored on the weights `RUN_IDENTITY.json` names (sha256 recomputed from disk and required equal), meet the bar in all
ten cells; the same samples re-scored on the **other** checkpoint's weights fail it in all ten. *Falsified, with consequences
fixed by item 17:* an own-weights cell failing → that cell's K0 readouts are void and re-scored; more than one failing cell →
K0 re-runs in full; **any counterpart passing → the verification is void** and the fault is the verification's, not a finding
about K0. *Unconstrained optimum:* a verifier that passes for any model. Counterpart: the cross-model re-score is that
discrimination counterpart; chip-free corroboration that the bar can fail on this data is `test_..._the_bar_discriminates_on_real_k0_data`
(stored base against stored instruct scores, same keys, fails with max |Δ| above 100 τ_s in every finished suite).

**Step 3 — identity verdict reading (item 7).** *H3:* `harness_identity/IDENTITY_VERDICT.json` says `report_compared: true`.
*Falsified* by `false` or a missing field: the (i) verdict is read as `INCOMPLETE` whatever its readout comparison says and the
run is not complete. Chip-free; skipped, with the skip recorded, if the file does not exist when the job runs.

## 3. Setup

- **Chip.** One, the one K0 frees (K0 holds chips 0 to 4 until `K0_COMPLETE.json`, expected about 09:10Z). Claimed in
  `CHIP-ALLOCATION.json` at the moment it is taken, not before. Nothing here has taken a chip.
- **Job.** `r3_code/precondition_job.py --out r3_runs/precondition --k0 r3_runs/k0_fp32 --c32-root r3_runs/scorer_r3/c32`, launched
  detached through `sc_launch.sh` (command in `scorer_r3/c32/LAUNCH_PRECONDITION.txt`, relaunch command written to the run dir).
  **It refuses to start unless `k0_fp32/K0_COMPLETE.json` exists**, because the replay and the re-score sample finished readouts
  only (`--rehearsal` exists for dry runs and writes `REHEARSAL_DONE.json`, never the marker). Resumable per step and, inside steps,
  per item or file. The terminal marker `PRECONDITION_DONE.json` carries every step's exit code, whether the control passed
  (`c32_control_all_pass`), and the re-score verdict; that marker, not the container, is the source of truth.
- **Scorer.** `eval_r3.make_score_fn` with `--scorer rightpad --token-budget 16384 --dtype float32 --no-hf32 --require-record-grade`
  for the replay and the re-score (the control uses `scorer_r3.R3Scorer` directly through `measure_floor.py`, exactly as the
  fp32 table did). Weights: base `Qwen__Qwen3.5-0.8B-Base`, instruct `Qwen__Qwen3.5-0.8B`; the adapter-bearing cells of the control
  are the §14.6 item 3 cells (unmerged smoke adapter on the base, and the R0 model for the T1 `r0model` cells).
- **Control cells.** The ten fixed fp32 cells (decision-v7 and transfer-v4 on adapter and base, T1 typed-decisions / openjev-synth /
  akhilaaa3 on adapter and on `r0model`), same samples and sidecars (copied to `scorer_r3/c32/data`, so the table of record
  `scorer_r3/fp32` is never written to), `exact` references reused from the table, modes `rp_c32`, `rp_c32s5`, `rp_c32s16` added by
  `measure_floor.py` (4 waves, at most 3 concurrent processes; eight once ran a chip out of memory).
- **K0's call boundaries.** Derived, not assumed. Every readouts file is one `ReadoutStore` filled by `score_resumable`, so call j is
  stored lines `[32j, 32j+32)` provided every restart began on a multiple of 32 stored lines; a killed call stores nothing. The
  evidence is that every heartbeat `done` value is a number of stored rows at the end of a call. Result at derivation time
  (`scorer_r3/c32/k0_chunks_derived_*.json`): 277 files, 228 in finished units, 2,698 calls, **0 files with an off-grid
  non-final `done`, 0 duplicate keys; `units/failed` and `crash/` empty.** **Stated limit, kept exactly:** heartbeat lines are
  throttled, so this is evidence for the grid, not proof of it; a shift inside a stretch whose heartbeat line was throttled away
  would not be seen. Item 19 says the boundaries are "not recoverable from K0's own files"; this derivation recovers them up to
  that limit, and the shifted cells of step 1 are what cover the residual.
- **Tests, with mutation demonstrations (items 15 and 21).** `test_entry_point_r3.py` (8 tests; also run inside
  `test_full_eval_r3.py`, 22 of 22 passing) calls the entry point and observes what the scorer was given; `test_k0_rescore.py` (6),
  `test_identity_verdict_read.py` (2). Mutation scripts `mutation_demo_entry_point.py`, `mutation_demo_k0_rescore.py`,
  `mutation_demo_identity_verdict_read.py` write `r3_runs/make_score_fn_readback/mutation_demo*.json`; every mutation is caught and
  the live file's sha1 is unchanged after. The mutations hit the scoring path (constructor kwargs, the mode passed to `score_raw`,
  the call composition, `score_model`'s constructors), not a `describe()`. **Recorded because it belongs to this job's record:**
  the first version of the bar's argmax test survived its own mutation (the flip case also exceeded τ_s on delta, so the delta
  clause alone failed it); it was rewritten with a flip whose every delta is 8e-4 but whose argmax moves, and the mutation is then
  caught. The bar's test was strengthened before the bar was used.
- **Single-partition path (item 22).** `eval_r3.py` without `--full` now refuses `--scorer rightpad|exact|fast` unless
  `--not-of-record` is passed, refuses `--require-record-grade`, and records `dtype`, `hf32`, `record_grade: false` and each flag it
  ignores in the header. Not used by this job (it uses `--full`'s `make_score_fn`); stated here because it changed `eval_r3.py`'s
  sha1 after K0 launched. `make_score_fn` and `score_model` are byte-identical to K0's frozen copy.

**Declared differences and open questions.**

1. Items 17 and 19 were devised after K0 launched and while it was scoring (both say so). The bar is §14.6 item 3's, reused.
2. Item 17 says "re-scored by the stamped harness". This job uses `make_score_fn` (no stamping path). Put to the reviewer; the
   change, if ruled, is small and does not alter the bar.
3. Step 3 is a post-run read of the verdict file (item 7 says it needs no edit to live code). Whether the reviewer meant a re-run on
   a chip is put to the reviewer.
4. Step 1b is an addition of this entry and is diagnostic (§2).
5. The 7 of the 140 fp32 score files written by the first-wave `fp32/code/` harness (decision-v7 adapter `exact`, `exact2`;
   openjev-synth adapter `eq_a`, `eq_b`, `eq_c`, `exact`, `exact2`; `fp32/file_provenance.json`) carry a `seconds` field that is
   wall-clock under different concurrency from the sharded `exact` sum. Nothing here rests on those timings; they must not be
   summed with the others.

## 4. Results

Not run. To be filled from `PRECONDITION_DONE.json`, `scorer_r3/c32/c32_report.{json,md}`, `precondition/replay/replay_results.jsonl`
and `precondition/rescore/RESCORE_VERDICT.json`, with counts and max |Δ| per cell exactly as the verdict table gives them.

## 5. Verdict

Not run. Decision lines: H1 (30 of 30 cell-compositions inside the bar), H2 (ten own-weights cells inside, ten counterparts
outside), H3 (`report_compared` true). K0 may be read only if all three hold. What this job may not claim even if all hold: that
K0's rows were produced by a particular process (it demonstrates that the stored scores are reproduced by the named weights under
the scorer of record, not their origin), that bit-identity holds, or that the derived call grid is proven.
