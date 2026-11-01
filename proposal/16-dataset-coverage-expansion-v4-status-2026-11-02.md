# 数据集覆盖扩展 v4：现状、缺口与执行计划

**日期：** 2026-11-02  
**状态：** 覆盖修订已完成，新增面板仍处于元数据/来源/指标准入阶段；本文件不产生新的模型指标，也不授权读取新增候选 TEST。

## 结论

“数据集选少了”的判断成立。问题不在于本地没有数据目录，而在于当前 D1 冻结矩阵主要集中在 Kev、Nimble、Typed Decisions、Open-Jev 和 JEVal 几条路线；多个独立任务族、对比组、鲁棒性和概率语义面板尚未进入同一覆盖盘点。

当前必须同时报告四种数量，避免把目录数量误当成科学覆盖：

| 数量 | 当前读数 | 解释 |
| --- | ---: | --- |
| 本地目录库存 | 24 | 包含版本投影、结果包、同源子集和不同模态，不能直接相加为独立数据集 |
| 独立来源/任务族候选 | 约 16–17 | 按发布者、版本、来源指纹和任务语义去重后的候选族 |
| 原生 TEST/eval 面板 | 50+ | 一个来源按 config、split、variant、task/family、统计公式拆开后的面板 |
| 已冻结 D1 模型×数据集单元 | 38 | 36 个已有结果，2 个 Open-Jev×JEVal 仍为 blocked/null；这不是候选全集 |

新增候选目前没有进入推理队列。v3 元数据审计结果为 4 个新增来源、`ready_for_inference=0`、`needs_review=4`；没有读取候选 TEST 行，没有启动新增推理或训练。

## 一、按模型/方法看覆盖缺口

现有材料已经能覆盖一部分“直接改变驱动形态”的收益和基础校准，但还不够区分以下四类贡献：

1. **驱动形态变化**：同一基础模型通过 typed readout、概率接口、温度或 harness 改变得到的收益。Kev、Nimble、Open-Jev、JEVal 和 Typed Decisions 的现有面板属于这一层的主要证据。
2. **结构改造**：改变模型结构或加入专门头部、状态表示、视觉输入后带来的收益。复杂决策、空间决策、多模态 DecisionRobust image 和未来的结构对照需要独立面板，不能和文本驱动结果混报。
3. **任务与训练设计**：为特定任务设计数据、标签和训练配方后得到的提升。BEV、Typed Decisions、Open-Jev v1.1、jev-bench 和 DecisionBench 的 train/dev/test 需要先完成来源隔离，再用于 NxM 训练选择。
4. **学习/优化方法**：校准、proper scoring、选择性预测、对比学习、蒸馏以及后续强化学习带来的提升。当前公开测试能承载一部分校准和选择性指标，但业务 unknown/fallback、审计轨迹和成本约束仍然缺数据。

因此，扩展数据集的目标不是追求一个更大的总平均，而是让每类贡献至少有一组独立测试面板和明确的对照统计。

## 二、按任务和数据集看新增面板

### A 层：优先纳入文本参考 TEST/共同比较矩阵

这些任务与当前 Qwen3.5 文本主线接口较接近，优先完成元数据、来源交集和指标审计。每个面板单独计算原生指标，并保留统一 decision-level 指标；不同公式、分母和配对关系不合并。

| 来源/任务族 | 原生面板规模或结构 | 需要分列的指标/统计 | 当前状态与准入动作 |
| --- | --- | --- | --- |
| `Praveenrajus/jev-bench` v0.1.1 | 22 个来源，22,773 条 TEST | 每来源 accuracy；ChaosNLI/校准来源另报 expected accuracy、ECE、Brier、RPS、selective accuracy、TVD | 高优先级；先做 massive/PAWS/Civil Comments 与 Nimble 的 item/source identity 审计 |
| `Hanno-Labs/decision-bench` | 43 task IDs、27 families、28 domains、3 primitives、23,900 eval | row accuracy、task/family macro；probability 字段存在时另报 ECE/Brier；standard/compact 分开 | 高优先级；固定 canonical/applied/reasoning 来源和输入字段 |
| `akhilaaa3/decision-bench` | medium、hard 两个 test 面板，各 80 states/293 questions | state-macro accuracy 与 question-weighted accuracy、ECE、confidence gap、cost/state 分开 | 高优先级；不与 canonical DecisionBench 合并 |
| Eikos Decisions | tradeoff、healthcare、Spanish core heldout，eval suites 单列 | 按 type/family/language 的 accuracy；有概率时才报 calibration | 高优先级；确认 heldout 与 eval、FinEntity 来源隔离 |
| Korean JEV | Korean evaluation 与 English comparison | Korean/English accuracy、order agreement，按来源/子集分层 | 迁移优先；不用于替代中文业务任务 |
| Respan Behavior | core、multilingual，按 task_id/behavior_type/language | `present` F1 的 macro/weighted、task_id bootstrap；标签称教师/构造标签 | 边界优先；不称作自然 ground truth |
| DecisionPivot | 13 个 core family，另有 35 个 reference task | benchmark accuracy、contrast/paired consistency、core/reference 分开 | 高优先级；contrast group 不压成普通 accuracy |
| DecisionRobust text | clean、text adversarial、text injection 的 curated/full | clean accuracy、attack success、flip、stable-correct、stable-wrong；curated/full 分开 | 高优先级；按原始请求配对统计 |
| Complex Decisions | 19 family，含复杂规则、缺信息、多步状态 | answer-index accuracy、family macro、constant/question-only discrimination | 第二批；先固定 family、unknown 语义和判别对照 |
| Spatial Decisions | deterministic、stochastic、seen-in-training 分层 | deterministic accuracy；概率指标只对成立的 stochastic 分布字段计算 | 第二批；先完成 simulator/family 审计 |
| Guardrails / JEV Safety | content、prompt attack、denied topic、serialization/original/reversed | class-wise rate、balanced/collection macro、paired flip/stability | 第二批；只作为安全/鲁棒性诊断，不称生产安全 |

### B 层：单独保留的迁移、多模态和边界面板

- DecisionRobust image 的 6 个面板单独建立多模态矩阵；curated 是 full 的子集，不能拼接或平均；文本 Qwen3.5 不能用补零替代图像输入。
- WebJev 当前发布物只有 train，不能称公开 TEST；要先注册内部 heldout，再决定是否进入训练/评估。
- OneJev-Data 只有 train，作为多模态训练来源审计，不计入当前公开 TEST。
- Imajev 标签隐藏且 release datasheet 门禁未通过，保持 blocked。
- `btzsc` 通用分类集合尚未证明 typed-decision schema，暂列普通分类边界对照。
- Laya 作者自定义 probe 只作为文献对照，不与正式 benchmark accuracy 混合。

### C 层：需要后续自建的数据

公开集合仍不能承载业务作者规则、中文业务数字/日期、unknown/fallback、证据状态、规则版本变化、升级成本、审计轨迹、业务等价类以及端到端每正确结果成本。这些必须建立冻结 train/dev/test 和来源指纹，不能用继续增加公开目录代替。

## 三、按业务要求看还缺什么

现有公开任务可以承载：有限候选选择、boolean/nominal/ordinal 输出、部分概率校准、反事实或改写稳定性、跨领域迁移、攻击扰动和多语言迁移。

仍然缺失或只被孤立论文覆盖的业务要求包括：

- 业务人员编写规则后模型是否忠实执行；
- unknown、拒答、fallback 和升级成本；
- 证据状态、审计可追溯性和同一业务等价类的一致性；
- 中文业务规则中的数字、日期、等级和规则版本变化；
- 阈值跨任务/跨 fallback 模型迁移；
- 一次判断拆成多个判断后的总体校准；
- 端到端每正确结果成本和风险预算。

这些缺口会作为业务数据集设计和后续强化学习目标，而不是在本轮公开 TEST 统计中假装已经覆盖。

### D 层：业内对齐候选（尚未镜像）

文献审查还发现以下公开面板值得登记，但它们目前不在本地准入矩阵中，也没有被计入“50+ 原生面板”：System1-Arena 的大规模问题与闭环环境、TypedBench 的策略合规/改写/选择性预测组合、JevAdvBench 的答案保持攻击、Sys1Cal-v1 的已知概率真值、Probability Contracts、PFR/拒答测试、AgentDecisionBench/DecisionGym，以及 TUPLE-Bench 的接口泄漏维度。它们分别覆盖闭环控制、概率语义、攻击鲁棒性、拒答和隐私泄漏，不能与普通 accuracy 面板合并。

这些候选的接入顺序是：先记录论文版本、公开下载位置、原生 split 和指标公式，再判断是否有可复核 TEST；没有可复核 TEST 的只保留文献对照。镜像后仍需完成输入接口、来源交集、测试暴露和 paired key 审计，只有 `ready_for_inference` 才能入 FIFO。

## 四、自身实验维度与执行顺序

### M0：覆盖合同和准入（当前）

1. 逐面板固定版本、文件/数据 hash、split、行数、task/family、来源族、指标公式、分母、配对键和输入模态。
2. 对 jev-bench 的 4 个已知重叠来源做 item/source identity 审计；对两个 DecisionBench 来源做独立 lineage 审计；对 image 做接口和 curated/full 审计。
3. 只有合同验证器签发 `ready_for_inference` 收据的面板才进入 NPU FIFO；当前 4 个新增条目全部拒绝入队。

### M1：公开 TEST 参考模型推理

优先顺序为：去重后的 jev-bench source panels → canonical/legacy DecisionBench → Eikos/Korean/Respan → DecisionPivot/DecisionRobust text。每个面板按原生公式和分母汇报，并按 10 分钟左右轮巡读取 watchdog digest；不直接读取原始日志。

NPU 推理任务必须 detached、可恢复、带 heartbeat、EXIT、RELEASE、SUPERVISOR_DONE 和 relaunch 命令；CPU scorer、来源核验、报告和 Astra 审查与 NPU 队列异步执行，保持 NPU 满载。

### M2：鲁棒性、复杂/空间、安全和多模态

在 A 层文本主线首轮结果入账后，继续审计 Complex、Spatial、Guardrails/Safety 和 DecisionRobust image。多模态和文本结果分别维护，不能混在 Qwen3.5 文本主线的 NxM 笛卡尔积中。

### M3：更新 D1 参考报告

新增面板必须经过独立 scorer 验收和来源审查后，追加到扩展矩阵；原有 38 个模型×数据集单元及其历史读数保持不变。每个 milestone 完成后增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 和 Wiki 当前结论；过程材料只在本地 `.local` 留存，并按三天周期归档。

### M4：NxM 直接驱动基座

先完成同一批参考模型在已准入任务上的直接驱动结果，再冻结 Qwen3.5 的 NxM 任务矩阵。DEV/calibration 用于选择和调参，TEST 只做最终报告；不能用候选 TEST 结果倒过来选择训练混合。

### M5：学习、优化和业务缺口

在 K0 直接驱动完成后，比较 CE/LoRA 与一个 proper-scoring/calibration challenger；再建立业务缺口数据、unknown/fallback 基线，最后设计强化学习优化目标和可用基线。训练收益必须同时报告域内、未见来源和鲁棒性，禁止用单一平均数代替。

## 当前进度与需要决策的内容

当前没有阻塞执行的必答决策，默认按 A→B→C 和 M0→M1→M2 顺序推进。以下三项会改变范围，但都有默认值：

1. `btzsc` 是否进入正式扩展报告：默认仅作 B 层普通分类边界对照，不进入 Jev 主矩阵。
2. 是否把 DecisionRobust image、Imajev、OneJev 纳入当前文本 Qwen3.5 主线：默认不纳入，建立独立多模态/阻塞记录。
3. 是否把 Laya 作者 probe 作为正式任务：默认只作文献对照，不与公开 TEST 指标合并。

除非你另行改变范围，我会继续完成 M0 合同和来源审计，并在首批面板获得 `ready_for_inference` 后自动进入 NPU 队列；本文件不代表任何新增面板已经有模型指标。

## 权威记录

- [当前参考基线](../experiments/REFERENCE-BASELINE-LATEST.md)：已冻结结果和历史读数的权威入口。
- [v3 元数据审计](../.local/reports/dataset-expansion-v3-metadata-audit-20261102.json)：新增 4 个来源均为 `needs_review`。
- [v3 覆盖扩展方案](15-dataset-coverage-expansion-v3-2026-11-02.md)：上一版候选和准入说明。
- [数据集合同验证器](../tools/validate_dataset_panel_contract.py)：fail-closed 准入规则。
