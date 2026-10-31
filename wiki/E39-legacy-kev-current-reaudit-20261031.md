# E39 — current-date CPU re-audit of 28 legacy Kev reference panels

> Status: v2 CPU re-audit complete, parent verification complete; actual Astra bounded review complete with dated clarifications; v1 failure retained · Round: reference evaluation / evidence audit · Date: 2026-10-31 (Asia/Shanghai)
> Original pre-run plan (v1; successful v2 recorded below): `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e39_legacy_kev_current_reaudit_20261031_v1/PLAN.json`
> Code: [dated audit driver](../tools/legacy_kev_dated_reaudit.py); independent arithmetic from [Kev auditor](../tools/verify_reference_kev.py) and [devtools auditor](../tools/verify_reference_kev_devtools.py).

## 1. Purpose

Provide new, dated evidence of the **current** integrity and independently reconstructed metrics of the 28 panels marked `absent_legacy_inline_audit` in the [historical fixed matrix](../experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json). This addresses defect 12/16 identity and measurement evidence; it feeds reference-result reporting, not a training gate. It does not create a historical finisher or change the original matrix, original audits, predictions, formulas or historical-binding fields. It is independent of the Open-Jev JEVal numerical-admission block.

## 2. Hypothesis

The current saved inputs, predictions, report/terminal identities and independent native/T1 calculations match the original fixed matrix. A mismatch rejects this new audit and is reported without modifying old evidence. The unconstrained optimum—trusting copied aggregate metrics or hashing only reports—would trivially agree while missing altered predictions. The counterpart is complete per-file scans, original input/payload/config verification, independent probability/logit and metric reconstruction, and negative tests that reject changed JSON, extra receipts, metric substitutions and incorrect container exits. This is an integrity audit, not an invariance or model-quality objective.

## 3. Setup

Seven retained runs, four panels each:

| Original run under reference_inference | Records | Questions | Population / panel scope |
| --- | ---: | ---: | --- |
| kev08_test_20261030 | 1,940 | 2,204 | decision-v7 and transfer-v4 clean, native/T1 |
| kev08_extended_20261030 | 1,274 | 2,024 | hard-v1 and documents-v1 clean, native/T1 |
| kev08_devtools_20261030 | 900 | 1,073 | devtools full/release, native/T1 |
| kev4_extended_20261030 | 1,274 | 2,024 | hard-v1 and documents-v1 clean, native/T1 |
| kev4_devtools_20261030 | 900 | 1,073 | devtools full/release, native/T1 |
| kev9_extended_20261030 | 1,274 | 2,024 | hard-v1 and documents-v1 clean, native/T1 |
| kev9_devtools_20261030 | 900 | 1,073 | devtools full/release, native/T1 |
| Total | **8,462** | **11,495** | **28 panels**, not independent repeats |

Original native temperatures, test splits, clean/full/release filters and accuracy/Brier/ECE10/NLL formulas remain fixed. Existing auditors require metric agreement within 1e-10; no new threshold is fitted. Devtools keeps the release drop policy and positional identities. Small populations under 30, exact 0/1 accuracy, constant probability vectors and metrics identical across all panels are flagged and retained.

The prepared plan enumerates **8,952 input files**, including all 8,462 inference receipts and 385 unique original config dependencies (about 30.9 GB, mostly shared model weights). It records current expected hashes for fixed matrix/code/report/terminal/old-audit material and original frozen dependency hashes; receipts additionally carry original payload/input hashes checked by the independent auditor. No long audit or NPU execution has occurred during preparation.

- Plan SHA-256: `0a5ccdb82f9a6a51c02642331133aff150361bf0032541d7381f0f2675b7cf43`.
- Driver SHA-256: `414e19c1ecdb7e7f4c8f86e97e683c683d1357f65a34dfd847906cd0a2dfcd46`.
- Image: `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.
- Container: `nga-e39-legacy-kev-reaudit-20261031-v1`; 2 CPU cores, 4 GiB host RAM, **0 accelerator chips**. These are isolation settings, not a reintroduction of the cancelled compute budget.
- Original CephFS and repository mounted read-only; only the unique new output directory is writable. Docker socket is read-only mounted, and code exclusively sends HTTP GET inspect for seven fixed full container IDs. No environment variables are captured.
- Exact launch/resume scripts reside beside `PLAN.json`. Launch on host 175 via `ssh npu bash <output>/LAUNCH_EXACT.sh`; detached, retained container, no `--rm`. Resume uses the same retained container and creates a new generation rather than overwriting earlier terminal files.

Each scan hashes actual file-descriptor bytes and checks descriptor/path identity before and after. JSON is parsed from those same checked bytes. Existing auditors' one direct test-JSONL text read is replaced in memory with the same checked-byte reader; their metric arithmetic remains unchanged. Audit code itself is hash-checked before executing its exact bytes.

Every file scan appends a durable journal entry. A restart reads and hashes bytes again; it does not reuse an mtime-only cache. Completed run arithmetic may be reused only after the full current input manifest, plan and same-read result digest match. Before/after input manifests, all original terminal/DONE bindings and actual retained original container exits are checked. New process generation terminals are separate from the original inference and from the new container's post-exit observation. Completion is not accepted until that actual new Docker exit is independently observed as 0.

## 4. Results at original pre-run registration

**Pending at registration; current results are in dated additions below.** Ten local adversarial unit tests passed for same-size JSON substitution, before/after changes, expected dependency hashes, metric tampering, container exit/wrapper identity, extra receipts, auditor replacement, file-descriptor/path substitution, real auditor loading and suspicious-success flags. These tests do not establish that the seven original runs pass the new audit.

The inventory found all seven original inference containers retained and exited/0, and all fixed matrix report/config/old-audit hashes matching; six runs have historical launch receipts. Kev-0.8B test has no historical launch receipt; its currently retained container can be observed, but no historical launch record will be manufactured. Current inventory is not the full 30.9 GB dependency or 8,462-receipt re-audit.

## 5. Verdict at original pre-run registration

No result verdict at registration; current results are in dated additions below. After parent review of the frozen implementation/plan, the authorised CPU audit can run. Expected acceptance requires 7 runs, 8,462 records, 11,495 questions and all 28 fixed matrix panels, complete before/after agreement, original exits and new actual exit, retained flags and dated output hashes. The original `absent_legacy_inline_audit` limitation remains even if E39 succeeds. No historical immutability, model rerun, no-contamination, training/business benefit, resource release or Open-Jev JEVal admission claim follows.

## 2026-10-31 07:27 Beijing dated launch

Parent current Codex session independently checked the frozen plan/artifact hashes and reran 10/10 tests, then authorised this fixed CPU launch. This is explicitly not a Fable or Astra review. `PARENT_REVIEW.json` records that scope. The retained detached container is `e56ed5ff92898c3a772643e3b990e14ab8192cc0d5bd7348b8ec281a4470fbc5`, started on host 175 with the exact frozen launch script; `STARTUP_CONTAINER.json` records its actual identity/state, no accelerator devices, no network, 2 CPU cores/4 GiB host memory and mount permissions. All original CephFS/repository evidence is read-only; only the new output directory is writable. No audit result or new Docker exit has yet been accepted.

Before any resume, verify the retained container ID/spec/exit and save previous terminals; the simple `RESUME_EXACT.sh` is not permission for blind restart. Every driver generation and failure remains inspectable.

## 2026-10-31 dated v1 startup failure

The first CPU container actually exited 1; generation `0001/COMPLETE.json` records failure at 0/8,952 inputs because host 175 does not contain the local repository path used for the matrix input. No audit metric was computed. The root-created atomic digest also had mode 0600; its structured contents were retrieved through read-only Docker copy and preserved in `FAILURE_DIAGNOSIS_READABLE.json`. No raw logs were needed. V1 files, container and terminal remain untouched. V2 will freeze a SHA-identical matrix copy in CephFS and use mode 0644 for new atomic reports; it requires a newly frozen plan and parent check before launch.

## 2026-10-31 dated v2 frozen preparation (not launched)

New directory: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e39_legacy_kev_current_reaudit_20261031_v2`. The original matrix is copied byte-for-byte into its `source/` directory; the plan binds both the original path/hash and the portable snapshot hash. The repository mount is removed. Host 175 independently confirmed all **8,952** input paths exist and the copied matrix hash matches; no large hash audit was performed by that check.

V2 PLAN SHA `6086f9a267f507999941ecb7a60944888c4df44808581e1901159c7d097c0823`; driver SHA `0e6ad29b8d28ccb4a6ec5d3152d773f34ba0e5a35af818b3b0885561d5ffeebc`. Atomic reports now set mode 0644 and the wrapper uses umask 022. Eleven local adversarial tests pass, including output readability. Other formulas, inputs, counts, read-only original-tree policy, no-NPU rule, generation retention and independent actual-exit requirement are unchanged. Parent review of the new frozen plan is pending; the v1 launch permission is not reused for an unreviewed plan.

## 2026-10-31 dated v2 launch

Parent current Codex independently verified the new plan, portable matrix identity, seven original run IDs, script/source hashes and read-only/no-NPU launch settings and reran 11/11 tests. `PARENT_REVIEW.json` records this approval scope. Exact v2 launch created retained container `19e04dc4e65e200b14e8958756015a5ed1da568482926181e66c17f31cbab968`; its actual startup metadata and mount checks are saved in `STARTUP_CONTAINER.json`. V1 remains inspectable. The host Docker timestamps and local observation timestamps are retained separately; no equality between different host clocks is assumed.

## 2026-10-31 dated v2 results

V2 generation 0001 completed at host UTC 2026-10-30T23:34:02Z; actual retained container `19e04dc4e65e200b14e8958756015a5ed1da568482926181e66c17f31cbab968` exited 0 at `2026-10-30T23:34:02.99185183Z`. [Full result and limits](../experiments/LEGACY-KEV-DATED-REAUDIT-RESULTS-2026-10-31.md) and [machine index](../experiments/LEGACY-KEV-DATED-REAUDIT-RESULTS-2026-10-31.json) record **7 runs, 8,462 records, 11,495 questions, 28 panels**, all metric comparisons within original 1e-10 tolerance and **8,952 before/after file identities unchanged**. No new flags were raised in the explicitly limited 28-panel/whole-suite screen; this does not cover every source/type/threshold subgroup.

Report SHA `1d2c08c6dfb67b5311253430967923494b59fc676d0907d4bbecd2234878f59c`; terminal SHA `8a004289695466cc2095cd3659ca73fb41b581f2701c50f6ec19d6116c360676`; actual exit SHA `c7a5e8b2c7381a37b73e65b88bc73d5a300125aea1c4daef164581e7c1f8e6ba`; manifest SHA `d1fa5881ed8bad32ef8f727c69b23d10ddcdadf18f9f90e7f1759ded34556b77`. Original fixed matrix remains `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`. All historical `absent_legacy_inline_audit` fields remain; the new dated verification is current integrity evidence only. V1 failure, source snapshots, every terminal generation and journals remain retained. No cached run audit was reused in v2 generation 0001. No NPU, new predictions, training or Open-Jev JEVal admission. Parent result acceptance remains separate from the completed CPU run.

## 2026-10-31 dated parent result verification

The current Codex parent independently verified terminal/report binding, equality of all 8,952 before/after entries, 7 audit result hashes, 8,462 records/11,495 questions/28 panels, unchanged legacy matrix and the actual new container exited 0. A separate actual Astra bounded result review is being prepared; no earlier Kev-4B/9B verdict is reused. The earlier parent-pending statements describe their publication snapshot.

## 2026-10-31 actual Astra bounded review prepared (not launched)

A unique E39 review bundle contains **8,930 files / 45,876,752 bytes**, including all 8,462 original receipts. Manifest SHA `dfcf9aa9355e2563895f2e489c92acac18523fbacbaefe47583c95bf257d9f58`. [Review status](../experiments/ASTRA-LEGACY-KEV-DATED-REAUDIT-REVIEW-2026-10-31.md) records the proposed actual `gpt-6-astra` invocation and prompt. The brief requires independent 28-panel arithmetic and reviews the exact new driver, in-memory text-read adapter, same-byte and descriptor/path checks, cache/generation semantics, v1 failure, saved actual exits and clock offset. Seventy-seven excluded dependencies are indexed; no external-weight/tokenizer re-reading claim follows. No review process or verdict exists yet, and no previous experiment review is reused.

## 2026-10-31 dated actual Astra launch

After parent independently verified all 8,930 bundle hashes/byte counts and the specific review scope, the new actual `codex exec --model gpt-6-astra --sandbox read-only` process started. Runner PID **1628131**, real CLI child PID **1628133**; both were observed alive, and the bounded digest reported reviewing. PROCESS.json records the exact command and manifest identity. No review verdict exists yet. This is independent of the E38 review, and does not reuse another result approval.

## 2026-10-31 actual Astra bounded review complete

Actual review completed at 2026-10-30T23:54:43.046664+00:00, real child/runner rc 0. [Full verbatim review](../experiments/ASTRA-LEGACY-KEV-DATED-REAUDIT-REVIEW-2026-10-31.md) supports bounded current-evidence and 28-panel publication after the [dated source-result note](../experiments/LEGACY-KEV-DATED-REAUDIT-RESULTS-2026-10-31.md). The original registration and prior result text are preserved as historical snapshots.

Required wording correction: frozen auditor bytes are verified then one source-read expression is replaced in memory before execution; per-file durable journals cover BEFORE/AFTER hash_phase only; cross-scan equality means saved path/SHA/bytes, while descriptor/stat identity is checked within each read. No metric changed, original matrix and 28 historical-binding labels remain. New erratum `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e39_legacy_kev_current_reaudit_20261031_v2/ERRATUM-ASTRA-SCOPE-20261031.md` SHA `61a0c621cad1af89b029f53b6695c684b35298c29a8194f958bef80ccdcc7885`.

The reviewer rehashed 8,930 bundle files and independently rebuilt all 28 panels, maximum matrix difference 1.1102230246251565e-16. It did not re-read 77 excluded dependencies or all 30.9 GB, rerun the 11 unit tests, exercise cache/restart/recovery, or query live Docker. Resume remains a manually guarded command, not verified unattended recovery. Subgroup observations (aegis n=25; transfer confidence>=.99 n=13 all correct; dbpedia14 80/80) preserve small/perfect-cell limitations without changing original headline flags. Review SHA `588a9431baa419735055b76943fef841a015cae9d2829fa9d9d28c2dd16bf6d0`, COMPLETE SHA `49c9584ba95b599df571f6ad93c223ef8b122faf284fcf8fceffc740ec3f1dac`.
