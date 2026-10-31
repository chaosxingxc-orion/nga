# E41 — Full-shape lifetime extension

Status: preparation before NPU execution. Round: diagnostic after E40. Pre-registration: `experiments/OPENJEV-LIFETIME-E41-2026-10-31.md`.

## Purpose and hypothesis

Defects 12/16: preserve complete native outputs while reducing dead-reference memory on 9B short input 4200 and 2B longer input 8409. All four paths and two repeats retained, fresh originals. Exact outputs and full candidate identities discriminate against skipping work. No full JEVal or training-benefit claim.

## Setup

Fixed image `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`; physical chip 4 for 9B/4200, chip 1 for 2B/8409, only after exact review and live resource checks. E40 v3 immutable sources are transformed into separate E41 copies. Each plan requires new independent acceptance.

Before NPU, a retained device-free CPU container reconstructs the 2B/8409 input under the sanitized image Python/CANN environment. No model weight loading or NPU forward occurs. Terminal and artifacts are retained under `reference_inference/e41_input_openjev2_long_20261031_v1`. This setup is registered before launching that preparation.

## Results

Pending preparation and review; no NPU run or metric result.

## Verdict

Pending. E40 outcomes do not establish these new shapes' equivalence or memory effects.

## 2026-10-31 preparation evidence

The retained CPU input preparation actually exited 0 at 06:22:11 UTC, container `5afa7a60d1ef326bc5df68e35912c0c152390a29fb5e9e45aeb7a03c8abeeaeb`, no devices. It reconstructed 2B input 8409 as 24×3480 and wrote the exact token/mask/candidate identity. 9B short identity is copied from its accepted E38 plan. Eleven bounded derivation/protocol/runtime-guard tests passed; all generated local source hashes and syntax match the frozen plans.

Two v2 plans are prepared, not approved or launched. Their paths/hashes are recorded in `experiments/E41-LIFETIME-PREPARATION-2026-10-31.json`. The old unlaunched v1 plans retain a local-workspace generator dependency; v2 puts that source inside each frozen directory. No frozen E40 file was edited. New exact-code/plan review and separate E41 release pins remain required.
