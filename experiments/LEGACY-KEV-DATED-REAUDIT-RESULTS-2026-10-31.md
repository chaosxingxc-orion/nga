# E39 — new dated CPU re-audit of 28 legacy Kev reference panels

**Current publication status: actual Astra bounded review is complete, with the dated clarifications below.** The original CPU-result text is retained as its publication snapshot; no original metrics or frozen evidence were changed.

**All 28 fixed panels were independently reconstructed from the current saved evidence; no metric changed.** The new CPU run completed 7 original runs, 8,462 record receipts and 11,495 questions. Its 8,952-file before/after manifests match exactly, and the retained new container actually exited 0. This adds evidence of current integrity; all 28 original `absent_legacy_inline_audit` labels and the old matrix remain unchanged. The current Codex parent independently verified the result bindings and actual exit; a separate actual Astra bounded result review is being prepared.

Recorded locally: 2026-10-30T23:38:05.395478+00:00. Host 175 terminal time: 2026-10-30T23:34:02Z; actual Docker FinishedAt: 2026-10-30T23:34:02.99185183Z. The host clock was approximately 98 seconds behind the local observation clock; both original timestamps are preserved.

## Scope and checks

This CPU-only run rehashed the original frozen dependencies, including model weight bytes, and independently checked original test identities, expected sets, receipt payload/input/config hashes, probabilities/logits and native/T1 accuracy, Brier, ECE10 and NLL. It compared all 28 matrix entries within the existing 1e-10 tolerance. Full/release populations remain distinct; temperatures and filters were not selected again. Defects 12/16 concern provenance and measurement; copying aggregates alone is the degenerate solution, countered here by complete receipt and input reconstruction.

The complete input manifest contains **8,952 files / 30,910,366,106 bytes**. Two full scans match; audit-side dependency checks additionally verify the original frozen hashes. Every file read checks its actual descriptor and path identity, and parsed JSON/source text uses the same bytes whose digest was verified. Journal entries and completion generations are retained. No run resumed from cached arithmetic in this successful generation. Original seven retained inference-container identities, commands, images and exited/0 states were checked using Docker HTTP GET only; all saved observations are bound in the JSON index.

| Metric population | Native/T1 accuracy | Brier/ECE10/NLL |
| --- | --- | --- |
| Kev-0.8B decision-v7 and transfer-v4 clean | independently reconstructed and matched | independently reconstructed and matched |
| Three Kev sizes hard-v1 and documents-v1 clean | independently reconstructed and matched | independently reconstructed and matched |
| Three Kev sizes devtools-v1 full and release | independently reconstructed and matched | independently reconstructed and matched |

The machine record retains all 28 panel values and original matrix row indices. These are the same measurements already reported, not 28 new inference experiments or new benchmark gains.

## Retained flags and evidence limitations

The new 28-panel screen produces no flags for n<30, accuracy exactly 0/1, an identical metric across every panel, or a constant probability vector across a whole suite. All individual panel denominators and values remain in the JSON. Zero flags in this scope says nothing about every source/type/threshold subset, data contamination, historical immutability or model generalization.

The original old audits, report/terminal files and matrix are unchanged. In particular, a newly dated successful terminal cannot prove that the old inline audit SHA was bound by a historical finisher. The older result evidence still carries `absent_legacy_inline_audit`. Current weight-byte matching does not rerun the model or independently establish the original execution's numerical behavior.

## Execution and hash evidence

The successful retained container is `19e04dc4e65e200b14e8958756015a5ed1da568482926181e66c17f31cbab968`, image `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`, 0 accelerator chips, 2 CPU cores and 4 GiB host RAM. There is no per-chip throughput because this is a CPU evidence audit. Original CephFS is mounted read-only; only the unique new output directory is writable. The launch uses no network or accelerator devices. `PARENT_REVIEW.json` records the current Codex parent's plan review and independent 11/11 regression tests, explicitly not Fable/Astra.

| Evidence | SHA-256 |
| --- | --- |
| Frozen PLAN.json | `6086f9a267f507999941ecb7a60944888c4df44808581e1901159c7d097c0823` |
| Exact driver | `0e6ad29b8d28ccb4a6ec5d3152d773f34ba0e5a35af818b3b0885561d5ffeebc` |
| Current re-audit report | `1d2c08c6dfb67b5311253430967923494b59fc676d0907d4bbecd2234878f59c` |
| New generation COMPLETE.json | `8a004289695466cc2095cd3659ca73fb41b581f2701c50f6ec19d6116c360676` |
| Actual new container exit | `c7a5e8b2c7381a37b73e65b88bc73d5a300125aea1c4daef164581e7c1f8e6ba` |
| Before and after manifest (equal) | `d1fa5881ed8bad32ef8f727c69b23d10ddcdadf18f9f90e7f1759ded34556b77` |
| Original fixed matrix (unchanged) | `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e` |

Directory: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e39_legacy_kev_current_reaudit_20261031_v2`. [JSON artifact index and full panel values](LEGACY-KEV-DATED-REAUDIT-RESULTS-2026-10-31.json) bind the report, terminals, actual exits, code, plan and manifests. [E39 wiki](../wiki/E39-legacy-kev-current-reaudit-20261031.md) records the purpose before launch and all dated corrections.

V1 remains retained with actual exit 1 and generation 0001 failure at 0/8,952: the local repository matrix path was absent on host 175. V2 froze a SHA-identical portable matrix snapshot and made root-created atomic outputs readable with 0644. No original reference data was rewritten, no metric changed and no NPU run was launched.

This result does not establish historical binding, all upstream diagnostics, contamination exclusion, paired consistency, training/business gain, resource release or Open-Jev JEVal admission. It does not change the 36 result-combination count or the 2 blocked JEVal units.

## 2026-10-31 actual Astra review and dated clarifications

The [full actual review](ASTRA-LEGACY-KEV-DATED-REAUDIT-REVIEW-2026-10-31.md) supports bounded publication after the following clarifications. Runner and real child both exited 0. The reviewer independently rebuilt all 28 panels from original receipts; maximum absolute difference from the original matrix was 1.1102230246251565e-16. This is an independent new review, not inherited approval.

1. The driver verifies the frozen original auditor source bytes, then performs one bounded in-memory replacement of the direct test.jsonl text-read expression and compiles the modified source. It does not execute the original auditor bytes unchanged. Actual Astra AST comparison confirmed that build_rows, softmax and metric mathematics were unchanged; its independent reconstruction from original receipts establishes the metric result.
2. Durable per-file journal entries apply to the BEFORE/AFTER hash_phase scans. Additional auditor dependency digests and JSON/source reads are not each individually journaled. No claim of journaling every read is made.
3. Equal before/after manifests prove equality of saved path-to-SHA256/byte-count entries. File-descriptor/stat identity is checked within each read; inode/mtime/ctime identity is not stored and compared across the two full scans.

The successful v2 generation 0001 reused no cached arithmetic. Cache reuse, restart, crash and recovery paths were not executed by the actual reviewer, who did not rerun the 11 unit tests. RESUME_EXACT.sh only runs docker start by name; its required prior container ID/spec/exit checks and saved terminal observations remain manual, documented conditions. This result does not establish verified unattended safe recovery.

The reviewer independently rehashed 8,930 bundle files / 45,876,752 bytes and rebuilt 11,495 questions from all 8,462 original receipts. Of the original 8,952 scan inputs, 8,875 files / 31,876,988 bytes were included and re-read; 77 inputs / 30,878,489,118 bytes were excluded. Exclusions include weights, tokenizers/configs and some development inputs. E39 saved full-scan records cover 30,910,366,106 bytes; the actual review did not independently read all those bytes.

Zero new headline flags applies to the original 28 fixed panels and whole-suite constant-vector screen only. Additional reviewer observations retain subgroup limits: devtools aegis_category has 25 questions (correct 22/23/21 for 0.8B/4B/9B); 0.8B transfer clean at native confidence>=0.99 selects 13 questions, all correct; 0.8B decision dbpedia14 is 80/80. These are reviewer diagnostics, not new preregistered inference panels, and do not change any headline metric or original flag count.

All 28 absent_legacy_inline_audit labels remain unchanged. No historical finisher reconstruction, historical immutability, no-contamination, model/tokenization/device rerun, training/business gain, resource release, or Open-Jev JEVal admission follows.

Additive erratum SHA `61a0c621cad1af89b029f53b6695c684b35298c29a8194f958bef80ccdcc7885`.
