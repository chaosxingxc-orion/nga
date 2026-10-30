# 参考模型在现有数据集上的测试指标汇总

日期：2026-10-30。状态：**本地镜像中已发布测试结果的统计，未进行新的模型推理或训练**。当前目标按[用户决定](../proposal/04-reference-test-first-decisions-2026-10-30.md)：先看参考结果和不同计算口径，再讨论 Jev 训练方案。

这里的“未进行新推理”描述本表的数值来源，不是暂停推理的决定。用户已明确要求自动驱动与实际推理评测继续完成；执行顺序和最新探测进度见 [指令逻辑与执行次序](../proposal/05-instruction-order-and-execution-2026-10-30.md)。

审查状态：已发起指定 `gpt-6-astra` 的只读对抗审查，但返回仅为规则确认，没有实质意见，**不算 Astra 审查通过**。下表作为带来源和限制的参考统计交付；不构成 NGA 实验结果发布或模型采用放行。

本报告分别呈现官方 test、公开 evaluation／challenge 和内部 holdout；不能把三者合并为同一个榜单。没有报告的模型×数据集单元为缺失，不能填 0，也不能拿 dev 数字代替。27B 等较大模型作为文献参考保留，不代表决定训练这些尺寸。

## 1. 能直接回答什么

现有镜像包括 24 个数据仓库和 42 个模型目录；部分参考模型只有上游结果，没有本地 checkpoint。已存在足够多的 test 证据来比较准确率、概率质量、成对全部正确、扰动敏感性和成本边界，暂不需要先训练 NGA 模型才能形成参考表。

最重要的口径差异有四个：

1. **同样叫 accuracy，分母不同。** Kev 是 question micro；akhilaaa3 是 state macro；DecisionPivot headline 是 family macro，pair accuracy 又要求整组全部正确。
2. **同样叫 Brier，目标不同。** Kev 使用 one-hot；typed-decisions 使用标签概率分布；Open-Jev 另报 expected Brier。它们不能直接排同一名次。
3. **同样是同一个模型，推理设置不同。** Tev 原生 prompt 与 Jevify prompt 要分行；Kev 原 locked 记录与服务温度重统计的概率分数要分列。
4. **同样叫测试，暴露范围不同。** train-fitted 与 zero-shot、内部扩充集合与公开投影、curated 与 full、旧版本与新版不能混合。

下列数值是引用上游结果或从上游结构化报告直接提取；不是本项目复现成绩，也不证明本项目已经获得训练收益。

## 2. Kev：五套 test 的问题级准确率

每格为百分比；按问题等权，clean 主表排除 permuted／NOTA 变体。原生 pointer head，argmax tie 取第一个最大项。

| test 数据集 | n（问题） | Kev-0.8B | Kev-4B | Kev-9B v2 | Kev-27B v2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| decision-v7 clean | 1,200 | 83.750 | 86.500 | 87.250 | 86.583 |
| transfer-v4 clean | 656 | 69.665 | 83.841 | 85.213 | 88.872 |
| hard-v1 | 1,088 | 66.544 | 80.331 | 83.364 | 91.820 |
| devtools-v1，全来源 | 1,071 | 63.679 | 75.630 | 79.085 | 78.992 |
| documents-v1 | 936 | 85.150 | 90.278 | 89.957 | 90.812 |

**Jev 在 decision-v7／transfer-v4 没有已发布 test 值。** README 的 0.845／0.857 是 dev，不填入这张表。2B 没有该 Kev 官方模型行。

来源：本地 Kev repo `runs/release/{kev-08b-r15,kev-4b-r10,kev-9b-r27,kev-27b-r23}.json` 的 `candidate` 对应字段；4B documents 来自 `runs/fam-4b-docs1test/report.json`；27B decision 来自 `runs/locked/kev-27b-r23-ungated/summary.json`。这两处补充仅用于该准确率，不推定服务温度概率指标已齐全。源码和数据口径详见 [KEV-PROTOCOL](KEV-PROTOCOL.md)。

### 2.1 同一 transfer-v4 test 的不同温度结果

| 模型 | locked 原记录 Brier | 服务温度 Brier | 服务温度 ECE10 | 高置信错误／全样本 | 经验 error≤5% 最大 coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kev-0.8B | 0.416460 | 0.396632 | 0.044841 | 0.000000 | 0.274390 |
| Kev-4B | 0.241904 | 0.224210 | 0.016767 | 0.015244 | 0.701220 |
| Kev-9B v2 | 0.216532 | 0.199036 | 0.034421 | 0.013720 | 0.742378 |
| Kev-27B v2 | 0.155554 | 0.153696 | 0.018741 | 0.007622 | 0.875000 |

这里不是两种 Brier 定义，而是 `scripts/release_numbers.py` 按 checkpoint 服务温度重算后的两组值。温度分别约 2.35110、2.40605、2.19365、1.31951；本次没有重新拟合温度。positive temperature 不改 argmax，但改变概率指标。

高置信错误指 `P(max p≥0.9 且预测错误)`，分母是全部样本，不是高置信子集。0.8B 的零值也不意味着所有判断可靠，应结合 coverage 和原始计数审查。最后一列按 test 的置信度排序，求经验错误率符合预算的最长前缀，是事后诊断，不是预先验证的生产自动执行阈值。

### 2.2 breadth-v1：同一批 3,089 问题的三种统计

| 模型 | 问题 micro accuracy | 分层 raw score（0–1） | chance-corrected index（0–100） |
| --- | ---: | ---: | ---: |
| Kev-0.8B | 0.586274 | 0.457458 | 23.3391 |
| Kev-4B | 0.689867 | 0.572000 | 38.0256 |
| Kev-9B v2 | 0.698284 | 0.590542 | 40.9833 |
| Kev-27B v2 | 0.756879 | 0.670472 | 52.2941 |
| Jev | 0.756556 | 0.680736 | 54.0494 |
| AutoJev | 0.748462 | 0.656069 | 49.9575 |

该 panel 的 14 个数据集分成五个 area。每数据集先算 `skill=clip((score−chance)/(1−chance),0,1)`，area 内等权，再对五个 area 等权，乘 100。raw score 保留相同分层聚合但不做 chance correction。SATA／BFCL 用 record exact match，其余用 question accuracy。

| 子集 | 原始计分单位 | Kev-0.8B | Kev-4B | Kev-9B v2 | Kev-27B v2 | Jev |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| musr | 150 问题 | .466667 | .600000 | .613333 | .673333 | .673333 |
| sata_bench | 150 案例，全部问题对才对 | .186667 | .346667 | .333333 | .420000 | .333333 |
| chessbench | 150 问题 | .166667 | .140000 | .206667 | .246667 | .253333 |
| contractnli | 160 问题 | .381250 | .550000 | .718750 | .762500 | .806250 |
| hellaswag | 150 问题 | .513333 | .706667 | .753333 | .873333 | .880000 |
| clinc150 | 150 问题 | .740000 | .793333 | .813333 | .913333 | .953333 |
| sgd | 150 问题 | .486667 | .673333 | .653333 | .720000 | .733333 |
| bright | 150 问题 | .353333 | .526667 | .600000 | .680000 | .720000 |
| bfcl | 150 案例，全部问题对才对 | .706667 | .900000 | .913333 | .933333 | .913333 |
| toolret | 150 问题 | .533333 | .586667 | .553333 | .640000 | .626667 |
| apibank | 150 问题 | .766667 | .893333 | .953333 | .946667 | .926667 |
| routerbench | 150 问题 | .340000 | .346667 | .180000 | .306667 | .380000 |
| humicroedit | 150 问题 | .440000 | .540000 | .473333 | .566667 | .593333 |
| cfcolor | 150 问题 | .466667 | .506667 | .513333 | .653333 | .660000 |

来源为 `runs/fam-breadth-test-report/report.json` 与 `runs/r23-breadth-report/report.json`；后者提供 Jev／AutoJev。原始题目分区在私有 mirror，本地有 manifest 和报告不能自动意味着可以逐字节复跑。本 panel 与 Decision Index 官方不同 edition 不混合。

## 3. JEVal：同一公开 test 上的多模型结果

完整 test 有 11,257 样本，其中 10,938 个 choice／noul 用于以下分类指标；319 个 score 单独评估。accuracy 将无效回答计错；ECE 和 Brier 只使用有效回答，二者的分母并不相同。该集合包含英文和中文，不能冒称英文单语结果。

| 模型 | 模式 | ACC % | ECE | raw Brier |
| --- | --- | ---: | ---: | ---: |
| Jev | Decision | 78.38 | .0532 | .287 |
| Kev-0.8B | Decision | 49.63 | .0432 | .617 |
| Kev-4B | Decision | 68.90 | .0843 | .435 |
| Kev-9B | Decision | 70.87 | .0579 | .404 |
| Kev-27B | Decision | 77.17 | .0356 | .304 |
| Intern-Decision-0.8B | Decision | 47.71 | .0635 | .643 |
| Intern-Decision-2B | Decision | 55.72 | .0214 | .553 |
| Intern-Decision-4B | Decision | 70.74 | .0152 | .399 |
| Laya | Decision | 26.30 | .2485 | .833 |
| Openjev-4b-v5 | Decision | 70.20 | .1472 | .481 |
| Nimble-9B | Decision | 73.87 | .1045 | .369 |
| Nanojev | Decision | 25.34 | .1300 | .806 |
| Lightjev | Decision | 37.20 | .1145 | .742 |
| Jevforge-0.8B | Decision | 31.04 | .1164 | .794 |
| InnerJev-4B | Decision | 71.92 | .0843 | .383 |
| InnerJev-27B | Decision | 79.24 | .0149 | .279 |
| Qwen3.5-4B | Non-thinking | 61.37 | .2526 | .781 |
| Qwen3.8-27B | Non-thinking | 73.81 | .1697 | .446 |
| DeepSeek-V4-Flash | Non-thinking | 72.83 | .1923 | .494 |
| GPT-6-Luna | Non-thinking | 80.93 | .1159 | .297 |
| GPT-6-Sol | Non-thinking | 79.92 | .1309 | .322 |
| Qwen3.5-4B | Thinking/default | 70.73 | .1716 | .489 |
| Qwen3.8-27B | Thinking/xhigh | 79.49 | .1005 | .319 |
| DeepSeek-V4-Flash | Thinking/high | 79.69 | .1449 | .382 |
| GLM-5.3-Flash | Thinking/high | 80.37 | .0784 | .316 |

来源：`carlosxiang__JEVal/README.md` Main results，原论文 [2610.03935v1 Table 1](https://arxiv.org/pdf/2610.03935v1#page=6)。ECE 的精确实现尚需对应论文／源码确认，不能默认等于 Kev 的 ECE10。Openjev-4b-v5 的名字也不能自动映射到 ZefanCai 的 2B／9B。

## 4. 已有任务三来源：typed-decisions、DecisionBench、Open-Jev

### 4.1 typed-decisions 官方 test

400 cases × 5 questions＝2,000 decisions。这里是原始官方 test，不是 NGA `group70` 或 T1–T3 派生分区。完整零样本与 train-fitted 两张榜保存在来源附录；以下列出代表性行和退化对照。

| 模型 | 使用范围 | Accuracy | KL from gold | Brier | ECE |
| --- | --- | ---: | ---: | ---: | ---: |
| Quyet-1.0-Large | general zero-shot | .791 | .281 | .114 | .093 |
| meraGPT Decider 1 | general zero-shot | .768 | .096 | .052 | .180 |
| Amos 1 medium 9B | general zero-shot | .7645 | .151 | .080 | .103 |
| d3-mini 4B | general zero-shot | .743 | .319 | .123 | .047 |
| TypeSafe Jev 1.13.0 | general zero-shot | .727 | 1.442 | .148 | .144 |
| d3-nano 2B | general zero-shot | .629 | .545 | .211 | .113 |
| d3-lite 0.8B | general zero-shot | .531 | .518 | .244 | .130 |
| Prior，忽略 input | 对照 | .470 | .347 | .189 | .088 |
| Uniform | 对照 | .308 | .444 | .238 | .169 |

其 scorer 将模型分布归一化，accuracy 比较预测和 gold 分布的 argmax；`KL=Σq log(q/p)`，`Brier=Σ(p−q)²`，再按问题平均；ECE10 基于 max probability 和 argmax 是否相同。gold 是分布而非 one-hot，所以不能与 Kev Brier 直接比较。来源：`LocalLLaMA__typed-decisions/README.md` 与 `bench/score_with_jobs.py:24–41,84–104`。

Laya 的独立审计在同一 2,000 decisions 上报告：未微调 accuracy .360／ECE .175；该任务微调后 .767／.212；引用 Jev .727／.144。微调与零样本必须分层。这组结果能说明 accuracy 与校准可能朝不同方向变化，不能据此认定记忆噪声或真实业务收益已被因果证明。

### 4.2 akhilaaa3 DecisionBench：state macro

每个 medium／hard 分区 80 situations、293 questions；先计算每场景 accuracy，再等权平均场景，缺回答排除。不同 request shape 的成本不直接比较。

| 模型 | medium accuracy % | medium ECE | hard accuracy % | hard ECE |
| --- | ---: | ---: | ---: | ---: |
| Gemini 3.8 Flash | 99.12 | .0067 | 96.04 | .0093 |
| Claude Sonnet 5 | 99.12 | .1116 | 88.35 | .1365 |
| GPT-5.6 Luna | 98.76 | .0044 | 85.92 | .0748 |
| Jev 1.13 | 90.48 | .0324 | 65.26 | .1204 |

来源：`akhilaaa3__decision-bench/README.md` Technical details。Jev 每问题一请求，chat 模型每场景一请求。旧 Jev batched medium 89.10% 已被原作者从成本图撤回，不作为当前主行。ECE 分箱细节未由本次源码核对，不冒称与其他 ECE 一致。

### 4.3 Open-Jev：hard accuracy 与 expected accuracy

| 模型 | 分区 | 全行数／hard 行数 | hard accuracy % | expected accuracy % | NLL | Brier | ECE15 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Open-Jev 2B | Test | 10,532／10,046 | 94.71 | 91.95 | .195380 | .076117 | .011606 |
| Open-Jev 2B | OOD | 15,920／15,446 | 86.02 | 84.62 | .802990 | .246450 | .105594 |
| Open-Jev 9B | Test | 10,532／10,046 | 97.54 | 94.72 | .130947 | .039113 | .007707 |
| Open-Jev 9B | OOD | 15,920／15,446 | 91.97 | 90.40 | .299441 | .126647 | .037398 |

hard accuracy 只统计 one-hot targets；expected accuracy 是所有行 `q[argmax p]` 的均值。Brier 对目标分布 q 计算；expected Brier 另外加 `1−Σq²`。ECE15 的 correctness 可为软目标质量，不等于 Kev ECE10 的 0／1 correctness。

27B v1.1 另有内部 expanded Test：41,357／42,789 hard 正确＝96.65%，OOD：80,934／83,924＝96.44%；这不是上表的同一分母。old Test／OOD 是 expanded 的子集，不能相加；公开 v1.1 投影剔除了部分 Wiki 数据，不可宣称完整内部总分就是公开投影总分。2B／9B 无对应 expanded 结果。

来源：本地 `Zefan-Cai__Open-Jev/reports/full-data-eval-n1-v1/`、`docs/internal-full-evaluation.md` 及模型目录 `evaluation/full-data.json`。没有同口径全数据 base 对照，仅凭这些总分不能推定训练带来的增益。

## 5. Jevify：同一 22,773 test records 的不同 readout／prompt

22 configs；本表保留上游字段 `summary.macro`：先计算每 config 指标，再等权平均 22 configs。本次用 Jev 的 `test_metrics.json` 复核得到相同宏均值；其按样本数加权 accuracy 则为 0.723532，与宏平均 0.732644 不同。ECE 的 config 加权均值也不等于把全部预测重新分箱的 pooled ECE。完整 46 个设置及各 primitive／config 的字段在结构化附件中。

| 模型／设置 | macro accuracy | macro ECE | macro Brier | sel90 |
| --- | ---: | ---: | ---: | ---: |
| Jev 1.13.0 API | .732644 | .113312 | .348522 | .759548 |
| Qwen3.5-9B，readout LoRA + coherence | .762929 | .056154 | .299203 | .790671 |
| Qwen3.5-4B，readout LoRA + coherence，seed 0 | .750926 | .057591 | .315566 | .779068 |
| Qwen3.5-4B-Base，readout LoRA | .740925 | .063568 | .324037 | .769546 |
| Qwen3.5-4B-Base，readout LoRA + coherence | .746912 | .058435 | .317806 | .776780 |
| Tev1-4B，Tev1 prompt | .703324 | .086099 | .360530 | .732281 |
| Tev1-4B，Jevify prompt | .690025 | .087742 | .369037 | .717731 |
| Qwen3.5-4B，Tev1 prompt | .673256 | .104086 | .401912 | .701539 |
| Qwen3.5-2B，Tier 1 residual | .631992 | .068793 | .444786 | .656553 |

`sel90` 指保留 90% coverage 时的准确率，**不是 confidence≥0.9**。ECE15 与前述 ECE10 不混；noul／choice 的 Brier 维度及 soft-label 指标在其分项表中保留。此处均是 Jevify 上游训练／测评结果，不能冠名 NGA 已训练完成。

**2026-10-30 补充复算：** 全部 46 个设置已映射到 52 个源 `test_metrics.json`，共 1,012 个设置×config 行；各设置的原 macro 指标均在绝对差 `1e-12` 内复现，无缺失映射。另计算按问题数加权的 accuracy／Brier，例：Jev macro accuracy 为 0.732643714，问题加权为 0.723532253；macro Brier 为 0.348521971，问题加权为 0.357255034。两条多 seed 汇总按显式 seed 等权，重复测试题不计为新增独立样本。

完整分项与公式见 [Jevify 分口径重算表](/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/jevify_reaggregation.md)，可用 [重算脚本](../tools/reaggregate_jevify_reference.py) 复现。附录中的加权 config ECE **不是 pooled ECE**，加权 config sel90 **不是全体样本重排序后的 selective accuracy**；只凭聚合文件无法重建这两项全局指标。已独立核查 52 个来源哈希和各源 accuracy／Brier 加权运算；这仍是已发布结果复算，不是本地模型推理成绩。

来源：`Praveenrajus__jev-bench/results/leaderboard/leaderboard.json`；逐 config 位于各 run 的 `test_metrics.json`。Tev 两行同时改变了 prompt、各类型温度与 noul bias，因此是不同 prompt 与各自校准配置的联合结果，不能把差值归因于 prompt 单一因素；后续训练对照须控制这些配置。

## 6. 更接近规则执行和稳定性目标的 evaluation

### 6.1 DecisionPivot：单题正确不等于成对全部正确

本表是 core evaluation，保留上游 family-macro headline；不是另造的 test 划分。所有值按百分数报告。训练匹配任务类型的行与 zero-shot 行不能混称同等泛化。

| 设置 | accuracy | pair accuracy | level-3 pair accuracy | auto_at_5 | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: |
| hosted Jev 1.13.0 | 63.9 | 31.0 | 15.9 | 19.3 | 14.9 |
| Kev 27B | 70.6 | 44.2 | 26.5 | 35.2 | 9.2 |
| 4B starting model，同 readout 未训练 | 43.1 | 6.1 | 4.5 | 2.0 | 20.2 |
| 4B Instant final，kind-matched training | 66.6 | 40.2 | 27.9 | 31.1 | 8.8 |
| 9B starting model，同 readout 未训练 | 46.0 | 8.4 | 3.4 | 3.3 | 23.6 |
| 9B Instant final，kind-matched training | 69.0 | 43.3 | 30.2 | 35.3 | 8.3 |
| 27B Instant final，kind-matched training | 85.1 | 73.1 | 61.3 | 77.2 | 5.9 |

pair accuracy＝组内所有成员都对的组比例；pair direction 则比较正负成员 P(yes) 的大小，两者不同。auto_at_5 为 test／eval 上事后错误率前缀诊断，不能直接作为部署收益承诺。上游 95% bootstrap 区间、family 列表、其他设置保留在原 CSV，不因主表简写而删掉。

来源：`startlux-models__DecisionPivot/tables/T1_core_headline_intervals.csv` 和 `jev113_core_headline.csv`。原 CSV 某些 ECE 点估计在所报区间之外，当前原样保留；没有独立复算前不据其区间作显著性断言。

### 6.2 DecisionRobust：攻击成功与普通 flip 分开

本地有 `asr.csv`、`flip_asr.csv`，主表各配置行保留原始分子、分母、有效／排除 pairs、是否用于选择和版本。分母是 **clean-correct 且输出有效的 attack candidates**，不是所有独立原题。

- semantic／image perturbation 关注 Flip ASR；injection 另有 Target ASR，不能互换。
- curated 与 full 重叠，不能拼起来增加样本量。
- `used_for_selection=true` 的结果必须带选择暴露标记；v1.2／v1.3 和部分覆盖不合并。
- 缺结果不填零；不将低 ASR 单独当作正确性，必须同时看 clean accuracy。

例如旧 `text_adversarial_curated` 的 Jev 1.13 行为 100／138＝0.724638，`used_for_selection=true`；这是该攻击配置的 Flip ASR，不是模型总体错误率，也不是无偏完整测试结论。完整跨模型行在库存附件所指 CSV 中。

### 6.3 Safety challenge：类别准确率与置换稳定性

这是 SabaPivot 的 challenge，保留 original／reversed／repeat 及原始 benchmark test／validation 标记，不把所有 challenge 项都改名官方 test。

| 模型 | XSTest benign % | XSTest harmful % | OR-Hard benign % | OR-Toxic harmful % | HarmBench standard test harmful % |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original Jev | 93.60 | 94.00 | 33.89 | 92.06 | 100.00 |
| CLM | 83.20 | 83.50 | 31.99 | 96.03 | 98.74 |
| Laya | 67.20 | 67.00 | 91.28 | 41.68 | 57.86 |
| Open-Jev | 81.60 | 41.50 | 89.69 | 32.37 | 41.51 |
| Laya Multilingual | 52.00 | 61.50 | 86.13 | 31.60 | 67.30 |

来源：`SabaPivot__jev-safety-bench/README.md` Results at a glance。XSTest n 为 benign 250、harmful 200；其他子集原 n、unsupported 情况见来源附录。repeat 不进入 primary 分母。CLM 的 XSTest 置换 flip 为 0／450，也不能代替其分类正确率。本表衡量分类标签一致，不是实际拒绝行为或生产安全。

## 7. Nimble 和公开 JevBench 的分区边界

### 7.1 Nimble 上游公共 benchmark 中真正的 test 子集

| 子集 | n | Nimble-9B accuracy % | Jev 1.13 accuracy % |
| --- | ---: | ---: | ---: |
| massive-en-US test | 350 | 86.9 | 87.4 |
| massive-de-DE test，同 ids | 350 | 83.4 | 86.9 |
| paws test | 250 | 82.8 | 89.2 |
| civil_comments test | 300 | 70.3 | 81.0 |
| aegis2 test | 250 | 81.2 | 80.4 |
| summeval-consistency test 抽样 | 144 | 75.7 | 81.2 |
| summeval-relevance test 抽样 | 240 | 49.2 | 35.0 |

来源：`bespokelabsai__nimble/docs/PUBLIC_BENCHMARKS.md`。原汇总还包含 BoolQ／SQuAD2／HelpSteer2 validation、MNLI dev、VitaminC dev、PubMedQA train 抽样。因此原 3,880 行 macro 74.8%／76.0%、micro 75.9%／77.3% 只能叫混合分区汇总，不能叫全 test 成绩。

初始 Nimble 的合成 holdout 另有 324 行：292／324＝90.12%，base 215／324＝66.36%，Jev 302／324＝93.21%；合成标签、初始 checkpoint、不同精度限制须保留，不能套给 v3。Nimble v3 的 Decision Index **edition 0.2.1** 为 balanced_skill 56.88、balanced_raw 67.67；这与 Kev breadth-v1 或 Decision Index 0.4 的 Full score 都不是同一个指标。

### 7.2 JevBench public231

| 模型 | correct／231 | accuracy % | Brier | ECE10 |
| --- | ---: | ---: | ---: | ---: |
| Open-Jev 2B | 150 | 64.94 | .4751 | .1274 |
| Open-Jev 9B | 179 | 77.49 | .3219 | .0858 |
| Open-Jev 27B v1.1 | 197 | 85.28 | .2420 | 未报告 |
| Jev 1.13 | 200 | 86.58 | .1811 | .0318 |
| GPT-5.6 Luna | 206 | 89.18 | .2074 | .0932 |
| GPT-6 Astra | 231 | 100.00 | .0085 | .0149 |

来源：Open-Jev `docs/jevbench-public.md`、`site/jevbench.json`。只覆盖 231 个公开任务，不是完整 534；tie 为字典序最小标签，概率容差和无效处理与 Kev 不同。GPT 两行使用 verbalized probability，Open-Jev／Jev 使用 native probability；139 个 choice 中有 119 个的 native／GPT 候选顺序不同，上游明确 `order_controlled_comparison=false`。这些行不能支持严格同条件的概率质量优势结论。100% 为该小集合单次结果，需要检查覆盖、污染和测量过程，不能外推普遍能力。

## 8. 还缺哪些统计，为什么不填数字

| 数据／单元 | 当前状态 |
| --- | --- |
| 官方 Jev × Kev decision-v7／transfer-v4 test | 上游未报告；dev 不补位 |
| 某个参考模型 × 任意本地数据的完整笛卡尔积 | 现有公开结果没有全覆盖；尚未新跑推理，不伪造完整矩阵 |
| BEV、spatial、guardrails 等有 test 的集合 | 本地有数据／协议，但未在本次已核查材料中建立所有目标模型的结果与版本映射；按库存列待补，不填 0 |
| OneJev-Data、WebJev 的本地 train 集 | 不当作 test；不临时随机拆一个分区再冒称官方 test |
| Hanno、behavior-benchmark 等 eval | 保留 eval 命名和分母，不能直接并入 test 主表 |
| Open-Jev v1.1 完整内部集合 | 公开投影不完整，内部总分与公开投影区别保留 |
| 部分 ECE、Macro-F1、成本指标的精确实现 | 有源码则核对；只见表名则标定义未齐，不默认同义 |
| 所有本地复测 | 本报告未执行，不把导出 JSON 说成复现模型推理 |

本阶段参考 test 已用于训练方案研究。后续训练若受这些结果启发，必须披露该开发暴露，并设计独立确认或明确限定结论，不能重新声称所有参考 test 完全未见。

## 9. 文件与复核方式

本地根目录：

- Kev：`/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev/`。
- 其他 repo：`/mnt/cephfs/xingchao/omni/repos/jev/`。
- 数据与发布结果：`/mnt/cephfs/xingchao/omni/datasets/jev/`。
- 导出目录：`/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/`。

导出脚本为 [export_reference_test_metrics.py](../tools/export_reference_test_metrics.py) 与 [build_reference_tables.py](../tools/build_reference_tables.py)。输出保留源文件 SHA256、JSON pointer／表所在行、split 和历史版本，不能将全部导出字段数量视作独立指标数量。README 表附录同时包含数据统计和方法表，只有明确标为模型测试结果的表用于成绩。

可直接阅读的完整附件：

- [库存与文件哈希](REFERENCE-TEST-INVENTORY-2026-10-30.json)：24 数据镜像、42 个不同模型目录、源文件与导出产物索引。目录存在不证明权重内容或推理准入。
- [Open-Jev／Nimble 补充原始指标与分区说明](REFERENCE-TEST-ADDITIONAL-2026-10-30.json)。
- [各数据卡原表附录](/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/dataset_readme_tables.md)：23 张现有 README 的 91 张表，包含完整 typed-decisions 两榜、JEVal、DecisionBench 等；Kev 数据镜像本身无 README，使用 repo 来源。
- [跨模型完整统计表](/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/reference_panels.md)：Jevify 46 设置、DecisionPivot、DecisionRobust、韩语／英文评估等，保留所有模型设置行及主要成绩列；完整配置见 JSON。
- [分项机器可读 JSON](/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/reference_panels.json)：131 个原始聚合产物，含 Jevify 各 run 的逐 config test 指标，不含逐题预测。
- [Kev 服务温度 test CSV](/mnt/cephfs/xingchao/experiments/jev/_reference_inventory_20261030/kev_release_test_metrics.csv)：18 个 release panel；逐 panel 对照源 JSON 完全相等。

本次对上述附录的来源 hash 和 release 字段做了校验；这验证提取忠实度，不代替上游原始评测正确性。大型历史 Kev 导出包含大量中间候选与计数，仅作审计存档，不作为选出最佳模型的榜单。

主文表用于解释；结构化索引用于追溯；完整附录保留所有可提取模型行。此次统计不修改上游文件，不调用托管模型 API，不读取 NGA 尚未准入的 K0 指标，不启动新的训练。
