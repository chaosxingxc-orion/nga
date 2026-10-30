# E33 — JEVal actual reference inference

## Purpose and hypothesis

Defects 12/16: produce actual native reference predictions on the exact published
JEVal population while preserving eligibility failures in complete denominators.
Degenerate filtered-population scoring is rejected by identity/coverage checks;
gold-input invariance has candidate discrimination counterparts.

## Setup

See [pre-registration](../experiments/JEVAL-REFERENCE-INFERENCE-2026-10-30.md).
Six existing <10B checkpoints, unchanged native context and temperature, original
11,257 rows. Classification n=10,938 and score n=319; invalid handling and local
ECE/response conventions are frozen separately from the paper claims.

## Execution

Implementation preparation only. New driver supports all three native families,
actual consumed-token checks, synthetic and longest-eligible runtime probes,
item resume, raw native predictions and native-response formula scoring.
Twelve focused scoring tests cover returned-choice vs argmax, raw Brier mass, noul tie,
score original scale, invalid denominators, schema rejection and input isolation.
Four full-population synthetic-chain tests also pass (11,257 rows), including
missing receipts, changed consumed-token hashes and forged returned scores.
Together with the twelve E31 tests, 28 JEVal tests pass. Independent verifier and
guarded prepare/launch/finish implementations added.
No E33 NPU inference or checkpoint training has launched. Parent review and
implementation/chain admission remain required before launch.

## Results and verdict

Pending. E31 eligibility totals do not constitute E33 model-performance results.

## Parent-review corrections before any E33 run

Probe is now a separate mode/container: three synthetic types twice and the
metadata-selected longest eligible input twice, then a terminal without a test
loop. Formal inference requires explicit probe config/report hash approval and
identical native/executable dependencies. Required report+probe terminal outputs,
probe population/timing/drift checks, score legend/confidence reconstruction,
checkpoint temperature/runtime binding, exclusive finisher lock and refusal to
overwrite prior evidence were added. Fourteen scoring/preservation tests and
nine complete-population audit-chain tests pass; these are not real model evidence.

Kev-0.8B probe prepared (not launched):
`reference_inference/jeval_kev08_probe_20261030/config.json`,
SHA256 `83406e1479fb2c932e63809644cec02a1409a4421f6f3cbee9b530a905c6e652`,
76 frozen files, planned chip 0. Parent review is pending; no resource claimed.
Formal inference remains a separate configuration after actual probe acceptance.

## 18:47 UTC actual Kev-0.8B probe accepted

Parent reviewed the final source snapshots and reran 14 metric/preservation and
9 full-population chain tests. Probe config83406e1479fb2c932e63809644cec02a1409a4421f6f3cbee9b530a905c6e652
actually launched retained container `0c136bcf6a966a06c52e7c62ec599f3370c7163f7c8567d85f3d0c34906a27cd`
on chip0. Terminal18:45:03UTC and wrapper18:45:07UTC, actualDocker exited0.
All three synthetic types repeated twice with zero probability drift; longest
eligible index9361 has8187tokens, times2.182651/1.812264s, zero drift, reserved
8.736328GiB, one chip. No full-test receipts were emitted. Parent checked exact
boundary selection, terminal/config/report hashes and actual retained exit.
PROBE SHA256 `3c283c430a514590bd1d475891c79d64942e6579edd468d871cb3a92eceb011d`.
A hash-bound PROBE_REVIEW records engineering acceptance; chip0 was explicitly
released underlock. Formal inference is being prepared from the exact frozen
probe source rather than changing implementation after probe. No model score yet.

## 18:49 UTC — actual Kev-0.8B formal inference

Formal configuration `e1c0886040fd98dea82f4a8ce443c82742fc1f7b676e0770f4f8d4dfaf39cb46`
freezes79files and binds the accepted separate probe. Parent verified exact native
checkpoint/runtime/eligibility and executable identity before launch. Retained
NPU container `45dec3dc8f1bf886f53f443547c90aefb1fc28a98f0d204d8a04a87044be6af3`
actually launched onchip0; detachedCPU finisher
`5862f47739814fd64fb262e92892b53fc204200effe25bf5fafcbd18634181ed`.
Both actual containers were running; first digest was model loading.
Directory `reference_inference/jeval_kev08_inference_20261030/` and `_finish/`.
Full11257coverage and final metric acceptance remain pending.

## 18:52 UTC — 4B probe completed; 9B launch check preserved

Kev4 probe config `786a5b329748deeeeefae54a918973ed4e84485715ac435c29a5f91e4fb38ed7`,
container `bd34062c614d9f9dcdeff9ff87315bc813bea43d5dfe1aae5ba692a1511f8fa6`,
actual exited0, terminal18:50:13UTC/wrapper18:50:18UTC. Longest8187tokens
took3.414650/2.883803s, reserved27.320312GiB,1chip; all four probe pairs zero drift.
Probe reportSHA `1532d540bad4d0c39582939e68345d1fd58f43406944ff60903c9fcdefd765fd`.
Formal4B not launched yet.

Kev9 probe config `33b4b6e9fba4cca364f0da1a65bbb082ce019f2a77b93cc0e1b237d8e5f3a91f`
failed launcher binding after Docker create, before receipt/start/chip claim:
Docker reordered identical Binds arrays. Container
`5a35ddcb4e5384941b02856b498d1f1f3478fcf26b28bdd49053ab87f8ed5367` remains
created and original frozen files remain untouched. `LAUNCH_FAILURE.json`
records exact lists and cause. Future generation compares sorted exact mount
strings and full device triples, preserving paths/options/multiplicity.
This was a launcher false rejection, not a model forward failure.

## 18:56 UTC — corrected Kev9 probe actually running

New v2 configuration `aefba9ec015691d03125e3b75d117fda6ad2a7b7a9cc180285227e3a0742624d`
freezes80files; inference code remains byte-identical to the reviewed0.8B probe.
Only future launch/finish resource-order checking and explicit generation support
changed. Four negative mapping tests pass. Parent approved and launched retained
`nga-jeval-kev9-probe-v2`, ID
`a408eff9da038857d001a9886287134d80caea353ee0aee43b79228d115277b1`,
chip5, actual running; digest18:55:30UTC model loading. Failed v1 created container
and LAUNCH_FAILURE remain untouched. No9B fullJEVal inference yet.

## 19:03 UTC — Kev4 and Kev9 formal configurations prepared

Both separate probes have terminal and retained-container exit 0, approved
config/report hashes and four repeated groups with zero measured drift. Kev9 v2
longest-eligible 8,187-token forwards took 4.048164/3.696138 seconds, with
41.484375 GiB reserved on one chip. Probe report SHA256:
`4a41fcf11f2c51decef92eac9bb293fecab079ccc597a373e5115d2657aefea5`.
Chips 3 and 5 were explicitly released under the allocation lock after probe
acceptance; actual live container mappings were checked again before preparation.

Formal configurations are prepared, not launched:

| Model | Run directory under `reference_inference/` | Config SHA256 | Frozen files | Planned chip |
| --- | --- | --- | ---: | ---: |
| Kev4 | `jeval_kev4_inference_20261030` | `0efd92cfba52fe4c68e1c4302901e2e448b5f5e0a63692dd4e8db8f9d8868cc7` | 84 | 3 |
| Kev9 | `jeval_kev9_inference_20261030` | `1ade170ff6543894b4de210ea27ee1d282c816c83faa70defd73e7cf16134936` | 83 | 5 |

Each formal run binds its accepted probe and identical executable/native source
closure, immutable image, checkpoint, temperature and eligibility configuration.
Kev4 preserves the v1 launcher; any ordering-only launch rejection will be retained
as a failed launch rather than fixed inside its frozen files. Full-test results
and independent acceptance remain pending.

## Remaining-family probe preparation

Open-Jev 2B/9B and Nimble probe configurations were prepared from the frozen
Kev9 v2 executable source, all planned serially on chip 1. No model inference was
performed by the preparation container. `jeval_remaining_probe_prepare_20261030`
completed 3/3 with actual retained Docker exit 0 and no NPU devices; audit SHA256
`e4c230c5cfa506f8319395a9cf3acd925386262cb77b3b7f24457204f7b008f8`.
Configs under `reference_inference/jeval_{openjev2,openjev9,nimble}_probe_20261030`:

| Model | Config SHA256 | Frozen files |
| --- | --- | ---: |
| Open-Jev2 | `81113da7d23f9de4f6aff27b4d06a277a177fced4efedf33a9d278e59800551e` | 97 |
| Open-Jev9 | `d1e953ca97c89ce0880116a5e48f4eebe733e2d1fe5ce87027c1cfe3a21f6c85` | 100 |
| Nimble | `9cc49322c7a515e1e6fec56b4f34d4d1b1b404c089166589ee142ebe3ed17997` | 148 |

Chip 1 was explicitly released after rechecking E24 supplement/queue exit 0,
join plan/output hashes and actual live maps. Next execute the Open-Jev2 separate
probe; the longest eligible input has 30 candidates and max 4,096 tokens.
The 9B and Nimble probes remain prepared until serial resource acceptance.

## 19:08 UTC — additional actual execution

Parent checked executable/probe/runtime identity and approved the exact configs;
the guarded launcher rehashed frozen dependencies and checked locked resources.
Kev9 formal inference actually started on chip 5: retained container
`ec04b7dba1f656d57aa1a30040e498cbd8bdb841c000ab9bc53fa9fc4742a372`;
independent finisher `32597ee2603b8f33527fb9b42e47e363f8164eeea26dcbc09574a2474a09d295`.
Both actual states running; digest 19:07:09 UTC was model loading.
Kev4 formal launch returned rc 1 before a launch receipt; `LAUNCH_FAILURE.json`
and created container are retained. Diagnosis and a separate corrected v2 probe
are assigned; the frozen original sources are unchanged.
Open-Jev2 probe actually started on chip 1, retained container
`8788ccb1b776d6d3053000c91185ef898552d023ad6f0c253cad20672ba396f4`.
Open-Jev9 and Nimble probe configurations remain prepared only.
These are launch observations, not full-test results or Astra acceptance.
