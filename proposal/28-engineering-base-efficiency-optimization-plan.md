# 工程基座效率优化计划（增量报告）

更新：2026-11-06。当前结论是：工程基座仍处于 `HOLD`，新研究实验不启动；已经存在的实验保持原镜像、原配置和原输出目录。只有新基座完成资格、独立审查和替换演练后，才停止旧实验并迁移。

## 当前状态

当前审查材料没有可用于资源分配的实时 NPU 占用、吞吐或 AI Core 利用率证据，不据此判断主机空闲。监控目录的一次 watchdog 摘要为 418 个记录：26 failed、34 stalled、27 unknown、1 running、276 done、54 archived。这是监控目录统计，不能直接当作主机利用率；历史 stalled/unknown 也不能被调度器当作可复用资源。

已交付的两个基座通道：

- 诊断控制器安装资格 v14b：已交付，但未通过完整资格。full3 的 46,320 条路径出现 `ValueError: parity mismatch`；controller exit 1，child exit 137 是验证失败后的清理终止，评分子进程 exit 0，不能解释成评分 OOM。full4 controller/child exit 0，但它将预期 summary hash 改成了 full3 实测值，因此只证明改配置后执行成功，不能证明冻结 parity 修复。
- 服务契约公共集成 v17：已完成，`EXIT.json` 为 0。原生桥接回归 6/6 通过；训练集成在依赖完整的本地 CPU 虚拟环境中 5/5 通过，但不是 Docker/NPU 资格。源预测/导出预测/contract 精确相等，输入变化和损坏身份会被拒绝。

已证实的效率数据来自 Sol 的固定负载分析：统一基座 v1–v6 交付窗口 8,658.29 秒；8 个同主机 CPU 交接间隔合计 1,912.92 秒，中位数 243.17 秒，范围 82.02–586.70 秒；必经权重校验至少读取 260.73 GB 逻辑输入；46,320 条评分的记录阶段约占插桩调用 87.6%，历史评分耗时 88.46–307.86 秒；65 条显式依赖边等待中位 16.48 秒、p95 36.46 秒、最大 108.64 秒。

尚未测得权重哈希的物理 Ceph 流量、真实 JSON/fsync 成本、AI Core 利用率、NPU 吞吐和分块评分恢复收益。因此以下改动先作为工程假设，不能提前写成加速结论。

## 瓶颈诊断与优先级

| 优先级 | 瓶颈 | 证据 | 处理方式 | 放行条件 |
|---|---|---|---|---|
| P0 | 交接和终态碎片化 | CPU 交接中位 243.17 秒；大量目录只有 heartbeat 或不完整 marker | 以事件驱动 CPU 交接，600 秒轮询只作漏事件兜底；每阶段固定 `EXIT/TERMINAL/RELEASE` 和可重放 relaunch | 20 次故障/恢复事务，零重复派发、零丢失租约 |
| P0 | 诊断资格不完整 | full3 元数据不一致；full4 使用事后观察到的期望 hash；准入混淆 controller/child ID | 修复身份校验；单列显式 schema 兼容协议，保留原冻结失败；补齐故障矩阵 | 独立审查通过；模拟与安装证据分列，未执行项记 NOT_RUN |
| P0 | 服务契约身份传播 | v16 快照曾把 native 当 trained；v17 原生 6/6 修复 | 保留本地 native 6/6、trained 5/5 回归凭据；镜像闭包和安装资格另验 | native/trained focused tests 均通过，contract identity 字节一致 |
| P1 | 重复权重哈希 | 逻辑输入至少 260.73 GB | 对每个不可变模型代次缓存一次可信 hash；变更、缺失或身份不确定时强制重验 | 每代最多一次完整 hash，warm admission p95 ≤5 秒 |
| P1 | 评分记录和小文件开销 | 记录阶段占插桩调用 87.6%；小文件数量大 | 在身份绑定下做二进制/分块持久化，保持逐位一致和原摘要 hash；先做 matched benchmark | 46,320 条汇总 hash 不变；恢复最多重做 100 条 |
| P1 | 监控噪声 | 34 stalled、27 unknown、历史目录多 | watchdog 只读日志、心跳、marker、report；智能体只读 digest；事件触发，10 分钟轮巡兜底 | digest 可解释，历史目录不参与新资源判定 |
| P2 | NPU 真实性能 | 当前无实时资源分配证据；暂无 AI Core/吞吐资格 | 基座 G1–G3 通过后，再做真实模型/真实 NPU 有界资格；不以 CPU fixture 推断 | 每芯片吞吐、保留内存、设备映射和恢复数值证据齐全 |

## 下一阶段执行图

CPU 侧工作与 NPU 队列保持异步，但在当前基座 HOLD 期间只运行资格和效率验证，不派发新的科学研究：

1. v14b 已交付；Terra 在独立候选目录修复身份准入，并建立显式 schema 兼容校验，Astra 独立评审 full3/full4 的证据边界。原历史 summary hash 不变，不能以候选输出回填期望值。
2. v17 已在本地 CPU 环境通过两类回归，命令、源码哈希与终态已存于 `.local/preparations/v17-cpu-receipt-20261106-v1/{RESULT.json,SOURCES.json,EXIT.json}`；trained 命令使用 `.local/venvs/trained-eval-component/bin/python -B -P -m unittest discover -s docker/engineering-base -p test_trained_integration.py -v`。该 receipt 不替代安装后的镜像资格，禁止复制 replay shim。
3. 接入阶段计时、memory.stat、线程池、IO 和事件时间戳，覆盖至少 99% 的 CPU 资格阶段；计时必须带 boot/monotonic identity。
4. 做四个 matched benchmark：事件交接、哈希冷/热路径、二进制持久化、评分分块恢复。每次只改变一个因素，固定数据、指标、阈值、并发和主机。
5. 完成 G1（测量）→G2（正确性）→G3（20 次故障恢复）→G4（真实设备资格）。每一个 hash、事件、持久化或分块评分改动都必须逐项证明输入总体、split、顺序、阈值、算术/容差、typed decision、逐条 prediction、汇总字段和 decision-level paired metric 不变；仅 summary hash 不足以证明分块或重排实现等价。事件验收还必须覆盖丢失、重复、延迟事件，证明只派发一次、只释放一次，且 600 秒轮询是恢复路径而不是正常路径。任一证据绑定、数值、恢复或资源租约失败，继续保留旧路径。
6. G1–G3 和 Astra 复核通过后，仍不得迁移研究任务。必须先完成 G4 真实设备/真实模型资格，包括实际设备映射、每芯片吞吐、保留内存、数值恢复和完整报告；只有 G4 及独立发布审查通过后，才停止旧实验。迁移必须在持久化 checkpoint 或 item 边界完成，然后替换镜像和配置，重新排队研究任务。

## 暂不需要用户决策的事项

当前已有决策足够执行：取消算力预算约束；真实业务收益暂不作为第一阶段放行条件；评测主要汇报测试集；配置文件是唯一输入；监控采用脚本和约 600 秒兜底轮询；LoRA 小模型暂不扩展多卡训练。27B 仅保留候选，不抢占小于 10B 主线。

真实设备资格属于已授权工程范围：CPU 前置条件通过后，以独立有界配置执行 G4，不要求 G4 在其自身执行前通过。研究迁移/派发须等 G4 和发布审查通过。27B 保留原预算，当前不改变小于 10B 的目标范围；兼容现有结果读取协议。

## 事实边界

CPU fixture 通过、镜像构建成功、watchdog 心跳和单次 `npu-smi` 快照都不能证明真实 NPU 科学结果。所有实验指标仍必须从测试集、预注册统计口径和自身 report 文件产生；工程效率优化不能改变数据集、拆分、阈值、指标定义或历史结果。

## 本轮证据与明确限制

v14 交付位于 `.local/preparations/engineering-diagnostic-installed-qualification-20261106-v14/`，full3/full4 的配置和终态位于 `/mnt/cephfs/xingchao/experiments/jev/engineering-diagnostic-installed-qualification-20261106-v14/`。full3 历史预期 summary 为 `b345c196…`，实际为 `2994474a…`，有六项 schema/来源元数据差异；数值 payload 和有序收据一致。full4 使用后一个 hash，不能作为原协议修复的证明。这里的 2B 保存记录为 26,782/46,320，与 Wiki 中 9B 的 30,465/46,320 属于不同模型，不得混用。

矩阵标签需要纠正：full3 是意外正向失败，不是预注册的故障注入；原准入 ID 错配的拒绝不是 partial receipt 注入；full4 新配置成功不是 finalization interruption/retry。原交付保留不改，这些项尚待有针对性的故障测试。可安全使用隔离 Docker 客户端/子进程 fault harness，但模拟证据不能冒充实际安装故障，不能中断共享 daemon 来补证据。

Astra v3 把 full3 controller exit 写作 137，应更正为 controller 1、child 137、scorer 0。Sol 诊断的 phase_count 写作 8，明细实际为 7；由后续分析追加更正，不静默重写历史审查。

流式 hash 改动由 Astra v2 限定接受，完整 CPU 流水线命名空间回归通过；它保留全部字节校验，未实现 hash 缓存。128MiB 本地单次微测仅支持峰值 RSS 降低，不支持端到端吞吐或 Ceph 流量收益。


## 按变更固化的验收凭据

每项优化都应交付机器可读 receipt，而不是仅写“通过”：

- 数值不变凭据：baseline/candidate 源码与镜像、配置、数据总体与 split、样本顺序、模型/contract、阈值、逐条 prediction 与 typed decision 的有序 hash、summary 全字段和 paired metric。记录比较方法、差异字段、执行命令和 exit；缺失项不能默认通过。显式 schema 迁移单独声明，不能声称旧摘要逐字节一致。
- 事件凭据：事务/event/lease ID，注入故障、接收/派发/释放/fallback 次数，单调时钟及 boot identity、ready/dispatch/release 时间与事前目标。目标正常交接 p95≤5 秒、就绪派发 p95≤10 秒；20 次故障恢复零重复派发、零丢失租约；600 秒 fallback 只用于丢失事件恢复。
- 性能凭据：相同输入/主机/容器配额/线程库设置，交替重复对照，wall/CPU/RSS、冷暖缓存条件和并发情况。现有 full3 88.15 秒与 full4 76.04 秒并非 matched benchmark，不能据此宣称提速。

`d1fa563` 同时包含流式 hash 和 `after_export_config` 测试 hook；后者不是此前提交已有改动，且不在 Astra 的 hash-only 验收范围内。不要把同一提交中的所有内容都视为被限定验收。

当前三个 Codex 子进程输出分别为 `.local/preparations/engineering-parity-repair-20261106-v15/`、`.local/reviews/engineering-efficiency-matched-sol-20261106-v3/` 和 `.local/reviews/engineering-v14-astra-review-20261106-v4/`。工程修复、固定负载分析与独立审查并行；输入与输出文件隔离。下一次更新在它们交付可复核里程碑后进行。
