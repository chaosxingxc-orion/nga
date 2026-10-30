# Typed Decisions 共同测试：本地参考结果

2026-10-30 17:44 UTC。Kev 三尺寸均完成原始 400 states／2,000 questions，独立验收 `COMPLETED_SCOPED`、审查标记 0，推理与验收容器、结构化终态及 wrapper 均退出 0。Nimble、Open-Jev 的共同推理尚未完成，不能称六模型比较已齐全。协议见 [E26](TYPED-COMMON-REFERENCE-2026-10-30.md)，运行记录见 [wiki](../wiki/E26-typed-common-reference-20261030.md)。

数据 SHA256：`4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`。保留原始题目与候选顺序，未截断、未选择子集；每模型返回并验证全部 2,000 个分布，无 invalid／unsupported／overlength／failed。该集不同于 NGA 派生分区。

## 原方法算术，原生概率读出

Accuracy 为问题等权、预测与金标首次 argmax 相等；gold 保留原舍入质量、不归一化，prediction 按原 scorer 归一化。KL floor 为 1e-9；Brier 是对 soft gold 各维平方差之和；ECE10 使用 max probability 和 hard argmax correctness。不是 Open-Jev 原测试的 ECE15／expected correctness，也不是 JEVal 的 returned-choice 口径。

| 模型 | 温度 | accuracy % | KL from gold | soft Brier | ECE10 |
| --- | --- | ---: | ---: | ---: | ---: |
| Kev-0.8B | 原生 2.3510958125672174 | 45.95 | .349523040 | .195493398 | .045770036 |
| Kev-0.8B | raw T=1 | 45.95 | .498068065 | .260309344 | .155169722 |
| Kev-4B | 原生 2.406050072164233 | 66.45 | .223109423 | .124564683 | .089533926 |
| Kev-4B | raw T=1 | 66.45 | .504515027 | .201069093 | .091401498 |
| Kev-9B | 原生 2.193649959389252 | 68.05 | .213789510 | .116320990 | .064928038 |
| Kev-9B | raw T=1 | 68.05 | .519308862 | .187224530 | .091135501 |

每行 n=2,000。两温度来自相同预测记录，服务温度使用保存的原生概率，T=1 从 logits 复算；没有按 test 拟合温度。Kev 的 noul wire 缺原评分器所需概率字段，因此这里明确是原方法算术作用于原生概率，不冒称 HTTP／vLLM／wire 完全复现。预注册的 expected-score MAE 已暂缓，不从 ordinal accuracy 推断该指标。

| 题型 | n | Kev-0.8B accuracy % | Kev-4B accuracy % | Kev-9B accuracy % |
| --- | ---: | ---: | ---: | ---: |
| choice | 600 | 51.000000 | 64.000000 | 64.333333 |
| noul | 600 | 51.666667 | 75.666667 | 74.666667 |
| score（等级 argmax） | 800 | 37.875000 | 61.375000 | 65.875000 |

9B 总体比 4B 高 1.60 个百分点，但 noul 低 1 个百分点；agent_trace_observability 分项为 50.2% 对 56.0%。因此尺寸增大并非每个单元改善。此处只是参考结果描述，未做显著性／配对一致性结论，也不是我们的继续训练收益。

## 验收与执行证据

运行目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/typed_kev{08,4,9}_inference_20261030/`；各自 `_finish/` 保存独立审计。验收覆盖全部逐项身份、依赖闭包、runtime、checkpoint 温度、token provenance、分布与指标重算；token 哈希绑定不等于独立重新 tokenize。Astra 实质审查仍未获得。

| 模型 | 冻结／必需文件数 | report SHA256 | audit SHA256 |
| --- | --- | --- | --- |
| 0.8B | 70／66 | `bb8db0937e7d50881128350d245bdf4c68e8434859bfeeb227998eacf6359b10` | `81522d770b77742a2c668663dd22c0e532a7fc121468ff4251b15467d799a397` |
| 4B | 75／71 | `d92e85ffb6d3f85cbc39b4dc1033de1872770e7ebe21538faee57de0b272a88b` | `1ecb010f3cfb5ae3e1b1c942a5e36fe10294f7fafaed376186dfb309f965a83a` |
| 9B | 73／69 | `e9da5cd6fab9f7b3508c7751508b266e6ddc8851bfa294296ce20da4219a18d9` | `b4e68d08a55e84660ba7ade731861053ef742bc78246fc989f38f07ed2ecc28f` |

各使用 1 chip，最后累计吞吐分别为 10.5837／8.7235／7.2509 questions/s/chip，reserved memory 为 4.2344／18.0625／32.1836 GiB。这是本次原生 FP32/eager 推理的观测，不是跨接口公平速度排名或加速等价性实验。
