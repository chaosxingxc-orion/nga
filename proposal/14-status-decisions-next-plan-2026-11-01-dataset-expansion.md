# 当前任务状态、决策项与下一阶段计划：数据集覆盖扩展

**日期：** 2026-11-01
**状态：** 当前任务仍在执行；本文件是数据集覆盖反馈后的最新阶段说明。运行中的 NPU 任务不因本次规划更新而中断。

## 当前状态

当前参考基线已完成既定矩阵的汇报：38 个模型×任务单元中 36 个有结果，2 个 Open-Jev×JEVal 单元保持 `blocked/null`。这些结果按测试集、原生统计方法、温度、mask、hard/soft target 和分母分别保留，不能用一个总平均替代。

正式 Qwen3.5 训练/推理链仍按原合同运行，CPU 审查、来源核验、报告整理与 NPU 队列异步进行。正式 seed2 DEV 的读出完成数不能替代容器终态、`ENGINEERING_EVAL_EXIT`、`RELEASE` 和 supervisor 标记；在真实终态齐备前，不启动 CPU report watcher，也不宣称正式 TEST 收益。K2 外部科学准入仍被既有链证据缺口阻断。

用户指出数据集选少了，这一判断成立。当前新增公开评估合同只有 6 个任务族、14 个单元：Kev、Typed Decisions、BEV、Open-Jev v1.1、DecisionPivot 和 DecisionRobust 文本。库存虽然有 24 个目录，但目录数包含版本投影、结果包、同源候选和不同模态，不能直接当作 24 个独立数据集。

本轮只完成覆盖扩展规划，没有读取新增候选 TEST 样本，没有启动新增推理或训练，也没有修改既有冻结指标、split、阈值、训练门槛或历史读数。

## 需要用户决策的内容

当前没有阻塞执行的必答项，默认按以下顺序推进：

1. 第一批先扩到 8 个直接测试任务族：现有 6 个，加上复杂确定性决策和空间决策。
2. 第二批加入安全/guardrail、多语言/行为、网页/动作，用于边界和迁移诊断。
3. 第三批把图像/视频 typed decision 单独建立多模态矩阵，不混入当前文本 NxM 总分。

只有你希望改变默认顺序时，才需要决策：是否把安全、多语言或网页任务提前到第一批；是否把视觉/视频纳入当前文本路线。默认保持真实业务接入和 RL 后置，先完成公开测试对齐和可复现训练基座。

## 下一阶段计划

### 阶段 A：扩展任务合同

CPU 侧为第一批 8 个任务族逐项固定版本、split、mask、样本数、来源族、原生指标、统一指标、成对关系和 TEST 暴露状态。复杂/空间任务必须登记规则族或 simulator family holdout，并提供判别对照。未达到 `ready_for_inference` 的单元保持 `needs_review`，不进入 NPU 队列。

### 阶段 B：异步直接驱动评估

通过独立 CPU/执行审查后，将合格单元写入 NPU FIFO；每个 job 保留固定 plan、CephFS 日志、heartbeat、终态 marker 和 relaunch 命令。NPU 按队列持续执行，CPU 同步实现 scorer、核对来源和汇总结果；常规状态每约 10 分钟只读取 watchdog digest，不读取原始日志。

### 阶段 C：测试指标发布

先按每个任务的原生方法报告测试集结果，再在字段和语义足够时补充统一 decision-level 指标。不同温度、mask、分母、hard/soft target、paired 与 marginal 统计分列；不支持或不可比的格子明确写 `unsupported` 或 `not_comparable`。

### 阶段 D：训练计划讨论

第一批公开测试指标完成并独立复核后，再冻结下一轮 Typed Decisions、BEV、Open-Jev v1.1 的训练混合、去重规则、DEV 选择和未见来源 TEST。先比较同骨干 K0、窄域 K1 和广覆盖 K1；域内、未见来源迁移和鲁棒性分开汇报。

### 阶段 E：业务缺口与 RL

公开任务只能承载部分要求。后续冻结业务作者规则、等价改写、unknown/fallback、证据审计、中文数值/日期和成本/升级任务，并先建立直接驱动和开源学习方法基线。RL 必须在这些基线和可审计奖励对象具备后启动；奖励提高不直接等同业务收益。

## 交付入口

- 覆盖扩展方案：[proposal/13-dataset-coverage-expansion-v2-2026-11-01.md](13-dataset-coverage-expansion-v2-2026-11-01.md)
- 机器可读决策：[dataset-coverage-expansion-decision-20261101.json](../.local/reports/dataset-coverage-expansion-decision-20261101.json)
- 第一批公开评估契约：[proposal/12-public-eval-preregistration-2026-11-01.md](12-public-eval-preregistration-2026-11-01.md)
- 数值权威入口：[REFERENCE-BASELINE-LATEST.md](../experiments/REFERENCE-BASELINE-LATEST.md)

本文件是当前规划和状态说明，不产生新模型指标。每个 meaningful milestone 完成后，刷新最新报告和 Wiki 当前结论页，旧过程文件按三天周期归档。

### 本轮审计后的实际准入状态

第一轮元数据审计已落盘，但没有一个新增单元被授权直接推理。扩展合同目前为 16 个单元，其中 12 个 `needs_review`、4 个 `blocked`。复杂/空间任务的公开文件、guardrail 的 test 配置、Korean/Eikos 的候选 heldout 仍需逐单元固定来源和统计；WebJev 与 OneJev 缺少原生 TEST；Imajev 的隐藏标签和未通过发布门禁使其不能作为本地测试结果来源。该状态不影响现有 NPU 任务继续执行，也不改变已有参考基线。

### 工程队列接续状态

chip3 的 `instruct_k0_chip3_20261101_v1` 已有 `EXIT=0`、`RELEASE` 和 `SUPERVISOR_DONE`，但 precheck 终态的 review 仍为 `PENDING_ROOT_REVIEW`，科学准入仍为 false。因此它只能作为待审查的工程 DEV successor，不能直接发布结果或激活下游训练。watchdog 最近快照还显示没有合格排队 successor、约三个 chip 未使用；历史 stalled 条目不计入有效任务。下一步先完成来源/前置审查，再决定是否进入 FIFO，避免为保持满载而绕过准入。
