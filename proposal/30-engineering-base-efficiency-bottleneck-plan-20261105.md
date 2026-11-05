# 工程基座效率瓶颈分析与优化计划

更新时间：2026-11-05 UTC。研究实验仍处于 HOLD；已运行容器和其镜像、配置、输出不修改。本文只记录工程基座的效率收敛，不把 CPU fixture 或历史评分结果写成 NPU 性能结论。

## 当前结论

目前最耗时的可测阶段是保存结果消费。旧的 175 实测阶段剖析中，`records` 占插桩调用 101.708403/116.085555 秒，约 87.615%。这只是阶段占比，四个 worker 的读/hash 计时存在重叠，插桩本身会扰动时序，因此还不能断言瓶颈是 Ceph、JSON、Python 校验、数值重建或调度中的某一项。

端到端交付还有三类更容易被重复放大的成本：前置核验与准入准备约 11.35 分钟，六轮旧评分序列约 12.23 分钟，CPU 交接历史中位数约 243.17 秒（范围 82.02–586.70 秒）。这些数字来自不同测量窗口，不能相加或排序成完整事务耗时，但说明仅做一个数组转换优化不会解决整体效率问题。

当前实际代码已加入显式阶段遥测和低频资源采样：七个评分阶段各写 start/end，记录 cgroup、memory.stat、memory.events、CPU/IO pressure、线程池和进程 RSS；事件服务在初始尝试后以 600 秒作为兜底轮巡。正常运行不读取原始长日志，状态由 watchdog digest、终态 marker 和结构化 receipt 汇总。CPU 与仍在运行的设备任务保持异步。

## 已验证和已拒绝的优化

1. 读 ahead 在 1/2/4/8 worker 上全部慢于参考（wall 比值 1.118528、1.057798、1.019607、1.024700），不采用。
2. `copy=False` 候选在并发 alias 场景造成决策差异，按预注册等价性规则在性能测试前拒绝，不恢复该改法。
3. full-label float64 cast 是目前唯一保留的单因素候选：保留完整 finite 检查和 float32 输入副本，只在 full-label 分支避免把完整词表先扩大为 float64；top20 路径和所有收据、顺序、汇总逻辑不变。候选仍需固定快照、功能门禁和 actual175 CPU A/B，尚未成为基座。
4. 事件服务和诊断评分的回归测试已通过：事件/恢复相关测试 34/34，panel/诊断相关测试 34/34；这些是 CPU 功能证据，不是 Docker、Ceph 或 NPU 资格。

## 瓶颈优先级

### P0：减少无效返工和准入等待

先冻结“一个完整事务”的输入、源码、镜像、配置、收据和终态。准入器必须从实际有序 receipt 源重新计算摘要，拒绝悬空 `INCOMPLETE`、路径逃逸、身份错误和可重绑定的占位 trust root。没有冻结证据时重复跑评分只会增加成本，不会增加可用结论。

### P1：把交接和设备租约从 CPU 分析中解耦

NPU/设备队列保持 detached、连续消费；CPU 只消费结构化事件。事件接收、租约、派发、释放和 fallback 都写 event id、lease id、计数和边界时间。用有限的 20 次故障恢复事务验证丢失、重复、延迟事件只派发一次和只释放一次。600 秒轮巡只负责漏事件恢复，不能成为常规等待路径。

### P1：拆分评分阶段并做一次性可信复用

下一次 actual175 CPU 测量必须同时记录 source admission、population validation、records、post-record validation、aggregation、summary/report、terminal publication，并覆盖从 scorer spawn 到 durable terminal 的父进程区间。模型代次、输入树、配置和源码身份完全匹配时，才允许使用已认证不可变缓存；身份缺失或变化必须回到完整校验。禁止通过删校验或复用旧 summary 换取速度。

### P2：只做有等价性门禁的局部算术优化

对 full-label cast 候选执行预注册 ABBA/BAAB 八次 actual175 CPU 测量，固定 2B、46,320 条记录、4 workers、chunk 100 和线程池上限。必须满足预测、ordered receipt、summary bytes 完全一致，且候选/参考主 wall 中位数不高于 0.98；高于 1.10 或资源证据不完整立即拒绝。没有完整 cgroup/终态证据时只保留数据，不发布性能结论。

## 175 当前状态和边界

本次只读检查确认主机 `k8s-node1`、`/mnt/cephfs` 为 Ceph，诊断镜像已存在；现有 CPU 容器仍在运行。`npu-smi` 显示 8 张 910B3 健康，但没有 NPU 运行进程。这个观察不授权停止现有容器，也不等同于主机长期空闲判断；新研究任务继续 HOLD，待基座通过审查和资格后再恢复。

## 下一阶段顺序

1. 等待 Terra v19 生成全新冻结准入包；只读取其终态、`FROZEN.json` 和有界 handoff，不能把开发中目录当证据。
2. 等待 Astra 对固定 launcher/cast 快照的独立结论；若仅批准 CPU smoke，则使用真实 175、Ceph 输出、固定镜像和 UID 9009 做 detached smoke，不映射设备。
3. 修正并冻结 actual175 benchmark driver、资源采样和结果摘要；先做功能 preflight，再做八次 A/B，保持旧候选和失败证据可追溯。
4. 只有功能、恢复、CPU 安装资格和独立审查都通过，才按 checkpoint/item 边界停止旧实验、替换工程基座并恢复研究队列；此前不改运行中实验。

## 仍需决策的内容

当前没有新的阻塞性决策。需要在后续候选达到资格门槛后再确认两件事：是否接受 full-label cast 的 scoped CPU non-regression，以及是否批准基座迁移窗口。27B 多卡、业务数据集扩展和新的研究训练均不属于本轮效率收敛范围。

