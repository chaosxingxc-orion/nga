# 当前任务状态、待决策事项与下一阶段计划

更新时间：2026-11-01 UTC。本文是当前状态快照；远程协作只引用最新结论，运行日志、逐项收据和过程审查留在本地/CephFS 归档。

## 00:58 UTC 增量更新

本次用户主动询问触发了一次有界检查。当前实际状态是 5 个训练容器、2 个推理容器；4B K1 seed2 已以 exit code 0 完成，4B K1 seed3 仍为 1,153/3,116；共享 K2 两个 seed 为 1,169/3,116 和 1,131/3,116。四路 K1 推理均为 148,542/148,542，0.8B K0 为 148,542/148,542，2B K0 为 26,432/148,542（17.8%，仍有 incomplete receipt 标记）。CPU 选择队列已完成 10 项，仍有 6 项等待报告、10 项等待推理；posttrain 队列已完成 6 项、2 项等待训练。

这次检查同时发现 4 张芯片显示空闲，watchdog 报告无失败/停滞但只有 1 个运行任务、0 个排队任务。该信号违反“持续保持 NPU 满载”的工程目标，当前不能把它解释成成功；需要在下一步区分已完成任务的正常资源释放、successor 依赖等待和调度缺口。自动队列和资源释放脚本仍在运行，主会话不会通过重复轮询抢占 CPU/NPU。

真实 Astra 审查已在 `jev_formal_readiness_20261101_v1/review.md` 返回 `CHANGES_REQUIRED`。它验证了 10 个冻结文件的 manifest 哈希，并指出 F1–F8 八类 fail-open 问题。已提交并推送两项修复：`efc3e70` 使 K0 缺失、重建失败和未绑定审查计划均 fail-closed，并要求 resume 收据匹配 canonical plan hash；`a7f4a76` 要求 K0 消费端保留 scoring receipt、生成器和非空检查 provenance。相关 readiness、formal、resume、fresh-precheck 测试均通过。F5–F8（完整 K0 provenance 关系、QO/PT 分臂绑定、完整容器命令拒绝额外配置、formal scope flags）仍需逐项补强或由新 Astra 审查确认，旧审查绝不能作为通过依据。修复后必须构建新的 bundle 和 manifest，重新进行独立 Astra 审查。

## 当前结论

项目仍处在“参考推理与工程准入收口、正式控制训练尚未开始”的阶段。工程基座训练和推理已经产生进度，但当前没有可发布的训练收益，也没有正式测试集训练前后对比。D1 的 38 个参考单元仍是固定范围；已形成的参考矩阵可以继续作为指标汇报入口，Open-Jev×JEVal 的两个单元仍不能填零，必须保持 blocked/null，直到真实准入和独立计分完成。

NPU 任务正在 detached 队列中运行：最近一次有界巡检（2026-11-01 00:58 UTC）记录 5 个训练容器和 2 个推理容器，无失败或停滞告警。4B K1 seed2 已以 exit code 0 完成，seed3 为 1,153/3,116；共享 K2 两个 seed 为 1,169/3,116 和 1,131/3,116。四路 K1 推理和 0.8B K0 均为 148,542/148,542；2B K0 为 26,432/148,542（17.8%，仍带 incomplete receipt 标记）。以上是进度计数，不是测试指标或训练收益。

正式控制 readiness 仍为 `WAITING`：QO 与 PT 证据通过，K0 报告虽已完成部分 CPU 后处理但尚未形成可消费的完整正式 bundle，真实训练终止收据、CPU reconstruction 和新的独立 Astra 审查尚未齐全；`scientific_acceptance=false`、`test_read=false`。不存在手工伪造的 TRAIN_EXIT、CONTRACT_RESULT 或恢复收据。

独立 Astra 已通过真实 CLI detached 启动并返回 `CHANGES_REQUIRED`。审查 bundle 固定为 10 个文件，manifest SHA256 为 `56fdd8faf97bc449695e2a347213b340be158f0480e84932f5a119dc9846a052`；报告验证了全部 manifest 哈希，并列出 F1–F8 具体反例。该审查不是批准文件，不能作为正式准入通过。

## 已落实的工程规则

- NPU 与 CPU 异步：每张芯片维护 FIFO 任务队列；CPU 计分、基线锁定、Astra 结果分析和报告刷新按依赖有序处理，不阻塞无依赖的 NPU 后继任务。
- 监控共享 600 秒窗口。watchdog 默认 `--interval 600`，`.local/NPU-MONITORING.json` 也以 600 秒为最小例行检查间隔。用户明确询问、终止/失败/停滞、队列耗尽或设备空闲等信号允许只检查受影响任务的提前检查；没有信号时不高频轮询、不读取原始长日志。
- 主会话只读取 bounded digest 和定向审查结论；原始日志由 watchdog 或受限的审查代理处理。
- 队列调度、资源释放和 CPU 后处理由脚本持续推进，不能因为模型未被唤醒而暂停 NPU。
- 每三天把本地过程文稿归档；远程 wiki 只保留最新结论和协同所需信息。

## 已完成与进行中

### 已完成

1. D1 的固定参考范围、按公式/温度/目标/有效分母拆分的统计规则已冻结。
2. 参考基线矩阵和增量报告已建立；测试集是主要汇报口径，开发集只用于选择、阈值和诊断。
3. watchdog 和本地共享巡检锁已统一为约 10 分钟 cadence；运行中的 watchdog 无失败或停滞标记。
4. 训练/推理 detached 运行、heartbeat、terminal marker、可恢复任务和 bounded digest 机制已在用。
5. readiness 审计、恢复合同和闭包检查已完成近期修复；F1–F4 及 K0 provenance 消费闭包已加固，相关 CPU 回归通过；F5–F8 仍需完成或由新 Astra 审查确认。

### 进行中

1. 根据 `CHANGES_REQUIRED` 修复结果生成新的 formal readiness bundle，并等待新一轮真实 Astra CLI 终态。
2. 等待 2B K0、4B seed3 和共享 K2 真实退出，随后验证报告、终止收据和资源释放。
3. 对已完成的 NPU 输出执行独立 CPU reconstruction 和计分，再刷新最新参考/训练报告。
4. 准备 formal K1 的精确计划、manifest 和审查材料；正式训练仍受 D1 阶段顺序与 readiness 约束。

## 需要负责人决策的内容

已确认的 D1–D7 不需要再次决策：D1 不扩展 38 个参考单元；D2 暂不设算力预算上限；D3/D4/D7 暂不接入真实业务；D5–D6 按已登记 seed、控制器和版本化方案推进。当前只需要在下列节点做阶段性确认：

1. **NPU 空闲处置（当前需要确认）**：如果下一次定向核验确认 4 张芯片只是已完成任务的正常释放，是否允许队列控制器自动把已准备的 successor 补到空闲芯片；默认允许，但必须有真实启动收据、芯片所有权和 600 秒 watchdog。
2. **参考矩阵缺口处理**：两个 Open-Jev×JEVal 单元在准入完成后是否作为同一 D1 增量报告追加；默认按既定方案追加，不改写旧快照。
3. **训练首轮的冻结门槛**：formal readiness、K0 报告、CPU reconstruction、新的独立 Astra 和 exact manifest 全部齐备后，是否启动 K1 seed 2/3；默认满足后启动。
4. **指标冲突处理**：文献公式、温度或分母不同继续分栏；若无法证明同口径，保留并列值与限制，不强行合并。

这些是门槛确认，不影响当前队列继续运行。

## 下一阶段计划

### M1：收口当前运行与 Astra 审查

- 等待明确完成信号；到下一个共享 600 秒窗口再读一次 bounded digest。
- Astra 已返回 `CHANGES_REQUIRED`；保留旧审查代次，完成 F1–F4 与 K0 provenance 修复，随后生成新 bundle。新审查必须重新验证 manifest、代码闭包、exact plan identity 和 F5–F8，不复用旧 verdict。
- K0/训练实际终止后验证 canonical receipt、wrapper EXIT、report SHA、资源释放和恢复链。

### M2：独立重算与最新参考报告

- CPU lane 异步完成 reconstruction、分数和 flags；严格使用冻结测试集及预注册公式。
- 生成新的增量报告，读数与既有快照一致时保留原值；旧过程文稿进入本地 archive，远程 wiki 只更新最新结论。
- 在两个 Open-Jev×JEVal 单元完成真实准入前继续保留 `blocked/null`。

### M2.5：恢复满载和 successor 调度

- 只读取受影响队列的 bounded digest 和芯片分配文件，定位 4 张空闲芯片对应的前驱/后继依赖。
- 若是正常释放，自动继续下一个已准备任务；若是等待训练或 receipt 缺失，修复调度器的依赖推进，不重复启动已有 generation。
- 保持每个任务 detached、可恢复、带 heartbeat、terminal marker 和 relaunch 命令；不通过手工标记完成来填补队列。

### M3：工程基座首轮训练

- 冻结代码/模型/数据/配置 SHA 和 K1 seed 2/3；先跑 direct-readout K0 对照，再跑同骨干 K1。
- NPU 队列保持持续消费；CPU 同步处理 dev 评分、收据核验和候选选择。候选选择只能看 dev，不能提前读取候选 test 收益。
- 每芯片记录吞吐、reserved/allocated/峰值显存、heartbeat、恢复点和资源释放证据。

### M4：测试集汇报与后续学习方法

- 只有候选锁定、seed/来源/终态/独立计分和 Astra 范围审查完整后，才读取并发布一次候选测试集结果。
- 在 K0/K1 基线稳定后，逐项加入 option-restricted loss、proper scoring、校准、蒸馏和优化方法；RL 需等可审计业务缺口任务和可用基线完成后再登记。
- 每个 milestone 完成后刷新最新报告，维持可追溯的旧归档。

## 当前出口条件

进入正式训练收益判断前必须同时满足：参考报告能解释全部 38 个登记组合的状态；K0 测试读数已由独立计分确认；formal readiness 不再为 WAITING；真实恢复/终止收据完整；精确训练计划有独立 Astra 结论；候选测试集仍处于锁定状态直到选择完成。满足后才讨论“是否观察到 Jev 收益”，并将结果限定为公开任务收益，不写成真实业务收益。

证据入口：

- `experiments/REFERENCE-BASELINE-LATEST.md`
- `experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json`
- `/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_control_readiness_20261031_v1.json`
- `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jev_formal_readiness_20261101_v1/`
- `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jev_formal_readiness_20261101_v1/review.md`（`CHANGES_REQUIRED`，不可作为准入通过）
- `.local/NPU-MONITORING.json`
