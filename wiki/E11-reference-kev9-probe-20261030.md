# E11 — Native Kev-9B development compatibility and efficiency probe

Status: preregistered before launch, 2026-10-30. Host 175, chip 1 after allocation and
live Docker device verification. No test inference or training is authorized by this entry.

## Purpose and hypothesis

Measure whether released Kev-9B can execute its native pointer head in the existing Ascend
image with float32 eager/reference GDN and checkpoint temperature. Defect registry row 12:
instrument validity. Valid constant probabilities could satisfy structural checks, so this
probe establishes execution only, not semantic quality, invariance or generalization.
Keep full predictions/logits and repeat deltas; no post-hoc numerical tolerance is imposed.

## Frozen setup

First four official decision-v7 development records, each twice, fixed before inference.
Use native LocalPredictor, original encoding/context, merged LoRA, no FLA, HF32 off.
Verify checkpoint base ID/revision equals the existing Qwen3.5-9B-Base mirror; fail rather
than substitute another revision. Freeze source, model/base weights, tokenizer/configuration,
development split/manifest, wrapper and launch scripts. No temperature fitting.

Report loading time separately, repeat-pass questions/s/chip, one physical chip and reserved
memory. Four records are not a full-suite throughput benchmark. Repeatability is diagnostic,
not evidence of cross-device equivalence. Every prediction must have complete finite native
distributions; changed persisted receipts are refused. Unique temporary paths and joined
heartbeat thread prevent final STATUS writer races in this script version.

## Execution and acceptance

Fixed retained detached container `nga-reference-kev9-probe`, existing immutable image from
E7/E8. CephFS directory:
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev9_probe_20261030/`.
Keep exact launch/restart commands, frozen provenance, log, 15-second heartbeat, per-record
atomic receipts, report and REFERENCE_PROBE_COMPLETE marker plus wrapper DONE/FAILED.
Release chip only after terminal and retained Docker exit are verified. Long runs are detached;
container commands use python3 -P so CANN PYTHONPATH survives.

## Results

Pending. Model directory presence alone does not establish compatibility or memory fit.

**First launch correction:** the orchestrator launched before the background host hashing
process had finished publishing FROZEN.json. The container exited 1 at 15:01:48 UTC with
the manifest absent; no model inference occurred. This is launch sequencing failure, not
9B model failure. Preserve that directory/container. Retry uses a new directory and waits
for completed manifest verification before launch. The atomic writer also explicitly uses
0644 for shared audit artifacts; mkstemp's default 0600 prevented host reading the first
container-owned failure marker.

## Verdict

**2026-10-30 successful retry:** run directory `kev9_probe_20261030b`, fixed container
`nga-reference-kev9-probe-b` (`62d22e1e36a9482b7fc779f83b93c3e8d01b1497da8e3dc9a4d204dedde7b9a3`).
The 65-file manifest was fully written before this launch. Native checkpoint base identity
matched revision `68c46c4b3498877f3ef123c856ecfde50c39f404`; serving temperature remained
2.193649959389252. All four development records were inferred twice, preserving complete
finite distributions. Payload receipt hashes were independently rechecked.

Model load took 17.6042 seconds, excluding file hashing. Repeated-pass rates were 1.8409,
1.8055, 1.8132 and 1.8505 questions/s/chip, one chip. Reserved memory was 31.1094 GiB.
All four repeat probability deltas were zero; this is a small diagnostic sample, not numerical
equivalence evidence. End-of-run frozen file hashes were verified before the terminal marker.
Structured terminal, wrapper DONE (15:04:46 UTC) and retained container all report rc 0.
Chip 1 was released only after terminal and container exit checks.

Native Kev-9B is executable in the tested configuration. No full test result, general throughput,
training benefit or Astra approval is claimed. Original failed run remains preserved, and its
launch error is not counted as a model failure. Exact retry launch is in the `b` directory;
restart is deliberately disabled pending explicit ownership/identity revalidation.
