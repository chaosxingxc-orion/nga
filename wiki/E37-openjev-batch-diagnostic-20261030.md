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
