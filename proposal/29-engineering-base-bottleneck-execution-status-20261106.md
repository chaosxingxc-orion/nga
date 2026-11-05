# 工程基座瓶颈执行状态与优化计划

更新时间：2026-11-06。研究实验继续 HOLD；已运行任务保持原镜像和原配置。只有新基座通过资格、独立审查和迁移演练后才切换。

## 当前进度

| 工作项 | 状态 | 证据边界 |
|---|---|---|
| 公共 CPU 服务契约 | 有限 CPU 集成完成 | v17 native 6/6、trained 5/5；不是 Docker/NPU 资格 |
| 保存结果复算 | 可运行 | 46,320 条保存结果的预测、收据和数值摘要一致；不是新推理收益 |
| 流式 SHA-256 | 候选改动通过限定测试 | 1 MiB 读取保持 hash 一致；128 MiB 本地微测 RSS 约 146 MiB→20 MiB；无端到端提速结论 |
| 安装诊断资格 | 未通过 | full3 controller exit 1，child exit 137 为失败后的清理终止；首错 `ValueError: parity mismatch`；评分子进程 exit 0，失败归档保留 |
| full4 | 仅改配置执行成功 | 预期摘要 hash 被改为 full3 实际 hash `299447…`，不构成冻结 parity 修复或 finalization recovery 证据 |
| Terra 候选 | v15 被 Astra 拒绝，v16 控制器候选隔离测试通过 | v15 14/14 仅 CPU/模拟；Astra 发现结果 hash 抄写错误、finalization 自调用假测试、输入 lineage 缺失、源码信任可被调用者重绑、OOM 等状态未完整绑定。v16 6/6 将兼容协议接入控制器候选，默认仍冻结 parity；未重建镜像、未改生产源码。|
| Sol 配对效率测量 | 候选拒绝 | 24 个 CPU fixture 试验保持共同 prediction/receipt digest；读 ahead/并行候选在全部 worker 数下均未快于参考 |
| NPU/真实设备 | 尚未资格化 | 没有设备映射、每芯片吞吐、内存和恢复证据；不据此判断主机空闲 |

## 效率瓶颈

1. CPU 交接历史为 82.02–586.70 秒，中位 243.17 秒；事件触发尚未有安装后 20 次 exactly-once 证据。
2. 评分记录阶段约占插桩调用 87.6%；旧 profile 的重复 record/commit 读取已由当前 loader 改为各读一次；当前仍包含 JSON 解析、hash、来源路径验证及数值校验，需重新拆分热点。worker wall 时间有重叠，不能直接解释为 I/O 或 GIL。
3. 权重和输入校验累计至少读取 260.73 GB 逻辑数据；逻辑读取量不等于 Ceph 物理流量，可信不可变代次缓存尚未实现。
4. 最新评分比较比值 1.1012367395，超过事前 1.10 门槛；只能判定性能未通过，不能归因到单一原因。需要 matched benchmark 分离内存、文件访问、线程池和缓存影响。
5. Sol 的 1,024 条固定样本 benchmark 中，候选相对参考 wall 中位数：1 worker +11.85%，2 worker +5.78%，4 worker +1.96%，8 worker +2.47%；因此不接入候选路径。
6. watchdog 历史摘要有 34 stalled、27 unknown；这是目录统计，不是主机利用率。监控由脚本读取心跳、日志、终态和 report，事件优先，约 600 秒轮询仅作漏事件恢复。

## 复核后的当前阻塞

- v15 admission 候选不能接受：Astra 的独立反例证明输入树、可信源码身份和完整 child 生命周期状态仍未锁定。v17 正在隔离目录修复这些问题；安装证据仍未运行。
- v16 controller 候选已把兼容协议接入控制器，但生产镜像仍包含旧控制器，且生产 admission 尚不识别 `COMPATIBILITY.json`；必须配套镜像构建、准入器变更和独立审查。
- “finalization interruption” 目前只有 mock primitive 证据，不能算控制器恢复。

## 优化顺序

### P0：先修正验收真实性

保留 full3 的历史失败，不把 full4 的事后 hash 替换当作 parity 修复。Terra 候选固定历史输入、模型、计划和收据，逐项核验科学 payload、样本数、顺序、typed decision、逐条预测和汇总数值；元数据只允许在预先命名并 pin 的 schema 兼容表内变化。准入校验必须比较正确的 terminal child id 与 controller id，并拒绝错误身份、缺失 inventory、路径逃逸、软链接和不完整收据。fault harness 只能标为模拟边界，不能冒充安装后故障。

### P1：降低评分 CPU/文件开销

不采用本轮读 ahead/并行候选。下一步先做可信不可变模型代次 hash 的 cold/warm 测量，缓存必须绑定 model manifest、文件树、配置和来源身份；身份缺失或变化时强制冷校验。然后根据当前 loader 的分项测量设计单因素候选，每项都用固定输入、交替重复、逐条 prediction 与 receipt 顺序核验。

### P1：缩短 CPU 交接并保持 NPU 异步

事件接收、租约、派发、释放和 fallback 写结构化 receipt，包含 event/lease id、计数和边界时间。用 20 次故障恢复事务验证丢失、重复、延迟事件只派发一次、只释放一次；600 秒轮询只作兜底。CPU 分析与 NPU 队列异步，不因分析暂停现有任务。

### P2：真实设备资格

G1 测量、G2 正确性、G3 故障恢复通过并经 Astra 复核后执行有界 G4：真实镜像、真实模型、设备映射、每芯片吞吐、保留内存、checkpoint/item 边界恢复。G4 和独立发布审查通过后，才按持久化边界停止旧实验并替换基座。

## 当前决策

暂无新的阻塞性决策。既有约束继续有效：取消算力预算；业务收益不作为第一阶段放行条件；测试集为主要汇报口径；配置文件为唯一实验输入；脚本监控并约 600 秒兜底；LoRA 小模型暂不扩展多卡；27B 保留候选，不改变当前小于 10B 基座资格范围。

用户已授权在新基座优化并通过资格后切换旧实验；届时按 checkpoint/item 边界迁移，无需重复请求许可。当前尚未满足切换条件。

## 并行执行输出

- Terra：`.local/preparations/engineering-parity-repair-20261106-v15/`
- Sol：`.local/reviews/engineering-efficiency-matched-sol-20261106-v3/`
- Astra：`.local/reviews/engineering-v14-astra-review-20261106-v4/`；v15 admission 专项：`.local/reviews/engineering-v15-admission-astra-20261106-v1/`

每个输出包含可读 HANDOFF/RESULT、命令、源码/证据 SHA-256 和失败项。主会话只读取摘要及有界证据片段，不直接读取原始长日志。

## 2026-11-06 核验更正

上一版将最终配对测量误写为 4,096 条；终态、sample-before/after 和 24 个 trial 的权威样本数均为 1,024。百分比读数不变。Terra v15 的 14 项 CPU 测试通过不等于故障恢复成立：finalization 用例只直接调用模拟的 rename，没有驱动控制器恢复；该项不得标为恢复 PASS。v15 的 controller diff 为空，兼容协议尚未接入控制器，交由 v16 集成并专项审查。所有这些工作都不构成安装资格或研究放行。
