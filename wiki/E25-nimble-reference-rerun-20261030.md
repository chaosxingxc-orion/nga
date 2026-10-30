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
