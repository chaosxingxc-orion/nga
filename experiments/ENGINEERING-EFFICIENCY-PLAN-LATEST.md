# Engineering efficiency plan (RC1)

Updated: 2026-11-07 UTC. This is the current efficiency decision sheet; detailed
process evidence remains under `.local/releases/engineering-base-rc1/tasks/`.

## Resource state

The latest script digest shows five active one-chip jobs on host 175: H1 seed 2
and seed 3 on chips 0 and 1, H2 seed 2 and seed 3 on chips 2 and 3, and the
shared-prefix DEV job on chip 4. Chips 5, 6 and 7 are the candidate idle lanes.
The visible `npu-smi` state is not sufficient to claim a chip: historical pending
claims remain in the allocation records. A new job must pass the resource
controller's current ownership check, claim one chip, and release it only after
the retained container exits and the terminal marker is written. Chip 0 stays
reserved for the H1 DEV continuation after H1 seed 2 completes.

## Measured bottleneck decomposition

The current H2 K2 run uses one chip per seed, global batch 10, reference kernel,
gradient checkpointing and `micro_tokens=12000`. The observed post-first-step
means are about 91 s/update (seed 2) and 144 s/update (seed 3), with roughly
32--33 GiB reserved per chip. Candidate-token work explains nearly all measured
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
   per-question graphs limit safe batching. The 32--33 GiB reservation does not
   by itself prove that checkpointing can be removed or that a larger batch fits.
4. **Startup and inter-step gaps (not the dominant cause).** The measured gap
   outside the step timer is about 0.2--0.3 s between adjacent updates; startup
   is about 18 s. These do not explain minute-long heavy updates.
5. **Evaluation is a separate queue.** DEV/TEST scoring must run on CPU workers
   and spare NPU lanes asynchronously; it must not block training or be used as
   a reason to leave chips unassigned.

## Candidate changes and acceptance order

| Candidate | Expected scope | Gate before adoption | Decision |
|---|---|---|---|
| Bulk scalar synchronization | Speed-only, same forward/backward/order | Seeded numerical comparison, then paired baseline/candidate timing on the same workload; peak memory within +5% | First one-chip screen on an idle lane |
| Cached/vectorized host preparation | Speed-only if token IDs, order, masks and RNG are unchanged | Numerical equality/noise-floor check plus paired timing | Second, only if scalar screen is neutral or positive |
| Fused question/candidate batching | Potentially large gain | Explicit dropout/RNG mapping, memory check, gradients/optimizer state and paired timing | Separate prospective candidate; no live recipe change |
| Global batch 20/40 | Changes optimization semantics | New preregistered recipe and scientific comparison | Not a speed-only change |
| World-size 2 DDP | Potential throughput gain | Real rank loop, fixed collective order, global denominator, RNG/dropout compatibility, checkpoint/resume and NPU numerical gate | After one-chip candidate passes; world 4 only after world 2 |
| World-size 4 DDP | Potential throughput gain | All world-2 gates plus measured end-to-end scaling | Do not launch speculatively |

The current CPU DDP algebra and Gloo tests are preparation only. They do not
qualify an Ascend multi-card run. A multi-card result is accepted only when all
paired ratios are below 1.0 and the preregistered scaling thresholds are met:
median speedup at least 1.20 for two cards (each seed at least 1.10), and at
least 2.00 for four cards (each seed at least 1.70).

## Queue policy while cards are idle

Keep H1/H2 and the shared-prefix job running. Use at most one newly claimed
idle chip for the bounded eight-update baseline-versus-candidate numerical
screen; do not start a filler job. If the numerical gate passes, keep the same
lane for synchronized AB/BA timing. If it fails, write the failure receipt,
release the lane, and fix only the identified adapter issue. Once a lane is
released, the next eligible task may claim it through the same controller.

CPU analysis, result comparison, DEV/TEST aggregation and queue construction run
in parallel with these NPU jobs. Routine monitoring remains script based at the
approximately 600-second cadence and consumes digests, markers and report files,
not raw logs.

## Current decision

There is useful idle capacity, but the queue is not empty: five NPU jobs are
active. The safe action is therefore a bounded efficiency screen on one verified
idle lane, followed by world-size 2 only if the screen and numerical gates pass.
No batch-size change, DDP claim or speedup claim is accepted yet.
