# E40 actual Astra v2 — BLOCK

Actual child/runner/EXIT rc 0 and six COMPLETE output hashes verified. Execution success is not approval.

**BLOCK — v1 blocker 4 remains partially unresolved. The exact plan is not launch-ready; fresh operational checks alone cannot resolve it.**

A completed forward with NaN/Inf logits bypasses the new rejected-measurement publisher. [Native.predict():150](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e40_lifetime_candidate_20261031_v2/dependencies/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_openjev2_probe_20261030/jeval_reference_inference.py:150) obtains logits, then calls `softmax`, which rejects nonfinite values before returning. Consequently, [driver:184](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e40_lifetime_candidate_20261031_v2/plan/openjev_lifetime_npu.py:184) never reaches timing/peak collection or `publish_measurement()`. The intent and generic failure survive, but the observed logits and completed-forward measurements disappear. I reproduced this using the actual `Native.predict` implementation with a mocked completed tensor forward. The bundled nonfinite test supplies an already-constructed prediction directly to the publisher and misses this path.

**Minimal fix:** capture raw logits and available measurements before prediction validation can raise; durably publish them as explicitly rejected, non-reusable evidence with the attempt/generation identity and terminal commitment. Preserve numerical rejection. Add a fixture exercising failure through `Native.predict`, then refreeze the affected dependency closure and plan.

The other four v1 repairs are substantively implemented:

- Only absent/`None` native `cu_seqlens` is accepted; unknown/non-None kwargs fail.
- Authenticated original/candidate arithmetic shares identical bind/default/validation work; patch restoration is protected.
- Fixed-image startup uses `-S -s -P` with explicit nonempty trusted paths. Retained startup evidence supports CANN/tbe imports.
- Running-container response-loss recovery avoids requiring its own device to be empty. Pending claim/receipt recovery preserves validated publication bytes. Durable-file fixtures mock Docker; they do not establish live crash recovery.

Both supplied hashes match. All **331 payloads**, **329 SOURCE_MAP mappings**, and **227 planned bindings** check out: 221 bundled bindings plus six declared omissions. External bytes were not read; runtime requires their validation before model loading.

Delete-only AST identity/generated hashes, full candidate/token/mask checks, exact serialized predictions including signed zero, probability/wire checks, comparable timing, cooperative allocation locking, generation binding, and uncertain-attempt rejection are implemented. The 8-GiB minimum-free and 48-GiB maximum-reserved checks are stop rules. Numerical mismatches remain negative and admission remains false. **CLI rc0 does not mean scientific PASS.**

The new CPU verifier support provides a post-exit request, detached no-device spec, authenticated reconstruction, receipts, and exit attestation. No production request is expected yet. Its changed wrapper was **not** exercised by the retained 12-test fixture. Likewise, the fullshape native-call fixture predates the terminal `rejected_manifest` addition.

I reran seven structural tests and short in-memory prediction/negative-path checks, and reconstructed the retained **32-cell/256-forward** CPU receipt comparisons. Durable-file crash tests, fixed-image startup, tensor execution, and live launch were **not rerun** under this read-only review.

The preregistration honestly limits this stage to 2B/input4200/full15×186, eight forwards, chip1. Full restart capability, larger shapes, offload, stage instrumentation, and full JEVal admission are outside this verdict.
