# 数据集覆盖扩展 v9：补齐本地已镜像的公共任务面

**日期：** 2026-11-02  
**触发：** 用户复查后指出 v8 的数据集选择仍然偏少。  
**性质：** 覆盖登记、去重规则和执行计划；不改写 D1 历史读数，不新增 Qwen3.5 指标，不自动授权 TEST 推理。

## 1. 复查结论

这个反馈仍然成立。v8 已经按能力轴登记了普通路由、概率语义、拒答、鲁棒性、排序、多语言、闭环和多模态，但它仍然把若干已经在 CephFS 本地镜像、具有公开评测材料的来源压缩成了抽象任务族。这样会造成两个问题：

1. 我们可以说“覆盖了某个能力轴”，却不能指出同一能力轴下有哪些独立来源、原生测试集和参考指标；
2. 训练后的 Qwen3.5 结果仍可能只在 Kev/Typed/Open-Jev 的窄域上显示收益，无法区分域内收益、跨来源迁移、普通路由能力和风险边界。

因此 v9 不再只增加目录名称，而是把本地可追溯的来源、原生面板和指标口径显式列入登记。

## 2. 数量口径

数量按“独立来源/版本/输入语义/原生 TEST 面板”统计，不能把模型×数据集单元、temperature、mask、论文结果镜像或同一数据的改写重复计数。

| 层级 | 当前事实 | 允许写入结果表 |
| --- | ---: | --- |
| D1 冻结参考矩阵 | 38 个模型×数据集单元；36 有结果，2 个 Open-Jev×JEVal 为 `blocked/null` | 可以；历史数值、公式、温度和分母保持不变 |
| 本地顶层数据目录 | 24 个 | 不可以直接当作独立数据集 |
| v8 规划范围 | 约 35–45 个来源/任务族、100+ 原生面板 | 仅规划，不是完成实验 |
| v9 新增明确登记 | 10 个本地公共来源族，约 50 个原生任务/协议面板（含待去重项） | 仍为 `needs_review`，不能直接写入 Qwen3.5 结果 |
| v9 规划上限 | 约 45–55 个来源/任务族、150+ 原生面板 | 只有逐面板合同通过后才可逐项进入结果表 |

“150+”是覆盖审计完成前的上限，不能作为已下载、已运行或已完成实验数量。JevBench 的 231 是公开 item 数，不是 231 个独立数据集；Applied ML 的 37 个报告也必须按来源和 item lineage 去重。

## 3. v9 新增的具体来源和面板

### P0：首批共同文本矩阵

这些来源可以统一到文本 input、typed candidate set、single-pass readout 和 CPU scorer，优先完成合同；合同通过后按 FIFO 进入推理队列。

| 来源 | 计划登记的原生面板 | 原生指标和用途 | 关键去重/准入问题 |
| --- | --- | --- | --- |
| AppliedMachineLearning-Lab Jev benchmarking | 37 个公开任务报告；choice、noul/multilabel、ordinal/score、moderation、grounding、OOD | accuracy、macro/micro-F1、AUROC/AUPRC、Spearman/Pearson/Kendall、MAE、Brier、ECE、coverage | 部分报告不是官方 test split；每项记录 `split_role`，不能把论文数字当 Qwen 结果 |
| JevBench v1.6.1 public | public-231 及 easy/standard/hard/judge、calibration、cost/latency 面板 | native accuracy、chance-corrected score、harmonic/full score、校准和成本 | public rows 才可复现；private aggregate 只保留文献参考；与 Nimble/Applied ML 逐 item 去重 |
| Intern-Decision | accuracy-v1 的 7 个 suite、known-distribution calibration pilot | accuracy、hard Brier/ECE、expected Brier/ECE、成本/延迟 | 与 JevBench、Typed Decision、ToolACE、AG News、WildJailBreak 的来源 lineage 分开 |
| Jevals 0.1.0 | Banking77、PubMedQA、HelpSteer2 三个 primitive 面板 | choice accuracy、noul accuracy/Brier、ordinal/score correlation/MAE、ECE | 三种 target 和分母绝不合并；检查公开 split 与许可证 |
| Canonical/legacy DecisionBench | canonical 43 task IDs/27 families/28 domains；akhilaaa3 medium/hard | state-macro、question-weighted、difficulty/family macro、校准 | canonical、legacy、medium/hard 是不同版本；先查同源 item，禁止按仓库数计数 |
| Decision Model Benchmark | Banking77、CLINC150/OOS、NLU++ complete-message | complete-message accuracy、micro/macro-F1、AUROC/AUPRC、latency、cost | Banking77/CLINC150 与已有来源重叠；NLU++ 的 message 与 binary decision 分母分开 |
| TDM prevalence-shift | CLINC150、HWU64、Financial PhraseBank、HateXplain、TREC-6 的 no-shift/shifted 面板 | prior-shift 曲线、校准、paired primary tests、coverage-risk | 35 个预注册测试；shifted 与 no-shift 分表，检查与 transfer-v4 重叠 |
| Jev OOD calibration | 3,721 public known/unknown item；900 synthetic support-ticket item | accuracy、NLL、ECE、noise-floor ECE、refit-T 诊断 | public in-domain 与 policy-defined synthetic unknowable 分表，不宣称无偏泛化 |
| BEV Decision | counterfactual_15k、numeric_temporal、hard_50k、skills/default | paired flip/stability、numeric/temporal accuracy、hard decision accuracy | 保留 pair key、rule family holdout；子集和 all 不重复计数 |
| LocalLLaMA typed decisions | invoice、security、customer service、agent trace observability | typed state/question accuracy、升级/审计字段、unknown/fallback | 核实 split、candidate type、公开 TEST 和与 Track T 的暴露关系 |

这十类合计是“合同登记量”，不是十个已经可运行的队列任务；当前仍应全部保持 `needs_review`，直到来源 hash、split、输入 adapter、native scorer、分母、许可证、lineage 和 TEST 暴露字段闭合。

### P1：专项能力和风险边界

P1 不与静态 choice 总分合并，但必须补进覆盖矩阵，否则无法验证直接驱动是否只学会了候选格式。

- `nibzard/decision-model-benchmark` 的操作/延迟扩展与 `yodablocks/jev-orderby-bench`：排序、tie、inversion、complete-message 和成本；
- `samanjoy2/system-one-coherence`：重复问题、层级重建、选项顺序和 coherence；
- `FLock-io/this-that-model`：空间、组合规则、模拟器真值和 OOD 校准；
- `DecisionRobust`、`awesome-jev-robustness`、`DecisionPivot`、`JevAdvBench`：clean/attack、paired flip、stable-correct/stable-wrong、接口泄漏；
- `raxITLabs/decision-models-as-guardrails`、`SabaPivot/jev-safety-bench`、PFR/selective refusal：拒答正确性、coverage-risk、AURC、升级成本；
- `apolinario/decision-index`：公开 edition 的 routing、knowledge、retrieval、tool/language 子面板，保留 chance correction、coverage adjustment 和 edition；
- Korean JEV、Eikos、Respan Behavior、Belebele、AfriXNLI、SIB-200：逐语言、逐来源和 clean/perturbed 统计，不制作跨语言总分。

### P2：独立模态、闭环和业务缺口

- UniJev、OneJev、Imajev、DecisionRobust image：另建 image/video matrix，绑定模态、资产 hash、source-group split 和原生指标；
- WebJev、AgentDecisionBench、DecisionGym、JevAgentHarness：报告 success、constraint violation、steps、latency、cost 和 terminal reward；没有公开可复现 TEST 的只做来源登记；
- 自建中文业务规则：数字/日期/区间/等级、证据 support/conflict/missing、unknown/fallback、升级、审计 receipt、规则版本变化和每正确结果成本；必须固定 train/dev/test、rule-family holdout、等价 pair 和 discrimination counterpart。

## 4. 当前进度和事实边界

- D1 参考模型测试集统计已冻结，原生公式、温度、hard/soft、valid/full 分母继续分开报告。
- v8 及之前的新增候选均未产生新的 Qwen3.5 指标；当前新增面板 `ready_for_inference=0`。
- v9 只补齐了本地来源登记和执行顺序，没有读取候选 TEST，不改变正在运行的 formal K1 v15，也不解锁 TEST。
- Applied ML 的 37 个结果、JevBench 的公开汇总、Intern-Decision 和其他仓库的 README 数字都是参考文献/来源证据，不能直接填入我们的 Qwen3.5 结果表。
- NPU 训练继续由 detached supervisor 运行；CPU 侧可异步完成 manifest、lineage、scorer 和文献指标登记。数据集扩展不应打断 v15。

## 5. 下一阶段计划

### M0：先完成来源合同，不占用 NPU

1. 为十个 P0 来源写出逐面板 manifest：source/version/hash、split、item count、input fields、candidate set、level type、pair key、target type、native formula、denominator、license 和 TEST exposure。
2. 建立 item-level lineage 表，至少与 Kev、Nimble、Typed、JEVal、Open-Jev、Banking77、CLINC150、MASSIVE、PAWS、Civil Comments、TREC 交叉核对。
3. 标记每个面板为 `completed_d1`、`ready_for_inference`、`needs_review`、`blocked` 或 `reference_only`；未闭合项不得补零或入队。

### M1：按能力轴形成第一批 FIFO

合同通过的面板按以下顺序入队：

1. Jevals 三 primitive 和 JevBench public 的 source-disjoint 小批；
2. Applied ML 的 BoolQ、CLINC/OOS、ANLI、HellaSwag、ARC、CommonsenseQA、STS-B、SST-5、SummEval、HelpSteer2、ToxicChat 等公开且 split 闭合面板；
3. DMB、TDM prevalence-shift、OOD calibration；
4. BEV counterfactual/numeric-temporal 与 LocalLLaMA 四业务域。

每个队列任务都先登记预注册指标，再由 NPU 按队列持续执行；CPU scorer、去重审计和报告刷新异步进行。watchdog 维持约十分钟轮巡，编排者只读取 digest。

### M2：完成 P1/P2 和业务缺口

P0 文本矩阵取得 direct-readout 基线后，继续加入排序、coherence、鲁棒性、安全、多语言，再单独启动多模态和闭环。内部业务缺口在公共面板审计完成后制作，真实业务仍不接入。

### M3：再讨论训练方案

先比较同骨干 K0 direct-readout 与 K1 LoRA/SFT 在域内、source-disjoint 迁移、鲁棒性、校准和成本上的分任务结果；随后才冻结 proper-scoring、校准、distillation、option-restricted loss 和 RL 的单因素计划。TEST 仍只在 DEV 选择、独立 scorer 和 Astra acceptance 后读取一次。

## 6. 用户无需重新决定的事项

本轮默认执行“扩大候选登记、逐面板准入、按 FIFO 自动推进”，不要求再从十个 P0 来源中手工删减。若后续需要控制首批运行量，只缩短 FIFO，不删除覆盖登记，也不改写 D1 历史结果。

## 7. 验收条件

- 十个 P0 来源的面板都有可追溯 manifest 和 lineage 状态；
- 任何进入 FIFO 的面板都具备公开、可复现的 TEST、原生 scorer、明确分母和输入 adapter；
- 原生 accuracy/F1/AUPRC/correlation/MAE/Brier/ECE/NLL/coverage-risk/cost 指标分别报告；
- source-disjoint、domain transfer、robustness、multilingual、multimodal、closed-loop 和业务缺口分层，不汇总成一个总分；
- 每个 milestone 增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 与 `wiki/CURRENT-CONCLUSIONS.md`，历史过程按三天归档；
- v15 训练不被扩展计划打断，新增数据集不会绕过资源 claim、detached launcher、watchdog 和 TEST lock。

## 8. 证据入口

- `.local/reports/candidate-inventory-20261102.md`
- `.local/reports/dataset-gap-inventory-20261102.md`
- `.local/reports/independent-candidates-beyond-v5-20261102.md`
- `.local/reports/capability-matrix-gap-20261102.md`
- `proposal/22-dataset-coverage-expansion-v8-2026-11-01.md`
- `experiments/REFERENCE-BASELINE-LATEST.md`
