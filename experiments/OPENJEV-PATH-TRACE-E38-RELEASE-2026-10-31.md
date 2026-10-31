# E38 serial execution and resource-release operation sheet

Status: implementation candidate for independent review. No release performed. This external tool does not change either frozen v4 plan or its execution closure. It supports only the exact two v4 plan hashes and physical chip 4. A successful resource release is not scientific success or E36 admission.

## Exact launch approvals

Each target `openjev_path_trace_openjev{2,9}_20261031_v4` requires a new, no-overwrite `PARENT_REVIEW.json` containing `approved_plan_sha256`, and `INDEPENDENT_REVIEW.json` containing:

```json
{
  "approved": true,
  "approved_plan_sha256": "EXACT_TARGET_PLAN_SHA256",
  "review_path": "/absolute/path/to/actual/astra/review.md",
  "review_sha256": "ACTUAL_REVIEW_FILE_SHA256"
}
```

The parent writes these only after accepting the actual Astra review of the exact plans. The launcher checks byte identity, not the review's prose semantics, so merely supplying `approved=true` is not a review. Exact target plan hashes:

- 2B: `882b686ba62c75f1bb41c670b18fb4785f439273bbd32b4c5de29ff9a512a8df`.
- 9B: `b1afb0e81a5c3c77f6bb5892e8dfdb7da750220d6d44f17dc2a7e52b6d9afce3`.

Before launching, add the dated execution purpose/hypothesis/setup to E38 wiki. Launch 2B first, then independently verify and release its ownership before launching 9B. Never start the two NPU plans together; both target chip 4. Their launchers acquire the shared allocation lock and enforce exact ownership/current physical emptiness.

## Commands for one model

Run the following commands on the physical `npu` SSH host (`k8s-node1`). Set `MODEL=2` for the first pass. Repeat with `MODEL=9` only after the first release terminal and allocation state have been verified.

```bash
ROOT=/mnt/cephfs/xingchao/experiments/jev/reference_inference
MODEL=2
RUN="$ROOT/openjev_path_trace_openjev${MODEL}_20261031_v4"
VERIFY="$ROOT/e38_openjev${MODEL}_verify_20261031_v4"
RELEASE="$ROOT/e38_release_openjev${MODEL}_20261031_v4"
TOOL="$ROOT/e38_release_tools_20261031_v1/release_openjev_path_trace.py"

# Starts the retained NPU container and returns immediately, after approvals.
bash "$RUN/LAUNCH_EXACT.sh"
```

Poll `digest.md`, `COMPLETE.json`, `EXIT` and short actual Docker state queries. Do not tail raw logs in the parent session. A marker with rc 0 still requires the wrapper EXIT and retained Docker actual exit. Scientific flags are retained. A report/terminal gap or unmatched intent is a failed generation and must not trigger a retry. Long verification stays detached:

```bash
python3 -B -I "$RUN/prepare_openjev_path_trace.py" \
  --source "$RUN" --preregistration "$RUN/PREREGISTRATION.md" \
  --verify-plan "$RUN/plan.json" --request-out "$VERIFY"
```

The parent inspects the new verification request/closure and writes `VERIFY/PARENT_REVIEW.json` with its exact `approved_request_sha256`. Then:

```bash
bash "$VERIFY/LAUNCH_EXACT.sh"
```

This is CPU-only independent reconstruction with retained Docker identity checks, no NPU forward. Wait for its own `COMPLETE.json`, `EXIT` and actual CPU exit 0. Inspect the independent report and scientific flags, and record the result/verdict in wiki before approving resource release.

## Resource-release review schema

The parent creates `RELEASE/RELEASE_REVIEW.json` with exclusive creation after accepting the independent CPU evidence. All digests refer to actual file bytes; the booleans and flags must reproduce the result, including `false` and nonempty flags when present.

```json
{
  "schema": "e38-resource-release-review-v1",
  "approved": true,
  "approved_plan_sha256": "EXACT_TARGET_PLAN_SHA256",
  "verification_request_sha256": "VERIFY/request.json SHA256",
  "verification_report_sha256": "VERIFY/report.json SHA256",
  "verification_terminal_sha256": "VERIFY/COMPLETE.json SHA256",
  "accepted_trace_valid": false,
  "accepted_review_flags": ["EXACT_FLAGS_FROM_NPU_COMPLETE.json"],
  "candidate_batch_admission": false,
  "release_tool_sha256": "REVIEWED release_openjev_path_trace.py SHA256",
  "evidence_helper_sha256": "REVIEWED sibling e38_evidence.py SHA256"
}
```

The example `false` is illustrative, not a required failure outcome. The tool also verifies the existing exact-plan parent/actual independent launch review, original preparation success, independent CPU verification request/result/terminal/EXIT, actual CPU/NPU container identity and exit timestamps, NPU terminal/report/EXIT, and every receipt/attempt hash. It accepts `trace_valid=false` only when the release review explicitly acknowledges that exact value and every flag. Nonzero NPU or verifier exits require a separate failed-run closeout; this normal-release tool rejects them.

After this separate tool's implementation and release review are accepted:

```bash
python3 -B -I "$TOOL" --plan "$RUN/plan.json" \
  --verification-request "$VERIFY/request.json" \
  --review "$RELEASE/RELEASE_REVIEW.json" --journal "$RELEASE"
```

This short host transaction makes no Docker start/stop/create calls. Under the shared `CHIP-ALLOCATION.json.lock` it requires the exact current owner, rechecks actual exits, rejects active/created chip-4 references, and runs the existing exact empty-process guard. Exited historical evidence containers remain retained. It writes durable `RELEASE_INTENT.json` (original allocation bytes plus parsed snapshot/hash; exact after snapshot/hash), then `INTENT_COMMITTED.json` binding that intent before publishing the allocation. The allocation write uses a new no-follow exclusive temporary file, file fsync, atomic replacement and directory fsync. Finally it publishes no-overwrite `RELEASED.json` with rc 0, intent/commitment SHA and before/after allocation SHA.

A crash after allocation mutation but before the terminal can be resumed with the same command only when current allocation exactly matches the recorded after state and all evidence still binds. A crash before mutation requires the exact before bytes/state. Unexpected intervening allocation changes fail closed. A completed replay verifies its immutable journal and returns `ALREADY_RELEASED`; it does not mutate or free a later owner's allocation. Ordinary detected errors append a uniquely named failure record and preserve evidence. Never delete a journal to force a retry.

After successful 2B release, check its terminal hashes and that chip 4 has exactly one free entry identifying the prior run. Then repeat the same procedure with `MODEL=9`. The 9B launcher independently rechecks current free ownership and physical emptiness, so another task acquiring chip 4 in the interval blocks it safely. Both models' original E36 admission remains false.
