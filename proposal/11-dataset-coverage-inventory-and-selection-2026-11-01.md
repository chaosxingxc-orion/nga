# 数据集覆盖库存与接入选择矩阵

2026-11-01。本文把本地发现的 24 个数据目录整理成任务覆盖矩阵，回应“数据集选少了”的问题。目录存在、`.complete` 标记或 README 描述都不等于科学准入；本轮只做元数据盘点，没有读取候选 TEST 样本，没有新增推理，也没有改变已冻结的 TEST 协议。

## 当前缺口

我们当前训练收益的有效覆盖仍主要是 `decision-v7` 与 `transfer-v4`，它们属于同一 typed-decision 主路线。已有参考基线虽然有 38 个模型×任务单元，但不是 38 个独立数据集，而且很多单元是模型在自己的原生测试上的结果。缺少的是三条轴的交叉：

1. **任务轴**：文档、开发工具、数值/时间、空间、多语言、网页动作、安全与鲁棒性等输入分布没有进入同一选择矩阵。
2. **来源轴**：训练、开发和最终测试还没有按来源族、场景族和规则族完成去重与隔离。
3. **可比模型轴**：同一组参考模型在同一任务上的直接驱动结果不足，原生指标和本项目统一指标需要并列维护。

## 24 个本地目录的初步归类

| 目录 | 任务/模态线索 | 当前用途建议 | 处理状态 |
| --- | --- | --- | --- |
| `jaredpalmer/kev-suites` | hard、documents、devtools typed decisions | 外部测试扩展；优先 | 已有参考结果；核对版本、mask 和来源重叠 |
| `LocalLLaMA/typed-decisions` | 工作流 typed decisions，4 个领域 | 下一代训练、DEV、共同测试 | 候选；先核对原生 train/test 与场景边界 |
| `avbiswas/bev-decision` | default、hard、numeric-temporal、skills、counterfactual | 下一代训练、DEV 与迁移测试 | 候选；成对反事实不得拆散 |
| `ZefanCai/Open-Jev-v1.1` | typed、多领域、中英文，含 OOD | 下一代训练与外部测试 | 候选；按版本和来源族隔离 |
| `startlux-models/DecisionPivot` | 规则组合、数值/时间、状态更新 | 外部诊断测试 | 只纳入 core；reference 任务单列、去重后再接入 |
| `yflantmy/DecisionRobust` | 文本扰动、注入、鲁棒性 | 外部鲁棒性测试 | 优先文本子集；clean/attacked 成对统计 |
| `limberc/this-that-complex-decisions` | 复杂规则、缺信息、多步状态 | 后续确定性复杂测试 | 延后；按 family 和未知类判别对照 |
| `limberc/this-that-spatial-bench` | 空间状态与路径规则 | 后续确定性复杂测试 | 延后；按 family/状态分层 |
| `raxITLabs/decision-models-as-guardrails` | 安全、拒答、提示攻击 | 后续边界/安全测试 | 延后；不表述为生产安全结论 |
| `SabaPivot/jev-safety-bench` | 安全分类与 choice robustness | 后续边界/安全测试 | 延后；按原始、反转、序列化版本统计 |
| `DaehanKim/korean-jev-benchmark` | 韩文多源 finite-choice | 多语言迁移测试 | 延后；只作为韩文补充，不替代中文任务 |
| `Lexmount/WebJev` | 网页元素定位、动作预测 | 后续网页任务 | 延后；按网站/任务族重划分 |
| `OmniJev/OneJev-Data` | text/image/video 混合来源 | 来源调查与后续多模态路线 | 暂不并入当前文本训练 |
| `mohit67890/imajev-bench` | text、visual、joint typed decisions | 后续多模态测试 | 延后；preview 标记需保留 |
| `Praveenrajus/jev-bench` | banking、意图路由等多任务 choice | 外部任务补充 | 候选；先核对其来源是否与现有 transfer 重叠 |
| `Hanno-Labs/decision-bench` | 43 tasks、27 families、28 domains | 外部共同测试候选 | 候选；eval-only，需确认发布权限与指标 |
| `akhilaaa3/decision-bench` | 同名 DecisionBench，独立发布者 | 外部任务候选 | 不根据同名推断同源；核对来源、配置与交集后计数 |
| `carlosxiang/JEVal` | 统一 typed decision test | 现有参考 TEST | 已纳入基线；Open-Jev×JEVal blocked 单元保持 blocked |
| `Luni/laya-jev-benchmark` | Jev/Laya 比较材料 | 参考文献及任务来源核对 | 独立任务和已有任务的重叠尚待核查，暂不计为新增覆盖 |
| `bespokelabs/bespoke-nimble-9b-v3-decision-index` | Nimble Decision Index 结果包 | 参考结果核对 | 结果/代码包，不作为训练数据 |
| `btzsc/btzsc` | 多配置分类数据 | 来源候选 | 需确认是否有 typed decision schema；未准入前不纳入 |
| `caiovicentino1/eikos-decisions` | 英/葡/西 typed decisions | 多语言候选 | 延后；需确认 split、标签类型和来源族 |
| `respanai/behavior-benchmark` | 多语言行为任务；数据卡记录 1990 tasks | 外部行为测试候选 | 延后；先核对原生评估单位和统计方法，再决定评估范围 |
| `ZefanCai/Open-Jev` | 旧版七套语料及发布投影 | 现有原生 TEST/OOD 与来源核查 | 已有参考读数；配置有包含关系，不相加为独立数据 |

注：上表涵盖 24 个不同本地目录，按数据卡线索归类，尚未完成独立来源计数。结果包、版本投影和同源子集保留来源关联，不能将它们各自算作独立泛化证据；有内容差异的版本仍分别记录。

## 接入顺序

### 第一批：先补公开 TEST 与共同比较

先完成 Kev hard/documents/devtools、Typed Decisions test、BEV 的固定子集、Open-Jev v1.1 的公开测试，以及 DecisionPivot core、DecisionRobust 文本子集的协议核查。此批的目标是回答“各参考模型在更广任务上测试集表现如何”，不是立即训练。每个任务要同时记录：原生指标、统一 decision-level 指标、样本数、split/mask、温度或阈值、来源重叠和是否允许用于选择。

### 第二批：扩训练和开发分布

在第一批指标和来源核查完成后，再讨论并冻结 Typed Decisions、BEV、Open-Jev v1.1 的可用 train 部分。建议比较现有窄域训练（decision-v7 train）、广覆盖训练（去重后的公开 train）及未见来源评估，并分别保留 boolean、nominal、ordinal 及反事实配对。transfer-v4 是现有主要评估集，不因此被改列为训练集。同一骨干的 K0、窄域 K1、广覆盖 K1 应逐任务比较。

### 第三批：补任务缺口

复杂决策、空间、guardrail/safety、多语言、网页和多模态数据用于检验迁移与边界，不直接宣称业务收益。它们必须有独立 TEST、判别对照和失败类型统计；没有可靠原生切分时，只做诊断，不进入训练混合。

## 完成标准

- 公开任务测试指标先完成并发布；原生计算方法不同的结果分表，不强行平均。
- 每个候选登记 train/dev/test、来源族、场景/规则族、输入模态、level 类型和可比较指标。
- 记录 TEST 暴露情况；如果用其结果反向选择方案，则将该轮证据标为开发证据，后续独立泛化声明需要未用于选择的冻结 TEST。已有参考分数的正常汇报不自动使测试集失效。
- 新推理任务前瞻登记后异步入队；CPU 来源审计与指标实现不等待 NPU 空闲，常规模型巡检保持约 10 分钟。
- 任何新增训练收益都必须同时报告域内、未见来源迁移和鲁棒性，不能用一个聚合平均替代。

本文件是覆盖规划与库存记录，不是新增实验结果。新增读数在实验报告和 GitHub Wiki 的最新结论页中登记；本地过程文件按既定三天周期归档。
