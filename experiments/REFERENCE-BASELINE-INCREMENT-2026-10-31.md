# 参考基线固定矩阵的带日期增量（2026-10-31）

初始记录截点：2026-10-30T22:40:21.856599+00:00。本文件为旧 [30 个组合／58 个面板快照](REFERENCE-BASELINE-MATRIX-2026-10-31.md) 的增量索引，不覆盖旧矩阵、旧 pending 记录或预注册。首次增量为4个组合；随后新增Kev-4B/9B测量，当前共新增 **6 个模型×数据集结果组合**：其中4个已完成实际Astra限定审查、2个科学发布审查待完成。与旧快照合计有结果索引的组合为 **36 个**，证据等级仍逐项保留，不能据此宣称所有参考实验完成。

最后内容更新：2026-10-31 北京时间，包含22:43:17Z形成的Kev-4B/9B正式测量；第5节为该后续增量，科学发布审查仍待完成。

## 1. D1 登记范围的交接

| 原登记组 | 组合数 | 本次状态 | 入口 |
| --- | ---: | --- | --- |
| 旧 Kev 原生 test | 15 | 旧结果保留；历史终态绑定范围未升级 | [旧矩阵§1](REFERENCE-BASELINE-MATRIX-2026-10-31.md) |
| 旧 Nimble 原生 test | 7 | 旧结果保留 | [旧矩阵§2](REFERENCE-BASELINE-MATRIX-2026-10-31.md) |
| 旧 Typed 共同 test | 6 | 旧结果和实际 Astra 限定审查保留 | [Typed审查](ASTRA-TYPED-RESULTS-REVIEW-2026-10-31.md) |
| 旧 Open-Jev 原始 test | 2 | 旧结果保留 | [旧矩阵§4](REFERENCE-BASELINE-MATRIX-2026-10-31.md) |
| Kev-0.8B / Nimble × JEVal | 2 | 本次新增；Astra有界支持发布，6/30 flags保留，原因勘误已记录 | [JEVal结果](JEVAL-REFERENCE-RESULTS-2026-10-31.md) |
| Open-Jev-2B / 9B × 原始 OOD | 2 | 本次新增；两尺寸实际Astra有界审查完成，0/3主面板flags | [OOD审查](ASTRA-OPENJEV-OOD-RESULTS-REVIEW-2026-10-31.md) |
| Kev-4B / 9B × JEVal | 2 | 强化审计、closeout与正式结果已完成；科学发布审查pending（8/7 flags） | [Kev4/9结果](JEVAL-KEV4-KEV9-RESULTS-2026-10-31.md) |
| Open-Jev-2B / 9B × JEVal | 2 | 数值准入blocked，指标null；E36/E37 admission=false | [E37诊断](OPENJEV-BATCH-DIAGNOSTIC-RESULTS-2026-10-31.md) |

上述为原先30个有结果组合和8个未完单元的明确交接，不是全部兼容模型×数据集笛卡尔积完成。Kev4/9状态来自主会话核验交接：强化审计4B于22:30:19Z、9B于22:31:50Z完成，保留8/7 flags；closeout v2在22:39:12Z摘要为22,514/22,514完成。此后正式结果文档于22:43:17Z形成，新增分数见下方dated段落；实际Astra仍待完成，旧Kev08/Nimble审查不覆盖这两个checkpoint。E38处于诊断路径，其结果不能自动解除JEVal准入阻塞。

## 2. JEVal 原始 test：新增两个组合

完整人口为11,257行，classification=10,938，score=319。accuracy使用完整分类分母；Brier/ECE/MAE使用各自有效人口。表内分母不能互换，也不能把有效子集视作两模型相同题目的受控比较。

| 模型 | native温度 | 正确/全分类 | accuracy% | 有效分类n | raw summed Brier | ECE10 | score MAE | 有效score/全score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kev-0.8B | 2.35109581257 | 5089/10938 | 46.525873 | 9911 | 0.598302104 | 0.163216356 | 1.121768025 | 319/319 |
| Nimble v1 | 1 | 5394/10938 | 49.314317 | 7694 | 0.433576240 | 0.135360806 | 0.842948718 | 312/319 |

Kev有1,027条overlength。Nimble有2,253条unsupported，准确拆分为 **2,047条候选数超限、206条空context**（ARC-Challenge95、ARC-Easy111），另有998条overlength。原closeout README的候选超限单一归因已有追加勘误，冻结证据未改动。Kev longbench-retrieval-en为200/200 overlength，valid-only accuracy为null；Nimble CUAD有效子集31/31，但完整cell31/200=15.5%，另169条超长。

分类按实际choice或noul≥0.5计分，不支持/超长按全分母错误计入。Brier为原生wire概率对one-hot的平方差之和，不重新归一化；noul重建[1−p,p]。ECE10使用Kev chance-adjusted choice confidence、Nimble selected probability、noul已选二元概率，分箱`min(int(10c),9)`。Kev score为原生期望等级（保留响应精度），Nimble为选中整数等级；MAE以原等级单位计算。未追加raw T=1、NOTA或permuted结果。

## 3. Open-Jev 原始 OOD：新增两个组合

同一原始release-v2 OOD共15,920行：hard15,446、soft474，包含恢复的219条Wikispeedia；不是15,701行公开投影或10,532行test。hard正确数2B为13,288、9B为14,207。

| 模型/计分 | 温度 | hard accuracy% | expected accuracy% | NLL | Brier | expected Brier | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Open-Jev-2B/serving | 1.51879634286 | 86.028745 | 84.616890 | 0.802074062 | 0.246288900 | 0.263619640 | 0.105578241 |
| Open-Jev-2B/raw_T1 | 1 | 86.028745 | 84.616890 | 1.156734154 | 0.254766583 | 0.272097322 | 0.119212764 |
| Open-Jev-9B/serving | 1.89691187663 | 91.978506 | 90.413799 | 0.299676558 | 0.126747550 | 0.144078290 | 0.037592607 |
| Open-Jev-9B/raw_T1 | 1 | 91.978506 | 90.413799 | 0.451535465 | 0.137554553 | 0.154885293 | 0.058512809 |

hard accuracy仅对15,446条one-hot行；expected accuracy为全部15,920行的`q[argmax(p)]`均值。`p=softmax(logits/T)`；NLL自然对数及1e−15下限，Brier对候选维度求和，expected Brier加`1−Σq²`。ECE15用最大概率与expected correctness，15等宽箱`min(floor(15c),14)`，与JEVal的ECE10不是同定义。

coverage阈值为0.5/0.7/0.8/0.9/0.95/0.99，使用最大概率≥阈值；coverage分母为对应面板全体行，selected accuracy仅以入选hard行为分母，expected accuracy以全体入选行为分母，无定义保持null。JSON保留总体两温度、native来源与题型全部分项及coverage值，来源/题型均不当作独立推理次数。

2B原审计0个主面板flags不代表所有coverage子格没有精确边界；9B保留3个flags：customer-control hard560/560，以及agent_trace_observability hard/expected525/525。后者两标记来自同一面板；group结构也不支持把所有行当作独立业务场景。审查未发现计分/缺失等错误，不证明无数据污染。

## 4. 面板计数、审查证据与可比边界

本增量只计新增6个模型×数据集组合（4个已实际Astra限定审查、2个待审查）；**不把展示行直接相加到旧58面板**。OOD展示4个总体模型×温度计分面板，它们来自2次保存推理；JEVal每模型含分类和score，且全分母/有效分母不同，因此这里不设跨协议“新增面板总数”（JSON为null）。不能把温度重算当重复稳定性实验。

| 证据 | 实际Astra原文SHA-256 | 冻结包MANIFEST SHA-256 |
| --- | --- | --- |
| JEVal Kev/Nimble | `a2bbbd95d1627b1196347d0aaa5ce8a89009499e6cd80c9484abb55ee5d946f9` | `a4f9ec8476dfca250244d1b6372467c1b1d1787de41874663a376a4e27cfca5d` |
| Open-Jev两尺寸OOD | `cbea46b7695117328836dbca5745505c83d718819b5fa7c17ab0f912736c5bc9` | `cc46408dcf5d0482fd4d1b84c8ad39d48d72433791cd6f67a6ba4d8ea4cbac26` |

[JEVal实际审查](ASTRA-JEVAL-RESULTS-REVIEW-2026-10-31.md)与[OOD实际审查](ASTRA-OPENJEV-OOD-RESULTS-REVIEW-2026-10-31.md)保留完整原文、真实runner/child退出和限制。指标、报告、审查记录的路径、SHA和JSON pointer见[机器索引](REFERENCE-BASELINE-INCREMENT-2026-10-31.json)。本增量读取各自独立验收报告，实际Astra状态逐项列明；不重新计分或创建实验结果。

Open-Jev两尺寸覆盖相同OOD，可描述其参考差异；仍不能视作新训练处理的收益。JEVal有效子集因原生接口预算不同，概率指标不构成同题受控比较。不同数据集、不同Brier/ECE定义不求总平均。没有训练收益、真实业务收益、paired consistency、精确论文复现或无污染证明。旧28个Kev面板的历史审计终态绑定缺口仍保留。D1要求继续完成余下登记组合或明确其影响，再讨论Jev训练方案。

## 5. 2026-10-31 后续测量增量：Kev-4B/9B JEVal，科学发布审查待完成

来源为[正式结果](JEVAL-KEV4-KEV9-RESULTS-2026-10-31.md)，closeout于22:39:12Z完成22,514条回执，report SHA `8d2af0809eda8d1c7772051b33b91bb30e864fae8d972c119810109417de0649`。下面是已有测量，尚不能称这两模型获得实际Astra发布结论。

| 模型 | native温度 | 正确/全分类 | accuracy% | 有效分类n | Brier | ECE10 | score MAE | 有效score/全score | flags |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kev-4B | 2.40605007216 | 6741/10938 | 61.629183 | 9911 | 0.436118754 | 0.173661124 | 0.914080878 | 319/319 | 8 |
| Kev-9B | 2.19364995939 | 6931/10938 | 63.366246 | 9911 | 0.406847145 | 0.109838099 | 0.923336991 | 319/319 | 7 |

口径与第2节冻结JEVal协议相同；各有1,027条overlength。两模型审计状态保持 `VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED`。这里不从尺寸差异推导训练收益，不沿用Kev-0.8B/Nimble的Astra结论。Open-Jev两尺寸JEVal依然是blocked/null，旧30组合/58面板快照原样保留。
