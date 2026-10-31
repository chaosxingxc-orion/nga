# 参考基线工程 milestone：release 修复与下一步数值/内存准入

时间：20261031T032919Z

## 当前累计进度

当前登记范围仍为 38 个模型×数据集组合，36 个已有保存结果，Open-Jev-2B/9B×JEVal 两个仍为 blocked/null。旧矩阵的 58 是其历史计分面板数，不是把后续 JEVal/OOD 增量相加后的统一面板总数。原始 test、OOD、不同公式/温度、hard/soft 目标及分母继续单列。

参考指标 **metric values unchanged**。主指标来源为冻结 test；dev/calibration 用于诊断与拟合，禁止用候选 test 结果选配方。历史 test 已向方案设计披露的限制继续保留。已有结果、分母、上游对照及 flags 见 [原始完整表](REFERENCE-BASELINE-MATRIX-2026-10-31.md) 和 [六组合增量](REFERENCE-BASELINE-INCREMENT-2026-10-31.md)；本次没有新模型分数、训练收益或审查放行声明。

## 已完成工程工作

- 修复 release 对 NPU receipt/EXIT 的绑定；独立退出后 CPU 凭证绑定容器 StartedAt/FinishedAt、request/report/terminal/receipt/EXIT，不改旧报告。
- 使用调用方在 journal 外固定的 anchor SHA 约束 release review 和 allocation 原始字节，拒绝协调重写；所有将执行的 Python 依赖均核对计划哈希。
- 发布中断恢复保留原 intent；测试覆盖 CPU/NPU 代次替换、合法 rc=0 EXIT 替换、真实 release 入口和 link/unlink 等内部中断。真实入口测试使用真实 queue 与模拟 preparer/Docker，不能说成真实资源端到端释放。
- 新 review bundle v5 的 **53/53 独立子进程测试通过**，主会话重核文件集合/哈希。v3/v4 失败包保留；修复了测试依赖协议文件漏复制，未放宽断言。
- 实际 Astra release-only v3 已 detached 启动，进程与 heartbeat 已核验；结论待返回。旧 v2 有 BLOCK 原文，但无实际 child/runner 终态，未补造退出记录。
- E40 已有 L1/L2/L1L2 Delete-only AST 候选和 **7/7 结构测试**；固定镜像 CPU v3 完成 **32 cells/256 forwards**，全部候选与原函数输出字节 exact，实际 retained Docker exited/0。v1/v2 在导入阶段失败且无 tensor cell，均保留。主会话核验每项输出 SHA/形状人口和现场退出；没有重新运行 tensor 算术。完整 NPU 执行计划仍待完成。

## NPU 与执行顺序

正确 SSH 别名为 npu，服务器 hostname=k8s-node1。最新现场观察八卡无 NPU 进程，满载目标尚未达成；chip 1 在 free[]，chip 4 仍由 E38 2B 持有。2B NPU/CPU verifier 实际 exited/0；9B 未启动。0.8B 的三步训练入口 preflight 已完成，它不属于正式训练或测试集收益。

先取得新的 release-only Astra 结论，再核验并释放 2B、串行运行 9B。E38 结束后还有独立数值/内存准入：2B 首差位于第一层投影，chunk8 未等价；9B 最大实际输入的某阶段即使清理引用仍约 59.4 GiB core-only，不能直接运行全量。按 [完整准入路线](OPENJEV-JEVAL-NEXT-ADMISSION-2026-10-31.md) 并行准备生命周期优化及后续必要的字节搬运实验。完成同协议完整 JEVal 结果后再收口 D1、讨论和冻结正式 Jev 训练。

## 决策与证据边界

当前无新增必须由用户决策的事项。范围不扩展、预算取消、公开任务优先、推理自动执行和 milestone 增量报告的决策均继续生效。上述 release 工具测试不等于资源释放，E40 AST 和 CPU tensor 相同不等于 NPU 数值等价或显存下降；真实业务仍不纳入本阶段。

最新完整计划：[状态与下一阶段计划](../proposal/08-task-status-decisions-and-next-plan-current.md)。工程记录：[E38](../wiki/E38-openjev-path-trace-20261031.md)、[E40](../wiki/E40-openjev-lifetime-candidate-20261031.md)、[R3 preflight](../wiki/R3-training-engineering-preflight-20261031.md)。

机器索引 SHA256：

- REFERENCE-BASELINE-MATRIX-2026-10-31.json: `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`
- REFERENCE-BASELINE-INCREMENT-2026-10-31.json: `fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`

CPU 新证据：[E40 结果绑定](E40-LIFETIME-CPU-RESULT-2026-10-31.json)。原 test 指标没有变化；CPU 小 tensor 验证不计入基线矩阵。
