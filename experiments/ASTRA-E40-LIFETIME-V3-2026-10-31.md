# ASTRA-E40-LIFETIME-V3-2026-10-31 — PASS

范围：exact E40 v3 code and plan; fresh operational checks before launch。实际终态和输出哈希已核验；通过不等于 NPU 已运行或资源已释放。

**PASS — exact code/plan is substantively ready for the next approval gate.**

- `MANIFEST.json`: SHA256 matches `3bf8ea52…09dc`.
- `plan/plan.json`: SHA256 matches `90721d65…c3d9`.
- 348 manifest payloads and 346 SOURCE_MAP mappings verify. The 227 planned bindings resolve as 221 bundled files plus six declared external omissions; external weights/data were not read.
- `Native.predict` obtains logits at the completed forward, then native `softmax` rejects nonfinite values. The new wrapper captures `z` from that authenticated traceback frame, records elapsed time, available peak metrics, input/core observations, attempt and generation identity, tags nonfinite values for strict JSON, durably publishes `rejected/<key>.json`, and re-raises.
- Rejected records cannot enter `items/` or successful-prefix recovery. `COMPLETE.json` commits `rejected_manifest`; no fallback or altered success-path arithmetic is introduced.
- The retained `E40-NATIVE-RUNTIME-CPU-V2` evidence reports eight tests, including NaN/+Inf/-Inf native-predict failures and successful prediction behavior. Its driver, candidate, helper, test, and wrapper hashes match the final sources. This evidence is CPU-only with mocked completed tensor outputs plus separate full-shape CPU GDN arithmetic; it is neither checkpoint nor NPU execution.
- The four accepted v2 repairs remain present: `cu_seqlens=None` only, equal guards across modes, sanitized `-S -s -P` startup preserving CANN without Ascend `-I`, and owned-generation/pending-byte launch recovery. Stop rules remain 8 GiB free and 48 GiB reserved; admission remains false.

I did not rerun fixed-image tests or launch NPU. A local fixture invocation was unavailable because the read-only sandbox has no writable temporary directory; I relied on the retained authenticated evidence and static review.

NPU launch may proceed only after fresh host occupancy/allocation checks and separate exact parent/independent approval bound to plan SHA `90721d6509df030a71ed012848f7a0b11ce31b7fd11d63c306fbaf90b223c3d9`.
