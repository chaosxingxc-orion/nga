# E16 — Initial Nimble native NPU compatibility

Preregistered 2026-10-30 before launch. Engineering synthetic inputs only.

## Purpose and counterpart

Defect registry row 12, measurement validity: establish whether the original public-benchmark
Nimble adapter can execute on the authorized Ascend image without replacing its candidate-token
readout. A constant distribution can pass shape checks; this probe does not establish accuracy,
consistency or training benefit. V3 alias substitution must fail, while the pinned initial adapter
must pass identity checks. Candidate projection is also recomputed on CPU from the same hidden
state; differences are diagnostic, with no invented numerical equivalence threshold.

## Frozen setup

Original public-benchmark revision `594dfdcfb6f94e3d0c0db7535180d3c71689169a`, adapter SHA256
`ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b`. Restored to a separate
inventory directory after discovering the no-suffix local model alias actually contains v3.
Seven required files match that revision's SHA256SUMS. Base Qwen/Qwen3.5-9B revision
`c202236235762e1c871ad0ccb60c8ee5ba337b9a`, already local. Preserve v1 schema contract and
prompt source hash, tokenizer, BF16 CPU safe merge, BF16 SDPA backbone and FP32 candidate-token
projection. Temperature 1.0, prompt limit 2048, no truncation, sampling or fitting.

Four frozen synthetic fixtures exercise boolean, enum, ordered score-like enum and a named-choice
discrimination pair; each is executed twice. Logit repeat and CPU projection deltas are diagnostic.
No public test row, held-out NGA candidate or training is used.

## Execution and acceptance

175 only, physical chip 3 after allocation lock and live-device checks. Existing immutable image
`sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.
Run directory `/mnt/cephfs/xingchao/experiments/jev/reference_inference/nimble_initial_probe_20261030/`;
retained detached container `nga-reference-nimble-initial-probe`. CephFS contains exact launch,
frozen dependencies, timestamped progress, per-chip throughput, reserved memory, eight atomic
receipts, report hash, terminal and wrapper exit. A resume command validates frozen configuration
and the contiguous receipt prefix; changed or incomplete receipts are rejected.

Acceptance requires eight outputs, finite logits and normalized probabilities, matching prompt
and candidate token identities, all frozen hashes intact and terminal/wrapper/container exit zero.
No CUDA/NPU numerical equivalence claim follows. Full public test identity reconstruction remains
separate work, with seven true-test subsets totaling 1,884 rows.

## Results

2026-10-30 15:56 UTC: probe completed all eight outputs; structured terminal rc 0
at 15:56:32Z, wrapper rc 0 at 15:56:37Z and retained Docker exited 0. Container ID
`ec781da0595036043996dfe0510aacb3695043de79b6b1a4078f554ed1d1f1ed`.
Report hash, eight receipt hashes and all 136 frozen files were independently rechecked.
Load plus CPU merge took 35.6788 seconds; single-chip reserved memory 18.2051 GiB.
Repeat max logit delta was 0; same-hidden-state CPU FP32 projection max delta was
0.0000438690185546875. These diagnostics do not certify cross-device equivalence.

Timing correction: the frozen report's 0.37177 questions/s/chip included final full-file
hash verification after inference. The final inference heartbeat recorded 1.88151
questions/s/chip (one chip), including projection diagnostics and receipt writes. The
repository driver now stops the inference timer before final hash verification; frozen
artifacts remain unchanged. Neither number is production throughput or a full-test rate.
Chip 3 released only after terminal, hashes, wrapper and exited-container verification.
Post-run operational note: `RESUME_EXACT.sh` was added after completion to document the
resource/identity-guarded relaunch command. It deliberately rejects this successful terminal
and released allocation. It was not in the 136-file frozen execution and no interruption or
resume was exercised in E16; item-prefix resume support must not be described as a tested
recovery result.

## Verdict

Native synthetic compatibility observed; no reference test result. Public subsets and
independent formal-evaluation audit remain to be completed. No training benefit claimed.
