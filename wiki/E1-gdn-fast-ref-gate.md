# E1 — the admissibility gate for `gdn_fast_ref`, a third gated-delta-rule kernel

> Status: planned · Round: R3 SFT round 1, engineering prerequisite to wave 1 (`R3-SFT-PREREG.md`
> §14.7 launch checklist item 2) · Date written (UTC): 2026-10-30, before the run
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

Not run yet. To be filled from `gate_fast_ref/`'s own files: (G1) model-level fp32 logits relative
L2 and minimum gradient cosine; (G2) the per-tensor pass fraction over the 372 tensors with the
count of tensors beyond 3 · e_ref(t) + 1e-3; (G3) d(R,R′) over the stacked LoRA gradient and the
per-step |loss_R − loss_R′| series; (G4) the full 100-step per-step |Δloss| series with its mean,
its first-20 mean and its last-20 mean, against the bar max((G3) floor, 1.14e-02) and the 3× trend
clause; the four sha256s; and the speed figures **per chip with the chip count stated** and reserved
memory (CLAUDE.md §9), each at ±15%.

Suspicious-success checks, explained **before** any number is reported (CLAUDE.md §7.1): a (G3)
floor of exactly 0.00e+00, a (G2) pass fraction of exactly 1.0, a |Δloss| series identical across
steps, or any criterion measured on fewer batches than the amendment's fixed set.

## 5. Verdict

Not run yet. Will state, per pre-registered criterion only: (G1), (G2), (G3) and (G4) each passed,
failed or void, with the measured value beside its bar; which of H1–H4 survived; and the single
consequence — `gdn_fast_ref` admitted for wave 1 and the ladder, or wave 1 and the ladder train on
the reference kernel at the recorded cost of ~2.8 h per K1 run, ~6.8 h per K2-shared run, roughly a
day. The fallback is not reopened after the result is seen. A pass also fixes the kernel on which
§14.7 item 3's production bf16 K2 cell is re-measured against the (G3) floor (launch checklist
item 5), which is a separate record.
