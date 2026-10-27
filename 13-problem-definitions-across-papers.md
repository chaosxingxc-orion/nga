# 13 · 问题定义的跨论文比较：同一个词，不同的定义

> 口径：用户要求"把问题定义详细地总结下，不同论文的学术定义很可能不一样"。本章只做定义层面的梳理与比较，不提出我们自己的定义（那是下一阶段的工作），但在 §13.9 列出"我们定义问题时必须先回答的分歧点"。所有引文都回到缓存的全文 / 摘要 / 文档核对过；没有核到的定义标注"未核实"。

## 13.0 为什么定义会分歧

Jev 发布只有六周，TypeSafe 没有公开训练细节与形式化定义，社区同时在做三件事：复现（需要可操作的定义）、审计（需要可检验的定义）、理论化（需要公理化的定义）。三种动机给出的"决策模型"定义互相不兼容，而且**同一个指标名（ECE、翻转率、置信度、RLCD）在不同论文里指不同的量**。跨论文比较数字之前必须先对齐定义，这也是 README §4 "跨论文的数字不可直接比较"的根源。

## 13.1 "决策模型"叫什么、指什么

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

## 13.2 请求 / 契约的形式化

| 形式化 | 内容 | 出处 |
| --- | --- | --- |
| TypeSafe 三原语 | Noul（单个概率）、Choice（≤255 个选项上的分布）、Score（2–10 个有序级别上的分布）；一个请求 = 一个 state + 多个 questions；state 与问题分离，示例可放在 state 或问题的 examples 字段 | 01 章、[state 文档](https://docs.typesafe.ai/concepts/state) |
| Kev 的问题 schema | `{"type": "choice", "instructions": …, "criteria": {name: definition, …}}`，选项由"名称 + 定义"对给出 | [jaredpalmer/kev](https://github.com/jaredpalmer/kev) |
| JEVal 四元组 | (state, instruction, criteria, gold)；criteria 定义合法决策空间 | [2610.03935](https://arxiv.org/abs/2610.03935) |
| LDM | Choice 2–8 命名选项、yes/no、Score 3–6 级；上限是实现选择 | [2610.15501](https://arxiv.org/abs/2610.15501) |
| NDM 契约 | 闭集分布 + 按问题类型校准 + 单遍 + 置换不变 + 问题隔离 + 显式弃权 + 读选项描述；声明 / 未声明弃权；集合值目标；合成数据引擎带"有效性守卫"；"specification first" | [2610.25553](https://arxiv.org/abs/2610.25553) |
| Probability Contracts | 把 Event（Noul）与 Choice 两种接口当作两个可能不一致的"概率契约"：同一事实用两种接口问，再比较"规范后验误差"、"补集残差"、"粗化残差"；Jev 的 Event 与 Choice 接口在 10% 延迟成本下**改变 32.8% 有效配对的二元动作** | [2609.37470](https://arxiv.org/abs/2609.37470) |
| 多问题共享状态 | Verdict："answering many small typed questions about one piece of state"；结构化掩码让状态编码与问题无关、问题互不影响、选项顺序无关"by construction"；Intern-Decision 在完整 JSON 骨架里每字段一个决策占位符 | [2610.20778](https://arxiv.org/abs/2610.20778)、[2610.22131](https://arxiv.org/abs/2610.22131) |
| 单 token 受限生成 | Koa-decision 的原子标签 token；SALSA 的类别→token 映射 | [2609.36115](https://arxiv.org/abs/2609.36115)、[2510.22691](https://arxiv.org/abs/2510.22691) |
| 自然语言请求 + 自然语言候选 | MetaEncoder：无 schema，候选可到百万级 | [2610.11316](https://arxiv.org/abs/2610.11316) |
| 动作空间 | FunDM / Dyad / AgentDecision：候选是动作描述；DecisionGym 三级（L1 孤立问题、L2 记录轨迹上的步级、L3 控制运行中的 Agent） | [2610.17175](https://arxiv.org/abs/2610.17175)、[2609.36116](https://arxiv.org/abs/2609.36116)、[2610.21412](https://arxiv.org/abs/2610.21412) |

**分歧点**：Event 与 Choice 是否是同一个契约（2609.37470 证明 Jev 上不是）；"选项 = 名称 + 定义"时模型跟谁（2609.26758：跟名称；2610.02586：标签压倒定义）；多问题是"隔离"（NDM D5、Verdict）还是"联合有利"（pplx-decider：同一消息的多个侧面联合问 +5.1，独立候选联合问 −0.2 到 −0.4，见 02 章）。

## 13.3 "置信度"指什么

| 定义 | 内容 | 出处 |
| --- | --- | --- |
| TypeSafe `confidence` | 把分布形状压成 0–1 的一个数："1 when all the probability is on one outcome and 0 when the probability is spread evenly"；Noul 没有这个字段；01 章给出其公式只依赖最高概率（(p_max − 1/n)/(1 − 1/n)） | [confidence 文档](https://docs.typesafe.ai/confidence)、01 章 |
| 最高概率 | "confidence to be the probability of its verdict"；并指出 Jev 原生字段"是整个标签分布的一个统计量，其公式未公开"，两者 Spearman 0.976；SanSi 同样"Confidence is the top probability" | [2609.26550](https://arxiv.org/abs/2609.26550)、[2610.07730](https://arxiv.org/abs/2610.07730) |
| 期望误差 | ufakzeka-karar 返回温度缩放概率 + "an expected error that serves as a 'not sure' signal" | [2610.06744](https://arxiv.org/abs/2610.06744) |
| 学到的不确定性分数 | SHIFT-JEV 从不确定性、格式、选项一致性三类信号学一个风险分数，与最高概率分数对比（目标风险 10% 下超标 3–5 对 5–15 / 27） | [2610.34329](https://arxiv.org/abs/2610.34329) |
| 两种不确定性（训练视角） | OpenJev-RLCD：结果"one-hot when there is a right answer (epistemic uncertainty) and spread when humans disagree (aleatoric uncertainty)"；"Aleatoric uncertainty: when RL cannot help" | [2609.38850](https://arxiv.org/abs/2609.38850) |
| 两种不确定性（部署视角） | 人类分歧 vs 决策风险；非对称损失下两者要求相反的升级信号，"no single confidence number serves both"；把判断拆成并行子问题读分散度可恢复分歧信号 | [2610.33258](https://arxiv.org/abs/2610.33258) |
| 校准 vs 敏感性 | "calibration and sensitivity (how well confidence separates right from wrong answers) are distinct"；最敏感模型的置信度追踪"哪类情境会失败"而非"哪个答案错" | [2610.09683](https://arxiv.org/abs/2610.09683) |
| 答案置信 vs 自知 | "你知道答案吗"类 Noul 与答案置信分离；表面线索会伪装成自知 | [2610.01006](https://arxiv.org/abs/2610.01006) |
| 决策模型"不知道自己的极限" | "its confidence flags the errors it makes itself but not" 输入错误继承的错误 | [2610.24929](https://arxiv.org/abs/2610.24929) |
| 答案质量（answer mass） | AnyJev 用"合法选项上的总概率质量"作为读出的归一化项与有效性指标 | [2610.00831](https://arxiv.org/abs/2610.00831) |

**分歧点**：置信度是（a）分布形状的统计量（TypeSafe），（b）top-1 概率（多数审计），（c）学到的风险分数（SHIFT-JEV），还是（d）两个不可合并的量（2610.33258）。（a）与（b）在排序上高度相关，但**在阈值层面不等价**（同一 0.6 阈值在 2 选项与 10 选项下含义不同），且都不是"错误检测器"（06 章 D1）。

## 13.4 "校准"怎么定义、怎么测

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
| 适当评分规则 | Brier、log-loss、RPS 作为训练目标与评测（jevlike、Open-Jev、NDM、SanSi、OpenJev-RLCD、UniJev CORA） | 12 章 C 族 |
| 选择性预测 / AURC | 按置信排序后的风险-覆盖曲线（OpenJev-RLCD、PACT、2609.37647） | [2609.38850](https://arxiv.org/abs/2609.38850)、[2609.35865](https://arxiv.org/abs/2609.35865) |
| 策略感知校准 | 在部署策略（选择、路由）下测置信-准确差，184 种设置 ≤2.7 pp；"下游选择会扭曲置信-准确关系即使模型不变" | [2610.17309](https://arxiv.org/abs/2610.17309) |
| 风险预算 / 错误遗漏风险 | 不确定时默认保守兜底，在"被分配效用最大动作"的子集内控制错误遗漏风险；朴素阈值在约一半设置超标，Learn Then Test 7.8% | [2610.19811](https://arxiv.org/abs/2610.19811) |
| 先验偏移下的校准 | 候选限定、EM 先验校正、35 个预注册配对检验 | [2610.26325](https://arxiv.org/abs/2610.26325) |
| 概率公理 / 相干 | 否定对之和偏离 1：Jev 0.064，Qwen3.8-27B 首 token 0.293、口头概率 0.122；层级边缘化与直接问的总变差：Jev 0.219–0.349，Laya 0.424–0.689 | [2609.33209](https://arxiv.org/abs/2609.33209)、[2609.33971](https://arxiv.org/abs/2609.33971) |
| 跨接口一致 | 规范后验误差、补集残差、粗化残差 | [2609.37470](https://arxiv.org/abs/2609.37470) |

**分歧点**：（1）分箱方案（10/15、等宽/等质量、末箱闭合）直接改变 ECE 数值，跨论文不可比；（2）"校准"是否包含相干性（2609.33209 / 2609.33971 认为不包含，需单列）；（3）校准在"孤立问题"还是"部署策略"下测（StartLux、2610.19811、2609.37470 认为后者才是产品指标）；（4）Noul 的校准是否按正负类分别测（2609.37647 用 Noul 概率本身，TypedBench 用友好 / 对抗表述）。

## 13.5 "一致性 / 翻转"怎么定义

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

**分歧点**：（1）"翻转率"至少有五种分母（一次洗牌、八种呈现累积、列表反转、重标注、答案保持变体）；（2）顺序不变性是**构造保证**（Prism-1、块因果、Verdict、NDM）还是**经验度量**（AnyJev、2610.35826）；（3）"一致"的对象是名称、定义还是分布（2609.26758 的核心区分）；06 章 30 个子维度是在这些定义之上的枚举。

## 13.6 "RLCD"至少有四种含义

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

**分歧点**：读到"RLCD"时必须先问三件事——有没有推理链、奖励是正确性还是适当评分、是策略梯度还是直接梯度。12 章 §12.3 的结论"单遍模型上 RL 无正面证据"只对"无推理链 + 策略梯度"这一种含义成立。

## 13.7 "弃权 / 兜底 / 不知道"怎么定义

| 定义 | 内容 | 出处 |
| --- | --- | --- |
| 显式选项 + 单独校准 | NDM D6："none of these" 的概率单独校准；声明（选项里有）与未声明（选项里没有，靠概率）两种机制 | [2610.25553](https://arxiv.org/abs/2610.25553) |
| 概率带 | TypeSafe cookbook：0.30–0.70 映射为 `uncertain` 交人工，并明确"The band is illustrative; it is neither a calibrated guarantee nor an optimized threshold"；confidence routing 用全局下限（示例 0.6）+ 每类动作阈值 | [consistency cookbook](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook)、[confidence-routing](https://docs.typesafe.ai/patterns/confidence-routing) |
| 评测口径里的弃权 | JevBench 把 yes/no 概率落在带内的答案计为"弃权 = 错误"，Releasing the Inner Jev 因此把这类答案移到 0.801 / 0.199 | [2610.17205](https://arxiv.org/abs/2610.17205) |
| 兜底规则的执行 | PFR 测试：常规分配与兜底分配之间的切换是否正确；Intern 在 TREC50 从 97.9% 跌到 23.1%，"即使显式给出正确类别" | [2610.19856](https://arxiv.org/abs/2610.19856) |
| 正确答案缺席 | 显式拒绝选项存在时仍接受错误替代（算术依赖的拒绝瓶颈，7% → 阈值后 79%，见 04 章）；法律：替换正确判决后，生成式 LLM 仍在 38–86% 的条目里选一个，最谨慎的决策模型 30% | [2609.39496](https://arxiv.org/abs/2609.39496)、[2610.29961](https://arxiv.org/abs/2610.29961) |
| 超范围项 | TypedBench："out-of-scope items, whose true option is withheld"，有 / 无 "none of the above" 两种条件下分别测弃权率 | [2610.11392](https://arxiv.org/abs/2610.11392) |
| 可回答 / 不可回答 | SanSi 只在"answerable items"上算 ECE，另有未标注请求上拟合阈值的停止器 | [2610.07730](https://arxiv.org/abs/2610.07730) |
| 静默幻觉 | RSAJEV："assigning higher confidence to unseen than to seen classes (AUROC 0.38)"；用原型检索恢复"可校准的弃权通道" | [2610.15742](https://arxiv.org/abs/2610.15742) |
| 认证弃权 | SHIFT-JEV 用 Learn-then-Test 认证弃权阈值；2610.19811 在无人工交接时以保守兜底动作替代弃权并控制错误遗漏风险 | [2610.34329](https://arxiv.org/abs/2610.34329)、[2610.19811](https://arxiv.org/abs/2610.19811) |
| 交接选项无效 | "neither an explicit nor a trained hand-off option closes this gap"（输入错误继承） | [2610.24929](https://arxiv.org/abs/2610.24929) |
| 三元契约 | true / false / unknown 准入（05 章） | [2610.10978](https://arxiv.org/abs/2610.10978) |

**分歧点**：弃权是**选项**（NDM、TypedBench 有 NOTA 条件）、**概率带**（TypeSafe、JevBench）、**单独的风险分数**（SHIFT-JEV、ufakzeka）、还是**兜底动作**（2610.19811、PFR）。四种定义对应四种失败：选项不被选（法律 30%）、带不校准（TypeSafe 自述）、分数不迁移（jevlike 域外）、兜底不执行（Intern 23.1%）。

## 13.8 Agent 层的定义

| 定义 | 内容 | 出处 |
| --- | --- | --- |
| 记录-状态不匹配 / claim laundering | 决策层"follows the record instead [and] turns the agent's claim into the decision"；12 个模型-域配置里记录都占主导 | [2610.25947](https://arxiv.org/abs/2610.25947) |
| 三级委托 | L1 孤立问题、L2 记录轨迹上的步级、L3 控制运行中的 Agent；"在轨迹上拟合的置信阈值"；非劣性检验作为接受标准 | [2610.21412](https://arxiv.org/abs/2610.21412) |
| 控制器 | 决策模型作为 Agent 控制器时"好判断、坏建议"（排序 AUROC 0.78 但平均"已完成"概率 0.50 而 87% 实际通过，见 06 章） | [2610.24649](https://arxiv.org/abs/2610.24649) |
| System Switch | 快模型何时停下来交给推理模型：按置信延后最不确定的 30% | [2610.09683](https://arxiv.org/abs/2610.09683) |
| 快选择器 | 决策模型"over a state that a reasoning model has computed and checked" | [2610.24929](https://arxiv.org/abs/2610.24929) |
| 能否交给 System 1 | 同一类型化请求发给 30 个模型，四组任务 + 138 个闭环环境 | [2610.21244](https://arxiv.org/abs/2610.21244) |
| 四元组 / 联合可靠性 | 规则迁移、联合可靠性、信息使用的受控测试；"等价改写有相反的任务级效应" | [2610.30045](https://arxiv.org/abs/2610.30045) |
| 双时标 | 慢教师在暂停的环境里写指令，快学生在运行中执行；"live clock"下更快的模型反超 | [2610.20665](https://arxiv.org/abs/2610.20665) |
| 决策级持续学习 | 类型化反馈（接受 / 撤销）变成有界因果状态 | [2610.31521](https://arxiv.org/abs/2610.31521) |

**分歧点**：Agent 层的"正确"是**孤立准确率**（L1）、**步级一致**（L2）还是**任务成功 / 成本 / 时钟**（L3、live clock）；07 章的结论"更快的决策 ≠ 更好的 Agent"正是三种定义不一致的表现。

## 13.9 分歧总表与"我们定义问题前必须回答的"

| 维度 | 定义 A | 定义 B | 定义 C | 后果 |
| --- | --- | --- | --- | --- |
| 决策模型 | 接口（TDM / LDM） | 性质契约（NDM 八条、readout stability） | 用途（gate / selector / 能否交给 System 1） | 决定评测对象是"模型"还是"模型 + 阈值 + 代码" |
| 请求 | 三原语 + 上限 | 四元组 (state, instruction, criteria, gold) | 自然语言候选 / 动作空间 | 决定 D3 规则语言的输入形态 |
| 置信度 | 分布形状统计量 | top-1 概率 | 学到的风险分数 / 两个量 | 阈值在不同选项数下不可迁移 |
| 校准 | 群体频率匹配（10/15 等宽/等质量） | 相干性 + 公理 | 部署策略 / 风险预算下的误差 | ECE 数字跨论文不可比 |
| 一致性 | 一次洗牌翻转 | 累积失败集 / 答案保持变体 | 定义级翻转 | "准确率不变"掩盖单题不稳定 |
| 顺序 / IIA | 经验翻转率 | 构造保证（Luce） | 读出稳定性 | 混合骨干能否满足构造保证（08 章） |
| RLCD | 未公开 | 带推理链的适当评分奖励 | 直接梯度的替身 | "RL 有没有用"的结论取决于含义 |
| 弃权 | 显式选项（单独校准） | 概率带 | 风险分数 / 兜底动作 | 四种失败模式各不相同 |
| 多问题 | 隔离（NDM D5） | 联合有利（pplx） | 分解后读分散度（2610.33258） | 扇出与分解的语义 |
| Agent 正确性 | 孤立准确率 | 步级一致 | 任务成功 / 成本 / 时钟 | "更快 ≠ 更好" |

在我们自己写问题定义之前，这些分歧中至少有六个必须先取定：（1）"决策模型"是按接口还是按契约定义；（2）置信度采用 top-1 还是分布统计量，以及是否要与"自知"分开；（3）校准用哪种分箱、是否含相干性、在孤立还是部署策略下测；（4）翻转率用哪个分母、顺序不变性要构造保证还是经验度量；（5）弃权是选项、带、分数还是动作；（6）"RLCD"一词在我们文档里指哪一种。本章不做取定，只指出每种取法在文献里已经有的证据与失败案例。
