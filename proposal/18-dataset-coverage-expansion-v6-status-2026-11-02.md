# 数据集覆盖扩展 v6：从 Jev 基准集合扩展到完整能力矩阵

**日期：** 2026-11-02  
**状态：** 范围修订和候选登记；不产生新的 Qwen3.5 指标，不授权读取新增 TEST。

## 结论

“数据集选少了”的判断成立，而且 v5 的扩展仍然不够。当前 D1 冻结矩阵有 38 个模型×数据集单元，其中 36 个有结果、2 个 Open-Jev×JEVal 单元为 `blocked/null`。v5 已登记约 16–17 个来源/任务族和 50+ 个原生面板，但这些面板仍偏向 Jev 专门 benchmark；普通分类/路由、先验漂移、已知概率语义、排序、拒答、证据审计、成本和闭环动作没有形成完整的可执行矩阵。

本版把覆盖分成三种数量，避免把候选数误报成已完成实验：

| 数量 | 当前状态 | 含义 |
|---|---:|---|
| D1 冻结模型×数据集单元 | 38（36 有结果，2 blocked） | 既有权威参考读数，不追溯修改 |
| v6 候选来源/任务族 | 约 25–30 | 目录、仓库、论文和独立任务族按来源指纹去重后的暂定范围 |
| v6 原生测试面板 | 70+（暂定） | 按 split、任务、模态、难度、配对关系和原生公式拆分的候选面板 |

“25–30”和“70+”在 manifest、版本 hash、item lineage、TEST 暴露及指标合同完成前都只是规划数量。它们不能写入 Qwen3.5 结果表，也不能当作已经有 25–30 个独立数据集的实验结论。

## 新增覆盖轴

### 1. Jev 直接读出和共同文本测试

保留 v5 已登记的 JevBench public-231、AppliedMachineLearning-Lab、Intern-Decision、Jevals 和 canonical/legacy DecisionBench，但把它们从“来源候选”展开为独立可审计面板。Applied ML 的 37 个报告只能先作为文献/来源登记；只有能锁定公开 TEST、输入字段和本项目 scorer 的面板才可进入 Qwen3.5 推理。

### 2. 普通分类、路由和 complete-message 边界

新增明确的非 Jev 专项边界：Decision Model Benchmark（Banking77、CLINC150/OOS、NLU++）、`btzsc` 的意图/主题/情感/毒性集合，以及 Jevals 的 Banking77/PubMedQA/HelpSteer2。它们用于回答“typed readout 的收益是否超出普通分类/路由基线”，不能和 typed choice 的 accuracy 混成一个总分。complete-message accuracy、micro/macro-F1、AUROC/AUPRC、延迟和成本各自分表。

### 3. 业务型 typed decision、数值/时间和反事实

把 `avbiswas__bev-decision` 的 `counterfactual_15k`、`numeric_temporal`、`hard_50k`，以及 `LocalLLaMA__typed-decisions` 的 invoice、security-incidents、customer-service、agent-trace-observability 作为独立任务族。它们补足业务式规则、数值/日期、反事实判别和升级/轨迹信息。反事实不变率必须同时报告 flip/discrimination；规则或生成器记忆必须有 question-only/constant 对照。

### 4. 概率、先验漂移、OOD 和选择性预测

新增 `tdm-prevalence-shift` 的五个公开来源和 35 个预注册测试、`jev-ood-calibration` 的公开 in-domain 与 synthetic unknowable 面板，并保留 Open-Jev OOD、Sys1Cal/known-probability 电池。no-shift、shifted、已知目标分布和 synthetic unknown 不合并；Brier、ECE、NLL、proper score、coverage-risk、AURC 和 noise-floor ECE 按各自公式及分母报告。

### 5. 排序、顺序和层级一致性

新增 `jev-orderby-bench`，报告 tie、inversion、reverse-order paired flip 和排序校准；新增 `system-one-coherence`，报告 coarse-to-fine coherence、重复问题一致性和 option-order 审计。`bro789__typed-decision-coherence` 可能与前者同源，暂不计作独立来源，必须完成 lineage 后再决定。

### 6. 鲁棒性、拒答、安全和跨语言

DecisionRobust text、DecisionPivot、JevAdvBench、Respan Behavior、Guardrails/Safety、PFR/selective-refusal 作为独立诊断族，分别保留 clean/attack、stable-correct/stable-wrong、attack success、拒答 coverage-risk 和升级成本。Korean JEV、Eikos 以及 Applied ML 的多语言面板按语言和来源分层；它们不能替代中文业务规则集合。

### 7. 多模态、网页和闭环

UniJev、OneJev、DecisionRobust image、Decision Index vision 单独建立视觉/视频矩阵；文本 Qwen3.5 不能用零值或文本替代。WebJev、Decision Index public text、AgentDecisionBench/DecisionGym 作为网页工具和闭环候选，报告 success、constraint violation、steps、latency、cost 和 terminal reward，不与静态 readout accuracy 合并。

### 8. 公开集合仍不能承载的业务任务

继续建立自有冻结集合：业务作者规则及同义改写、中文数字/日期/区间/等级、unknown/fallback/拒答/升级、证据 support/conflict/missing、审计回执、规则版本变化、每正确结果成本。每个集合必须有 train/dev/test、rule-family holdout、等价配对和 discrimination counterpart，先做直接驱动测试，再决定是否训练。

## 分阶段准入

### P0：首批共同文本与业务型测试合同

CPU 侧先为以下来源建立完整合同，不等于立即读取 TEST：

1. JevBench public-231、Applied ML 的 source-disjoint 子集、Intern-Decision、Jevals 三个小型 primitive 面板和 canonical DecisionBench；
2. Decision Model Benchmark；
3. `avbiswas__bev-decision`；
4. `LocalLLaMA__typed-decisions`；
5. prevalence-shift；
6. OOD-calibration。

每个面板要固定版本/hash、split、item 数、输入字段、candidate set、level type、pair key、native formula、分母、来源交集、TEST 暴露和模型支持状态。通过验证器并得到 `ready_for_inference` 收据后，才可按 FIFO 入队。

### P1：能力专项

P0 合同稳定后接入 ORDER BY、System-One coherence、DecisionRobust、DecisionPivot、JevAdvBench、Guardrails/Safety、PFR/selective refusal、Korean/Eikos/Respan 和 This-That spatial/complex。每个任务保留原生公式，不用统一总分替代。

### P2：独立模态、闭环和业务缺口

P2 包括 UniJev/OneJev/DecisionRobust image、WebJev、Decision Index vision、闭环环境和自建业务集合。它们拥有独立输入 adapter、分割和报告，不能阻塞文本 Qwen3.5 NxM，也不能把缺少 TEST 的 train-only 仓库当作公开测试集。

## 指标与实验顺序

先汇报参考模型在锁定 TEST 上的原生指标，再补充字段完全一致时的 decision-level paired 指标。accuracy、complete-message accuracy、macro/micro-F1、AUROC/AUPRC、相关系数、MAE、Brier、ECE、NLL、coverage-risk、flip/stability、成本和延迟不能合成一个平均分。不同温度、hard/soft target、valid-only/full、state/question macro、clean/attack、no-shift/shifted 和 synthetic unknown 都要分列。

CPU 侧并行完成来源审计、lineage、scorer、指标表和报告；NPU 侧只消费已准入的 FIFO 任务并持续运行。监控继续约十分钟读取 watchdog digest，不读原始日志。每个 milestone 只增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 和 `wiki/CURRENT-CONCLUSIONS.md`；过程材料留在 `.local/` 并按三天归档。

新增任务的 TEST 结果不能反向挑选训练混合。P0 参考结果完成后，才冻结 Qwen3.5 NxM 直接驱动矩阵；随后再讨论 LoRA、proper-scoring、校准和 RL。真实业务接入仍不在本阶段范围内。

## 本轮结论与需要的决策

本轮没有需要用户立即改变范围的决策，默认按 P0→P1→P2 执行。若后续需要压缩队列，优先保留 P0 的六类能力：共同 Jev 文本、普通路由、业务型 typed decision、先验/OOD、数值/时间反事实和概率校准。现有 38 个 D1 单元、历史指标、训练门槛和 NPU 运行不因本次扩展改写。

## 证据

- `.local/reports/dataset-gap-inventory-20261102.md`
- `.local/reports/capability-matrix-gap-20261102.md`
- `.local/reports/independent-candidates-beyond-v5-20261102.md`
- `proposal/17-dataset-coverage-expansion-v5-status-2026-11-02.md`
- `experiments/REFERENCE-BASELINE-LATEST.md`
