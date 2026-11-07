# Engineering efficiency plan (RC1)

Updated: 2026-11-07 UTC. This is the current efficiency decision sheet; detailed
process evidence remains under `.local/releases/engineering-base-rc1/tasks/`.

## Resource state

As of the **2026-11-07 02:56:20 UTC** script snapshot, H1 seed2 and seed3
have completed 3116 updates and exited 0. H2 seed2/seed3 remain on physical
chips 2/3, at 111/96 updates. Shared-prefix DEV has exited 0 and released chip4.
The H2 efficiency diagnostic launched on physical chip5 at 02:55:44 UTC, in
retained container `nga-h2-efficiency-actual`. Its current task is a bounded
screen followed by tensor-level numerical qualification, not accepted timing.
H1 DEV preparation remains CPU-only; no claim or inference launch is asserted.

The previous five-active-job description was based on the older 01:22 UTC
snapshot and is superseded by these terminal records. Running-job counts and
instantaneous device use are different from measured accelerator utilization.
All new claims still use current controller ownership checks. Historical pending
claims are preserved; the diagnostic has its own explicit priority override.

## Measured bottleneck decomposition

The current H2 K2 run uses one chip per seed, global batch 10, reference kernel,
gradient checkpointing and `micro_tokens=12000`. The observed post-first-step
means are about 91 s/update (seed 2) and 144 s/update (seed 3), with roughly
30--31 GiB reserved per chip. Candidate-token work explains nearly all measured
step variation in the captured window: the descriptive fit is
`step_seconds = 24.54 + 0.00079334 * candidate_tokens` with R² 0.999236.
This is a workload diagnosis, not a speedup claim.

The actionable components are:

1. **Candidate expansion and repeated prompt work (primary).** K2 expands every
   base question to all candidates and repeats prompt tokens. Each question is
   forwarded in chunks and then backed up separately, so heavy candidate sets
   dominate both compute and graph lifetime.
2. **Per-question launch and host preparation (secondary).** Tokenization,
   sorting, CPU padding/index construction, transfers and Python control happen
   inside the measured step. The current implementation also performs one host
   scalar read after each question. Their individual shares are not yet measured.
3. **Model memory/activation pressure (constraint).** Checkpointing and retained
   per-question graphs limit safe batching. The 30--31 GiB reservation does not
   by itself prove that checkpointing can be removed or that a larger batch fits.
4. **Startup and inter-step gaps (not the dominant cause).** The measured gap
   outside the step timer is about 0.2--0.3 s in aggregate across the captured adjacent updates; startup
   is about 18 s. These do not explain minute-long heavy updates.
5. **Evaluation is a separate queue.** DEV/TEST scoring must run on CPU workers
   and spare NPU lanes asynchronously; it must not block training or be used as
   a reason to leave chips unassigned.

## Candidate changes and acceptance order

| Candidate | Expected scope | Gate before adoption | Decision |
|---|---|---|---|
| Bulk scalar synchronization | Speed-only, same forward/backward/order | Seeded numerical comparison, then paired baseline/candidate timing on the same workload; peak memory within +5% | First one-chip screen on an idle lane |
| Cached/vectorized host preparation | Speed-only if token IDs, order, masks and RNG are unchanged | Numerical equality/noise-floor check plus paired timing | Independent candidate; scalar-sync need not improve first |
| Candidate micro-batch 12k → 16k / 24k tokens | Same global batch10; different forward chunk shapes | Fixed-workload memory, dropout/checkpoint and gradient checks, then matched timing | CPU shape accounting complete; NPU validation pending |
| Fused question/candidate batching | Potentially large gain | Explicit dropout/RNG mapping, memory check, gradients/optimizer state and paired timing | Separate prospective candidate; no live recipe change |
| Global batch 20/40 | Changes optimization semantics | New preregistered recipe and scientific comparison | Not a speed-only change |
| World-size 2 DDP | Potential throughput gain | Real rank loop, fixed collective order, global denominator, RNG/dropout compatibility, checkpoint/resume and NPU numerical gate | Independent path after its own one-chip baseline; scalar-sync is optional, not a prerequisite |
| World-size 4 DDP | Potential throughput gain | All world-2 gates plus measured end-to-end scaling | Do not launch speculatively |

The current CPU DDP algebra and Gloo tests are preparation only. They do not
qualify an Ascend multi-card run. A multi-card result is accepted only when all
paired ratios are below 1.0 and the preregistered scaling thresholds are met:
median speedup at least 1.20 for two cards (each seed at least 1.10), and at
least 2.00 for four cards (each seed at least 1.70).

The DDP path must first compare an actual world-1 run and a world-2 run on the
same frozen eight-update workload. It does not need to wait for scalar-sync to
show a gain, because scalar-sync changes host synchronization while DDP changes
the execution topology. Both candidates still require their own numerical gate
before timing is interpreted.

## CPU shape accounting for candidate micro-batches

The already materialized TRAIN workload contains eight updates per seed. CPU
counting reproduces the current 12k chunk and padded-position totals exactly.
It reads no original dataset or model payload and makes no speed claim.

| Seed | Candidate tokens (all configurations) | 12k chunks | 16k chunks | 24k chunks | Padding at 12k / 24k |
|---|---:|---:|---:|---:|---:|
| 2 | 666,251 | 147 | 132 | 123 | 0.1226% / 0.2097% |
| 3 | 995,043 | 168 | 148 | 129 | 0.1122% / 0.2041% |

Larger micro-batches reduce forward chunk counts by roughly 10–23% in this
small workload; they do not reduce candidate-token work or the number of
question backwards. This is an opportunity to measure, not predicted speedup.
Padding waste is already small. Changing chunk shapes can change dropout RNG
and peak activation memory even with the same global batch10; adoption therefore
needs its own numerical check. This differs from global batch20/40, which also
changes sample weighting per update and schedule semantics.

## Queue policy and next actions

Keep H2 training on chips2/3 unchanged while the diagnostic on chip5 completes.
The CPU side prepares H1 DEV against its actual completed checkpoints, then
launches each seed independently after its own runtime is ready. No further
training-completion wait is necessary for H1.

Scalar-sync, micro-batch sizing, host preparation and DDP are separate candidate
branches; a scalar-sync benefit is not a prerequisite for the others. World2
needs a real world1 comparator, its own numerical gate, and measured timing;
world4 follows an accepted world2 result and available resources. Preserve the
registered global batch10. Do not reserve devices during CPU preparation.

The completed shared-prefix DEV diagnostic has an independent CPU recomputation:
three paired raw-wall ratios of 2.355505, 2.342771 and 2.296179; max score delta
0.000146151 nat, no argmax flips. **Final Astra result review remains pending.**
This is actual 9B seed2 single-chip DEV192 evidence; it does not authorize full
TEST adoption, other-model use, or shared-prefix training with dropout.

Routine monitoring uses script digests and terminal events at approximately
600-second cadence. Process evidence and numerical recipes remain local under
`.local/releases/engineering-base-rc1/`; publication must distinguish CPU
preparation, running NPU diagnostics, and accepted results. No user decision is
currently required.
