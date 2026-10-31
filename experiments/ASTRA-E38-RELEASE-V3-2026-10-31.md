# E38 release-only Astra v3 — BLOCK

实际 child wait、runner terminal、EXIT 均为 0，输出摘要已独立核验；审查结论仍为 BLOCK。原文如下，原包与原指标不修改。

**BLOCK for the exact frozen bundle** (`e38_release_candidate_20261031_v5`).

The bundle itself is intact:

- `MANIFEST.json` SHA256 matches the expected `2d42456545fbe8dffee0f1261d130340c5ededc82e3786531ff89ed310a7a685`.
- All 316 manifest entries match size and SHA256; no symlinks or unmanifested payload files were found. `MANIFEST.json` itself is the expected metadata exception.
- Frozen `cpu_tests/report.json` records 53/53 passed, with all 53 per-test log hashes valid.
- I reran `current/test_release_openjev_path_trace.py` in an isolated `/dev/shm` temp directory: 23/23 passed. The initial default run was not runnable because no default temporary directory was usable.

The implementation repairs the prior v2 findings:

- NPU report receipt/EXIT/StartedAt/FinishedAt binding: [release_openjev_path_trace.py:123-131](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/release_openjev_path_trace.py:123).
- Post-exit CPU attestation with container generation, FinishedAt, receipt and EXIT hashes: [release_openjev_path_trace.py:60-78](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/release_openjev_path_trace.py:60).
- Caller-pinned external anchor for review bytes and allocation-before bytes: [release_openjev_path_trace.py:81-93](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/release_openjev_path_trace.py:81).
- Durable pending publication recovery, crash windows, and idempotence: [release_openjev_path_trace.py:234-301](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/release_openjev_path_trace.py:234).
- Coordinated review/journal rewrite rejection, negative scientific flags, replay protection, and real `release()` fixture entry are covered in [test_release_openjev_path_trace.py:231-249](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/test_release_openjev_path_trace.py:231), [test_release_openjev_path_trace.py:252-289](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/test_release_openjev_path_trace.py:252), and [test_release_openjev_path_trace.py:368-405](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/test_release_openjev_path_trace.py:368).

The exact bundle still cannot substantiate or execute an actual release:

- It contains no actual `CPU_EXIT_BINDING.json`, `RELEASE_REVIEW.json`, trusted anchor, or release journal. The CPU attestation exists only as captured stdout in `additional_evidence/2-result-isolated.json`; the allocation observation is a read-only captured host record.
- Therefore the supplied NPU/CPU evidence is inspectable, but the exact bundle has no externally pinned review/anchor artifact proving the release-before state. CPU/NPU Docker identity and allocation claims remain evidence supplied by files, not live observations rerun here.
- There is also an unresolved executable-closure boundary: [release_openjev_path_trace.py:28-33](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/release_openjev_path_trace.py:28) path-imports and executes `e38_evidence.py` before `frozen_context()` snapshots and validates the frozen dependency bytes at [release_openjev_path_trace.py:305-330](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_release_candidate_20261031_v5/current/release_openjev_path_trace.py:305). The fixture proves the frozen preparer/queue closure, but does not prove that this already-loaded global helper is the validated snapshot.

The tests are CPU/temp-filesystem fixtures with synthetic Docker responses and allocation state. They do not establish live Docker, host, SSH, NPU, allocation, scientific, or operational approval. No production release, launcher, preparer, Docker, SSH, network, NPU, allocation mutation, approval creation, or external-weight access was performed.

处置：修复顶层 helper 在校验前被按路径执行的问题；提供真实退出后凭证与调用方固定的 anchor 作为新审查输入。审查未授权或执行资源释放，9B 未启动。
