# 当前任务状态、待决策事项与下一阶段计划

更新时间：2026-11-01 UTC。本文是当前状态快照；远程协作只引用最新结论，运行日志、逐项收据和过程审查留在本地/CephFS 归档。

## 00:58 UTC 增量更新

本次用户主动询问触发了一次有界检查。当前实际状态是 5 个训练容器、2 个推理容器；4B K1 seed2 已以 exit code 0 完成，4B K1 seed3 仍为 1,153/3,116；逐候选 K2 两个 seed 为 1,169/3,116 和 1,131/3,116。四路 K1 推理均为 148,542/148,542，0.8B K0 为 148,542/148,542，2B K0 为 26,432/148,542（17.8%，仍有 incomplete receipt 标记）。CPU 选择队列已完成 10 项，仍有 6 项等待报告、10 项等待推理；posttrain 队列已完成 6 项、2 项等待训练。

更正（2026-11-01）：摘要 `unused chips 4` 中的 4 是芯片编号，**不是四张芯片空闲**。同一摘要中的 1 个运行任务、0 个排队任务只覆盖该推理 watchdog 的登记范围，不能解释成全机任务数。00:58 UTC 的 Docker 快照仍有 5 个训练、2 个推理容器。定向检查发现 4B seed2 后继队列报 `invalid container name`，这是需要修复的实际调度阻塞；不能据此声称全机持续满载。已授权的队列接续直接按资源所有权和真实收据执行，不需要负责人重复批准。01:03 UTC 新调度代次 `scale4b_dispatch_20261101_v2` 已启动 4B seed2 推理；主会话再次核验容器 `09d92c903752…` 为 running，实际使用芯片 4。修复 `fd27a3e` 及 33 项队列/launcher 测试通过。

真实 Astra 审查已在 `jev_formal_readiness_20261101_v1/review.md` 返回 `CHANGES_REQUIRED`，核对了 10 个文件并提出 F1–F8。现有 `PROCESS.json` 记录请求模型和进程；进程已退出、报告存在，但该代次没有保留 `COMPLETE.json` / `EXIT.json`，因此不能宣称 runner 退出码链完整。

修复状态更正：`efc3e70` 和 `a7f4a76` 只堵住部分反例，**并未完整解决 F1–F5**。恢复源仍需强校验，重建仍需数值与目标绑定，review 仍需验证具体计划，K0 provenance 不能仅靠文件名和额外字段。部分新增测试只是断言常量或重复实现，不能证明生产路径有效，正在替换。`51475db` 已补充完整恢复 Docker 命令匹配、所有保留训练容器的配置检查及正式训练 false scope flags；29 项定向测试通过，仍须独立复审。`dc9b9c9` 将 readiness 改为 QO seed2、PT seeds2/3 分别绑定模型、输入模式、实际计划、强恢复验证、CPU 重建及具体审查文件；14 项生产入口 fixture 测试通过。缺任何目标时保持 WAITING，不授权启动。`26ee084` 已将 K0 消费改为完整来源、分数、六项检查重建，6 项 fixture 测试通过；真实 0.8B K0 v2 生成和消费重建已退出 0：6 项检查、95 项输入，bundle SHA `bf52cbe391b619f6ec5dc1f993ad89a5cf4feb3ebdb1338aa88ac1daf39571eb`，主会话已核对输入/检查哈希无差异。仅为 dev/calibration 工程证据。托管子智能体 `/root/astra_repairs_v2` 已发起审查；两次均仅确认规则，记为 NOT_REVIEWED；01:14 UTC 已在同代次 cli_review/ 下 detached 启动真实 CLI 复审，实际 child PID 2582149 经核实存活，保留 heartbeat 和真实终态 writer。冻结包 25 个文件，manifest `5702e521e94229b191a8ec01a973d81e970b93355f6e685f70c2ddba747bf334`；以上代码尚未取得新 Astra 通过。

## 开发集比较里程碑（2026-11-01 01:16 UTC）

实际开发集比较与输出终态已核对，输入报告哈希一致。K0 为同骨干确定性基础模型；候选使用 seed2/3 等权平均。下表是开发集准确率，不是测试集成绩、真实业务收益或一致性指标。

| 开发集 | n | K0 | K1 均值 | K1 − K0 | 共享 K2 均值 | 共享 K2 − K1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| decision-v7 | 1,264 | 58.3861% | 82.9114% | +24.5253 pp | 83.0696% | +0.1582 pp |
| transfer-v4 | 656 | 60.5183% | 64.1006% | +3.5823 pp | 62.9573% | −1.1433 pp |

K1 相对 K0 的配对 90% bootstrap 区间分别为 [22.1519, 26.9778]、[0.2287, 7.0122] pp，两者下界均大于 0。共享 K2 相对 K1 的区间分别为 [−0.5934, 0.9098]、[−2.5915, 0.2287] pp，未建立优于 K1 的证据，而且 transfer-v4 的点估计退化超过登记的 1.0 pp 界限。不能只挑 decision-v7 的微小正差宣称共享 K2 更优。

两种训练均通过 K-floor；K1 通过开发 K-align，但这些门槛不是正式科学验收。共享 K2 另缺 R0 gating，候选未锁定，同测试集收益未评测。下一步保留 K1 作为开发比较参考，不采用共享 K2 替代，不事后修改阈值；继续已有逐候选 K2、模型规模及控制实验。详细逐 seed、CI 和原始报告路径保存在 `.local/reports/dev-findings-current.md`，结论同步到远程 Wiki。

01:15 UTC 共享巡检：5 个训练容器、3 个推理容器；无失败/停滞告警。逐候选 K2 为 1,194/1,145 步，4B seed3 为 1,313 步；2B K0 29,472/148,542。芯片 4 接续已恢复；一次利用率采样不能证明持续满载。基础 K1 恢复前驱已释放，R0 已接续；新的 CPU 恢复证据核验正在独立推进。

## 当前结论

项目仍处在“参考推理与工程准入收口、正式控制训练尚未开始”的阶段。工程基座训练和推理已经产生进度，但当前没有可发布的训练收益，也没有正式测试集训练前后对比。D1 的 38 个参考单元仍是固定范围；已形成的参考矩阵可以继续作为指标汇报入口，Open-Jev×JEVal 的两个单元仍不能填零，必须保持 blocked/null，直到真实准入和独立计分完成。

NPU 任务正在 detached 队列中运行：最近一次有界巡检（2026-11-01 00:58 UTC）记录 5 个训练容器和 2 个推理容器，无失败或停滞告警。4B K1 seed2 已以 exit code 0 完成，seed3 为 1,153/3,116；逐候选 K2 两个 seed 为 1,169/3,116 和 1,131/3,116。四路 K1 推理和 0.8B K0 均为 148,542/148,542；2B K0 为 26,432/148,542（17.8%，仍带 incomplete receipt 标记）。以上是进度计数，不是测试指标或训练收益。

正式控制 readiness 仍为 `WAITING`：QO 与 PT 证据通过，0.8B K0 报告和旧版预检已完成，但旧消费逻辑存在 Astra F5 缺口，必须通过新验证器或重建后才可用，真实训练终止收据、CPU reconstruction 和新的独立 Astra 审查尚未齐全；`scientific_acceptance=false`、`test_read=false`。不存在手工伪造的 TRAIN_EXIT、CONTRACT_RESULT 或恢复收据。

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
5. 已取得真实 Astra 的负面审查与具体反例，部分修复已提交；完整修复、可信生产路径回归和独立重审仍未完成。不得把曾经通过的测试数当成问题全部关闭。

### 进行中

1. 根据 `CHANGES_REQUIRED` 修复结果生成新的 formal readiness bundle，并等待新一轮真实 Astra CLI 终态。
2. 等待 2B K0、4B seed3 和逐候选 K2 真实退出，随后验证报告、终止收据和资源释放。
3. 对已完成的 NPU 输出执行独立 CPU reconstruction 和计分，再刷新最新参考/训练报告。
4. 准备 formal K1 的精确计划、manifest 和审查材料；正式训练仍受 D1 阶段顺序与 readiness 约束。

## 需要负责人决策的内容

**当前没有必须由负责人追加授权的事项。** 已确认的范围与规则继续执行：38 个参考单元不扩展；暂无算力预算上限；先证明公开任务与 Jev 训练方案，暂不接入真实业务；测试集负责正式指标汇报，开发集用于选择；不同文献统计口径分别报告。

已授权的工程动作由我推进：修复调度、接续 ready 任务、完成 Astra 修复和复审、按 milestone 更新 Wiki、每三天归档本地过程文稿。参考矩阵缺口在证据齐备后增量补充，不需要再次确认。

只有证据导致实质范围变化时再请你决策，例如增加模型或数据集、修改业务目标、改变预注册成功标准，或现有登记方案全部不能支持收益目标。负结果照实报告，不能为得到提升而事后改指标。现有 D5–D6 原建议细节不在本次可核查材料中，不将它们重新解释成新的 seed 或方案授权。

## 下一阶段计划

### M1：收口当前运行与 Astra 审查

- 等待明确完成信号；到下一个共享 600 秒窗口再读一次 bounded digest。
- Astra 已返回 `CHANGES_REQUIRED`；保留旧审查代次，完成 F1–F8 的实质修复及反例测试，随后生成新 bundle。新审查必须重新验证 manifest、代码闭包、exact plan identity 及全部旧反例，不复用旧 verdict。
- K0/训练实际终止后验证 canonical receipt、wrapper EXIT、report SHA、资源释放和恢复链。

### M2：独立重算与最新参考报告

- CPU lane 异步完成恢复重建、开发集计分与候选选择；测试集指标必须等单独测试准入完成后，按冻结公式生成。
- 生成新的增量报告，读数与既有快照一致时保留原值；旧过程文稿进入本地 archive，远程 wiki 只更新最新结论。
- 在两个 Open-Jev×JEVal 单元完成真实准入前继续保留 `blocked/null`。

### M2.5：恢复满载和 successor 调度

- 只读取受影响队列的 bounded digest 和芯片分配文件，定位芯片 4 的前驱/后继依赖及容器命名错误。
- 先修复阻断接续的容器名校验问题；核实旧控制器没有启动 worker 后部署新冻结代次。资源释放后接续已准备任务，不重复启动已有 generation。
- 保持每个任务 detached、可恢复、带 heartbeat、terminal marker 和 relaunch 命令；不通过手工标记完成来填补队列。

### M3：继续现有工程训练并完成正式准入

- 继续已经启动的工程训练和同骨干 K0 推理，完成剩余 2B/4B/9B、逐候选 K2 及控制实验。正式代次需要新计划和新审查，不能重标工程结果；K0 和候选 NPU 任务按依赖并行，比较必须等待同口径结果齐备。
- NPU 队列保持持续消费；CPU 同步处理 dev 评分、收据核验和候选选择。候选选择只能看 dev，不能提前读取候选 test 收益。
- 每芯片记录吞吐、reserved/allocated/峰值显存、heartbeat、恢复点和资源释放证据。

### M4：测试集汇报与后续学习方法

- 只有候选锁定、seed/来源/终态/独立计分和 Astra 范围审查完整后，才读取并发布一次候选测试集结果。
- 在 K0/K1 基线稳定后，逐项加入 option-restricted loss、proper scoring、校准、蒸馏和优化方法；RL 需等可审计业务缺口任务和可用基线完成后再登记。
- 每个 milestone 完成后刷新最新报告，维持可追溯的旧归档。

## 当前出口条件

进入正式训练收益判断前必须同时满足：参考报告能解释全部 38 个登记组合的状态；K0 测试读数已由独立计分确认；每个控制臂的 formal readiness 和计划准入均通过；真实恢复/终止收据完整；精确训练计划有独立 Astra 结论；候选测试集仍处于锁定状态直到选择完成。满足后才讨论“是否观察到 Jev 收益”，并将结果限定为公开任务收益，不写成真实业务收益。

证据入口：

- `experiments/REFERENCE-BASELINE-LATEST.md`
- `experiments/REFERENCE-BASELINE-MATRIX-2026-10-31.json`
- `/mnt/cephfs/xingchao/experiments/jev/r3_runs/formal_control_readiness_20261101_v2.json`
- `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jev_formal_readiness_20261101_v1/`
- `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jev_formal_readiness_20261101_v1/review.md`（`CHANGES_REQUIRED`，不可作为准入通过）
- `.local/NPU-MONITORING.json`
