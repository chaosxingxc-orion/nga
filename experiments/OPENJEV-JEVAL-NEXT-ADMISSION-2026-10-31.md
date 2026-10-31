# Open-Jev JEVal：E38 后的实际准入路线

日期：2026-10-31。状态：工程分析与下一实验提案；没有新 NPU 执行，没有变更 E36/E37/E38 的冻结协议，没有授予完整 JEVal 准入。

## 结论与当前依赖

**释放 2B → 完成 9B E38 → 完整 JEVal** 中间缺少一个必要步骤：**实现并验证全量可运行、且符合所声明数值协议的推理路径**。E38 的成功终态只能证明定位仪器和诊断执行完整，不能证明 full-test 内存安全，也不能把原先失败的 chunk8 等价准入改成成功。

两尺寸的原始 JEVal 指标仍为 `blocked/null`。参考测试主指标必须沿用完整冻结 test 人口、原生温度、输出规则、有效/无效分母；不能通过减少候选、删去高内存题目或将有效分母改小来填满矩阵。

## 已核对的新定位证据

直接读取 2B v7 `report.json`（SHA256 `fa80f7e6797ac232ceb51baca0e6c6e76313dee376f556e81f4ef64df461f64c`）。两次 `cross_traces` 的首个不同观测事件都是：

`base_model.model.layers.0.linear_attn.in_proj_qkv:output`

15/15 候选均在这个事件出现不同摘要；其前序观测一致。报告的 11 项 repeat/hook/localization controls 全为 true。这个边界位于 GDN core 之前，因此不能把 chunk8 差异单独归因于 GDN recurrent 算术；它支持保留完整 batch 的投影形状继续调查。观测事件没有覆盖每个内部算子，不能据此断言某个 NPU kernel 是原因。9B 仍需自己的 E38 结果。

## 为什么只删死引用还不能宣布全量可跑

依据[固定源码内存分析](OPENJEV-NATIVE-MEMORY-CANDIDATES-2026-10-31.md)，实际 eligible 最大输入是 255×2156（pad 到 2176），不是人为拼出的 255×4096。9B 的有效 GDN heads 为 32。

| 9B 最大实际输入的 core-only 估算 | GiB | 含义 |
| --- | ---: | --- |
| 原始 305 行后存活 payload | 72.531967 | 尚未计入模型权重、调用方和 workspace |
| L1 生命周期清理后同一位置 | 47.131577 | 不代表全程峰值 |
| 清理后 299 行表达式的近似 payload | 59.399872 | 加常驻权重和调用方后仍没有单卡安全保证 |

这些是静态 payload 估算，不能代替设备峰值。E37 已测 9B 原始 30×4096 的 peak allocated/reserved 是 41.709454/56.710938 GiB；原始大候选输入未运行。当前没有证据支持直接对 255 候选任务试跑。

还有两个独立的风险必须进入全量内存检查：MLP 的完整 intermediate 张量；SDPA 的实际 Ascend 后端和 attention workspace。原生 Open-Jev 校验要求 `sdpa`，不能为了降内存默默改后端。仅分析 GDN 不构成整个 backbone 的内存上界。

## 最短的工程路线

1. **完成当前 release 修复与 9B E38。** 不改变已冻结计划或挪动 owner。CPU 侧的候选实现、测试及新预注册可以同时准备；等待只影响需要 NPU 的部分。
2. **新建独立生命周期实验。** 将 L1（早期死引用）与 L2（返回转换前释放）分别实现，并保留组合项。固定 C=64、inference mode、无 cache、无 final state；仅插入 last-use 后的 `del`，不得重排表达式、拆 matmul、改 batch/length/精度/候选顺序。用 AST 移除新增 `Delete` 后与原函数对比，另做支持条件 fail-closed 检查。AST 一致只是源码约束，不能替代实际数值验证。
3. **对既有安全形状验证。** 输入按既有 metadata 固定为 4200、9027、8409，不读取 gold 选择输入。每个原始/候选路径至少两次，无 hooks 输出做 exact 序列化比较；带生命周期观测的路径另与无 hooks 对照。分别输出 token/mask/候选身份、全部 logits/probabilities/wire、每芯片吞吐、chip count、peak allocated/reserved、关键阶段 allocated。任何失配保留原始输出和失败标记，不能调宽阈值后复用该代次。
4. **若 L1/L2 的全量余量不足，新增独立字节搬运实验。** 保持完整计算形状及操作顺序，只把长寿命、当前不用的张量或非活动层参数搬到 host，下一次使用前按原 dtype/shape/stride 恢复。host 不做数学、不重分片算子、不 merge adapter。先验证 byte round trip、alias、view、权重/LoRA 绑定、异常恢复与无 cache 限制，再对同一安全输入做完整输出 exact 对照。把张量 offload 与层权重 offload 分开测量，再登记必要组合；不要把新的搬运代码冒充 L1/L2。
5. **根据实测边界登记扩大工作量。** 对全部 3,675 个 eligible shape 组合建立阶段性 live-set 和后端 workspace 的保守预算，写出明确 headroom 和准入上界，再审查并逐级扩大安全 workload。255×2156 只在边界已经证明有余量后运行；不作为故意 OOM 的探针。不能拿三个 shape 的成功线性外推全部 attention/workspace。
6. **完整 test 推理与独立计分。** 候选通过独立数值/内存审查后，以新配置代次启动每模型 11,257 行任务。逐 item 恢复、终态、独立 verifier、flags、资源释放、wiki 必须实际完成。无需原始 full-batch 最大形状故意 OOM 来形成对照；若原始对照无法安全运行，该部分逐位等价的证据边界必须明确写出，不能声称已实测。

## 一个可减少 299 行峰值的 offload 位置（待验证候选）

原函数的 query 在缩放后、进入 recurrent 循环前不参与中间三角求解或 `k_cumdecay` 表达式。将它的原始字节暂存 host，再在循环前恢复，理论上可从 299 行重叠中去掉一份 F（最大 9B 约 8.466797 GiB）。这只是减少某时点 payload 的候选；restore 时其他张量仍在，且调用方 view、设备格式转换、异步使用和 NPU workspace 都会影响实际峰值。因此不以 `59.399872 − 8.466797` 作为获准运行上界。

同理，层权重 offload 可以降低常驻参数，但不能解决大单层激活的必需 payload。先量化再决定组合，不能假设“模型小于 10B，所以 64 GiB 必然够”。

## 最小新实验的验收和自动化

- 实验前冻结目的、defect 12/16、模型/数据/代码 SHA、输入身份、路径、重复数、exact 比较、失败条件及各路径独立状态。
- 无约束最省内存解是少算候选或跳过计算；其区分性对照是完整候选/事件、全量输出及字节身份一致，不能只比较最终 decision。
- detached 固定容器、不 `--rm`、CephFS 日志、heartbeat、逐 item 回执、真实退出、terminal marker、relaunch 命令和独立验收均沿用仓库规则。新的实验预注册与 wiki 必须在启动前写完。
- throughput 只比较同输入、同路径观测条件的无 hooks forward；带 profiling 的耗时单独报。吞吐和显存都标明 per chip 与 chip 数。
- 此提案没有提供 NPU 启动许可、Astra PASS 或新实验成绩；候选源码与 exact plan 尚需实际审查。

## 决策边界

在用户已授权的“先修工程效率、完成当前 38 组合”范围内，L1/L2 和保持运算形状的字节 offload 工程准备可以继续，无需再次询问算力预算。若这些路线不能满足完整原协议，才需要提出具体选择：继续投入原协议路径；或另立 chunk8 数值配置的参考结果，并保留原协议 `blocked/null`。后者会改变比较口径，不能由工程侧悄悄替换。

当前不推荐先降阈值或改分母来填表。正式训练仍由 D1 收口后冻结的训练方案决定；E38 和内存诊断均不构成 Jev 训练收益。

## 来源

- [E37 实测与失败准入](OPENJEV-BATCH-DIAGNOSTIC-RESULTS-2026-10-31.md)
- [E38 预注册](OPENJEV-PATH-TRACE-E38-2026-10-31.md)
- [固定源码与 eligible shape 静态分析](OPENJEV-NATIVE-MEMORY-CANDIDATES-2026-10-31.md)
- 2B v7 `/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v7/report.json`
- 固定 native 源码 `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_native_static_source_20261031/modeling_qwen3_5.py`

