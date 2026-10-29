# 1 · 对象与口径：Jev 类模型是什么，骨干约束是什么，各篇论文在说什么

> 本章建立全报告的事实基础，不含判断。§1.1 是对象本身（接口原语、官方承认的锯齿、黑盒架构还原、独立评测与审计）；§1.2 是十五个以上开源复现给出的配方矩阵与小模型证据；§1.3 是混合骨干（Gated DeltaNet 类）在哪一步破坏 Jev 式接口依赖的结构假设——**只调研不选型**；§1.4 是跨论文的定义分歧，它解释了为什么后面各章的数字不能直接相互比较。
>
> 读法：§1.1–§1.2 回答"它是什么、谁复现了它"，§1.3 回答"我们的骨干能不能承载它"，§1.4 回答"读到两个数字时该不该放在一起比"。

## 1.1 Jev / System One：定义、接口原语、架构还原与独立评测

> 本节回答："Jev 类快思考模型"到底是什么、对外暴露了什么接口、黑盒探针推断出什么架构、独立评测给出了什么结论。所有数字均回到缓存的原文核对。

### 1.1.1 基本事实

| 项目 | 内容 | 出处 |
| --- | --- | --- |
| 厂商 / 发布 | TypeSafe AI（旧金山，2024 年成立），Jev 于 2026-09-15 发布；Jev 1.14 于 2026-10-14 发布 | [Wikipedia](https://en.wikipedia.org/wiki/Jev_(AI_model))、[docs/models](https://docs.typesafe.ai/models) |
| 定价 | 输入 $0.042 / Mtok，输出不计费（输出不是文本） | [docs/models](https://docs.typesafe.ai/models) |
| 上下文 | 每请求 64k、每问题 32k；加 `TypeSafe-Danger-Zone-Long-Context: true` 头可放宽；一次请求问题数不限，只受两个上限约束 | [docs/models](https://docs.typesafe.ai/models) |
| 训练 | "RLCD"（Reinforcement Learning for Calibrated Decisions），只用合成数据，细节未公开；不用客户数据微调，一套权重服务所有账户 | [ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer)、[docs/models](https://docs.typesafe.ai/models)、Wikipedia |
| 定位 | "为构建 AI 驱动的软件而非 Agent"：代码掌握控制流、确定性规则与副作用，模型只回答窄而结构化的判断；"把独立问题一起问，再在代码里组合答案" | [How to build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) |

### 1.1.2 接口原语（我们后续"逻辑原语"讨论的起点）

TypeSafe 的 System One API 只有三种问题类型，再加上 `state`：

| 原语 | 返回 | 约束 | 备注 |
| --- | --- | --- | --- |
| **Noul** | 命题为真的概率 P(true) | 可选 `criteria`，当 yes/no 边界微妙时用结构化的 `true` / `false` 描述，各自带定义与示例 | [primitives/advanced](https://docs.typesafe.ai/primitives/advanced) |
| **Choice** | 对每个选项的概率分布 + 置信度 | 选项带 `criteria`（描述）与 `examples`；可用 JSON 结构 | 同上 |
| **Score** | 对有序等级的概率分布 + 得分 + 置信度 | `criteria` 为从低到高的有序等级描述，≥2 级，API 最多 10 级 | [primitives/score](https://docs.typesafe.ai/primitives/score) |
| **State** | 问题所针对的材料：文本、JSON 对象或数组，"可以包含相关上下文、示例和其他有助于回答的信息"；比喻为"交给专家小组的材料" | 文档明确允许在 state 中放示例 | [concepts/state](https://docs.typesafe.ai/concepts/state) |

**置信度**的定义是 `confidence = (p_max − 1/n) / (1 − 1/n)`：只看最高概率，均匀分布为 0，确定为 1（[docs/confidence](https://docs.typesafe.ai/confidence)）。这意味着"置信度"不是熵，也不是 top-2 差距，而只是 top-1 相对均匀分布的高度。多篇论文指出这个定义与"错误检测能力"并不是一回事（见 D§4.1）。

**官方模式（patterns）**，构成了"用代码组合小判断"的原语库：

- **Speculative fan-out**：一次请求里并行问多个独立问题（[patterns/fan-out](https://docs.typesafe.ai/patterns/fan-out)）。
- **Composite scoring**：多个 Noul / Score 的结果在代码里加权求和（[patterns/composite-scoring](https://docs.typesafe.ai/patterns/composite-scoring)）。
- **Confidence routing**：一个全局下限（示例 0.6）+ 每类动作各自的阈值，低于阈值交人工（[patterns/confidence-routing](https://docs.typesafe.ai/patterns/confidence-routing)）。
- **Walking a taxonomy**：每层一个 Choice，在代码里逐层走树（[primitives/advanced](https://docs.typesafe.ai/primitives/advanced)）。
- **Agent skill 文档**的工程建议："把问题和阈值常量放在一个文件里便于审查；Agent 不擅长写问题，要和它协作编辑"；"如果只要选最优选项，就取最高置信度，不要到处设阈值"（[agent-skill](https://docs.typesafe.ai/agent-skill)）。

**用例地图**（[use-case map](https://docs.typesafe.ai/concepts/use-case-map)）把决策形状分为分类、检测、打分、路由、搜索、检索、排序、验证、ML 特征抽取、结构化抽取十类。这十类是我们定义 D3 原语集合时的参考分类。

### 1.1.3 官方承认的"锯齿"（jev-1.13 model jaggedness）

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

### 1.1.4 架构还原（黑盒探针）

Archer Hume 的《Jev's Architecture Unmasked》（2026-09-17，[链接](https://archerhume.com/posts/jevs-architecture-unmasked)）通过 API 探针得出：

- **因果 Transformer**（作者猜测含稀疏 MoE，但明确说"是推测"），**共享的 state 前缀 + 相互隔离的问题分支 + 直接概率读出**。
- **分支隔离证据**：把一个秘密代码放在兄弟问题里，被问到的问题给出 0.00 概率；删掉那个兄弟问题结果不变；把同样的声明放进 state，概率上升。
- **列表式读出证据**：把目标选项放在最前时 12/16 正确，放在最后时 16/16 正确，说明选项之间不是独立打分。
- **无关选项改变现有选项之间的优势比**：加入一个无关选项后，两原选项的平均 log-odds 从 +0.38 降到 +0.11，十个随机区块全部下降（均值 −0.28，95% 区间 −0.36 到 −0.19）。这否定了"固定独立 logit + 不变 softmax"的机制。
- **服务特征**：到约 100 个问题为止服务器时间几乎不变，之后线性上升；按 token 计，问题文本的成本约为 state 的两倍。
- **分词器**在 415 次探针中与 192 个公开分词器都不匹配；每个数字单独切分。

这套还原直接决定了开源复现的结构（见 [§1.2](01-object-and-definitions.md)）和混合架构下的分支隔离难题（见 [§1.3](01-object-and-definitions.md)）。

### 1.1.5 独立评测与审计：Jev 擅长什么、不擅长什么

#### 1.1.5.1 横向能力

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

#### 1.1.5.2 元审计与生态

- **早期证据审计**（[2609.32160](https://arxiv.org/abs/2609.32160)）：复盘发布后 9 天内的 28 篇论文，结论是"**类型化读出本身尚未显示出独立于同类标签概率读出的准确率优势**；Jev 最清楚的收益在延迟与成本，困难任务上仍有准确率差距；实践中置信度多用于决定何时转交更强模型或人"。给出 14 项评测清单。
- **生态**（[2609.30216](https://arxiv.org/abs/2609.30216)）：截至 2026-09-22 的 2,170 个公开 GitHub 项目，属性判断与打分最常用，动作选择、内容过滤、模型/工具选择在各领域差异大。
- **实践者指南**（[2610.33775](https://arxiv.org/abs/2610.33775)）提出五族分类：编码器分类器、奖励模型、非自回归决策引擎、对比决策模型、抽取模型。我们的方向落在"非自回归决策引擎"中的**解码器骨干**子类。
- **排行榜**：Decision Index 0.4 的主排名改为"Full score = 60% 同技能私有测试 + 40% 新领域私有决策任务"，技能分按机会水平校正（[apolinario/decision-index](https://github.com/apolinario/decision-index)）；Jev 领跑 0.2 版（[systemonemodels.org](https://systemonemodels.org/examples/articles/jev-decision-index/)）。

#### 1.1.5.3 稳定性与偏置（概述，细节在 D§4.1）

- 重复性极高：文化价值观调查 24 题 288,000 次回答 ICC 0.997（[2609.36399](https://arxiv.org/abs/2609.36399)）。
- 但"同分不同判"：ContractNLI 上改变可见假设、请求答案与输出顺序后，纠正与回退相互抵消，准确率不变而决策已变（[2609.27678](https://arxiv.org/abs/2609.27678)）。
- 认知偏差上大体表现好，但对无关数值信息和选项顺序敏感（[2610.19619](https://arxiv.org/abs/2610.19619)）。

### 1.1.6 本节小结：Jev 是什么、不是什么

1. **是什么**：一个把"state + 类型化问题 → 概率"作为唯一接口的因果 Transformer，共享前缀、分支隔离、列表式读出，靠校准训练与极低成本取胜。
2. **不是什么**：不是更准的分类器，不是会算术/比日期/数数的模型，不是对选项顺序与无关选项免疫的打分器，也不是"置信度 = 知道自己不知道"的模型。
3. **对我们的含义**：Jev 的价值在于**接口契约**（概率可阈值、可组合、可审计）而非权重。只要复现这个契约，小模型 + 领域数据就能在特定任务上超过它（见 §1.2）。真正难的是让这个契约在 D1–D5 各维度上**保持一致**（见 §4.2）。
4. **这一条在 17、§8.1被改进过**：说"价值在接口契约"还不够，因为它没说契约是干什么用的。更锋利的版本是"契约把**决策的记账**交给代码，而把**语义**留在模型里"——注意不是"把决策变成代码"：把开放世界的非结构化情形映射成一个带刻度的观测记录这一步没有任何代码写法，它就是语义泛化，也是整个构造里唯一不可替代的部分（§2.1.7）——它能预测哪类部署成功（决策权在代码里）、哪类失败（决策权回到模型里），与 §5.1.4 的五格表吻合。但它**不能**被进一步读成"于是系统就幂等了"：宿主 Jev 自身的重复抖动、菜单构成对指标的影响、harness 计划与排队的影响、以及"写不出中间步骤就做不出的判断"这四项，共同把它限制为"把非幂等的表面收缩成可定界、可定价的若干字段"（§2.1 §2.1、§8.1.1.2）。

## 1.2 开源解码器复现与配方矩阵（含小模型证据）

> 本节回答：用开源因果语言模型（Qwen / Gemma 等）复现 Jev 接口的工作有哪些，各自的骨干、读出头、损失、数据、校准与"分支隔离"方式是什么，以及小模型（0.6B–9B）到底能做到什么程度。编码器系（Laya、Verdict、Jeva、NDM、RubriX、Bongard 等）不在我们的技术方向内，仅作对照时引用。

### 1.2.1 一个共同的骨架

所有解码器复现都遵循 Archer Hume 还原出的三段式：

1. **共享 state 前缀**：state 只编码一次（KV 缓存 / 前缀分叉 / 独立行）。
2. **问题分支相互隔离**：树形注意力掩码（纯注意力骨干）、或每问题一行、或前缀分叉（混合骨干，见 §1.3）。
3. **读出**：从最后一个位置读 LM-head 的候选字母 logit（letter readout），或在每个选项末尾位置放"指针头"（pointer head）/ 跨度均值池化（mean-span），再对合法选项做 softmax，最后乘一个拟合温度。

一个重要的先验证据：**不训练也能读出**。LDM 论文发现未调优的 27B 模型的读出已达到其调优后准确率的 97%（[2610.15501](https://arxiv.org/abs/2610.15501)）；FunDM 用 Qwen3-8B 的 24/36 层、无标签训练的小头恢复约 99% 的多选准确率，吞吐 1.56–1.57 倍、峰值显存降约三分之一（[2610.17175](https://arxiv.org/abs/2610.17175)）；LLM-as-Jev 的结论直接写进标题："LLM 已经是 Jev 式决策模型"（[2610.02076](https://arxiv.org/abs/2610.02076)）。

### 1.2.2 配方矩阵

| 名称 | 骨干 | 读出 / 头 | 训练目标 | 数据 | 校准 | 分支隔离 | 关键数字 | 出处 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Kev** 1.0 | Qwen3.5-0.8B/4B/9B、Qwen3.8-27B | rank-16 LoRA + 指针头 | 交叉熵（细节见 README） | `decision-v7`：10,000 条公开数据集样本 + 896 条生成策略样本 + 60 种规则结构的 1,680 条 | 每个检查点存一个温度（0.8B 2.35、4B 2.41、9B 2.19、27B 1.32；27B/9B 在从未训练的保留集上拟合） | 纯注意力骨干用树掩码+位置重置；**Qwen3.5/3.8 因 DeltaNet 忽略掩码，每个问题单独一行** | Kev-9B 对新来源问题有 2.4% 的情况把 ≥0.9 概率放在错误答案上；日期事实补充（`KEV_DATE_FACTS`）把截止期策略题从 0.80 提到 0.90（Jev 0.93）；提供 `/v1/systemone/permute` 多序测试 | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| **Tev1** | Qwen3.5-4B | 输出单个答案字母（letter） | SFT | 37,840 条唯一训练样本，约 17 美元、25 分钟 | 未说明 | 单问题/请求 | 880/1,000 主决策，300/300 策略迁移 | [togethercomputer/tev1](https://github.com/togethercomputer/tev1)、[Together 博客](https://www.together.ai/blog/how-to-train-your-own-jev) |
| **Bespoke Nimble** 9B | Qwen3.5-9B + LoRA | 枚举字段（1–255 个选择） | SFT | **对比数据策展**："改一个事实让答案翻转"，公开 2,676 条训练样本 + 324 条评测 | 未说明 | 8,192 token 上下文 | 在金融领域流行度偏移下 Macro-F1 −12.0（见 D4） | [bespokelabsai/nimble](https://github.com/bespokelabsai/nimble)、[模型卡](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B-v3) |
| **pplx-decider** v1.2 | 27B（继承 v1.1-27B） | 多读出/请求 | 未公开细节 | 未公开 | — | 请求内联合、请求间独立 | Decision Index 68.09（联合请求）对 67.75（分开）对 v1.1 的 62.30；**同一条消息的多个侧面联合问有利（PhishNChips +5.1），独立候选联合问有害（−0.2 到 −0.4）→"独立候选分开请求"** | [模型卡](https://huggingface.co/perplexity-ai/pplx-decider-v1.2) |
| **OneJev** 1.6 | Qwen3.5-0.8B/4B/9B、Qwen3.8-27B（多模态，视觉塔冻结） | 答案位置 | 交叉熵 + Brier | 99,193 题（公开 94,707），lr 5e-6，16,384 token，1 epoch | Brier 项 | — | H200 上一张 720p 截图：0.8B 1 问 31 ms / 10 问 51 ms；4B 64 / 104 ms；9B 81 / 131 ms | [OmniJev/OneJev](https://github.com/OmniJev/OneJev) |
| **Open-Jev**（Zefan-Cai）| Qwen 2B/9B/27B | LoRA（27B rank 8）+ 标量决策头 | — | 冻结的 148,639 行训练混合 | 保存温度 | — | 27B v1.1 的 127,787 行内部评测通过独立审计 | [Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev) |
| **open-jev / TOD**（daseinlabs）| Gemma 4 12B + LoRA；或冻结 Gemma 3 4B 上的小头 | 头 | — | 用户自带数据 | — | — | cookbook 01：84.2% / 66.3% 零样本 → 97.0% / 100%（team / priority） | [daseinlabs/open-jev](https://github.com/daseinlabs/open-jev) |
| **qwen-rlcd** | Qwen3.5-0.8B-Base（18 DeltaNet + 6 注意力） | letter / likelihood / PMI / `<|read|>` 头 | 仅推理（训练搁置） | — | — | **前缀分叉**替代树掩码；分叉对全前向 8–19 倍加速；0.8B 上分叉 vs 顺序误差 4.8e-5；穿过缓存的梯度检查未做 | [shamazharikh/qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| **Mapika decider** | 原版 Gemma-4-31B-it / Qwen3.6-27B（不改权重） | 读出 | 无训练 | — | **按选项数拟合温度** T(n)=max(0.05, 10.124 − 1.633·ln n) | — | Gemma-4-31B-it Decision Index 57.33，70 个里第 2；Qwen3.6-27B 51.35 第 8；decider-31b v2（合并微调）63.90 | [Mapika/decider](https://github.com/Mapika/decider) |
| **StartLux-Decision** v1.1 | 4B / 9B / 27B（Instant 与 AutoThink 两种） | 单遍（Instant 在全注意力层用双向注意力）；AutoThink 在 top 概率 < 0.9 时生成推理 | 三阶段：共享决策能力 → 分化 → AutoThink 的推理监督 + RL | 阶段 2 加入评分 / 安全 / 偏好 / 逻辑族后，DecisionPivot 上对应 18 个任务 +8.6 点，族外任务只 +0.3 | **策略感知校准**：184 种设置下置信-准确差 ≤2.7 pp | — | AutoThink 对 Instant 在 4B/9B/27B 分别 +18.4/+12.4/+11.5 点配对准确率；27B AutoThink 86.9%、Instant 75.4%；27B Instant 在 Decision Index 174 个条目中排第 1（2026-10-16） | [2610.17309](https://arxiv.org/abs/2610.17309)、[StartLuxLabs](https://github.com/StartLuxLabs/StartLux-Decision) |
| **Releasing the Inner Jev** | Gemma 4 31B / 12B、Qwen3.6-27B、Qwen3.5-4B | LoRA + 从 LM-head 切片初始化的决策头 + 学到的修正项 | 教师标签（Qwen3.5-122B-A10B、Qwen3.6-27B）；**软标签"可能"无益** | OpenDecisions | — | — | Gemma 4 31B 不微调 79.6 对 Jev 80.1，微调后 84.4；**LoRA 是改进的来源，对秩不敏感** | [2610.17205](https://arxiv.org/abs/2610.17205) |
| **LLM-as-Jev** | 4B 冻结（含 0.6B 实验） | 直接读 logits；列表式损失 + KL 正则 | — | — | — | — | 启用受 token 预算约束的原生思考后 JevBench 94.8%；0.6B 在 Banking77（77 类）从 22.2% → 60.5%；字母读出不能处理 77 类 | [2610.02076](https://arxiv.org/abs/2610.02076) |
| **LDM** | 三个基座（含 Gemma-4-31B） | 一次 prefill，最后位置经 LM-head 只归一化合法选项 logit | DDS（多样决策监督）+ SPRD（自提问推理蒸馏） | DecisionVista-Synth / Human | — | — | 比步数匹配基线 +1.8 / +1.5 点；对推理 rollout 182 倍中位延迟加速；路由用 27–58% 推理 token 恢复 92% 的推理优势 | [2610.15501](https://arxiv.org/abs/2610.15501) |
| **SII-Decision** | 4B / 27B（全秩与 LoRA 各一） | — | **Reasoning-to-Readout 自蒸馏** | — | — | — | 27B 在 JEVal 上与 Jev 持平，典型查询约 0.1 s | [2610.03935](https://arxiv.org/abs/2610.03935) |
| **Chinese Decision** | Qwen3.5-0.8B/2B/4B | 最后位置候选字母 logit，只对合法选项归一化 | 1 epoch，13.048M 决策 | 同左 | 验证集拟合温度；Q8_0 量化 | 每问题编译为共享指令+候选提示 | CJ-Bench 307,900 决策：4B 总体 85.97%，通用 75.69%，医/法/金融平均 84.00% | [2610.23170](https://arxiv.org/abs/2610.23170) |
| **Intern-Decision** | 0.8B / 2B / 4B 多模态 | 在完整 JSON 骨架里每字段一个决策占位符，用原生 LM-head 读出 | 自回归掩码 LM | — | 温度缩放：Brier 0.628→0.550、ECE 0.213→0.089 | 单次因果前向评估所有字段 | 4B 七套件平均 90.02% 对 Jev 1.13 的 88.74%；三字段 289 token 请求 RTX 4090 上 44.16 ms；置信交接把 JevBench-Hard 73.87%→87.39% | [2610.22131](https://arxiv.org/abs/2610.22131) |
| **AnyJev** | 冻结骨干 | **与问题无关的头**：仿射映射到最终层空间，复用原输出头 | — | — | — | — | 11 个模型平均反转选项列表改变 33% 的答案；旋转把顺序翻转率从 0.33 降到 0.14 / 0.18 | [2610.00831](https://arxiv.org/abs/2610.00831)、[nokia-applied-research/AnyJev](https://github.com/nokia-applied-research/AnyJev) |
| **OpenJev-RLCD** | Qwen3-1.7B | 显式概率 | "先校准再强化"：以同一个适当评分规则为奖励 | 两个真实推理任务 | 内生 | — | 与 SFT / RFT / GRPO（各加温度缩放）相比准确率持平或更好，选择性预测全部更优；GSM8K 答案验证单次查询可在 ≤5% 错误下决定 81% 的条目，GRPO 为 19% | [2609.38850](https://arxiv.org/abs/2609.38850) |
| **PACT** | — | 单 token 类型化决策 | 成对锚定校准微调 | — | — | — | 准确率 84.6 对已发布配方 85.2（无显著差）；位置偏置最低、重标注 9.8 对 13.8%；种子间方差减半、NLL −26%；"价值在稳健性而非准确率" | [2609.35865](https://arxiv.org/abs/2609.35865) |
| **this-that-model** 1.0 | 2B | 从指定位置的隐状态直接读出，限定在声明的选项集 | — | 42 族内部套件 | Brier 0.042 | 同一前向回答请求中的所有问题 | 笔记本 GPU 30.9 ms；第三方 68 题队列 0.941 对 Jev 0.765 | [2609.23886](https://arxiv.org/abs/2609.23886)、[FLock-io](https://github.com/FLock-io/this-that-model) |
| **System X** | Qwen3-0.6B → v4 Qwen3-1.7B LoRA | LLM-as-Jev 读出 + "文本回复"选项，赢时从 KV 缓存续写 | — | Reason-9k + Bitext | ECE 0.292→0.169 | 在提示缓存副本上打分，与全序列打分差 1.4e-6 | v4 JevBench 55.0%→61.0%；缓存复用省 15–39% 延迟 | [2610.25456](https://arxiv.org/abs/2610.25456) |
| **Our Own Jev** | 冻结骨干 + rank-16 LoRA + 指针头 | 一次前向答三问 | — | 148K Agent 编码会话 | — | — | 替代每遍约 1,000 美元的前沿裁判，1,000 会话约 3 分钟一张 GPU 约 0.06 美元 | [2610.29052](https://arxiv.org/abs/2610.29052) |
| **Decision Model Factory** | 可选骨干 | 只计算允许答案的概率，复用共享上下文 | 简短配方：训练→校准→验证→评测 | — | — | 专用 runner 在多问题负载上提速 2 倍以上 | 日语任务五个模型全部超过骨干，三个超过公开最优 | [2610.34956](https://arxiv.org/abs/2610.34956) |
| **SecJev** | 基于 Kev 的 0.8B–9B | Kev 单遍候选打分 | 场景加权训练 | SecJev-Corpus：14 任务 8 来源 | — | — | **SecJev-0.8B 比通用 Kev-9B 高 20.51 pp 任务宏准确率**；0.8B/4B 与仅答案的生成式微调准确率与延迟接近、峰值显存更低 | [2610.03073](https://arxiv.org/abs/2610.03073) |
| **AgentDecision-4B** | 4B | — | 在 Agent 自己犯错后到达的状态上训练，用 Jev 的答案做标签 | DecisionGym | 按选择逐项拟合阈值 | — | 分布外任务 91.5% 对 Jev 82.0%；分布内让 Agent 便宜 81.1–89.0%、快至 2.5 倍 | [2610.21412](https://arxiv.org/abs/2610.21412) |
| **SanSi / LEV**（循环） | 预训练为循环的 LM（LEV 2.6B 等） | 每个循环步后读选项，所有步联合训练 | 适当评分规则 | — | 小停止器按未标注请求拟合阈值 | — | SanSi 59 来源 10,027 决策 72.0%，比同形非循环 +13.5；LEV 2.6B JevBench 深度 1→4 从 63.2%→76.2%，按需深度省 15% 计算 | [2610.07730](https://arxiv.org/abs/2610.07730)、[2610.20951](https://arxiv.org/abs/2610.20951) |
| **Block-causal** | — | 候选无关的块因果注意力 + 位置重置 | — | — | — | 隔离 + 位置重置 | 仅隔离把测试翻转率 8.30%→3.82%，OOD 7.54%→3.71%；只重置位置更差 | [2610.01601](https://arxiv.org/abs/2610.01601) |
| **Prism-1** | Qwen3-8B / Gemma 4 12B | 位置与对手无关的打分 | — | — | — | — | 字母读出一次洗牌改变 20.0% / 11.9% 的答案；Prism-1 零翻转 | [2610.22066](https://arxiv.org/abs/2610.22066) |
| **Runoff** | 任意（免训练） | 先逐选项单独打分留下少数候选，再让每个候选占每个位置做列表比较 | 无 | — | — | 两次前向 | 构造上与顺序无关；两开源模型五数据集零翻转，循环平均 9.3%；20 选项时快 3–4 倍 | [2610.18233](https://arxiv.org/abs/2610.18233) |
| **ufakzeka-karar** | 土耳其语 | 选项盲头（order-invariant） | — | — | — | — | — | [2610.06744](https://arxiv.org/abs/2610.06744) |
| **JEV entailment reranking** | NeoHorse-1-4B | **mean-span 池化**替代选项末尾指针 | **选择性适配**：LoRA 保留在注意力与 Gated DeltaNet 投影，去掉 FFN 适配器 | MC11 | — | — | 可训练参数减半以上且准确率提升 | [2610.35654](https://arxiv.org/abs/2610.35654) |

补充的训练理论：Gaussian 代理下的精确风险计算表明，**学生继承教师偏差，更多学生数据不能消除，与教师的一致性也不能暴露它**；固定表示只在样本量低于某阈值时降低风险；温度缩放只在教师系数方向正确时消除全部超额风险（[2610.26797](https://arxiv.org/abs/2610.26797)）。这与"Releasing the Inner Jev"中"教师标签有用、软标签可能无用"的经验一致，也是 D4 中"教师偏差继承"子维度的来源。

### 1.2.3 小模型到底行不行：证据汇总

| 证据 | 结论 |
| --- | --- |
| SecJev-0.8B > Kev-9B（+20.51 pp）（[2610.03073](https://arxiv.org/abs/2610.03073)） | **领域数据 > 参数量** |
| AgentDecision-4B 分布外 91.5% > Jev 82.0%（[2610.21412](https://arxiv.org/abs/2610.21412)） | **在自己轨迹的状态上训练 > 通用模型** |
| 0.6B Banking77 22.2% → 60.5%（[2610.02076](https://arxiv.org/abs/2610.02076)） | 小模型能学会多类列表式读出 |
| Chinese Decision 4B 医/法/金融 84.00%（[2610.23170](https://arxiv.org/abs/2610.23170)） | 1 epoch、13M 决策即可得到可用的中文小决策模型 |
| this-that 2B 第三方 68 题 0.941 > Jev 0.765（[2609.23886](https://arxiv.org/abs/2609.23886)） | 单一来源，样本小，但方向一致 |
| JevCascade：150 类全菜单 69.0% → 精选 5 候选菜单 95.4%，**跨度 26 点，大于 0.8B 与 4B 之间的差距**；菜单干预可预测到 4.2 点以内（[2610.07716](https://arxiv.org/abs/2610.07716)） | **候选集设计比模型尺寸更一阶** |
| Microtask eligibility gap：现成 Qwen3 0.6/1.7/4/8B 在 4 个 Agent 微任务上 0/16 通过实践者阈值，4-bit 量化无法改变，Llama-3.x 12/12 不合格；建议"把 SLM 放在已达标的廉价基线后面，只在基线失效处用"（[2610.00025](https://arxiv.org/abs/2610.00025)） | **不训练的小模型不够用**，要么训练要么放在基线之后 |
| Measure Before You Train：739 封真实邮件上，约 200 标签的逻辑回归在每个字段上最准，少样本提示不能弥合差距；但"最准的系统"组合成动作后最常忽略需要处理的邮件（18% 对最佳 LLM 的 4%），对噪声概率设一个成本选择的阈值使其减半并成为最便宜的系统（[2610.32955](https://arxiv.org/abs/2610.32955)） | **先测量再训练；准确率不是产品指标；阈值是产品的一部分** |
| Jev-like（Qwen3-1.7B + LoRA + 37 个开源数据集）：域内置信度几乎精确跟踪准确率，域外一个在域内验证为 99.85% 的 0.99 门会失效（[mustafasemi-ai/jevlike](https://github.com/mustafasemi-ai/jevlike)） | 小模型校准**不迁移**到新分布 |
| 继续后训练小模型：SDFT 依赖强 ICL 与指令遵循能力，在小模型上失败；遗忘与获取不足与分布偏移线性相关（[2610.13113](https://arxiv.org/abs/2610.13113)） | 持续训练小决策模型需要控制分布偏移，这与 D1 直接相关 |

### 1.2.4 从配方矩阵读出的共识与分歧

**共识**

1. LoRA + 小读出头 + 温度即可复现接口；全秩不是必需。
2. 教师（更大模型）硬标签有效；对比/反事实数据（Nimble、Certo、DecisionPivot 训练集）对规则敏感性有效。
3. 校准必须在**保留分布**上拟合（Kev-27B/9B 的做法），且按**选项数**（Mapika）或**部署策略**（StartLux）拟合更稳。
4. 顺序偏置要在**结构上**解决（块因果、Prism-1、Runoff、AnyJev 旋转），不能靠训练数据洗牌解决（Prism-1 证明已发布的决策微调仍有翻转）。

**分歧 / 未定**

1. 软标签是否有益（Releasing the Inner Jev 说"可能无益"，OneJev 用 Brier，OpenJev-RLCD 用适当评分规则做奖励）。
2. 单遍 vs 循环（SanSi / LEV）vs 按需推理（StartLux AutoThink、Selective Reasoning、LDM 路由）：三条路都声称在"难题"上有大幅收益，但没有在同一基准、同一骨干上的对照。
3. 混合骨干（Gated DeltaNet）下**训练时**的分支隔离：Kev 用独立行绕开，qwen-rlcd 的前缀分叉只做推理，没有任何工作报告"在混合骨干上用树掩码训练"的结果（见 §1.3）。

### 1.2.5 对我们的含义（仅分析）

- 复现接口本身不是难点，**领域数据、候选集设计、按选择拟合的阈值、保留集校准**才是分数的来源。
- 小模型（0.6B–4B）在窄领域可以超过通用 9B–27B 与 Jev，但**不训练就不行**，且校准不迁移。
- 配方矩阵里几乎所有工作都把"示例 / 定义 / 规则"当作**训练数据**而非**推理时输入**；这正是 D1 与 D3 的空白所在。

## 1.3 骨干模型与混合架构约束（只调研不选型）

> 口径：**只调研，不选型**。用户要求"有 mamba 的都有这类问题，先调研再选型"。本节整理：Jev 式接口依赖的三个结构假设；混合骨干在哪一步破坏它们；开源复现各自怎么绕；推理系统文献能借什么；哪些问题没人研究。

### 1.3.1 Jev 式接口依赖的三个结构假设

Archer Hume 对托管 Jev 的探针（[architecture](https://archerhume.com/posts/jevs-architecture-unmasked)）与所有开源复现（§1.2）共享同一骨架：

1. **共享状态前缀**：状态编码一次，所有问题复用其缓存。"因果注意力描述哪些位置能用哪些信息，而不是输入 token 必须执行的顺序"——所以 prefill 阶段可以并行。
2. **问题分支隔离**：每个问题（及其选项）只能看见状态和自己，看不见兄弟分支。隔离给了接口语义："问客户是否生气不应改变票据进哪个队列"。探针证据：秘密放在兄弟分支 → 0.00，放在状态 → 概率上升。
3. **位置重置 / 读出**：每个分支的位置 ID 从状态末尾重新开始；在分支末 token 读出。

在**纯注意力**模型上，1–3 可以用一个树形注意力掩码 + 位置 ID 重置在一次前向里实现（Kev README："在纯注意力模型上，行与掩码给出相同概率"；[Kev](https://github.com/jaredpalmer/kev)）。块因果论文证明隔离本身就有价值：仅隔离把测试翻转率 8.30%→3.82%、OOD 7.54%→3.71%，只重置位置更差（[2610.01601](https://arxiv.org/abs/2610.01601)）。

### 1.3.2 混合骨干在哪一步破坏假设

| 事实 | 出处 |
| --- | --- |
| Qwen3.5-9B-Base：32 层 = **24 Gated DeltaNet（线性注意力）+ 8 全注意力**，hidden 4,096 | [Kev-9B 模型卡](https://huggingface.co/jaredpalmer/kev-9b) |
| Qwen3.5-0.8B-Base：24 层 = **18 Gated DeltaNet + 6 门控全注意力** | [qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| "Qwen3.5 与 Qwen3.8 混合注意力层与 Gated DeltaNet 层，后者是递归的，**忽略注意力掩码**" | [Kev README](https://github.com/jaredpalmer/kev) |
| "树形注意力掩码不能在递归层内隔离兄弟分支" | [qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| 混合模型的递归层**原地更新状态**，部分前缀重叠的缓存条目无法回滚，只能精确匹配命中 | [Marconi 2411.19379](https://arxiv.org/abs/2411.19379) |
| 缓存状态有**历史依赖**：相同 token 序列在不同缓存操作序列下产生不同缓存状态，前缀匹配不足以保证正确复用 | [Cache Engineering 2610.28577](https://arxiv.org/abs/2610.28577) |

已核实的层配置（2026-10-28 直接读取 Hugging Face 上各仓库的 `config.json`；全部为 `Qwen3_5ForConditionalGeneration`，`full_attention_interval = 4`，即每 4 层 1 层全注意力、3 层 Gated DeltaNet；词表 248,320，上下文 262,144）：

| 模型 | 层数 | 全注意力 / 线性注意力 | hidden | 注意力头 / KV 头 | FFN |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B（Base / Instruct 同） | 24 | 6 / 18 | 1,024 | 8 / 2 | 3,584 |
| Qwen3.5-2B（同） | 24 | 6 / 18 | 2,048 | 8 / 2 | 6,144 |
| Qwen3.5-4B（同） | 32 | 8 / 24 | 2,560 | 16 / 4 | 9,216 |
| Qwen3.5-9B（同） | 32 | 8 / 24 | 4,096 | 16 / 4 | 12,288 |
| Qwen3.5-27B、Qwen3.6-27B、**Qwen3.8-27B** | 64 | 16 / 48 | 5,120 | 24 / 4 | 17,408 |

三代 27B 的形状完全相同，差别只在权重；Qwen3.8 系列**没有 27B 以下的尺寸**（Hugging Face 上只有 `Qwen3.8-27B`、`Qwen3.8-2.4T-A95B`、`Qwen3.8-Flash-Next`，后两者为 MoE），Qwen3.6 也只有 27B 与 35B-A3B。因此"从小到大"的同架构阶梯只能是 Qwen3.5-0.8B / 2B / 4B / 9B → 27B（3.5 / 3.6 / 3.8 任一），这与 Kev、OneJev 等复现实际使用的四档一致（§6.1.5）。**终局尺寸取定在 27B / 35B 这一档**（2026-10-28 口径），而这里有一个必须先分清的事实：**27B 是稠密的，而 Qwen 没有稠密 35B——所有 35B 都是 `35B-A3B` 的 MoE（约 3B 激活）**。若终局落在 35B-A3B，则下面三个结构假设之外还多出一项"逐 token 专家路由是否在隔离分支间引入新耦合"，而本报告对此**零命中**（§6.1.5）。本机 `/mnt/cephfs/models/` 已有完整且未量化的 Qwen3.5-27B、Qwen3.6-27B、Qwen3.8-27B 三个 27B 检查点，可直接做"同形状、跨代权重"的对照——这正好把"小端与大端跨代"这一变量变成可测量的量：同一套决策评测在 3.5-27B 与 3.8-27B 上的差，就是跨代预训练带来的差，与尺寸无关。

**含义**：递归层让假设 2（隔离）不能靠掩码实现——分支 A 的 token 会通过递归状态"流进"分支 B。假设 1（共享前缀）仍成立，但复用的是**递归状态快照**而非 KV。

### 1.3.3 开源复现的三种绕法

| 方法 | 做法 | 代价 / 证据 | 出处 |
| --- | --- | --- | --- |
| **逐行执行（Kev）** | 每个问题一行："状态 + 该问题"，位置同树掩码方案；状态缓存计算一次、每行复用；服务端按 token 预算（每次前向一个最大 16,384 token 的行）分批，"内存不随问题数增长、答案不依赖分批" | 隔离精确；每行要重新把状态的递归状态读入；`forward()`（所有已发布数字的来源）与服务端结果在 fp32 舍入内一致 | [Kev](https://github.com/jaredpalmer/kev) |
| **前缀分叉（qwen-rlcd）** | 预填状态保留缓存（注意力层 KV + DeltaNet 层 conv 与递归状态）；沿 batch 维复制一行一分支；所有"问题 + 答案"分支右填充、同一位置偏移一批跑；在各分支最后真实 token 读隐状态 | 比每分支一次前向快 8–19×；分块分支约束内存；0.8B 实权重上分叉 vs 顺序误差 4.8e-5（容差 1e-3），递归状态清零的阴性对照 6.3；**"穿过缓存的梯度检查推迟到训练时"**——训练暂停 | [qwen-rlcd](https://github.com/shamazharikh/qwen-rlcd) |
| **共享上下文锚定 + 候选前缀共享 + 决策引导剪枝（FastJEV）** | 复用递归初始状态、省略未用的最终递归缓存；保留后续分支需要的中间状态；按小无标签集上的相对分数变化剪枝深度 | 候选深度 −43.75–45.83%，保留 93.66–97.52% 任务分数；**"候选前缀共享能减少重复计算但会增加延迟"**；"共享粒度与执行调度要一起设计" | [2610.11379](https://arxiv.org/abs/2610.11379) |

另外两个与架构相关的训练侧选择：

- **选择性适配**：LoRA 保留在注意力与 Gated DeltaNet 投影上、去掉 FFN 适配器，MC11 上优于全模块基线且可训练参数减半以上（[2610.35654](https://arxiv.org/abs/2610.35654)）；Kev-9B 的 LoRA 也打在注意力、MLP 和 DeltaNet 投影上（45.4M 参数）。
- **StartLux Instant**：在**全注意力层**内对提示做双向注意力（llama.cpp 非因果标志、vLLM 插件）——只改注意力层，递归层不动（[StartLux](https://github.com/StartLuxLabs/StartLux-Decision)）。这说明在混合骨干上"改读法"的自由度集中在少数注意力层。

### 1.3.4 推理系统文献能借什么

| 工作 | 适用层 | 要点 | 出处 |
| --- | --- | --- | --- |
| Hydragen | 注意力 | 共享前缀与唯一后缀分开计算注意力 | [2402.05099](https://arxiv.org/abs/2402.05099) |
| DeFT | 注意力 | 树形 KV 的 IO 复用与负载均衡 | [2404.00242](https://arxiv.org/abs/2404.00242) |
| Block-Attention | 注意力 | 文档分块独立算 KV，最后一块看全部 | [2409.15355](https://arxiv.org/abs/2409.15355) |
| IPPD | 注意力 | 虚拟位置 ID + 掩码操纵在一个提示内并行答多个同上下文问题，不改架构 | [2609.05707](https://arxiv.org/abs/2609.05707) |
| Visual Jev | 两者（实现上批处理隔离后缀） | 图像与公共上下文编码一次、隔离问题后缀批处理：N=32 时暖态 8.9× 于串行、3.4× 于重算前缀的批处理，峰值内存更高；类型化头无一致优势 | [2609.25845](https://arxiv.org/abs/2609.25845) |
| Marconi | 递归 | 混合模型前缀缓存的准入/逐出策略：token 命中率最高 34.4×、TTFT −71.1% | [2411.19379](https://arxiv.org/abs/2411.19379) |
| Cache Engineering | 两者 | Agent 直接 drop/repos 缓存；历史依赖的服务挑战 | [2610.28577](https://arxiv.org/abs/2610.28577) |
| FastJEV | 两者 | 见 8.3 | [2610.11379](https://arxiv.org/abs/2610.11379) |

注意力层的工作（前四项）解决的是**同一问题**的不同面：在树上共享前缀的 IO。它们都假设掩码有效，因此只覆盖混合骨干中的注意力层；递归层只有 Marconi 与 FastJEV 两篇。

### 1.3.5 纯注意力骨干作为对照

复现工作中用到的纯注意力骨干：Qwen3 系列（OpenJev-RLCD 的 Qwen3-1.7B；FunDM 的 Qwen3-8B；System X / SHIFT-JEV / Microtask 的 Qwen3-0.6B–8B）、Gemma 3（daseinlabs 在冻结 Gemma 3 4B 上的决策头）、Qwen3-8B / Gemma 4 12B（Prism-1）、Gemma 4 31B（Releasing Inner Jev）。在这些骨干上，Kev README 所述的"行与掩码等价"成立，树掩码方案可直接训练（梯度穿过共享前缀没有递归状态问题）。

**成本对比的空白**：没有工作在同等参数量下比较"混合骨干 + 逐行/分叉"与"纯注意力 + 树掩码"的决策准确率、校准与延迟。现有数字分散：OneJev（Qwen3.5 混合）0.8B 31/51 ms、4B 64/104、9B 81/131（[OneJev](https://github.com/OmniJev/OneJev)）；Intern-Decision 4B 44.16 ms（[2610.22131](https://arxiv.org/abs/2610.22131)）；this-that 2B 30.9 ms（[2609.23886](https://arxiv.org/abs/2609.23886)）；测量条件各不相同。

### 1.3.6 本节矩阵

| 问题 | 纯注意力 | 混合（DeltaNet） | 证据状态 |
| --- | --- | --- | --- |
| 共享状态前缀（推理） | KV 复用，成熟 | 递归状态快照复用（Kev、qwen-rlcd、FastJEV） | 都可做 |
| 分支隔离（推理） | 树掩码一次前向 | 逐行 / 前缀分叉（多行 batch） | 混合可做，内存与调度代价有数字（8–19×、FastJEV 的延迟警告） |
| 分支隔离（**训练**） | 树掩码，梯度自然流过 | 分叉缓存需穿过复制的递归状态求梯度 | **qwen-rlcd 明确推迟；无任何文献** |
| 前缀缓存服务 | vLLM 等成熟 | Marconi 式准入/逐出 | 混合有一篇 |
| 读法改动（双向等） | 全层可改 | 只有注意力层可改（StartLux） | 已有实践 |
| 适配器位置 | 任意 | 注意力 + DeltaNet 投影，去 FFN（2610.35654） | 一篇 |
| 同参数量混合 vs 纯注意力的决策质量 | — | — | **无** |

### 1.3.7 盲区（供选型前补齐）

1. **训练时的分支隔离**在混合骨干上没有文献：Kev 的训练用"逐行"（每问题一行），等价但代价是状态重复编码；qwen-rlcd 的分叉方案在训练上"推迟"。要么接受逐行训练成本，要么证明穿过复制递归状态的梯度正确——两者都没有公开数字。
2. **递归层对"大状态里的无关细节"是否比注意力更敏感**：D2/D4 的证据（Jev 20k token 内检索无误，但多次更新互相干扰）全部来自托管 Jev，架构未知；无开源混合 vs 纯注意力的对照。
3. **顺序偏置的结构性缓解**（块因果、Prism-1、Runoff）在混合骨干上如何实现：块因果依赖掩码；Runoff 是两次前向（与架构无关）；Prism-1 的实现细节未核。
4. **量化与融合核**：Kev 在 CUDA 上用融合 DeltaNet 核 + CUDA 图，bf16 对 fp32 最多 0.03/0.05 偏差；Chinese Decision 的 Q8_0 改 0.4–1.1% top-1——都是单点数字，没有按层类型拆分。
5. ~~Qwen3.6 / 3.8 的层配置没有可核实的数字~~——已于 2026-10-28 从 `config.json` 核实并列在 8.2；剩余的空白是 Qwen3.8 没有小尺寸，小→大阶梯必须跨代（Qwen3.5 小模型 → 3.8-27B），跨代的预训练 / 后训练差异本身是一个未被任何文献控制的变量。

## 1.4 问题定义的跨论文比较：同一个词，不同的定义

> 口径：用户要求"把问题定义详细地总结下，不同论文的学术定义很可能不一样"。本节只做定义层面的梳理与比较，不提出我们自己的定义（那是下一阶段的工作），但在 §1.4.10 列出"我们定义问题时必须先回答的分歧点"。所有引文都回到缓存的全文 / 摘要 / 文档核对过；没有核到的定义标注"未核实"。

### 1.4.1 为什么定义会分歧

Jev 发布只有六周，TypeSafe 没有公开训练细节与形式化定义，社区同时在做三件事：复现（需要可操作的定义）、审计（需要可检验的定义）、理论化（需要公理化的定义）。三种动机给出的"决策模型"定义互相不兼容，而且**同一个指标名（ECE、翻转率、置信度、RLCD）在不同论文里指不同的量**。跨论文比较数字之前必须先对齐定义，这也是 README §4 "跨论文的数字不可直接比较"的根源。

### 1.4.2 "决策模型"叫什么、指什么

| 命名 | 定义要点 | 出处 |
| --- | --- | --- |
| **System One model**（TypeSafe） | "trained for calibrated decisions: their probabilities are optimized against outcomes to reflect uncertainty. Calibration is measured across groups of predictions; it does not guarantee that an individual answer is correct"；"designed to return stable answers across repeated evaluations"（Self-consistent）；不写回复、不产代码、不生成解释；归入"Machine Native Intelligence"；训练路径是 RLCD（与 RLHF、RLVR 并列的"第三条后训练路径"） | [system-one](https://docs.typesafe.ai/concepts/system-one)、[how-to-build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one)、[ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer) |
| **Typed decision model（TDM）** | 审计类论文的通用名；强调"类型化"接口而非训练方式："Type-Safe Is Not Error-Free"、"Labels Override Definitions"、"TDMs under Prevalence Shift"、"How Reliably Do TDMs Use Fallback"、"open TDMs" | [2609.32160](https://arxiv.org/abs/2609.32160)、[2609.26758](https://arxiv.org/abs/2609.26758)、[2610.02586](https://arxiv.org/abs/2610.02586)、[2610.26325](https://arxiv.org/abs/2610.26325)、[2610.19856](https://arxiv.org/abs/2610.19856)、[2609.31142](https://arxiv.org/abs/2609.31142) |
| **Typed decision models, also called System One models** | "return such probabilities without generating text"；目的物是"decision gates"："Software that hands branching decisions to a model needs a declared option and a probability it can threshold" | [2610.00346](https://arxiv.org/abs/2610.00346) |
| **Large Decision Model（LDM）** | "processes the task in one prefill, projects the last input hidden state through the LM head, and normalises only the allowed option logits"；Choice 2–8、Score 3–6 的上限"是实现选择，不是 LDM 定义的一部分"；把训练叫 **decision tuning**，把输出叫 **readout** | [2610.15501](https://arxiv.org/abs/2610.15501) |
| **General decision model** | 决策实例是四元组（state, instruction, criteria, gold）："state 提供决策所需信息，instruction 指定决策目标，criteria 定义合法决策空间"；读出叫 **First-Token Decision Readout**（答案位置、限定合法选项标签的分布，一次前向得到 choice / noul / score） | [2610.03935](https://arxiv.org/abs/2610.03935) |
| **Narrow Decision Model（NDM）** | 八条 desiderata：D1 类型化输出（闭集上的分布，绝不自由文本）；D2 校准（"among answers given probability p, about p are right"，按问题类型分别测量、调整、报告）；D3 单遍（一次请求的所有问题与选项在一次前向内回答，状态只编码一次）；D4 选项置换不变（重排选项只置换输出分布，别的不变）；D5 问题隔离（答案不依赖同一请求里的其他问题及其选项）；D6 弃权（每个 Choice 可含显式"none of these"，其概率单独校准）；D7 读而非记（选项由描述识别，可处理未见选项与未见组织架构）；D8（结构项，未摘录）。自称给出"System One decision contract 的形式化陈述"，含**声明 / 未声明两种弃权机制**与**集合值训练目标**，并要求"接受或拒绝机制的评测协议在打开保留数据之前完成"（contract tests） | [2610.25553](https://arxiv.org/abs/2610.25553) |
| **Prefill-only decision model** | "score every candidate in a menu in a single forward pass and never decode"；核心性质是 **readout stability**（Definition 1：把菜单限制到子集后的分布等于原分布在该子集上的归一化） | [2610.07716](https://arxiv.org/abs/2610.07716) |
| **System 1 decision models** | "architectures that map an input directly to a typed, structured decision in a single forward pass"；五族分类：编码器分类器、奖励模型、非自回归决策引擎、对比决策模型、抽取模型 | [2610.33775](https://arxiv.org/abs/2610.33775) |
| **System 1 / 能否交给 System 1** | 问题是"can it be left to a fast model that answers with calibrated probabilities in a single forward pass, or does it still need a generative LLM" | [2610.21244](https://arxiv.org/abs/2610.21244) |
| **Probability-only model** | "return calibrated probabilities for fixed choices in milliseconds and generate no text" | [2610.09188](https://arxiv.org/abs/2610.09188) |
| **Candidate-scoring decision model** | "return a probability distribution over a presented set of answers"；三种训练成分（软目标、冻结骨干、温度）决定"这些概率估计的是什么" | [2610.26797](https://arxiv.org/abs/2610.26797) |
| **Decision models（FunDM）** | "score candidate answers or actions"——把动作选择和答案选择视作同一类 | [2610.17175](https://arxiv.org/abs/2610.17175) |
| **Direct-decision model** | "JEV-like direct-decision models"，强调跳过推理直接出分布，用于序数偏置研究 | [2609.38827](https://arxiv.org/abs/2609.38827) |
| **One-pass decision model** | 结论性定义："best used as fast selectors over a state that a reasoning model has computed and checked"，即决策模型是**选择器**而不是**计算器** | [2610.24929](https://arxiv.org/abs/2610.24929) |
| **System 1.5** | 循环模型：每个循环步读一次选项，"一个模型服务从 1 到 8 次循环的每种预算" | [2610.07730](https://arxiv.org/abs/2610.07730) |
| **Atomic action** | "fast, single-step decisions such as classification, semantic endpointing, Boolean checks, and scoring — formulated as constrained generation with single-token outputs"（仍是生成式解码，只是单 token） | [2609.36115](https://arxiv.org/abs/2609.36115) |
| **Native typed decision-making** | 动作编码器把每个候选动作描述并行嵌入，与 LLM 内部状态打分得到类型化动作分布 | [2609.36116](https://arxiv.org/abs/2609.36116) |
| **Machine intuition** | "recognising patterns and judging situations without explicitly unfolding every intermediate step"，作为独立可训练能力 | [2609.39111](https://arxiv.org/abs/2609.39111) |
| **Typed probabilistic assessor** | Laya 的自述：回答工作流状态上的 choice / noul / score 问题 | [2609.33843](https://arxiv.org/abs/2609.33843) |
| **自然语言接口的 System One** | 反对"结构化 schema 对象编码状态、意图与候选"，主张请求与候选都用自然语言表达，候选空间可到百万级开集 | [2610.11316](https://arxiv.org/abs/2610.11316) |
| **"LLM 已经是 Jev 式决策模型"** | 冻结聊天模型直接读 logits 即满足定义；"决策模型"是读出方式而不是模型类别 | [2610.02076](https://arxiv.org/abs/2610.02076) |

**分歧点**：（1）定义的主体是**接口**（TDM、LDM、JEVal）、**性质**（NDM 八条、readout stability）、**训练方式**（TypeSafe 的 RLCD、"optimized against outcomes"）还是**用途**（decision gate、fast selector、能否交给 System 1）；（2）"不生成文本"是否是定义的一部分——Koa-decision 与 SALSA 单 token 生成、System X 从 KV 缓存续写、StartLux AutoThink 先推理再读出，都自称决策模型；（3）选项上限（255 / 2–8 / 百万级）是否属于定义；（4）"校准"在 TypeSafe 是训练目标的描述，在 NDM 是契约条款，在审计论文是待检验的假设。

### 1.4.3 请求 / 契约的形式化

| 形式化 | 内容 | 出处 |
| --- | --- | --- |
| TypeSafe 三原语 | Noul（单个概率）、Choice（≤255 个选项上的分布）、Score（2–10 个有序级别上的分布）；一个请求 = 一个 state + 多个 questions；state 与问题分离，示例可放在 state 或问题的 examples 字段 | §1.1、[state 文档](https://docs.typesafe.ai/concepts/state) |
| Kev 的问题 schema | `{"type": "choice", "instructions": …, "criteria": {name: definition, …}}`，选项由"名称 + 定义"对给出 | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| JEVal 四元组 | (state, instruction, criteria, gold)；criteria 定义合法决策空间 | [2610.03935](https://arxiv.org/abs/2610.03935) |
| LDM | Choice 2–8 命名选项、yes/no、Score 3–6 级；上限是实现选择 | [2610.15501](https://arxiv.org/abs/2610.15501) |
| NDM 契约 | 闭集分布 + 按问题类型校准 + 单遍 + 置换不变 + 问题隔离 + 显式弃权 + 读选项描述；声明 / 未声明弃权；集合值目标；合成数据引擎带"有效性守卫"；"specification first" | [2610.25553](https://arxiv.org/abs/2610.25553) |
| Probability Contracts | 把 Event（Noul）与 Choice 两种接口当作两个可能不一致的"概率契约"：同一事实用两种接口问，再比较"规范后验误差"、"补集残差"、"粗化残差"；Jev 的 Event 与 Choice 接口在 10% 延迟成本下**改变 32.8% 有效配对的二元动作** | [2609.37470](https://arxiv.org/abs/2609.37470) |
| 多问题共享状态 | Verdict："answering many small typed questions about one piece of state"；结构化掩码让状态编码与问题无关、问题互不影响、选项顺序无关"by construction"；Intern-Decision 在完整 JSON 骨架里每字段一个决策占位符 | [2610.20778](https://arxiv.org/abs/2610.20778)、[2610.22131](https://arxiv.org/abs/2610.22131) |
| 单 token 受限生成 | Koa-decision 的原子标签 token；SALSA 的类别→token 映射 | [2609.36115](https://arxiv.org/abs/2609.36115)、[2510.22691](https://arxiv.org/abs/2510.22691) |
| 自然语言请求 + 自然语言候选 | MetaEncoder：无 schema，候选可到百万级 | [2610.11316](https://arxiv.org/abs/2610.11316) |
| 动作空间 | FunDM / Dyad / AgentDecision：候选是动作描述；DecisionGym 三级（L1 孤立问题、L2 记录轨迹上的步级、L3 控制运行中的 Agent） | [2610.17175](https://arxiv.org/abs/2610.17175)、[2609.36116](https://arxiv.org/abs/2609.36116)、[2610.21412](https://arxiv.org/abs/2610.21412) |

**分歧点**：Event 与 Choice 是否是同一个契约（2609.37470 证明 Jev 上不是）；"选项 = 名称 + 定义"时模型跟谁（2609.26758：跟名称；2610.02586：标签压倒定义）；多问题是"隔离"（NDM D5、Verdict）还是"联合有利"（pplx-decider：同一消息的多个侧面联合问 +5.1，独立候选联合问 −0.2 到 −0.4，见 §1.2）。

### 1.4.4 "置信度"指什么

| 定义 | 内容 | 出处 |
| --- | --- | --- |
| TypeSafe `confidence` | 把分布形状压成 0–1 的一个数："1 when all the probability is on one outcome and 0 when the probability is spread evenly"；Noul 没有这个字段；§1.1给出其公式只依赖最高概率（(p_max − 1/n)/(1 − 1/n)） | [confidence 文档](https://docs.typesafe.ai/confidence)、§1.1 |
| 最高概率 | "confidence to be the probability of its verdict"；并指出 Jev 原生字段"是整个标签分布的一个统计量，其公式未公开"，两者 Spearman 0.976；SanSi 同样"Confidence is the top probability" | [2609.26550](https://arxiv.org/abs/2609.26550)、[2610.07730](https://arxiv.org/abs/2610.07730) |
| 期望误差 | ufakzeka-karar 返回温度缩放概率 + "an expected error that serves as a 'not sure' signal" | [2610.06744](https://arxiv.org/abs/2610.06744) |
| 学到的不确定性分数 | SHIFT-JEV 从不确定性、格式、选项一致性三类信号学一个风险分数，与最高概率分数对比（目标风险 10% 下超标 3–5 对 5–15 / 27） | [2610.34329](https://arxiv.org/abs/2610.34329) |
| 两种不确定性（训练视角） | OpenJev-RLCD：结果"one-hot when there is a right answer (epistemic uncertainty) and spread when humans disagree (aleatoric uncertainty)"；"Aleatoric uncertainty: when RL cannot help" | [2609.38850](https://arxiv.org/abs/2609.38850) |
| 两种不确定性（部署视角） | 人类分歧 vs 决策风险；非对称损失下两者要求相反的升级信号，"no single confidence number serves both"；把判断拆成并行子问题读分散度可恢复分歧信号 | [2610.33258](https://arxiv.org/abs/2610.33258) |
| 校准 vs 敏感性 | "calibration and sensitivity (how well confidence separates right from wrong answers) are distinct"；最敏感模型的置信度追踪"哪类情境会失败"而非"哪个答案错" | [2610.09683](https://arxiv.org/abs/2610.09683) |
| 答案置信 vs 自知 | "你知道答案吗"类 Noul 与答案置信分离；表面线索会伪装成自知 | [2610.01006](https://arxiv.org/abs/2610.01006) |
| 决策模型"不知道自己的极限" | "its confidence flags the errors it makes itself but not" 输入错误继承的错误 | [2610.24929](https://arxiv.org/abs/2610.24929) |
| 答案质量（answer mass） | AnyJev 用"合法选项上的总概率质量"作为读出的归一化项与有效性指标 | [2610.00831](https://arxiv.org/abs/2610.00831) |

**分歧点**：置信度是（a）分布形状的统计量（TypeSafe），（b）top-1 概率（多数审计），（c）学到的风险分数（SHIFT-JEV），还是（d）两个不可合并的量（2610.33258）。（a）与（b）在排序上高度相关，但**在阈值层面不等价**（同一 0.6 阈值在 2 选项与 10 选项下含义不同），且都不是"错误检测器"（§4.2 D1）。

### 1.4.5 "校准"怎么定义、怎么测

| 定义 / 指标 | 内容 | 出处 |
| --- | --- | --- |
| TypeSafe | "measured across groups of predictions; it does not guarantee that an individual answer is correct" | [system-one](https://docs.typesafe.ai/concepts/system-one) |
| NDM D2 | "among answers given probability p, about p are right"，**按问题类型**分别测量、调整、报告 | [2610.25553](https://arxiv.org/abs/2610.25553) |
| ECE，15 等宽分箱 | Choice 用最高选项概率，Noul 用其概率；"top-label ECE, 15 equal-width bins, the last bin closed" | [2609.37647](https://arxiv.org/abs/2609.37647)、[2610.26325](https://arxiv.org/abs/2610.26325) |
| ECE，10 等宽分箱 | JEVal："ten equal-width confidence bins"；SanSi：十等宽、只在可回答项上 | [2610.03935](https://arxiv.org/abs/2610.03935)、[2610.07730](https://arxiv.org/abs/2610.07730) |
| ECE，15 等质量分箱 | AnyJev | [2610.00831](https://arxiv.org/abs/2610.00831) |
| 等质量分箱 + 偏差感知估计 | benchmark 论文以"估计依赖分箱方案"为由采用 | [2610.00346](https://arxiv.org/abs/2610.00346) |
| 相对有限样本零假设的 ECE | TypedBench："calibration relative to a matched finite-sample null ECE"，并报 smooth ECE、Brier、NLL、5% 风险下覆盖率、翻转率、JSD、RPS、QWK、非对称代价下的决策价值；评测跨"友好 / 对抗"两种表述 | [2610.11392](https://arxiv.org/abs/2610.11392) |
| smooth ECE | ufakzeka-karar（温度缩放在开发集降、在保留支持题升 0.027→0.045） | [2610.06744](https://arxiv.org/abs/2610.06744) |
| 带符号置信-准确差 | Laya 审计：−0.214，所有占用箱准确率高于置信，"符号一致让每种分箱 ECE 变体坍缩到同一个值"；方向决定级联往哪边失效 | [2609.33843](https://arxiv.org/abs/2609.33843) |
| 适当评分规则 | Brier、log-loss、RPS 作为训练目标与评测（jevlike、Open-Jev、NDM、SanSi、OpenJev-RLCD、UniJev CORA） | §6.1 C 族 |
| 选择性预测 / AURC | 按置信排序后的风险-覆盖曲线（OpenJev-RLCD、PACT、2609.37647） | [2609.38850](https://arxiv.org/abs/2609.38850)、[2609.35865](https://arxiv.org/abs/2609.35865) |
| 策略感知校准 | 在部署策略（选择、路由）下测置信-准确差，184 种设置 ≤2.7 pp；"下游选择会扭曲置信-准确关系即使模型不变" | [2610.17309](https://arxiv.org/abs/2610.17309) |
| 风险预算 / 错误遗漏风险 | 不确定时默认保守兜底，在"被分配效用最大动作"的子集内控制错误遗漏风险；朴素阈值在约一半设置超标，Learn Then Test 7.8% | [2610.19811](https://arxiv.org/abs/2610.19811) |
| 先验偏移下的校准 | 候选限定、EM 先验校正、35 个预注册配对检验 | [2610.26325](https://arxiv.org/abs/2610.26325) |
| 概率公理 / 相干 | 否定对之和偏离 1：Jev 0.064，Qwen3.8-27B 首 token 0.293、口头概率 0.122；层级边缘化与直接问的总变差：Jev 0.219–0.349，Laya 0.424–0.689 | [2609.33209](https://arxiv.org/abs/2609.33209)、[2609.33971](https://arxiv.org/abs/2609.33971) |
| 跨接口一致 | 规范后验误差、补集残差、粗化残差 | [2609.37470](https://arxiv.org/abs/2609.37470) |

**分歧点**：（1）分箱方案（10/15、等宽/等质量、末箱闭合）直接改变 ECE 数值，跨论文不可比；（2）"校准"是否包含相干性（2609.33209 / 2609.33971 认为不包含，需单列）；（3）校准在"孤立问题"还是"部署策略"下测（StartLux、2610.19811、2609.37470 认为后者才是产品指标）；（4）Noul 的校准是否按正负类分别测（2609.37647 用 Noul 概率本身，TypedBench 用友好 / 对抗表述）。

### 1.4.6 "一致性 / 翻转"怎么定义

| 定义 | 内容 | 出处 |
| --- | --- | --- |
| 重复性 | 同一请求多次调用的 ICC（0.997）；test-retest 地板（"Jev is not deterministic, so … the flip rate between two identical runs"）；固定顺序重复作为对照；同文重跑翻转 0.17% | [2609.36399](https://arxiv.org/abs/2609.36399)、[2609.26758](https://arxiv.org/abs/2609.26758)、[2610.35826](https://arxiv.org/abs/2610.35826)、[2609.31142](https://arxiv.org/abs/2609.31142) |
| 一次洗牌翻转 | 字母读出一次洗牌改变 12–20%（Qwen3-8B 20.0% / Gemma 4 12B 11.9%，已发布微调 9.1%） | [2610.22066](https://arxiv.org/abs/2610.22066) |
| 累积失败集 | 八种呈现下追踪单题："accuracy varies by less than two percentage points, yet its cumulative failure set expands by 27–29% relative to the original order"；即**准确率稳定 ≠ 单题稳定** | [2610.35826](https://arxiv.org/abs/2610.35826) |
| 列表反转 | 11 个模型平均反转选项列表改变 33% 的答案 | [2610.00831](https://arxiv.org/abs/2610.00831) |
| 顺序不变（定义） | Runoff Definition 1：决策规则对任意选项顺序给出相同分布；NDM D4：重排只置换分布 | [2610.18233](https://arxiv.org/abs/2610.18233)、[2610.25553](https://arxiv.org/abs/2610.25553) |
| Luce 两公理 | 顺序无关 + 加选项不改其他选项的相对赔率；定理：只有"每个选项的分数只依赖自身"的 softmax 同时满足两者；"a well-chosen added option steers 4–34% of decisions" | [2610.22066](https://arxiv.org/abs/2610.22066) |
| IIA / 克隆 / 诱饵 | 预注册测试 Jev 的选项集依赖（诱饵、填充） | [2610.16655](https://arxiv.org/abs/2610.16655) |
| 读出稳定性 | 菜单限制后分布 = 原分布归一化（Definition 1）；成立时限制预测器精确 | [2610.07716](https://arxiv.org/abs/2610.07716) |
| 定义级翻转 | "track changes in the selected definition rather than in the returned name"：交换名称-定义绑定后，跟定义的模型应返回不同名称；AUC 93.8% → 23.2% | [2609.26758](https://arxiv.org/abs/2609.26758) |
| 标签压倒定义 | 删除 / 矛盾 / 反转定义三种干预 | [2610.02586](https://arxiv.org/abs/2610.02586) |
| 答案保持变体 | 只保留"不应改变答案"的 5,586 个变体，只攻击正确决策：翻转 46.3% 对同文重跑 0.17% | [2609.31142](https://arxiv.org/abs/2609.31142) |
| 等价措辞 vs 同文重复 | "changes answers more across equivalent wordings than across identical-text repeats" | [2610.30045](https://arxiv.org/abs/2610.30045) |
| 序数压缩 | "candidate-space compression"：选项数与压缩相关、方向不唯一、大模型仍偏置 | [2609.38827](https://arxiv.org/abs/2609.38827) |
| 位置偏置（训练指标） | PACT："answer flips under relabelling" 9.8 对 13.8% | [2609.35865](https://arxiv.org/abs/2609.35865) |
| 问题隔离 | NDM D5；Verdict 的结构掩码；pplx-decider 的"联合 / 分开请求"实验 | [2610.25553](https://arxiv.org/abs/2610.25553)、[2610.20778](https://arxiv.org/abs/2610.20778) |

**分歧点**：（1）"翻转率"至少有五种分母（一次洗牌、八种呈现累积、列表反转、重标注、答案保持变体）；（2）顺序不变性是**构造保证**（Prism-1、块因果、Verdict、NDM）还是**经验度量**（AnyJev、2610.35826）；（3）"一致"的对象是名称、定义还是分布（2609.26758 的核心区分）；§4.2 30 个子维度是在这些定义之上的枚举。

### 1.4.7 "RLCD"至少有四种含义

| 用法 | 含义 | 出处 |
| --- | --- | --- |
| TypeSafe | 与 RLHF、RLVR 并列的"第三条后训练路径"，"probabilities are optimized against outcomes"；**算法、奖励、数据均未公开** | [ML primer](https://docs.typesafe.ai/introduction/machine-learning-primer) |
| 带推理链的适当评分奖励 | OpenJev-RLCD：每条推理链后读出承诺的分布，用严格适当评分规则打分；方差恒等式区分"逐链打分"与"混合打分"（后者 = RLVR + 多样性奖励）；"先校准再强化" | [2609.38850](https://arxiv.org/abs/2609.38850) |
| RLCD²（推理质量差分奖励） | StartLux AutoThink：推理前后两次读出的适当评分之差 + 软长度惩罚；只用于生成推理的模型 | [2610.17309](https://arxiv.org/abs/2610.17309) |
| 五种"RLCD 算法"的统称 | UniJev 比较 Shaped RLCD、GRPO、CtR、RLCD-lite、Rewarding Doubt；其 Table 1 把 Von / OneJev / Open-Jev 的 CE + Brier 和 Kev / NanoJev 的 CE 列为"direct gradient"对照 | [2610.25784](https://arxiv.org/abs/2610.25784) |
| "开源 System One 模型发布的 RLCD 配方" | SBERT2S1 指一种带奖励归一化的得分函数估计器（REINFORCE 式），比交叉熵低 2.5–3.0 点 | [2610.02486](https://arxiv.org/abs/2610.02486) |
| "对适当评分规则做强化学习" | benchmark 论文对 Laya 的描述："trained with reinforcement learning against proper scoring rules, a recipe its developers call RLCD" | [2610.00346](https://arxiv.org/abs/2610.00346) |
| 替身 | jevlike："our open-source stand-in for TypeSafe's unpublished RLCD. We claim no equivalence"——实际是 CE + 0.5·Brier | [mustafasemi-ai/jevlike](https://github.com/mustafasemi-ai/jevlike) |
| 等价定理 | NDM："proper scoring rules applied directly when labels are known … reach the same optimum as the policy gradient of an RLCD-style reward without its variance" | [2610.25553](https://arxiv.org/abs/2610.25553) |
| 社区命名 | `SFT + RLCD`（S²-MAS）、`qwen3-0.6b-rlcd-decision`、`rlcd-modernbert-151m`、`Qwen-2.5-1B-RLCD` 等模型名，训练细节各异 | [2610.27746](https://arxiv.org/abs/2610.27746)、HF 探测记录 |

**分歧点**：读到"RLCD"时必须先问三件事——有没有推理链、奖励是正确性还是适当评分、是策略梯度还是直接梯度。§6.1.3 的结论"单遍模型上 RL 无正面证据"只对"无推理链 + 策略梯度"这一种含义成立。

### 1.4.8 "弃权 / 兜底 / 不知道"怎么定义

| 定义 | 内容 | 出处 |
| --- | --- | --- |
| 显式选项 + 单独校准 | NDM D6："none of these" 的概率单独校准；声明（选项里有）与未声明（选项里没有，靠概率）两种机制 | [2610.25553](https://arxiv.org/abs/2610.25553) |
| 概率带 | TypeSafe cookbook：0.30–0.70 映射为 `uncertain` 交人工，并明确"The band is illustrative; it is neither a calibrated guarantee nor an optimized threshold"；confidence routing 用全局下限（示例 0.6）+ 每类动作阈值 | [consistency cookbook](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook)、[confidence-routing](https://docs.typesafe.ai/patterns/confidence-routing) |
| 评测口径里的弃权 | JevBench 把 yes/no 概率落在带内的答案计为"弃权 = 错误"，Releasing the Inner Jev 因此把这类答案移到 0.801 / 0.199 | [2610.17205](https://arxiv.org/abs/2610.17205) |
| 兜底规则的执行 | PFR 测试：常规分配与兜底分配之间的切换是否正确；Intern 在 TREC50 从 97.9% 跌到 23.1%，"即使显式给出正确类别" | [2610.19856](https://arxiv.org/abs/2610.19856) |
| 正确答案缺席 | 显式拒绝选项存在时仍接受错误替代（算术依赖的拒绝瓶颈，7% → 阈值后 79%，见 §4.1）；法律：替换正确判决后，生成式 LLM 仍在 38–86% 的条目里选一个，最谨慎的决策模型 30% | [2609.39496](https://arxiv.org/abs/2609.39496)、[2610.29961](https://arxiv.org/abs/2610.29961) |
| 超范围项 | TypedBench："out-of-scope items, whose true option is withheld"，有 / 无 "none of the above" 两种条件下分别测弃权率 | [2610.11392](https://arxiv.org/abs/2610.11392) |
| 可回答 / 不可回答 | SanSi 只在"answerable items"上算 ECE，另有未标注请求上拟合阈值的停止器 | [2610.07730](https://arxiv.org/abs/2610.07730) |
| 静默幻觉 | RSAJEV："assigning higher confidence to unseen than to seen classes (AUROC 0.38)"；用原型检索恢复"可校准的弃权通道" | [2610.15742](https://arxiv.org/abs/2610.15742) |
| 认证弃权 | SHIFT-JEV 用 Learn-then-Test 认证弃权阈值；2610.19811 在无人工交接时以保守兜底动作替代弃权并控制错误遗漏风险 | [2610.34329](https://arxiv.org/abs/2610.34329)、[2610.19811](https://arxiv.org/abs/2610.19811) |
| 交接选项无效 | "neither an explicit nor a trained hand-off option closes this gap"（输入错误继承） | [2610.24929](https://arxiv.org/abs/2610.24929) |
| 三元契约 | true / false / unknown 准入（§3.2） | [2610.10978](https://arxiv.org/abs/2610.10978) |

**分歧点**：弃权是**选项**（NDM、TypedBench 有 NOTA 条件）、**概率带**（TypeSafe、JevBench）、**单独的风险分数**（SHIFT-JEV、ufakzeka）、还是**兜底动作**（2610.19811、PFR）。四种定义对应四种失败：选项不被选（法律 30%）、带不校准（TypeSafe 自述）、分数不迁移（jevlike 域外）、兜底不执行（Intern 23.1%）。

### 1.4.9 Agent 层的定义

| 定义 | 内容 | 出处 |
| --- | --- | --- |
| 记录-状态不匹配 / claim laundering | 决策层"follows the record instead [and] turns the agent's claim into the decision"；12 个模型-域配置里记录都占主导 | [2610.25947](https://arxiv.org/abs/2610.25947) |
| 三级委托 | L1 孤立问题、L2 记录轨迹上的步级、L3 控制运行中的 Agent；"在轨迹上拟合的置信阈值"；非劣性检验作为接受标准 | [2610.21412](https://arxiv.org/abs/2610.21412) |
| 控制器 | 决策模型作为 Agent 控制器时"好判断、坏建议"（排序 AUROC 0.78 但平均"已完成"概率 0.50 而 87% 实际通过，见 §4.2） | [2610.24649](https://arxiv.org/abs/2610.24649) |
| System Switch | 快模型何时停下来交给推理模型：按置信延后最不确定的 30% | [2610.09683](https://arxiv.org/abs/2610.09683) |
| 快选择器 | 决策模型"over a state that a reasoning model has computed and checked" | [2610.24929](https://arxiv.org/abs/2610.24929) |
| 能否交给 System 1 | 同一类型化请求发给 30 个模型，四组任务 + 138 个闭环环境 | [2610.21244](https://arxiv.org/abs/2610.21244) |
| 四元组 / 联合可靠性 | 规则迁移、联合可靠性、信息使用的受控测试；"等价改写有相反的任务级效应" | [2610.30045](https://arxiv.org/abs/2610.30045) |
| 双时标 | 慢教师在暂停的环境里写指令，快学生在运行中执行；"live clock"下更快的模型反超 | [2610.20665](https://arxiv.org/abs/2610.20665) |
| 决策级持续学习 | 类型化反馈（接受 / 撤销）变成有界因果状态 | [2610.31521](https://arxiv.org/abs/2610.31521) |

**分歧点**：Agent 层的"正确"是**孤立准确率**（L1）、**步级一致**（L2）还是**任务成功 / 成本 / 时钟**（L3、live clock）；§5.2的结论"更快的决策 ≠ 更好的 Agent"正是三种定义不一致的表现。

### 1.4.10 分歧总表与"我们定义问题前必须回答的"

| 维度 | 定义 A | 定义 B | 定义 C | 后果 |
| --- | --- | --- | --- | --- |
| 决策模型 | 接口（TDM / LDM） | 性质契约（NDM 八条、readout stability） | 用途（gate / selector / 能否交给 System 1） | 决定评测对象是"模型"还是"模型 + 阈值 + 代码" |
| 请求 | 三原语 + 上限 | 四元组 (state, instruction, criteria, gold) | 自然语言候选 / 动作空间 | 决定 D3 规则语言的输入形态 |
| 置信度 | 分布形状统计量 | top-1 概率 | 学到的风险分数 / 两个量 | 阈值在不同选项数下不可迁移 |
| 校准 | 群体频率匹配（10/15 等宽/等质量） | 相干性 + 公理 | 部署策略 / 风险预算下的误差 | ECE 数字跨论文不可比 |
| 一致性 | 一次洗牌翻转 | 累积失败集 / 答案保持变体 | 定义级翻转 | "准确率不变"掩盖单题不稳定 |
| 顺序 / IIA | 经验翻转率 | 构造保证（Luce） | 读出稳定性 | 混合骨干能否满足构造保证（§1.3） |
| RLCD | 未公开 | 带推理链的适当评分奖励 | 直接梯度的替身 | "RL 有没有用"的结论取决于含义 |
| 弃权 | 显式选项（单独校准） | 概率带 | 风险分数 / 兜底动作 | 四种失败模式各不相同 |
| 多问题 | 隔离（NDM D5） | 联合有利（pplx） | 分解后读分散度（2610.33258） | 扇出与分解的语义 |
| Agent 正确性 | 孤立准确率 | 步级一致 | 任务成功 / 成本 / 时钟 | "更快 ≠ 更好" |

在我们自己写问题定义之前，这些分歧中至少有六个必须先取定：（1）"决策模型"是按接口还是按契约定义；（2）置信度采用 top-1 还是分布统计量，以及是否要与"自知"分开；（3）校准用哪种分箱、是否含相干性、在孤立还是部署策略下测；（4）翻转率用哪个分母、顺序不变性要构造保证还是经验度量；（5）弃权是选项、带、分数还是动作；（6）"RLCD"一词在我们文档里指哪一种。本节不做取定，只指出每种取法在文献里已经有的证据与失败案例。
