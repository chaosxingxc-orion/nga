# 当前参考基线报告入口（最新）

更新时间：20261031T062902Z

最新累计报告：[REFERENCE-BASELINE-REPORT-20261031T062902Z.md](REFERENCE-BASELINE-REPORT-20261031T062902Z.md)。

这是当前参考基线阶段的最新报告入口。以后每个 milestone 完成后，新建带时间戳的报告并更新本文件；旧报告保留在归档目录或旧文件名中，只用于追溯，不作为当前事实权威。指标不得因刷新而改变；若指标、分母、公式或审查范围改变，必须新建代次并明确变更。

## 当前阶段

- D1 范围已由项目负责人确认：只收口当前登记的 **38 个模型×数据集组合**，不扩展完整笛卡尔积。
- 当前已有 **36 个结果组合**，另有 Open-Jev-2B×JEVal、Open-Jev-9B×JEVal 两个 `blocked/null` 单元。
- 参考面板仍按数据集、公式、温度、hard/soft 目标和有效分母分别报告；不做跨协议总平均。
- 最新数字入口：[`REFERENCE-BASELINE-MATRIX-2026-10-31.json`](REFERENCE-BASELINE-MATRIX-2026-10-31.json) 和 [`REFERENCE-BASELINE-INCREMENT-2026-10-31.json`](REFERENCE-BASELINE-INCREMENT-2026-10-31.json)。本次 milestone 没有修改这些读数。
- 机器索引 SHA256：matrix JSON `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`；increment JSON `fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`。
- 最新工程 milestone：E40 已完成 NPU 对照、独立 CPU 验证、实际 Astra 结果 PASS 和资源释放；固定输入上 L1/L1L2 完整输出 exact、peak allocated 降低约 1.42%，reserved 不变。此前 0.8B 三步训练入口 preflight 仍仅是工程预检，不属于正式训练或测试集收益。

## 当前阻塞和下一步

Open-Jev 两个 JEVal 单元仍受完整路径数值与内存准入阻塞。实际 Astra release v4 已对精确 v6 工具代码及拟议证据给出 PASS。2B 资源已通过 guarded release 释放，9B v7 已于 UTC 03:40:15 实际启动并完成 8/8 项诊断，NPU 于 03:44:24 exited/0；独立 CPU verifier 于 03:45:29 exited/0。

两尺寸首个不同观测事件均为第一层 `in_proj_qkv` 输出；9B 最大 logits/probability/wire 差为 0.13169223070144653 / 0.013869159693189886 / 0.01485981395698921，decision 未变，`candidate_batch_admission=false` 不变。9B 资源已释放并独立核对，free=[1,4]；有界 Astra 结果审查已 PASS，仅支持诊断与冻结资源证据。没有新增 JEVal 分数或训练收益。

E40 v3 已通过实际代码/计划审查并完成 NPU 8/8 对照、独立 CPU 验证与 chip 1 释放。L1/L1L2 完整输出 exact，单输入 peak allocated 节省 56.251953125 MiB（1.422531%），reserved 不变；L2 单独无改善。没有普遍提速、完整 JEVal 或训练收益结论；结果实际 Astra 有界审查已 PASS。下一阶段 9B/4200 和 2B/8409 的完整形状对照已冻结计划，11 项派生/协议检查及 39 项释放测试通过，实际代码/计划审查已 BLOCK：2B 的预测校验器仍限定 15 候选，9B 的 owner 恢复仍限定 chip 1；两处正在修复，旧冻结计划未启动。释放工具代码已获有界 PASS，新计划需重新绑定。

当前 free=[4,1]，本项目 NPU 容器均已退出；持续满载尚未实现。最新累计报告收录全部既有参考表格及新增工程证据，主测试指标不变。

## 最新工程调度决定

按用户明确要求：NPU 满载与实验效率最高同时执行。NPU 任务队列持续消费；独立验证、结果分析、基线锁定和报告走有序异步 CPU 队列，不再串行阻塞下一项独立 NPU 实验。资源交接与科学验收分开，未验收结果保持 pending。当前正在实现队列与最小操作交接支持；E41 审查发现的两处执行常量遗漏同时修复，旧计划未启动。详见 [当前执行规则](../proposal/08-task-status-decisions-and-next-plan-current.md#7-npu-满载与实验效率异步执行规则用户明确修订)。

## 测试集优先规则

参考模型对外和业内对齐的主指标统一来自各数据集冻结的 **test split**。development/calibration 只用于配方诊断、工程效率测量、阈值拟合和训练前门槛；不得用 dev 数字替代 test 指标，也不得在读取 test 后调整训练方案。不同论文公式、温度、有效分母和 hard/soft 目标继续并列统计。

## 归档规则

每个 milestone 完成后：

1. 新建 `REFERENCE-BASELINE-REPORT-<UTC timestamp>.md`；
2. 写入本次 milestone、读数入口、公式/分母、结果状态、flags、审查范围和机器索引 SHA；
3. 用本文件更新“最新入口”，只改变入口指针，不重写历史报告；
4. 若读数不变，明确写 `metric values unchanged`；若变化，必须说明原因、旧值和新值，并生成新的机器索引代次。

本文件是当前阅读入口；历史矩阵和旧报告是查询材料，不替代当前入口。

