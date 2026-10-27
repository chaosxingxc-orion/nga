# 02 · 开源解码器复现与配方矩阵（含小模型证据）

> 本章回答：用开源因果语言模型（Qwen / Gemma 等）复现 Jev 接口的工作有哪些，各自的骨干、读出头、损失、数据、校准与"分支隔离"方式是什么，以及小模型（0.6B–9B）到底能做到什么程度。编码器系（Laya、Verdict、Jeva、NDM、RubriX、Bongard 等）不在我们的技术方向内，仅作对照时引用。

## 2.1 一个共同的骨架

所有解码器复现都遵循 Archer Hume 还原出的三段式：

1. **共享 state 前缀**：state 只编码一次（KV 缓存 / 前缀分叉 / 独立行）。
2. **问题分支相互隔离**：树形注意力掩码（纯注意力骨干）、或每问题一行、或前缀分叉（混合骨干，见 08 章）。
3. **读出**：从最后一个位置读 LM-head 的候选字母 logit（letter readout），或在每个选项末尾位置放"指针头"（pointer head）/ 跨度均值池化（mean-span），再对合法选项做 softmax，最后乘一个拟合温度。

一个重要的先验证据：**不训练也能读出**。LDM 论文发现未调优的 27B 模型的读出已达到其调优后准确率的 97%（[2610.15501](https://arxiv.org/abs/2610.15501)）；FunDM 用 Qwen3-8B 的 24/36 层、无标签训练的小头恢复约 99% 的多选准确率，吞吐 1.56–1.57 倍、峰值显存降约三分之一（[2610.17175](https://arxiv.org/abs/2610.17175)）；LLM-as-Jev 的结论直接写进标题："LLM 已经是 Jev 式决策模型"（[2610.02076](https://arxiv.org/abs/2610.02076)）。

## 2.2 配方矩阵

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

## 2.3 小模型到底行不行：证据汇总

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

## 2.4 从配方矩阵读出的共识与分歧

**共识**

1. LoRA + 小读出头 + 温度即可复现接口；全秩不是必需。
2. 教师（更大模型）硬标签有效；对比/反事实数据（Nimble、Certo、DecisionPivot 训练集）对规则敏感性有效。
3. 校准必须在**保留分布**上拟合（Kev-27B/9B 的做法），且按**选项数**（Mapika）或**部署策略**（StartLux）拟合更稳。
4. 顺序偏置要在**结构上**解决（块因果、Prism-1、Runoff、AnyJev 旋转），不能靠训练数据洗牌解决（Prism-1 证明已发布的决策微调仍有翻转）。

**分歧 / 未定**

1. 软标签是否有益（Releasing the Inner Jev 说"可能无益"，OneJev 用 Brier，OpenJev-RLCD 用适当评分规则做奖励）。
2. 单遍 vs 循环（SanSi / LEV）vs 按需推理（StartLux AutoThink、Selective Reasoning、LDM 路由）：三条路都声称在"难题"上有大幅收益，但没有在同一基准、同一骨干上的对照。
3. 混合骨干（Gated DeltaNet）下**训练时**的分支隔离：Kev 用独立行绕开，qwen-rlcd 的前缀分叉只做推理，没有任何工作报告"在混合骨干上用树掩码训练"的结果（见 08 章）。

## 2.5 对我们的含义（仅分析）

- 复现接口本身不是难点，**领域数据、候选集设计、按选择拟合的阈值、保留集校准**才是分数的来源。
- 小模型（0.6B–4B）在窄领域可以超过通用 9B–27B 与 Jev，但**不训练就不行**，且校准不迁移。
- 配方矩阵里几乎所有工作都把"示例 / 定义 / 规则"当作**训练数据**而非**推理时输入**；这正是 D1 与 D3 的空白所在。
