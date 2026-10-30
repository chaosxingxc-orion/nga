# Astra auditor 局部复审

2026-10-30。指定 `gpt-6-astra` 实际只读审查，外层进程退出 0。以下仅覆盖 auditor 的 F2／F5 修复；不放行队列、waiter 或模型成绩。

未发现可确认的 F2/F5 范围内缺陷或回归。两文件 SHA-256 在审查前后均与 `manifest.json` 一致。

已核查：

- [审计文件:54](/tmp/nga-astra-auditor-rereview2-5alsc1uf/tools/audit_jeval_inference_hardened.py:54)：完整、有序的 11257 条 receipt 清单、逐文件哈希及规范化根哈希；拒绝缺失、额外条目及 records 目录／文件符号链接。
- 同文件第 75、437、497 行：消费者函数重新读取磁盘并严格比较；主流程在审计前建立清单、结束前复核。
- 第 96 行：临时文件写完并 fsync 后，以硬链接发布；目标即使并发出现也不会被覆盖。
- 第 384、402 行：保留全量分母 accuracy，独立计算 valid_accuracy，并纳入跨来源相同指标诊断。
- 已读[测试文件](/tmp/nga-astra-auditor-rereview2-5alsc1uf/tools/test_jeval_inference_hardened.py:180)，包括不同全量分母、清单篡改及发布失败案例。

边界：前后复核不构成并发写入下的原子快照；JSON 与摘要分别发布；相同指标诊断要求同类型所有非空来源值一致，不检测部分来源重复。未重跑测试，“25 passing”为父流程提供；未审查或认证队列消费者行为。全程只读，无外部调用、实验或子代理。