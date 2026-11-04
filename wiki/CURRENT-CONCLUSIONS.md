# Current Conclusions

Updated: 2026-11-04  
Authority: this page is the current collaboration summary. Detailed procedures, run logs, receipts and intermediate reviews remain in the local dated archive and CephFS. Historical versions are available through Git history.

## Current position

The fixed reference base is locked for the registered TEST matrix. The next crossed-candidate interface DEV is prepared but has not been launched. Numerical admission has completed on four Qwen3.5 sizes; this validates execution consistency only and is not a scientific gain or business result.

The 175 host currently has no active NPU allocation. All eight chips are free in the allocation ledger. This idle interval is caused by the behavior-DEV execution gate, not by completion of the Cartesian product or training program.

## Frozen reference and direct-drive results

- Qwen3.5 0.8B/2B/4B/9B × 28 registered panels: **112/112 cells accepted**.
- Jev-bench subset: **88/88 cells accepted**.
- D1 heterogeneous reference layer: **36/38 model×dataset units scored**; Open-Jev-2B×JEVal and Open-Jev-9B×JEVal remain `blocked/null`.
- Five large candidate TEST tasks × four model sizes: **20/20 cells completed**, independently rescored on CPU.
- The five-task accuracy table and protocol-specific metrics are authoritative in [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md). Hard/soft targets, native temperature versus raw T=1, Brier variants, calibration metrics and denominators remain separate.

## Training status

The 0.8B LoRA DEV qualification and seven-member candidate assembly are complete. DEV mean is about 82.397152% (+24.011076 pp versus K0); transfer mean is about 65.167683% (+4.649390 pp). These are DEV/transfer diagnostics and are **not** same-TEST training gains.

The seven-member same-TEST evaluation is still blocked. The final admission requires a real `independent_astra` review using `gpt-6-astra` with a substantive `PASS` file. Dispatch acknowledgements without a review artifact do not satisfy this gate.

## Latest NPU experiment: numerical interface admission

Run root: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/large_candidate_interface_execution_20261104_v2/`

| Model | Forwards | Variants | Raw exact | Scientific acceptance | TEST read | Chip / reserved |
| --- | ---: | ---: | --- | --- | --- | --- |
| Qwen3.5-0.8B | 144/144 | 3/3 | true | false | false | 0 / 3.7695 GiB |
| Qwen3.5-2B | 144/144 | 3/3 | true | false | false | 1 / 8.1387 GiB |
| Qwen3.5-4B | 144/144 | 3/3 | true | false | false | 2 / 18.4023 GiB |
| Qwen3.5-9B | 144/144 | 3/3 | true | false | false | 3 / 36.2734 GiB |

Each report has `completed_items=144`, `passes=3`, `reused_items=0`, `all_raw_exact=true`, `scientific_acceptance=false` and `test_read=false`. Host claim, run exit, release and container evidence exist for all four jobs. An independent CPU audit is pending before these results can be sealed as formal numerical-admission PASS.

## Behavior DEV gate

The behavior package contains 672 requests per model, 2,688 forwards total. It has fixed candidate order and mapping, semantic discrimination controls, full-vocabulary checks, float32, HF32 off, batch 1, max length 8192, item-level resume and 600-second watchdog configuration. The preparation audit verdict is `PASS_PREPARATION_ONLY_NOT_EXECUTION_AUTHORITY`.

Launch remains blocked until all of the following are present:

1. Independent CPU audit of the four numerical reports.
2. Formal numerical-admission PASS artifacts and refreshed behavior-plan hashes.
3. Fresh prospective behavior review and resource binding.
4. Parent execution review, then detached launch with claim/heartbeat/exit/release evidence.

## Next execution order

1. Seal or reject numerical admission from the independent audit.
2. Regenerate and re-review the four behavior plans.
3. Claim fresh chips from the ledger and launch the 2,688-forward behavior DEV as detached FIFO work.
4. Run CPU scoring and diagnostics asynchronously with multithreaded scripts; watchdog polling remains event-driven or about every 600 seconds.
5. Use preregistered DEV gates to select candidates. Only after a real Astra substantive PASS may the final seven-member same-TEST evaluation start.
6. After the stable base is closed, add missing business-task datasets and then design RL optimization and baselines.

## Evidence pointers

- Current detailed status: [`experiments/STATUS-LATEST-2026-11-04.md`](../experiments/STATUS-LATEST-2026-11-04.md)
- Frozen baseline: [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md)
- Numerical execution root: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/large_candidate_interface_execution_20261104_v2/`
- Allocation ledger: `/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json`
- Preparation review: `.local/reviews/interface-dev-independent-20261104-v1/REVIEW.md`
- Final admission tool: [`tools/r3_final_admission.py`](../tools/r3_final_admission.py)

The terms “numerical admission”, “behavior DEV”, “same-TEST scientific acceptance” and “business gain” are separate states. Current work has reached numerical execution completion, but not behavior-DEV execution or training-gain acceptance.
