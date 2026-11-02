# 数据集覆盖扩展 v10：从来源登记到可执行任务矩阵

**日期：** 2026-11-02  
**触发：** 复查后确认当前数据集选择仍然偏少。  
**性质：** 覆盖范围与排程修订；不改写 D1 冻结读数，不读取候选 TEST，不改变 formal K1 v15。

## 1. 判断

当前 D1 的 38 个模型×数据集单元（36 个有结果、2 个 Open-Jev×JEVal 为 `blocked/null`）仍是参考模型测试集指标的事实权威，但它主要集中在 Kev、JEVal、Open-Jev 和 Nimble。它足以支持第一轮参考对齐，不能支持完整的 Jev 能力或业务收益判断。

本地 CephFS 已镜像的目录比 D1 覆盖更宽，包含常规路由、排序、重复问题一致性、空间/复杂规则、鲁棒性、安全、多语言、多模态、网页/闭环和行为稳定性来源。此前 v9 已登记部分来源，但仍把不少内容停留在抽象能力轴。v10 把这些来源拆成独立任务面板，并明确哪些可以进入文本 NxM、哪些只能做专项矩阵、哪些必须自建。

数量仍按“独立来源/版本/输入语义/原生 TEST 面板”计数。目录、论文报告、温度、mask、hard/soft 目标和结果镜像都不能单独算作新数据集。

## 2. 覆盖分层

### P0：共同文本 NxM（优先完成合同并进入 FIFO）

这些任务可以使用同一套文本输入、typed candidate set、single-pass readout 和 CPU scorer。每个面板仍需单独关闭 source hash、split、输入字段、target/type、pair key、原生公式、分母、license、lineage 和 TEST 暴露。

| 来源族 | 任务面板 | 承载能力 | 进入条件 |
|---|---|---|---|
| JevBench public / Praveenrajus Jev-bench | public-231、choice/noul/score、难度和校准子面板 | Jev 原生读出、难度、校准、成本 | 与 Nimble/Applied ML 逐 item 去重，private 仅文献参考 |
| AppliedMachineLearning-Lab | 约 37 个公开报告中的 choice、noul、score、路由、OOD、moderation、grounding 面板 | 跨来源直接驱动、分类、校准 | 报告 split 与可复现 TEST 分开登记，未闭合者 reference-only |
| Intern-Decision | 7 个 accuracy suite 与 known-distribution calibration | typed decision、已知概率语义、成本/延迟 | 固定后端、温度、输入格式和来源 lineage |
| Jevals | Banking77、PubMedQA、HelpSteer2 | 常规意图、医学问答、评分/ordinal | choice/noul/score 三种 target 分表，禁止合并总分 |
| Canonical/legacy DecisionBench | canonical task/family/domain、legacy medium/hard | 跨任务、跨领域、难度迁移 | canonical、legacy、medium/hard 分源，检查同源 item |
| Decision Model Benchmark | Banking77、CLINC150/OOS、NLU++ complete-message | 路由、完整消息、拒答边界 | 与已有 Banking77/CLINC150 逐 item 比对，message 与 binary 分母分开 |
| BEV Decision | counterfactual、numeric_temporal、hard、skills/default | 等价改写、数字/日期/规则变化、discrimination | 固定 pair key、规则族留出和生成版本 |
| LocalLLaMA typed decisions | invoice、security、customer service、agent trace observability | 业务式 typed state、升级、审计字段 | 核实公开 TEST、候选类型和 unknown/fallback 语义 |
| TDM prevalence-shift | CLINC150、HWU64、Financial PhraseBank、HateXplain、TREC-6 的 no-shift/shifted | 先验变化、稳定性、校准 | no-shift 与 shifted 分表，检查 transfer-v4 重叠 |
| Jev OOD calibration | public known/unknown 与 synthetic unknowable | OOD、拒答、ECE/Brier/NLL | public in-domain 与 synthetic unknown 分开，不宣称同一种泛化 |
| btzsc conventional routing | Banking77、MASSIVE、AGNews、topic、sentiment、toxicity | 普通分类/路由边界 | 只有 typed schema 和 split 合同闭合后才进入 Jev NxM，否则保留边界诊断 |

P0 不是“十一个已完成数据集”。截至本版本，v9 审计的 12 个来源族仍全部为 `needs_review`，`ready_for_inference=0`，没有候选 TEST 指标。

### P1：文本专项矩阵（P0 direct-readout 后按能力轴加入）

| 来源族 | 面板/任务 | 必须保留的指标 |
|---|---|---|
| ORDER BY / ranking | 排序、tie、inversion、顺序变化、成本 | pairwise accuracy、inversion rate、tie accuracy、cost |
| System-One coherence / typed-decision-coherence | 重复提问、层级重建、选项顺序、状态一致性 | coherence、paired flip、stable-correct/stable-wrong |
| DecisionPivot / DecisionRobust / JevAdvBench | clean/attack、选项通道和答案保持攻击 | attack success、paired flip、有效样本数 |
| Respan Behavior | 指令扰动、行为稳定性 | clean/perturbed、teacher-label provenance、稳定性；不与普通 accuracy 合并 |
| Safety/guardrail/PFR | 拒答、选择性预测、升级 | coverage-risk、AURC、拒答正确性、升级成本 |
| This-That spatial/complex | 空间、组合规则、模拟器真值 | accuracy、Brier、OOD、rendered-modality 分层 |
| Korean JEV、Eikos、多语言 | 语言与来源分层的 typed decision | language/source macro、native denominator、paired consistency |

### P2：多模态、网页和闭环（独立矩阵）

- `OneJev/UniJev/Imajev/DecisionRobust image`：绑定图像/视频资产 hash、模态、source-group split 和独立 scorer；没有公开可复现 TEST 的保持 `blocked` 或 `reference_only`。
- `WebJev/AgentDecisionBench/DecisionGym/JevAgentHarness`：报告 success、constraint violation、steps、latency、cost、terminal reward；不能与静态 readout accuracy 合并。
- Decision Index vision 只在独立 item 和公开 TEST 闭合后纳入，模型索引/结果镜像不算新数据集。

### P3：必须自建的业务缺口

公共数据不能承载以下问题，后续要建立冻结的 train/dev/test 和 rule-family holdout：中文数字/日期/区间/等级、证据 support/conflict/missing、unknown/fallback、升级与审计 receipt、规则版本变化、等价 pair、discrimination counterpart，以及每正确结果成本。真实业务暂不接入；先用合成和专家定义的冻结任务验证直接驱动收益。

## 3. 指标与报告边界

先报告各任务发布时的原生 test 指标，再报告字段完全一致时的 decision-level paired 指标。accuracy、complete-message accuracy、macro/micro-F1、AUROC/AUPRC、Spearman/Pearson/Kendall、MAE、Brier、ECE、NLL、coverage-risk、flip/stability、成本和延迟分别列出。不同温度、hard/soft、valid/full、clean/attack、no-shift/shifted、known/unknown 和模态不做平均分。

论文或 README 数字只能进入参考文献表，不能冒充 Qwen3.5 结果。候选面板只有在合同、lineage 和 TEST 暴露闭合后才允许加入 NPU FIFO。

## 4. 不改变当前训练和实验流水线

formal K1 v15 双 seed 继续 detached 运行，训练不读取 TEST；CPU 侧同时完成合同、去重、scorer 和文档。三条流水线保持异步：

1. CPU：来源合同、item lineage、指标预注册和 admission receipt；
2. NPU：只消费 `ready_for_inference` 的 FIFO 任务并保持资源 claim、heartbeat、terminal marker；
3. CPU：scorer、双 seed 对齐、报告刷新和 Astra bounded review。

watchdog 继续约 10 分钟轮巡，编排者只读 digest。每个 milestone 增量刷新最新报告，过程文件三天后归档。

## 5. 执行顺序

1. 完成 P0 逐面板合同和 lineage，优先 JevBench/Jevals、BEV/LocalLLaMA、DMB routing、TDM/OOD；
2. 合同闭合的 P0 面板按 FIFO 进入文本 NxM direct-readout，CPU scorer 异步运行；
3. P0 取得可比基线后加入 ORDER BY、coherence、robustness、guardrail、跨语言和空间/复杂规则；
4. 单独建立多模态、网页/闭环矩阵；
5. 冻结业务缺口集并报告基础模型直接驱动表现；
6. 只有直接驱动、SFT/LoRA、proper scoring、校准和成本基线稳定后，才讨论 RL。

## 6. 当前需不需要用户再决策

不需要重新删减来源。默认扩大登记范围、逐面板审计、合同通过即按 FIFO 推进。若 NPU 队列需要限流，只缩短当前 FIFO，不删除 P0/P1/P2/P3 覆盖登记，也不改写 D1 历史数值。

## 7. 验收

- D1 38 单元及其原生指标保持不变；
- P0/P1/P2/P3 每个任务面板有独立身份、指标和准入状态；
- 任何进入 FIFO 的面板都有公开可复现 TEST、adapter、scorer、分母和 lineage；
- 文本、专项、多模态、闭环和业务缺口不合并成一个总分；
- 新增 Qwen3.5 指标只来自实际推理报告，不来自论文汇总；
- NPU 满载、异步流水线、TEST lock、watchdog 和三天归档规则继续有效。

证据入口：`proposal/23-dataset-coverage-expansion-v9-2026-11-02.md`、`.local/reports/p0-v9-source-contract-audit-20261102.{md,json}`、`.local/reports/dataset-expansion-plan-impact-20261102.{md,json}`、`experiments/REFERENCE-BASELINE-LATEST.md`。
