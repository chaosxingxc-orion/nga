# 数据集覆盖扩展 v7：从冻结参考结果到可执行能力矩阵

**日期：** 2026-11-02  
**状态：** 范围扩大、准入顺序重排；不读取新增候选 TEST，不产生 Qwen3.5 新指标，不授权训练或推理。

## 结论

“数据集选少了”的判断成立。当前 D1 参考结果只有 **38 个模型×数据集单元**，其中 **36 个已有结果，2 个 Open-Jev×JEVal 单元为 blocked/null**。这组结果必须继续冻结，作为参考模型在已锁定测试集上的权威读数。它不等于完整能力覆盖。

v6 已经登记了 5 个新增来源族、18 个声明面板；5 个来源全部为 `needs_review`，`ready_for_inference=0`。本版把公共扩展和内部业务缺口一起纳入统一矩阵，规划范围为 **约 25–30 个独立来源/任务族、70+ 个原生测试面板**。这两个数是候选规划量，不是已完成实验数量，也不能写入 Qwen3.5 结果表。

覆盖层次固定为三层：

1. **冻结 D1 参考层：** 38 个模型×数据集单元，保持历史数值、公式、温度和分母不变。
2. **公共扩展层：** 通过来源、版本、split、输入、指标、分母、重叠 lineage 和 TEST 暴露审计后，进入 Qwen3.5 直接驱动 NxM。
3. **业务缺口层：** 公开数据无法承载的中文业务规则、未知/升级、证据和审计回执、成本与闭环任务，自建冻结集合后进入同一直接驱动协议。

## 为什么现有集合不足

已有集合集中在静态文本 typed choice、noul、score 以及少量校准任务。以下能力仍需要独立任务面板：

- 普通分类、路由、OOS 和 complete-message correctness；
- 数值/时间规则、反事实等价改写与 discrimination counterpart；
- 先验漂移、已知分布概率语义、synthetic unknown、选择性预测和拒答；
- 排序、tie/inversion、选项顺序和层级一致性；
- clean/attack 鲁棒性、安全护栏和跨语言；
- 证据 support/conflict/missing、可审计回执、规则版本变化；
- 中文数字、日期、区间和等级规则；
- 每正确结果成本、升级代价、网页工具和闭环动作；
- 图像/视频输入的独立多模态接口。

这些能力不能用一个汇总准确率代替。每个面板保留其原生目标、指标和分母。

## 公共扩展来源与任务族

### P0：共同文本、路由、业务 typed decision 和概率语义

P0 先建立来源合同，只有合同通过后才可读取候选 TEST 或进入 FIFO：

- **AppliedMachineLearning-Lab Jev benchmarking：** 约 37 个公开任务面板；按 choice、noul、安全、多语言、排序/评分、校准和 OOD 分表。只有 source-disjoint、公开 TEST 和输入字段闭合的面板进入推理。
- **JevBench public-231：** 保留其 choice/noul/score、难度、校准和成本/延迟原生面板；private aggregate 只做文献参考。
- **Intern-Decision：** JevBench、Typed Decision、ToolACE、AG News、WildJailBreak 和 known-distribution calibration；同源面板保留 item lineage。
- **Jevals：** Banking77、PubMedQA、HelpSteer2 三个 primitive 面板，分别报告分类、noul 和 ordinal/score 指标。
- **Canonical/legacy DecisionBench：** 按版本、task/family 和来源分开，不能因同一主题合并成一个结果。
- **Decision Model Benchmark：** Banking77、CLINC150/OOS 和 NLU++；同时保留 complete-message accuracy、micro/macro-F1、AUROC/AUPRC、延迟、成本和置信度可靠性。
- **BEV Decision：** `counterfactual_15k`、`numeric_temporal`、`hard_50k`、skills 和 default；反事实同时报告 flip/stability 与 discrimination。
- **LocalLLaMA Typed Decisions：** invoice processing、security incidents、customer service、agent trace observability 和 all；按 typed primitive 与业务域分表。
- **TDM prevalence-shift：** 五个公开来源、35 个预注册测试；no-shift、shifted、目标先验和每个来源分别报告。
- **Jev OOD calibration：** OpenBookQA、CommonsenseQA、HellaSwag 的公开面板与 synthetic unknowable 分开，保留 noise-floor ECE 与诊断性 refit-T。

P0 的目标不是一次性把所有面板跑完，而是先获得可复核的共同输入合同和参考指标表，作为后续 NxM 的固定任务轴。

### P1：能力专项与风险边界

P0 合同稳定后接入：

- ORDER BY ranking：tie、inversion、reverse-order paired flip、排序校准；
- System-One coherence：coarse-to-fine、重复问题、option-order permutation；同源 typed-decision coherence 先做 lineage，不计独立来源；
- DecisionRobust、DecisionPivot、JevAdvBench：clean/attack、stable-correct/stable-wrong、attack success、paired flip；
- Guardrails/Safety、PFR/selective refusal：coverage-risk、AURC、拒答正确性、升级成本；
- Korean JEV、Eikos、Respan Behavior、Belebele、AfriXNLI、SIB-200：按语言和来源分层；
- This-That spatial/complex：分别固定 rendered modality、rule family、chance baseline 和 OOD calibration；
- Decision Index 选定的公共文本面板：保留 edition、chance correction、coverage adjustment 和 area weights，不合并为单一总分。

### P2：独立模态、闭环和内部业务缺口

P2 与文本 Qwen3.5 NxM 分开排程：

- UniJev、OneJev、DecisionRobust image、Decision Index vision：分别建立图像/视频输入 adapter、split、label 和原生指标；
- WebJev、AgentDecisionBench、DecisionGym：报告 success、constraint violation、steps、latency、cost 和 terminal reward；缺少可复现 TEST 的仓库只保留来源登记；
- 内部业务缺口集合：业务作者规则及同义改写、中文数字/日期/区间/等级、unknown/fallback/升级、证据 support/conflict/missing、审计回执、规则版本变化、每正确结果成本。

每个内部集合必须包含 train/dev/test、rule-family holdout、等价配对、discrimination counterpart、typed candidate set 和显式分母。真实业务接入不属于当前阶段；这里只建立可控的冻结任务来验证 Jev 训练方案是否产生明确收益。

## 数量和状态口径

| 层级 | 数量 | 当前状态 | 允许写入 Qwen3.5 结果表吗 |
|---|---:|---|---|
| D1 冻结单元 | 38（36 有结果，2 blocked） | 已锁定 | 可以，历史值保持一致 |
| v6 已审计新增来源 | 5 个来源、18 个声明面板 | 全部 `needs_review` | 不可以 |
| v7 公共候选规划 | 约 25–30 个来源/任务族、70+ 原生面板 | 规划中 | 不可以 |
| 公共或内部准入面板 | 以 `ready_for_inference` 收据为准 | 尚未形成 | 通过后可以 |

目录、论文报告、模型卡和结果镜像都不能直接计作独立数据集。只有 item identity、来源 hash、版本、split 和输入语义独立，才可计入独立泛化证据。

## 面板准入合同

每个面板必须在 CPU 侧完成以下字段，然后才能产生 FIFO 入队资格：

1. source、version、commit/hash 和原始许可证；
2. split、item count、输入字段、candidate set、level type 和模态；
3. pair key、equivalence class 和 discrimination counterpart；
4. native formula、target type、温度、hard/soft target、valid/full 分母；
5. 与 Kev、Nimble、Typed、Open-Jev、JEVal、Banking77、CLINC150、MASSIVE、PAWS、Civil Comments 和 TREC 等已有来源的 item-level lineage；
6. TEST 是否公开、是否可复现、是否被本项目读取；
7. 模型输入 adapter、失败处理、未知/拒答语义和报告 schema。

验证器必须输出 `ready_for_inference` 或明确的 `needs_review/blocked` 原因。未通过的面板不得用零填充，也不得从候选列表直接进入 NPU 队列。

## 指标与统计规则

先报告参考模型在各自锁定 TEST 上的论文原生结果，再报告同一 TEST、同一字段下的复算结果。accuracy、complete-message accuracy、macro/micro-F1、AUROC/AUPRC、Spearman/Pearson/Kendall、MAE、Brier、ECE、NLL、coverage-risk、flip/stability、成本和延迟全部独立列出。

native temperature 与 raw T=1、hard 与 soft target、valid-only 与 full、state macro 与 question-weighted、clean 与 attack、no-shift 与 shifted、in-domain 与 synthetic unknown 分开。若目标、分母和输入语义一致，可补充 decision-level paired 指标；不得用 aggregate accuracy 充当一致性指标。

所有 invariance 任务都必须有 discrimination counterpart。若 question-only、常数分类器、查表或生成器记忆能达到退化最优，必须加入对应对照，防止把任务记忆误判为规则理解。

## 与当前 NPU 训练计划的关系

覆盖扩展的 CPU 审计、lineage、scorer、文献表和报告与 NPU 任务异步运行。NPU 只消费已准入的 FIFO 任务，并由约十分钟轮巡的 watchdog digest 监控；编排者不读取原始日志。候选扩展不会绕过 formal K1 的 Astra exact-plan、资源 claim、物理设备复核和 detached launcher 门槛。

P0 参考合同完成后，冻结 Qwen3.5 的 NxM 直接驱动任务轴，再讨论 LoRA、proper-scoring、校准和 RL。训练结果不能反向挑选测试集合。每个 milestone 增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 和 `wiki/CURRENT-CONCLUSIONS.md`，历史过程保留在 `.local/` 归档。

## 本版决定与后续动作

本版直接接受“数据集选少了”的修订，不要求用户重新选择范围。执行顺序固定为：

1. CPU 侧补齐 P0 十类来源合同和 lineage 表；
2. 对合同通过的面板生成 `ready_for_inference` 收据并按 FIFO 入队；
3. NPU 队列持续执行已准入推理，CPU 侧异步完成指标复算和参考表；
4. P0 完成后冻结 NxM 直接驱动矩阵；
5. P1、P2 按能力缺口推进，内部业务集合在公共集合审计完成后制作；
6. 只有在直接驱动、SFT/LoRA、校准和 proper-scoring 基线明确后，才设计 RL。

**本版没有新增 TEST 指标，也没有启动新增推理或训练。**

## 证据

- `proposal/18-dataset-coverage-expansion-v6-status-2026-11-02.md`
- `.local/reports/dataset-gap-inventory-20261102.md`
- `.local/reports/capability-matrix-gap-20261102.md`
- `.local/reports/independent-candidates-beyond-v5-20261102.md`
- `.local/reports/dataset-expansion-v6-metadata-audit-20261102.json`
- `.local/reports/dataset-expansion-v6-contract-validation-20261102.json`
- `experiments/REFERENCE-BASELINE-LATEST.md`
