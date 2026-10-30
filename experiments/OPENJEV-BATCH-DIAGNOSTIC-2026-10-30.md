# E37 — Open-Jev batch-shape, no-op and layer-memory diagnostic

Pre-registration prepared 2026-10-30, before E37 forwards. Defects 12/16: preserve
executable task identity and distinguish genuine memory optimization from numerical
configuration changes. Unconstrained optimum is to delete candidates or hide
changed predictions. Counterparts check all ordered candidates/tokens, exact no-op
outputs and paired original/chunk differences. No labels or correctness select
inputs; this is not training, full-test scoring or an E33/E36 gate amendment.

## Existing evidence and question

E36 completed 20 forwards per checkpoint. Both `candidate_batch_admission` values
are **false** and remain false. On index 9027 (30 candidates, maximum 4096 tokens):

| Model | Maximum logits difference | Maximum probability difference | Original repeat difference |
| --- | ---: | ---: | ---: |
| Open-Jev2 | 0.23634731769561768 | 0.014141414650314155 | 0 |
| Open-Jev9 | 0.14102649688720703 | 0.000009391012487314221 | 0 |

E36 report hashes: 2B `f9924b954ec46a690a38f4c4f264247d2f2fdaccf78aaebfb79a0c82d46986b6`;
9B `54e31f8ea0b2893cb3f71e6b291bbc903b3a3633447469fb36119890cf2f77b6`.
The two original/chunked paths each repeated exactly; chosen choices and consumed
tokens matched. Their numerical difference has not been attributed to a kernel.
This protocol is explicitly designed after observing that difference. It must not
be described as an unseen confirmatory test or use a new tolerance to pass E36.

The new questions are: does the wrapper itself alter outputs without splitting;
do synchronized metadata hooks alter results; and which decoder layers show the
largest inclusive allocation peaks in original and split execution?

## Metadata-only selection, frozen before additional predictions

Use the exact accepted E31 report and lowest original index to break ties. Include
the existing longest input, index 9027. Select at most one item in each stratum:

| Stratum | Candidate batch | Maximum prompt tokens | Selection |
| --- | ---: | ---: | --- |
| short_tail | 9–16 | 1–512 | lowest eligible original index |
| mid_tail | 17–30 | 513–2048 | lowest eligible original index |
| long_tail | 17–30 | 2049–4096 | lowest eligible original index |

Every selected original workload must also satisfy batch × length <= 122880 and
batch × length² <= 503316480, the already exercised E36 boundary envelope. The
maximum width 255 / padded workload 549780 is **excluded from original execution**;
no intentional original worst-batch OOM is requested. A missing stratum remains
missing; duplicate selected indices are executed once. These bounds are a limited
admission heuristic, not proof all smaller tensor shapes fit.

Metadata inspection of current E31 reports selects indices **9027, 4200, 8409**:
4200 is 15×186, 8409 is 24×3480. `mid_tail` is empty. Counts are 754 / 0 / 66.
The future plan must include the complete `select()` result and its source report
hash; the runtime reselects and requires equality. No future replacement based on
predictions, labels, performance or memory failure is allowed within this plan.

## Forward schedule and exact checks

For index 9027, run original twice, no-op wrapper twice with chunk_rows=30, and
chunk_rows=8 twice. Then run one original and one chunk8 pass with metadata hooks.
Other selected indices receive original twice and chunk8 twice. This is 16 forwards
per model for the current selection. Both 2B and 9B retain their own checkpoint,
source closure, temperature, BF16 backbone / FP32 head, native global padding and
response semantics. No precision, attention, candidate or context change.

The no-op and hook checks require **exact serialized predictions**, including
logits, probabilities, wire values, candidate order and token hashes. Signed zero
is distinguished. This is exactness of saved numerical outputs, not a claim that
all unsaved intermediate tensor bits were inspected. Any boundary original-repeat/no-op difference or hook
effect makes `diagnostic_valid=false`; descriptive differences remain reported,
but attribution from that instrumentation is not accepted. Repeat differences in
both original and chunk paths are reported without fitting a new threshold.

For each pair report maximum logits / probabilities / wire differences, mean
absolute probability difference, exactness, token identity and decision changes.
Choice uses returned choice, noul uses >=0.5, and score uses the actual returned
score (not ordinal argmax). Summarize paired decision changes over selected items,
with the explicit small selected denominator and source/stratum coverage. No gold
accuracy, ECE/Brier, aggregate generalization or “negligible effect” claim is made.
`candidate_batch_admission` remains false regardless of diagnostic outcomes.

## Passive profiling and limits

Hooks return `None` and never replace an input or output. On the two instrumented
boundary passes, retain backbone input/output shape, dtype and device, ordered
input-ID and attention-mask row hashes, chunk ranges, and every decoder layer's
input/output metadata, module/attention class, synchronized duration, allocated
bytes before/after and inclusive peak allocated/reserved bytes. Hooks must be
removed even on failure. Empty layer discovery is an error, not an empty success.

Each decoder pre-hook synchronizes and resets peak statistics. Its corresponding
post-hook synchronizes and records the layer's inclusive peak. Consequently these
peaks are **not additive**, and that pass does not provide a whole-forward peak.
Uninstrumented passes separately record whole-forward timing and peak memory.
Hooked timings include synchronization and CPU metadata hashing, so they cannot
serve as fair throughput measurements or an acceleration claim.

Layer peaks can identify where further investigation belongs; they do not identify
a specific internal operator or prove causality. Preserve the layer/batch shape
when considering a future memory optimization. Inference already disables cache;
CPU offload between layers may not reduce the dominant within-layer temporary
allocation. CPU computation, new precision, attention replacement or modified GEMM
shape needs separate numerical validation. Concatenating chunk hidden states can
retain extra memory and must remain disclosed. No strategy is automatically
accepted because its name says “offload” or “same batch shape.”

## Execution contract — not launched

`tools/openjev_batch_diagnostic.py` requires a new frozen schema-1 plan. It does not
allocate a chip or launch Docker. Prepare the exact run only after the orchestrator
has chosen an explicitly available chip. Use only 175 and existing immutable image
`sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.
Chip 1 currently belongs to the Nimble formal queue and is not available for E37.

Plan fields: `schema`, `image`, `chunk_rows=8`, `out`, `source_config`,
`source_config_sha256`, `selection`, `preregistration`, `wrapper`, `launch`,
`resume`, `container_spec`, and `files` hashes. Freeze the diagnostic script,
chunk wrapper, protocol, scripts/spec, source configuration and its complete
native dependency closure before launch. The actual launcher must bind approved
plan hash, exact image/command/environment/mount/device specification and resource
ownership under the allocation lock. This file is a protocol, not that launcher.

All long work is detached, fixed-name and retained, with CephFS logs, 10-second
heartbeats, terminal/EXIT, identity-bound per-forward receipts and guarded exact
relaunch. Unexpected exceptions fail with evidence; no row substitution or
candidate trimming. Existing terminal evidence is never overwritten. Receipt
resume only occurs with unchanged plan/request/mode/repetition/profile identity.
Completion requires frozen hashes, declared forward count, report/selection hashes,
wrapper and retained Docker exit, and independent comparison review. Existing
E33/E36 artifacts are neither changed nor relabelled.

A future chunk8 numerical-configuration evaluation, if pursued, requires a separate
pre-registration and separately labelled full-test result. It cannot fill the
original-batch E33 completion cell or overwrite E36 failed equivalence admission.

## 2026-10-31 resource-selection amendment — before E37 preparation or execution

E37 may select one physical chip from **0, 1, 2, 3, 4, 5** on 175 after its
current experiment has completed the required inference/audit acceptance, its
retained device-owning container has actually exited, and the allocation file
explicitly records it as free. Chips **6 and 7 remain excluded**, even if a future
allocation snapshot erroneously lists them free. The earlier preparer restriction
to chips 0/1 was an orchestration choice, not a numerical or scientific condition;
this amendment permits the first legitimately released reference-experiment chip,
including chip 4 after E32 Open-Jev-2B OOD acceptance.

This does not release any current allocation. Both CPU preparation request and
NPU launch still check allocation ownership and actual Docker/device-process
occupancy under the allocation lock. Every new plan records its actual physical
chip; the new container exposes exactly that single physical davinci device and
continues native logical `npu:0`. Historical source probe configurations and their
original physical-chip fields stay immutable. Original inputs, ordered candidates,
metadata-selected indices 9027/4200/8409, 16-forward schedule, dtype, temperature,
wrapper comparison, thresholds and `candidate_batch_admission=false` are unchanged.

Validation before use: 38 preparer CPU tests and 10 diagnostic CPU tests pass.
Added counterparts reject chips 6/7 at request and launch even under a synthetic
free-allocation claim, and verify chip-4 mapping/claim preserves the historical
source chip and logical device. No E37 remote request, frozen runtime plan, NPU
claim or diagnostic forward was created by this amendment. The completed Astra review found no deterministic blocking defect in its frozen
code scope; its snapshot predates this chip-allowlist adjustment and associated
tests/documentation. Parent review separately covers this resource-only delta;
the scientific driver and chunk wrapper are byte-unchanged. The review does not
certify actual resource release, remote plans or numerical outcomes.
