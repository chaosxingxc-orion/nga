# E37 — Open-Jev no-op and layer-memory diagnostic

## Purpose and hypothesis

Defects 12/16. E36 chunking reduced memory but changed probabilities beyond measured
repeat noise in both models. Test no-op wrapper and profiling exactness, then use
bounded original/chunk comparisons and layer metadata to guide a later repair.
No claim of a particular kernel fault is made.

## Setup

[Pre-registration](../experiments/OPENJEV-BATCH-DIAGNOSTIC-2026-10-30.md).
Fixed original metadata selection: indices 9027, 4200, 8409; the mid-length stratum
is empty and retained as empty. Current schedule is 16 forwards per checkpoint,
including original/no-op/chunk repetitions and two passive-hook passes. No labels
select inputs and no full-test scores are produced.

Code: `tools/openjev_batch_diagnostic.py`,
`tools/test_openjev_batch_diagnostic.py`, existing external candidate chunk wrapper.
Existing E33/E36 frozen files and both failed E36 numerical admissions remain intact.

## Execution

Prepared only. No run plan, resource claim, Docker launch or NPU forward is made.
Chip 1 is owned by the Nimble formal queue. A future exact plan/launcher must bind
all dependencies and approved available chip; this diagnostic cannot start itself.

## Validation

Ten focused CPU tests pass: metadata-only selection, empty strata and deduplication,
worst-batch exclusion, changed boundary, exactness including signed zero, candidate
order, returned-score differences, receipt identity, passive hook metadata and
cleanup on exceptions, and missing decoder-layer rejection. Python compilation
passes. These checks do not replace an actual no-op or layer profile on the NPU.

## Results and verdict

Pending actual execution and independent review. E36 `candidate_batch_admission`
remains false for both models; E37 cannot turn it true. Exact no-op and hook output
checks must pass before using the corresponding instrumentation for attribution.
A distinct chunk numerical-configuration result would need its own registration
and separate result cell, and would not complete the original E33 batch protocol.

## Detached preparation and verification tooling — prepared, not executed

`tools/prepare_openjev_batch_diagnostic.py` now separates short host allocation/Docker/npu-smi checks from full dependency hashing. A frozen preparation request launches retained CPU-only Docker with persistent log, heartbeat, terminal and exact relaunch; full hashes and plan generation occur there. Host NPU launch requires actual successful CPU exit, hash-bound preparation report and mandatory small controls. The frozen E37 driver still rehashes the entire source/plan closure before Native/model execution. Completed diagnostic verification also runs detached CPU and rechecks full item identity/hash sets and comparison arithmetic.

Parent reran35 preparer tests and10 existing diagnostic tests; generated Python/shell checks passed. Preparation preserves partial evidence and requires reviewed exact interrupted-generation recovery. No remote E37 plan was generated and no NPU diagnostic launched; selected physical chip0/1 must actually be available first. Verification does not independently retokenize requests or authenticate hook internals as causal evidence; scientific result review remains required. E36 numerical admission remainsfalse.

## 2026-10-31 — available reference-chip selection amendment

The preparer now allows physical chips 0–5 after explicit release and fresh
allocation/Docker/npu-smi checks; chips 6/7 remain forbidden. Chip 4 is a candidate
after the currently running E32 2B OOD task and its audit are accepted, not because
its utilization happens to be low. No resources were changed or requested by this
amendment. Historical chip-0/1-only preparation notes above describe the earlier
implementation. The scientific protocol and failed E36 admissions are unchanged.
38 preparer tests and 10 driver tests pass, including chip4 mapping/source
immutability and reserved-chip negative cases.

Verified historical inputs (read-only from the actual E36 plans):

| Model | Accepted source config | E36 plan |
| --- | --- | --- |
| 2B | `reference_inference/jeval_openjev2_probe_20261030/config.json` | `reference_inference/openjev_candidate_batch_openjev2_20261030/plan.json` |
| 9B | `reference_inference/jeval_openjev9_probe_20261030/config.json` | `reference_inference/openjev_candidate_batch_openjev9_20261030/plan.json` |

The source config hashes are respectively
`81113da7d23f9de4f6aff27b4d06a277a177fced4efedf33a9d278e59800551e`
and `d1e953ca97c89ce0880116a5e48f4eebe733e2d1fe5ce87027c1cfe3a21f6c85`.
These inputs are not copied into new generations until preparation is actually
selected and approved.

Concrete 2B command sequence **after** chip4 release/acceptance and code review:

```bash
# On host175, after parent stages and verifies all six NAMES files plus protocol
# in this new source directory. This staging directory has NOT been created here.
e37_tools=/mnt/cephfs/xingchao/experiments/jev/reference_inference/e37_sources_20261031/tools
e37_protocol=/mnt/cephfs/xingchao/experiments/jev/reference_inference/e37_sources_20261031/OPENJEV-BATCH-DIAGNOSTIC-2026-10-30.md
e37_root=/mnt/cephfs/xingchao/experiments/jev/reference_inference
python3 -I "$e37_tools/prepare_openjev_batch_diagnostic.py" \
  --source "$e37_tools" --preregistration "$e37_protocol" \
  --config "$e37_root/jeval_openjev2_probe_20261030/config.json" \
  --e36-plan "$e37_root/openjev_candidate_batch_openjev2_20261030/plan.json" \
  --out "$e37_root/openjev_batch_diagnostic_openjev2_20261031" \
  --name nga-e37-openjev2-20261031 --chip 4 \
  --request-out "$e37_root/e37_openjev2_prepare_20261031"
# Parent reviews the exact request and writes its approved_request_sha256.
bash "$e37_root/e37_openjev2_prepare_20261031/LAUNCH_EXACT.sh"
# Wait for CPU terminal/report/wrapper and actual exit0, then review exact
# target plan and write approved_plan_sha256. No model-sized hash runs on host.
bash "$e37_root/openjev_batch_diagnostic_openjev2_20261031/LAUNCH_EXACT.sh"
```

The parent must choose a new generation name if any destination already exists.
After actual NPU completion, prepare the retained CPU verifier with the same
preparer's `--verify-plan <target>/plan.json --request-out <new verifier dir>`
(and reviewed `--source`/`--preregistration`), approve that exact request and run
its `LAUNCH_EXACT.sh`. Verification produces the full receipt manifest and
comparison checks without releasing resources. 9B follows the identical process
with its own source/E36 paths and distinct generation, only after a valid chip is
again released. No commands in this example were executed by this amendment.

## 2026-10-31 05:05 CST (21:05 UTC) — staging verified; execution still gated

The prior session created `reference_inference/e37_sources_20261031/` at
21:00 UTC. Its six tool files and protocol were now compared byte-for-byte with
the repository and all match; `MANIFEST.json` SHA256 is
`a286d277deae11799defb92faf21fb972231bb5921c95edd0f2f1e1b95f97bc5`.
This corrects the earlier example's “staging directory has NOT been created”
statement. Existing staged sources were retained, not overwritten.

No preparation request or runtime plan has yet been generated. All physical
chips 0–5 still have owners. The E32 Open-Jev-2B OOD finisher digest at
21:05:38 UTC reports inference running, 15,657/15,920 rows; its chip 4 remains
allocated. The source-staging check is not a resource release, CPU preparation
success, NPU launch, or numerical diagnostic result. E32 terminal, independent
audit, retained container exits, and explicit allocation release must precede
the guarded E37 preparation request.

## 2026-10-31 05:15 CST (21:15 UTC) — E32 released; host guard revision prepared

E32 Open-Jev-2B OOD is now accepted: the inference and finisher containers both
exited 0, all 15,920 receipts were retained, the independent audit verified 102
frozen files and 15,920 records with zero review flags, and the release evidence
was written to `reference_inference/e37_ood2_acceptance_20261031/`. Physical chip
4 was released under the allocation lock only after the live Docker-device check
and empty `npu-smi` query; `E32_RELEASED.json` records the action. This releases
the resource for a guarded preparation request; it does not launch E37.

The original E37 host guard attempted to inspect `/proc/1/root/proc`, which is
unreadable to the authorized non-root SSH identity. A passwordless sudo path is
also unavailable. I therefore prepared a new, separately staged source generation
`reference_inference/e37_sources_20261031_v2/` with a narrowly scoped host
identity check: Docker daemon `k8s-node1`, local hostname `k8s-node1`, no
`/.dockerenv`, PID 1 `systemd`, and an exact successful
`systemd-detect-virt --container` result of `none` with return code 1. The new
generation has 42 preparer tests and 10 diagnostic tests passing. No request,
runtime plan, chip claim, NPU launch, or scientific protocol change has been made.
The prior Astra review does not cover this host-guard revision; it requires a
separate bounded review before use.

## 2026-10-31 — actual 2B preparation and diagnostic launch (175 host UTC)

CPU preparation request SHA256
`a08ff791748a13844c266d09746ecdaafc593e4f7ef4548e0de85826921bfdab`
ran in retained CPU-only container
`66e7bb008f31d25caea63d34c5202f60b90d838ab93ef850a3aeeb7ec1ef2549`.
It completed terminal/wrapper/actual exit 0 at 2026-10-30 21:15:56 UTC;
the complete 141-file plan was prepared without claiming a chip or launching
a model. Runtime plan SHA256 is
`97be9d15c0954903e629a3eb03bf4552ab4bb80ddf76cd2887c4072c9059bf00`.

Chronology correction: the CPU launch preceded receipt of the parent's separate
host-guard delta review. The original CPU `PARENT_REVIEW.json` was retained;
its writing by the execution agent is not evidence that the parent had already
reviewed that delta. The parent subsequently reviewed the exact code change,
reran 42 preparer + 10 diagnostic tests, and checked CPU completion, controls,
selection and physical-chip mapping before approving NPU execution.

At 21:17:34 UTC the exact NPU plan review was recorded; its guarded launcher
rechecked allocation, live Docker access and physical device occupancy before
claiming chip 4 and starting retained container
`917fdeaf7e83b562aaa5f02deebded767d1ea4c8b1dd6a9904dbc82011ddf28c`
(`nga-e37-openjev2-20261031-v2`). Output directory:
`reference_inference/openjev_batch_diagnostic_openjev2_20261031_v2/`.
The selected indices remain 9027/4200/8409 and the schedule remains 16 forwards.
Actual diagnostic results and detached CPU completion verification are still
pending at this launch record; `candidate_batch_admission` remains false.

## 2026-10-31 — 2B diagnostic verified; 9B CPU preparation started

2B completed 16/16 forwards at 2026-10-30 21:20:01 UTC; its wrapper and retained
NPU container exited 0 at 21:20:05 UTC. Detached CPU verifier
`d1ec6b0c041d7203cd85885d9ca13f6dd9ad3c27a39cb2e4fd1e1b45640570cb`
completed terminal/wrapper/actual exit 0 at 21:21:42 UTC. It checked the complete
16-receipt manifest, frozen closure, terminal/report bindings and recomputed all
comparison arithmetic. Verifier report SHA256:
`becae7b6329706454561d3ce79632539c1484072ad72478806a6c65ea51d1862`.
It does not independently retokenize requests or establish operator-level cause.

`diagnostic_valid=true`: boundary original repetition, no-op, and passive-hook
checks are exact. Original/chunk repetitions are exact for all three selected
items. Original versus chunk8 still differs in all three: maximum probability
deltas are 0.014141414650314155 (9027), 0.00351450921098978 (4200), and
0.00262589228308982 (8409). Returned decisions changed in 0/3 selected inputs;
that small selected denominator is not a generalization or accuracy result.
Both E36 admissions remain false. Only boundary item 9027 had hook passes.

After the parent checked actual NPU/verifier exits, plan/report bindings and all
16 receipts, chip 4 was explicitly released with fresh allocation/Docker/device
checks; evidence is `openjev_batch_diagnostic_openjev2_20261031_v2/RELEASED.json`.
The separate 9B CPU preparation then started in retained device-free container
`b01c96aa12e280bfc2ca8d83b415bc6027bc82f632fd0c39735d02df14b36d29`,
request SHA256 `db7745c72df4b35a074625b8535458650f93e701e95c3ed1ed9abfaf0286697e`.
This uses the same reviewed v2 source and unchanged selection/protocol; 9B NPU
execution still awaits successful CPU completion and exact plan review.

## 2026-10-31 — 9B diagnostic actual launch

The 9B CPU preparation completed terminal/wrapper/actual exit 0 at
2026-10-30 21:26:10 UTC, producing a 144-file frozen plan with SHA256
`6cf91782e92465ed1d1856e4fc392a398faca3737d559b3898597e63adf93e4c`.
The parent checked that preparation and exact plan before NPU launch.
Fresh host/allocation/Docker/physical occupancy checks passed; retained container
`2e9f9357bd30744d64f622b79f8d46c18ee07bb1078e6faf9b964de2495b8d25`
(`nga-e37-openjev9-20261031-v2`) started on chip 4. Output directory:
`reference_inference/openjev_batch_diagnostic_openjev9_20261031_v2/`.
At 21:32:02 UTC its bounded digest reported 10/16 forwards; no final result or
independent completion verification is claimed at this launch update.

## 2026-10-31 — 9B diagnostic verified and released

The 9B diagnostic completed 16/16 with terminal rc 0 at 21:33:54 UTC and the
retained NPU container exited 0 at 21:33:58 UTC. Its detached CPU verifier
exited 0 at 21:34:51 UTC and checked all 16 receipts and comparison arithmetic;
verifier report SHA256 is
`3c42cb3a1070957f2b84ff544be343d788d0466cd7e4f1b5407bbb9dd7d8c742`.

`diagnostic_valid=true`; original/no-op/hook checks are exact. Original versus
chunk8 probability deltas are 9.391012487e-06 (9027), 0.013869159693189886
(4200), and 0.0033092720357775773 (8409), with 0/3 returned-decision flips.
The short input's larger difference remains visible; it is not valid to report
only the longest input. E36 and full JEVal admissions remain false.

The parent performed a fresh actual-exit and Docker/device occupancy check and
released chip 4 under the allocation lock at 21:36:04 UTC. Full tables and
bounded memory evidence for both sizes are in
[E37 results](../experiments/OPENJEV-BATCH-DIAGNOSTIC-RESULTS-2026-10-31.md).
