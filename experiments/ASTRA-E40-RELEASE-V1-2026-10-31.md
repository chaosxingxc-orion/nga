# ASTRA-E40-RELEASE-V1-2026-10-31 — PASS

范围：release code only; actual exit evidence and caller-pinned approval required。实际终态和输出哈希已核验；通过不等于 NPU 已运行或资源已释放。

**PASS — exact E40 release TOOL CODE only, within the documented trust model.** No release is authorized by this review.

Verified:

- `MANIFEST.json` SHA256: `e941447b98dedfd4c8860f932cc5b8ef0c4bd9297c7bc02a57694f18966dfa02`.
- Exact v3 plan SHA256: `90721d6509df030a71ed012848f7a0b11ce31b7fd11d63c306fbaf90b223c3d9`.
- All 245 manifest payload entries match size and SHA256; no duplicate entries or symlinks.
- `SOURCE_MAP.json` SHA256: `800a96e16bdf4d3b48057e493aa7a8139976a48a201bb283e2c608a5b1eb1ae1`; all 241 mappings match.
- External large inputs are recorded in `OMITTED.json` and remain runtime-authenticated by the plan; they were not read.

The release implementation correctly:

- Authenticates the frozen helper before execution ([release_openjev_lifetime.py:26](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e40_release_candidate_20261031_v1/current/release_openjev_lifetime.py:26)).
- Requires the exact v3 plan, chip 1, detached CPU request, parent/independent approvals, receipts, generations, terminal markers, EXIT files, and CPU post-exit attestation ([release_openjev_lifetime.py:103](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e40_release_candidate_20261031_v1/current/release_openjev_lifetime.py:103)).
- Reconstructs all receipt/control/flag results independently rather than trusting report equality ([release_openjev_lifetime.py:153](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e40_release_candidate_20261031_v1/current/release_openjev_lifetime.py:153)).
- Requires retained, device-free CPU verification and actual exited generation identity.
- Requires physical-host/device-free checks and cooperative locks before the sole chip-1 owner transition ([release_openjev_lifetime.py:191](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e40_release_candidate_20261031_v1/current/release_openjev_lifetime.py:191)).
- Preserves pending publication, crash recovery, exact before bytes, and later-owner replay behavior ([release_openjev_lifetime.py:270](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e40_release_candidate_20261031_v1/current/release_openjev_lifetime.py:270)).
- Rejects failed or rejected NPU generations for normal release via the terminal `rejected_manifest` gate. Negative scientific flags may be explicitly accepted while `candidate_batch_admission` remains false.

The frozen release test source contains 17 tests covering real `release()` entry, real binding/transaction, anchor rewriting, generation changes, CPU exposure, owner replay, allocation races, symlink locks, publication crash windows, and frozen-context authentication. I reran the isolated fixture suite with `TMPDIR=/dev/shm`: **17/17 passed**. This remains synthetic Docker/fixture evidence, not live NPU, CPU, Docker, host, allocation, or release evidence.

No code blocker or minimum fix is identified. Actual release still requires a fresh caller approval, immutable anchor, and future NPU/CPU operational evidence.
