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

## 2026-10-31 release candidate v3: pinned evidence and CPU exit attestation

The earlier commands and v4 scope above are retained as their historical operation sheet. They are superseded for the new release candidate by this addendum. No resource release is performed by this implementation update, and actual release-only Astra acceptance is still required. The exact v7 plans now supported are 2B `2a859fe2ba77ac431e2e5c62408c964bb15a5794e07c8981be625bf626a0e66d` and 9B `fae8ac8368b7a98fad32e07acc1b54b1dded55c1812f95ec4cdb136b92ef3593`; their frozen source bytes and original reports remain unchanged.

The running CPU verifier cannot know its future Docker `FinishedAt` or wrapper `EXIT`. Therefore its original `report.json` is preserved. After actual CPU exit, the separately reviewed release tool has a host-only `--attest-cpu-exit` action:

```bash
python3 -B -I "$TOOL" --plan "$RUN/plan.json" \
  --verification-request "$VERIFY/request.json" --attest-cpu-exit
```

This writes only a no-overwrite `VERIFY/CPU_EXIT_BINDING.json`. It binds the original request/report/terminal SHA256, CPU container ID, `StartedAt`, `FinishedAt`, launch-receipt SHA256 and wrapper-EXIT SHA256. The host independently checks successful retained CPU exit, original request/spec/receipt identity and absence of devices before creating it, then rechecks the same Docker exit generation. The release transaction compares every field to live/current evidence. Creating this attestation does not amend the original CPU report or establish a new NPU forward.

The parent release review additionally requires `cpu_exit_binding_sha256` and `allocation_before_sha256`. Before release, the trusted parent must accept the actual Astra review of the new tool, independently inspect the CPU attestation, capture the exact original allocation bytes, then create a new anchor outside the release journal:

```json
{
  "schema": "e38-resource-release-anchor-v1",
  "release_review_sha256": "EXACT_RELEASE_REVIEW_SHA256",
  "cpu_exit_binding_sha256": "EXACT_CPU_EXIT_BINDING_SHA256",
  "allocation_before_sha256": "SHA256_OF_EXACT_ORIGINAL_ALLOCATION_BYTES",
  "allocation_before_bytes_b64": "BASE64_OF_EXACT_ORIGINAL_ALLOCATION_BYTES"
}
```

The trusted parent records the anchor's SHA256 in its independent acceptance record and supplies that exact literal digest in the launch/relaunch command. The command must not derive this trusted digest at runtime from the same mutable anchor, review, journal or a neighboring relaunch script. This is an explicit trust boundary: an attacker who controls the caller's accepted command or its independent acceptance record is outside the tool's integrity guarantee. File creation with `O_EXCL` alone is not claimed to make stored files immutable.

```bash
python3 -B -I "$TOOL" --plan "$RUN/plan.json" \
  --verification-request "$VERIFY/request.json" \
  --review "$RELEASE/RELEASE_REVIEW.json" --journal "$RELEASE" \
  --anchor "/absolute/path/to/parent-accepted-anchor.json" \
  --anchor-sha256 EXACT_LITERAL_PARENT_ACCEPTED_SHA256
```

The transaction validates this pinned anchor before accepting any release review or journal state. Rewriting review, before bytes, intent, commitment and terminal coherently cannot change the caller-pinned anchor. The NPU verifier's saved `npu_launch_receipt_sha256`, `npu_exit_sha256`, `npu_started_at` and `npu_finished_at` must match actual evidence. Both CPU and NPU generations are rechecked before allocation mutation.

Pending publication recovery now validates byte-identical retained pending records, completes links, persists the directory before removing the pending name, and removes only the accepted duplicate. Regression injection covers link-before, link-after, directory-sync-before-unlink and unlink-after windows for all three release records (`RELEASE_INTENT`, `INTENT_COMMITTED`, `RELEASED`). A differing partial pending file fails closed and remains available for diagnosis. These are real temporary-filesystem syscall-injection tests, not a claim to have simulated hardware power failure or all filesystem failure modes.

The pure CPU suite also exercises the real `release()` import/compile entry with the real `jeval_reference_queue.py` and `e38_evidence.py`, while host/preparation history, Docker responses and occupancy remain explicit fixtures. This verifies the executable source snapshot boundary without claiming a live Docker or live NPU release. The new Astra bundle must contain all three release files, these tests, the exact frozen preparer/queue/evidence closure, the operation sheet, per-test results and actual v7 CPU/NPU evidence. Old release-only BLOCK findings remain authoritative until a new actual review accepts this candidate.

## 2026-10-31 addendum: v7 release candidate with an external anchor

The v4 commands above are historical and remain unchanged. They are not the
current execution target. The new candidate accepts the frozen v7 2B/9B plans
(`2a859fe2ba77ac431e2e5c62408c964bb15a5794e07c8981be625bf626a0e66d` /
`fae8ac8368b7a98fad32e07acc1b54b1dded55c1812f95ec4cdb136b92ef3593`).
It still requires separate actual release-tool Astra review and parent acceptance
before resource mutation. This addendum records implementation, not approval.

A running CPU verifier cannot know its own eventual Docker `FinishedAt` or
wrapper `EXIT`. After its actual exited/0 state is observed, the reviewed host
entry point `--attest-cpu-exit` creates a no-overwrite `CPU_EXIT_BINDING.json`
beside the verification request. The original verifier report is not rewritten.
The binding contains schema `e38-cpu-exit-binding-v1`, request/report/terminal
SHA256, CPU container ID, StartedAt/FinishedAt, launch receipt SHA256 and EXIT
SHA256. It checks the actual container twice and makes no allocation mutation.
This establishes a post-exit observation, not proof that no unobserved earlier
restart occurred before the observation.

The parent release review additionally binds `cpu_exit_binding_sha256` and the
original `allocation_before_sha256`. A separately stored anchor has schema
`e38-resource-release-anchor-v1` and these fields:

```json
{
  "schema": "e38-resource-release-anchor-v1",
  "release_review_sha256": "EXACT_REVIEW_BYTES_SHA256",
  "cpu_exit_binding_sha256": "EXACT_CPU_EXIT_BINDING_SHA256",
  "allocation_before_sha256": "EXACT_ORIGINAL_ALLOCATION_SHA256",
  "allocation_before_bytes_b64": "BASE64_OF_THE_EXACT_ORIGINAL_BYTES"
}
```

The trusted caller must pin the **anchor's SHA256 outside the mutable review,
anchor and journal files**, then supply that literal digest using
`--anchor-sha256`. Recomputing it from a mutable anchor on every retry defeats
this trust boundary. This protects against coordinated on-disk review/journal
rewriting while the caller's digest and reviewed executable remain trusted;
it does not protect against a party able to alter that caller or executable.

After the new release-only review is accepted, use the reviewed tool snapshot
on SSH host `npu` (`k8s-node1`). Host Python 3.10 requires `-I`; do not use `-I`
inside Ascend containers. For the already completed 2B generation:

```bash
python3 -B -I "$TOOL" --plan "$RUN/plan.json" \
  --verification-request "$VERIFY/request.json" --attest-cpu-exit

# After parent review and externally pinned anchor creation:
python3 -B -I "$TOOL" --plan "$RUN/plan.json" \
  --verification-request "$VERIFY/request.json" \
  --review "$RELEASE/RELEASE_REVIEW.json" --journal "$RELEASE" \
  --anchor "$ANCHOR" --anchor-sha256 "$PINNED_ANCHOR_SHA256"
```

Here RUN is `openjev_path_trace_openjev2_20261031_v7`, VERIFY is
`e38_openjev2_verify_20261031_v8`, and RELEASE/TOOL/ANCHOR must be newly reviewed
unique paths. These symbolic commands are not an exact authorized launch.
Release compares NPU receipt/EXIT hashes and StartedAt/FinishedAt against the
saved independent verifier; CPU exit identity and all saved hashes against the
anchored post-exit observation; and the allocation's original bytes against the
external anchor. Publication recovery preserves the original intent timestamp
and accepts only an exact committed before/after transition. Original scientific
flags and `candidate_batch_admission=false` remain unchanged.
