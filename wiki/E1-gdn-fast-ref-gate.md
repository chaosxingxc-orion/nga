# E1 — the admissibility gate for `gdn_fast_ref`, a third gated-delta-rule kernel

> Status: done — **(G2) failed; `gdn_fast_ref` is not admitted**, and wave 1 and the ladder train
> on the in-tree reference kernel · Round: R3 SFT round 1, engineering prerequisite to wave 1
> (`R3-SFT-PREREG.md` §14.7 launch checklist item 2) · Date (UTC): 2026-10-30 — sections 1–3
> written before the run, sections 4–5 after it from the run's own report files; verdict ruled in
> `R3-SFT-PREREG.md` §14.10 item 1
> Pre-registration: `experiments/R3-SFT-PREREG.md` §14.7 item 2, criteria (G1)–(G4); it narrows
> §14.4 (§14.7 item 1), inherits §14.1 (a′) and (b′), and is measured on the trainer after the
> §14.7 item 4 fix · Run dir:
> `/mnt/cephfs/xingchao/experiments/jev/r3_runs/eff/gate_fast_ref/` · Code:
> `r3_code/gdn_fast_ref.py`, `train_r3.py`, `test_gdn_e2e.py`, `test_gdn_fast_ref.py` (working copy
> `/mnt/cephfs/xingchao/experiments/jev/r3_code/`; the four sha256s go into the run dir)

## 1. Purpose

Decide **one engineering question**: may wave 1 and the ladder train on `gdn_fast_ref`, a third
implementation of the gated-delta-rule layer, or must they train on the in-tree reference kernel?

The kernel is a speed measure and nothing else. It re-implements the reference kernel's math with a
block-doubling matrix inverse and an analytic backward in place of the 63-iteration in-place
inverse. The motivation is launch-bound execution, not precision: **~69,000 device tasks per step at
21% device-busy wall time**, corroborated by **9–22% AICore** on host 175 under three concurrent
jobs (§14.7 item 2). It buys throughput; it buys no capability, and a pass here improves no accuracy
number in this round.

The downside of a fail is bounded and is written down **before** the measurement, so it cannot be
reopened under schedule pressure after a result is seen: training on the reference kernel costs
about **2.8 h per K1 run** at three processes per chip and about **6.8 h per K2-shared run**,
roughly **a day for wave 1** (§14.7 item 2, fallback clause). That is the whole stake of this
experiment.

**Why a third kernel needs its own gate, which is the methodological point.** §14.4 already issued a
kernel verdict — (b′) and (c) failed, the ladder's only route left open through K1-FLA — but that
verdict is about a *different* implementation: the fused gated-delta-rule / FLA kernel under
`speedup/`. §14.7 item 1 narrows §14.4 to that kernel and to no other, and states the rule
explicitly: a third implementation **does not inherit the word "reference" by being mathematically
the same function**; it is admitted by measurement or not at all. The instrument is deliberately not
rebuilt for it. (G2) is the *identical* per-tensor bound that the FLA kernel failed at **96.6% of
tensors within the bound against 99% required** (§14.4), so passing it is earned on the same scale
rather than argued from the new kernel's lineage.

Registry rows (survey §2.2.4): **none.** This is an engineering admissibility gate, not a measure of
the model. Gate it feeds: **none** of G1/G2/G3. It feeds exactly one decision, the kernel of record
for wave 1 and the ladder (§14.7 launch checklist item 2).

## 2. Hypothesis

Stated before any of the four criteria is measured on the post-fix trainer. One hypothesis per gate
criterion, with the bar quoted from the amendment.

**H1 ((G1), same function in fp32).** With the whole model in fp32 and no autocast, the logits
relative L2 between the two kernels is **≤ 1e-4** and every trainable tensor's gradient cosine is
**≥ 0.9999** — §14.1 (a′) applied unchanged. The declared prior is layer level only: fast-vs-ref max
relative L2 **2.63e-07 to 3.51e-07** over shapes (B2,T64), (B3,T100), (B2,T700), (B1,T1024),
(B4,T257), with and without an initial state; against an fp64 gold both kernels agree to ~1e-6;
worst over the 18 real layers **3.1e-05 forward** and **8.3e-05 gradient**. *If it is reversed* —
if the model-level fp32 comparison misses either bound — the two implementations are not the same
function at model scale, the remaining three criteria are moot, and wave 1 trains on the reference
kernel. A layer-level agreement of 1e-7 does not transfer the claim to the model; that is what (G1)
is for.

**H2 ((G2), no worse than the reference in bf16, per tensor).** With e_X(t) the relative L2 of LoRA
tensor t's gradient from kernel X in bf16 against the whole-model fp32 gold on the same step,
**e_fast(t) ≤ 1.5 · e_ref(t) + 1e-3 for at least 99% of the 372 tensors**, and **no tensor beyond
3 · e_ref(t) + 1e-3**. *If it is reversed* — if the pass fraction lands where the FLA kernel's did,
at 96.6% — the kernel fails exactly as the FLA kernel failed, and the day of wave-1 wall clock is
paid on the reference kernel. The stacked aggregate already recorded (**e(F,G) 4.02e-02** against
**e(R,G) 3.79e-02**, ratio **1.06**) does **not** discharge this criterion and is not quoted as if
it did: a ratio of stacked norms cannot show that no individual tensor is off by 3×, which is the
half of the bound that catches a kernel that is right on average.

> **Correction, 2026-10-30, same day, after amendment 8.** Three statements in this entry are
> superseded in part by `R3-SFT-PREREG.md` **§14.8 item 1**, which fixed (G2)'s population before
> any gate number was read: the "*identical* per-tensor bound … 96.6%" sentence in §1, H2 above,
> and §4's results line, which asks only for the pass fraction over the 372 tensors. The **bound
> is identical; the population is not.** (G2)'s 372 are the LoRA tensors asserted by
> `r3_code/gate_model_level.py` on the LoRA-wrapped model's trainable list, while §14.4's 96.6% is
> **309 of 320 full-model trainable** parameters built from `named_parameters()` on a plain,
> non-LoRA model (`speedup/runs/modelcheck2/model_check.json`, `speedup/code/gate_bprime.py`). The
> decisive finding is sharper than the mismatch: the eleven tensors the FLA kernel actually failed
> (b′) on — L0/L1/L9/L20/L21 `dt_bias`, `A_log`, `linear_attn.norm`, `post_attention_layernorm`,
> `in_proj_a`, per `speedup/README.md:51` — are **all frozen under LoRA and so cannot appear in
> the 372**. (G2) as first written was therefore **blind to its predecessor's only failure mode,
> and the FLA kernel would have passed it**; H2's "fails exactly as the FLA kernel failed" does
> not follow, and a 96.6% over the 372 would not be the event §14.4 recorded. The ruled remedy,
> pre-registered in §14.8 item 1 before the numbers are read: the **372 LoRA tensors gate** the
> decision, because they are the only tensors any arm of this round updates; the **320 full-model
> trainable tensors are measured in the same backward, recorded in `gate_fast_ref/`, and reported
> beside them as a non-gating cross-check**; **only one population may gate**; and the split
> verdict is fixed in advance — 372 pass with 320 fail **admits** the kernel and obliges every
> statement resting on it to name the split, while both failing sends wave 1 and the ladder to the
> reference kernel. §4 and §5 are filled accordingly: both pass fractions, with the 320 labelled
> non-gating.

**H3 ((G3), the same-config replicate floor — the criterion that exists because the floor did
not).** Two invocations of the *reference* kernel with identical micro-batch, seed, data and chunk
plan, reporting d(R,R′) over the stacked LoRA gradient and |loss_R − loss_R′| per step. We expect a
nonzero floor, and that floor — **not re-batching** — is the floor of record for every bf16
statement about this kernel.

The floor offered when the kernel was proposed is **void as a floor** (§14.7 item 2 (G3), item 4):
**d(R2,R) = 3.77e-02 / 3.78e-02** with R2 at one row per chunk. One row per chunk is the habitat of
the backward-pass nondeterminism defect found in item 4 — transformers drops a plain 2D mask when a
chunk has no padding, sdpa takes the causal flash path, and that path's backward is not bitwise
reproducible on this stack, measured at **1.8e-02 relative L2 against the corrected path** — so that
number mixes re-batching with the defect and measures neither. The other figure offered, d(R3,R), is
not a second composition either: **R3 has R's chunk count and padding and its median per-tensor
difference is 0.0e+00**.

Stated plainly, because it is the reason (G3) is a gate criterion and not a note: **the evidence
offered for this kernel contained no same-config replicate floor anywhere.** (G3) exists to create
one. This is the **third time in this program** that a tolerance was set below the noise of the
thing being measured — the first was §11.3 (a) and (b), ratified without a floor and replaced by
§14.1 after the *reference* kernel in bf16 was found to fail the per-tensor bound on 311 of 320
tensors, with §14.4 adding that the (c) tolerance also sits below run-to-run noise (0.0272 and
−3.03% for the reference against its own same-seed rerun); the second was **§14.6 item 1**, where
the §14.5 item 7 scorer bar turned out to be unsatisfiable by construction in bf16 — the null
control `eq`, with no padding anywhere, failed 10 of 10 cells, and criterion (i) was found to be
comparing one draw of bf16 composition noise with another. *If it is reversed* — if the replicate
floor comes out at exactly 0.00e+00 — that is a suspicious success, not a convenience
(CLAUDE.md §7.1): a zero is plausible on this stack post-fix (five post-fix repeats gave an
identical adapter at 0.00e+00 in all five, with the logged per-step loss at 0.00e+00 in three and
5.96e-08 / 2.98e-08 on steps 5 and 6 in two, reproducibly the same values, §14.7 item 4), so a zero
must be shown to be the real floor of two distinct invocations before (G4) is judged against it.

**H4 ((G4), trajectory over 100 steps, judged on the trend).** Both kernels run 100 optimizer steps
with the same seed, data and chunk plan, and the per-step |Δloss| series is reported in full.
Passing requires **both**: mean |Δloss| ≤ max(the (G3) floor, **1.14e-02**, which is 0.5 ·
|loss_R − loss_G| on the same rows with the recorded **|loss_R − loss_G| = 2.28e-02**); **and** the
mean of the last 20 steps ≤ **3 ×** the mean of the first 20 steps.

The second clause is not decoration. The four-step evidence offered for this kernel grows
monotonically — **1.5e-3, 1.4e-3, 4.4e-3, 1.2e-2**, mean **4.7e-3**, an **8×** rise — while its
proposed floor series — **7.5e-3, 2.5e-3, 8.8e-3, 9.7e-4** — does not, so a four-step mean cannot
distinguish bf16 noise from divergence: both stories fit it. *If it is reversed* — if the 100-step
mean passes the first clause but the last-20 mean exceeds 3 × the first-20 mean — the kernel
**fails**, on a passing mean, which is precisely what the clause was written to catch. §14.1 (c) is
**not** relaxed retroactively and stands as written for the FLA kernel (§14.4); (G4) is a different
test, pre-registered for a different kernel before it ran, and its floor is same-config rather than
a second draw of composition noise, which is why §14.6 item 1's objection to criterion (i) does not
apply to it.

**Unconstrained optimum and the discrimination counterpart** (CLAUDE.md §4 rule 2). The
unconstrained optimum of a speedup gate is a kernel that is **bit-identical** to the reference: it
passes (G1)–(G4) trivially and the gate then measures nothing, since any correct re-expression of
the same arithmetic is admitted by construction. The counterpart that seals it is therefore a
**wrong fast kernel that must fail**, and one is recorded in the amendment: the first attempt at
this kernel, a **Neumann-product inverse**, fails the 1e-3 forward check on **3 of the first 8 real
layers**, and its NaN-loss benchmarks are excluded in `r3_runs/eff/INVALID_nan_square_inverse/` and
are cited in **no number of this round**. A gate that admits the block-doubling inverse while
rejecting the Neumann-product one is discriminating between implementations, not rubber-stamping the
class.

## 3. Setup

- **Kernel under test**: `r3_code/gdn_fast_ref.py`, selected with `--gdn-impl fast_ref`. The
  incumbent it is compared against is the in-tree reference
  `transformers.models.qwen3_5.modeling_qwen3_5.torch_chunk_gated_delta_rule`; those two are the
  only kernels §14.7 item 1 leaves admissible for 0.8B, the FLA kernel under `speedup/` having
  failed §14.4.
- **Trainer**: `r3_code/train_r3.py` **after the §14.7 item 4 fix** (`row_logprob_sums` now always
  builds an explicit 4D attention mask, at no measured speed cost). All four criteria are measured
  on the post-fix trainer; pre-fix numbers are not reused as floors.
- **Data**: fixed batches of real `decision-v7` **train** rows (§14.7 item 2). Every `fast_ref`
  number in this gate is at **0.8B over 18 layers**.
- **Measurement order, fixed: (G1), (G2), (G3), (G4).** (G4)'s bar depends on the (G3) floor, and
  the amendment requires (G3) measured and written into `gate_fast_ref/` **before** (G4) is run, so
  that the bar is fixed before its own data exists. The order is part of the pre-registration, not a
  convenience of scheduling.
- **Outputs**: every number, plus the sha256 of `train_r3.py`, `gdn_fast_ref.py`, `test_gdn_e2e.py`
  and `test_gdn_fast_ref.py`, into
  `/mnt/cephfs/xingchao/experiments/jev/r3_runs/eff/gate_fast_ref/`, committed **before any wave-1
  arm launches** (§14.7 launch checklist item 2). If a criterion fails, the recorded decision to
  train on the reference kernel goes in the same directory and discharges the same checklist item.
- **Compute**: host 175 (`npu`), 8 × Ascend 910B3, **chips 1 and 4**, image
  `nga-verl-qwen35-v030:20261029`, `python3 -P` inside the container and never `-I`
  (CLAUDE.md §6, §11.1).
- **Declared difference.** A gate measurement is not a run of record, so §14.5 item 4 step 2's
  one-chip-per-run rule and its chip-assignment file govern wave 1's eight arms, not this gate; the
  chips used here are recorded above instead. The host is co-tenanted while this runs, which is why
  **every speed figure carries ±15%**, per `r3_runs/eff/bench_record.json`'s own note of ~10–15%
  repeat-to-repeat variation from other tenants on the same chips and CPUs (§14.7 item 2). Numeric
  criteria (G1)–(G4) are unaffected by co-tenancy; only the throughput and wall-clock figures are.
- **Run hygiene**: detached per CLAUDE.md §7 and §11.2 — `docker run -d`, fixed container name, no
  `--rm`, log and heartbeat on cephfs, terminal marker file holding the exit code as the source of
  truth, resumable, relaunch command written into the run directory.
- **Ladder rule, pre-registered now.** Before each of **2B, 4B and 9B** trains with `fast_ref`,
  **(G1) is repeated at that size on real rows of that size** and recorded; a size that fails trains
  on the reference kernel. **(G2)–(G4) are not repeated per size.**
- **No `K1-fast_ref` arm, and why.** §14.4's downstream accuracy route (K1-FLA) existed only because
  the FLA kernel had already failed the numeric gate and a coarse accuracy check was the sole
  remaining instrument. A **±1.0-point one-seed accuracy band cannot resolve what an fp32 gradient
  comparison resolves**, so a ninth run is not spent on it (§14.7 item 2). K1-FLA itself still runs
  in wave 1: §14.4 governs the FLA kernel and §14.7 did not touch that arm.

**What this gate cannot claim, stated before it runs.** Nothing about accuracy, on any suite, for
either kernel. Nothing about any Track K or Track T decision line — not K-align (§9.1), not K-floor
(§9.2), not the §8.2 K1-against-K2 adoption. No evidence for or against research gates G1, G2 or G3,
in either direction (§12.1, §14.5 item 6). Nothing about the FLA kernel, whose verdict remains
§14.4's. It decides one thing: which kernel wave 1 and the ladder may use.

## 4. Results

Written after the run, on 2026-10-30, from `gate_fast_ref/`'s own files (`GATE_RESULT.json`,
`GATE_RECORD.txt`, `SHA256SUMS.txt`, `CRASH_NOTE.txt`) and the figures §14.10 item 1 rules on.
Sections 1–3 are as written before the run and are not edited.

**Run of record, and which batch decides.** `model_level_final/` (trainer `train_r3.py` sha256
`d6313c52…`) is the run of record for (G1), (G2) and the model-level (G3); `trajectory_final/` for
the trajectory (G3). The two earlier model-level runs — `model_level/` on trainer `bd2642ae` and
`model_level_v2/` — give **identical** 372-tensor counts on all three batches (368 / 371 / 367) and
differ only in the last digits of the fp32 gold loss (1e-7). The three batches are steps 0, 1 and 2
of the 300-row sample, and **batch 0 is the pre-declared verdict batch**: the gate script's
docstring says "Verdict of record = step 0", and §14.7 item 2 (G4) had recorded
`|loss_R − loss_G| = 2.28e-02` before any of these runs existed, which of the three batches only
step 0 matches (0.0228285, against 0.016142 and 0.028856). The four sha256s §14.7 checklist item 2
requires are in `SHA256SUMS.txt` (`train_r3.py d6313c52…`, `gdn_fast_ref.py 7e68b361…`,
`test_gdn_e2e.py 9472f2ae…`, `test_gdn_fast_ref.py 94bdfa2d…`), with six further scripts beside
them. The first launch of the model-level measurement crashed at process start on a chip that was
not free and **produced no number** (`CRASH_NOTE.txt`, which marks itself a reconstruction;
corrected in §14.10 item 10), so the verdict below rests on a completed measurement, not a crash.

**(G1): passed on all three batches.** Whole-model fp32 logits relative L2 between the two kernels
**1.63e-06 / 1.52e-06 / 1.50e-06** against the bar **≤ 1e-4** — two orders of margin — measured over
all positions; over response positions only, 1.58e-06 / 1.63e-06 / 1.79e-06. Minimum gradient cosine
over the 372 LoRA tensors **0.9999997** on every batch against the bar **≥ 0.9999**, with **0
tensors below** it.

**(G2) on the 372 LoRA tensors, the gating population (§14.8 item 1), as a count.** ⌈0.99 × 372⌉ =
**369 needed** within `e_fast ≤ 1.5 · e_ref + 1e-3`.

| batch | within bound | needed | reading | worst ratio to the bound | beyond 3 · e_ref + 1e-3 |
| --- | --- | --- | --- | --- | --- |
| 0, the verdict batch | **368 of 372** | 369 | **fails by one tensor** | 1.12 | 0 |
| 1 | 371 of 372 | 369 | passes | 1.03 | 0 |
| 2 | 367 of 372 | 369 | fails | 1.50 | 0 |

**Every out-of-bound tensor is an `in_proj_a` LoRA tensor.** All ten across the three batches are
`linear_attn.in_proj_a` — layers 0, 1 and 16 on batch 0, layer 9 on batch 1, layers 9, 20 and 21 on
batch 2 — and nothing else, out of 372.

**(G2) on the 320 full-model trainable tensors, non-gating** (§14.8 item 1), collected from the same
backward: 317 needed. Batch 0 **315 of 320**, 0 beyond 3× — the verdict batch fails here too; batch
1 **317 of 320**, 0 beyond 3×; batch 2 **305 of 320**, and **one tensor beyond 3×**:
`layers.21.linear_attn.dt_bias`, e_fast **3.29e-02** against e_ref **9.74e-03**, i.e. 3.4× its own
e_ref against the bound 3 · e_ref + 1e-3 = 3.02e-02. The out-of-bound tensors here are
`linear_attn` `A_log`, `dt_bias`, `norm` and `in_proj_a`, plus one `self_attn.q_norm` and one
`k_norm` on batch 2. Both populations fail the verdict batch, which is §14.8 item 1's pre-registered
**"both fail"** branch and not its split verdict.

**Loss and stacked aggregates, batch 0.** `|loss_R − loss_G| = 2.2828e-02`, matching §14.7's pre-run
2.28e-02 exactly, and `|loss_F − loss_G| = 3.80e-03`. Stacked: e_R 3.79e-02 against e_F 4.02e-02,
the ratio 1.06 that H2 refused to accept as a discharge of the per-tensor bound; the per-tensor
counts above are the reading that decides.

**(G3) at model level: the floor is exactly 0.0.** Two invocations of the reference kernel with
identical micro-batch, seed, rows and chunk plan — **one in-process repeat and one in a separate
process** (`--stage rep`, whose gradient file was written two and a half minutes after the first) —
give d(R,R′) = **0.0** over the stacked 372-tensor LoRA gradient, **372 of 372 tensors bitwise
equal**, max per-tensor d **0.0**, and `|loss_R − loss_R′| = 0.0`. Per batch at model level, 372 of
372 are bitwise equal on all three, with `|Δloss|` 0.0 / 1.19e-07 / 0.0 — one in-process repeat on
batch 1 differs by a single float32 half-ULP. Of the non-gating 320, **318 to 320 of 320** are
bitwise equal per batch. **The scope limit the reviewer attached, stated rather than implied**
(§14.10 item 5): one chip, one container, one host, one CANN version, sequential in time. It is
**not** evidence of reproducibility across chips, hosts or images, and no claim of that kind follows
from it.

**(G3) on the trajectory: the floor is not zero.** 100 optimizer steps, production config, dropout
0.05, seed 2, both invocations the reference kernel: mean `|loss_R − loss_R2|` **6.046e-03**, max
**3.587e-02**, **8 of 100 steps bitwise equal**, first-20 mean 4.342e-03, last-20 mean 7.181e-03.
The earlier replicate (`trajectory/`, `TASK_QUEUE_ENABLE=1`) gave mean **5.430e-03**, max 2.361e-02,
**10 of 100 bitwise equal**. The full per-step series is in `GATE_RESULT.json`
(`G3_trajectory.per_step_final`): the two runs are bitwise equal on steps 1–4 and 6–9, which is
where the eight equal steps are, differ at the sub-ULP level on steps 5 and 10 (5.96e-08 and
1.19e-07), and jump to 3.587e-02 at step 11.

**(G4): not run.** The engineer stopped at the (G2) failure as instructed, so this kernel has no
100-step fast-against-reference `|Δloss|` series, and therefore no mean, no first-20 mean and no
last-20 mean. §14.10 item 1 holds that (G4) was not required — §14.7 item 2's consequence
clause fires on any one of (G1)–(G4) failing — and that a number produced after the branch is
decided could serve only to argue against it. The script (`gate_trajectory.py` without `--g3-only`)
is in place and takes about ten minutes on one chip; it was not run. **This is the one item on
section 4's own pre-run list that the run did not produce**, and the reason is the stop rule and not
a measurement that failed.

**The pooled reading: measured, reported by the engineer, and refused.** Pooling the three batches
gives **1106 of 1116 = 99.1%** within the bound (the mean of the three per-batch fractions,
99.105%, is the same story), which **would have passed** the 99% bar. The engineer computed it,
reported it as an undeclared alternative rather than as a result, and asked for a ruling. It is
recorded here because it is a measured number; the reasoning that refuses it is in section 5.

**Speed, per chip with the chip count stated** (CLAUDE.md §9), reference kernel, K1, micro-tokens
4096, **one chip**, **about 30.5 GiB reserved** (`reserved_gib_peak` 30.57 at `TASK_QUEUE_ENABLE=1`,
30.49 at 2). Every figure carries **±15%** for host co-tenancy, as section 3 declares.

- Over all 100 steps: **1.94 q/s/chip** at `TASK_QUEUE_ENABLE=1` against **4.4 q/s/chip** at 2 — a
  **2.3×** speedup; over steps 11–100 only, 1.93 → 4.84, i.e. 2.5× on steady state.
  `GATE_RECORD.txt` also quotes the end-of-run 20-step windows, 2.00 → 4.96 q/s/chip; §14.10 item 9
  fixes the whole-run pair as the headline and the windowed pair is not the figure of record.
- The cause was an efficiency defect in the trainer, not a property of either kernel: the container
  image exports `TASK_QUEUE_ENABLE=1`, so `train_r3.py`'s `setdefault("TASK_QUEUE_ENABLE", "2")`
  **never took effect inside a container**. Now assigned, overridable by `NGA_TASK_QUEUE_ENABLE`,
  with the realized value in every manifest (§14.10 item 9).
- That the flag changes **speed only** was shown by the single-step, identical-state, cross-process
  instrument rather than by a loss curve: `tq_check/out/tq_check.json`, five fixed batches, four
  separate processes at TQ = 1, 2, 1, 2, gives `max_rel_l2` **exactly 0.0 and 372 of 372 LoRA
  gradients bitwise equal in all six pairings**; the only non-zero quantity is a half-ULP loss
  difference on two batches, which occurs in the TQ2-against-TQ2′ **same-config** pair and is
  therefore inside the replicate floor.

**Suspicious-success checks, as this section pre-committed to them above** (CLAUDE.md §7.1).

1. **A (G3) floor of exactly 0.00e+00 — this check fired, and this is what was done about it.** The
   model-level floor is exactly 0.0, the case the section flagged in advance, and it was not
   accepted as read. (i) The reviewer verified the cross-process bit-identity **without torch**: a
   `.pt` file is a zip of serialized tensor storages, so `model_level_final/out/grads_R_step0.pt`
   (main process) and `grads_Rprime_step0.pt` (the `--stage rep` subprocess) were compared by
   hashing their members — **372 storage blobs each, 43,290,624 bytes, all byte-identical**, with
   the `data.pkl` streams that carry the loss scalar hashing equal as well. Two files written by two
   processes two and a half minutes apart, so not a self-comparison, and not the script's own check.
   (ii) The same `rel()` and `torch.equal` calls that return 0.0 here return **3.31e-02** for the
   fast-against-reference stacked comparison on the same step, and **318 and 319 of 320** rather
   than 320 for base tensors on batches 1 and 2: a measurement that can report 318 can report 371.
   (iii) An independently written second script, `r3_code/tq_check.py`, reports `max_rel_l2` exactly
   0.0 and 372 of 372 bitwise equal on five further batches in every one of six pairings. The zero
   is the real floor of two distinct invocations, within the scope limit stated above.
2. **A (G2) pass fraction of exactly 1.0 — did not fire.** 368 / 371 / 367 of 372. The companion
   zero inside the same criterion, "0 tensors beyond 3×" on all three batches of the 372, is not a
   by-construction zero either: the same clause **fired once**, on the non-gating 320 at batch 2
   (`layers.21.linear_attn.dt_bias`).
3. **A `|Δloss|` series identical across steps — did not fire.** The 100-step trajectory series runs
   from 0.0 (8 steps) to 3.587e-02, and the two replicates differ from each other (6.046e-03 against
   5.430e-03, 8 bitwise-equal steps against 10).
4. **A criterion measured on fewer batches than the fixed set — fired for (G4) only, and is recorded
   rather than waived.** (G1), (G2) and the model-level (G3) are measured on all three declared
   batches; the model-level (G3) additionally holds on six batches across `model_level_final` and
   `diag_steps9_11` and on five more in `tq_check`. **(G4) is measured on none**, by the stop rule
   above. Separately, the instrument that decided the gate has a batch-to-batch spread of four
   tensors (367–371) and decided by a margin of one; §14.10 item 3 calls that badly calibrated
   whether or not it reached the right verdict, and fixes **five batches and a per-batch median**
   for any future kernel gate — explicitly **not** applied to this one.

## 5. Verdict

**Ruled in `R3-SFT-PREREG.md` §14.10 item 1**, from
`reviews/R3-GATE-VERDICT-RULING-fable-20261030.md`, after the gate reported and before any arm of
wave 1 was trained. Stated per pre-registered criterion only.

**The four criteria, with the measured value beside the bar.**

| criterion | bar | measured | outcome |
| --- | --- | --- | --- |
| (G1) logits rel L2 | ≤ 1e-4 | 1.63e-06 / 1.52e-06 / 1.50e-06 | **passed** |
| (G1) min grad cosine | ≥ 0.9999 | 0.9999997, 0 below, all 3 batches | **passed** |
| (G2), 372 LoRA, gating | ≥ 369 of 372 within `1.5·e_ref + 1e-3`, none beyond 3× | **368** of 372 on batch 0 (371 / 367 on 1 / 2), 0 beyond 3× | **failed** |
| (G2), 320 base, non-gating | ≥ 317 of 320 | 315 of 320 on batch 0 (317 / 305 on 1 / 2), 1 beyond 3× on batch 2 | failed, non-gating |
| (G3) model level | no bar; it *is* the floor | d(R,R′) = **0.0**, 372 of 372 bitwise equal | measured |
| (G3) trajectory | no bar; it *is* the floor | mean step loss difference **6.046e-03** over 100 steps | measured |
| (G4) | mean ≤ max(floor, 1.14e-02) **and** last-20 ≤ 3 × first-20 | — | **not run** |

(G3) is not a pass/fail criterion: it exists because no same-config replicate floor existed anywhere
in the evidence offered for this kernel, and it now does — two of them, one per level of comparison.

**Which hypotheses survived.**

- **H1 survived.** The layer-level 1e-7 agreement did transfer to the model: (G1) passes with two
  orders of margin on the forward bound and no tensor below the cosine bar. H1's point was that this
  had to be shown rather than inherited, and it was shown.
- **H2 is confirmed in its direction and wrong in its reason.** The kernel did fail (G2), as H2's
  reversal clause anticipated. It did **not** fail "exactly as the FLA kernel failed" at 96.6%: it
  failed at 368 of 372 on a population §14.8 item 1 had already corrected, and the dated correction
  note in section 2 above records why that sentence does not follow. What the entry got right, for a
  reason it did not give (§14.10 item 12): not the same tensors — the FLA kernel's eleven are frozen
  under LoRA — but the **same gate-and-normalisation path**, seen through `in_proj_a`, the one
  member of that family LoRA trains.
- **H3 is half confirmed and half reversed, and which half matters.** H3 predicted a **nonzero**
  same-config floor and pre-committed that an exact 0.00e+00 would be a **suspicious success rather
  than a convenience**. *Reversed at model level*: the floor is exactly 0.0 — H3's own flagged case,
  which duly fired and was discharged by section 4's check 1 (hashed storages across two processes,
  an independently written second script, and the same code reporting non-zeros on neighbouring
  cells). H3's prediction was wrong and H3's warning was right, and the warning is the half that did
  the work: it is the reason the zero is usable evidence instead of merely a clean number.
  *Confirmed on the trajectory*: 6.046e-03 mean over 100 steps, max 3.587e-02, only 8 of 100 steps
  bitwise equal — nonzero, as H3 expected any floor to be. The two are not in conflict; H3's single
  word "floor" covered two quantities that differ by every order of magnitude available, and the
  correct reading is that the backward from identical state is bitwise reproducible while a 100-step
  trajectory is not.
- **H4 is not tested.** (G4) was not run, so neither of its two clauses is discharged and nothing is
  claimed about the trend clause for this kernel. One observation from the floor rather than from
  (G4), and labelled as such: the (G3) trajectory replicate's own first-20-to-last-20 ratio is
  4.342e-03 → 7.181e-03, a 1.65× rise inside the same-config floor, so the 3× clause would have had
  to separate divergence from a floor that already trends. That is an observation about the
  instrument, not a (G4) result.

**The single consequence.** `gdn_fast_ref` is **not admitted**. **Every arm of wave 1 and every size
of the ladder trains on the in-tree reference kernel** (§14.10 item 1). The realized cost is the
one-chip-per-run figure, which is **smaller** than the stake written in sections 1 and 2: **about
1.84 h per K1 run** at 4.715 q/s/chip on **one chip** with 30.5 GiB reserved
(`bench_record.json` `ref_tq2_nockpt`) and **6.76 h for the whole wave set**, set entirely by the
two K2-shared runs at 1.280 q/s/chip on one chip with 30.7 GiB reserved
(`v4_ref_k2sh_mt3000_r48`). The "~2.8 h per K1 run, roughly a day for wave 1" of §14.7 item 2,
quoted in section 1 above, was a **three-processes-per-chip** estimate and is superseded as the cost
of record by §14.10 item 8's figures; sections 1 and 2 keep their pre-run text.

**The fallback was not reopened after the result was seen, and the passing reading was flagged
rather than used.** §14.7 item 2's consequence clause exists precisely so the gate cannot be
reopened under schedule pressure once a number is in hand, and it was not: the branch was taken on
the declared reading, with the engineer reporting the pooled 1106 of 1116 = 99.1% as an undeclared
alternative and asking for a ruling. It is refused on three independent grounds (§14.10 item 1,
ruling §3.1): rule 3 bars choosing among readings after the data; §14.8 item 1's "only one
population may gate" refuses the same move; and, independently of any question of timing, the
out-of-bound tensors are clustered by tensor identity and by batch, so **1,116 is not a sample of
1,116** and a bar calibrated on 372 correlated tensors does not transfer to a pool of three
correlated batches. Three of the four natural readings of this data pass and the one that fails is
the one declared in advance; that asymmetry is why the engineer's conduct is part of this record.

**`fast_ref` is not retired.** It passed (G1) with two orders of margin and is a correct
implementation that failed a bf16-rounding bar. §14.10 item 3 fixes the terms for re-gating a
revised version — five batches named in advance, each judged separately against the **unchanged**
bound, the verdict the **median** of the five per-batch counts, the 3× clause binding on every
batch, and no pooling of tensors in any form — and that rule is **not retroactive**. Its own
counterfactual, which §14.10 item 15 requires it to state: the median of {368, 371, 367} is 368 and
this verdict would be unchanged.

**The mechanism finding, labelled as this report's own construct and not a literature conclusion**
(CLAUDE.md §4 rule 4). The claim is that **the gate path is the error-concentrating path of a
re-expressed gated-delta-rule inverse**, and it is a conclusion of this round's measurements on
Qwen3.5-0.8B at 18 layers in bf16, not a result from the literature.

- **The small-norm explanation is refuted by the gate's own numbers.** If `in_proj_a` failed because
  small-norm tensors carry large relative error, **both** kernels would be bad there and e_ref would
  be elevated with e_fast. It is not: on the verdict batch the median `e_ref` over the 372 is
  **0.035145** and the median `e_fast` is **0.035052** — the two kernels are indistinguishable in
  bulk — while the four failing tensors sit **at or barely above that median** in e_ref (0.03398,
  0.03710, 0.04826, 0.03563) with e_fast **1.5–1.7× higher** (0.05348, 0.06336, 0.07676, 0.05469).
  The reference kernel finds nothing unusual about these tensors; only `fast_ref` does.
- **Why the gate path and not another.** `g`, the cumulative gate, enters the kernel **only**
  through the matrix that is inverted, `A = −((k_beta @ kᵀ) · exp(g_i − g_j))`, while `q`, `k` and
  `v` also enter through paths outside it. `gdn_fast_ref` replaces the reference's replayed 63-step
  in-place forward substitution with `_BlockInverse`'s analytic backward `dL/dA = Xᵀ (dL/dX) Xᵀ`,
  with `X = (I − A)⁻¹`. So the change deposits its **whole rounding difference in `dL/dA`**, which
  is the **sole** route to the gate parameters — `dL/dq`, `dL/dk` and `dL/dv` receive diluting
  contributions from outside the inverse — and it applies **`X` twice**, so the backward error
  scales with cond(X)² where the forward scales with cond(X) once.
- **Three predictions, all observed.** (a) The kernel passes (G1) in fp32 with two orders of margin
  while failing (G2) in bf16, because conditioning bites at the bf16 mantissa and not the fp32 one.
  (b) The per-batch count varies with the batch's decay profile — the observed 367–371 spread.
  (c) The worst batch is the one with the longest chunks and the most padding, which is step 2
  (4,282 padded tokens, worst ratio 1.50, per ruling §4.2).
- **It is a property of the operator, not of either implementation.** Two independent
  re-expressions of this inverse, by different authors with different algorithms, degrade the same
  path, and §14.8 item 1 predicted that from the FLA evidence alone before any `fast_ref` number had
  been read.

**What this record cannot claim.** Everything section 3 forbade before the run stands unchanged:
nothing about accuracy on any suite for either kernel, nothing about any Track K or Track T decision
line, no evidence for or against research gates G1, G2 or G3 in either direction, and nothing about
the FLA kernel, whose verdict remains §14.4's. Added by the result:

- **§12.7, new** (§14.10 item 4). Under the reference kernel in bf16 the gate path is the noisiest
  gradient in the model — e_ref of 0.034 to 0.051 relative error against the fp32 gold on
  `in_proj_a`, `A_log` and `dt_bias`. The claim that is therefore **not available: this round cannot
  claim that its `in_proj_a` LoRA adapters learned a well-conditioned signal.** A 3–5% relative
  gradient error on the one gate-path adapter is a plausible low-SNR channel, and if a later round
  finds `in_proj_a` adapters contributing little, this measurement is the first place to look rather
  than a finding about gating's importance in the architecture. bf16 compute over fp32 master
  weights remains this round's pre-registered precision (§7.2); nothing changes, and no experiment
  is authorised by the item.
- **Nothing changes for the reference kernel.** It is the baseline against which e_ref is defined
  and its fp32 form is the gold, so no measurement here is evidence about its admissibility in
  either direction.
- The model-level (G3) zero is scoped to one chip, one container, one host, one CANN version,
  sequential in time, and is **not** evidence of reproducibility across chips, hosts or images.
- §14.7 checklist item 5, which the pre-run section 5 said a pass would fix, is **met for the branch
  that now trains**: reference + shared K2 0.0585 against the row form's 0.0586, clean against the
  floor. The `fast_ref` cell (0.0746 against 0.0642, not covered by the model-level floor) is moot
  under this verdict.

**Two findings this gate produced that are not about this kernel.** They came out of the (G3)
measurements, they belong to the trainer rather than to `gdn_fast_ref`, and they are recorded as
**§14.10 items 5 and 6**. E1 points at them; it does not restate them as its own result.

1. **The roughly ten-step reproducibility limit** (§14.10 item 6). A same-seed training run is
   bitwise reproducible for about 5 to 10 optimizer steps and not beyond; past that, two same-config
   runs are two samples from one distribution. §14.3's "exact resume" claim keeps its numbers and
   loses its scope, the word "exact" is struck, and the resume test is rewritten before wave 1
   launches.
2. **The divergence seed is in the forward / loss reduction rather than in the gradients, and Adam
   is refuted as the amplifier** (§14.10 items 5 and 6). No gradient tensor ever differs across the
   measured same-config pairings while the loss scalar differs by a half-ULP, and at the first
   differing step of every trajectory pair the `grad_norm` difference is exactly 0.0. The SGD
   replicate in `sgd_replicate/` diverges **earlier** than AdamW (first differing step 3 against 5)
   and ends twice as far apart (final-weight relative L2 2.69e-04 against 1.31e-04), so Adam's
   second moment is not necessary for the phenomenon.

Each has its own scope limits and its own follow-ups in §14.10 — item 7's localisation run and items
8 and 13's two K1 seed-2 replicates — and each of those gets its own wiki entry, written before it
launches (CLAUDE.md §8).

**Open question this record leaves.** Whether a revised `fast_ref` can pass (G2) under §14.10 item
3's five-batch median rule. The mechanism above says where to look: the cond(X)² dependence of
`_BlockInverse`'s analytic `dL/dA`. (G4) remains unrun and would only be informative after a (G2)
pass.
