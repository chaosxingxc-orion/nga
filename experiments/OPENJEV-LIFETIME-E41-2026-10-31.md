# E41: bounded full-shape lifetime extension

Status: pre-registered engineering preparation, no NPU approval. This is separate from E40 and does not amend its frozen runs or grant JEVal admission. Defects 12/16.

## Purpose and discrimination

Test whether the same Delete-only L1/L2/L1L2 arithmetic remains exact and reduces memory on two previously measured native shapes. The unconstrained minimum skips work; its discrimination counterpart requires complete candidate/token/mask identities, all native logits/probabilities/wire fields, both repeats and a fresh original baseline. No candidate removal or denominator change is allowed.

## Exact finite cases

| Case | Model | Metadata-selected input | Full GDN shape | GDN modules | Physical chip |
| --- | --- | --- | --- | --- | --- |
| openjev9_short | Open-Jev-9B | 4200 | 15×186×32×128 | 24 | 4 |
| openjev2_long | Open-Jev-2B | 8409 | 24×3480×16×128 | 18 | 1 |

The input identities were selected by E37 metadata, not gold or favorable predictions. Each case runs original, L1, L2, L1L2 in that order, twice each: eight forwards, fresh original included. All four variants remain even though E40 L2 did not reduce memory. Raw source, model, temperature, candidate order, global padding, backend, precision and arithmetic remain fixed. Only dead-reference deletion differs.

E37 historical original reserved peaks were 17.572265625 GiB for 9B/4200 and 14.142578125 GiB for 2B/8409. These justify preparation of the same shapes, not direct admission. Require 8 GiB free before each forward, stop after any reserved peak above 48 GiB, preserve failed observation and generation, no retry of uncertain forward. These are stop rules, not hardware caps. No 9B/9027 or maximum 255-candidate shape is authorized.

## Measurements and acceptance

Complete serialized predictions must match exactly across repeats and each candidate against corresponding original, including signed-zero semantics. Retain every mismatch, per-chip elapsed time, questions/s, tokens/s, baseline/peak allocated and reserved, chip count. All paths include the same passive token guard and one common core guard. First-call compilation/warmup and fixed order prevent general speedup claims from two repeats; timing remains diagnostic. No stage-liveness claim is made.

The driver derives from exact E40 v3 bytes through a finite, recorded source transformation. The generated sources and all replacements are independently reviewed as executable code; source derivation does not inherit approval. Frozen E40 artifacts are untouched. `DERIVATION.json` records original and derived hashes. Protocol identities reject cross-case inputs/models/chips.

## Preparation and execution

Before NPU: derive generated source, reconstruct token/mask identities in retained fixed-image device-free CPU preparation, freeze the exact plan and dependency closure, then obtain actual Astra code/plan review and exact parent/independent approval. Actual launch checks physical host, devices and cooperative ownership. Long runs are detached retained Docker with Ceph logs, heartbeat, terminal, wrapper EXIT, relaunch command and per-item attempt/receipt records. Same-start prefix recovery only; uncertain generations fail closed.

Independent CPU verification reuses the separately reviewed E40 request launcher against each plan's derived verifier, after new exact request review. Release requires a separate exact E41 chip-bound reviewed transaction; E40's chip-1/v3 release pin cannot release these plans. A complete diagnostic does not grant JEVal admission or establish trained-model/business gain.

## CPU input preparation preregistration

Device-free fixed-image preparation derives only 8409 request/candidate/token/mask identity from the same frozen test and native tokenizer. It loads no checkpoint weights and uses no NPU. It validates inherited dependencies before native imports. Retained output includes source hashes, request output hash, exit code and container identity. 9B/4200 identity is copied byte-for-byte from its accepted E38 plan and revalidated by the runtime.
