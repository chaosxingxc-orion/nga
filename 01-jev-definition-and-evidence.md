# 01 · Jev / System One：定义、接口原语、架构还原与独立评测

> 本章回答："Jev 类快思考模型"到底是什么、对外暴露了什么接口、黑盒探针推断出什么架构、独立评测给出了什么结论。所有数字均回到缓存的原文核对。

## 1.1 基本事实

| 项目 | 内容 | 出处 |
| --- | --- | --- |
| 厂商 / 发布 | TypeSafe AI（旧金山，2024 年成立），Jev 于 2026-09-15 发布；Jev 1.14 于 2026-10-14 发布 | [Wikipedia](https://en.wikipedia.org/wiki/Jev_(AI_model))、[docs/models](https://docs.typesafe.ai/models) |
| 定价 | 输入 $0.042 / Mtok，输出不计费（输出不是文本） | [docs/models](https://docs.typesafe.ai/models) |
| 上下文 | 每请求 64k、每问题 32k；加 `TypeSafe-Danger-Zone-Long-Context: true` 头可放宽；一次请求问题数不限，只受两个上限约束 | [docs/models](https://docs.typesafe.ai/models) |
| 训练 | "RLCD"（Reinforcement Learning for Calibrated Decisions），只用合成数据，细节未公开；不用客户数据微调，一套权重服务所有账户 | [ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer)、[docs/models](https://docs.typesafe.ai/models)、Wikipedia |
| 定位 | "为构建 AI 驱动的软件而非 Agent"：代码掌握控制流、确定性规则与副作用，模型只回答窄而结构化的判断；"把独立问题一起问，再在代码里组合答案" | [How to build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) |

## 1.2 接口原语（我们后续"逻辑原语"讨论的起点）

TypeSafe 的 System One API 只有三种问题类型，再加上 `state`：

| 原语 | 返回 | 约束 | 备注 |
| --- | --- | --- | --- |
| **Noul** | 命题为真的概率 P(true) | 可选 `criteria`，当 yes/no 边界微妙时用结构化的 `true` / `false` 描述，各自带定义与示例 | [primitives/advanced](https://docs.typesafe.ai/primitives/advanced) |
| **Choice** | 对每个选项的概率分布 + 置信度 | 选项带 `criteria`（描述）与 `examples`；可用 JSON 结构 | 同上 |
| **Score** | 对有序等级的概率分布 + 得分 + 置信度 | `criteria` 为从低到高的有序等级描述，≥2 级，API 最多 10 级 | [primitives/score](https://docs.typesafe.ai/primitives/score) |
| **State** | 问题所针对的材料：文本、JSON 对象或数组，"可以包含相关上下文、示例和其他有助于回答的信息"；比喻为"交给专家小组的材料" | 文档明确允许在 state 中放示例 | [concepts/state](https://docs.typesafe.ai/concepts/state) |

**置信度**的定义是 `confidence = (p_max − 1/n) / (1 − 1/n)`：只看最高概率，均匀分布为 0，确定为 1（[docs/confidence](https://docs.typesafe.ai/confidence)）。这意味着"置信度"不是熵，也不是 top-2 差距，而只是 top-1 相对均匀分布的高度。多篇论文指出这个定义与"错误检测能力"并不是一回事（见 D4 章）。

**官方模式（patterns）**，构成了"用代码组合小判断"的原语库：

- **Speculative fan-out**：一次请求里并行问多个独立问题（[patterns/fan-out](https://docs.typesafe.ai/patterns/fan-out)）。
- **Composite scoring**：多个 Noul / Score 的结果在代码里加权求和（[patterns/composite-scoring](https://docs.typesafe.ai/patterns/composite-scoring)）。
- **Confidence routing**：一个全局下限（示例 0.6）+ 每类动作各自的阈值，低于阈值交人工（[patterns/confidence-routing](https://docs.typesafe.ai/patterns/confidence-routing)）。
- **Walking a taxonomy**：每层一个 Choice，在代码里逐层走树（[primitives/advanced](https://docs.typesafe.ai/primitives/advanced)）。
- **Agent skill 文档**的工程建议："把问题和阈值常量放在一个文件里便于审查；Agent 不擅长写问题，要和它协作编辑"；"如果只要选最优选项，就取最高置信度，不要到处设阈值"（[agent-skill](https://docs.typesafe.ai/agent-skill)）。

**用例地图**（[use-case map](https://docs.typesafe.ai/concepts/use-case-map)）把决策形状分为分类、检测、打分、路由、搜索、检索、排序、验证、ML 特征抽取、结构化抽取十类。这十类是我们定义 D3 原语集合时的参考分类。

## 1.3 官方承认的"锯齿"（jev-1.13 model jaggedness）

官方文档列出 9 类失效，并给出"改用什么"的建议（[model-jaggedness/jev-1.13](https://docs.typesafe.ai/model-jaggedness/jev-1.13)）：

| # | 失效模式 | 官方建议 |
| --- | --- | --- |
| 1 | 字面阅读（literal reading） | 为每个选项写出精确条件与判据 |
| 2 | 数学与数字：不会可靠计数（字符数、词频、列表项），"识别答案的形状而非逐一清点" | 算术放代码里 |
| 3 | 日期时间比较：把日期当文本读，先后、间隔、窗口判断不可靠 | 抽出分量，在代码里比较 |
| 4 | 间接（indirection）：双重否定、属性的属性、多跳 | 减少跳数，直接指向相关 state |
| 5 | 大量无关细节的 state | 先过滤，只送问题需要的 |
| 6 | 对抗内容 | 写精确提示，上线前测边界 |
| 7 | 指令与判据矛盾 | 对齐判据与指令 |
| 8 | Choice 选项顺序：偏向排在前面的选项 | 重排选项，检查答案一致 |
| 9 | 生成 | 用生成模型 |

这份表格几乎就是 D2 / D4 的"官方版问题清单"；第三方论文（下文与各维度章节）把每一条都量化了，并发现了官方没列出的更多失效。

## 1.4 架构还原（黑盒探针）

Archer Hume 的《Jev's Architecture Unmasked》（2026-09-17，[链接](https://archerhume.com/posts/jevs-architecture-unmasked)）通过 API 探针得出：

- **因果 Transformer**（作者猜测含稀疏 MoE，但明确说"是推测"），**共享的 state 前缀 + 相互隔离的问题分支 + 直接概率读出**。
- **分支隔离证据**：把一个秘密代码放在兄弟问题里，被问到的问题给出 0.00 概率；删掉那个兄弟问题结果不变；把同样的声明放进 state，概率上升。
- **列表式读出证据**：把目标选项放在最前时 12/16 正确，放在最后时 16/16 正确，说明选项之间不是独立打分。
- **无关选项改变现有选项之间的优势比**：加入一个无关选项后，两原选项的平均 log-odds 从 +0.38 降到 +0.11，十个随机区块全部下降（均值 −0.28，95% 区间 −0.36 到 −0.19）。这否定了"固定独立 logit + 不变 softmax"的机制。
- **服务特征**：到约 100 个问题为止服务器时间几乎不变，之后线性上升；按 token 计，问题文本的成本约为 state 的两倍。
- **分词器**在 415 次探针中与 192 个公开分词器都不匹配；每个数字单独切分。

这套还原直接决定了开源复现的结构（见 [02 章](02-open-reproductions-and-recipes.md)）和混合架构下的分支隔离难题（见 [08 章](08-backbone-hybrid-constraints.md)）。

## 1.5 独立评测与审计：Jev 擅长什么、不擅长什么

### 1.5.1 横向能力

| 来源 | 设置 | 主要结论 |
| --- | --- | --- |
| [2609.37647](https://arxiv.org/abs/2609.37647) | 37 个数据集零样本，346,009 次请求花费不到 10 美元；对照 Qwen3.8-27B、Gemma-4-E4B 的精确下一 token 概率 | IMDB / SST-2 / HellaSwag / ARC 95–99%，Belebele 122 种语言 86.7%；37 个数据集中胜 Qwen 27 个、胜 Gemma 全部；三者都在低资源语言、细粒度/噪声标签、基于评分细则的质量判断上退化。Choice 概率校准良好；**二元概率排序好但相对固定 0.5 阈值摆放不准**，在 UNFAIR-ToS 上用训练集调阈值使 micro-F1 从 0.50 升到 0.75 |
| [2610.11978](https://arxiv.org/abs/2610.11978) | 13 个多选基准，对照 19 个 LLM | 知识与常识上与前沿模型相当，MMLU-Redux 与 ARC-Challenge 最佳；**MathQA 比前沿中位数低 17.7 点，低于全部 19 个 LLM** |
| [2609.24574](https://arxiv.org/abs/2609.24574) | 计算社会科学 18 任务 7,977 条，对照 19 个 LLM | 15 个任务里 14 个落后于该任务最好的 LLM，中位差 11.6 macro-F1，但成本中位低 44 倍；置信度比 19 个 LLM 中 16 个的口头置信度更校准；在"同伴支持对话中的共情"任务上**高置信但接近随机** |
| [2610.18529](https://arxiv.org/abs/2610.18529) | 医学 15 数据集 8,742 条 | 文本驱动任务上与领先模型相当，**数值驱动任务上明显弱**；问题格式变化下一致性强；大多数模型不能识别"正确答案缺失"也不会用可选弃权；**把逐选项的二元得分归一化比 Choice 打分保留更高准确率** |
| [2610.33258](https://arxiv.org/abs/2610.33258) | 142,658 条人工标注评论的内容审核，对照 14 个前沿推理模型 | 零样本 AUROC 0.83 与 14 个前沿系统中的 13 个在统计上不可区分，成本低 1–3 个数量级；"置信度"混合了**人类分歧**与**决策风险**两种不同的不确定性 |
| [2609.26550](https://arxiv.org/abs/2609.26550) | JEV-as-a-Judge，对照 16 个生成式与奖励模型裁判 | 凡是裁决能从文本直接读出的任务，与 GPT-6 差 3 点以内，费用为其 0.36%，中位延迟 0.15 s；**需要推导裁决的数学 / 代码 / 逻辑任务落后**；置信门控级联在 1,610 对上比 GPT-6 高 0.9 点，费用 41% |
| [2610.35721](https://arxiv.org/abs/2610.35721) | 临床试验入组条件，2,048 对 | 批量模式下 TrialGPT / MIMIC-IV 与 Qwen Flash 相当，MIMIC-III 显著更好（0.768 对 0.534），优势主要来自对"信息不足"类别的召回（56.3% 对 9.9%）；延迟 1.18–1.40 s 对 2.80–8.90 s，成本低 53%–74% |
| [2609.24052](https://arxiv.org/abs/2609.24052) | 德州 499,500 条事故叙述筛查，195,857 条按 27 问模式编码 | 对人工标签 F1 0.908；成本由模式大小而非叙述长度决定；**校准因模型而异而非因范式而异，每个模型都要审计**；重校准把校准误差降低 3.3 倍 |
| [2609.23136](https://arxiv.org/abs/2609.23136) | 6G Open RAN 意图解释 | Jev 在 99.8% 的调用上满足 1 s 近实时预算，两个托管 LLM 为 17.9% 与 0% |

### 1.5.2 元审计与生态

- **早期证据审计**（[2609.32160](https://arxiv.org/abs/2609.32160)）：复盘发布后 9 天内的 28 篇论文，结论是"**类型化读出本身尚未显示出独立于同类标签概率读出的准确率优势**；Jev 最清楚的收益在延迟与成本，困难任务上仍有准确率差距；实践中置信度多用于决定何时转交更强模型或人"。给出 14 项评测清单。
- **生态**（[2609.30216](https://arxiv.org/abs/2609.30216)）：截至 2026-09-22 的 2,170 个公开 GitHub 项目，属性判断与打分最常用，动作选择、内容过滤、模型/工具选择在各领域差异大。
- **实践者指南**（[2610.33775](https://arxiv.org/abs/2610.33775)）提出五族分类：编码器分类器、奖励模型、非自回归决策引擎、对比决策模型、抽取模型。我们的方向落在"非自回归决策引擎"中的**解码器骨干**子类。
- **排行榜**：Decision Index 0.4 的主排名改为"Full score = 60% 同技能私有测试 + 40% 新领域私有决策任务"，技能分按机会水平校正（[apolinario/decision-index](https://github.com/apolinario/decision-index)）；Jev 领跑 0.2 版（[systemonemodels.org](https://systemonemodels.org/examples/articles/jev-decision-index/)）。

### 1.5.3 稳定性与偏置（概述，细节在 D4 章）

- 重复性极高：文化价值观调查 24 题 288,000 次回答 ICC 0.997（[2609.36399](https://arxiv.org/abs/2609.36399)）。
- 但"同分不同判"：ContractNLI 上改变可见假设、请求答案与输出顺序后，纠正与回退相互抵消，准确率不变而决策已变（[2609.27678](https://arxiv.org/abs/2609.27678)）。
- 认知偏差上大体表现好，但对无关数值信息和选项顺序敏感（[2610.19619](https://arxiv.org/abs/2610.19619)）。

## 1.6 本章小结：Jev 是什么、不是什么

1. **是什么**：一个把"state + 类型化问题 → 概率"作为唯一接口的因果 Transformer，共享前缀、分支隔离、列表式读出，靠校准训练与极低成本取胜。
2. **不是什么**：不是更准的分类器，不是会算术/比日期/数数的模型，不是对选项顺序与无关选项免疫的打分器，也不是"置信度 = 知道自己不知道"的模型。
3. **对我们的含义**：Jev 的价值在于**接口契约**（概率可阈值、可组合、可审计）而非权重。只要复现这个契约，小模型 + 领域数据就能在特定任务上超过它（见 02 章）。真正难的是让这个契约在 D1–D5 各维度上**保持一致**（见 06 章）。
4. **这一条在 17、20 章被改进过**：说"价值在接口契约"还不够，因为它没说契约是干什么用的。更锋利的版本是"契约把**决策的记账**交给代码，而把**语义**留在模型里"——注意不是"把决策变成代码"：把开放世界的非结构化情形映射成一个带刻度的观测记录这一步没有任何代码写法，它就是语义泛化，也是整个构造里唯一不可替代的部分（17 章 §17.1.7）——它能预测哪类部署成功（决策权在代码里）、哪类失败（决策权回到模型里），与 17 章 §17.5 的五格表吻合。但它**不能**被进一步读成"于是系统就幂等了"：宿主 Jev 自身的重复抖动、菜单构成对指标的影响、harness 计划与排队的影响、以及"写不出中间步骤就做不出的判断"这四项，共同把它限制为"把非幂等的表面收缩成可定界、可定价的若干字段"（17 章 §17.1、20 章 §20.1.2）。
