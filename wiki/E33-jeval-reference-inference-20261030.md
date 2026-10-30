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

## Kev4 v2 probe recovery preparation

The old Kev4 formal launcher rejected the Docker-created container before start,
receipt or chip claim. The retained container
`05090669e8b9866d6747b3c1f2499daa6c4f1ee4abaef2fed323f2eddea13543`
remains `created`: exact sorted mount strings match and devices match; only the
mount-list order differs. `LAUNCH_DIAGNOSIS.json` records this bounded diagnosis.
Old frozen files and the failed container are preserved.

A separate Kev4 v2 probe uses the already fixed frozen Kev9 v2 source, unchanged
Kev4 native dependencies and E31 eligibility. Planned chip 3 must remain explicitly
free and have no live mapping before launch. The probe checks the same three
synthetic types and longest eligible input twice; formal inference still requires
separate probe acceptance. CPU-only preparation runs detached in
`nga-jeval-kev4-v2-prepare`, with persistent log, heartbeat, terminal and exact
relaunch under `reference_inference/jeval_kev4_v2_prepare_20261030`.

Kev4 v2 preparation completed 1/1 at 19:08:46 UTC; the retained CPU preparation
container exited 0. The new probe configuration SHA256 is
`d42acbeef917c5d736a84b70cb6d23efa67e4b9aeec9fbc9de17b7c237095776`,
with 82 frozen files. Source scripts match the accepted fixed v2 source byte for
byte; runtime matches, and native dependency paths/hash sets match E31.
After full frozen-file checks and locked resource verification, retained container
`6b6319833385c7c59eb850b5fb4edf3efd6b762c4e656fd9e51aca4403ff6eb5`
actually launched on chip 3. Probe completion and separate formal acceptance remain
pending; no JEVal score follows from this launch.

## Serial remaining-family probe acceptance and execution

The parent delegated engineering acceptance of Open-Jev2 and serial execution of
Open-Jev9 then Nimble probes on chip 1. The acceptance script is retained outside
model/data directories at
`reference_inference/nga_probe_accept_sequence_20261030.py`.
It checks full frozen hashes, exact source/runtime/native E31 closure, actual
Docker/resource/exit/wrapper binding, synthetic and longest-eligible identity,
repeated probability drift, durations, reserved memory and consumed token hashes.
Token provenance is not independent retokenization. The allocation release is
locked and requires the exact owner and absence of a live chip-1 mapping.
This sequence does not launch formal inference or new training.

### 19:10 UTC — Open-Jev2 probe accepted

All 97 frozen files passed hash verification; eligibility/native/runtime/source
and actual Docker/resource/exit/wrapper checks passed. Terminal 19:07:58 UTC and
wrapper 19:08:02 UTC are rc 0; retained container
`8788ccb1b776d6d3053000c91185ef898552d023ad6f0c253cad20672ba396f4` exited 0.
The three synthetic types and longest eligible index 9027 (4,096 tokens, 30
candidates) each repeated with maximum probability delta 0. Boundary timings were
9.774910/9.182082 seconds, reserved 24.052734 GiB, one chip. Boundary consumed-token
hashes match E31. `PROBE_REVIEW.json` binds config
`81113da7d23f9de4f6aff27b4d06a277a177fced4efedf33a9d278e59800551e`
and probe `d1801ca88a7124e4531f107137c6daa586bdf00397d02260acbf1ebc534f8cbe`.
Chip 1 was explicitly released under lock after actual live maps were checked.
This is engineering admission, not a JEVal full-test result or Astra approval.

Kev4 v2 probe completed at 19:10:25 UTC; wrapper 19:10:30 UTC and retained
container exit code are both 0. Config/terminal/launch/wrapper and PROBE hashes
were independently checked. PROBE SHA256:
`26cfdb82fec3d88afbc1406bcf7ff47512d99e471722d134dfce0e1ed12e9315`.
All four repeated pairs have maximum probability delta 0. The boundary index 9361
was reselected from the full eligible population (8,187 tokens, input/token hashes
matched); the two forwards took 3.353422/2.865180 seconds. Reserved memory was
27.3203125 GiB on one chip; last-probe throughput was 0.349018 questions/s/chip.
`PROBE_VERIFICATION.json` records engineering checks for parent acceptance.
No full-test receipts or formal v2 inference were emitted; chip 3 remains owned
until explicit acceptance and release.

### 19:11 UTC — Open-Jev9 probe actually started

The prepared 100-file config
`d1e953ca97c89ce0880116a5e48f4eebe733e2d1fe5ce87027c1cfe3a21f6c85`
passed full hashes, frozen v2 executable identity, runtime/native E31 closure and
single-chip specification checks. The guarded launcher acquired chip 1 and started
retained container `16cc0baadea08a6421481662f142c585fb1abfff44fd08ad10bac4ebaf87e8e1`.
Actual state was running at 19:11:12 UTC. Probe result remains pending.

After the parent requested acceptance, hash-bound `PROBE_REVIEW.json` was written.
Chip 3 was explicitly released under the allocation lock after rechecking the
actual retained exit, current ownership and all live device mappings. Formal v2
inference remains a separate preparation and launch.

## 19:13 UTC — corrected Kev4 formal inference actually started

After parent rechecked v2 probe terminal/output hashes, engineering verification,
actual retained exit 0 and explicit chip-3 release, formal v2 was prepared from
that exact frozen source. Config SHA256
`ca320e1d174d6349042962151af1807fb028f26eb172ed98873cf24f50de2d71`, 85 files,
run `reference_inference/jeval_kev4_inference_20261030_v2`.
Executable/runtime/native identity matched the accepted probe; guarded launch
rehashed frozen files and checked locked live resources. Retained inference
`2ccdf964c4c22d9831b0baec50895f4fd38065b18e88c8f28f427c245975e906`
and independent finisher
`5260f9111d02bab3937ee08299fa03178c25e7afb37857e260d70859be4e8ccb`
were both actually running. The inference digest at 19:13:25 UTC was loading.
Old formal-v1 created container and failure evidence remain untouched.
No final JEVal score or training benefit is claimed.

### 19:14 UTC — Open-Jev9 probe accepted

Terminal 19:13:10 UTC, wrapper 19:13:13 UTC and retained actual container all
completed with exit 0. All 100 frozen files, native/runtime/E31 and launch
bindings passed. `PROBE_REVIEW.json` binds the prepared config and probe SHA256
`c4cf4018c659621b63599142bf0367a91cb40a16e6e33f870a9dd62aaac79af7`.
All four repeated groups had maximum probability delta 0. Longest eligible
index 9027 (4,096 tokens, 30 candidates) took 27.429424/26.640149 seconds,
reserved 56.728516 GiB on one chip; consumed-token hashes match E31.
Chip 1 was explicitly released under lock after actual live-map checks.
Nimble is next in the pre-registered serial probe sequence. This acceptance is
limited to the observed probe workload; it does not establish all JEVal shapes
fit memory or produce a full-test score.

### 19:15 UTC — Nimble probe actually started

The 148-file config
`9cc49322c7a515e1e6fec56b4f34d4d1b1b404c089166589ee142ebe3ed17997`
passed full hashes, v2 executable identity, E31 native closure, runtime and resource
specification checks. Base and adapter revision both match
`c202236235762e1c871ad0ccb60c8ee5ba337b9a`; native temperature remains 1.
The guarded launcher acquired chip 1 and started retained container
`9a13bfadfb65e6bfc8a36adf80231082de3cd989ed20a95a741f43ba55fa653b`
at 19:15:47 UTC. Its longest eligible index is 6831, 2,046 tokens.
The actual result remains pending; no formal inference was launched by this sequence.

### 19:18 UTC — Nimble probe accepted; remaining formal preparation

Nimble probe terminal 19:17:22 UTC and retained actual container exit 0 were
verified after the earlier terminal-before-exit observation. Wrapper chronology,
config/PROBE/output hashes, all 148 frozen files, v2 source/runtime/native E31
closure and actual resource binding passed. `PROBE_REVIEW.json` binds config
`9cc49322c7a515e1e6fec56b4f34d4d1b1b404c089166589ee142ebe3ed17997`
and probe `fa28824157c5595fc31678845b54798b9d92d3ade2049e1d30fa436cc79f1a47`.
All four repeated groups had maximum probability delta 0; longest eligible
index 6831 (2,046 tokens) took 0.873322/0.821468 seconds, reserved 18.791016 GiB
on one chip. Consumed token hashes match E31; this is provenance verification,
not independent retokenization. Chip 1 was explicitly released under lock after
checking exact ownership and all actual live device mappings.

CPU-only detached preparation `nga-jeval-remaining-formal-prepare`, container
`a932d84712e65f3669273235f8ab4bc4a1c58284acf3b9ec85ff3cbcad682667`, prepares
Open-Jev2/9 and Nimble formal configurations from their own accepted frozen probes,
all planned on chip 1 for serial execution. No formal inference or resource claim
is made by this preparation. Persistent status/heartbeat/terminal and exact launch
and resume commands are under `reference_inference/jeval_remaining_formal_prepare_20261030`.

Parent review subsequently identified a separate Open-Jev memory-admission gap:
the accepted longest-token boundary has 30 candidates at 4,096 padded tokens,
whereas eligible rows 633/637 have 255 candidates at 2,156 tokens (549,780 padded
tokens versus 122,880). The native implementation batches all candidates together.
Thus Open-Jev formal configurations remain prepared only; the existing probe does
not establish that the maximum padded workload fits. Additional admission or a
numerically verified batching change is required before those formal launches.
Frozen configurations and probe evidence remain unchanged. This specific batch
workload finding does not apply to Nimble's single-sequence interface.

### 19:21 UTC — remaining formal configurations prepared, not launched

The CPU preparation completed 3/3 at 19:21:51 UTC, retained Docker exited 0,
with no NPU devices. Full frozen hashes and exact accepted-probe executable,
runtime/native closure were checked for each new configuration. Preparation audit
SHA256: `6259fb89d0f10037891385149342c5f01c5bd04611afa21b9730027ff97525c4`.
All are planned on chip 1, with no formal launch or chip claim by this preparer.

| Model | Config SHA256 | Frozen files |
| --- | --- | ---: |
| Open-Jev2 | `07c820002e4663495a60c7d69b5b9798ffe12e5afb83bb0177003264e2cac11f` | 100 |
| Open-Jev9 | `ca935b254e9e7c22abba0a3ff81494365b39f32320c01e46244ea30afa933f7c` | 103 |
| Nimble | `b310b6271a7174f7efad1ba435fa2ad9ac53fecab3aec0f1944ee2f5fd703156` | 151 |

Directories: `reference_inference/jeval_{openjev2,openjev9,nimble}_inference_20261030`.
Open-Jev remains blocked on the newly identified padded-workload memory admission,
not on preparation. Nimble is available for parent review and separate launch.
