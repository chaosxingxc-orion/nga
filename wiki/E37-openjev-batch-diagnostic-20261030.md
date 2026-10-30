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
