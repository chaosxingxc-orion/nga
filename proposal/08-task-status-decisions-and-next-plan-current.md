# 当前任务现状、待决策事项与下一阶段计划

更新时间：2026-10-31（依据当前仓库、参考矩阵、E38/E39 记录、E38 release 修复状态和实际审查结果）。本文件保留为完整状态说明；每个 milestone 的最新阅读入口是 [`REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md)。

这是一份面向项目负责人的当前快照。它只描述已经形成证据的进度，不把运行中的容器、CPU 回归或历史报告当成科学结果。用户已经确认的 D1–D7 和“推理实验也必须自动驱动执行”均作为本文件的硬约束。

## 先看结论

当前处在“参考模型测试结果基本形成，两个 Open-Jev×JEVal 单元仍被 E38 工程准入阻断，训练尚未开始”的阶段。

- 原登记矩阵中有 **36 个已形成结果的模型×数据集组合**，另有 **2 个 `blocked/null` 组合**：Open-Jev-2B×JEVal、Open-Jev-9B×JEVal。
- 不同文献公式、温度、hard/soft 目标和有效分母已经分开统计；不能把这些面板合并成一个总分。
- E39 已完成 28 个历史 Kev 面板的当前 CPU 独立重算和有界 Astra 审查，最大数值差约 `1.11e-16`。这证明保存证据可重建，但没有补造历史 finisher，也没有证明 cache/restart 的无人值守安全性。
- E38 v7 固定镜像 CPU 套件 **100/100 通过、无 skip**；两份 v7 exact plan 已通过实际 Astra 的指定范围审查。
- Open-Jev-2B 已完成 8/8 NPU 诊断 forward，Docker 和独立 CPU verifier 均 exit 0，`trace_valid=true`，但这只是路径诊断，不是 JEVal 结果或训练收益。
- 2B 资源已由通过审查的工具实际释放；9B v7 已启动并完成 8/8 NPU 诊断，NPU 与独立 CPU verifier 均实际 exited/0。9B 数值差异仍存在，完整 JEVal 准入保持 false；资源释放已完成并独立核验；有界 Astra 结果审查已 PASS，范围仅为诊断与冻结资源证据。
- 正式 Jev 训练、训练后评测和训练收益尚未发生；真实业务、生产接入和业务标注按 D3/D4/D7 暂不纳入。

当前最准确的阶段描述是：**先收口并汇报参考指标，同时完成剩余推理实验的自动执行和工程准入；E38/JEVal 收口后再讨论并预注册 Jev 训练。**

## 1. 用户指令如何约束当前工作

| 指令 | 已确定的含义 | 当前执行结果 |
| --- | --- | --- |
| D1 | 先汇报参考模型在测试集上的指标；文献有不同计算方法时分开统计；之后再讨论训练 | 当前优先级是参考推理、独立计分、分口径报告；新训练不能抢在参考汇报之前开始 |
| D2 | 暂时取消算力预算上限 | 不再用旧预算限制任务；仍记录芯片数、每芯片吞吐、显存、占用、释放和异常退出 |
| D3/D4/D7 | 暂不考虑真实业务、生产系统和业务标注；先做 Jev 训练方案并在公开任务看目标相关收益 | 公开测试集是首阶段收益证据；不能把公开任务结果写成业务收益 |
| D5 | 按建议登记 seed | 读取训练结果前先登记 seed 数量和身份，禁止看结果后追加有利 seed |
| D6 | S1 监测、确定性 controller、S2 版本化 slots 保留为候选架构 | 这些是后续研究候选，不是当前已经验证的收益，也不替代实验执行 controller |
| 自动执行 | 自动启动、恢复、计分、终态检查、资源释放和 wiki 记录必须真实完成 | 推理和训练都按实验处理；只有完整证据链才可进入正式报告 |

D1 是阶段顺序，不是暂停推理。为取得参考指标而进行的推理、恢复、工程修复和独立验收现在必须继续；但正式 Jev 训练要等参考汇报和训练预注册完成。推理本身是正式实验，不能因训练尚未开始而暂停自动执行。

## 2. 当前参考结果进度

机器可读主索引为 [`REFERENCE-BASELINE-MATRIX-2026-10-31.json`](../experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json)，增量索引为 [`REFERENCE-BASELINE-INCREMENT-2026-10-31.json`](../experiments/REFERENCE-BASELINE-INCREMENT-2026-10-31.json)。

已完成并可纳入 D1 增量报告的结果包括：

1. **Kev 原生测试集**：0.8B、4B、9B 的 decision-v7、transfer-v4、hard-v1、documents-v1、devtools-v1（devtools full/release 分母分开），native serving 温度和 raw T=1 分开报告 accuracy、Brier、ECE10、NLL。
2. **Nimble 原生测试集**：七个子集分别报告 accuracy、multiclass Brier、Noul binary Brier、expected-score MAE 等原任务指标；这些子集不能合并成 Kev 定义的总分。
3. **Typed Decisions 共同测试**：400 states、2,000 questions；serving 温度和 raw T=1 分开，KL、Brier、ECE10 使用预注册定义。
4. **Open-Jev 原始 OOD 测试**：hard accuracy 只使用 one-hot 行，expected accuracy、NLL、Brier、expected Brier、ECE15 使用全体行；两套输入集合的分母不能混合。
5. **JEVal**：Kev-0.8B、Kev-4B、Kev-9B、Nimble 已有有界参考结果，并保留各自 flags、overlength、candidate-limit、empty-context 等限制。Open-Jev-2B/9B 尚为 `blocked/null`。

这些结果能支持“参考模型在已登记公开测试上的现状”汇报，不能推出 Jev 训练收益、论文精确复现、无污染结论或真实业务收益。

参考模型的主要对齐指标来自各数据集冻结的 **test split**。development/calibration 只用于配方诊断、效率测量、阈值拟合和训练前门槛；它们不能替代 test，也不能在读取 test 后反向调参。业内或论文存在不同计算公式时，按公式、温度、有效分母和 hard/soft 目标并列统计。

## 3. E38/E39 与当前阻塞

### 已完成

- E39：8,462 条回执、11,495 个问题、28 个历史 Kev 面板独立重算；实际 Astra 完成有界审查，指标和分母未被修改。
- E38 v7 CPU 工程套件：固定镜像 100/100 通过，无 skip；实际 Qwen3.5/GDN 源码闭包、计划 SHA、审批字节和退出代次已纳入证据。
- E38 v7 exact-plan Astra 审查：结论为 **PASS for exact v7 plans only**。该结论不授权 NPU、JEVal、训练或资源释放。
- Open-Jev-2B：8/8 预注册 forward、NPU 容器 exit 0、独立 CPU verifier exit 0。within-path repeats 和 hook controls exact；original/chunk8 差异可重复，最大 logit/probability/wire delta 分别为 `0.05192685127258301`、`0.00351450921098978`、`0.003765545583203328`，decision 未变化但 serialized prediction 非 exact。

### 当前交接与剩余阻塞（2026-10-31 更新）

此前 release 的代次绑定、可信 before-state、发布中断恢复和顶层 helper 身份问题已修复。实际 Astra v4 对精确 v6 候选给出代码 PASS、拟议证据一致性 PASS；主会话已独立核验 COMPLETE 的 6 个输出哈希及 child/runner/EXIT 的 rc=0。审查原文见 [v4 归档](../experiments/ASTRA-E38-RELEASE-V4-2026-10-31.md)。审查检查了 58/58 测试记录及源码对应关系，本轮未重跑测试，不应表述为 Astra 亲自重跑 58 项。

1. **2B 实际交接已完成**：新建 approved review 和调用方固定的外部 anchor，经现场核验和 guarded release 释放 chip 4；主会话核验 journal 哈希与其他 owner 未改变，旧 approved=false 提案未覆盖。
2. **9B E38 已执行并独立验证**：UTC 03:40:15 启动、03:44:24 NPU exited/0，8/8 完成；03:45:29 独立 CPU verifier exited/0。两个重复的首个不同事件均为第一层 in_proj_qkv 输出，candidate_batch_admission=false。资源释放已完成，free=[1,4]，有界 Astra 结果审查也已 PASS。
3. **完整 JEVal 数值/内存准入仍未完成**：E38 诊断通过不能替代 full-test 准入。E40 生命周期候选的固定镜像 CPU 检查已完成 32 cells/256 forwards，输出字节 exact；NPU 显存与数值效果尚未证明。E40 v1 已被实际 Astra BLOCK：原生 cu_seqlens=None 兼容、启动路径可信性、各模式 guard 开销一致性、失败观测保存、启动恢复五项问题已修复，固定镜像 CPU 接口/启动验证完成，v2 已冻结并启动实际复审。
4. **满载尚未实现**：03:37 UTC 的现场八卡均无 NPU 进程，只有 chip 1 登记为 free。除 chip 4 交接外，其他历史 owner 的退出、验收和释放证据需逐一核验，不能把空闲读数直接改写为资源授权。

下一顺序是：取得 E40 v2 实际审查结论 → 现场核验并启动 E40 NPU 对照 → 实测全形状数值/内存效果 → 逐级完整 JEVal 准入。现有参考指标不变，没有新增训练收益。

## 4. 推理实验的自动执行闭环

每个模型×数据集组合都必须独立经过以下状态，不能用另一个组合的结果替代：

```text
REGISTERED
  -> PREPARED       固定模型、数据、公式、分母、代码和 plan/request SHA
  -> REVIEWED       exact plan 获得对应范围的独立审查放行
  -> RUNNING        detached 容器、CephFS 日志、heartbeat、逐 item receipt
  -> PAUSED         中断或资源异常，保留证据
  -> RUNNING        从最后一个确定完成的 item 恢复
  -> FINISHED       Docker exit、wrapper EXIT、terminal marker、report 齐全
  -> SCORED         独立计分，按预注册公式和分母输出全部口径
  -> ACCEPTED       独立 verifier 核对身份、receipt、终态、flags 和资源证据
  -> REPORTED       写入 D1 矩阵和 wiki，只追加新快照
```

每项超过一分钟的推理实验必须留下：预注册目的和假设、模型/数据/代码 SHA、固定容器名、detached 启动命令、CephFS 日志、heartbeat、逐 item 恢复状态、wrapper EXIT、terminal marker、report SHA、独立 verifier、watchdog digest、资源释放证据和 wiki 条目。watchdog 的 `done` 只代表进程结束，不能替代科学验收；原始长日志由 watchdog 和定向审查读取，不能直接当作主会话结论。

这也解释了为什么“2B 容器 exit 0”还不等于“2B JEVal 完成”：它完成了 E38 诊断路径的一部分，尚未完成 Open-Jev JEVal 的原生推理、计分、独立准入和资源释放。

## 5. 已确认的决策与仍需讨论的内容

项目负责人已经确认：D1 不扩展完整笛卡尔积；以后每个 milestone 完成后增量刷新一份新报告，最新报告作为阅读入口，旧报告保留归档查询且不再作为当前事实权威。已确认的 D2–D7 不需要再次决策。

本次已将该规则写入 [`REFERENCE-BASELINE-LATEST.md`](../experiments/REFERENCE-BASELINE-LATEST.md) 和 milestone 报告 [`REFERENCE-BASELINE-REPORT-20261031T021500Z.md`](../experiments/REFERENCE-BASELINE-REPORT-20261031T021500Z.md)。指标刷新必须保持读数一致；任何读数变化都要新建代次并解释旧值、新值和原因。

此前待确认的两项范围选择现已关闭：

### 5.1 D1 第一批是否扩展完整笛卡尔积

**已确认：不扩展。** 按当前已登记的 38 个组合收口：36 个先报告，2 个 Open-Jev×JEVal 明确标为 `blocked/null`，完成后追加。临时扩展所有兼容模型×数据集会改变数据适用性、资源计划和分母，应另立登记，不能在结果出来后扩大范围。

### 5.2 D1 是否先发布增量报告

**已确认：按 milestone 增量发布。** 先发布 36 个已有结果的带限制报告，两个 Open-Jev×JEVal 完成后追加新日期快照。旧矩阵不覆盖、不把缺失项记为零分；新增结果只追加 SHA、分母、flags 和审查范围。最新入口指向当前报告，旧报告只作归档查询。

这两项边界已经确定，工程侧按此执行，不会把未完成组合伪装成完成。

训练相关决策将在 D1 汇报之后提出，预计包括第一训练规模、K0/K1/K2 对照、seed 数量、公开测试集、收益阈值和失败处置；现在不提前冻结，也不启动正式训练。

## 6. 下一阶段计划与出口条件

### P0：交付 D1 增量参考报告（当前可做）

- 固定 36/2 计数、公式、温度、有效分母、flags 和限制。
- 明确区分“有结果”“blocked/null”“不适用/未登记”。
- 发布参考指标表和机器索引，不把历史面板、上游数字和本地新推理混写。
- 主表使用冻结 test split；dev/calibration 只作为辅助诊断并单独标注。

出口：读者可以从报告中知道每个登记组合的指标来源、计算口径和证据限制；所有主指标均来自冻结 test split，并能与业内结果按同一公式或明确的并列公式对照。

### P1：修复并重新审查 E38 release（已完成代码与拟议证据审查）

- 补齐 CPU/NPU verifier 对 `LAUNCH_RECEIPT`、`EXIT`、`FinishedAt` 的绑定。
- 建立可信 allocation before-state 锚。
- 把 queue、真实 release 入口和 `publish_new()` 崩溃窗口测试纳入审查 bundle。
- 运行纯 CPU 回归，生成新的 bundle/request，不修改旧审查文件。
- 审查期间并行完成 CPU 修复、回归、bundle 构建、报告整理和 watchdog 准备，缩短获批后的 NPU 启动间隔。

出口已达到：实际 Astra v4 对精确 v6 候选代码与拟议证据给出 PASS。该阶段不涵盖现场释放；实际交接和新 anchor 属于 P2。历史 BLOCK 及修复过程保留归档。

### P2：释放 2B 并串行完成 9B E38（执行、独立 CPU 验证、释放与有界结果审查均完成）

- 重新核验 175 上 allocation、Docker、`npu-smi` 和 chip 4 实际状态。
- 只由审查通过的 release 事务释放 2B；独立确认 allocation 变为 free。
- 串行启动 9B，完成 8/8 诊断、独立 CPU verifier 和 wiki 记录。

出口：两尺寸 E38 诊断均有完整终态、独立验收和资源证据；仍需把它们与 JEVal 计分严格区分。

### P3：完成 Open-Jev JEVal 并更新参考矩阵

- E38 完成后先做独立的数值与内存准入。2B 的首个观测差异在第一层 `in_proj_qkv` 输出，早于 GDN core；chunk8 仍不等价。保持完整运算形状的生命周期优化及必要的字节搬运需另立实验，不能从 E38 成功直接跳到全量 JEVal。详见 [后续准入路线](../experiments/OPENJEV-JEVAL-NEXT-ADMISSION-2026-10-31.md)。
- 只使用准入通过的原生结果；严格分开 hard、expected、valid、overlength 和 score 分母。
- 按已登记公式并列输出不同文献口径，执行独立计分和限定审查。
- 更新增量索引，不覆盖旧矩阵。

出口：38 个原登记组合都有明确状态，D1 参考报告可以完整说明缺口和限制。

### P4：D1 汇报完成后再讨论训练

- 以当前参考结果作为训练方案输入。
- 首轮建议从一个小规模 Qwen/Jev 闭环开始，保留同一公开测试集的训练前基线。
- 训练前登记 seed、K0/K1/K2 对照、数据/模型/代码 SHA、主指标、稳定性、校准/拒答、效率字段、采用规则和失败处置。

出口：预注册文件冻结，自动训练和评测任务具备启动条件。

### P5：自动训练、评测和收益判断

- detached 启动，写入 heartbeat、逐 step/逐 item 进度、可恢复状态、terminal marker 和 relaunch 命令。
- 独立评测同一测试集、同一公式和同一分母，训练前后成对比较。
- 每芯片报告吞吐、芯片数、reserved/allocated 显存、峰值显存和有效工作量。
- 只有 seed、paired protocol、结果来源、终态和资源证据全部通过，才能写“观察到 Jev 收益”或“未观察到收益”。

## 7. NPU 满载原则的实际执行方式

“持续保持 NPU 满载”是调度原则，但必须服从实验准入和证据链。当前执行顺序如下：

1. 复用已登记且已审查的 NPU 工作；chip 4 的 9B 诊断已完成并释放，chip 1/4 已登记 free，不能把瞬时 `npu-smi` 空闲当成可重新分配。
2. 当前并行推进 chip 4 交接、chip 1 的 E40 驱动与计划、其他历史 owner 的只读释放证据核验。CPU 工作不能计作 NPU 利用率；记录实际空闲和造成空闲的缺口。
3. Astra PASS 后重新核验 Docker、`npu-smi`、allocation 和 owner；由 release 工具完成 2B 释放，独立确认 chip 4 为 free 后立即串行启动 9B。
4. 9B E38 完成并验收后，继续数值/内存准入实验；原生完整 test 路径通过后立即进入两个 Open-Jev JEVal 推理、独立计分和报告刷新。所有长任务均用 detached、可恢复、带 heartbeat 的自动执行。
5. 每芯片记录吞吐、芯片数、reserved/allocated/peak 显存、heartbeat、终态和释放时间。没有安全且已登记的 NPU 工作时，受控空闲优于污染正式实验。

## 8. 当前明确不能做的事

- 不启动被实际 Astra BLOCK 的旧 E38 计划。
- 不把 CPU 100/100 或容器 exit 0 写成 JEVal 完成。
- 不手工修改 allocation，不在 2B 未释放前启动 9B。
- 不把 OOD、Typed Decisions、JEVal、Kev 原生 test 的不同分母合成总分。
- 不在 D1 参考结果汇报和训练预注册前启动正式 Jev 训练。
- 不把 D6 候选架构写成已验证收益，不把公开任务收益写成真实业务收益。

## 9. 证据入口

- [上一版完整状态与执行计划](07-current-status-decisions-and-inference-execution-plan-2026-10-31.md)
- [参考矩阵](../experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json)
- [参考增量索引](../experiments/REFERENCE-BASELINE-INCREMENT-2026-10-31.json)
- [E38 路径跟踪](../wiki/E38-openjev-path-trace-20261031.md)
- [E39 Kev 当前复核](../wiki/E39-legacy-kev-current-reaudit-20261031.md)
- [研究方案](JEV-REPRODUCTION-PLAN.md)

