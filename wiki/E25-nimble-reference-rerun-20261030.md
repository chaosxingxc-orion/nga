# E25 — Original Nimble reference rerun after dependency-freeze failure

Pre-registration: [complete dependency rerun](../experiments/NIMBLE-REFERENCE-RERUN-2026-10-30.md), written before launch.

## Purpose and hypothesis

Defects 12/16: close the missing base `config.json` provenance in E19 by a fresh
fully frozen run, preserving the failed original evidence. Same model and 1,884
inputs, no result-driven protocol changes or training. Valid/corrupt artifact
counterparts are required; memorizing labels would be a degenerate optimum, so
this fixed benchmark reproduction does not establish unseen generalization.

## Setup

Exactly E19 native original adapter, base, prompts, populations, precision and
metrics. New output `reference_inference/nimble_public_test_20261030_v2/`, inference
container `nga-reference-nimble-public-test-v2`, 175 chip 3. CPU observer output
`nimble_public_test_20261030_v2_finish/`, container
`nga-reference-nimble-public-test-v2-finish`. No original receipts are copied.

## Results

Preparation. Parent reran 21 independent verifier tests and 3 actual finisher chain
tests successfully. Dependency closure and launch evidence are pending.

## Verdict

Pending inference and independent audit; no full accepted score, Astra approval or
training benefit claimed. E19/E21 failure remains retained, not silently amended.

2026-10-30 16:43 UTC execution update: pre-launch closure independently derived
150 required dependency paths, all present in the 152-file frozen manifest.
The previously missing base `config.json` is included. Twelve corrected-driver
receipt tests passed in addition to the parent-verified 21 + 3 audit tests.
Chip 3 was transferred under the allocation lock only after validating E19's
actual container identity/exited-0 and successful inference terminal/wrapper,
retaining its failed audit as the reason for the new run. Live Docker maps showed
no chip 3 conflict. No earlier receipt was reused.

New inference container ID:
`ddffa765ef3174607740c3cd902568470ba951eaf1e8f292dfb3c52d7849baa1`.
CPU independent observer ID:
`1be81b414f70335da5b1243f78c1fd5c54ac2ba5c066f66c714c74114190b7e0`.
Both were observed running after launch. Nine observer inputs are frozen,
including the inference config and launch receipt. `DEPENDENCY_CLOSURE.json`,
`TRANSFER_EVIDENCE.json` and both `LAUNCH_RECEIPT.json` files bind the preparation
and launch evidence. Full inference and independent metric acceptance remain
pending; this launch does not repair or supersede the original failed evidence.

2026-10-30 17:07 UTC completion update: E25 completed all 1,884 rows at 17:05:53;
inference wrapper rc 0 at 17:05:57, independent observer wrapper rc 0 at 17:06:38.
Both retained containers were inspected exited/0 with the exact IDs above and the
frozen image. Independent audit is VERIFIED_SCOPED: 152 frozen / 150 required
files, all 1,884 records and seven manifest data hashes/ordered IDs checked, no
current review flags. Independent follow-up rechecked all 152 inference and 9
observer hashes plus terminal/output bindings. No allocation was released here.

| Subset | Correct / n | Accuracy |
| --- | ---: | ---: |
| massive-en-US | 304 / 350 | .868571429 |
| massive-de-DE | 294 / 350 | .840000000 |
| paws | 207 / 250 | .828000000 |
| civil_comments | 210 / 300 | .700000000 |
| aegis2 | 204 / 250 | .816000000 |
| summeval-relevance | 117 / 240 | .487500000 |
| summeval-consistency | 108 / 144 | .750000000 |

Full NLL, multiclass/binary Brier, ECE10, score MAE, distribution metrics and
published rounded-value comparisons are in [the reference result report](../experiments/NIMBLE-REFERENCE-RESULTS-2026-10-30.md).
Report SHA256 `8d54869ee54f566ffc1b5c7aa7813ea97f986d6d52351a27d947cc7f7f7b6e2c`;
audit SHA256 `0a7476130ee3d55c1fb661e2bb8d127cc240ba1e242c6014c024f2e372a8929b`.
Scoped acceptance does not establish prompt retokenization parity, unseen
generalization, same-hardware reproduction, family-complete metrics, new training
benefit or substantive Astra approval. Published per-row predictions were not
available, so the different aggregates cannot identify individual flipped records.
E19/E21 failed evidence remains unchanged.
