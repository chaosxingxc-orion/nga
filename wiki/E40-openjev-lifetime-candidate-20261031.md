# E40 — Open-Jev full-shape GDN lifetime candidate

> Status: planned, draft protocol; no NPU launch · Round: reference engineering · Date: 2026-10-31
> Draft: [E40 protocol](../experiments/OPENJEV-LIFETIME-E40-DRAFT-2026-10-31.md)

## 1. Purpose

Prepare a native full-candidate memory path for remaining Open-Jev JEVal reference inference; defect 12/16. E38 success does not establish this admission. Current E36 `candidate_batch_admission=false` remains unchanged.

## 2. Hypothesis

Deleting last-use references may lower allocated peak while preserving full outputs. The minimum-memory degenerate solution skips work; full candidate/token/output identity and exact paired repeats prevent it. A numerical mismatch or no memory improvement is reported as a candidate failure or negative result without relaxing the protocol.

## 3. Setup

Candidate generation is in `tools/openjev_lifetime_candidate.py`, tests in `tools/test_openjev_lifetime_candidate.py`. Only the fixed native source SHA `0e2cd8dc50885b2701d26b116c585eedcdc62a24080ec34345af55b963126ded` is accepted. L1, L2 and their combination insert only AST Delete nodes. Inference/no-cache/C64/nonempty native 2B/9B shape conditions are enforced externally. Proposed later NPU input identities are 4200, 9027, 8409; exact model/data/code/launch and headroom registration remains to be frozen. No actual run directory or NPU launch exists.

## 4. Results

Seven pure CPU tests pass: Delete-only AST preservation/compilation, insertion locations/remaining reads, loop-view cleanup and no double deletion, native source mutation/variant rejection, supported-mode and shape guards, gradient/empty/device rejection, unrelated callable rejection. The tests read the fixed source as data and execute no tensor operation. No numerical, memory or throughput result exists.

## 5. Verdict

Implementation candidate ready for review and fixed-image tensor verification. Not numerical admission, no JEVal result, no training gain and no resource-release permission. Next steps: independent code review, fixed-image tests, complete driver/receipt/verifier integration, freeze exact plan and obtain actual Astra review before any NPU work.
