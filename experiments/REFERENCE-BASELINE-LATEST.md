# 当前参考基线报告入口（最新）

更新时间：20261031T033450Z

最新累计报告：[REFERENCE-BASELINE-REPORT-20261031T033450Z.md](REFERENCE-BASELINE-REPORT-20261031T033450Z.md)。

这是当前参考基线阶段的最新报告入口。以后每个 milestone 完成后，新建带时间戳的报告并更新本文件；旧报告保留在归档目录或旧文件名中，只用于追溯，不作为当前事实权威。指标不得因刷新而改变；若指标、分母、公式或审查范围改变，必须新建代次并明确变更。

## 当前阶段

- D1 范围已由项目负责人确认：只收口当前登记的 **38 个模型×数据集组合**，不扩展完整笛卡尔积。
- 当前已有 **36 个结果组合**，另有 Open-Jev-2B×JEVal、Open-Jev-9B×JEVal 两个 `blocked/null` 单元。
- 参考面板仍按数据集、公式、温度、hard/soft 目标和有效分母分别报告；不做跨协议总平均。
- 最新数字入口：[`REFERENCE-BASELINE-MATRIX-2026-10-31.json`](REFERENCE-BASELINE-MATRIX-2026-10-31.json) 和 [`REFERENCE-BASELINE-INCREMENT-2026-10-31.json`](REFERENCE-BASELINE-INCREMENT-2026-10-31.json)。本次 milestone 没有修改这些读数。
- 机器索引 SHA256：matrix JSON `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`；increment JSON `fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`。
- 最新工程 milestone：0.8B K1 preflight 在 chip 1 完成 3 个 optimizer steps，Docker exit 0、`DONE rc=0`、heartbeat 和每步吞吐均有记录；随后已按终态证据释放 chip 1。该 smoke 不属于测试集指标，也不构成 Jev 收益。

## 当前阻塞和下一步

Open-Jev 两个 JEVal 单元仍受 E38 数值准入阻塞。2B E38 v7 诊断已完成，但 chip 4 尚未释放；9B 必须串行等待 release-only Astra 复审通过、实际容器退出、空设备查询和 allocation 独立核验后启动。该工程门禁不改变已有参考读数。

2026-10-31 补充：E38 完成后仍须独立证明完整 JEVal 路径的数值与内存准入，不能直接从诊断成功跳到 full-test。2B 首个差异位于第一层 `in_proj_qkv` 输出；9B 最大实际输入在生命周期清理后仍有约 59.4 GiB 的某阶段 core-only 估算，未计权重和其他分配。后续按 [准入路线](OPENJEV-JEVAL-NEXT-ADMISSION-2026-10-31.md) 准备保持完整计算形状的候选实验，原始 `candidate_batch_admission=false` 不变。当前没有新测试分数。

为满足持续保持 NPU 满载的工程原则，在等待 chip 4 release 审查时，CPU 准备、审查包制作、纯 CPU 回归和报告整理并行推进；不使用未经审查的 NPU 任务占用设备，也不把瞬时 `npu-smi` 空闲误判为可分配。chip 1 的空闲记录已通过真实 detached smoke、容器退出和 guarded release 形成可复核证据；其余 owner 仍不能由瞬时空闲状态推断为 free。

## 测试集优先规则

参考模型对外和业内对齐的主指标统一来自各数据集冻结的 **test split**。development/calibration 只用于配方诊断、工程效率测量、阈值拟合和训练前门槛；不得用 dev 数字替代 test 指标，也不得在读取 test 后调整训练方案。不同论文公式、温度、有效分母和 hard/soft 目标继续并列统计。

## 归档规则

每个 milestone 完成后：

1. 新建 `REFERENCE-BASELINE-REPORT-<UTC timestamp>.md`；
2. 写入本次 milestone、读数入口、公式/分母、结果状态、flags、审查范围和机器索引 SHA；
3. 用本文件更新“最新入口”，只改变入口指针，不重写历史报告；
4. 若读数不变，明确写 `metric values unchanged`；若变化，必须说明原因、旧值和新值，并生成新的机器索引代次。

本文件是当前阅读入口；历史矩阵和旧报告是查询材料，不替代当前入口。

