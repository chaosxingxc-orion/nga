# E37 Open-Jev 有界诊断结果：2B 与 9B

两尺寸均已完成 **16 forwards/model**，且 detached CPU verifier、NPU 容器实际退出均为 0。结果是：**no-op 与边界 profiling hooks 未改变保存的输出；候选 chunk8 在三个固定输入上仍改变概率。因此 E36 的纯效率等价准入继续为 false，Open-Jev 原协议 JEVal 完整测试尚未获准启动。** 这是限定诊断结果，不是参考 test 总分，也不是新训练收益。

协议：[E37 预注册](OPENJEV-BATCH-DIAGNOSTIC-2026-10-30.md)。源码准备期间修复了非 root 主机身份检查，父会话另行复核并复跑 42+10 tests；原 Astra 代码审查快照不覆盖该局部修订。此处没有新的 Astra 数值结果放行。

## 固定输入与检查范围

由原始 eligibility 元数据选定 9027（30×4096）、4200（15×186）、8409（24×3480）；mid-tail 分层为空，保持为空。没有按 gold、预测或运行效果替换输入。每尺寸只在 **9027** 做 no-op 和 original/chunk8 各一次 profiling；其他两项只做 original/chunk8 各两次。原始超大候选批次 255×2156 未在 E37 原路径执行，不能据三项完成证明完整 JEVal 的内存上界。

两尺寸原始路径及 chunk8 重复输出在三个输入上均精确一致。9027 的 no-op、no-op 重复及两种 hook 输出也精确一致；包含保存的 logits、probabilities、wire、候选顺序和 token 哈希。`diagnostic_valid=true` 仅表示这些已登记仪器检查通过，不认证未保存中间张量或算子因果。

## Original 与 chunk8 的差异

| 模型 | 原始 index | max logits delta | max probability delta | max wire delta | returned decision changed |
| --- | --- | ---: | ---: | ---: | --- |
| 2B | 9027 | 0.236347317696 | 0.0141414146503 | 0.0146290496383 | false |
| 2B | 4200 | 0.0519268512726 | 0.00351450921099 | 0.0037655455832 | false |
| 2B | 8409 | 0.0742716789246 | 0.00262589228309 | 0.00262589228309 | false |
| 9B | 9027 | 0.141026496887 | 9.39101248731e-06 | 9.71484050405e-06 | false |
| 9B | 4200 | 0.131692230701 | 0.0138691596932 | 0.014859813957 | false |
| 9B | 8409 | 0.0528364181519 | 0.00330927203578 | 0.00345315342864 | false |

各尺寸 returned decision 改变均为 **0/3**，tokens 相同，但三项数值均不精确相同。这个小型元数据选中集合不支持“差异可忽略”或全量稳定性的结论。尤其 9B 在最长边界 9027 的概率差约 9.39e-6，却在短输入 4200 达约 **0.01387**；不能只展示最长输入上的小差值。未使用 gold accuracy 判断任何配置。

## 边界 9027 的内存和观测吞吐

下表是 **未加 hooks** 的 whole-forward 峰值；两次重复峰值相同。GiB=2^30 bytes。

| 模型 | 路径 | peak allocated GiB | peak reserved GiB |
| --- | --- | ---: | ---: |
| 2B | original | 16.749704 | 24.048828 |
| 2B | chunk8 | 7.172883 | 7.539062 |
| 9B | original | 41.709454 | 56.710938 |
| 9B | chunk8 | 22.231260 | 24.394531 |

以下吞吐是同一边界输入两次执行的观测，单位 questions/s/chip；每次单芯片。它不是跨接口公平性能排名，也不能因速度改善而授予数值等价准入。

| 模型 | 路径 | repeat0 / repeat1 questions/s/chip | peak reserved GiB | chips |
| --- | --- | ---: | ---: | ---: |
| 2B | original | 0.098251 / 0.108637 | 24.048828 | 1 |
| 2B | chunk8 | 0.110376 / 0.111213 | 7.539062 | 1 |
| 9B | original | 0.036222 / 0.037671 | 56.710938 | 1 |
| 9B | chunk8 | 0.039507 / 0.039510 | 24.394531 | 1 |

profile 中记录的最大 decoder-layer inclusive peak 如下。层峰值包括该时刻仍存活的其他分配，**不能相加、不能当成独立层内存，也不能定位具体内部算子**。chunk index=-1 表示未切块；原层顺序从 0 开始。

| 模型 | 路径 | attention class | layer | chunk index | inclusive peak allocated bytes | GiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 2B | original | Qwen3_5Attention | 3 | -1 | 11860433408 | 11.045889 |
| 2B | original | Qwen3_5GatedDeltaNet | 1 | -1 | 17984858112 | 16.749704 |
| 2B | chunk8 | Qwen3_5Attention | 3 | 1 | 6066002944 | 5.649405 |
| 2B | chunk8 | Qwen3_5GatedDeltaNet | 1 | 1 | 7701824000 | 7.172883 |
| 9B | original | Qwen3_5Attention | 3 | -1 | 31533544960 | 29.367902 |
| 9B | original | Qwen3_5GatedDeltaNet | 2 | -1 | 44785185280 | 41.709454 |
| 9B | chunk8 | Qwen3_5Attention | 3 | 2 | 20471068672 | 19.065168 |
| 9B | chunk8 | Qwen3_5GatedDeltaNet | 1 | 1 | 23870633984 | 22.231260 |

原始 2B 输入 hidden shape 为 `[30,4096,2048]`，9B 为 `[30,4096,4096]`；chunk8 对应批次维度为 8（最后一个块为 6）。原始路径分别观察 24/32 decoder layers，切块为四次、共 96/128 个 layer observations。GatedDeltaNet 层显示更高 inclusive peak，只用于指引后续调查；hook 同步和 CPU 元数据哈希使 profile 时间不能用作公平吞吐测量。

## 实际执行、验收与资源释放

2B NPU：21:20:01 UTC terminal，21:20:05 UTC actual exit 0；CPU verifier：21:21:42 UTC actual exit 0。9B NPU：21:33:54 UTC terminal，21:33:58 UTC actual exit 0；CPU verifier：21:34:51 UTC actual exit 0。均为 2026-10-30 的 175 主机时间（北京时间次日）。每尺寸保存完整 16-item receipt manifest；CPU verifier 核对冻结依赖、实际容器身份/退出、terminal/输出哈希、完整集合和 comparison 算术。它未独立重分词，也未通过第二套 NPU 实现验证 parity。

- **2B**：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_batch_diagnostic_openjev2_20261031_v2`；plan `97be9d15c0954903e629a3eb03bf4552ab4bb80ddf76cd2887c4072c9059bf00`；report `60e0e86638ccf5e23b9ec6695fb58f11b9970b61817481d12c7f2d777a7ac540`；verifier report `becae7b6329706454561d3ce79632539c1484072ad72478806a6c65ea51d1862`。
- **9B**：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_batch_diagnostic_openjev9_20261031_v2`；plan `6cf91782e92465ed1d1856e4fc392a398faca3737d559b3898597e63adf93e4c`；report `d03e1298ce4dde83077a21628ce57aa2a4a194f7c46fa18b9942e556f1ef4cc9`；verifier report `3c42cb3a1070957f2b84ff544be343d788d0466cd7e4f1b5407bbb9dd7d8c742`。

chip 4 在两次诊断之间及 9B 验收后均按 allocation lock、实际退出和新鲜 Docker/device 查询显式释放；各自 `RELEASED.json` 保留证据。9B 最终释放时间为 21:36:04 UTC。没有启动 Open-Jev 完整 JEVal，也未覆盖旧 E36 失败记录。

下一步只可依据这些结果设计受影响路径的修复及独立数值验证，或明确登记另一种数值配置的额外评测。任何 chunk8 完整结果都必须单列其协议，不能回填原协议已完成格、重新定义 E36 阈值或借 0/3 decisions flip 宣布等价。机器可读完整精度摘要见 [JSON](OPENJEV-BATCH-DIAGNOSTIC-RESULTS-2026-10-31.json)。
