# Open-Jev 原始完整 OOD：已验收的 2B 参考结果

2026-10-31（本次完成时间采用 175 主机 UTC）。这是 E32 的本地原生推理结果；预注册见 [E32 协议](OPENJEV-ORIGINAL-OOD-2026-10-30.md)。只包含已完成的 Open-Jev-2B；9B 仍单独等待完成，不能据此记为整个 OOD 阶段完成。此文件承接较早的 58 面板固定快照，不覆盖该历史快照。

## 数据和方法

保留原始 `release-v2/ood.jsonl` 的全部 **15,920 行**：hard **15,446**、soft **474**；这是 `ood`，不与原始 `test` 的 10,532 行合并。数据 SHA256：`9152bff7f3d9c83cce3f1423cc6e0e6b33286b3092b3f544cb18dcc37b35a7ee`。原生 checkpoint、BF16 unmerged backbone、FP32 head、SDPA、输入顺序和候选全部保留；无截断、无 OOD 温度拟合。两种温度面板使用同一套已保存 logits，不是两次独立推理。

令 gold 分布为 q、预测概率为 p，k 为预测最大概率的首次 argmax。hard accuracy 只在 one-hot 的 15,446 行统计；expected accuracy 在全体 15,920 行统计 q[k]。NLL 为 `-sum(q*log(max(p,1e-15)))`；Brier 为各类 `(p-q)^2` 求和；expected Brier 再加 `1-sum(q^2)`。ECE15 用 max probability 与 expected correctness q[k]，按 15 个等宽 bins 计算绝对加权偏差。它不是 Typed Decisions 的 hard-correctness ECE10，也不是 Nimble 的 Noul binary Brier。

| 计分面板 | hard accuracy % | expected accuracy % | NLL | Brier | expected Brier | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原生 T=1.518796342858676 | 86.028745 | 84.616890 | 0.802074062 | 0.246288900 | 0.263619640 | 0.105578241 |
| raw T=1 | 86.028745 | 84.616890 | 1.156734154 | 0.254766583 | 0.272097322 | 0.119212764 |

accuracy 的正确数为 **13,288/15,446**；其余总体概率指标分母为 15,920。保留各来源的不同样本量，不把来源平均值冒充问题等权总体。

| 原始来源（原生温度） | 全体 n | hard n | hard accuracy % | expected accuracy % | Brier | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| customer-control-v1 | 600 | 560 | 97.321429 | 93.833333 | 0.053472568 | 0.026549824 |
| painting-geometry-v1 | 6912 | 6912 | 80.512153 | 80.512153 | 0.379820393 | 0.183038240 |
| reasoning-control-v1 | 750 | 750 | 67.066667 | 67.066667 | 0.450567414 | 0.131070376 |
| snake-v1 | 3464 | 3192 | 86.779449 | 83.852964 | 0.202043056 | 0.074733294 |
| vizdoom-basic-v1 | 825 | 825 | 92.969697 | 92.969697 | 0.098949623 | 0.026354610 |
| wikispeedia-v1 | 219 | 57 | 59.649123 | 29.380020 | 0.314447648 | 0.125820629 |
| workflow-controls-v1/agent_trace_observability | 525 | 525 | 98.857143 | 98.857143 | 0.019068331 | 0.005611061 |
| workflow-controls-v1/customer_service | 600 | 600 | 95.000000 | 95.000000 | 0.079934817 | 0.035145568 |
| workflow-controls-v1/invoice_processing | 750 | 750 | 99.733333 | 99.733333 | 0.005054427 | 0.008638511 |
| workflow-controls-v1/security_incidents | 1275 | 1275 | 99.372549 | 99.372549 | 0.010552492 | 0.002481382 |

## 执行和验收证据

推理于 **21:08:45 UTC** 写出成功终态，15,920/15,920；推理 wrapper 及保留容器在 **21:08:49 UTC** 退出 0。独立 CPU 审计与保留 finisher 在 **21:09:41 UTC** 退出 0，`VERIFIED_SCOPED` / `COMPLETED_SCOPED`，核查 102 个冻结文件、89 个必需文件、全部逐项身份与指标，原审计的 review flags 为 0。该 flags 检查覆盖总体及来源/题型主面板，不涵盖每一个 coverage 子面板；例如高阈值子集的完美准确率或空集仍须按其分母解释，不能把零 flags 写成所有子集都无异常。

另保存了全部 15,920 receipts 的文件哈希，并在审计完成后重新核对未变；推理和 finisher 的 ID、命令、镜像、wrapper、实际 exit、terminal、report 与 audit 绑定通过。chip 4 在独立核查 Docker 无活跃访问和 npu-smi 无进程后，按 allocation lock 显式释放。

- config：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_original_ood_20261030/config.json`；SHA256 `e0922cda0415a0972375365f806eba3230607724d7a6587cb99b69577710562d`。
- report：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_original_ood_20261030/report.json`；SHA256 `35f4f3bd824f435aa2813e60de0e41f7af863a3d2ced96783d394bd624906e07`。
- audit：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_original_ood_20261030_finish/INDEPENDENT_AUDIT.json`；SHA256 `36e65d8c398902fcfe4fd0b3ce1c829ad28212f27d7072625289f3db7038de58`。
- release acceptance：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/e37_ood2_acceptance_20261031/ACCEPTANCE_EVIDENCE.json`；SHA256 `4b15cd7c5a9ffaaa50f9bd8a935fcaef805220faf7d7ed41dc5240b411fd9bab`。

指标的机器可读入口为 `report.json#/serving`、`#/raw_T1`、`#/by_source_serving`、`#/by_kind_serving`；完整精度、coverage 阈值及分母保留在原报告。终态累计吞吐为 **1.686637 questions/s/chip，1 chip**，reserved memory **4.146484 GiB**；这是当前原生配置的观测，不是跨接口公平效率排名。

## 结论边界

这是参考 checkpoint 在冻结 OOD 分区上的表现，**不是 Jev 新训练收益、业务上线收益或 Astra 对此结果的认证**。来源间差异可以描述；没有配对设计或一致性协议时，不能用总体 accuracy 代替决策稳定性。9B 未完成的单元仍保持 pending；E37 诊断和 Open-Jev JEVal 原协议的失败准入状态不因 OOD 完成而改变。
