# E38 — Open-Jev native path trace (pre-registration)

> Status: planned; no NPU forward has been launched. Date: 2026-10-31.

## 1. Purpose

E36 found that the Open-Jev original candidate batch and the candidate-chunked
path are not numerically equivalent (`candidate_batch_admission=false`). E37
confirmed the result is repeatable for its selected short and long
inputs, but did not localize the first observable divergence. E38 records passive
intermediate tensor fingerprints for the same native backbone so that a future
review can say where the first *observed* divergence occurs.

This addresses defect-registry rows 12 and 16: preserve executable identity and
distinguish a memory wrapper from a numerical configuration change. It is a
diagnostic experiment, not a new admission test, a full-test score, or a training
run. It cannot change E36's false admission result.

## 2. Hypothesis and counterpart

The hypothesis is that the first observed difference is at a reproducible native
decoder boundary (projection, convolution, gated-delta core, norm, MLP or full
attention) and that passive hooks do not change the prediction. The result would
be weakened if the first difference moves between repetitions or if hooks change
the serialized prediction.

The unconstrained optimum is to trace only rows that make the paths look equal,
or to omit a missing event. The discrimination counterpart is mandatory: the
trace must include all 15 ordered candidates, every expected event, exact dtype
and shape, signed-zero-preserving SHA-256 fingerprints, and both original and
chunked executions. Missing, repeated, reordered or partial observations fail
closed. A reported first event is only a localization pointer; it is not proof of
kernel causality.

## 3. Frozen scope and schedule

Only the E37 short input is supported by the driver: 15 candidates, global padded
width 186, native BF16 backbone and FP32 readout head. Use **index 4200 only**,
the existing metadata-selected short-tail representative. This diagnostic is
designed after seeing E37's differences (including the comparatively large 9B
short-input difference); it is not an unseen confirmatory experiment. The selection,
request/token hashes, candidate order, temperature, model checkpoint and native
mask are inherited unchanged from the accepted E37 report. No future prediction
or gold label may replace this index within E38. Inputs 9027 and 8409 are outside
this instrumentation's bounds and require a separately frozen extension.

For each of the two checkpoints (2B and 9B), execute in this fixed order: original
untraced twice, chunked untraced twice, original traced twice, chunked traced
twice. This is **8 forwards per checkpoint, 16 forwards total**. The chunked path
uses the already frozen candidate wrapper (8 + 7 rows). Compare repeats within
each path, every traced prediction against its matching untraced baseline, and
the two repeated traces within each path. Compare serialized logits, probabilities, wire
values, choices/scores, candidate order and token hashes exactly. No new numeric
tolerance is introduced. All repeat and instrumentation controls must be exact;
failure marks `trace_valid=false`. Cross-path differences are descriptive outputs,
not a pass/fail tolerance. An NPU or trace failure ends the run with evidence;
no substitution, silent continuation or automatic protocol relaxation is allowed.

`tools/openjev_path_trace.py` is passive: hooks return `None`, retain only bounded
per-row fingerprints, and always remove hooks and restore the native core on
success or exception. It requires 24 or 32 decoder layers and the inspected
`torch_chunk_gated_delta_rule` fallback. It rejects training mode, unknown block
types, cache-returning cores, shape/dtype changes, duplicate events, missing
events and incomplete or overlapping chunk coverage.

## 4. Pre-registered outputs and limits

For each model and index report the trace plan/source hashes, complete event list,
first observed differing event, changed candidate rows, exact prediction checks,
and any cleanup or runtime failure. Report memory and timing only as descriptive
instrumentation; hooks synchronize and retain CPU hashes, so they are not a fair
throughput measurement. Do not report accuracy, ECE, Brier, aggregate
generalization, or a full-test equivalence claim.

The CPU container test (`tools/test_openjev_path_trace.py`) has six passing checks,
including a randomly initialized tiny native Qwen3.5 with 24 mixed linear/full
attention blocks, 15×186 inputs and right-padding masks. Original traced/untraced
outputs are exact, both original and 8+7 trace populations validate, and hooks
are removed. The tiny test does not require cross-batch arithmetic to be exact.
It proves API compatibility, cleanup and fail-closed guards only; it is not
execution of E38 on a trained checkpoint. Before any NPU launch,
freeze the exact plan, source closure, image, device allocation, detached run
directory, heartbeat, terminal/EXIT, receipts and relaunch command in a wiki
entry. A successful trace does not authorize Open-Jev JEVal; E36 chunk8
admission remains false until a separately registered numerical evaluation is
accepted.

## 5. Driver/preparer work still required

The helper is not a runnable experiment. A dedicated driver must freeze exactly
eight `(mode, traced, repetition)` identities per model, call the existing native
request builder/eligibility checker, and bind each receipt to the plan, request,
checkpoint and complete source closure. In traced chunk8 mode, enter
`trace_path(backbone, torch, trace)` first and pass its yielded observer directly
to `candidate_chunks(backbone, 8, observer)`; do not nest a second manual chunk
loop. In traced original mode, the recorder defaults to candidate range `[0,15)`.
The wrapper must preserve global width and every token/mask row.

The driver must compare all four traced predictions to the matching untraced
baseline, all repeat pairs, and both repeated traces for each path. It then
compares original/chunk8 traces independently for repetition 0 and 1. A verifier
must reconstruct these results from all eight hashed receipts; missing, extra or
relabelled receipts fail closed. Source/input identity checks happen before and
after execution, including full ordered token and mask row hashes. The report
retains `candidate_batch_admission=false` explicitly.

The preparer may reuse E37's reviewed resource/identity guards but must create a
new E38 plan/schema and output tree, never edit an E37 plan. Required launch
evidence includes exclusive allocation under the lock, only chips 0–5 after
actual release, exact retained container/image/mount/command specification,
10-second heartbeat, item-level receipts, terminal plus wrapper EXIT, actual
Docker exit and an identity-checked exact relaunch. A receipt is accepted only
with the original frozen identity; failed terminal evidence is preserved.
Parent and independent review of this new closure precede NPU launch.

## 6. Repair candidates after localization (design, not approved changes)

The inspected native torch fallback converts query/key/value/beta/g to FP32,
forms full sequence-chunk tensors (`v_beta`, `k_beta`, `decay_mask`, `attn`,
`k_cumdecay`) and retains several until the recurrent chunk loop. This makes
within-layer tensor lifetime a concrete memory investigation. It does not prove
which operation caused E37's probability differences.

1. **Shorten demonstrably dead tensor lifetimes first.** After the two products
   `value = attn @ v_beta` and `k_cumdecay = attn @ (...)`, `v_beta` and `k_beta`
   are not referenced again. After `k_cumdecay`, the full `attn` is also dead
   before its per-chunk reassignment. A narrowly instrumented candidate can
   delete only these dead local references before allocating recurrent/output
   tensors. Preserve every arithmetic expression, dtype, shape and operation
   order. This may reduce peak allocated bytes; it does not guarantee lower
   reserved memory or a sufficient whole-workload bound.
2. **Measure parameter residency separately.** Layer parameter offload can
   reduce persistent weights while preserving the full candidate batch, but it
   does not remove the FP32 core's own peak and can slow inference substantially.
   First measure one complete native boundary forward with unchanged kernels;
   never claim that a 2B/9B checkpoint fits all JEVal rows from the short trace.
3. **Consider temporary storage offload only with explicit arithmetic identity.**
   An exact CPU/NPU byte transfer may preserve tensor values, but altered
   allocator/alignment/kernel selection still needs full-output validation.
   Stage live temporaries without slicing the operands of matmul/conv; do not
   silently replace sequence-chunk batched arithmetic with smaller calls.

Each candidate needs its own pre-registration and frozen source, exact native
repeat/output checks and representative memory/throughput evidence. Initial
triage includes the E37 short input and both previous long inputs; the largest
JEVal padded workload is a separate admission bound, not intentionally executed
as an OOM probe. Full-batch shape alone does not prove numerical equivalence.
Switching to the recurrent delta-rule implementation, fused kernels, another
precision, CPU arithmetic or candidate chunk8 changes arithmetic and cannot be
labelled a pure memory optimization. No candidate is currently selected or
accepted; a failed original-path optimization leaves the corresponding reference
cell blocked until an alternative protocol is explicitly registered and labelled.

## 2026-10-31 implementation clarification before NPU execution

The runtime closure is now implemented in `openjev_path_trace_run.py`,
`prepare_openjev_path_trace.py`, and `verify_openjev_path_trace.py`, with separate
E38 schemas. This updates the earlier implementation-to-do status, without
changing the fixed input, schedule or exact-control criteria above. A passive
full-padded-input identity guard runs in every traced and untraced forward; it
checks the same 15 ordered token rows and mask rows before the native backbone
call, and returns no modified inputs. Internal tensor fingerprints are added only
in the four traced forwards. Every receipt and its independent reconstruction
must retain these full-input identities.

Execution success and scientific trace validity are separate. Completed execution
with a failed exact repeat/hook/trace control retains `rc=0` as process evidence,
but the terminal explicitly carries `trace_valid=false`, one `review_flags` entry
per failed control, and `status=COMPLETED_SCOPED_REVIEW_REQUIRED`. The independent
verifier reconstructs and checks both the controls and terminal flags. Runtime or
instrumentation exceptions retain a nonzero terminal; neither condition permits
E36 admission or a full-test claim.

CPU preparation and verification use the fixed image's original entrypoint and
`python3 -P`; the entrypoint initializes the native import paths needed even by
CPU Transformers. Each CPU request and the later NPU plan are separate immutable
generations. Parent approval of a CPU request does not approve NPU execution;
that requires the final plan/source closure and an independent review bound to
that exact plan. Historic failure/skipped fixture generations remain retained.

## 2026-10-31 amendment — actual Astra v2 execution BLOCK

Applies only to new v3+ plans. Frozen v2 remains blocked. Numerical validation uses native temperature, unit mass with native `isclose(rtol=atol=1e-6)`, softmax/logit absolute tolerance `1e-5`, native wire renormalization tolerance `1e-8`, first argmax tie breaking, and chance-adjusted confidence tolerance `1e-7`. These cross-runtime recomputation tolerances do not relax exact serialized repeat/hook controls. Freeze registration population separately from execution order and exact per-event dtype, candidate row shape, and source layout. Folded normalization requires the exact batch × 186 × value-heads flattened source shape.

All control evidence must bind parsed JSON and SHA to the same no-symlink file bytes and verify unchanged file identity/content before accepting or mutating launch state. Every scheduled forward requires a durable no-overwrite intent committed before the call, and its receipt binds that intent. An unmatched intent permanently fails that generation; retrying an uncertain forward is forbidden. Eight receipts alone never establish exactly eight attempted forwards. A report/terminal publication gap also explicitly fails the generation; retain its report, EXIT, terminals and receipts, and allow only reviewed CPU forensic reconstruction. Do not overwrite failed evidence or silently promote/reuse it into a successful new generation. Ordinary resume is limited to a validated committed prefix with no unmatched attempt and no terminal/report. A new full execution requires a new plan/review generation.

## 2026-10-31 amendment — actual Astra v3 BLOCK of v4 plans

This amendment applies only to new v5+ execution plans, not frozen v4. Every first possible forward must follow durable creation of `items/` and `attempts/`: fsync each opened/new directory and its parent along the no-symlink path. Publishing an intent must not assume that fsync of the intent's direct parent persisted that parent's own directory entry. Historical EXIT moves persist the new archive parent chain, link and fsync the destination before unlinking the source, then fsync the source parent. Directory history moves likewise persist both parents. Fault tests establish syscall ordering and rejection behavior; they are not a claim of a reproduced Ceph power loss.

Native confidence must satisfy the hard closed interval `[0,1]` before any arithmetic reconstruction tolerance is applied. Add complete eight-receipt/intent regressions for negative `-5e-8` and greater-than-one values, plus valid uniform/saturated positive controls.

The fixed-image CPU suite must export the actual imported Qwen3.5 modeling/GDN fallback source path and bytes with SHA, package/config identity and image provenance, enabling independent source-to-trace review. Historical source extracts alone are insufficient. Preserve original v4 approvals unchanged; paired current local/175 clock samples explain the observed clock difference without claiming a retrospective historical timestamp proof. Future CPU/NPU launch receipts bind the exact parent-review file SHA read before launch and record launcher host/UTC. Subsequent bindings check that digest, so wall-clock order is not the sole evidence of prior review.
