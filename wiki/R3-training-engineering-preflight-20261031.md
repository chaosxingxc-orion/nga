# R3：Qwen3.5-0.8B 训练入口工程 preflight（2026-10-31）

## Purpose

在正式 Jev 训练和测试集读取之前，验证 175 上固定 Ascend 镜像、Qwen3.5-0.8B-Base、decision-v7 训练数据、K1 LoRA 入口和资源回收链能够完成一个短 detached smoke。该实验只验证工程路径，不产生正式训练收益或测试集指标。

## Preregistered setup

- Host: 175 (`k8s-node1`), physical chip 1。
- Image: `nga-verl-qwen35-v030:20261029`，reference kernel，`PYTORCH_NPU_ALLOC_CONF=expandable_segments:True`。
- Model: `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base`。
- Data: `/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl`，15,576 base questions。
- Training arm: K1 LoRA，seed 2，186 LoRA pairs，gradient checkpointing，`micro_tokens=12000`，`--stop-after 3`，`--no-merge`。
- Output: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/preflight_k1_08b_chip1_20261031/`。
- Test split was not read. No formal checkpoint was selected.

## Evidence

- Container: `nga-r3-preflight-k1-08b-chip1-20261031`，ID `41d5ac525602d8a7143730a6c0fad0b4835285fe7ca662dac495ccd6058dcf21`。
- Docker exit: `0`；terminal marker `DONE`: `rc=0 utc=2026-10-31T02:32:25Z`。
- Completed steps: 3/3；manifest reports `lora_pairs=186` and `base_questions_per_epoch=15576`。
- Heartbeat and progress include per-chip throughput, questions/s/chip, reserved GiB and chip count。
- After verifying terminal and retained container exit, guarded release wrote `RELEASE_INTENT.json` and `RELEASED.json`; chip 1 returned to `CHIP-ALLOCATION.json` `free[]`。

## Result and verdict

**工程 preflight PASS。** The model loaded, the fixed data path was consumed, NPU forward/backward and optimizer steps completed, the detached wrapper emitted heartbeat/terminal evidence, and the resource release was recorded. This does not establish a training improvement, a test-set score, a reference-paper match, or permission to start the formal training wave.

## Limitations and next action

Only three optimizer steps were run; no dev or test score was computed, no adapter was selected, and no multi-seed stability conclusion is possible. The next scientific milestone remains the frozen public test-set reference report. Formal training requires the D1 test report, frozen seeds/controls, and the remaining Astra release gate for E38; development data remains diagnostic only.

