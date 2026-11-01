# 当前任务状态、数据集覆盖修订、待决策项与下一阶段计划

**日期：** 2026-11-02  
**状态：** 执行中；本文件是本轮“数据集选少了”反馈后的增量权威说明。  
**范围：** 只更新任务范围、准入顺序和计划，不改写 D1 已冻结读数，不新增候选 TEST 指标。

## 1. 当前结论

你的判断成立：原来的数据集集合适合做 Jev 参考模型的第一轮对齐，但不足以支持“Jev 训练方案在业务目标下有明确收益”的完整判断。问题有两层：一是已有 D1 矩阵集中在少数 Jev 发布集；二是本地已经存在多种能力轴，却没有进入统一的准入清单。

当前事实边界如下：

- D1 参考基线仍为 **38 个模型×数据集单元**，其中 36 个有结果，2 个 Open-Jev×JEVal 单元为 `blocked/null`。这些数值、原生公式、温度、mask 和分母保持冻结，是当前参考模型测试集汇报的事实权威。
- 本地 CephFS 的 Jev 数据目录当前可见 **24 个顶层目录**。这个数量不能直接当作 24 个独立数据集：其中包含同一项目的版本、结果镜像、不同模态和同源子面板。按来源、输入语义和 item lineage 去重后，当前可执行清单应按来源族和原生面板统计。
- 扩展计划暂定为 **约 25–30 个来源/任务族、70+ 个原生面板**。这是审计完成前的规划上限，不是已完成实验数，也不是已经授权的推理数。
- P0 元数据审计已经覆盖六个新增公共来源族；当前全部为 `needs_review`，`ready_for_inference=0`。没有读取候选 TEST，没有新增 Qwen3.5 指标。
- formal K1 v15 的 Qwen3.5-0.8B seed2/seed3 训练仍在 host 175 的 chip2/chip3 上运行。最近可用 watchdog digest 为 2026-11-01 21:09 UTC：seed2 230/3116、seed3 190/3116，heartbeat 新鲜且无异常 flags。该快照不是训练结束结论；尚无 `EXIT`、`RELEASE`、`SUPERVISOR_DONE`，也没有 TEST 读取或 scientific acceptance。
- NPU 继续按约十分钟 watchdog 轮巡；CPU 侧同时做数据合同、lineage、指标复算和报告更新。不能为了扩大数据集而打断正式训练，也不能让未准入候选占用 NPU。

## 2. 本地数据覆盖盘点

下面按“可承载的能力”组织本地 24 个目录。目录是证据入口，不等于已经通过准入；每个独立面板仍需单独记录版本、split、输入、指标和 TEST 暴露。

### 2.1 冻结参考层

| 来源族 | 本地目录/面板 | 当前用途 | 状态 |
|---|---|---|---|
| Kev | `jaredpalmer__kev-suites` 的 decision/transfer/hard/documents/devtools 等冻结面板 | D1 参考模型原生 TEST | 已冻结，可报告 |
| JEVal | `carlosxiang__JEVal` | valid/full、分类/score/unsupported 等协议对齐 | 已登记；Open-Jev×JEVal 两单元仍 blocked/null |
| Open-Jev | `ZefanCai__Open-Jev`、`ZefanCai__Open-Jev-v1.1` | original release 与 OOD/合成未知面板 | D1 已冻结的行可报告；新增版本需重新审计 |

### 2.2 P0：文本、typed decision、路由和概率语义

这些面板最适合先进入 Qwen3.5 的 NxM 直接驱动矩阵，因为输入仍可统一为文本、候选集和 typed readout。

| 来源族 | 本地目录/面板 | 要覆盖的能力 | 主要去重或准入问题 |
|---|---|---|---|
| BEV Decision | `avbiswas__bev-decision`：`counterfactual_15k`、`numeric_temporal`、`hard_50k`、`skills` | 等价改写、discrimination、数字/时间规则、大规模 hard decision | 需冻结 pair key、生成版本、规则族 holdout，并检查与内部规则重叠 |
| LocalLLaMA typed decisions | `LocalLLaMA__typed-decisions`：invoice、security、customer_service、agent_trace_observability | 业务式 typed candidate、升级、审计/trace | 需核实许可证、split、公开 TEST 和 candidate-set 类型 |
| DecisionBench | `Hanno-Labs__decision-bench`、`akhilaaa3__decision-bench` | 多任务决策、领域迁移、medium/hard 难度 | canonical、legacy、akhilaaa3 必须分源；task ID 和 item lineage 不能合并 |
| Praveenrajus JevBench | `Praveenrajus__jev-bench` | Jev choice/noul/score 的额外任务配置 | 与 JevBench、Applied ML 报告可能同源；需逐 item 去重 |
| Applied ML Jev benchmarking | 论文/仓库登记的约 37 个原生面板 | choice、noul、安全、多语言、排序、校准、OOD | 论文面板和可复现 TEST 必须分开；没有公开 TEST 的只做文献参考 |
| JevBench public / Intern-Decision / Jevals | 公共版本登记；Jevals 含 Banking77、PubMedQA、HelpSteer2 | 路由、分类、noul、ordinal/score | 原生公式、分母、公开 TEST authority 和输入 adapter 待闭合 |
| TDM prevalence shift | 公开来源与 shift 面板 | 先验漂移、目标先验、校准稳定性 | no-shift/shifted 必须分表；不能当作普通 accuracy |
| OOD calibration | OpenBookQA、CommonsenseQA、HellaSwag 与 synthetic unknowable | known/unknown、拒答、ECE/NLL | in-domain 与 synthetic unknown 分开；需固定 refit-T 规则 |
| 常规分类边界集 | `btzsc__btzsc` 的 Banking77、MASSIVE、AGNews、topic、sentiment、toxicity 等 | 普通路由、意图、主题、情绪、毒性 | 只有证明 typed decision schema 后才能进入 Jev 主矩阵；否则作为边界诊断 |

### 2.3 P1：能力专项和风险边界

P1 用于检验直接驱动是否只是记住固定候选格式，必须保留 paired decision 或 discrimination counterpart。

| 来源族 | 本地目录/登记 | 能力轴 | 统计方式 |
|---|---|---|---|
| Eikos decisions | `caiovicentino1__eikos-decisions` | typed decision、行为/一致性 | state macro 与 question-weighted 分开 |
| Korean JEV | `DaehanKim__korean-jev-benchmark` | 跨语言 typed decision | 按语言、任务族和 native denominator 分开 |
| Behavior perturbation | `respanai__behavior-benchmark` | 指令扰动、行为稳定性 | clean/perturbed、paired flip、stable-correct/stable-wrong |
| DecisionPivot | `startlux-models__DecisionPivot` | pivot/structured choice | 先确认 test split 和 native metric，避免与 DecisionBench 重复 |
| DecisionRobust | `yflantmy__DecisionRobust` | clean/attack、鲁棒决策 | attack success、paired flip、有效样本数单列 |
| Safety/guardrail | `SabaPivot__jev-safety-bench`、`raxITLabs__decision-models-as-guardrails` | 安全、拒答、选择性预测、升级 | coverage-risk、AURC、拒答正确性、升级成本，不并入 accuracy |
| Spatial/complex decisions | `limberc__this-that-spatial-bench`、`limberc__this-that-complex-decisions` | 空间关系、复杂规则、顺序鲁棒性 | rendered modality、rule family、chance baseline、OOD 分开 |
| Order/coherence | ORDER BY、System-One coherence 登记 | 排序、tie/inversion、层级一致性、重复问题 | reverse-order paired flip、coherence rate、不能用总准确率替代 |

### 2.4 P2：独立模态、闭环和业务缺口

这些任务不能简单塞进文本 NxM；需要单独 adapter、资源合同和结果 schema。

| 来源/任务族 | 本地目录/登记 | 能力轴 | 当前限制 |
|---|---|---|---|
| OneJev/UniJev | `OmniJev__OneJev-Data` | 图像/视频 typed decision | 当前没有可复现公开 TEST 的面板不进入推理 |
| Imajev | `mohit67890__imajev-bench` | 图像输入决策 | hidden labels/release gate 未闭合，保持 blocked |
| WebJev | `Lexmount__WebJev` | 证据、检索、网页决策 | 必须冻结 retrieval snapshot、证据字段和 evaluator |
| Laya/结果镜像 | `Luni__laya-jev-benchmark` | 跨模型协议和结果对照 | 先判断是否独立 TEST；结果镜像不能计作新数据集 |
| Decision Index metadata | `bespokelabs__bespoke-nimble-9b-v3-decision-index` | 指标/运行索引 | 只有找到独立 item 才能计入数据集 |
| 内部中文规则 | 新建 | 中文数字、日期、区间、等级、版本变化 | 需 train/dev/test、rule-family holdout、等价配对、discrimination |
| 内部证据与审计 | 新建 | support/conflict/missing、receipt、审计状态 | 公共集不能替代，需要冻结状态机和回执 schema |
| 内部 unknown/升级/成本 | 新建 | fallback、升级代价、每正确结果成本、闭环 | 先做直接驱动基线，再决定训练或 RL |

## 3. 为什么不能只把数据集数量加大

扩展的有效单位是“独立来源族 × 原生面板”，不是目录数或论文数。一个来源下的 `numeric_temporal`、`counterfactual`、`hard` 可以是三个面板；同一数据的 temperature、mask、hard/soft target 只是协议变体，不能计成三个独立泛化来源。反过来，canonical/legacy DecisionBench、Eikos、Korean JEV 和 DecisionRobust 即使主题相近，也要先用 item-level lineage 判断是否独立。

每个面板都必须满足：source/version/hash、许可证、split/item count、输入字段、candidate set、level type、equivalence class、discrimination counterpart、原生公式、target type、温度、valid/full 分母、重叠 lineage、TEST 是否公开，以及 adapter 的失败/unknown 语义。未满足时保持 `needs_review` 或 `blocked`，不读候选 TEST，不补零，不进入 NPU FIFO。

## 4. 当前任务进度

### 已完成

1. D1 参考模型测试集指标已冻结并持续维护，原生计算方法分列。
2. 四维结果组织方式已确定：收益来源、任务/指标、业务要求承载关系、我们自己的 NxM 与训练/优化路线。
3. 用户反馈后的覆盖计划已从少数 Jev 集合扩展到 P0/P1/P2 三层；本地目录盘点证明扩展不是凭空增加目录。
4. P0 元数据审计完成六个来源族的文档/manifest 检查；全部仍 `needs_review`，无候选 TEST 读取。
5. formal K1 v15 双 seed 已经通过 Astra `PLAN_VERIFIED`，在 chip2/chip3 detached 运行；CPU 后处理准备与 NPU 训练异步进行。
6. watchdog 已固定为约十分钟轮巡；编排者只读 digest，不读原始日志。

### 尚未完成

1. P0 尚未形成任何 `ready_for_inference` 面板；因此尚无新增 Qwen3.5 P0 指标。
2. formal K1 尚未产生训练终端证据和 DEV 选择结果；不能宣称训练收益。
3. 业务缺口集尚未冻结；真实业务仍不接入。
4. P1/P2 的指标合同、lineage 和 adapter 尚未完成；多模态、Web/闭环不能和文本结果混合。

## 5. 需要你决策的内容

这些选择只影响排程，不改变 D1 数值和准入原则。

1. **P0 的第一批宽度。** 建议先对全部 P0 来源做 CPU 合同审计，但只把合同通过的面板按 FIFO 入队；不建议人为缩到两个数据集。若你希望控制首批推理量，可指定先跑 BEV Decision、LocalLLaMA typed decisions、DecisionBench、JevBench 四族。
2. **内部缺口的前两类。** 建议先做“中文数字/日期/区间/等级规则”和“unknown/fallback/证据状态”，它们既贴近业务目标，又能在不接真实业务的情况下建立可检验的直接驱动收益。
3. **P2 启动时机。** 建议 P0 文本直接驱动和 P1 风险专项完成后再启动多模态与 Web/闭环；P2 需要独立资源和 scorer，提前启动会稀释文本 NxM 的验收轴。

## 6. 下一阶段计划

### M0：覆盖合同和去重

- 为 P0 每个来源族建立 manifest、版本/hash、split、许可证和面板表。
- 建立 item-level lineage，明确与 Kev、Nimble、Typed、JEVal、Open-Jev、Banking77、MASSIVE、PAWS、Civil Comments 的重叠。
- 为每个面板生成 `ready_for_inference`、`needs_review` 或 `blocked` 收据。
- 对 D1 38 单元做只读回归，确保本轮扩展不改变历史数值。

### M1：P0 直接驱动 NxM

- 合同通过的文本面板按 FIFO 持续推理，NPU 保持已有准入队列，不因 CPU 报告等待而空闲。
- CPU 异步复算论文原生指标和同 TEST 的复算指标，分开 native/raw T=1、hard/soft、valid/full、clean/attack、shifted/unknown。
- Qwen3.5 先完成直接驱动 baseline，再冻结 NxM 的任务轴和选择规则。

### M2：训练与工程基线

- formal K1 完成后只读 train/dev/calibration 与 selection half，生成双 seed DEV、paired decision、ECE/Brier/NLL、吞吐、显存和恢复证据。
- 通过 Astra 独立对抗审查后，创建独立 final TEST ticket；TEST 只读一次并与参考原生公式对齐。
- 在同一任务轴比较参数不动的驱动变化、结构变化、任务/训练设计和学习方法设计。

### M3：业务缺口与优化

- 冻结内部中文规则、证据/unknown/升级任务，先报告基础模型直接驱动表现。
- 在 SFT/LoRA、proper-scoring、校准基线稳定后，再设计 RL；RL 必须有可审计 reward、成本约束和可复现 model-free baseline。

## 7. 这轮不应作出的结论

- 不能把 24 个本地目录、25–30 个规划来源族或 70+ 面板写成已完成实验。
- 不能把候选面板的缺失指标写成 0，也不能把论文结果直接当作 Qwen3.5 结果。
- 不能在 formal K1 完成前宣称训练收益，不能在模型选择和 Astra 审查前读取最终 TEST。
- 不能把不同 native formula、温度、分母、模态或来源 lineage 合并成一个总分。

## 证据入口

- [`experiments/REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md)
- [`proposal/19-dataset-coverage-expansion-v7-status-2026-11-02.md`](19-dataset-coverage-expansion-v7-status-2026-11-02.md)
- [`.local/reports/dataset-gap-inventory-20261102.md`](../.local/reports/dataset-gap-inventory-20261102.md)
- [`.local/reports/p0-common-text-metadata-audit-20261102.md`](../.local/reports/p0-common-text-metadata-audit-20261102.md)
- [`wiki/CURRENT-CONCLUSIONS.md`](../wiki/CURRENT-CONCLUSIONS.md)
