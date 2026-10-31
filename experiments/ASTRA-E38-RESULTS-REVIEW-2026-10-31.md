# E38 9B actual Astra results review — bounded PASS

实际 child/runner/EXIT 均为 0，COMPLETE 所列输出哈希已独立核验。结论支持固定 9B 诊断与冻结资源证据的一致性，不批准完整 JEVal，不证明实时占用。

**PASS for the bounded 9B diagnostic-result claims and frozen resource-evidence consistency. No blocking inconsistency found.** This does not approve JEVal or establish current live resource state.

Reviewer process metadata records `codex exec --model gpt-6-astra` in [PROCESS.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_astra_20261031_v1/PROCESS.json:2).

1. **Bundle integrity passed first and again after review.** [MANIFEST.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_candidate_20261031_v1/MANIFEST.json:1) hashes to the expected `0523422b981c115f619693cfe320bac7770cacf7d1293f2d671b891944fe0bc2`. All 99 payload files match their sizes and SHA256 values. Membership is exact, with no missing/extra payloads, duplicate entries, or symlinks.

2. **All eight items and eight attempts validate.** I evaluated only selected, inspected verifier functions in memory, using bundle-local reads; no model code was imported. Receipt-envelope hashes, attempt hashes, identities, numeric contracts, ordered token/mask fingerprints, trace populations, and both report manifests match. Every reconstructed report field agrees with the structured claim and dated wiki results.

   The frozen identity is index **4200**, `jeval:disc-law-multi:000000`, shape **15×186**, temperature **1.8969118766347646**, physical chip **4**, logical `npu:0`. Candidate order is exactly:

   `A, B, C, D, AB, AC, AD, BC, BD, CD, ABC, ABD, ACD, BCD, ABCD`.

   Original execution uses all 15 rows; chunk8 uses `[0,8)` and `[8,15)`, preserving global padding and mask rows. The eight-call schedule is original untraced twice, chunk8 untraced twice, original traced twice, chunk8 traced twice. See [plan.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_candidate_20261031_v1/npu9/plan.json:22), pointers `/input`, `/schedule`, `/numeric_contract`.

3. **Exact controls pass; cross-path predictions differ reproducibly.** All four prediction-repeat comparisons and four hook-effect comparisons have zero numeric deltas and identical serialized prediction fingerprints. Both within-path trace-repeat comparisons are exact, and the cross-path localization repeats exactly: **11/11 report controls true**.

   Both original-versus-chunk repetitions reconstruct:

   | Comparison | Result |
   |---|---:|
   | Maximum logit delta | 0.13169223070144653 |
   | Maximum native-probability delta | 0.013869159693189886 |
   | Mean absolute probability delta | 0.0018492212924253178 |
   | Maximum wire delta | 0.01485981395698921 |
   | Decision | ABCD → ABCD |
   | Token identities | Identical |
   | Exact prediction | False |

   The source-defined wire comparison includes confidence. Its maximum comes from confidence changing from **0.1815781925790345** to **0.16671837862204528**; it is not another probability-only metric. Numeric validity tolerances do not relax the exact repeat/hook controls. See [verifier source](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_candidate_20261031_v1/npu9/verify_openjev_path_trace.py:189) and `npu9/report.json` pointers `/controls`, `/comparisons`, `/repeated_traces`.

4. **The first observed difference is supported by complete trace comparison.** All four traced items satisfy the frozen **928-event**, 32-layer contract, including every candidate row, event order, dtype, shape, layout, and chunk coverage. I also regenerated that contract using the bundled contract builder.

   In both repetitions, the first differing event is **`base_model.model.layers.0.linear_attn.in_proj_qkv:output`**, affecting candidates **0–14**. The preceding four observed events—including that projection’s input—match. There are **916 differing events** overall, with identical difference lists across repetitions. These are tensor-byte fingerprints; they establish earliest *observed* divergence, not kernel causation. See `npu9/report.json` pointers `/cross_traces/0` and `/cross_traces/1`, consistent with [wiki results](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_candidate_20261031_v1/claims/wiki.md:395).

5. **NPU/CPU generation and terminal bindings are consistent.** I checked the plan/request, reports, COMPLETE outputs, EXIT files, launch receipts, wrappers, parent-review hashes, and CPU post-exit binding. All **21/21 CPU-request dependencies** are available and match, including the target NPU plan.

   | Recorded generation | StartedAt | FinishedAt |
   |---|---|---|
   | NPU `36fe2217…f8e861` | 03:40:15.49105426Z | 03:44:24.39875505Z |
   | CPU `2d18a8ef…e80b61` | 03:44:38.04329506Z | 03:45:29.50054917Z |

   Both dates are **2026-10-31**. IDs and timestamps agree throughout the verifier report, CPU attestation, and release bindings. The CPU specification has `Devices=[]`. Its FinishedAt is appropriately supplied by the **post-exit** attestation. See [CPU report](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_candidate_20261031_v1/cpu9/report.json:2) and [CPU_EXIT_BINDING.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_candidate_20261031_v1/cpu9/CPU_EXIT_BINDING.json:2).

   These match the parent-supplied live observations. **I did not independently query Docker.** The verdict rests on reconstructed controls and bindings, not rc0 alone.

6. **The release evidence passes the caller-pinned anchor and exact-transition checks.** The 9B anchor hashes to `f4359466aa97f700fd85f4e134c12178a13ac497ec59e0aa7dbb0cdeeea7358f`. It binds the review, CPU attestation, and original allocation bytes. Those decoded bytes are identical across anchor and intent, hashing to `97060cc090783c771e13f7e3197b12e3aba653a7272770275c6818b25b59ad6b`.

   Intent, commitment, RELEASED, review, and the entire reconstructed `/bindings` dictionary agree. The only allocation transition removes the exact 9B chip-4 owner and appends its chip-4 free record. Other owners—chips **6, 7, 2, 0, 5, 3**—and all other allocation content remain unchanged. Resulting free chips are **[1,4]**; source-defined serialization hashes to `c8c94a2f63844df50b1fc72e6d9a0575aecb5cdd0e4a3db2d8819cca81ac60e8`. See [release intent](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_results_candidate_20261031_v1/release9/RELEASE_INTENT.json:5).

   Release tool/helper hashes exactly match the caller’s accepted Astra-v4 hashes. The prior review supplies a substantive bounded code PASS; its rc0 is not treated as scientific admission. Scientific flags remain `trace_valid=true`, `review_flags=[]`, **`candidate_batch_admission=false`**.

   The trusted 2B anchor also matches. Contextual terminal/report bindings and its chip-4-only release are consistent; the recorded 03:40:01 release precedes the 9B claim/launch. Comparing the handoff snapshots shows no unrelated allocation changes. This was not a new full 2B audit.

Remaining limitations: only **21/213 NPU plan-file dependencies** are bundled; the other **192 external dependencies**, including model/framework/data and historical preparation evidence, were not revalidated. Saved token fingerprints were checked consistently, not regenerated from external data/tokenizers. Historical execution and release depend on the trusted caller, recorded attestations, reviewed runtime, and cooperative allocation model; this review does not establish live occupancy or exclude an unobserved earlier restart.

The wiki’s approximately **0.0502 questions/s/chip** and **17.5703125 GiB** match the final traced item, not an aggregate performance benchmark. Missing raw logs do not prevent saved-result reconstruction. **Candidate-batch admission remains false and E36 admission remains failed, unchanged. No full JEVal score, speedup, training benefit, or causal claim is supported or approved.**
