# E18 — Native Open-Jev-9B public test evaluation

Preregistered 2026-10-30 before test inference. Subject to successful E17 native probe and whole-test token preflight.

## Purpose and hypothesis

Measure the fixed released 9B checkpoint on the complete redistributable release-v2 test. Defect 12: measurement validity; defect 16: comparable evidence. The unconstrained optimum is memorizing exposed labels; a fixed-reference result alone does not prove generalization or NGA training benefit. Constant output can satisfy structural validation, so report per-source metrics and suspicious-success flags; aggregate accuracy is not consistency.

## Frozen setup

All 10,356 ordered test rows, raw SHA256 `0c4b953282a4292272110536ca543fe6e2736ab729b81d9b0464dd8ab4eec86a`; hard 9,995 and soft 361. This public projection omits 176 Wiki rows from the old 10,532-row full test. No truncation, sampling, skipping, prompt tuning, test temperature fitting or model selection.

Use Open-Jev-9B native package/checkpoint and Qwen/Qwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, bf16 backbone/float32 scalar head, unmerged LoRA, native SDPA, original candidate prompts, right padding, thinking disabled, max_length 4096. Saved serving temperature 1.8969118766347646, with separately reported raw T=1 from the same logits.

Native metrics: hard accuracy on exactly one-hot targets; expected accuracy, NLL (floor 1e-15), sum-squares Brier and expected Brier on all rows; expected Brier adds 1-sum(q²). ECE15 uses top-label confidence and expected correctness, first-argmax tie. Fixed coverage thresholds .5/.7/.8/.9/.95/.99; source and kind metrics and full hard/soft/failed denominators retained. Failure blocks whole-test success; incomplete probability results are not presented as full results.

## Execution and acceptance

Host 175, physical chip 1 after E17 exits and ownership/live-device checks; existing immutable image. Run `/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev9_test_20261030/`, retained CPU preflight `nga-reference-openjev9-lengths`, retained full inference `nga-reference-openjev9-test`. Freeze native source, driver, execution scripts, tokenizer/model files, data and manifest before preflight. Reuse reviewed E14 driver unchanged with 9B configuration. Preflight must verify all candidate lengths, terminal/wrapper/report hash and complete item receipts before test inference. Oversize blocks rather than truncates.

CephFS logs, heartbeat, per-chip throughput (one chip), reserved memory, per-item identity-bound receipts, output-hash-bound terminal and precise guarded relaunch are required. No automatic retry of recorded inference errors. Completion requires exact whole-test IDs/order/counts, zero failed rows, successful terminal and wrapper, exited container and independent primary metric recomputation. Scalar probe and test launch are not full-test completion; substantive Astra review is separate.

## Results

2026-10-30 execution: E17 completed with independently verified synthetic receipts and resource use. All 92 test dependency/executable files were frozen before CPU preflight. `nga-reference-openjev9-lengths` completed at 15:55:58Z; all 10,356 rows / 28,622 candidate prompts passed, maximum 724 tokens, zero overlength. Terminal rc 0, wrapper EXIT rc 0 and CPU container exited 0 agree.

Before launch, the frozen driver rechecked every dependency hash and length receipt, full manifest/source/kind counts, preflight report hash and terminal/wrapper. Under allocation flock, exited E17 ownership was transferred to E18 only after both completed containers and live device maps were checked. Full retained inference container `nga-reference-openjev9-test` was started on physical chip 1:
`f82bb8a54f431ddca6cb27cd7c7c3e319ee770351dbea8f278fd25f7a5065f45`.
`LAUNCH_RECEIPT.json` binds actual image/command/entrypoint/container, config and wrapper hashes. No final test result yet; independent audit is still required.

15:57:42Z structured heartbeat: inference 40/10,356, 2.17631 questions/s/chip, one chip, reserved 17.58789 GiB; container confirmed running.

## Verdict

Pending complete inference and independent audit. No new training launched.
