# Jev 工程与实验状态（2026-11-04）

> 这是当前状态快照，记录截至 2026-11-04 的事实、门禁和下一步计划。它不是测试结果本身，也不替代 `REFERENCE-BASELINE-LATEST.md` 中已经冻结的指标。NPU 状态以 175 服务器的 allocation ledger、终态文件和报告为准。

## 1. 当前结论

项目已经完成“固定基座的主要测试集基线”和“交叉候选接口的数值准入”，但还没有进入下一轮行为 DEV，也没有产生训练候选在同一 TEST 集上的科学收益结论。175 服务器当前没有运行中的 NPU 容器；8 张卡均在 allocation ledger 中标记为 free。这是行为 DEV 门禁尚未解除造成的空档，不代表笛卡尔积或训练收益已经完成。

当前最重要的事实是：

- 固定基座 Qwen3.5 四规格 × 28 个面板，共 112/112 格已验收；Jev-bench 子集 88/88 格已验收。
- D1 异构参考层 38 个 model×dataset 单元中，36 个有结果，2 个 Open-Jev×JEVal 单元仍为 `blocked/null`。不同论文的温度、硬/软标签、分母和概率指标继续分表，不做不等价合并。
- 五个大候选任务 × 四规格，共 20 格 TEST 推理和 CPU 独立复算已完成。它们用于模型/任务基座比较，不等于训练收益。
- 0.8B LoRA 训练的 DEV 资格和七成员候选方案已经形成。DEV 平均约 82.397152%，相对 K0 提升 24.011076 pp；transfer 平均约 65.167683%，相对 K0 提升 4.649390 pp。这些仍是 DEV/transfer 诊断，不能写成同 TEST 收益。
- 七成员候选的最终同 TEST 评测仍未启动，因为正式门禁要求真实的 `independent_astra`、`gpt-6-astra`、`PASS` 审查文件；目前只有调度规则确认，没有实质 Astra REVIEW 文件。不能用普通独立复核替代，也不能伪造审查身份。

## 2. NPU 上最近完成的实验设置

### 2.1 数值准入 v2（已完成，非科学收益实验）

运行目录：`/mnt/cephfs/xingchao/experiments/jev/r3_runs/large_candidate_interface_execution_20261104_v2/`

四个模型各自使用单卡、3 个变体（`reference`、`reference_repeat`、`adapter`），每个模型 48 条输入 × 3 变体，共 144 次 forward。结果如下：

| 模型 | forward | 变体通过 | 原始值完全一致 | scientific_acceptance | test_read | 资源 |
| --- | ---: | ---: | --- | --- | --- | --- |
| Qwen3.5-0.8B | 144/144 | 3/3 | `true` | `false` | `false` | chip 0，3.7695 GiB |
| Qwen3.5-2B | 144/144 | 3/3 | `true` | `false` | `false` | chip 1，8.1387 GiB |
| Qwen3.5-4B | 144/144 | 3/3 | `true` | `false` | `false` | chip 2，18.4023 GiB |
| Qwen3.5-9B | 144/144 | 3/3 | `true` | `false` | `false` | chip 3，36.2734 GiB |

每个报告都显示 `completed_items=144`、`passes=3`、`reused_items=0`、`all_raw_exact=true`，并明确 `scientific_acceptance=false`、`test_read=false`。因此这一步只说明接口的数值一致性和运行完整性通过，不能说明模型在业务任务上变好。

每个任务均有 host `CLAIM.json`、运行 `EXIT.json`、host `EXIT.json` 和 `RELEASE.json`。四张卡已经释放，释放时间约为 2026-11-04 19:26–19:29 UTC。证据不删除，保留在上述 CephFS 目录中。

### 2.2 行为 DEV（已准备，尚未启动）

准备目录仍为：

`.local/preparations/large-candidate-interface-dev-20261104-v1/`

以及执行包：

`.local/preparations/large-candidate-interface-execution-20261104-v1/`

计划规模为每模型 672 个行为请求，四模型合计 2,688 个 forward。计划已经完成配置化生成、候选顺序固定、语义辨别对照、完整词表检查、batch=1、float32、HF32 off、8192 最大长度、item-level resume 和 600 秒监控配置。独立工程审查结果为 `PASS_PREPARATION_ONLY_NOT_EXECUTION_AUTHORITY`，即准备包合格，但不构成执行授权。

行为计划当前仍标为 `ready=false`，原因是：

1. 数值准入还没有由独立复核文件正式封存为 PASS；
2. 行为计划需要更新对应 numerical gate 后重新计算计划哈希；
3. 重新做行为计划的前瞻登记和独立审查；
4. 启动时必须使用新鲜的 physical resource binding，不能借用旧 lease；
5. 最终仍需父会话执行审查后才可以 claim 卡并 detached 启动。

## 3. 175 服务器当前资源状态

当前 ledger：`/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json`

- host：`npu (175)`
- 设备：8 × Ascend 910B3，单卡 64 GiB HBM
- `allocation=[]`
- `free=[0,1,2,3,4,5,6,7]`
- 当前没有已登记的 NPU 运行任务

这里的“空闲”来自 allocation ledger 和释放证据，不是从一次 `npu-smi` 采样推断。当前空闲的直接原因是行为 DEV 尚未获得执行授权，而不是资源故障。按照工程约束，这个空档应在行为门禁通过后立即用已排队的 2,688-forward 行为 DEV 填充；在门禁通过前，不启动未经审查的实验来制造假满载。

## 4. 任务完成度

| 工作线 | 当前状态 | 是否可写成最终科学结论 |
| --- | --- | --- |
| D1 参考模型/数据集 TEST 指标 | 固定矩阵已锁定，38 单元中 36 有结果 | 是，限于已登记协议 |
| Qwen3.5 固定基座 NxM | 112/112 面板验收；大候选五任务 20/20 完成 | 是，限于直接驱动基线 |
| 0.8B LoRA DEV/transfer | 七成员候选已形成，DEV 诊断有提升 | 否，尚未完成同 TEST |
| 交叉候选数值接口 | 四模型 144/144 完成 | 否，只是数值准入 |
| 交叉候选行为 DEV | 计划完成，0/2,688 启动 | 否 |
| 七成员同 TEST | 被真实 Astra 实质审查门禁阻塞 | 否 |
| 新业务缺失数据集 | 已识别缺口，尚未进入本轮实验执行 | 否 |
| 强化学习优化 | 依赖前一阶段稳定轨迹和采集，尚未开始 | 否 |

## 4.1 Numerical admission 复核后的新发现（2026-11-05）

四个 v2 numerical probe 的父执行审查均为 PASS，但 Astra 评价发现一个必须修复的证据缺口：运行时确实检查了完整 `(1, 248320)` float32 vocabulary logits，却没有把完整 raw vocabulary 输出持久化，现有 report 只有候选 operand/摘要。因此 `all_raw_exact=true` 只能证明运行时内部比较通过，不能支持独立 raw-logit 复算，也不能升级为正式 full-vocabulary numerical admission PASS。

旧目录中其他批次的 `PASS_204_SYNTHETIC_OPERANDS` 或短/长 probe 证据属于不同 generation、不同计划和不同 scope，不能回填到 v2。Terra 正在制作新 generation：补充可独立复算的分块 raw evidence、shape/dtype/request/plan 绑定和篡改反例测试；在新证据完成前，行为 DEV 仍保持 `launch_authorized=false`。

## 5. 当前需要用户决策的内容

现在没有必须立即回答才能继续做的科学定义问题，D1–D7 的范围已经按此前约定冻结。为了避免下一次执行歧义，建议确认两项运行策略：

1. **行为 DEV 自动启动策略（建议：同意）**：独立 numerical 复核为 PASS、计划哈希刷新、行为独立审查为 PASS、fresh binding 成功后，是否允许父会话不再等待额外人工确认，直接启动四模型行为 DEV？这只授权 DEV，不授权读取 TEST 或宣称业务收益。
2. **空卡备用队列（建议：同意）**：当主行为 DEV 因门禁暂不能启动时，是否保留一组已经审查过的、短时可恢复的工程验证任务作为 fallback；它们只验证吞吐、恢复和监控，不改变科学数据或结论。若不同意，则在门禁期间保持卡空闲，避免运行未完成审查的任务。

## 6. 下一阶段执行计划

### 阶段 A：封存数值准入

1. 接收独立 CPU 复核 `.local/reviews/interface-numerical-results-independent-20261104-v1/REVIEW.{json,md}`。
2. 主会话只核对 bounded review、四份 report、CLAIM/RELEASE/EXIT 和 container 终态哈希；不读原始长日志。
3. 复核通过后，为四模型生成正式 numerical admission PASS 证据，并在每个行为计划中更新 gate 和哈希。

### 阶段 B：启动行为 DEV

1. 重新生成四份行为计划并做独立前瞻审查。
2. 读取最新 ledger，逐卡完成 fresh claim；每张卡一个 detached 容器，保留日志、心跳、退出码、释放证据和 relaunch 命令。
3. 启动 0.8B、2B、4B、9B 的 2,688 个行为 forward。NPU 任务按 FIFO 运行，CPU 评分和诊断异步进行。
4. watchdog 只按约 600 秒轮巡或明确事件触发；digest 负责汇总状态、错误签名和证据指针，原始日志不进入主会话。
5. CPU 使用多线程脚本完成数值评分、重复性检查和候选筛选，不能让评测串行阻塞 NPU。

### 阶段 C：决定是否进入同 TEST

1. 用预注册规则对行为 DEV 结果做候选筛选，保存每个单元的原始结果和可复算报告。
2. 若候选满足门槛，继续真实 Astra 实质审查；没有真实 `independent_astra` PASS 就不读最终 TEST。
3. 完成七成员同 TEST 后，再独立重建训练/控制对比，报告 TEST 指标、不同统计协议和置信区间。

### 阶段 D：继续业务任务与系统训练

行为基座稳定后，按四个维度推进：模型直接驱动、结构改造、任务/训练设计、学习/优化方法。先补齐业务侧缺失的中文规则、证据、unknown/fallback、升级和成本任务，再设计强化学习优化和可用基线。此阶段依赖稳定轨迹、采集协议和前一阶段门禁，不提前并行宣称收益。

## 7. 证据和操作入口

- 固定基座：`experiments/REFERENCE-BASELINE-LATEST.md`
- 数值准入执行包：`/mnt/cephfs/xingchao/experiments/jev/r3_runs/large_candidate_interface_execution_20261104_v2/`
- 175 资源账本：`/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json`
- 工程准备独立审查：`.local/reviews/interface-dev-independent-20261104-v1/REVIEW.md`
- Astra 最终审查调度记录：`.local/reviews/astra-final-test-adversarial-20261104-v3/DISPATCH-OUTCOME.json`
- 最终准入工具：`tools/r3_final_admission.py`

## 8. 状态边界

本文件把“完成推理”“数值准入通过”“行为 DEV 完成”“同 TEST 科学验收”和“业务收益”分开。当前只完成到数值准入运行结束，尚未越过行为 DEV 执行门禁；任何后续报告都必须保留这条边界。
