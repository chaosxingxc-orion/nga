# Jev 工程与实验最新状态（2026-11-05）

> 事实截点：2026-11-05 约 02:42 UTC；运行状态是观察快照，完成和科学验收须以终态、释放记录及独立复核为准。项目仍在推进，同 TEST 训练收益尚无结论。

## 当前状态

- 固定基座 Qwen3.5 四规格 × 28 个已登记面板为 **112/112 验收**，其中 Jev-bench 88/88；大候选五任务 × 四规格 20/20 完成并验收。这是固定面板清单，不是完整异构模型 × 数据集 × 协议 NxM 的完成。D1 异构参考层 38 格中 36 格有结果，2 个 Open-Jev × JEVal 为 `blocked/null`；不合并不等价协议。冻结数字见 `experiments/REFERENCE-BASELINE-LATEST.md`。
- 0.8B LoRA 七成员最终同 TEST 在 host 175 的 chip 0–6 运行，约 02:30 UTC 已观察启动；运行不等于完成、独立复核或科学验收。真实 Astra 精确 UID 交接复审 PASS，范围和限制见本地审查；尚无同 TEST 收益。此前 DEV 平均约 82.397152%（对 K0 +24.011076 pp），transfer 平均约 65.167683%（+4.649390 pp），只是诊断。
- 9B 交叉候选行为 DEV 已完成 672/672，runtime 和 host EXIT 0，chip 7 已释放；CPU 对保留的受限 logits、softmax、argmax 和 receipts 重建 PASS。探索组 0–3 的独立分析显示 K=28/77/151 语义准确分别为 18/32、8/32、8/32，均未通过完整预登记筛选。冻结的探索决定为否定：不提升未改动接口、不选择 K 或调整阈值；已登记 confirmation 可按原协议作为独立诊断运行，尚无确认结果。该 DEV 不证明业务或训练收益。
- 0.8B 行为 DEV 后继已在 chip 7 启动（host PID 3644197，container `3df2320022f6`）；2B/4B 按顺序排队，自动接续队列正在准备，仍为 **PREPARATION only**，不能声称已部署或已启动。
- 新 task graph 为 28 节点（11 NPU、17 CPU），仅规划及状态记录，不具备派发权限。实时设备状态须重新核验；不将排队、运行、终态和接受混为一谈。

## 证据与下一步

七成员精确审查：`.local/reviews/final-uid-followup-astra-20261105-v1/REVIEW.md`；执行包：`/mnt/cephfs/xingchao/experiments/jev/r3_runs/final_uid_handoff_repair_20261105_v2/package/`，输出在 `final_test_seven_20261104_v2/runs`。9B CPU 摘要和冻结决定在 `/mnt/cephfs/xingchao/experiments/jev/r3_runs/interface_cpu_continuation_20261105_v1/`；探索分析为 `.local/reviews/interface9b-exploration-sol-20261105-v1/ANALYSIS.md`。这些过程材料保留本地或 CephFS。

继续使用脚本摘要及终态证据监控，完成后独立重建和验收七成员同 TEST；按冻结决定处理 9B confirmation，并在实际前序释放及各自准入后推进后继。任何 TEST 收益须待完整结果及预登记比较复核，不从当前运行状态推断。
