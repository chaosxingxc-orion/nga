# 工程基座瓶颈执行状态与优化计划

更新时间：2026-11-05 22:02 UTC（沿用既有文件名）。研究实验继续 HOLD；已运行任务保持原镜像和原配置。只有新基座通过资格、独立审查和迁移演练后才切换。

本轮执行原则是先把工程基座的功能、可靠性和效率收敛，再迁移实验。当前运行中的实验不停止；新的研究任务不因设备空闲而追加。CPU 分析、审查和修复继续异步推进，不能占用已运行任务的设备生命周期。

## 当前进度

| 工作项 | 状态 | 证据边界 |
|---|---|---|
| 公共 CPU 服务契约 | 有限 CPU 集成完成 | v17 native 6/6、trained 5/5；不是 Docker/NPU 资格 |
| 保存结果复算 | 可运行 | 46,320 条保存结果的预测、收据和数值摘要一致；不是新推理收益 |
| 流式 SHA-256 | 候选改动通过限定测试 | 1 MiB 读取保持 hash 一致；128 MiB 本地微测 RSS 约 146 MiB→20 MiB；无端到端提速结论 |
| 安装诊断资格 | 未通过 | full3 controller exit 1，child exit 137 为失败后的清理终止；首错 `ValueError: parity mismatch`；评分子进程 exit 0，失败归档保留 |
| full4 | 仅改配置执行成功 | 预期摘要 hash 被改为 full3 实际 hash `299447…`，不构成冻结 parity 修复或 finalization recovery 证据 |
| Terra 候选 | v15 被 Astra 拒绝；v18 focused integration 3/3 通过，但 Astra 独立审查 NO-GO | Astra 复现 policy self-pin 不一致、悬空 `INCOMPLETE.json` 被忽略、summary/receipt pins 未独立核验、外部 trust root 占位；v18 仍未安装、未重建镜像、未改生产源码。|
| Sol 配对效率测量 | 候选拒绝 | 24 个 CPU fixture 试验保持共同 prediction/receipt digest；读 ahead/并行候选在全部 worker 数下均未快于参考 |
| CPU 配置化启动器 | 有界 smoke 通过 | 本地主机 Docker smoke 的两个保留容器均 exit 0，输出位于本地工作区（非175/Ceph输出资格）；确认 pinned image、9009:9009、只读输入、可写输出、network=none、资源上限、持久日志和 EXIT.json。仅为启动器操作证据，不是语义、性能或 NPU 资格 |
| NPU/真实设备 | 尚未资格化 | 没有设备映射、每芯片吞吐、内存和恢复证据；不据此判断主机空闲 |

## 效率瓶颈

1. CPU 交接历史为 82.02–586.70 秒，中位 243.17 秒；事件触发尚未有安装后 20 次 exactly-once 证据。这个等待区间与评分耗时同量级，应优先做事件、租约和释放路径的独立测量。
2. 评分记录阶段约占插桩调用 87.6%；旧 profile 的重复 record/commit 读取已由当前 loader 改为各读一次；当前仍包含 JSON 解析、hash、来源路径验证及数值校验，需重新拆分热点。worker wall 时间有重叠，不能直接解释为 I/O 或 GIL。
3. 权重和输入校验累计至少读取 260.73 GB 逻辑数据；逻辑读取量不等于 Ceph 物理流量，可信不可变代次缓存尚未实现。
4. 最新评分比较比值 1.1012367395，超过事前 1.10 门槛；只能判定性能未通过，不能归因到单一原因。需要 matched benchmark 分离内存、文件访问、线程池和缓存影响。
5. Sol 的 1,024 条固定样本 benchmark 中，候选相对参考 wall 中位数：1 worker +11.85%，2 worker +5.78%，4 worker +1.96%，8 worker +2.47%；因此不接入候选路径。
6. watchdog 历史摘要有 34 stalled、27 unknown；这是目录统计，不是主机利用率。监控由脚本读取心跳、日志、终态和 report，事件优先，约 600 秒轮询仅作漏事件恢复。

## 本轮执行效率判断

以下为工程处理优先级；返工、等待和评分来自不同测量窗口，不能相加或据此认定总耗时排名：

1. **接口和验收返工风险**。v18 开发中曾有 schema/metadata 接口错误，当前已修复且主会话复跑 3/3 通过。其用例调用 `controller.main()`，Docker 依赖仍为模拟。返工总时长尚未量化；优先级高是因为安装验证依赖正确的控制路径，不能据此声称它占用时间最多。
2. **前置核验和交接等待**。前置核验代理区间约 11.35 分钟，评分六轮约 12.23 分钟；历史交接中位数约 243 秒。若只优化评分函数，端到端收益会被前置和等待抵消。应先把阶段时间拆成准备、准入、设备运行、持久化、CPU评分和结果交付，并让 CPU 交接不持有设备租约。
3. **评分阶段的文件和校验成本**。固定 1,024 条样本的插桩计时显示 JSON 序列化、路径检查、有限值检查和类型转换都占用明显 CPU；当前每条记录和提交文件各读一次，已经关闭了旧的重复读取问题。下一步只能在可信不可变身份下做 warm/cold 对照，不能通过删校验换速度。
4. **内存压力和文件系统行为未分离**。前四轮 cgroup 计费接近 12 GiB 上限，后两轮约 0.80 GiB；原因尚未归因到 Python 对象、文件缓存、线程池或 Ceph。必须记录 `memory.stat`、回收计数、线程数和文件阶段，再做单因素优化。
5. **监控和历史目录噪声**。digest 中的 stalled/unknown 多为历史目录状态，不能直接当作当前 NPU 空闲或繁忙。脚本应以事件为主、600 秒兜底，输出 bounded digest；主智能体不读原始长日志。

因此本阶段的效率目标不是追求一个局部 micro-benchmark 的最好数字，而是把“从任务就绪到可验证结果”的时间拆开并减少无效等待：功能接口先稳定，随后只保留能够通过数值等价门禁的单因素候选。

## 复核后的当前阻塞

- v15 admission 候选不能接受：Astra 的独立反例证明输入树、可信源码身份和完整 child 生命周期状态仍未锁定。v17 最终为 17 项测试（16 通过、1 项 finalization 恢复跳过）；Astra 给出限定候选 GO，但要求修复悬空 sentinel、生成器自检、直接摘要/收据校验，并冻结源码后复验。安装资格未通过。
- v16 controller 候选已把兼容协议接入控制器，但生产镜像仍包含旧控制器，且生产 admission 尚不识别 `COMPATIBILITY.json`；必须配套镜像构建、准入器变更和独立审查。
- v18 已补 controller main 路径的模拟 Docker 故障测试；当前证明的是故障拒绝和证据保留，不是安装后的成功断点续跑。原 v15 直接 mock rename 的证据仍不算恢复。Astra v2 另外确认 self-pin、dangling sentinel、独立摘要/收据校验和外部 trust root 均未达标。
- CPU launcher 的本地主机 smoke 不能证明175/Ceph输出；Astra 发现 launcher 未限制 durable output root。

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

## 当前路径分项测量与下一项优化

Sol v4 在本地主机、固定 1,024 条保存记录上完成分项计时。每条 record/commit 各读一次，共 2,048 次逻辑打开、2,048 次读取，1,150,635 字节。单线程插桩 CPU 分项：canonical JSON 序列化 0.4000 秒、native_read_logits 扣除嵌套项后 0.2806 秒、路径检查 0.2595 秒、isfinite 0.2518 秒、float64 转换 0.1914 秒、float32 转换 0.1025 秒。这里是插桩 CPU 归因，不是 175 的生产耗时比例；四线程插桩将 wall 中位数从 1.4822 秒扰动到 2.1088 秒，不能用插桩结果宣称提速。

已验证并拒绝的候选是 `z.astype(np.float32, copy=False)`（终态见下文），原设计保留全部有限值检查、float64 算术和决策协议。在独立目录测试 dtype、只读/非连续数组、极值、NaN/Inf、别名和输入不变性，然后在 175 CPU 容器做 6 对 AB/BA 比较。事前目标为配对 wall 比值中位数≤0.98、CPU≤1.0、RSS≤1.05，且所有有序 prediction/receipt 一致；不达标则不采用，不事后调整门槛。

已结束交付：`.local/preparations/engineering-copy-elision-terra-20261106-v1/`；已结束 v17 独立审查：`.local/reviews/engineering-admission-v17-astra-review-20261106-v1/`。两项均不授予整个基座发布资格。

## copy=False 候选终态

`z.astype(np.float32, copy=False)` 在等价性门禁中被拒绝，未进入 175 benchmark。普通 dtype、非连续数组、只读视图、极值、NaN/Inf 和输入字节保持测试通过，但并发 alias 场景出现 baseline/candidate 决策差异；根据预注册的“aliasing observable behavior=reject”规则，结果为 `REJECTED_PRE_BENCHMARK`。175 上的容器启动还暴露出两个启动器缺陷：Ceph 输出目录属主 `9009:9009` 且 `0700` 导致容器无法遍历，重试脚本曾硬编码旧输出目录。没有产生性能数据，也没有改生产 runtime。


## 当前实现工作与收敛条件

1. v18 将控制器、兼容凭据、准入器和配置生成器集成为一条可测试路径，当前 focused integration 3/3 通过，已从 controller main 进入发布前/后故障测试。仍需独立审查并完成安装后验证；不能用直接调用 mock rename 代替恢复验证。异常输出要保留，重复启动不得重复创建 child。兼容迁移的科学不变检查不允许被单纯回填候选 hash 替代。
2. 可复用 CPU 资格启动器固化镜像 digest、UID/GID、只读输入、输出目录和 argv，先在真实运行用户下检查输入可读/输出可写，再 detached 启动；日志由容器内部直接落 Ceph，失败与成功都写终态。当前旧启动脚本没有通过该契约，不能当作稳定基座继续复用。
3. 上述功能通过后，才进入隔离安装资格与候选效率测量；测试夹具和启动器 smoke 通过仍不代表 Docker/NPU 发布。

目录：`.local/preparations/engineering-controller-admission-integrated-20261106-v18/` 与 `.local/preparations/engineering-cpu-preflight-launcher-20261106-v1/`。v18 当前候选测试已结束；启动器 smoke 已结束。后续以冻结后的终态、测试凭据与独立审查为准。

## 下一阶段计划和完成条件

按依赖顺序执行，但 CPU 分析与仍在运行的实验保持异步：

1. **接口收敛**：当前 schema 差异已修复且集成测试 3/3 通过；冻结候选，核验 config、summary、receipt 和 pins；测试 receipt 必须由实际测试结果生成，summary/receipt hash 必须独立直接复核。完成条件是 focused integration 全通过，且没有 dangling `INCOMPLETE.json`、路径逃逸或可重绑定 trust root。
2. **故障恢复闭环**：从 controller main 进入发布前中断、发布后中断、重复启动、staging 保留和恢复；保留失败证据。完成条件是失败不会被准入为成功，重启不会重复创建 child，终态和 committed inventory 一致。
3. **CPU 端到端测量**：使用配置化启动器在固定输入上分别测 cold/warm 校验、JSON/数值校验、线程池和 cgroup memory.stat；每次只改变一个因素，保持 prediction、receipt、顺序和样本数不变。完成条件是得到可复现的阶段时间和明确的采用/拒绝结论。
4. **有限安装资格**：重建候选镜像并执行 CPU 安装资格；核对 UID/GID、输入只读、输出写入、日志、EXIT、重试路径和容器资源。完成条件是资格证据完整且经独立 Astra 审查。
5. **真实设备资格**：只在前四步通过后执行有界 G4，记录真实设备映射、每芯片吞吐、保留内存、checkpoint/item 恢复；不把历史容器状态或 CPU smoke 当作 NPU 证据。
6. **迁移**：G4 和发布审查通过后，才按 checkpoint/item 边界停止旧实验、替换工程基座并恢复研究队列；迁移前不修改旧实验的镜像、配置和输出。

## Astra v2 独立复核结论

`.local/reviews/engineering-v18-launcher-astra-review-20261106-v2/` 给出 `NO_GO_CANDIDATE_ONLY_ENGINEERING_HOLD`。v18 focused 3/3、launcher 9/9 和源码 pins 均通过，但不覆盖真实准入资格。Astra 的 V18-01/V18-04 为阻塞项，V18-02/V18-03 为高风险项，LCH-01 为启动器高风险项；安装、性能、NPU 和研究派发均未运行。

## 本轮核验更正与当前接续

2026-11-05 UTC：此前把开发中 schema 报错误标为最新失败，现以终态和主会话 3/3 复跑更正。启动器 9/9 复跑通过，但 smoke 的输出目录在本地工作区，不能认定175或Ceph输出通过。Astra独立审查和Sol下一轮效率方案已以Codex子进程启动；分别输出 `.local/reviews/engineering-v18-launcher-astra-review-20261106-v2/` 和 `.local/reviews/engineering-efficiency-next-sol-20261106-v2/`。未启动新研究任务，未停止旧实验。
