# 数据集覆盖扩展 v2：从六个任务族扩展到完整任务轴

**日期：** 2026-11-01
**状态：** 覆盖扩展规划与准入分层；尚未读取新增候选 TEST 样本，尚未启动新增推理或训练。

## 结论

用户指出“数据集选少了”是成立的。当前公开评估契约只有 **6 个任务族、14 个评估单元**：Kev（3 个单元）、Typed Decisions（1）、BEV（5）、Open-Jev v1.1（2）、DecisionPivot（1）和 DecisionRobust 文本（2）。这足以覆盖 typed readout、数值/时间、校准、规则诊断和文本鲁棒性的第一轮，但不能支撑广泛的 Jev 能力结论。

本地库存已发现 **24 个数据目录**，但目录数不是独立数据集数：其中包含 Open-Jev 的旧版与 v1.1、DecisionBench 的不同发布者、结果包、来源投影、同源子集以及文本/图像/视频混合数据。扩展目标因此不是把 24 个目录全部接入，而是把任务轴补齐，并在每个任务族内核实来源、划分、统计公式和 TEST 暴露。

本版将候选范围扩展为 **12 个任务族候选**，按三批处理：

1. **第一批直接测试扩展（8 个任务族）**：现有 6 个任务族，加上复杂确定性决策和空间决策。
2. **第二批边界与迁移诊断（再加 3 个任务族）**：安全/guardrail、多语言、网页/行为。
3. **第三批模态扩展（再加 1 个任务族）**：图像/视频 typed decision。

“候选任务族”不是“已准入任务”。只有在 split、来源族、候选字段、指标公式和测试暴露均核验通过后，才允许进入推理队列。

## 当前覆盖与缺口

| 维度 | 当前状态 | 缺口 |
| --- | --- | --- |
| 输入分布 | 以英文/合成 typed text 为主，覆盖少量数值、时间、工具技能和文本扰动 | 复杂状态、多步政策、空间状态、网页交互、多语言和视觉证据不足 |
| 决策类型 | boolean、nominal、ordinal、choice、score 已有 | unknown/fallback、拒答、证据不足、连续成本/升级决策没有统一承载 |
| 泛化来源 | decision-v7、transfer-v4 和公开参考集存在，但来源族去重尚未完成 | 规则族、场景族、网站族和作者来源的 held-out 仍需固定 |
| 统计口径 | accuracy、Brier、ECE、NLL、KL、expected accuracy 已分列 | paired invariance、abstention、selective risk、cost/correctness 尚无统一冻结协议 |
| 模态 | 当前主线是文本；多模态目录仅作库存 | 图像/视频任务需独立模型接口和新 harness，不能混入文本总分 |
| 业务承载 | 公开集能承载类型、校准、规则一致性和部分鲁棒性 | 业务作者规则、审计状态、unknown、升级成本和中文业务规则仍缺数据 |

## 扩展任务族矩阵

### 第一批：直接测试扩展

这批回答“参考模型在更多测试集上的表现如何”，优先于训练方案讨论。所有任务均先发布原生统计，再决定是否计算统一 decision-level 指标。

| 任务族 | 本地目录/来源 | 主要承载能力 | 首批固定单元 | 进入队列前的硬条件 |
| --- | --- | --- | --- | --- |
| Kev | `jaredpalmer__kev-suites` | hard、documents、devtools typed decision | hard、documents、devtools release/full | 版本、mask、行数、原生公式、来源重叠 |
| Typed Decisions | `LocalLLaMA__typed-decisions` | boolean/nominal/ordinal、校准 | 四领域 common test | scenario/group 边界、scorer、Track T 暴露 |
| BEV | `avbiswas__bev-decision` | 数值/时间、技能、反事实 | default、hard_50k、numeric_temporal、skills、counterfactual | config hash、成对关系、来源族和分母 |
| Open-Jev | `ZefanCai__Open-Jev-v1.1` | 中英文 typed、soft target、OOD | test、ood | 版本投影、source family、hard/soft 分母 |
| DecisionPivot | `startlux-models__DecisionPivot` | 规则组合、状态更新、配对一致性 | core 13 families | core 与 35 reference tasks 分离、pair schema |
| DecisionRobust | `yflantmy__DecisionRobust` | 文本攻击、注入、答案不变性 | text curated/full | clean/attacked 配对、curated/full 去重 |
| Complex decisions | `limberc__this-that-complex-decisions` | 多字段政策、缺信息、多步规则 | test，按 family 分层 | 原生 test、未知类判别对照、规则族 holdout |
| Spatial decisions | `limberc__this-that-spatial-bench` | 空间状态、路径和模拟器真值 | test，按 environment/family 分层 | simulator 版本、状态去重、family holdout |

第一批从 6 个任务族扩展到 8 个任务族；复杂和空间任务都属于确定性诊断，不直接当作真实业务收益。

### 第二批：边界与迁移诊断

| 任务族 | 本地目录/来源 | 主要承载能力 | 建议顺序 | 准入注意 |
| --- | --- | --- | --- | --- |
| Safety/guardrail | `raxITLabs__decision-models-as-guardrails`、`SabaPivot__jev-safety-bench` | prompt attack、PII、拒答、选项顺序鲁棒性 | 先 guardrail text，再 safety pair | 不称生产安全；原始/反转/序列化必须成对 |
| Multilingual/behavior | `DaehanKim__korean-jev-benchmark`、`respanai__behavior-benchmark`、`caiovicentino1__eikos-decisions` | 韩文、多语言、跨领域决策 | 先 Korean，再可比行为子集 | 语言与来源族分层；原生统计不可强行合并 |
| Web/action | `Lexmount__WebJev` | 网页元素定位、动作预测、工具路由 | 先 metadata 和网站族审计 | 必须有任务/网站隔离；不能用仅 train 卡片伪称 TEST |

第二批的目标是识别边界退化和跨域迁移，不改变第一批的训练选择或 TEST 门槛。

### 第三批：模态扩展

| 任务族 | 本地目录/来源 | 主要承载能力 | 处理方式 |
| --- | --- | --- | --- |
| Vision/video typed decisions | `mohit67890__imajev-bench`、`OmniJev__OneJev-Data` | 图片/视频证据、Unknown、对比集 | 独立 multimodal harness；文本模型不支持的格子标 `unsupported`，不补零 |

第三批不与当前文本 NxM 总分合并。只有在模型接口、图像读取、样本许可和独立测试协议完成后，才建立单独的多模态矩阵。

## 不计作独立覆盖的目录

以下目录仍保留在库存中，但在独立数据集计数时不直接新增任务族：

- `ZefanCai__Open-Jev`：与 v1.1 相关的旧版/发布投影，需按版本和来源族记录，不能与 v1.1 简单相加。
- `carlosxiang__JEVal`：现有参考基线中的任务，不因重新列出而成为新增任务族。
- `bespokelabs__bespoke-nimble-9b-v3-decision-index`：结果与代码包，不是训练数据集。
- `Luni__laya-jev-benchmark`：比较材料和引用结果，需先区分已发布数字、实测数字和数据来源。
- `akhilaaa3__decision-bench` 与 `Hanno-Labs__decision-bench`：同名不代表同源，完成来源交集后再决定是否合并或分别统计。
- `btzsc__btzsc`：通用分类数据，尚未证明 typed-decision schema，暂不纳入 Jev 任务族。

## 扩展后的 NxM 执行设计

### M 轴：任务族与统计面板

M 轴不使用一个总平均表示。每个任务族展开为若干面板：原生指标、统一可比指标、按 decision type/family 的分层指标、paired 指标（有成对关系时）和来源/暴露状态。缺失公式、分母或字段的面板保留 `needs_review` 或 `not_comparable`。

### N 轴：模型

N 轴沿用当前参考模型，并逐步加入 Qwen3.5 小于 10B 的 K0/K1 候选：0.8B、2B、4B、9B。模型不支持某一模态或接口时写 `unsupported`。先完成参考模型在扩展任务上的测试集汇报，再讨论混合训练和学习方法；新增 TEST 结果不能反向挑选训练方案。

### 运行顺序

1. CPU 并行完成每个任务族的来源、split、mask、公式、字段和暴露审计，生成 machine-readable contract。
2. 只有 `ready_for_inference` 的格子进入 NPU FIFO 队列；每个 job 写固定 plan、资源归属、恢复命令、CephFS 日志、heartbeat 和终态 marker。
3. NPU 按队列持续运行；CPU 同时做 scorer、来源核验、结果汇总和独立审查。常规状态只读 watchdog digest，约 10 分钟一轮，不读取原始日志。
4. 公开测试指标先按原生方法和统一方法分栏汇报；不合并不同分母、温度、mask 或 hard/soft target。
5. 第一批测试指标完成并经过独立复核后，才冻结下一轮训练数据混合和学习方法。

## 需要用户决策的内容

当前没有阻塞执行的必答项。按照现有授权，默认采用“第一批直接测试扩展 → 第二批边界诊断 → 第三批模态扩展”的顺序，保持真实业务接入和 RL 后置。

只有以下两项会改变计划，若你希望改变可以再指定：

1. 是否把第二批的安全/多语言/网页任务提前到第一批；默认不提前，先完成确定性任务和来源核验。
2. 是否把视觉/视频作为当前 Qwen3.5 文本主线的一部分；默认独立成多模态矩阵，不阻塞文本评估和训练。

没有新决策时，我会继续完成第一批 8 个任务族的合同核验；在全部合格前不启动新增候选 TEST 推理。

## 当前阶段完成标准

- 8 个第一批任务族各有版本、split、mask、样本数、来源族、原生指标和统一指标字段。
- 复杂/空间任务的规则族或 simulator family holdout 已登记，且有判别对照。
- 参考模型在可比 TEST 上的结果按任务族和统计方法分表；不能运行的格子显式记录原因。
- 新增推理前通过独立 CPU/执行审查；NPU FIFO 不因 CPU 报告串行而空闲。
- 第一批完成后刷新 `REFERENCE-BASELINE-LATEST.md`、Wiki 当前结论页和本地状态报告；历史过程文件按三天周期归档。

本文件不产生新模型指标，也不改变现有冻结 TEST、训练门槛和历史读数。

## 元数据审计后的准入更新

2026-11-01 的只读审计已经完成第一轮，结果写入本地 `.local/reports/dataset-expansion-*-audit-20261101.json` 和 `.local/preparations/dataset-expansion-contract-20261101-v1/CONTRACT.json`。这些文件只读取 README、数据卡、清单和小型元数据，没有读取候选 TEST 样本、模型输出或权重，也没有启动新增推理。

- `this-that-complex-decisions` 声明 1,710 个问题、19 个 family，原生按 `answer_index` 做 accuracy；没有显式 unknown 机制。它可作为确定性规则诊断候选，但还需要固定 family/schema、来源指纹和 question-only/常量判别对，因此当前仍是 `needs_review`。
- `this-that-spatial-bench` 声明 7,305 个问题、15 个 family，包含 6,805 个确定性问题和 500 个 stochastic 问题；2,000 个问题标记为作者训练形状。deterministic、stochastic 和 `seen_in_training` 必须分层，不能合并成一个准确率；当前均为 `needs_review`。
- `decision-models-as-guardrails` 有六个固定 test 配置和发布的 0.5 阈值，但存在 ids-only 行、来源/厂商暴露和子任务不平衡，必须按配置、类别和来源状态分列；当前为 `needs_review`，不能表述为生产安全结论。
- `jev-safety-bench` 的 original/reversed/serialization-control 复用同一请求，必须以 `pair_id` 做成对统计，不能把 variant 当独立样本；当前为 `needs_review`。
- Korean JEV 只有一个 evaluation split，没有 train/calibration split；Eikos 的 heldout 可以作为候选，但其 evaluation 文件必须与训练分离，并遵守 FinEntity 排除说明。两者当前均为 `needs_review`。
- WebJev 只发布 train split，需按 `task_id` 另行预注册 held-out；在此之前不能汇报公开 TEST，当前 `blocked`。
- ImajevBench 的 test 标签隐藏，且 datasheet 明确记录 statistical-power、image-necessity 和 construction-lint 门禁未通过；当前 `blocked`，不得在本地生成最终测试分数。
- OneJev-Data 只有 train，sample 也是 train 子集；它可作为未来多模态训练来源调查，不能作为参考 TEST，当前 `blocked`。

因此，扩展后合同共有 16 个新单元：12 个 `needs_review`、4 个 `blocked`，当前没有任何新增单元获得推理授权。只有完成逐单元来源/指标/执行审查并形成独立准入收据后，才可将单元加入 NPU FIFO。
