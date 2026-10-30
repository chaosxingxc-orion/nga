# 初始 Nimble 原生公共 test 复测结果

2026-10-30 17:07 UTC。E25 已完成 1,884 条推理与限定范围的独立验收。推理及 CPU 后处理的结构化终态、wrapper 与保留容器均退出 0；独立重算为 `VERIFIED_SCOPED`，未触发当前审查标记。此结论不包括实质 Astra 审查，也不证明新训练收益。

## 1. 配置、来源与验收范围

原始 adapter revision `594dfdcfb6f94e3d0c0db7535180d3c71689169a`，Qwen3.5-9B Instruct base revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`；原始 v1 schema、BF16 合并骨干、FP32 候选 token LM-head 投影、T=1、2048 token 上限。七套 test 的最终数据文件 SHA256 和有序 ID 与原 manifest 全部一致；没有截断、重抽样或复用 E19 预测。

运行前冻结 152 个文件，覆盖独立推导的全部 150 个必需依赖；CPU 验收器另冻结 9 个文件。完成后再次核对全部文件哈希、各 suite 数据哈希、有序 ID、配置及输出哈希绑定、实际 Docker ID/image/exited-0。E19 因遗漏 base config.json 的旧失败证据保持原状，没有回写。

独立计分器从保存的 logits/probabilities 重算 typed prediction、NLL、multiclass/binary Brier、ECE10、score MAE 和 human-distribution 指标，核对所有逐项记录与汇总。候选 token ID 对照冻结 tokenizer 词表核验；prompt token 哈希仅绑定来源及格式，未独立重新 tokenization。family-complete accuracy、与 Jev 的成对比较及硬件数值等价不在本次验收声明内。

## 2. 全量本地成绩与上游引用值

准确率使用 argmax，与对应 hard reference 比较；score 的 accuracy 也使用离散等级 argmax，不是期望值四舍五入。上游数来自 `docs/PUBLIC_BENCHMARKS.md`，仅提供以下精度的公开表，不应由同一舍入值推定逐项一致。

| 子集 | n | 正确数 | 本地 accuracy % | 上游 accuracy % | 本地 ECE10 | 上游 ECE10 | 本地 multiclass Brier | 上游 Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| massive-en-US | 350 | 304 | 86.857143 | 86.9 | 0.069903500 | 0.061 | 0.215612244 | 0.216 |
| massive-de-DE | 350 | 294 | 84.000000 | 83.4 | 0.081899113 | 0.079 | 0.256618634 | 0.256 |
| paws | 250 | 207 | 82.800000 | 82.8 | 0.100160241 | 0.100 | 0.279648319 | 0.280 |
| civil_comments | 300 | 210 | 70.000000 | 70.3 | 0.135850765 | 0.133 | 0.413403503 | 0.413 |
| aegis2 | 250 | 204 | 81.600000 | 81.2 | 0.098642061 | 0.102 | 0.289384455 | 0.289 |
| summeval-relevance | 240 | 117 | 48.750000 | 49.2 | 0.090175031 | 0.102 | 0.676895632 | 0.678 |
| summeval-consistency | 144 | 108 | 75.000000 | 75.7 | 0.171724079 | 0.177 | 0.419423051 | 0.421 |

MASSIVE en-US 与 PAWS 的准确率与上游表在其报告精度下一致；de-DE、Civil Comments、Aegis 和两个 SummEval 子集有差异。原上游逐题 `evaluations/public/` 是 gitignored 运行产物，当前镜像未取得，因此无法定位具体翻转题。即使准确率或三位 Brier 一致，也不称概率完全复现。上游采用 ROCm GPU/CPU offload，本地采用 Ascend；当前证据不足以把差异归因于特定硬件或算子。

## 3. 不同计算方法分列

multiclass Brier 为 `Σ_k (p_k−1[k=y])²`；Noul binary Brier 仅为 `(p_true−y)²`，两者不能混用。ECE 为 10 个等宽 top-candidate-confidence bins，按题目数加权。NLL 使用参考类别概率。score MAE 使用概率期望等级与 reference 的绝对误差，不归一化等级量纲。

| 子集 | 本地 NLL | 本地 binary Brier（仅 Noul） | 本地 score MAE | 上游 score MAE |
| --- | ---: | ---: | ---: | ---: |
| massive-en-US | 0.566444583 | — | — | — |
| massive-de-DE | 0.664880929 | — | — | — |
| paws | 0.541910675 | 0.139824160 | — | — |
| civil_comments | 0.641568115 | 0.206701752 | — | — |
| aegis2 | 0.568025637 | 0.144692227 | — | — |
| summeval-relevance | 1.305991113 | — | 0.695520387 | 0.698000000 |
| summeval-consistency | 0.905904174 | — | 0.567382163 | 0.569000000 |

Civil Comments 的 300 条另有 human label distribution：本地 base-2 Jensen–Shannon 为 **0.175792225**、total variation 为 **0.292534998**、human entropy 为 **0.239331648 bits**。上游 JSD/TVD 分别报告 .176/.292；该分布一致性口径与上面的 one-hot Brier 不同。

七套共答对 1,444／1,884（76.645435%）；该描述性 micro 数只代表这七套 test，不能与上游 13 子集混合 train/dev/validation 的 75.9% micro 直接比较，也不作为决策一致性指标。最后心跳为 1.5199 questions/s/chip，1 chip，reserved 18.6699 GiB；这是该次推理的累计观测，不是吞吐优化实验。

## 4. 可复核证据

- 推理目录：`reference_inference/nimble_public_test_20261030_v2/`。
- 独立验收目录：`reference_inference/nimble_public_test_20261030_v2_finish/`。
- 推理 report SHA256：`8d54869ee54f566ffc1b5c7aa7813ea97f986d6d52351a27d947cc7f7f7b6e2c`。
- 独立审计 SHA256：`0a7476130ee3d55c1fb661e2bb8d127cc240ba1e242c6014c024f2e372a8929b`。
- 推理容器 `ddffa765ef3174607740c3cd902568470ba951eaf1e8f292dfb3c52d7849baa1`，wrapper 17:05:57 UTC。
- CPU 验收容器 `1be81b414f70335da5b1243f78c1fd5c54ac2ba5c066f66c714c74114190b7e0`，wrapper 17:06:38 UTC。

上述相对目录位于 `/mnt/cephfs/xingchao/experiments/jev/`。详细冻结配置、完整逐项 receipt 和各指标分域表均保留。与参考的差异、原始失败运行及尚未完成的 Astra 审查不因本次限定验收通过而删除。
