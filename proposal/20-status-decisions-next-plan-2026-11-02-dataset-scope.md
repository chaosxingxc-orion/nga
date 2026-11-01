# 当前任务状态、待决策项与下一阶段计划（数据集范围修订）

**日期：** 2026-11-02  
**状态：** 执行中的范围修订；不改变已冻结 D1 数值，不把候选面板当作已完成实验。

## 1. 当前判断

“数据集选少了”的反馈成立。现有 D1 参考基线覆盖 **38 个模型×数据集单元**，其中 36 个有结果、2 个 Open-Jev×JEVal 单元因数值准入失败保持 `blocked/null`。这些读数、公式、温度、mask 和分母已经冻结，仍是当前参考模型 TEST/OOD 汇报的事实权威；它们不能代表业务能力的完整覆盖。

现有集合主要覆盖静态文本 typed choice、Noul、score 以及少量校准/OOD 面板。它没有充分覆盖路由和完整消息正确性、数值/时间规则、反事实 discrimination、先验漂移、未知/拒答、排序与顺序鲁棒性、层级一致性、证据与审计回执、中文业务规则、成本约束、工具闭环和多模态输入。因此需要扩大任务轴，再冻结 Qwen3.5 的 NxM 直接驱动矩阵。

当前候选规划量为 **约 25–30 个独立来源/任务族、70+ 个原生面板**。这是待审计的规划范围，不是已经完成的实验数；截至本文件日期，新增候选仍为 `needs_review`，`ready_for_inference=0`，没有新增候选 TEST 指标。

为避免范围数字造成误读，当前库存分成四层：

1. **D1 已完成层：** 38 个模型×数据集单元（36 个有结果、2 个 blocked/null），约 58 个协议面板，数值已冻结。
2. **本地库存层：** 约 24 个本地目录，其中包含版本投影、结果包、同源数据和不同模态，不能按目录数直接计为独立数据集。
3. **本地已登记候选层：** 约 16–17 个来源族、50+ 个原生面板；仍需完成合同、lineage 和 TEST 暴露审计，当前没有 `ready_for_inference` 面板。
4. **外部待镜像规划层：** 例如 AppliedMachineLearning-Lab Jev、JevBench public-231、Intern-Decision、Jevals、System1-Arena、TypedBench 等；它们尚未形成可运行本地快照，不得写入当前实验数量、不得进入 NPU FIFO。

因此，“70+ 面板”是覆盖规划上限，不是当前已下载、已准入或已完成推理的数量。

NPU 侧的 formal K1 训练任务继续按既定队列运行；CPU 侧并行完成数据合同、lineage、指标复算和报告。编排者只读 watchdog digest 和有指针的诊断摘要，不读取原始训练日志。NPU 任务采用 detached、可恢复、约十分钟轮巡，保持设备持续有队列可执行。

## 2. 结果应按四个维度组织

### 2.1 Jev 类模型的收益来源

报告中把模型和方法分为四类，并保留“直接驱动”作为共同起点：

1. **参数不动、改变驱动形态：** fixed order、typed readout、候选集/拒答 harness、温度或阈值等带来的收益；必须和参数更新结果分开。
2. **结构改造：** 改变 readout、候选表示、层级或分支结构带来的收益；报告结构差异和额外参数。
3. **任务与训练设计：** 通过任务定义、数据配方、SFT/LoRA 等得到的提升；严格使用预注册 split 和 TEST ticket。
4. **学习方法设计：** proper-scoring、校准、偏好/RL 等优化；只有直接驱动和基础训练基线稳定后才进入此类。

每一类都要报告同一任务上的 paired decision 指标、原生指标和失败/拒答统计，不能用汇总 accuracy 代替一致性。

### 2.2 任务/数据集与参考指标

每个面板保留来源版本、split、输入字段、candidate set、level type、原生公式和分母。论文公布的指标先按原生口径列出；同一 TEST 上的复算另列。native temperature/raw T=1、hard/soft、valid-only/full、clean/attack、no-shift/shifted、in-domain/synthetic unknown 均不得合并。

扩展按三批进入：

**P0（共同文本和 typed decision）：** AppliedMachineLearning-Lab Jev benchmarking（约 37 个原生面板）、JevBench public-231、Intern-Decision、Jevals（Banking77/PubMedQA/HelpSteer2）、canonical/legacy DecisionBench、Decision Model Benchmark（Banking77/CLINC150/OOS/NLU++）、BEV Decision（counterfactual/numeric-temporal/hard）、LocalLLaMA Typed Decisions、TDM prevalence-shift、Jev OOD calibration（含 synthetic unknowable）。

**P1（能力与风险专项）：** ORDER BY ranking、System-One coherence、DecisionRobust/DecisionPivot/JevAdvBench、Guardrails/Safety/PFR selective refusal、Korean JEV/Eikos/Respan/Belebele/AfriXNLI/SIB-200，以及 This-That spatial/complex。P1 仅在 P0 的来源和指标合同稳定后入队。

**P2（独立模态、闭环和内部缺口）：** UniJev/OneJev/vision Decision Index、多模态输入；WebJev/AgentDecisionBench/DecisionGym 的动作闭环；以及内部中文规则、证据、升级、审计和成本集合。P2 与文本 NxM 分开排程。

每个候选面板必须先通过 source/hash/license、split 与 item count、输入语义、等价类与 discrimination counterpart、原生指标/分母、item lineage、TEST 暴露审计和 adapter 失败语义检查，生成 `ready_for_inference` 收据后才可读取 TEST 或进入 FIFO。未通过的面板保持 `needs_review/blocked`，不补零。

### 2.3 业务要求映射

公共任务可以承载普通分类/路由、候选选择、未知检测、概率校准、顺序鲁棒性、层级一致性和部分证据/拒答要求。以下仍需自建冻结集合：中文数字/日期/区间/等级与版本规则；support/conflict/missing 证据；升级和审计回执；规则变更；每正确结果成本与闭环动作。真实业务接入不属于当前阶段，自建集合只用于验证 Jev 训练方案能否在可控问题上产生明确收益。

内部集合必须具备 train/dev/test、rule-family holdout、等价配对、discrimination counterpart、typed candidate set 和显式分母，并在公共集合审计完成后制作。

### 2.4 我们自己的实验轴

执行顺序固定为：

1. 完成 P0 合同和参考指标表，冻结 Qwen3.5 **N×M 直接驱动**矩阵；
2. 让已准入面板按 FIFO 持续推理，CPU 异步复算指标、做 lineage 和报告；
3. 在直接驱动基线之上选择开源 SFT/LoRA、proper-scoring、校准和优化方案，建立工程基线；
4. 用能力缺口清单制作内部冻结任务，并报告基础模型直接驱动表现；
5. 最后设计 RL 优化算法，预注册目标、对照和成本，并制定可复现 baseline。

每个 milestone 完成后增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 和 Wiki 的最新结论；旧过程文件按三天周期归档到 `.local/`，不作为事实权威。

## 3. 需要用户决策的内容

当前不需要重新选择“扩展还是不扩展”：范围扩展已经按反馈执行。仍有三项会影响排程的决策：

1. **P0 面板取舍：** 若资源有限，是否按上述全部 P0 先审计，还是先指定一个最小首批（建议先审计全部、只让合同通过者进入 FIFO）；
2. **业务缺口优先级：** 中文规则、证据/审计、未知/升级、成本/闭环中，第一批内部冻结集合先做哪两类；
3. **多模态/闭环时机：** 是否在 P0/P1 文本直接驱动完成后再启动 P2（建议如此），以免改变文本 NxM 的验收轴。

这些决策只影响候选队列顺序，不会改写 D1 历史指标，也不会绕过准入合同或 TEST ticket。

## 4. 下一阶段可验收产物

### Milestone M0：范围与合同

- P0 每个来源的 manifest、版本/hash、split、字段、公式、分母和许可证；
- item-level lineage 与 TEST 暴露审计；
- `ready_for_inference`/`needs_review` 收据和 FIFO 清单；
- D1 38 单元的只读回归检查，确保数值与上一版一致。

### Milestone M1：P0 直接驱动

- 逐面板 reference-native 指标表和复算表；
- Qwen3.5 NxM 直接驱动结果、失败/拒答与 paired decision 报告；
- 约十分钟 watchdog digest、终端 marker、恢复命令和 Wiki 最新结论。

### Milestone M2：工程学习基线

- 选定并预注册 SFT/LoRA、proper-scoring、校准基线；
- 在同一任务轴比较四类收益来源；
- 只使用已经锁定的 DEV/TEST ticket，不因结果修改指标或分母。

### Milestone M3：业务缺口与 RL

- 冻结内部缺口集合并完成直接驱动基线；
- 明确每个缺口的阻塞项和可承载任务；
- 设计 RL 目标、约束、成本和可用 baseline，单独申请运行。

## 5. 当前不应作出的结论

- 不能把 25–30 个来源或 70+ 面板写成已完成实验；
- 不能把候选面板的缺失指标写成零；
- 不能因训练任务正在运行就提前宣称 TEST 收益；
- 不能把不同公式、分母、温度或同源改写合并成一个总分；
- 不能用新增范围反向修改已冻结 D1 读数。

## 证据入口

- [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md)
- [`proposal/19-dataset-coverage-expansion-v7-status-2026-11-02.md`](19-dataset-coverage-expansion-v7-status-2026-11-02.md)
- [`.local/reports/p0-common-text-metadata-audit-20261102.md`](../.local/reports/p0-common-text-metadata-audit-20261102.md)
- [`wiki/CURRENT-CONCLUSIONS.md`](../wiki/CURRENT-CONCLUSIONS.md)

