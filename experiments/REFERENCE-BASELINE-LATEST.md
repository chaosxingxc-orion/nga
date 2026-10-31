# 当前参考基线报告入口（最新）

更新时间：2026-10-31T02:15:00Z

这是当前参考基线阶段的最新报告入口。以后每个 milestone 完成后，新建带时间戳的报告并更新本文件；旧报告保留在归档目录或旧文件名中，只用于追溯，不作为当前事实权威。指标不得因刷新而改变；若指标、分母、公式或审查范围改变，必须新建代次并明确变更。

## 当前阶段

- D1 范围已由项目负责人确认：只收口当前登记的 **38 个模型×数据集组合**，不扩展完整笛卡尔积。
- 当前已有 **36 个结果组合**，另有 Open-Jev-2B×JEVal、Open-Jev-9B×JEVal 两个 `blocked/null` 单元。
- 参考面板仍按数据集、公式、温度、hard/soft 目标和有效分母分别报告；不做跨协议总平均。
- 最新数字入口：[`REFERENCE-BASELINE-MATRIX-2026-10-31.json`](REFERENCE-BASELINE-MATRIX-2026-10-31.json) 和 [`REFERENCE-BASELINE-INCREMENT-2026-10-31.json`](REFERENCE-BASELINE-INCREMENT-2026-10-31.json)。本次 milestone 没有修改这些读数。
- 机器索引 SHA256：matrix JSON `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`；increment JSON `fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`。

## 当前阻塞和下一步

Open-Jev 两个 JEVal 单元仍受 E38 数值准入阻塞。2B E38 v7 诊断已完成，但 chip 4 尚未释放；9B 必须串行等待 release-only Astra 复审通过、实际容器退出、空设备查询和 allocation 独立核验后启动。该工程门禁不改变已有参考读数。

为满足持续保持 NPU 满载的工程原则，在等待 chip 4 release 审查时，CPU 准备、审查包制作、纯 CPU 回归和报告整理并行推进；不使用未经审查的 NPU 任务占用设备，也不把瞬时 `npu-smi` 空闲误判为可分配。当前 175 实时核验显示 8 张卡均无运行进程，但 allocation 仍保留既有所有权记录，不能据此手工释放。

## 归档规则

每个 milestone 完成后：

1. 新建 `REFERENCE-BASELINE-REPORT-<UTC timestamp>.md`；
2. 写入本次 milestone、读数入口、公式/分母、结果状态、flags、审查范围和机器索引 SHA；
3. 用本文件更新“最新入口”，只改变入口指针，不重写历史报告；
4. 若读数不变，明确写 `metric values unchanged`；若变化，必须说明原因、旧值和新值，并生成新的机器索引代次。

本文件是当前阅读入口；历史矩阵和旧报告是查询材料，不替代当前入口。

