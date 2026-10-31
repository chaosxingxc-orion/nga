# 参考基线 milestone 报告：D1 范围与报告归档规则确认

时间：2026-10-31T02:15:00Z

## Milestone 结果

项目负责人确认 D1 不扩展完整模型×数据集笛卡尔积，按当前登记的 38 个组合收口。当前 36 个组合已有结果，两个 Open-Jev×JEVal 组合保持 `blocked/null`。本 milestone 是范围和报告治理确认，不重新运行模型，不重算指标。

## 读数一致性

本 milestone 的指标读数与上一版保持一致。权威数据由最新入口指向的两个 JSON 索引提供：

- `REFERENCE-BASELINE-MATRIX-2026-10-31.json`：58 个已完成计分面板；
- `REFERENCE-BASELINE-INCREMENT-2026-10-31.json`：36 个有结果组合、2 个剩余 blocked/null。

JSON SHA256 分别为 `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e` 和 `fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`。

## 下一 milestone

继续完成 E38 release 工具修复和实际 Astra release-only 审查；通过后释放 2B 的 chip 4，串行完成 9B 诊断，再执行两个 Open-Jev JEVal 原生推理、独立计分和参考矩阵增量刷新。训练仍等待 D1 参考结果阶段收口和训练预注册。

