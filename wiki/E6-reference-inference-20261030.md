# E6 — Native Kev reference inference on Ascend

Status: preregistered before launch; development probe completed 2026-10-30 14:09:12 UTC. Host 175; existing image
`nga-verl-qwen35-v030:20261029`; one physical chip, 1.

## Purpose and hypothesis

Execute reference-model inference, beginning with a compatibility and throughput probe of
Kev-0.8B's native pointer head. This addresses defect registry row 12, measurement validity.
It is not NGA training, a test score, or evidence of model benefit.

The candidate instrumentation should load the published adapter and head over the local
Qwen3.5-0.8B-Base mirror, preserve the native encoder, option order and checkpoint temperature,
and produce finite complete probability distributions. The degenerate optimum of merely
returning valid constants is insufficient: preserve logits and probabilities for inspection,
repeat each input, and require later source/loader and discriminative controls before accepting
benchmark results. This probe alone does not admit a full benchmark.

## Fixed setup

Use the first two records of official decision-v7 development, selected before inference.
No test partition is read. fp32 weights and compute, eager attention, unmodified transformers
reference Gated DeltaNet, LoRA merged according to the upstream default; no fast_ref or FLA.
Disable NPU HF32. Hash adapter, head, base shards, tokenizer, dataset, code and manifest.
Run original `LocalPredictor`, adding explicit NPU synchronization because upstream sync
recognizes only CUDA/MPS. Resolve the original base ID to its existing local mirror.

Record repeat probability delta without inventing a post-hoc tolerance. Record wall time,
questions per second per chip (chip count 1), and reserved memory; loading/first compilation
may dominate this tiny probe, so it is not a steady-state throughput claim. Finite probabilities
and exact option coverage are validated by upstream `prediction_rows`.

## Survivability and acceptance

Fixed detached Docker name `nga-reference-kev08-probe`, no automatic removal. Outputs under
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev08_probe_20261030/` include
CephFS log, heartbeat, exact relaunch command, provenance, atomic per-record predictions and
terminal marker. Resume skips only records matching frozen provenance. Source and driver
snapshots are frozen outside downloaded trees. No existing container is stopped.

The source of completion is `REFERENCE_PROBE_COMPLETE.json` plus wrapper exit marker, not
Docker liveness. A successful probe is engineering evidence only. Before full test inference,
review native loader compatibility, observed numerical behavior, discrimination and efficiency;
register any necessary changes first. No new model-training job is authorized by this entry.

## Results

**2026-10-30, completed probe:** `REFERENCE_PROBE_COMPLETE.json` records rc 0 and
two development records; wrapper `DONE` records rc 0 at 14:09:12 UTC. Docker
`nga-reference-kev08-probe` exited 0, container ID
`572af25cd025bc24a978e00dc2db0fe7faf33342c1c50e33200a3c63b67d28f0`.
The existing image ID is
`sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.

The checkpoint's temperature is 2.3510958125672174. Both records produced complete,
finite native pointer distributions; repeated probabilities were identical on each record
(maximum absolute difference 0). They were not constant across records: the top options were
`fiat_currency_support` and `change_pin`. These two observations are too small to establish
general numerical equivalence or invariance; the zero repeat delta is a diagnostic, not a
research success claim. Both records happen to carry upstream `banking77/test/...` IDs, but
they were selected from the hashed Kev **development.jsonl**, not Kev's test partition.

| Development record | Repeated-pass wall time | Questions/s/chip | Chips | Reserved GiB |
| --- | ---: | ---: | ---: | ---: |
| banking77/test/914 | 1.24145 s for 2 passes | 1.61102 | 1 | 3.24023 |
| banking77/test/2120 | 0.90074 s for 2 passes | 2.22040 | 1 | 3.27734 |

The local base `.complete` revision is `dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`,
matching checkpoint provenance. Runtime versions were torch 2.10.0+cpu with torch_npu
registered, transformers 5.14.1, PEFT 0.21.2. The model reports npu:0, float32, eager
attention and the transformers reference gated-delta implementation. No test metric or
cross-hardware parity conclusion is reported.

Frozen inputs, executable code and per-record output are in the run directory. Source stamp:
`a59d17c8cc4dc8566ce0b26bd152031ee1003d03408d09950c6eb1afee7f2b10`.
The original pre-launch registration is preserved there as `PREREGISTRATION.md`; this dated
result addition does not change that snapshot.

## Verdict

Native Kev inference is executable in the existing Ascend image. Full test evaluation,
robust provenance validation and automatic orchestration remain work to complete; this
two-record probe does not satisfy them. No formal training or locked NGA test read occurred.
