# 第一批公开任务评估前瞻登记草案

2026-11-01。状态：**登记草案，尚未冻结或运行**。本文件回应“先汇报各参考模型在更广测试集上的指标，再讨论训练计划”的要求。它列出候选评估对象、已知统计口径与待核实边界；不读取候选测试样本，不产生新模型读数，也不改变既有 `REFERENCE-BASELINE-LATEST` 或正式 K1/K0 预登记。

2026-11-01 更正：初版“登记完成”表述过强。P5–P8 的精确配置、公式、分母和来源哈希仍待核实；下表中的指标是候选核查项，不能当作已确认的原生公式。必须形成经核查的逐任务合同后才能冻结并运行。

## 共同规则

- 参考模型优先沿用当前基线中的 Kev-0.8B、Kev-4B、Kev-9B、Nimble-9B、Open-Jev-2B、Open-Jev-9B；没有可用权重或原生接口的格子保持 `unsupported`，不以替代模型填充。
- 原生发布指标与统一指标分开。原生指标使用数据集/参考工作声明的分母、温度、mask 和有效行规则；统一指标只在字段和标签语义完全可比时计算。
- `n`、split、mask、温度、阈值、候选数、无效/超长行处理和来源暴露状态必须写入每个结果行。缺少上游方法或不可复现时写 `not_comparable`，不强行换算。
- 测试集用于参考结果汇报本身不等于训练选择。若未来用某个候选 TEST 结果选模型或训练混合，该结果转为开发证据，后续泛化结论必须使用未用于选择的新冻结 TEST。
- 所有新增推理都必须先生成固定 plan、容器、CephFS 日志、心跳、终态标记和可恢复队列；CPU 指标实现与来源核查可与 NPU 队列异步执行。

## 第一批矩阵

| ID | 任务与固定版本 | 首要对象 | 原生指标/分母 | 统一补充指标 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| P1 | Kev hard-v1，clean mask | Kev 0.8B/4B/9B | question-weighted accuracy；上游 Brier/ECE10/NLL（各自发布分母） | one-hot Brier、top-confidence ECE10、NLL；逐题 decision-level paired 仅在保存 item outputs 后计算 | 已有参考结果；复核版本/mask/来源后可纳入 |
| P2 | Kev documents-v1，clean mask | Kev 0.8B/4B/9B | accuracy；4B/9B 上游校准可比性未建立，不能补 Brier/ECE/NLL | 仅在 logit/probability 字段完整时计算；否则只报 accuracy | 已有参考结果；校准口径受限 |
| P3 | Kev devtools-v1，release mask（full mask 单列诊断） | Kev 0.8B/4B/9B | release accuracy、Brier/ECE10；full mask 1,073 与 release 1,071 不混合 | 统一指标按 mask 分开 | 已有参考结果；full/release 分列 |
| P4 | Typed Decisions common test，400 states/2,000 questions | Kev 0.8B/4B/9B、Nimble-9B、Open-Jev-2B/9B | common scorer accuracy/KL/Brier/ECE10；不声称复现各模型原生 TEST | argmax accuracy、KL(q‖p)、summed Brier、ECE10；按 question type 分层 | 已有共同测试结果；不是原生测试替代 |
| P5 | BEV Decision Mix：default、hard_50k、numeric_temporal、skills、counterfactual_15k | 先参考模型，后训练候选 | 以发布卡定义为准；反事实保留成对分母 | clean accuracy、paired counterfactual flip/consistency；numeric/temporal 分层 | 候选；split 与字段需核查后运行 |
| P6 | Open-Jev v1.1，发布 test 与 OOD 分开 | Open-Jev-2B/9B、Kev 0.8B/4B/9B | hard accuracy、expected accuracy、NLL、Brier、expected Brier、ECE15 | 同一 mask 的 decision-level paired；test/OOD 不合并 | 候选；版本投影和来源族需核查 |
| P7 | DecisionPivot core；13 core families 与 35 reference tasks 分开 | 当前可运行的参考模型 | 使用其 core scorer 的 family/任务分母 | 仅在 gold、候选集和概率字段一致时补 accuracy/Brier/ECE | 候选诊断；不把 reference tasks 当 35 个独立数据集 |
| P8 | DecisionRobust text：clean 与 attacked 成对子集 | 当前可运行的参考模型 | clean accuracy、attacked accuracy，按原生 collection 分母 | paired flip rate、robust retention、按攻击类型分层 | 候选诊断；不接图像子集，不称生产安全 |

## 结果状态编码

每格只允许以下状态：

- `reported_reference`：已有固定参考结果，读数和来源已绑定；
- `ready_for_inference`：版本、来源、指标和运行 plan 已核对，可排队；
- `needs_split_or_source_review`：数据卡存在，但 train/dev/test、来源重叠或发布投影仍未固定；
- `unsupported`：模型或接口不支持该任务；
- `not_comparable`：存在数值，但统计方法、分母或字段不足以直接对齐；
- `blocked`：有明确工程/数值准入原因，保留原因，不补零。

## 训练计划的前置条件

新增范围的参考测试指标先运行、审查并汇报，然后讨论并冻结下一代训练方案；来源/指标核查本身不能代替参考测试结果。训练候选暂定为 Typed Decisions、BEV 与 Open-Jev v1.1 的合格 train 部分；混合比例、去重规则、DEV 和未见来源 TEST 在结果汇报后另行登记。现有 K1/K0 训练、DEV 和最终 TEST 门槛不追溯修改。

本登记不授权任何新增 NPU 运行；它提供新增运行合同的准备清单。实际运行前还需要每格的 plan、来源哈希、资源归属、恢复命令和独立 CPU/执行审查。
