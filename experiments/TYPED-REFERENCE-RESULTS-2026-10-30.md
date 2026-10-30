# Typed Decisions 共同测试：本地参考结果

2026-10-30 17:44 UTC 初版，18:31 UTC 更新。Kev 三尺寸、initial Nimble 及 Open-Jev-2B／9B 均完成原始 400 states／2,000 questions，独立验收 `COMPLETED_SCOPED`、审查标记 0，推理与验收容器、结构化终态及 wrapper 均退出 0。六个参考模型的本集合推理与限定范围独立验收已齐全。Kev 协议见 [E26](TYPED-COMMON-REFERENCE-2026-10-30.md)，Nimble 见 [E28](../wiki/E28-typed-nimble-reference-20261030.md)，Open-Jev 见 [E29](../wiki/E29-typed-openjev-reference-20261030.md)。

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
| Nimble initial v1 | 原生 T=1 | 65.10 | .706027650 | .254995374 | .172864315 |
| Open-Jev-2B | 原生 1.518796342858676 | 58.25 | .410910644 | .193816502 | .081003319 |
| Open-Jev-2B | raw T=1 | 58.25 | .659782229 | .245027524 | .159234993 |
| Open-Jev-9B | 原生 1.8969118766347646 | 67.80 | .369436036 | .147618002 | .058201569 |
| Open-Jev-9B | raw T=1 | 67.80 | .885942246 | .224382522 | .148582028 |

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

## 18:19 UTC：Nimble 完成追加

Nimble 的 2,000 个分布全部有效，invalid／unsupported／overlength／failed 均为 0。choice／noul／score 的 accuracy 分别为 65.5%／74.166667%／58.0%，分母为 600／600／800。它保留同一 state 的完整五字段 schema，使用原生 T=1、BF16 safe merge 和 FP32 candidate projection；不同接口的总分差不能直接归因于 readout 结构或我们的训练。

运行目录 `reference_inference/typed_nimble_inference_20261030/`，独立验收在同名 `_finish/`。验收重新 tokenize 全部 prompts、检查 141／141 冻结／必需文件并独立重算指标。推理 wrapper 于 18:16:39 UTC、验收 wrapper 于 18:17:52 UTC 退出 0；父会话另核对实际保留容器退出状态、配置及全部终态产物哈希。

- config SHA256：`90aea1118abcead77a37c67d59526d2044d5b5be5a726dbc9d2a605ea477eaeb`
- report SHA256：`a99261c46b37e4b5e0533fd07f5a2fec4701d22beaf6835721d0374e0a5438f5`
- audit SHA256：`0ed217f5cd19d975531f449ed55610d4e8783f1d1a2a96387bec9895db927416`

最终累计吞吐 1.437146 questions/s/chip，1 chip，reserved memory 18.65625 GiB。没有新增训练收益或 Astra 实质放行结论。

## 18:23 UTC：Open-Jev-2B 完成追加

全部 2,000 questions 有效，choice／noul／score accuracy 为 55.5%／72.166667%／49.875%，分母为 600／600／800。原生 BF16 unmerged backbone、FP32 head、SDPA，使用各候选独立提示；原生温度与 T=1 来自相同逐项结果，没有 test 温度拟合。独立验收重新 tokenize 全部提示、重建 wire 并重算原方法指标，93／90 冻结／必需文件，审查标记 0。

运行 `reference_inference/typed_openjev2_inference_20261030/` 及 `_finish/`。推理／验收 wrapper 分别于 18:20:48／18:21:16 UTC 退出 0，父会话核对终态、配置、产物哈希及两个实际容器退出 0。

- config SHA256：`6f1f678c728a912e5f249c273389e248100aa26bdbafeaadb28361c58ca2c728`
- report SHA256：`0bb139be0026fb72fe9b4c7d512a8443645ccbeefb5ca95d355d77030cdac9f5`
- audit SHA256：`8481faf3d2ef4f0e58aaf5c76fa3221a9dc2dc650e6d4b82ca802b36c6626341`

最终累计吞吐 1.449861 questions/s/chip，1 chip，reserved memory 4.146484 GiB。结论限于该配置共同测试，不能以原生 test 的高分替代此处成绩，也不据此直接判断训练机制。

## 18:31 UTC：Open-Jev-9B 完成追加

全部 400 states／2,000 questions 有效；choice／noul／score accuracy 分别为 66.166667%／80.833333%／59.25%，分母为 600／600／800。独立重分词、wire 重建及计分核对通过，96／93 冻结／必需文件，审查标记 0。推理／验收 wrapper 于 18:29:32／18:30:26 UTC 退出 0；父会话另核对实际容器退出与配置、终态、全部产物哈希。

- config SHA256：`ecbb6411a67f59d18300962d8549eca33c9ac74bf74e651f9a8ea61874b6d4bb`
- report SHA256：`dcd2d16f995e5f4db8a5e5316daa6a2ea7bdc33a3d1c8e638d896d3f90e14bd1`
- audit SHA256：`acd97b8bced8d8c43f148c08472244abd34d3d37a6d0340c9ec738756a10d4ca`

最终累计吞吐 1.113950 questions/s/chip，1 chip，reserved memory 17.587891 GiB。原生温度下，Kev-9B accuracy 68.05% 对 Open-Jev-9B 67.80%，但后者 noul accuracy 较高；分项差异必须保留，0.25 个百分点的总体差距没有显著性或机制因果结论。该集合六模型完成不代表 JEVal／原始 OOD 完成，也不是我们的训练增益。
