# Current Conclusions

Updated: 2026-11-05
Authority: this page is the current collaboration summary. Detailed procedures, run logs, receipts and intermediate reviews remain in the local dated archive and CephFS. Historical versions are available through Git history.

## Current position

As observed around 2026-11-05 02:30 UTC, the seven final same-TEST runs are running on host 175 chips 0–6 following authentic exact UID-handoff Astra PASS. Running is not completion or scientific acceptance; no same-TEST training gain is established. The fixed 112 panels are a registered local inventory, not completion of the heterogeneous model × dataset × protocol matrix.

9B crossed-interface DEV completed 672/672 with runtime and host EXIT 0 and chip 7 release. Restricted-output CPU reconstruction passed. Exploration was negative for the unchanged interface at all registered K; the frozen decision permits registered confirmation as an independent diagnostic, with no selection or threshold change. The 0.8B successor has started on chip 7; 2B/4B are queued and their automatic continuation is preparation only, not deployed. The new 28-node graph (11 NPU, 17 CPU) is planning only.

## Frozen reference and direct-drive results

- Qwen3.5 0.8B/2B/4B/9B × 28 registered panels: **112/112 cells accepted**.
- Jev-bench subset: **88/88 cells accepted**.
- D1 heterogeneous reference layer: **36/38 model×dataset units scored**; Open-Jev-2B×JEVal and Open-Jev-9B×JEVal remain `blocked/null`.
- Five large candidate TEST tasks × four model sizes: **20/20 cells completed**, independently rescored on CPU.
- The five-task accuracy table and protocol-specific metrics are authoritative in [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md). Hard/soft targets, native temperature versus raw T=1, Brier variants, calibration metrics and denominators remain separate.

## Training status

The 0.8B LoRA DEV qualification and seven-member candidate assembly are complete. DEV mean is about 82.397152% (+24.011076 pp versus K0); transfer mean is about 65.167683% (+4.649390 pp). These are DEV/transfer diagnostics and are **not** same-TEST training gains.

The seven-member same-TEST evaluation is running after the authentic exact-plan UID-handoff review PASS; results and independent acceptance remain pending. It is independent of crossed-interface behavior DEV.

## Latest NPU experiment: numerical interface admission

Run root: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/large_candidate_interface_execution_20261104_v2/`

| Model | Forwards | Variants | Raw exact | Scientific acceptance | TEST read | Chip / reserved |
| --- | ---: | ---: | --- | --- | --- | --- |
| Qwen3.5-0.8B | 144/144 | 3/3 | true | false | false | 0 / 3.7695 GiB |
| Qwen3.5-2B | 144/144 | 3/3 | true | false | false | 1 / 8.1387 GiB |
| Qwen3.5-4B | 144/144 | 3/3 | true | false | false | 2 / 18.4023 GiB |
| Qwen3.5-9B | 144/144 | 3/3 | true | false | false | 3 / 36.2734 GiB |

Each report has `completed_items=144`, `passes=3`, `reused_items=0`, `all_raw_exact=true`, `scientific_acceptance=false` and `test_read=false`. Host claim, run exit, release and container evidence exist for all four jobs. Full-vocabulary operands were persisted for numerical admission. The host-ready plans bind the admission evidence; no new NPU generation is needed for that verification.

## Behavior DEV and next steps

The registered package has 672 requests per model with semantic discrimination controls. 9B completed and its restricted-output reconstruction passed. Exploration semantic accuracy was 18/32, 8/32 and 8/32 at K=28, 77 and 151; no K met the complete screen. The frozen negative exploratory decision permits confirmation only under the unchanged registered protocol as an independent diagnostic. No confirmation outcome is claimed.

The 0.8B successor started on chip 7 (PID 3644197; container `3df2320022f6`). The 2B and 4B successors are queued; their automatic continuation is still preparation only. Monitor the seven TEST runs and successors through bounded digests, reconcile terminals and releases, and independently reconstruct results before acceptance.

## Evidence pointers

- Current detailed status: [`experiments/STATUS-LATEST-2026-11-04.md`](../experiments/STATUS-LATEST-2026-11-04.md)
- Frozen baseline: [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md)
- Numerical execution root: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/large_candidate_interface_execution_20261104_v2/`
- Allocation ledger: `/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json`
- Preparation review: `.local/reviews/interface-dev-independent-20261104-v1/REVIEW.md`
- Final admission tool: [`tools/r3_final_admission.py`](../tools/r3_final_admission.py)

The terms “numerical admission”, “behavior DEV”, “same-TEST scientific acceptance” and “business gain” are separate states. The 9B exploration is a negative DEV diagnosis; confirmation and same-TEST training-gain acceptance remain pending.

Snapshot sources: `.local/reviews/final-uid-followup-astra-20261105-v1/REVIEW.md`; `.local/reviews/interface9b-exploration-sol-20261105-v1/ANALYSIS.md`; Ceph `interface_cpu_continuation_20261105_v1/digest.md` and `FROZEN-EXPLORATION-DECISION.json`. Process evidence remains local or on CephFS.
