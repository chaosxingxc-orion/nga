# 数据集覆盖扩展 v3：从 12 个候选族扩展到原生测试面板矩阵

**日期：** 2026-11-02  
**状态：** 规划和元数据准入阶段；本版没有读取新增候选 TEST 样本，没有启动新增推理或训练，也不修改既有冻结指标和历史读数。

## 结论

“数据集选少了”的判断成立。上一版已经把候选范围从 6 个任务族扩到 12 个，但仍把若干具有独立测试集、独立来源或独立统计公式的公开工作压缩成一个族，导致覆盖能力被低估。现在应把“目录数”“任务族”“原生测试面板”“模型×任务单元”四个概念分开：

- 24 个本地目录只是库存，不是 24 个独立数据集；其中包含版本投影、结果包、同源子集和多模态数据。
- 当前 D1 参考矩阵仍冻结为 38 个模型×数据集单元，36 个有结果，2 个 Open-Jev×JEVal 为 `blocked/null`；不能通过本文件追溯改写。
- 新的覆盖轴将纳入约 **16–17 个任务族/来源族、50 个以上原生测试面板** 的候选矩阵。每个面板保留原生 TEST、原生公式和分母；只有审计通过的格子才进入推理 FIFO。
- `Praveenrajus/jev-bench`、canonical `Hanno-Labs/decision-bench`、legacy `akhilaaa3/decision-bench` 和 DecisionRobust image 是上一版最明显遗漏的可审计候选；Eikos heldout、Korean JEV、Respan Behavior 和 DecisionRobust text 虽已出现在上一版候选中，本版将它们从“族级候选”提升为可独立计分的原生面板。
- 不把通用分类集合 `btzsc`、只有 train 的 WebJev/OneJev 或隐藏标签/发布门禁失败的 Imajev 伪装成公开 TEST；它们分别保留为边界候选、训练来源或阻塞记录。

## 扩展后的覆盖层级

### A 层：直接测试对齐（优先进入参考汇报）

这些来源有明确的公开 TEST/eval/heldout，且能够在只读元数据核验后建立固定 harness。它们回答“各参考模型在同一公开测试面板上表现如何”。

| 任务族/来源 | 原生面板 | 原生指标或统计方法 | 当前处理 |
| --- | --- | --- | --- |
| Kev suites | decision-v7、transfer-v4、hard-v1、documents-v1、devtools full/release | question-weighted accuracy、Brier、ECE、NLL；按 mask 分列 | 已在 D1，保持冻结 |
| Typed Decisions | common test，按领域和 boolean/nominal/ordinal | accuracy、KL、Brier、ECE；另保留 paired decision-level | 已在 D1，保持冻结 |
| BEV Decision Mix | default、hard_50k、numeric_temporal、skills、counterfactual_15k | 原生 accuracy/技能分项；counterfactual 另报 paired 指标 | 已纳入首批，待准入 |
| Open-Jev v1.1 | test、OOD，按 hard/soft target 和语言/来源族 | hard accuracy、expected accuracy、NLL、Brier、ECE | 已纳入首批，待准入 |
| DecisionPivot | core 13 families；35 reference tasks 单独列 | benchmark accuracy、paired consistency；core 与 reference 不合并 | 已纳入首批，待准入 |
| JEVal | 现有 reference/score/task panels | valid、overlength、unsupported、classification、score 分母分列 | D1 已冻结；缺失格子仍 `blocked/null` |
| Complex decisions | test 按 19 family | answer-index accuracy、family-macro；增加 constant/question-only 判别对照 | 新增，需来源和 family 审计 |
| Spatial decisions | deterministic、stochastic、seen-in-training 分层 | deterministic accuracy；stochastic 仅在分布字段成立时计算概率指标 | 新增，需 simulator/family 审计 |
| **Praveenrajus/jev-bench** | 22 个 native test configs：Banking77、CLINC150、MASSIVE、LEDGAR、GoEmotions、MMLU、ARC、MNLI、SST-5、Yelp-5、HelpSteer2×2、STS-B、Measuring Hate、BoolQ、FEVER、PAWS、Civil Comments、SMS Spam、StrategyQA×2、ChaosNLI | accuracy；有 calibration gold 时另报 ECE、Brier、RPS、selective accuracy、TVD；ChaosNLI soft label 不与 hard accuracy 合并 | **新增高优先级**；每 config 是独立面板，不能只报 22 个的总平均 |
| **Hanno-Labs/DecisionBench** | canonical eval：43 task IDs、27 families、28 domains；按 primitive（binary/candidate/ordinal）和 reasoning strata | row accuracy、task/family macro；如 probabilities 暴露，再报 ECE/Brier；按 task_id bootstrap | **新增高优先级**；一个 eval split 不等于一个单分数 |
| **akhilaaa3/DecisionBench** | medium、hard，各 80 states/293 questions | state-macro accuracy；question-weighted ECE、confidence gap、cost/state 分开 | **新增独立来源**；与 canonical DecisionBench 不合并 |
| **Eikos Decisions** | core heldout（tradeoff、healthcare、Spanish）；eval suites 单列 | accuracy 按 type/family/language；概率存在时才报 calibration | **新增高优先级**；heldout 与 eval 不能混用，排除 FinEntity 污染 |
| **Korean JEV Benchmark** | Korean evaluation、English comparison | Korean/English accuracy、order agreement；按来源/子集分层 | 新增迁移面板；无 train/calibration，不用于训练选型 |
| **Respan Behavior Benchmark** | core、multilingual；按 task_id/behavior_type/language | `present` F1、macro/weighted 分列；bootstrap over task_id，不按行简单聚合 | 新增边界面板；标签为教师/构造标签，不称 ground truth |
| **DecisionRobust** | text_adversarial curated/full、text_injection curated/full | clean accuracy、attack success/flip/stable-correct/stable-wrong；curated/full 不合并 | 新增高优先级；原始请求配对，不能当独立样本池 |
| Guardrails | content、prompt_attacks、denied_topics、word_filters、sensitive_information、grounding | accuracy、class-wise rates、balanced/collection macro | 新增安全诊断；不表述生产安全 |
| JEV Safety Bench | original/reversed/serialization-control | benchmark accuracy、paired flip/stability | 新增鲁棒性面板；variant 以 pair_id 统计 |

### B 层：边界、迁移和对照

这些面板有公开数据或结果，但与 A 层的 Jev typed-decision 主线不完全同构。它们应进入扩展报告，不能混入一个总平均：

- `WebJev`：当前发布物只有 train；必须先按 `task_id`/网站族注册内部 heldout，不能称公开 TEST。
- `Laya vs Jev`：可复核的 Phishing、typed-decisions 和 probe 结果属于参考工作/对照材料；probe 是作者自定义小套件，不与正式 benchmark accuracy 合并。
- `DecisionRobust` 的 image_* 面板：与文本鲁棒性共享部分来源但接口不同，另建 multimodal harness。
- `mohit67890/imajev-bench`：标签隐藏，且 release datasheet 的 statistical-power、image-necessity、construction-lint 门禁未通过，保持 `blocked`。
- `OmniJev/OneJev-Data`：只有 train，作为未来多模态训练来源审计，不是 TEST。
- `btzsc/btzsc`：包含大量通用分类 test，但尚未证明 typed-decision schema；只可作为普通分类边界对照，不能占用 Jev 主矩阵名额。
- `Hanno-Labs/DecisionBench` 与 `akhilaaa3/DecisionBench` 同名不同来源，必须独立报告，不用名称合并。

### C 层：业务缺口数据

公开集仍不能承载业务作者规则、可审计证据状态、unknown/fallback、中文业务数字/日期、升级成本和规则版本变化。这些要另建冻结 train/dev/test，不应通过再增加公开目录来假装已经覆盖。

## 推荐的面板计数方式

报告中同时显示四个计数：

1. **独立来源族**：按发布者、版本和来源指纹去重；当前候选约 16–17 个，不把结果包算数据集。
2. **原生测试面板**：一个来源内按 config/split/variant/任务族/统计口径拆分；当前候选 50+。
3. **模型×面板单元**：每个参考模型和面板独立有 `ready / needs_review / blocked / unsupported / scored` 状态。
4. **可比统计面板**：只在公式、分母、target、温度和输入接口一致时合并；否则并列表格。

禁止用“目录数”或“所有面板平均准确率”作为覆盖充分性的证据。对 `btzsc` 之类无法证明与 Jev schema 对齐的集合，保留在边界对照计数而不是主覆盖计数。

## 先后顺序与自动执行

1. **CPU 元数据审计并行**：为 A 层新增来源固定版本、文件 hash、split、行数、task/family、来源族、指标公式、分母、配对键和暴露状态；不读取候选 TEST 内容。
2. **NPU FIFO 维持工作**：只有得到 `ready_for_inference` 收据的面板进入队列。每个 job detached、可恢复、带 heartbeat、EXIT、RELEASE、SUPERVISOR_DONE 和 relaunch 命令。
3. **CPU scorer/分析异步**：NPU 执行时并行写 scorer、原生指标和统一指标转换；不等待 NPU 空闲后才分析。常规状态约 10 分钟轮巡，只读 watchdog digest。
4. **参考模型先于训练计划**：先完成 A 层已授权面板的参考模型 TEST 指标，再讨论数据混合、K1、学习方法和 RL；新增 TEST 读数不能倒过来选择训练集。
5. **分批发布**：每个 milestone 增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 和远程 wiki 当前结论；旧过程文件只留本地归档，不覆盖历史事实。

## 下一阶段里程碑

- **M0（当前）**：完成新增来源的 metadata contract；目标是 A 层新增 4 个来源族、至少 30 个原生面板完成 `needs_review` → `ready/blocked` 判定。
- **M1**：先运行 `jev-bench`、canonical DecisionBench、legacy DecisionBench、Eikos、Korean、Behavior、DecisionRobust text 的参考模型 TEST；每面板按原生公式发布。
- **M2**：完成 complex/spatial/guardrail/safety 的来源和配对审计，再决定是否加入 FIFO。
- **M3**：在新增参考指标经过独立 scorer 验收后，刷新 D1 增量报告；D1 原 38 个单元保持不变，新增面板以扩展矩阵单独编号。
- **M4**：冻结 Qwen3.5 NxM 训练面板；先 K0 直接驱动，再 K1 CE/LoRA 和一个学习方法 challenger，DEV 选择与 TEST 一次性读取分离。
- **M5**：业务缺口数据和 RL 后置，先建立直接驱动、SFT/LoRA、proper-scoring/calibration 基线。

## 需要用户决策

目前没有阻塞执行的必答项，默认按上述 A→B→C 顺序推进。只有以下选择会改变范围：

1. 是否把 `btzsc` 通用分类对照纳入正式扩展报告；默认保留为 B 层边界对照，不纳入 Jev 主矩阵。
2. 是否把 DecisionRobust image、Imajev、OneJev 纳入当前文本 Qwen3.5 主线；默认独立多模态矩阵，不阻塞文本参考评估和训练。
3. 是否把 Laya 的作者自定义 probe 作为正式任务；默认只作为文献对照，不与公开 TEST 指标混合。

若无新决策，我会继续做 M0 的元数据合同和逐面板准入；不会因“数据集更多”而绕过 split、来源、统计公式或资源准入门禁。

## 当前禁止的结论

本文件不产生任何新模型指标，不能称新增面板已经完成推理，不能把 `needs_review` 当作可运行，不能把公开任务提升写成真实业务收益，也不能把多模态/训练-only 来源补零进入总分。

## M0 元数据审计结果（2026-11-02）

第一轮新增来源审计已完成，机器结果保存在本地 `.local/reports/dataset-expansion-v3-metadata-audit-20261102.json`。审计只读取 README、manifest、dataset card 和发布元数据，没有读取候选 TEST 行、模型输出或权重。

| 来源 | 固定证据 | 当前状态 | 不能进入队列的原因 |
| --- | --- | --- | --- |
| `Praveenrajus/jev-bench` v0.1.1 | manifest SHA256 `eace4223…52209`；22 sources；22,773 TEST | `needs_source_overlap_review` | `massive`、`paws`、`civil_comments` 已与冻结 Nimble 面板的来源名和数据哈希对应上，但发布 TEST 数量与冻结抽样数量不同；必须做 item/source identity 审计，不允许直接当独立泛化证据 |
| `Hanno-Labs/decision-bench` | schema `decision-bench-hf-v2`；data SHA256 `6c97d3f3…893ca`；23,900 eval、43 task IDs | `needs_metric_source_review` | canonical/applied/reasoning 三个来源部分、standard/compact 输入和 probability 字段需独立固定 |
| `akhilaaa3/decision-bench` | README SHA256 `9031e3ff…48d5`；medium/hard 各 80 states、293 questions | `needs_source_overlap_review` | state-macro 与 question-weighted 统计必须分列，行身份和来源交集尚未核验 |
| `DecisionRobust` image v1.3.0 | manifest 与 dataset-info hash；6 个 image panels | `needs_multimodal_harness_review` | curated/full 有包含关系，clean/attack 需要配对；文本模型不能补零替代图像接口 |

所以本轮新增条目为 4 个，`ready_for_inference=0`，`needs_review=4`，`blocked=0`。只有逐项完成来源、指标和执行审查并签发准入收据后，才可把其中的面板加入 NPU FIFO。
