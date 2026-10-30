# E17 — Native Open-Jev-9B compatibility and efficiency probe

Preregistered 2026-10-30 before launch. Host 175 only, physical chip 1 after allocation and live-device checks.

## Purpose and hypothesis

Establish whether the released 9B checkpoint's original typed scalar-head inference runs on the existing Ascend image. Defect 12: measurement validity; defect 16: comparable evidence. A constant or structurally valid response can pass API validation, so this probe does not establish model quality or consistency. Three fixed synthetic requests (choice, noul, score), each evaluated twice, distinguish interface failures and nonfinite results from a usable path. Repeat differences are descriptive, without a fitted equivalence threshold.

## Setup

Qwen/Qwen3.5-9B Instruct revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, Open-Jev-9B package/checkpoint, native max_length 4096, saved temperature 1.8969118766347646. Preserve bf16 backbone, float32 head, unmerged adapter, native SDPA and prompt encoder. Only local model resolution and NPU device/timing are adapted. Use image `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.

## Execution and acceptance

Freeze all model, base, tokenizer, native source, fixture and executable files before launch. Directory `/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev9_probe_20261030/`; retained detached container `nga-reference-openjev9-probe`. CephFS logs, heartbeat, item receipts, terminal and exact launch survive disconnection. Require all three receipts, valid typed output, finite logits/probabilities, terminal and wrapper rc 0 plus container exit. Report per-chip throughput with one chip and reserved memory. No test inference or training occurs in this probe. Completion allows preparing public test inference, not claiming a benchmark result.

## Results

2026-10-30 completed: retained container `7ccbd58ec682e37e3bc1a8db6be85cf7635494d88933ec4de0801653b64d6ab4` exited 0; PROBE_COMPLETE and wrapper DONE agree. All three typed fixtures ran twice. Independent verification checked receipt payload/input identity, finite logits and probabilities, softmax arithmetic (within 1e-6 for the float32 softmax output), and all 88 frozen files. `PROBE_VERIFICATION.json` records `VERIFIED_SYNTHETIC_ONLY`.

Load time 10.9539 s; repeat throughput 2.47765 / 2.46894 / 2.46632 questions/s/chip, one chip, reserved memory 17.58789 GiB. Repeat probability deltas are zero for these three fixtures only. No benchmark or training result is inferred. E18 CPU length preflight was launched after the successful probe; chip 1 was subsequently transferred under the allocation lock to E18 after successful probe and CPU preflight containers had exited.

## Verdict

Native synthetic compatibility and measured resource use established. Full public-test inference and independent metric audit remain required; no Astra approval or training benefit claimed.
