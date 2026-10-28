# 12 · 学习视角：学习算法有没有变、数据集是否可得、基座怎么选

> 口径：仍然只做分析与调研，不给训练方案。本章回答三个问题：（1）现有 Jev 类方案的**学习算法**相对"普通分类微调"有没有变化、调整或增强，证据是否支持这些改动；（2）训练与评测**数据集**是否公开可得、许可如何、本地已经拿到哪些；（3）**基座模型**的选型规律。02 章的配方矩阵按"项目"组织，本章按"学习算法族"重新切分，并把消融证据放在一起看。

## 12.1 学习算法谱系

把 02 章 30 余个配方和本轮补充的论文按"**训练什么、用什么目标、监督从哪来**"分成八族。每族给出代表、关键实现细节与出处；同一个项目可以落在多族（例如 StartLux 同时属于 C、E、F、G）。

| 族 | 核心思想 | 代表（骨干 / 关键细节） | 出处 |
| --- | --- | --- | --- |
| **A. 不训练：读出 + 后验校准** | 冻结 LLM，直接把合法选项的 logits 归一化；只拟合温度或先验 | LLM-as-Jev 免训练配方（联合上下文打分、并行后缀打分；冻结 4B 与现有免训练读出持平或更好）；Mapika decider-chat（Gemma-4-31B-it / Qwen3.6-27B 不改权重，按选项数拟合温度 T(n)=max(0.05, 10.124−1.633·ln n)，Decision Index 第 2）；AnyJev（与问题无关的仿射头 + 复用输出头，15 等质量分箱 ECE，旋转去偏）；Releasing the Inner Jev 零样本 Gemma 4 31B 79.6 对 Jev 80.1；LDM 诊断"未调优 27B 的读出达到调优后 97% 的准确率"；P(Yes) 测试时搜索（冻结模型、无训练，Qwen3.8-27B 逻辑谜题全对数 2→30）；RSAJEV 用原型记忆替换读出（零梯度更新，开集 AUROC 0.91–0.99）；JevCascade 的菜单限制预测器（零标签）；Runoff 两次前向的顺序无关读出 | [2610.02076](https://arxiv.org/abs/2610.02076)、[Mapika/decider](https://github.com/Mapika/decider)、[2610.00831](https://arxiv.org/abs/2610.00831)、[2610.17205](https://arxiv.org/abs/2610.17205)、[2610.15501](https://arxiv.org/abs/2610.15501)、[2610.25474](https://arxiv.org/abs/2610.25474)、[2610.15742](https://arxiv.org/abs/2610.15742)、[2610.07716](https://arxiv.org/abs/2610.07716)、[2610.18233](https://arxiv.org/abs/2610.18233) |
| **B. 硬标签交叉熵 + LoRA（主流）** | 和"把 LLM 当分类器微调"一样的目标，只是读出位置换成 LM-head 切片 / 字母 logit / 指针头 | Kev（Qwen3.5-Base 系，LoRA rank 16，交叉熵，2 epoch，`decision-v7`；可选的 `--perm_kl`、`--ord_w` 损失**发布模型未使用**）；Tev1（Qwen3.5-4B，LoRA SFT，输出答案字母，37,840 训练 + 4,568 验证）；Bespoke Nimble（Qwen3.5-9B，**只在答案 token 上**的 LoRA，2,676 条对比样本；90.1% 对基座 66.4%、Jev 93.2%）；Releasing the Inner Jev（字母读出 + 从 LM-head 切片初始化的决策头**联合**交叉熵，417,825 条池，400 步约 5 GPU 小时）；LDM 基线与 DDS 都是硬标签交叉熵；Chinese Decision（1 epoch，13.048M 决策）；DKnown-Jev（从 Qwen3.5-2B / Qwen3.8-27B 基座直接微调，1 epoch，27B 98.75% 高于 Jev 6.07 pp）；SecJev（场景加权训练）；Koa-decision（原子标签 token + SFT，单 token 受限生成）；SALSA（类别→token 映射 + PEFT，单遍只投影到类别 logits）；对照：解码器 + 分类头 vs 指令微调，头方案以少 10–30 倍可训参数持平 BERT | [jaredpalmer/kev](https://github.com/jaredpalmer/kev)、[togethercomputer/tev1](https://github.com/togethercomputer/tev1)、[bespokelabsai/nimble](https://github.com/bespokelabsai/nimble)、[2610.17205](https://arxiv.org/abs/2610.17205)、[2610.15501](https://arxiv.org/abs/2610.15501)、[2610.23170](https://arxiv.org/abs/2610.23170)、[2610.24358](https://arxiv.org/abs/2610.24358)、[2610.03073](https://arxiv.org/abs/2610.03073)、[2609.36115](https://arxiv.org/abs/2609.36115)、[2510.22691](https://arxiv.org/abs/2510.22691)、[2512.12677](https://arxiv.org/abs/2512.12677) |
| **C. 软标签 / 适当评分规则** | 把校准写进目标：Brier、软交叉熵、对分布而非 argmax 的损失 | jevlike（Qwen3-1.7B + LoRA + 37 个开源数据集，`CE + 0.5·Brier`；理由："交叉熵不知足，把 0.99 推到 0.999 仍有奖励"；基座要 T=8.881 才校准）；OneJev（交叉熵 + Brier，lr 5e-6，1 epoch，视觉塔冻结）；Open-Jev（LoRA + 标量决策头，**软交叉熵 + 0.1·Brier**，头从预训练的 Yes−No 读出初始化，温度只在校准集拟合）；Eikos / Our Own Jev（软目标 + 推理理由辅助损失 + 英/葡两个视图之间的对称 KL，权重 0.5；约 25K 决策）；Releasing the Inner Jev 池里 Civil Comments、Measuring Hate Speech 等用标注者投票做软目标，结论"**教师标签有用，软标签可能无用**"；SanSi / LEV 每个循环步都用适当评分规则训练；NDM 主张"标签已知时直接用适当评分规则"并给出集合值目标；ufakzeka-karar 输出温度缩放概率 + 期望误差作"不确定"信号；UniJev 先 SFT 再做 CORA（按置信分箱把置信拉向该箱实际准确率，无 RL 阶段） | [mustafasemi-ai/jevlike](https://github.com/mustafasemi-ai/jevlike)、[OmniJev/OneJev](https://github.com/OmniJev/OneJev)、[Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev)、[2610.29052](https://arxiv.org/abs/2610.29052)、[2610.17205](https://arxiv.org/abs/2610.17205)、[2610.07730](https://arxiv.org/abs/2610.07730)、[2610.20951](https://arxiv.org/abs/2610.20951)、[2610.25553](https://arxiv.org/abs/2610.25553)、[2610.06744](https://arxiv.org/abs/2610.06744)、[2610.25784](https://arxiv.org/abs/2610.25784) |
| **D. 蒸馏（教师概率 / 推理→读出）** | 监督来自更大模型、推理链或自身的推理模式，而非人工标签 | FunDM（**无标签**：用 KL 学冻结 Qwen3-8B 自身的答案分布，只用 36 层中的 24 层，八基准 75.0 对全模型 75.7）；LDM 的 SPRD（自提问任务，冻结 Qwen3.8-27B 教师每题采 4 条推理+答案，SPRD-C 过滤一致性后蒸馏投票分布）；SII-Decision 的 Reasoning-to-Readout 自蒸馏（把推理链末端的答案分布蒸馏进首 token）；法律领域把决策模型的概率**无标签**蒸馏进 Qwen3-8B 得到校准的本地模型；国际象棋双教师：Jev 与 Qwen3-32B 标签平均比全预算给 Qwen 多 9.6 Elo，"同一裁判再答一次不能替代第二个教师"；AgentDecision-4B 用 Jev 的答案做标签；Releasing the Inner Jev 教师为 Qwen3.5-122B-A10B 与 Qwen3.6-27B；Mapika 用本地 Qwen3.5-27B 教师标注；CT0 两阶段在线策略蒸馏（同一组权重同时服务 System 1 类型化决策与 System 2 Agent）；对照（编码器）：学生引导的教师蒸馏，ModernBERT 学生 + DeBERTa NLI 教师迭代 | [2610.17175](https://arxiv.org/abs/2610.17175)、[2610.15501](https://arxiv.org/abs/2610.15501)、[2610.03935](https://arxiv.org/abs/2610.03935)、[2610.29961](https://arxiv.org/abs/2610.29961)、[2610.09188](https://arxiv.org/abs/2610.09188)、[2610.21412](https://arxiv.org/abs/2610.21412)、[2610.17205](https://arxiv.org/abs/2610.17205)、[Mapika/decider](https://github.com/Mapika/decider)、[2610.16550](https://arxiv.org/abs/2610.16550)、[2610.02516](https://arxiv.org/abs/2610.02516) |
| **E. 结构感知 / 校准感知目标** | 在损失里显式编码位置、序数、证据必要性、分布锚 | PACT（成对锚定 + 证据必要性项 + 序数运输代价 + 三参数上下文温度；准确率 84.6 对已发布配方 85.2、仅交叉熵对照 82.2±6.0；重标注翻转 9.8 对 13.8%；NLL −26%；**"没有单一项提高原始准确率，价值在稳健性"**）；LLM-as-Jev 树分解列表式损失 + KL 锚（总分对锚强度不敏感，无锚则退化）；SHIFT-JEV 的 KL 锚 + 温度（偏移下校准误差 0.289→0.087）；CORA；StartLux 附录 B.4 直接概率优化与**策略感知校准**（184 种设置下置信-准确差 ≤2.7 pp，属后验）；Releasing the Inner Jev 的期望效用目标（对正确 / 错误 / 弃权分别计期望收益，比交叉熵 +0.9±0.9 pp）；Bongard 第二阶段 JEPA（学"判断背后的结构"，诊断"余弦对齐几乎没有信号"后换目标，保留集改写题 75.7%→85.9%）；Kev 的 `--perm_kl`（顺序）与 `--ord_w`（序数）损失（实现了，发布模型未用） | [2609.35865](https://arxiv.org/abs/2609.35865)、[2610.02076](https://arxiv.org/abs/2610.02076)、[2610.34329](https://arxiv.org/abs/2610.34329)、[2610.25784](https://arxiv.org/abs/2610.25784)、[2610.17309](https://arxiv.org/abs/2610.17309)、[2610.17205](https://arxiv.org/abs/2610.17205)、[2609.39111](https://arxiv.org/abs/2609.39111)、[jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| **F. 强化学习（各种"RLCD"）** | 以适当评分规则或正确性做奖励的策略梯度 | OpenJev-RLCD（Qwen3-1.7B；每条推理链之后读出模型承诺的分布，用严格适当评分规则打分；一行方差恒等式说明"对多样本混合打分"会奖励分歧、RLVR 恰是去掉多样性项的混合目标；端到端优化要么"System-One 坍塌"（用 KL 锚防止）要么被策略梯度项淹没（其梯度比读出大 7–12 倍）→ **先校准再强化**；GSM8K 答案验证单次查询在 ≤5% 错误下决定 81% 条目，GRPO 19%）；StartLux RLCD²（只用于 AutoThink：推理前后两次读出的适当评分之差做决策质量奖励 + 软长度惩罚；在限长内终止的推理占比最多 +48 pp）；UniJev 比较五种 RLCD（Shaped RLCD、GRPO、CtR、RLCD-lite、Rewarding Doubt）：相对共同的 2B SFT 初始化，各算法改变各模态准确率的幅度"**与监督转换带来的增益相比很小**"，校准效应异质；SBERT2S1（编码器）：开源 System One 模型发布的 RLCD 配方比交叉熵**低 2.5–3.0 点**，缺口主要来自奖励归一化把噪声得分函数项放大 3.6–15 倍，留一法无偏估计可收回大部分；ufakzeka-karar：REINFORCE 比交叉熵**低 10.2 个 macro-F1**；JevAgentHarness：Agent 循环内 GRPO 多花 4.5 GPU 小时与 26.53 美元 LLM 调用**无可测增益**，不先 SFT 时 GRPO 后 11.5% 对之前 13.5%；Bongard 第三阶段沙盒 RL（从动作 rollout 与精确 oracle 学结果分布，冻结沙盒面板 50.6%→64.8%）；Dyad（冻结 LLM 只用 RL 训动作编码器，四个未见环境一致提升）；S²-MAS（SFT + RLCD，2.93M 样本，421M 模型 74.55%）；NDM §8.1"为什么不用强化学习"：标签已知时适当评分规则直接优化**到达与 RLCD 式奖励的策略梯度相同的最优点而无其方差**；TypeSafe 自己的 RLCD **未公开** | [2609.38850](https://arxiv.org/abs/2609.38850)、[2610.17309](https://arxiv.org/abs/2610.17309)、[2610.25784](https://arxiv.org/abs/2610.25784)、[2610.02486](https://arxiv.org/abs/2610.02486)、[2610.06744](https://arxiv.org/abs/2610.06744)、[2610.21412](https://arxiv.org/abs/2610.21412)、[2609.39111](https://arxiv.org/abs/2609.39111)、[2609.36116](https://arxiv.org/abs/2609.36116)、[2610.27746](https://arxiv.org/abs/2610.27746)、[2610.25553](https://arxiv.org/abs/2610.25553)、[ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer) |
| **G. 结构改动（改"训练什么"）** | 改注意力掩码、读出位置、层数、循环或编码器 | 候选无关块因果注意力 + 位置重置（Gemma 3 1B 翻转率 8.30%→0.11%，Qwen3 1.7B 18.16%→1.20%；Qwen3-4B 250K 研究件）；Prism-1（每个选项独立块、共享位置、LoRA，块上 softmax 的交叉熵；Qwen3-8B / Gemma 4 12B；零翻转，换 Luce 公理成立）；StartLux Instant 在提示上做**双向注意力**（同数据同 Stage 1 检查点下 5 个尺度中 4 个提升，最多 +2.4 DI 点；随机种子方差 0.2–0.7）；SanSi / LEV 循环骨干 Ouro，**骨干冻结只训 LoRA + 小读出**，每个循环步读一次；Bongard 用 T5Gemma 2 4B-4B 编码器-解码器，**全参数** 7.09B 在一张 Blackwell 上三阶段训练；选择性适配（LoRA 只放注意力与 Gated DeltaNet 投影、去掉 FFN 适配器）+ mean-span 池化；FunDM 提前退出（24/36 层，跳过 LM-head）；Intern-Decision 在 JSON 骨架里放决策占位符，用自回归掩码 LM 一次前向读全部字段；System X 从 KV 缓存续写"文本回复"选项；Dyad 动作编码器；MetaEncoder 把 30B 解码器微调成双编码器做单向对比学习（面向百万级开集候选） | [2610.01601](https://arxiv.org/abs/2610.01601)、[2610.22066](https://arxiv.org/abs/2610.22066)、[2610.17309](https://arxiv.org/abs/2610.17309)、[2610.07730](https://arxiv.org/abs/2610.07730)、[2610.20951](https://arxiv.org/abs/2610.20951)、[2609.39111](https://arxiv.org/abs/2609.39111)、[2610.35654](https://arxiv.org/abs/2610.35654)、[2610.17175](https://arxiv.org/abs/2610.17175)、[2610.22131](https://arxiv.org/abs/2610.22131)、[2610.25456](https://arxiv.org/abs/2610.25456)、[2609.36116](https://arxiv.org/abs/2609.36116)、[2610.11316](https://arxiv.org/abs/2610.11316) |
| **H. 持续学习 / 测试时适应** | 不重训或少重训地吸收新反馈 | Kev `--init_from`（从发布适配器与指针头继续训，README 称从基座重训会"丢掉 Kev 已学到的"）；SHIFT-JEV 增益门控的持续适应（Qwen3-0.6B 上 70.5%，每个种子都高于回放 / LwF / EWC / 微调；Qwen3-4B 上保守门控落后 0.4–1.4 点）；Jev-DLC 决策级持续学习（类型化反馈→有界因果状态，见 07 章）；TORSI 双时标：慢教师在暂停的游戏里研究失败并写可复用指令给快学生，Jev 平均分 13.51→24.19；P(Yes) 测试时搜索；Open-Jev 的时间窗回归对照 | [jaredpalmer/kev](https://github.com/jaredpalmer/kev)、[2610.34329](https://arxiv.org/abs/2610.34329)、[2610.31521](https://arxiv.org/abs/2610.31521)、[2610.20665](https://arxiv.org/abs/2610.20665)、[2610.25474](https://arxiv.org/abs/2610.25474)、[Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev) |

## 12.2 相对"普通分类微调"到底改了什么

把八族放在一起看，变化集中在五个位置，而不是"换了一种学习算法"：

1. **读出位置变了，分类头几乎消失。** 主流不再新建分类头，而是复用预训练输出层：字母 logit（Tev1、Chinese Decision、LLM-as-Jev）、LM-head 切片初始化的决策头（Releasing the Inner Jev）、从 Yes−No 读出初始化的标量头（Open-Jev）、指针头（Kev、Our Own Jev）、与问题无关的仿射头（AnyJev）。支持这样做的证据是"决策大部分已经在表示里"：未调优 27B 的读出达到调优后 97% 的准确率，9B 上 1/16 的数据就收回 88% 的调优增益（[2610.15501](https://arxiv.org/abs/2610.15501)）；FunDM 无标签 KL 就收回 99%（[2610.17175](https://arxiv.org/abs/2610.17175)）；Our Own Jev 单种子消融"训练输出层的 26 个字母行没有可检测的收益"（[2610.29052](https://arxiv.org/abs/2610.29052)）。LDM 据此把决策微调定义为"**改变表示如何被读出，而不是获取新知识**"。
2. **目标函数的"增强"主要是加一个适当评分规则项。** 交叉熵仍是基线；最常见的改动是 `+ Brier`（jevlike 0.5、Open-Jev 0.1、OneJev 未给权重）。更系统的框架把"适当评分规则"当作统一语言：SanSi / LEV 每步都用，NDM 直接用并证明与 RLCD 式奖励的策略梯度同最优点，OpenJev-RLCD 把它当奖励，StartLux 把推理前后评分之差当奖励。也就是说**"校准"从后验温度搬进了目标函数，但是否真的比"交叉熵 + 温度"更校准，证据是否定或不确定的**（见 12.3）。
3. **适配方式趋同：冻结骨干 + LoRA。** 秩 8–16 最常见（Kev 16、Open-Jev 27B 为 8）；Releasing the Inner Jev 报告"对 LoRA 秩稳定"；LEV 报告在 Ouro 上 LoRA 胜过全参数；只有 Bongard（7.09B 全参数）和 StartLux Stage 1（全参数 SFT）例外。Nimble 的变体是"只在答案 token 上"放 LoRA 损失。
4. **监督从"任务标签"变成"决策混合 + 教师"。** 训练集普遍是几十到上百个公开数据集重新编译成"状态 + 问题 + 选项"的决策格式（Kev 10 个数据集 + 策略 + 规则结构；Tev1 四类来源；Releasing 79 任务 300,042 条硬标签 + 软标签子集；StartLux 约 2.7M；Chinese Decision 13.048M），再叠加一个更大模型做教师（Qwen3.5-122B-A10B、Qwen3.6-27B、Qwen3.5-27B、Qwen3.8-27B、Jev 本身）。真正"新"的数据构造只有三种：Nimble 的**对比策展**（改一个事实让答案翻转）、LDM 的**自提问**任务（SPRD）、AgentDecision 的**在 Agent 自己犯错后到达的状态上**采样。
5. **强化学习只在少数项目里出现，且基本是"推理模式"的事。** 对单遍 Instant 模型，开源证据要么负面（SBERT2S1 −2.5 到 −3.0、ufakzeka −10.2 F1、JevAgentHarness 无增益）、要么"等价"（NDM 定理、UniJev "差异很小"）、要么只在**有推理链**的设定下成立（OpenJev-RLCD、StartLux AutoThink）。TypeSafe 的 RLCD 没有任何公开细节，开源社区对"RLCD"一词的用法至少有四种（见 13 章 §13.6）。

结构性改动（G 族）是唯一一类改了"问题本身"的学习算法：块因果 / Prism-1 把顺序不变性从"数据增强要学的东西"变成"构造保证的东西"，循环模型把"一个模型服务所有计算预算"变成训练目标，Bongard 把"同一状态多判断"做进编码器-解码器。这些改动与 08 章的混合骨干约束直接相关：Prism-1 / 块因果都依赖注意力掩码，在 Qwen3.5 的 DeltaNet 层上不成立。

## 12.3 消融证据：这些改动有没有用

| 改动 | 证据 | 结论 |
| --- | --- | --- |
| LoRA 本身 | "LoRA 驱动改进"、"对秩稳定"、"更长训练没有一致收益"（[2610.17205](https://arxiv.org/abs/2610.17205)）；LoRA 胜全参数（Ouro，[2610.20951](https://arxiv.org/abs/2610.20951)） | **有用且不敏感**；全参数无优势证据 |
| 只训头 / 不训 | 未调优读出 = 97% 调优准确率；1/16 数据收回 88%（[2610.15501](https://arxiv.org/abs/2610.15501)）；FunDM 无标签 99%（[2610.17175](https://arxiv.org/abs/2610.17175)）；Our Own Jev 2B 困难层训练后 63.1 **低于**冻结 67.6（1B 48.6 对 54.1），电池集持平 70.6 对 70.2（[2610.29052](https://arxiv.org/abs/2610.29052)） | **训练增益小且可能为负**，取决于评测集；头在冻结表示上训"没有一种损失在温度缩放后明显更校准"（[2610.17205](https://arxiv.org/abs/2610.17205)） |
| 训练时长 | 更长的基线训练让 Qwen 过度自信：迁移套件 ECE 9B 23.8、27B 18.5，配方保持 8–12；一个温度去掉大部分差距（[2610.15501](https://arxiv.org/abs/2610.15501)） | **越训越过信**，温度能补大部分 |
| 软标签 vs 硬标签 | "教师标签有用，软标签（可能）无用"（[2610.17205](https://arxiv.org/abs/2610.17205)）；Open-Jev、Eikos、OneJev 都用软目标但无对照；Gaussian 代理理论：学生继承教师偏差，更多数据不消除（[2610.26797](https://arxiv.org/abs/2610.26797)） | **矛盾且无对照**；对我们的蒸馏路线是一级风险 |
| 适当评分规则 / Brier 项 | SBERT2S1 两头 × 五目标网格：温度缩放后**没有目标明显比交叉熵更校准**（[2610.02486](https://arxiv.org/abs/2610.02486)）；PACT 四项都不提高原始准确率，收益是种子方差减半、NLL −26%（[2609.35865](https://arxiv.org/abs/2609.35865)）；期望效用目标 +0.9±0.9 pp（[2610.17205](https://arxiv.org/abs/2610.17205)） | **对准确率无效，对稳健性 / NLL 有效**；校准优势在温度后基本消失 |
| RL / RLCD | 五种 RLCD 相对 SFT 增益"很小"、校准异质（[2610.25784](https://arxiv.org/abs/2610.25784)）；发布 RLCD 配方 −2.5 到 −3.0（[2610.02486](https://arxiv.org/abs/2610.02486)）；REINFORCE −10.2 F1（[2610.06744](https://arxiv.org/abs/2610.06744)）；GRPO 无增益（[2610.21412](https://arxiv.org/abs/2610.21412)）；但有推理链时 OpenJev-RLCD 选择性预测全面更优（[2609.38850](https://arxiv.org/abs/2609.38850)），StartLux AutoThink 比 Instant +11.5 到 +18.4 配对准确率（[2610.17309](https://arxiv.org/abs/2610.17309)） | **单遍模型上 RL 无正面证据**；RL 的收益与"生成推理"绑定 |
| 结构隔离 | 块因果翻转率 8.30→0.11%、18.16→1.20%（[2610.01601](https://arxiv.org/abs/2610.01601)）；Prism-1 零翻转、加选项不改相对赔率（[2610.22066](https://arxiv.org/abs/2610.22066)）；双向注意力 5 尺度中 4 个 +≤2.4（[2610.17309](https://arxiv.org/abs/2610.17309)）；每步训练使循环 1 可用 58.4% 对 35.6%（[2610.07730](https://arxiv.org/abs/2610.07730)） | **结构改动是唯一有大效应量的"算法"改动**，但依赖注意力掩码 |
| 数据 vs 算法 | 换一版语料让 2B 困难层移动 11 点（[2610.29052](https://arxiv.org/abs/2610.29052)）；决策训练让 Nimble 金融情感 Macro-F1 −12.0，Tev1 从不显著差于基座（[2610.26325](https://arxiv.org/abs/2610.26325)）；SecJev-0.8B 比 Kev-9B +20.51（[2610.03073](https://arxiv.org/abs/2610.03073)）；LEV "更多数据主要加强浅层读出"（[2610.20951](https://arxiv.org/abs/2610.20951)）；Bongard JEPA +10.2、沙盒 +14.2（[2609.39111](https://arxiv.org/abs/2609.39111)） | **数据构成的效应量 ≥ 目标函数的效应量**；"决策训练"不是一律有益 |
| 教师数量 | 两个教师平均 > 一个教师全预算（+9.6 Elo），同一教师再采一次无效（[2610.09188](https://arxiv.org/abs/2610.09188)） | 教师多样性比标签数量重要 |

综合：**现有方案的学习算法相对分类微调几乎没有"换算法"，只有"换读出 + 加评分项 + 换数据"；可证实有效的是 LoRA、数据构成、结构隔离与温度；软标签与 RL 的证据不足或为负。**

## 12.4 数据集可得性

### 12.4.1 公开训练集与评测集（按论文 / 项目）

| 数据 | 用途 | 规模 | 公开状态 | 出处 |
| --- | --- | --- | --- | --- |
| Kev `decision-v7` + `kev-suites` | 训练 / 评测 | 10,000 + 896 + 1,680 | 训练脚本与套件公开（HF `jaredpalmer/kev-suites`，0.3 GB） | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| Tev1 `new-v1` | 训练 | 37,840 + 4,568 | 仓库内公开 | [togethercomputer/tev1](https://github.com/togethercomputer/tev1) |
| Nimble 训练 / 保留集 | 训练 / 评测 | 2,676 / 324 | 2026-09-20 补发；Decision Index 评测集在 HF（CC BY-NC 4.0） | [bespokelabsai/nimble](https://github.com/bespokelabsai/nimble) |
| Open-Jev 训练混合 | 训练 | 148,639 行（冻结） | HF `ZefanCai/Open-Jev`（CC0）与 v1.1 | [Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev) |
| OneJev-Data | 训练 | 99,193 题（公开 94,707） | HF `OmniJev/OneJev-Data`，17.7 GB（含图像 / 视频） | [OmniJev/OneJev](https://github.com/OmniJev/OneJev) |
| OpenDecisions + 417,825 条训练池 | 验证 / 训练 | 池 417,825 | 论文称发布模型、服务代码与 OpenDecisions | [2610.17205](https://arxiv.org/abs/2610.17205) |
| Eikos 语料 | 训练 | 约 25K | HF `caiovicentino1/eikos-decisions`（CC BY 4.0） | [2610.29052](https://arxiv.org/abs/2610.29052) |
| DecisionPivot | 评测 | 对照组 + 参考轨 32,233 | HF `startlux-models/DecisionPivot` | [2610.28522](https://arxiv.org/abs/2610.28522) |
| StartLux 训练混合 | 训练 | 约 2.7M（0.8–9B）/ 0.8M（27B） | **未见公开**；权重 CC BY-NC 4.0 | [2610.17309](https://arxiv.org/abs/2610.17309) |
| JEVal | 评测 | 11,257（36 数据集、10 领域、双语） | HF `carlosxiang/JEVal` | [2610.03935](https://arxiv.org/abs/2610.03935) |
| System1-Arena | 评测 | 92k 题 / 105 任务 / 268 来源 + 138 闭环环境 | 论文描述；HF 上未探到仓库 | [2610.21244](https://arxiv.org/abs/2610.21244) |
| TypedBench | 评测 | 六检查点 | 论文描述；未探到 HF 仓库 | [2610.11392](https://arxiv.org/abs/2610.11392) |
| JevBench | 评测 | 231 公开题（+ 111 困难） | GitHub 仓库；**HF `fstandhartinger/jevbench` 不存在** | [fstandhartinger/jevbench](https://github.com/fstandhartinger/jevbench) |
| Laya typed-decisions 基准 | 评测 | — | HF `LocalLLaMA/typed-decisions`（Apache-2.0）、`Luni/laya-jev-benchmark` | [2609.33843](https://arxiv.org/abs/2609.33843) |
| DecisionGym / AgentDecisionBench | 评测 / 训练 | 500 新任务等 | "将发布"（论文措辞） | [2610.21412](https://arxiv.org/abs/2610.21412) |
| DecisionVista-Synth / Human、DDS 语料 | 评测 / 训练 | — | 代码公开；数据状态未核实 | [2610.15501](https://arxiv.org/abs/2610.15501) |
| CJ-Bench / 13.048M 中文决策 | 评测 / 训练 | 307,900 / 13.048M | 论文称发布模型；训练集公开状态**未核实** | [2610.23170](https://arxiv.org/abs/2610.23170) |
| SecJev-Corpus | 训练 | 14 任务 8 来源 | 论文称发布适配器、头、语料与代码 | [2610.03073](https://arxiv.org/abs/2610.03073) |
| MEDLINE-S1 / BIODECIDE | 训练 / 评测 | 243k | 发布标签与模型（编码器路线，对照） | [2610.02486](https://arxiv.org/abs/2610.02486) |
| PACT 数据切分与适配器 | 训练 / 评测 | 324 保留 | 公开 | [2609.35865](https://arxiv.org/abs/2609.35865) |
| this-that complex / spatial | 评测 | — | HF `limberc/*`（MIT） | [2609.23886](https://arxiv.org/abs/2609.23886) |
| RLCDAlignBench | 评测 | — | HF **gated（自动）**，CC BY-NC 4.0 | [sumleo/RLCDAlignBench](https://github.com/sumleo/RLCDAlignBench) |
| 其他 HF 社区集 | 评测 | — | `akhilaaa3/decision-bench`、`Hanno-Labs/decision-bench`（0.98 GB）、`Praveenrajus/jev-bench`（2.95 GB）、`yflantmy/DecisionRobust`（19.9 GB）、`Lexmount/WebJev`、`mohit67890/imajev-bench`、`DaehanKim/korean-jev-benchmark`、`SabaPivot/jev-safety-bench`、`raxITLabs/decision-models-as-guardrails`、`respanai/behavior-benchmark`、`avbiswas/bev-decision` | HF 探测记录（`hf_probe.json`） |

**结论**：训练数据的可得性分三层。（a）**完全公开且带许可**：Kev、Tev1、Nimble、Open-Jev、OneJev、Eikos、PACT、SecJev；（b）**只公开模型与评测、训练混合不公开**：StartLux、Chinese Decision（未核实）、Intern-Decision、Mapika 的教师标注部分；（c）**完全不公开**：TypeSafe Jev 的训练数据与 RLCD。中文决策数据只有 Chinese Decision 一家，而且面向通用 / 医法金融，**没有面向业务规则（D3）的中文决策数据**。许可方面，多数数据与权重是 Apache-2.0 / MIT / CC0，但 StartLux、Nimble v3、AgentDecision-4B、Dohnuts、torchcast、openjev/openjev 的权重为 CC BY-NC；TuringLogic system-x 需人工审批。

### 12.4.2 本地副本（/mnt/cephfs/xingchao）

镜像范围在 2026-10-28 按用户决定收窄为**全部公开数据集 + 实验阶梯需要的 Qwen 基座**；模型权重不再成批下载。当天复查 `/mnt/cephfs/` 后又发现 27B 档的基座本来就在共享目录里，于是下载范围进一步缩到"只补 Qwen3.5 的小尺寸"。状态以清单为准（`/mnt/cephfs/xingchao/manifests/jev/hf_manifest.jsonl`、`github_manifest.tsv`、`hf_probe.json`）。本节更新时（2026-10-28 上午）：

- 目录约定：数据集 `datasets/jev/<org>__<name>`、模型 `models/jev/<org>__<name>`、GitHub 仓库 `repos/jev/<org>__<repo>`（浅克隆）；每个完成的 HF 仓库写 `.complete`（含修订号与时间）。
- **数据集**：探测到 24 个公开 HF 数据集约 43 GB，已完成 21 个（约 3.4 GB，含 kev-suites、this-that 两个基准、DecisionPivot、Open-Jev / v1.1、JEVal、decision-bench、WebJev、imajev-bench 等），正在下载 `Praveenrajus/jev-bench`，随后是两个大件 `OmniJev/OneJev-Data`（17.7 GB）与 `yflantmy/DecisionRobust`（19.9 GB）。排除：`fstandhartinger/jevbench`（不存在）、gated 仓库（RLCDAlignBench、system-x、prompt-injection）。
- **模型**：已落地 32 个 ≤9B 的决策模型 / 适配器与对照（约 14 GB：Nimble-9B-v3、Laya 三种、Open-Jev 适配器、decider-0.8b、Decision-2.0-Kai-0.6B、Qwen3-0.6B、JevAny-Qwen3.8-27B-LoRA 等）。
- **基座不需要重新下载**：`/mnt/cephfs/models/` 下已经有完整的 `Qwen3.8-27B`（52 GB，18/18 分片，config.json 与上游逐键一致且无 `quantization_config`）、`Qwen3.5-27B`（11/11）、`Qwen3.6-27B`（15/15）与 `Qwen3.5-35B-A3B`（14/14，MoE）；共享的 `huggingface_hub` 缓存里另有完整的 Qwen3-0.6B / 14B / 30B-A3B（纯注意力与 MoE 对照）。同目录下的 `-w8a8`、`-DSpark*`、`-DFlash2` 是量化或投机解码变体，不是基座。清单见 `manifests/jev/shared_models_reusable.tsv`。因此原计划的 55.6 GB `Qwen/Qwen3.8-27B` 下载已取消。
- **仍需下载的只有 Qwen3.5 的小尺寸**：0.8B / 2B / 4B / 9B 的 Base 与 Instruct 共 8 个仓库约 70 GB（1.77 / 4.57 / 9.34 / 19.33 GB 一档，均 Apache-2.0），cephfs 上任何位置都没有，已按"小→大"入队（`manifests/jev/hf_queue3.txt`）。
- 带宽约束：代理每连接约 10 KB/s，96 并行约 2.5 MB/s；小文件多的仓库实际只有约 1.5 GB/小时，大文件接近 9 GB/小时。剩余约 108 GB（70 GB 小基座 + 38 GB 两个大数据集）预计一天左右。
- **GitHub**：54 个被引用仓库中 49 个浅克隆完成（约 1.9 GB）；`jaredpalmer/kev` 只拿到 37 MB 的部分检出，`StartLuxLabs/StartLux-Decision`、`Mapika/decider`、`togethercomputer/tev1` 的 pack 在代理下反复截断，`PACT` 因缺 git-lfs 只有源码无权重。这四个仓库的代码仍可按文件从 raw 地址取回，但没有 git 历史。

## 12.5 基座选型规律

| 规律 | 证据 |
| --- | --- |
| **Qwen3.5 系列（0.8B / 2B / 4B / 9B）+ Qwen3.8-27B 是"完整复现"的默认骨干** | Kev（Qwen3.5-0.8B/4B/9B-**Base**、Qwen3.8-27B）、OneJev（同四档）、Nimble（Qwen3.5-9B）、Tev1（Qwen3.5-4B）、Mapika decider（Qwen3.5-2B/4B-**Base**、35B-A3B-Base）、DKnown-Jev（Qwen3.5-2B / Qwen3.8-27B 基座）、Chinese Decision（Qwen3.5-0.8B/2B/4B）、UniJev（Qwen3.5 多模态塔）、Eikos（Qwen3.5-4B、Qwen3.8-27B）、Open-Jev（Qwen 2B/9B/27B）、pplx-decider（Qwen3.8-27B）、qwen-rlcd（Qwen3.5-0.8B-Base）、Releasing the Inner Jev 与 LDM 的 Qwen 分支 |
| **纯注意力的 Qwen3（0.6B / 1.7B / 4B / 8B）集中在校准与结构研究** | OpenJev-RLCD（Qwen3-1.7B）、jevlike（Qwen3-1.7B）、SHIFT-JEV（Qwen3-0.6B / 4B + Phi-4-mini）、块因果（Gemma 3 1B、Qwen3 1.7B、Qwen3 4B）、Prism-1（Qwen3-8B）、FunDM（Qwen3-8B）、LLM-as-Jev（Qwen3-0.6B）、System X（Qwen3-0.6B→1.7B）、法律蒸馏（Qwen3-8B）、NanoJev 0.6B。原因与 08 章一致：这些工作需要树掩码 / 块掩码或梯度穿过缓存，混合骨干做不到 |
| **Gemma 4（12B / 31B）承担"大模型"位置** | Mapika decider-12b / 31b（Gemma-4-*-it + 合并的状态跟踪 LoRA）、daseinlabs open-jev（Gemma 4 12B）、Releasing the Inner Jev（Gemma 4 31B 微调后 84.4）、LDM、Prism-1（Gemma 4 12B）、torchcast-decision-12b |
| **Base 还是 Instruct 没有共识** | Kev、Mapika（Qwen 分支）、DKnown-Jev、qwen-rlcd 明确用 Base；Mapika 的 Gemma 分支、Tev1、OneJev 用 Instruct；Releasing the Inner Jev 把"从指令模型起步"列为消融项（数字不在缓存中，不引用）；**没有论文系统比较两者在决策质量、校准与 ICL 保留上的差异** |
| **尺寸：4B 是"完整配方"论文的众数；0.6–0.8B 面向延迟；27B 面向排行榜** | 4B：Tev1、AgentDecision-4B、SII-Decision、Intern-Decision-4B、Mapika-4b、StartLux-4B、Eikos-4B、Jeva-4B、OmniMed-Jev-4B；0.6–0.8B：Kev-0.8B、OneJev-0.8B、SecJev-0.8B、NanoJev、Dohnuts、System X；27B：StartLux-27B（Decision Index 第 1）、Open-Jev-27B、pplx-decider、Kev-27B、Eikos-27B |
| **非主流骨干各有一个代表** | 循环预训练 Ouro-1.4B / 2.6B（SanSi、LEV）；编码器-解码器 T5Gemma 2 4B-4B（Bongard）；NeoHorse-1-4B（JEV 重排）；MiniCPM5-1B/2B、Qwen3.6-35B-A3B（Our Own Jev）；Muse-Glimmer 30B（MetaEncoder）；自有 182M 基座（ufakzeka-karar） |
| **编码器只作对照** | Laya（ModernBERT-large 421M / mmBERT-base 322M）、Verdict-MQ 395M、SBERT2S1（Sentence-Transformers 家族）、NDM-Block、this-that、GLiNER2.5-Decide、CLM；benchmark 结论是"有任务标签时微调 DeBERTa-v3-large 在除一项外每个标注基准上准确率最高"（[2610.00346](https://arxiv.org/abs/2610.00346)），但这条路线不在我们方向内 |

对"在小尺寸 Qwen 类模型上继续训练"这一目标，文献给出的事实边界是：（1）Qwen3.5 全系是 DeltaNet 混合，分支隔离只能按行训练或前缀分叉（08 章）；（2）Qwen3 纯注意力系列上所有结构性方法都已有实现与数字；（3）0.6B–4B 上"冻结 + LoRA + 复用输出层"是每篇论文都用的起点，且小模型决策训练后校准**不迁移**（jevlike 域外、Nimble 金融）。（4）Qwen3.8 只有 27B 一个稠密尺寸（其余为 MoE），因此"从小到大"只能用 Qwen3.5-0.8B / 2B / 4B / 9B 做小端、27B 做大端；三代 27B 形状相同、0.8B–9B 与 27B 同族同比例（每 4 层 1 层全注意力，08 章 §8.2 的配置表），架构上是一条干净的阶梯，但小端与大端跨了一代预训练，这一差异没有任何文献控制过。

## 12.6 学习视角的盲区

1. **同骨干同数据的目标函数对照几乎没有。** 唯一的系统网格（两种头 × 五种目标）在编码器上做（[2610.02486](https://arxiv.org/abs/2610.02486)）；解码器上只有 Releasing the Inner Jev 的局部消融与 UniJev 的 RL 比较。"交叉熵 + 温度"是否已经是解码器路线的上界，没有答案。
2. **软标签 / 教师蒸馏的收益与风险都没有在决策模型上量化。** 一方说"软标签可能无用"，一方默认使用；理论说教师偏差不可消除且不可被一致性暴露。顺序、IIA、序数、否定等 D4 缺陷是否随教师概率一起被蒸馏进学生，无人测量。
3. **RL 的作用域不清。** 所有正面 RL 证据都来自带推理链的模型；单遍模型上 RL 为负或无效；TypeSafe 的 RLCD 不可复现。"RLCD"在社区里指至少四种不同的东西（13 章）。
4. **决策微调与 ICL 的关系仍是零文献**（09 章一级盲区 1）。从学习视角看，这等价于"LoRA 决策训练是否改变了注意力对上下文示例的使用"，现有消融只看准确率与 ECE。
5. **数据构成的效应量最大，但没有"数据配方"的研究。** 对比策展、自提问、Agent 自身轨迹三种构造各有一篇，没有同骨干比较；中文、业务规则、非技术人员撰写的输入三类数据为空。
6. **混合骨干上的训练时隔离仍无数字**（08 章），而所有可证实有大效应量的"算法"改动都是依赖掩码的结构改动。这把"选 Qwen3.5 还是 Qwen3"从工程问题变成了学习算法问题。
7. **SFT 的泛化边界没有在单遍模型上被受控测量。** 14 章按七个层次核对后，同族新来源上的迁移证据充分，而新 schema、新符号操作、先验偏移、校准迁移四层只有负面或缺失的证据；"SFT 对 RL 的分布外对照"在单遍决策模型上为零篇。
