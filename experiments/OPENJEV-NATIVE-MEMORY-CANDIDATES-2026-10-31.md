# Open-Jev 原生 GatedDeltaNet 内存候选：静态分析草案

日期：2026-10-31。状态：**只读源码/元数据分析；未选择修复方案，未改任何模型计算，未执行 NPU 或 OOM 探针。** 这不是 E38 冻结协议的修订。最终实验选择等待 E38 定位结果；本草案不能改变 E36 的 `candidate_batch_admission=false`。

## 1. 范围、来源和可证伪条件

目标对应 defect 12/16：维持可执行身份，区分内存生命周期优化与数值配置改变。无约束的最省内存解是跳过计算、少算候选或替换算术；它不满足参考协议。区分性对照必须同时要求完整候选/事件、原始 token/mask/顺序、相同 checkpoint/精度/表达式/操作顺序和预登记的原生重复、完整输出精确比较。删引用也可能影响分配器地址、workspace 或异步执行，不能仅靠源码判断授予数值准入。

固定镜像为 `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`。从已退出的 CPU 工程容器 `b9ae877b05f963476f031dbe3c068fe1cda404af26391cd40fdf8ec935754658` 只读导出原生 `transformers/models/qwen3_5/modeling_qwen3_5.py`，SHA-256 为 `0e2cd8dc50885b2701d26b116c585eedcdc62a24080ec34345af55b963126ded`。导出和来源记录保存在：

`/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_native_static_source_20261031/{modeling_qwen3_5.py,SOURCE.json}`。

下文行号均指该固定文件：chunk fallback 为 248–326，调用方为 440–563。本次读取文件，没有执行导出的 Python。不能将估算归因于文献；它是本项目对这一固定实现的工程分析。

2B/9B 原始 `config.json` SHA 分别为 `ed1c1723241f23f7f4e23430759cbd7dcfb4103cbdfe052bfe7626b57c2615b4`、`d0883072e01861ed0b2d47be3c16c36a8e81c224c7ffaa310c6558fb3f932b05`。E31 eligibility 报告 SHA 分别为 `58204e7a9216a24877a97e5dfc94fa2c185daf85df34e5eb9f49a7999466b3ca`、`b2705b7330eccf022e8e5121e05e79b832f09f8eae1a6ff11d71e59e8fad8f82`。它们来自已冻结 E38 plans 引用的 native config；未重新分词或用标签挑输入。

## 2. 实际输入边界：不能组合互不共现的最大值

两模型各 11,257 条 eligibility 记录，其中 9,704 条 eligible。下表只描述原生预算内的 eligible 集合，不把超长行截断后纳入。

| 条目/统计 | B：候选数 | L：全局 padding 后长度 | Lp：core 向 64 上取整 | 说明 |
| --- | ---: | ---: | ---: | --- |
| E38 index 4200 | 15 | 186 | 192 | 当前定位实验，不能据此证明全量内存安全 |
| E37 index 9027 | 30 | 4096 | 4096 | eligible 最大 L，非最大 B×L |
| E37 index 8409 | 24 | 3480 | 3520 | 已有长输入诊断 |
| JEVal index 633/637 | 255 | 2156 | 2176 | eligible 最大 B×L=549,780，亦为最大 B×L²=1,185,325,680 |
| 最大 B | 255 | 各条目不同 | 各条目不同 | 200 条并列；不能制造 255×4096 的不存在条目 |

core 的最大 B×Lp 为 **554,880**，有 11 条并列（包括 633/637）；它比 native 全局 padding 后的 B×L 略大。E37 排除过的最大候选工作量仍只用于静态边界分析，不执行原始路径 OOM 尝试。

对两份报告分别扫描全部 **9,704 eligible 条目、3,675 个不同 (B,L) 组合** 后，按 `B×Lp` 降序、并列按 `B×L` 降序列出的前 12 个实际组合如下。两模型的形状组合、计数与索引相同。`B×Lp` 只是 GDN 全序列 FP32 payload 的尺度代理，不是整模型/attention 峰值；因此同时保留 `B×L²` 代理。所有最大 `B×Lp` 并列条目为 627–637，未挑其中分数较好的条目。

| B | L | Lp | B×L | B×Lp | B×L² | 条数 | 原 index |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 255 | 2156 | 2176 | 549780 | 554880 | 1185325680 | 2 | 633, 637 |
| 255 | 2155 | 2176 | 549525 | 554880 | 1184226375 | 1 | 631 |
| 255 | 2154 | 2176 | 549270 | 554880 | 1183127580 | 1 | 628 |
| 255 | 2152 | 2176 | 548760 | 554880 | 1180931520 | 3 | 632, 634, 636 |
| 255 | 2151 | 2176 | 548505 | 554880 | 1179834255 | 1 | 635 |
| 255 | 2150 | 2176 | 548250 | 554880 | 1178737500 | 2 | 627, 629 |
| 255 | 2149 | 2176 | 547995 | 554880 | 1177641255 | 1 | 630 |
| 255 | 1802 | 1856 | 459510 | 473280 | 828037020 | 1 | 684 |
| 255 | 1801 | 1856 | 459255 | 473280 | 827118255 | 1 | 683 |
| 255 | 1261 | 1280 | 321555 | 326400 | 405480855 | 1 | 658 |
| 255 | 1260 | 1280 | 321300 | 326400 | 404838000 | 2 | 656, 659 |
| 255 | 1259 | 1280 | 321045 | 326400 | 404195655 | 1 | 657 |

| 参数 | 2B | 9B |
| --- | ---: | ---: |
| hidden size | 2048 | 4096 |
| key heads（投影后） | 16 | 16 |
| value heads / core 有效 heads H | 16 | 32 |
| key/value head dim D | 128 / 128 | 128 / 128 |
| decoder layers | 24 | 32 |

9B 的 query/key 在调用 core 前被 `repeat_interleave(2)`（524–525 行），因此 core 的 Q/K/V 都按 **H=32** 计，不能误用 key projection 的 16 heads 将内存减半。无 cache 的推理层顺次执行，不应把下文单层临时内存乘以 24/32；模型参数、外层 residual 和调用方保留张量另计。

## 3. 张量尺寸与生命周期

固定 `chunk_size C=64`，`N=Lp/C`，以 FP32 的 4 bytes/element 计。以下符号表示 payload，不含分配器对齐、workspace 或框架元数据：

- `F = 4×B×H×Lp×128`：一份完整 Q/K/V/k_beta/v_beta/k_cumdecay/core 输出。
- `A = 4×B×H×N×64² = F/2`：完整 `decay_mask` 或三角阶段 `attn`。
- `S = 4×B×H×Lp = F/128`：`beta` 或累计 `g`。
- `R = 4×B×H×128²`：recurrent state。
- `U = A×(63²+63)/64² = A×63/64`：三角更新最后一轮仍绑定的 `sub` 和 `row`。

这里的 `.reshape`/切片通常是 view，不能再次累加同一 storage；`del` 一个 view 也不保证底层 storage 释放。以下 last-use 是源码中的最后一次读取；“可删”仅表示局部引用不再参与后续算术。

| 名称 | 形状/payload | 最后读取/重绑定点 | 保留原因与候选删除位置 |
| --- | --- | --- | --- |
| 原始 FP32 `value` | `[B,H,N,64,128]`，F | 284 行 reshape；298 行被新 value 替换 | reshape 后原 value 不再作为算术输入，298 RHS 只读 `attn/v_beta`。可调查在 284 行后删原 `value`，避免它与后续表达式结果重叠 |
| `beta` | `[B,H,Lp]`，S | 281 行 `key * beta.unsqueeze(-1)` | 可调查在 281/284 行后删局部引用；调用方还有自己的 beta，但 FP32 core 副本的实际 alias 需核验 |
| `v_beta` | `[B,H,N,64,128]`，F | 298 行 `value = attn @ v_beta` | 可在这行完成后、299 行前删；后续没有读取 |
| `k_beta` | 同上，F | 299 行 `attn @ (k_beta * g.exp().unsqueeze(-1))` | 299 行后可删；不能提前改成切块 matmul |
| 完整 `attn` | `[B,H,N,64,64]`，A | 299 行；311 行才重绑定成单 chunk 的 attn | 299 行后可删局部引用，避免与 state/core output 创建重叠；311 行仍保留原表达式 |
| `row`、`sub` | 末轮 `[B,H,N,63]` 与 `[B,H,N,63,63]`；合计 U | 296 行最后一次三角更新 | **Python for 循环不建立局部作用域**，末轮 `.clone()` 仍由这两个名字保留到返回。可调查在循环结束、297 行前 `del row, sub`；仅适用于已固定 C=64，不可泛化为 C=1 无保护代码 |
| `query/key`、新的 `value`、`k_cumdecay`、`decay_mask`、`g` | 4F+A+S | 309–319 行按所有 chunks 使用 | 在循环中都不能提前删。循环结束后可调查返回前释放；必须一并处理 q_i/k_i/v_i 等 view 引用 |
| `q_i/k_i/v_i` | 单 chunk view | 最后一轮的 311/313/318 行 | 仅删完整 query/key/value 不足以释放其 storage，这些末轮 view 仍持有引用 |
| `v_prime/v_new/attn_inter`、单 chunk `attn` | 3F/N + A/N | 最后一轮 313/318/315 行 | 循环退出后不再参与返回；可调查返回格式转换前删这些引用 |
| `core_attn_out` | 完整 FP32 F | 返回前切片、transpose、contiguous、转回 BF16 | 必须保留输出本身。325 行可能同时持有原 FP32 padded storage、新 FP32 contiguous 和 BF16 返回副本，不能把 `.to(initial_dtype)` 当原地转换 |

**独占 clone 与 alias 的区别。** 294 行 `row = attn[..., i, :i].clone()` 和 295 行 `sub = attn[..., :i, :i].clone()` 的切片输入是 view，但 `.clone()` 结果是两份独立新 storage，不与 `attn` 共享 payload。固定 C=64 时，末轮 i=63；296 行 RHS 是它们的最后读取。`row.unsqueeze(-1)` 是临时 view，表达式完成后没有源码中持久保存的别名；在本协议 `torch.inference_mode()`、没有额外 profiler 保存 Tensor、且异步 kernel 已不再使用 storage 的前提下，删除这两个局部名可以解除其最后 Python 引用。预计可回收的 clone payload 就是 U，最大工作量分别约 2.083626/4.167252 GiB；它可回到 caching allocator，并不保证归还设备或降低 reserved。逐轮 `del row, sub` 还可能避免下一轮 `.clone()` 分配期间与上轮 storage 重叠，但这是需要独立区分的候选位置，不能与“只在末轮后删”混报。

`v_beta`/`k_beta` 来自 out-of-place 乘法，284 行 reshape 后只把 view 绑定回相同局部名；在 eager inference、无额外保存引用的假设下，其最后使用后删除也可解除那份乘法 storage 的持有。query/key/value、`core_attn_out` 以及 q_i/k_i/v_i 则有显式 reshape/slice view 关系，删除其中一个名字不够。cast/contiguous/pad 的具体 alias 行为、backend pending work 和额外 hook 持有不由“变量未再读取”自动证明；需要后续受控 storage identity 与 allocated 测量，但本次没有为此运行张量算术。

源实现的 `g` 已经是 FP32；291 行的 `.float()` 若输入仍为 FP32 是 dtype no-op，不应凭源码出现一次 `.float()` 就再加一份 A。263–278 行的归一化、transpose/contiguous、FP32 cast、padding 和 scale 自有短时峰值；本表未据此给出完整执行峰值。

## 4. 大小和阶段性 live-set 估算

下表单位均为 **GiB（2³⁰ bytes）**，只是单个 GDN core 的 payload。没有把参数、调用方 BF16 Q/K/V/z、PEFT、residual、MLP/full-attention、NPU 内部格式、workspace、缓存或日志观测工具算进去。

| 输入 | 模型 | 一份 F | 一份 A | R | 仍保留的 row+sub：U |
| --- | --- | ---: | ---: | ---: | ---: |
| E38 15×186 | 2B | 0.021973 | 0.010986 | 0.014648 | 0.010815 |
| E38 15×186 | 9B | 0.043945 | 0.021973 | 0.029297 | 0.021629 |
| E37 30×4096 | 2B | 0.937500 | 0.468750 | 0.029297 | 0.461426 |
| E37 30×4096 | 9B | 1.875000 | 0.937500 | 0.058594 | 0.922852 |
| 最大工作量 255×2156 | 2B | 4.233398 | 2.116699 | 0.249023 | 2.083626 |
| 最大工作量 255×2156 | 9B | 8.466797 | 4.233398 | 0.498047 | 4.167252 |

为定位值得测量的区间，采用 eager inference、没有 autograd 保存额外张量、相应乘法/clone/matmul/输出转换产生独立 storage、仅上文注明的 reshape/slice 为 alias 的假设。异步内核释放、allocator reuse 和实现内部临时块没有由此证明。

**305 行输出创建后、进入 recurrent 循环前**的显式 live payload 为：

`7F + 2A + U + 2S + R`。

七份 F 是 query/key、新 value、v_beta、k_beta、k_cumdecay、core_attn_out；两个 A 是完整 attn/decay_mask。若仅调查前述早期引用释放（beta、原 value、row/sub、v_beta、k_beta、完整 attn），同一时点候选 live payload 为 `5F + A + S + R`，差为 **3F**。这是该时点的存活引用差，**不是全程 peak 下降保证**。

| 输入 | 模型 | 原始 305 行后估算 | 早期 del 候选同一时点估算 | 同一时点差 |
| --- | --- | ---: | ---: | ---: |
| E38 15×186 | 2B | 0.201588 | 0.135670 | 0.065918 |
| E38 15×186 | 9B | 0.403175 | 0.271339 | 0.131836 |
| E37 30×4096 | 2B | 8.005371 | 5.192871 | 2.812500 |
| E37 30×4096 | 9B | 16.010742 | 10.385742 | 5.625000 |
| 最大工作量 255×2156 | 2B | 36.265984 | 23.565788 | 12.700195 |
| 最大工作量 255×2156 | 9B | 72.531967 | 47.131577 | 25.400391 |

还必须检查另外两个区间：

1. **299 行创建 k_cumdecay：** 原表达式有完整的 `k_beta * g.exp().unsqueeze(-1)` 临时 F，同时要产生 k_cumdecay 的 F。在上述候选提前释放之后，这一表达式仍约需 `6F+2A+2S` 的 core payload（给 g.exp 留一份 S），最大工作量约 **29.699936 GiB（2B）/59.399872 GiB（9B）**。不能拿 305 行的降低值当作新全程峰值；9B 加上权重/调用方等后仍可能无法装入单卡。
2. **325 行返回转换：** 若不清理循环末尾名字，原代码还保留完整输入/中间量、末轮 chunk 临时量，以及 FP32 contiguous/BF16 返回副本。令 `f=F×L/Lp`，按同一分配假设估算为 `7F+A+U+2S+A/N+3F/N+1.5f`。最大工作量约 **40.627785/81.255569 GiB**；30×4096 约 **8.964844/17.929688 GiB**。这个估算不是测得的设备峰值，也不包括更多 backend workspace；它说明需要同时审查返回阶段，而不只盯 recurrent state 创建。

E37 已测得 30×4096 原始 GDN 层的 inclusive peak 为 2B **16.749704 GiB**、9B **41.709454 GiB**。这些值包括权重和其他仍存活分配，不能用上述 core-only 静态数字替换，也不能简单相减得到“权重大小”。这里没有声称建立了完整的峰值预测器。

## 5. 允许继续讨论的最小候选与禁止越界

下列只是互相可区分的候选包，不是选定 patch，也不允许修改冻结 E38 source：

- **候选 L1，早期局部引用：** 在固定 C=64/无 cache 的原 fallback 中，仅在对应 last-use 后释放 `beta`、原始 FP32 `value`、`row/sub`、`v_beta`、`k_beta`、完整 `attn`。保留所有原表达式、操作顺序、matmul 形状、padding、FP32 和 BF16 边界。可以先分包量化哪些引用真正影响 allocated peak。
- **候选 L2，返回前生命周期：** 在全部 chunks 处理完后、返回格式转换前，释放不再读取的 query/key/value/k_cumdecay/decay_mask/g 及 q_i/k_i/v_i/v_prime/v_new/attn_inter/attn；必须核验所有 alias 与 `output_final_state=False` 的既有协议。它可能降低325行的重叠，但不能降低299行必需的完整表达式 payload。
- **后续参数驻留/临时存储调查：** 若生命周期优化仍不足，再单独测原始 full-batch 的权重驻留、参数 offload 或精确字节搬运；不能把它们与 L1/L2 混成一个无法归因的变化。

禁止把 reduced candidate batch、换 recurrent/fused core、改变精度、分解 matmul、重排/融合表达式、原地覆写活张量、CPU 算术或删除 padding 当成上述 `del` 候选的一部分。删除已死引用是 Python 对象生命周期变化，数学表达式不变；这仍不保证设备实现的逐位输出一致。

## 6. 下一次真正实验需要证明什么

静态已确定的是：固定实现和配置、实际 eligible 输入尺寸、上表 last-use、9B 的有效 H=32、末轮 row/sub 与 slice view 会继续持有引用。尚未确定的是：E38 首个观测差异位置、实际 storage alias、各阶段 allocated/reserved 峰值、异步释放和 workspace、整条原始 JEVal 路径能否装入、吞吐与完整输出是否保持精确一致。

只有定位结果返回后，才冻结候选代码和独立预注册。先用已有安全诊断输入（4200、9027、8409）及其完整对照测生命周期/数值，再以审阅后的静态边界与明确内存余量确定是否允许扩大工作量；不以最大255候选输入故意撞 OOM。reserved 不保证随 allocated 降低，既有 allocator 缓存可能继续占用；任何吞吐数据需标明每芯片、芯片数与 reserved memory。没有这些证据，不能解除 Open-Jev JEVal 阻塞，也不能用本草案声称已获得效率收益。
