# Open-Jev 原完整 release-v2 数据恢复

2026-10-30，见 [E23](../wiki/E23-openjev-original-data-restoration-20261030.md)。已完成真实 CPU
恢复任务；没有模型推理、训练或温度拟合，也没有修改正在运行的公共 test。

输出目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_original_restore_20261030/`。
原始数据在 `release-v2/`，证据为 `RESTORE_COMPLETE.json`、`report.json` 和
`INDEPENDENT_RESTORATION_AUDIT.json`。终态、包装脚本和 retained Docker 都为 0。

| 分区 | 原完整行数 | 硬标签 / 软标签 | 原始 SHA256 |
| --- | ---: | ---: | --- |
| train | 80,816 | 76,754 / 4,062 | `80a9ec19da9c4065b72f7a9e5ff8d67e62c1d1dd2572dfd296e46bfe2ea5a182` |
| calibration | 4,761 | 4,480 / 281 | `dd21b26912a6b26a09c3b00ae66a7985ee760e737b94ada4fcc6320406d4db63` |
| validation | 3,792 | 3,511 / 281 | `1dc97079d4fc034a1ba16315f801b0a4715b30c2a3874ae05aeb60dd1e40e8bb` |
| test | 10,532 | 10,046 / 486 | `fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b` |
| ood | 15,920 | 15,446 / 474 | `9152bff7f3d9c83cce3f1423cc6e0e6b33286b3092b3f544cb18dcc37b35a7ee` |

恢复使用发布 export 的源码快照，逐文件匹配 `source_code_sha256`；Wiki 原始 archive
匹配固定 SHA256。采用原参数（300 targets、12 pairs、12 candidates、seed 42），生成后
首先验证原 Wiki manifest，再按公开 export 记录的原位置插回。所有五个混合分区与原
manifest 逐字节相同，IDs 全唯一。再次移除这些位置，剩余每行字节也与现有公开投影一致。

`test-missing-wiki.jsonl` 和 `ood-missing-wiki.jsonl` 分别保存缺少的 176 / 219 行；报告保留
原行号与 ID。这提供下一次补充推理的输入身份基础，不自动证明可以合并不同运行的结果。
未来应先登记相同 checkpoint、tokenizer、prompt、原生 readout、精度及温度，核对完整行
映射后再补充推理和独立重算。不得把当前 10,356 行公共结果提前称为原完整 10,532 行成绩。

本任务恢复了训练分区以验证原混合数据，但没有据此启动任何正式训练。
