# Open-Jev-9B 原始完整 OOD 参考结果（2026-10-31）

这是 E32 冻结的 `release-v2/ood.jsonl` 原始 OOD 参考推理结果，不是 Jev 训练收益，也不是 Astra 审查结论。完整分母为 **15,920** 行，其中 hard **15,446**、soft **474**；原生 serving 温度为 **1.8969118766347646**，另列 raw `T=1`，没有用 OOD 数据调温度。

| 计分面板 | hard accuracy（15,446） | expected accuracy（15,920） | NLL | Brier | expected Brier | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| native serving | 91.978506% | 90.413799% | 0.299676558 | 0.126747550 | 0.144078290 | 0.037592607 |
| raw T=1 | 91.978506% | 90.413799% | 0.451535465 | 0.137554553 | 0.154885293 | 0.058512809 |

hard accuracy 的正确数和分母为 **14,207/15,446**；expected accuracy 在全部 15,920 行上使用 gold 分布对预测 argmax 的概率。Brier、expected Brier、NLL 和 ECE15 使用全体 15,920 行。NLL 为 `-sum(q*log(max(p,1e-15)))`；Brier 为各类 `(p-q)^2` 求和；expected Brier 再加 `1-sum(q^2)`。ECE15 用最大预测概率与 `q[argmax(p)]` 的 15 个等宽 bins 加权偏差。所有来源/题型分项、完整精度及证据路径保存在 [机器可读结果](OPENJEV9-OOD-RESULTS-2026-10-31.json)。

## 执行与独立验收

推理终态于 `2026-10-30T22:02:01Z` 写出，15,920/15,920，推理容器实际 Docker exit 0（`370d251b...`，`2026-10-30T22:02:05Z`）。独立 finisher 于 `2026-10-30T22:03:49Z` 写出 `COMPLETED_SCOPED_REVIEW_REQUIRED`，其容器实际 Docker exit 0（`c62f4476...`，`2026-10-30T22:03:50Z`）。记录中核验 105 个冻结文件、92 个必需文件，推理记录和长度记录各 **15,920** 条。

绑定哈希如下：

- config：`9ec95392a5a8dfb23041cdb905d9d32ac95960601363605d4723892ec50bddd1`
- report：`82c4ff583427c10d6e913a592d9f4397b10d15c72a185baff5d764b4f121593d`
- audit：`4a03f310b4722db73b8179a411f58ea06d09009e5bb24955c62a89952681cee6`
- FINISH_COMPLETE：`02361142a49191d9fbbf07ebbbef06504ab7b073b7c5ccc284f851613a692fe6`
- INFERENCE_CONTAINER_EXIT：`6cfc2f99b8bfa452770bc924b6b996e98a91d1cd3b084f75b72a56372005f103`

审计状态是 `VERIFIED_SCOPED_REVIEW_REQUIRED`，保留 3 个科学审查标记：`customer-control-v1` 的 accuracy=1.0，以及 `workflow-controls-v1/agent_trace_observability` 的 accuracy=1.0 和 expected_accuracy=1.0。它们来自分项精确边界值的 suspicious-success 规则，不会被抹除；整体指标仍按完整冻结分母报告。

## 本次回执复核与精确边界诊断

在既有独立 finisher 完成后，短时 CPU 复核重新读取所有 15,920 条推理回执和 15,920 条长度回执，核对完整索引集合、原始 OOD ID/split、输入/配置身份、payload 哈希、token 数和完整文件哈希。使用独立标准库指标实现重算 native/T1 总体及全部来源/题型面板，均满足既有审计比较条件。实时查询 175 的两个保留 Docker 容器，并核对完整 ID、镜像、命令、wrapper 哈希及 exited/0。没有重跑模型、改变温度或释放芯片。

| flagged source | 全部行 | hard 行及正确数 | expected correct 合计 | 不同概率向量 | 解释 |
| --- | ---: | ---: | ---: | ---: | --- |
| customer-control-v1 | 600 | 560/560 | 578/600 | 600 | 仅 hard accuracy=100%；另有40条 soft，expected accuracy=96.333333% |
| workflow-controls-v1/agent_trace_observability | 525 | 525/525 | 525/525 | 524 | 525个不同ID；gold 与预测 argmax 均为450个0、75个1，并非恒定输出 |

这些检查未发现缺失、重复 ID、恒定预测或计分错误，但不证明来源无泄漏或更广泛泛化；3 个 flags 原样保留。原 finisher 审计负责 105 个冻结依赖（包括模型文件）的完整哈希验证，本次 closeout 没有重新读取所有权重文件。该限定范围不能扩大成新的全模型来源认证。

复核证据目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev9_ood_closeout_20261031/`。`report.json` SHA256 为 `99609f7b4571372ff8ec9586b87af680415f979b1dd0f879e7a684b171018b59`；目录内保留全部回执清单、实时容器退出记录、复核脚本、成功 terminal 与 EXIT。本次短时复核执行退出 0。原推理终态吞吐为 **1.279087362 questions/s/chip，1 chip**，reserved memory **17.587890625 GiB**；它不是不同模型接口间的公平效率排名。

## 结论边界

该结果只证明此 checkpoint 在原始 OOD 快照上的本地 native/raw-T1 计分及完整执行链。它不能证明论文 scorer 的严格复现、跨设备数值等价、训练增益、真实业务收益或 Astra 放行。Open-Jev 的 JEVal 原协议仍受 E36/E37 数值准入阻塞。
