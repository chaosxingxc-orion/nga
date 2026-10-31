# 参考基线 milestone 报告：测试集优先与 0.8B 工程 preflight

时间：2026-10-31T02:35:00Z

## 本 milestone 完成内容

项目负责人进一步明确：参考模型主要在冻结 **test split** 上汇报指标，以便与参考文献和业内结果对齐。开发集仅用于训练配方诊断、效率测量、阈值拟合和预注册门槛，不能替代测试集结果。

在正式训练之前，已完成 Qwen3.5-0.8B-Base 的真实 NPU 工程 preflight：

- chip：1；固定镜像 `nga-verl-qwen35-v030:20261029`；reference kernel；K1；seed 2；
- 训练数据：decision-v7 train，15,576 base questions；
- 训练入口成功匹配 186 个 LoRA pairs，完成 3 个 optimizer steps；
- 容器 `nga-r3-preflight-k1-08b-chip1-20261031`，Docker exit 0，`DONE` 为 `rc=0`；
- 产生 heartbeat、逐步 loss/吞吐记录和 manifest；单步记录包含 `tok_s_chip`、`q_s_chip`、显存和 chip 数；
- 终态核验后 guarded release chip 1，allocation 已恢复为 free，并保存 `RELEASE_INTENT.json`、`RELEASED.json`。

## 科学边界

这次 smoke 只证明模型加载、数据读取、训练入口、NPU 动态算子、heartbeat、终态和资源释放链可运行。它不读取 test，不修改正式模型，不进入参考矩阵，不代表训练收益，也不能与论文 accuracy 对齐。

当前参考 test 数字未改变，机器索引仍为：

- matrix JSON：`03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`；
- increment JSON：`fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`。

## 下一步

先完成 E38 release 工具的新 Astra 审查。通过后释放 2B 的 chip 4，串行完成 9B 诊断；随后完成两个 Open-Jev JEVal 的原生 test 推理、独立计分和最新报告刷新。训练正式 wave 仍须在 D1 test 汇报和训练预注册之后启动。

