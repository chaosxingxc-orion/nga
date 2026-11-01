# 数据集覆盖扩展 v8：补齐能力轴后的任务选择

**日期：** 2026-11-01  
**触发：** 用户指出当前数据集仍然偏少。  
**性质：** 范围登记和执行计划，不新增 TEST 读数，不改变已冻结 D1 指标。

## 1. 判断

这个反馈成立。v7 已把候选范围从最初的六个任务族扩大到约 25–30 个来源/任务族、70+ 个原生面板，但仍有三个问题：

1. 大多数面板仍是 Jev 专用的静态 choice/score/noul，普通路由、概率真值、选择性拒答和排序没有足够的独立对照；
2. 对抗扰动、选项通道攻击、答案保持改写和概率接口一致性被分散在论文说明中，没有成为可执行的单独任务族；
3. Agent 闭环、视觉/视频、心理测量和业务成本被列为远期候选，尚未在选择矩阵中有明确位置。

因此，本版把**规划范围**提高到约 **35–45 个独立来源/任务族、100+ 个原生面板**。这是完成来源、版本、item lineage、TEST 暴露和许可证审计前的上限，不是已经下载、准入或完成推理的数量。目录数、论文数、结果镜像和同源改写都不能直接计数。

## 2. 四层任务盘

### A：共同文本 NxM（第一优先级）

这些任务可以统一为文本 input、typed candidate set 和单次 readout，适合在参考模型锁定后进入 Qwen3.5 的 N×M 直接驱动矩阵。

| 能力轴 | 来源/面板 | 原生指标 | 当前位置 |
|---|---|---|---|
| Jev choice/score/noul | Kev、JEVal、Open-Jev、Nimble、JevBench、Applied ML、Intern-Decision、DecisionBench、BEV、LocalLLaMA typed | accuracy、state/question accuracy、score MAE、ECE、Brier、NLL、selective metrics | D1 或 P0；按来源和公式分表 |
| 普通路由和完整消息 | Decision Model Benchmark；Jevals Banking77、PubMedQA、HelpSteer2；CLINC150/OOS、NLU++、MASSIVE、AGNews、topic/sentiment/toxicity | complete-message accuracy、micro/macro-F1、AUROC/AUPRC、成本/延迟 | 新增 P0 对照；不并入 typed accuracy |
| 数值、时间、等级和 ordinal | BEV numeric-temporal；TypedBench ordinal suites；Praveenrajus 的 STS-B、SummEval、ChaosNLI；NumericJev 路线 | MAE、Spearman/Pearson/Kendall、proper score、区间命中 | 新增 P0；hard label 与连续/软目标分开 |
| 概率真值和接口一致性 | Sys1Cal-v1；Probability Contracts；TDM prevalence-shift；Jev OOD calibration | TV distance、Brier、ECE、NLL、coverage-risk、AURC、known/unknown 分层 | 新增 P0；不能用普通 accuracy 替代 |
| 选择性预测、fallback、拒答 | PFR；TypedBench selective prediction；guardrail/safety；JEVal refusal 子集 | coverage-risk、AURC、拒答正确性、升级成本 | 新增 P0/P1；显式 abstain 是结构化输出 |
| 等价改写和语义一致性 | BEV counterfactual；TypedBench wording；System-One coherence；DecisionPivot contrast | paired flip、stable-correct/stable-wrong、coherence、contrast accuracy | 新增 P0/P1；必须有 pair key |
| 顺序、候选表示和排序 | ORDER BY；DecisionPivot ranking；option-order panels；This-That complex/spatial | inversion、tie、reverse-order flip、rank correlation、空间关系准确率 | P1，单独统计 |
| 对抗与接口泄漏 | JevAdvBench；option-channel attack；TUPLE-Bench；DecisionRobust text | attack success、fail-open/fail-closed、paired flip、接口泄漏率 | 新增 P1；clean 与 attack 分表 |
| 多语言和跨域 | Korean JEV、Eikos、Respan Behavior、Belebele、AfriXNLI、SIB-200 | 按语言/来源的 native accuracy、flip、校准 | P1；不能替代中文业务集 |
| 业务式规则和可审计字段 | 内部中文数字/日期/区间/版本、证据 support/conflict/missing、unknown/fallback、审计 receipt | paired decision、unknown precision/recall、evidence state、成本 | P2 自建；真实业务不接入 |

### B：闭环和 Agent 动作（独立矩阵）

System1-Arena（单步问题与 138 个闭环环境）、AgentDecisionBench、DecisionGym、WebJev 和工具选择/升级任务必须记录 success、constraint violation、steps、latency、cost、terminal reward。它们不是静态 readout accuracy 的附加行，也不与 A 层总分合并。只有取得可复现环境快照和 evaluator 后才可入队；没有公开 TEST 的只保留来源登记。

### C：视觉/视频和空间（独立矩阵）

UniJev/OneJev、Imajev、DecisionRobust image、vision Decision Index、This-That spatial 单独维护 image/video adapter、资产 hash、模态限制和 chance baseline。文本 Qwen3.5 结果不得填充这些格子；Imajev 的隐藏标签和发布门未关闭前保持 `blocked`。

### D：人类/业务边界（诊断和自建）

Psychometric audit、文化/偏差审计、在线 moderation、RLCDAlignBench 作为边界诊断，分别报告 construct validity、bias、fail-open、alignment failure 和人工基线。它们不能被包装成 Jev 泛化分数。内部集合必须有 train/dev/test、rule-family holdout、等价配对、discrimination counterpart、typed candidate set 和明确分母。

## 3. 计数和状态口径

| 层级 | 当前数量 | 是否可写入结果表 |
|---|---:|---|
| 冻结 D1 | 38 个模型×数据集单元，36 有结果、2 blocked/null | 可以；历史读数不变 |
| 本地 CephFS 目录 | 24 个顶层目录 | 不可以直接当独立数据集 |
| 已登记本地候选 | 约 16–17 个来源族、50+ 面板 | 不能；必须逐面板准入 |
| v8 规划上限 | 约 35–45 个来源/任务族、100+ 面板 | 不能；只是覆盖目标 |
| `ready_for_inference` | 当前为 0 | 只有这一状态可进 FIFO |

同一来源的版本、温度、mask、hard/soft target 和 valid/full 只是协议面板；只有输入语义、item identity、来源 hash 或能力轴真正独立时才计为新面板。结果镜像和论文数字保留为 reference-only。

## 4. 执行顺序

1. **CPU 合同审计（立即并行）：** 对 A 层新增的 Sys1Cal、Probability Contracts、TypedBench、PFR、JevAdvBench、option-channel、TUPLE 和普通路由面板建立 manifest、版本/hash、split、指标分母、pair key、许可证和 TEST 暴露记录。
2. **本地快照先行：** 先审计 CephFS 已存在的 BEV、typed-decisions、DecisionBench、DecisionPivot、Eikos、Korean、Respan、guardrail、DecisionRobust、spatial/complex 和 btzsc；没有通过合同的面板不读 TEST。
3. **首批 FIFO：** 仅把合同通过的 A 层文本面板按来源和能力轴入队；参考模型直接驱动、Qwen3.5 直接驱动和 CPU 指标复算异步运行。formal K1 NPU 训练不中断。
4. **B/C/D 分离：** 闭环、视觉/视频、人类/业务边界分别建立 adapter、环境/资产快照和指标 schema，不等待或污染文本 NxM 结果。
5. **训练路线：** 先完成扩展后的直接驱动基线，再比较 SFT/LoRA、proper-scoring、校准和 RL。TEST 仍只在 DEV 选择、Astra 审查和独立 scorer 完成后读取一次。

## 5. 当前不需要用户重新决策

用户已经指出范围偏小，本版按“扩大覆盖、保持准入门槛”执行。除非需要人为限制首批推理量，否则默认：**全部候选先做 CPU 审计，合同通过者按能力轴和 FIFO 自动进入**。如果后续资源或时间需要收缩，只缩短 FIFO，不删除覆盖登记，也不改写 D1 历史结果。

## 6. 验收条件

- v8 目录中每个来源/面板都有状态：`completed_d1`、`ready_for_inference`、`needs_review`、`blocked` 或 `reference_only`；
- `ready_for_inference` 面板均有来源 hash、公开 TEST 证据、输入 adapter、原生 scorer、分母和 lineage；
- 文本、闭环、视觉/视频、人类/业务四层不合并总分；
- 每个 milestone 增量刷新 `experiments/REFERENCE-BASELINE-LATEST.md` 和远程 Wiki，旧过程文件继续按三天归档；
- 新增范围不改变 D1 38 单元任何历史读数。

证据入口：`proposal/19-dataset-coverage-expansion-v7-status-2026-11-02.md`、`proposal/21-status-decisions-next-plan-2026-11-02-dataset-coverage-revision.md`、`.local/reports/dataset-gap-inventory-20261102.md`、`.local/reports/p0-common-text-metadata-audit-20261102.md`。
