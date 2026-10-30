# W1 — wave 1: the first weight updates (K1, K2, K1-PT, K1-QO, K1-FLA)

> Status: planned · Round: R3 SFT round 1, step 2 (`R3-SFT-PREREG.md` §14.5 item 4 step 2)
> Date written (UTC): 2026-10-30, before the run · Pre-registration: §7.2 (K1), §7.3 (K2), §7.8
> (K1-PT), §7.9 (K1-QO), §14.4 (K1-FLA), §8.2 (adoption), §9.1–§9.2 (decision lines)
> Run dir: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/w1_*` · Code: `experiments/r3_sft/r3_code/`

## 1. Purpose

The **first weight updates of the whole program.** Eight single-chip LoRA runs, decided together:

| arm | what it is | role |
| --- | --- | --- |
| K1 seeds 2, 3 | Kev's stage-1 recipe replicated, read out with our label log-probability readout | **gating.** K-align (§9.1) is judged on K1 only |
| K2 seeds 2, 3 | same, but the loss is option-restricted (Kev's objective expressed in our readout) | candidate, via §8.2 |
| K1-PT seeds 2, 3 | K1's recipe on the post-trained `Qwen3.5-0.8B` | control: lets B-4 be evaluated against R0 itself |
| K1-QO seed 2 | K1's recipe with the input dropped from every training prompt | control: the trained question-only seal |
| K1-FLA seed 2 | K1 seed 2 on the fast gated-delta-rule kernel | engineering only; decides whether the ladder may use that kernel |

It answers one question: **can a small Qwen3.5 checkpoint, trained on public data with a recipe we
can defend line by line, reach the reference's reported accuracy on the reference's own test sets?**
That is the user's goal for this round. It does **not** answer whether the semantics are read, which
is G2's question and is not measured here (§1.2, §12.1).

Registry rows: 1 and 17 via accuracy on declared level sets; 8 via Kev's ordinal `score` questions.
Gate: **none.** No trained-arm number of this round is evidence for or against G1 (§14.5 item 6).

## 2. Hypothesis

**H1 (K-align, the headline).** K1's two-seed mean reaches decision-v7 dev ≥ 0.80 and transfer-v4
dev ≥ 0.60. The like-for-like reference is Kev's own stage-1 trials on the same base checkpoint:
0.8172 / 0.8196 / 0.8291 and 0.6220 / 0.6341 / 0.6433 (three seeds). *If it is reversed*, one of the
five declared differences from Kev (§3.3) costs more than we judged, and the round reports a gap with
those differences named as **candidate** causes — not as measured causes, since this round measures
none of them. A miss does not stop the round and does not disqualify K1; it forbids the words
*aligned*, *matches* and *replicates* (§14.5 item 3).

**H2 (K2 beats K1).** The option-restricted loss should help: it is the objective Kev actually
optimises, and it normalises over exactly the options the readout will compare at evaluation time,
whereas K1's token cross-entropy does not. *If it is reversed* — if K1 ≥ K2 — then the gradient
signal of "push the gold name's tokens up" is sufficient, and the readout's normalisation is not
something training needs to match. Either way the §8.2 paired bootstrap decides adoption, not the
point difference.

**H3 (the trained question-only seal).** K1-QO, trained and scored with the input dropped, stays
**more than 5 points below** K1 on transfer-v4 dev. *If it is reversed* — if a model that never sees
the input matches one that does — then this round's accuracy is a property of the level sets and
label priors, not of reading the business situation, and no transfer-v4 number may be called semantic
transfer (§5.5). This is the discrimination counterpart that seals the whole round; see §2 below.

**H4 (the fast kernel).** K1-FLA lands within [min − 1.0, max + 1.0] points of the two
reference-kernel K1 seeds on both dev suites, with paired disagreement no larger than seed 2 vs
seed 3. *If it is reversed*, the ladder trains on the reference kernel and the measured speed gain is
forfeited. The criterion was fixed in §14.4 **before** the run, after the kernel had already failed
its numeric gate.

**Unconstrained optimum and the discrimination counterparts** (CLAUDE.md §4 rule 2). The
unconstrained optimum of "maximise accuracy on decision-v7" is to **memorise the trained sources'
label priors** and ignore the input; a second degenerate route is to **learn the generator's
grammar** rather than the decision rule. Three counterparts seal them, all pre-registered:
transfer-v4, whose sources are never trained on (§2.2); K-floor (§9.2), which requires every seed of
every arm to beat both the constant and the test-time question-only arm by ≥ 5 points on **both**
suites; and K1-QO (H3), the *trained* question-only seal, which is stronger than the test-time one
because it gives the degenerate strategy a full training budget to succeed with.

## 3. Setup

- **Base**: `Qwen3.5-0.8B-Base` (rev `dc7cdfe2…`) for K1/K2/K1-QO/K1-FLA; `Qwen3.5-0.8B`
  (rev `2fc06364…`) for K1-PT. From `/mnt/cephfs/xingchao/models/jev/`.
- **Data**: Kev `decision-v7` train only, 15,576 base questions, augmented by calling Kev's own
  functions (§3.4, ruling 12), one example per question, prompt `r0-prompt-v2`. No Track T data is
  trained on, so §2.6's exclusion is vacuous this round.
- **Recipe** (frozen, §7.2): LoRA r16 / α32 / dropout 0.05 on the hybrid target list, embeddings and
  LM head frozen; AdamW, weight decay 0.01, `OneCycleLR(max_lr=1e-4, pct_start=0.1)`, grad-norm clip
  1.0, bf16 compute over fp32 master weights; 2 epochs; 10 base questions per optimizer step, 1,558
  steps per epoch, **3,116 total** (Kev runs 3,144 — a declared difference); loss on the response
  `" " + gold name` only, prompt masked, **no EOS**; end-of-training checkpoint.
- **Model of record**: the **unmerged** adapter applied to the base at scoring time (§14.5 item 5).
  Folding into bf16 perturbs scores: on the smoke run it moved the headline by +0.005 under Kev's tie
  rule and −0.005 under R0's, entirely through 2 manufactured ties.
- **Kernel**: the **reference** kernel for all 0.8B arms (§14.4; the fast kernel failed (b′) and (c)).
  K1-FLA is the single exception, by design.
- **Trainer**: `r3_code/train_r3.py`, single-chip PyTorch + peft (§14.3, not verl's FSDP SFT).
- **Compute**: host 175 (`npu`), 8 × 910B3, image `nga-verl-qwen35-v030:20261029`, one chip per run,
  no chip shared between runs of record (§14.5 item 4 step 2). The chip assignment and per-chip
  concurrency are written into the wave directory **before launch** and do not change after any
  arm's dev number is read; the file's sha256 goes into each run's §7.7 record.
- **Efficiency, settled before launch** (CLAUDE.md §9 and the user's instruction that efficiency is
  fixed first): the smoke run used 6.6 GiB of ~61 GiB at ~4.5 s/step, and the K2 loss cost ~72.6k
  tokens/step against ~3.0k with prompt sharing. Both are being addressed before this wave starts;
  the before/after per-chip throughput table goes in §4.
- **Run hygiene**: detached, fixed container name, no `--rm`, log and heartbeat on cephfs carrying
  per-chip throughput, terminal marker holding the exit code as the source of truth, resumable at
  step granularity, relaunch command in the run directory.

> **Correction, 2026-10-30, same day, after amendment 7.** The **Kernel** bullet above is
> superseded in part. `R3-SFT-PREREG.md` §14.7 item 1 reads §14.4's verdict as governing the fused
> gated-delta-rule / FLA kernel under `speedup/` only, so the kernel of record for wave 1 is now
> **whichever kernel §14.7 item 2's gate leaves admissible**: the in-tree reference, or
> `gdn_fast_ref` if (G1)–(G4) all pass. That gate is recorded in
> [`E1`](E1-gdn-fast-ref-gate.md). Wave 1 may not launch until the **seven-item launch checklist**
> at the end of §14.7 is green. H1–H3 are unaffected. H4 is unaffected too: K1-FLA still runs,
> since §14.4 governs the FLA kernel and §14.7 did not touch that arm.

## 4. Results

Not run yet. To be filled from each run's own files: per-seed dev accuracy per suite with n and tie
counts, the §8.2 paired bootstrap CI and discordant counts, K-floor margins against the constant and
question-only arms, the K1-FLA comparison, the loss curves, and per-chip throughput with chip count
and reserved GiB (before and after the efficiency work).

## 5. Verdict

Not run yet. Will state only what the pre-registered lines allow: K-align met or missed by how much;
K-floor per arm per seed; whether K2 replaces K1 under §8.2; whether the ladder may use the fast
kernel; and which of H1–H4 survived. Explicitly **not** claimable from this wave: any invariance,
consistency, abstention or unknown-handling result; any G1 or G2 evidence; any statement that a
result is aligned with the reference unless the §14.5 item 3 bound is met.
