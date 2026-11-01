# 数据集覆盖扩展 v5：从 Jev 专门集合扩展到能力轴

**日期：** 2026-11-02  
**状态：** 计划和来源登记；不产生新的 Qwen3.5 指标，不授权读取新增 TEST。

## 结论

用户关于“数据集选少了”的判断仍然成立。v4 已经把候选登记扩展到约 16–17 个来源/任务族和 50+ 个原生测试面板，但这仍主要是 Jev 专门 benchmark 的横向拆分。它回答了不同 Jev 工作的结果如何比较，却没有充分覆盖我们业务要求对应的能力轴：普通分类和路由、排序与顺序敏感性、数值/时间、拒答和选择性预测、概率语义、分布漂移、证据/审计、闭环动作以及多模态输入。

D1 的事实范围不变：冻结的 38 个模型×数据集单元中 36 个有结果，Open-Jev-2B×JEVal 和 Open-Jev-9B×JEVal 仍为 `blocked/null`。新增来源不会改写这些数值；所有新增面板必须先完成来源、split、输入接口、配对键、指标公式、分母和 TEST 暴露审计。

## 覆盖现状与新增来源

本地 Jev 数据目录的数量不能直接代表独立数据集。当前已知库存包括 24 个目录、23 份数据卡，以及若干位于 `/mnt/cephfs/xingchao/omni/repos/jev/` 的独立评测仓库。目录和仓库之间有版本投影、结果包、同源子集和模态重叠，必须按来源指纹去重。

### A0：优先登记、可形成共同测试的文本来源

这些来源有本地镜像和可追溯结果/数据文件，但其已有结果只能作为参考文献结果；只有完成逐行 TEST 合同并由验证器签发 `ready_for_inference`，才可以进入 Qwen3.5 推理队列。

| 来源 | 本地证据 | 覆盖能力 | 处理规则 |
|---|---|---|---|
| AppliedMachineLearning-Lab Jev benchmarking | `omni/repos/jev/AppliedMachineLearning-Lab__jev-benchmarking`；37 个公开任务报告 | choice/noul/score、跨域、多语言、moderation、grounding、OOD | 先登记 37 个原生面板；accuracy、F1/AUPRC、相关系数、MAE、校准分开；不能把 Jev-1.13.0 的结果当作 Qwen 结果 |
| JevBench v1.6.1 | `omni/repos/jev/fstandhartinger__jevbench`；公开 231 面板及 private aggregate | typed choice/noul/score、难度、校准、成本 | 只把可复核 public 231 作为候选；private/leaderboard 数字保留为文献对照 |
| Intern-Decision | `omni/repos/jev/InternLM__Intern-Decision`；accuracy/calibration suites | JevBench、Typed Decision、ToolACE、AG News、WildJailBreak、known-distribution | 固定后端、温度、输入格式和来源；known-distribution 与普通 accuracy 分列 |
| Jevals | `omni/repos/jev/Jevals__jevals-data`；Banking77、PubMedQA、HelpSteer2 | choice、noul、ordinal score 三类 primitive | 作为小而完整的 typed smoke/common tranche；三种 primitive 和分母不合并 |

首批建议共同测试面板为：JevBench public 231；Jevals 的 Banking77、PubMedQA、HelpSteer2；Applied ML 中 BoolQ、Banking77、CLINC150/OOS、ANLI、HellaSwag、ARC、CommonsenseQA、MMLU/C-Eval、STS-B、SST-5、SummEval、HelpSteer2。这里的“建议”只是准入顺序，不表示这些面板已经授权推理。

### A1：补充业务和协议能力的候选

| 来源/面板 | 主要缺口 | 首要准入条件 |
|---|---|---|
| Decision Model Benchmark | complete-message accuracy、OOS、延迟/成本 | 与 Banking77/CLINC150 的来源重叠和 NLU++ 分母分开 |
| TDM prevalence shift | 先验分布变化下的校准和风险 | 固定 prevalence 曲线、重复次数、测试行和未见 split |
| System-One coherence | 直接与重构/层级决策的一致性、重复和顺序 | 保留 paired question graph；一致性不能用总 accuracy 替代 |
| This-That spatial/model benchmark | 空间状态、复合规则、模拟器真值 | deterministic/stochastic、记录集/生成集和 simulator 版本分开 |
| Jev OOD calibration | unknown/OOD 识别和噪声底校准 | OOD 标签、noise-floor ECE、coverage-risk 公式冻结 |
| ORDER BY robustness | 排序、序敏感和 ties/inversion | 排序候选、tie 规则、逆序率和 paired key 冻结 |
| DecisionPivot、DecisionRobust text、Eikos、Korean、Respan、Complex/Spatial、Guardrails | 对比扰动、跨语言、复杂规则、安全边界 | 延续 v4 的来源、指标、分母、curated/full 和 pairing 审计；当前仍不得读取候选 TEST |

这些来源不能被简单加总。普通 accuracy、complete-message accuracy、Macro-F1/AUPRC、ordinal correlation/MAE、ECE/Brier、coverage-risk、paired flip 和 cost/latency 都要各自列出；只有目标、分母和输入语义完全一致时，才补充统一 decision-level 指标。

### A2：独立多模态矩阵

UniJev（文本/图像/视频）、OneJev 和 DecisionRobust image 具有独立输入接口、模态和来源分层。它们必须单独建立矩阵，不能把图像/视频缺失替换成文本零值，也不能把多模态结果混入当前文本 Qwen3.5 NxM 总分。Imajev 继续保持 blocked，直到 release gate、标签和公开 TEST 都可复核。

### A3：公开集合仍无法承载的自建任务

公开集合仍缺少业务作者规则、中文数字/日期和规则版本变化、显式 unknown/fallback、证据状态与审计回执、业务等价类、升级成本和端到端每正确结果成本。后续自建集合至少包含：

- 业务作者编写的规则与同义改写，按规则族留出 test；
- 中文业务数值、日期、区间和等级，保留可判定/不可判定两组；
- unknown、拒答、fallback、升级和风险预算，报告 coverage-risk-cost 曲线；
- 证据支持/冲突/缺失、来源版本和可审计回执；
- 单步问题与闭环动作的成对任务，分别报告正确率、约束违反、步骤数和成本。

这些集合先做直接驱动基线，再决定是否纳入 SFT/LoRA；真实业务样本和生产接入仍不在本阶段范围内。

## 四个维度的覆盖判断

1. **Jev 增益来源：** 现有 D1 能比较驱动形态、结构、任务数据和学习方法，但新增 A0/A1 才能把“任务泛化”和“概率/选择性收益”从单一 typed-choice 中拆出来。
2. **任务/数据集指标：** 现有 D1 的 native temperature、raw T=1、hard/soft、Brier/ECE/KL/MAE 已分列；v5 继续按原生公式统计，不建立跨公式总分。Applied ML 的 37 个任务结果只作为参考模型文献表，Qwen3.5 需重新在锁定 TEST 上推理。
3. **业务要求：** A0/A1 承载分类、排序、校准、跨域、鲁棒性和部分拒答；证据审计、中文业务规则、等价类和成本仍需 A3 自建；闭环动作和图像/视频进入独立矩阵。
4. **自身实验：** 先完成 A0 元数据和重叠审计，再让首批可准入文本面板进入 FIFO；CPU scorer、来源核验、报告和 Astra 审查异步执行。A1 只在 A0 共同测试合同稳定后推进；A2 不阻塞文本 NxM；A3 在直接驱动基线之后进入训练设计。

## 下一步执行顺序

1. 为 Applied ML、JevBench、Intern-Decision、Jevals 生成只读来源合同：版本/hash、split、item 数、输入字段、目标类型、公式、分母、来源交集和 TEST 暴露。
2. 先处理与现有 D1 重叠最大的 Banking77、CLINC150、MASSIVE、PAWS、Civil Comments，建立 item-level lineage 表；重叠行不得计入未见来源泛化。
3. 对 A0 通过合同的面板生成 `ready_for_inference` 收据，加入 NPU FIFO；未通过者保持 `needs_review`，不读取候选 TEST。
4. NPU 继续按任务队列运行，约十分钟轮巡 watchdog digest；CPU 端并行完成 scorer、指标表、来源审查和最新报告。
5. 每个 milestone 只增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 和 `wiki/CURRENT-CONCLUSIONS.md`；旧过程文件按三天周期归档到 `.local/archive/`。
6. 文本共同测试首轮完成后，再决定 A1 的优先子集和训练混合；RL、真实业务和生产闭环继续后置。

## 当前决策状态

本轮不需要用户改变既定范围即可执行。默认纳入 A0 的四个来源，默认把 Applied ML 的 37 个任务登记为参考文献/来源候选而不是现成 Qwen 指标，默认把 A2 与 A3 分开。若用户希望进一步压缩或扩展，只需改变 A0 首批共同测试面板，不影响 D1 冻结结果。

机器审计依据：`.local/reports/candidate-inventory-20261102.md`、`.local/reports/panel-gap-design-20261102.md`、`/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/reference_table_manifest.json`。这些文件没有授权读取新增 TEST，也没有产生新的模型指标。
