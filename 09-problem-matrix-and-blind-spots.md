# 09 · 工作-问题矩阵与盲区汇总

> 本章把 01–08 的结论压成两张表：(1) 每个维度下"哪类问题被哪些工作解决到什么程度"；(2) 跨维度的盲区清单，按"我们自训 Jev 类模型时会直接撞上"的程度排序。细节与数字都在各章，此处只给索引。

## 9.1 五维度总览

| 维度 | 问题重述（按用户口径） | 已解决 | 部分解决 | 未解决 |
| --- | --- | --- | --- | --- |
| **D1 ICL** | 决策微调后的单遍模型是否保留 ICL；如何利用；业务人员能用哪些提示杠杆 | 选项名与定义是最强杠杆（03 §3.2.2）；状态内示例/先例有效（JevKT、审核先例） | 示例数量与格式的效应只有间接证据；上游 ICL 机制（标签空间、格式、符号电路）未在决策模型上验证 | **决策微调对 ICL 的保留/破坏没有直接测量**；非技术人员写的提示的效果没有被测 |
| **D2 符号指令** | 模型是否忠实执行明确的符号规则（阈值、日期、否定、兜底） | "读"类事实探针稳（Reading Right 0.96–1.00 代码组合） | 否定/层级有免标签度量；算术/日期边界清楚（官方建议放代码） | **拒绝/兜底是最弱环节**（99%/7%、97.9→23.1）；等价措辞不变性无缓解 |
| **D3 规则语言** | 给非技术专家一套逻辑原语，用文字写业务规则，模型忠实执行 | Skill 范式对生成式 Agent 有效（+16.6）；NL→IR 编译器有多种中间表示 | SemTree（Yes/No/Unknown 树、按裁判编译）、概率感知确定性裁决（并集界）是单遍模型上的雏形 | **没有面向单遍模型的规则语言**；原语可执行性未分级；Unknown 原语与"模型说不了不知道"矛盾；L1/L2 规则（依赖/新框架）即使推理模型也只有 35%/13% |
| **D4 一致性** | 定义并度量所有让"同一判断"概率变化的因素 | 顺序（结构性缓解）、先验偏移（EM/KL 锚）、重复性 | 30 个子维度中 26 个有定义和度量 | **缓解只覆盖 2 项**；版本漂移、教师偏差无实证；无统一一致性基准；中文零证据 |
| **D5 Agent/知识** | 快/慢协同能否替代"慢思考 + 执行反馈" | 记忆选择/判断（预注册非劣）；动作空间被代码枚举的领域 Agent | 切换信号四类，但置信 ≠ "需要思考"；S1 监控 S2 只有 SOMA | **省钱不等于更好**（三篇反方）；收益核算无标准；知识结构维护无工作；规则/LR 基线常够用 |
| **08 骨干** | 混合骨干对 Jev 式接口的约束 | 推理时隔离（逐行/分叉）可做 | 选择性适配、注意力层双向读法 | **训练时分支隔离无文献**；同参数量混合 vs 纯注意力无对照 |

## 9.2 工作 → 问题矩阵（主要工作）

列 = 维度；格内 = 该工作对该维度的贡献类型：**E** 证据（度量了问题）、**M** 缓解（给出可用方法）、**T** 工具/基准、**N** 反方证据。

| 工作 | D1 | D2 | D3 | D4 | D5 | 08 |
| --- | --- | --- | --- | --- | --- | --- |
| TypeSafe 文档（primitives / patterns / jaggedness / cookbooks / agent-skill） | M | E | M | E | M | — |
| Archer Hume 架构探针 | — | — | — | E | — | E |
| Kev | — | — | — | T(permute) | — | M(逐行) |
| qwen-rlcd | — | — | — | — | — | M(分叉) |
| StartLux-Decision | — | — | — | M(校准) | M(AutoThink) | M(双向) |
| Releasing Inner Jev / LLM-as-Jev / LDM / FunDM / AnyJev | — | — | — | E(读出) | — | — |
| OneJev / Open-Jev / Tev1 / Nimble / Intern-Decision / Chinese Decision | — | — | — | E | — | E(延迟) |
| PACT / Prism-1 / Runoff / Block-causal | — | — | — | M(顺序) | — | — |
| SanSi / LEV | — | — | — | — | M(深度) | — |
| 2609.26758 选项名 / 2610.02586 定义 | E, M | — | E | E | — | — |
| JevKT / 审核先例 / MemCom / cheat-sheet / Jev-LDE | E | — | — | — | — | — |
| CALICO / Goldsmith | M | — | M | — | — | — |
| In-context fixation / 语义锚 / schema | E(上游) | — | — | — | — | — |
| Reading Right | — | E, M | M | — | — | — |
| 否定公理 2609.33209 / 层级 2609.33971 / 合取 2610.19619 | — | E | — | E | — | — |
| 拒绝瓶颈 / Lost in the Fallback / 法律弃权 / 拒绝迁移 / 退役门 | — | E | E | E | — | — |
| JevOut / JevAdvBench / 选项通道 / Same Attack / TrustJev / DICE | — | E | — | E | N | — |
| 2610.30045 措辞 / 表格 2610.19536 | — | E | — | E | — | — |
| IIA 2610.16655 / 选择偏差 2610.35826 / 请求独立性 2610.14631 | — | — | — | E | — | — |
| 多正确 2610.29217 / 序数压缩 2609.38827 | — | — | E | E | — | — |
| 自知 2610.01006 / 两种不确定性 2610.33258 / 字面锁定 2610.22526 | — | — | — | E | — | — |
| 流行率偏移 2610.26325 / SHIFT-JEV | — | — | — | E, M | M | — |
| 教师偏差 2610.26797 | — | — | — | E(理论) | — | — |
| SemTree | — | — | M | E(版本) | — | — |
| 概率感知确定性裁决 2610.10978 / 语义查询优化 2610.08089 / JEVDB | — | — | M | M(组合) | — | — |
| Jev-Guard / SafePyramid / LPG / gpt-oss-safeguard / PolicyGuard | — | — | E, M | — | M | — |
| Artic / FlashScript / TraceCompiler / Formal Skill / P2T / SIRNA / Cedar / ARc / LSP | — | — | M(IR) | — | — | — |
| SkillsBench / 138K SKILL.md / Skill coverage / SkillSentry / Auto-Policy | — | — | E | — | — | — |
| Code Owns the Simulation / What Can't Jev Decide | — | E | M(边界) | E | N | — |
| When Faster Decisions… / Good Judgment Bad Advice / JevAgentHarness / Microtask / Measure Before You Train / JEVal | — | — | — | — | N, M | — |
| System1-Arena / Fast Models Slow Evidence / DecisionPivot / TypedBench | — | E | — | E | T | — |
| Selective Reasoning / SOMA / System Switch / VoI / Truncated Reasoning / TORSI | — | — | — | — | M | — |
| 选择 vs 抽取 / Mnemon / Jev-Mem / SJC / 压缩后续问题 | — | — | — | — | E, M | — |
| REFLEX / Jev-LiteMAS / S1-MAS / BLADE / Jarvis | — | — | — | — | M | — |
| Jev-Mobile / JEV-Star / SearchJev / JevCoder / Decision4Rec / NIOCIS | — | — | M(动作空间) | — | M | — |
| Claim Laundering / Jev-DLC | — | — | — | E | E, M | — |
| Marconi / FastJEV / Hydragen / DeFT / Block-Attention / IPPD / Visual Jev / 选择性适配 | — | — | — | — | — | M |

## 9.3 盲区汇总（按对自训工作的影响排序）

### 一级：直接决定训练配方能否成立

1. **决策微调是否保留 ICL（D1）**。所有复现只报准确率/ECE，没有人在微调前后测"状态内示例改变决策的幅度"。如果 RLCD/软标签蒸馏抹掉了 ICL，D1 与 D3 的前提都不成立。
2. **训练时分支隔离在混合骨干上无文献（08）**。Qwen3.5 全系是 DeltaNet 混合；Kev 用逐行训练，qwen-rlcd 推迟。要么证明梯度穿过复制递归状态正确，要么接受逐行成本，要么换纯注意力骨干——三条路都没有公开数字。
3. **教师偏差继承无实证（D4-D5）**。小模型 + Jev 标签（AgentDecision-4B）或 + 大 LLM 标签（Releasing Inner Jev）是主流配方；理论说学生继承教师的 IIA/序数/否定缺陷且更多数据不消除；没有人测过。
4. **拒绝/兜底/Unknown（D2-F6、D3-盲区 3）**。规则语言需要"不知道"原语；单遍模型在这一项上最弱；缓解只有三元契约（退役门）一例。

### 二级：决定规则语言的形状

5. **没有面向单遍模型的规则语言**；原语可执行性没有按"读 / 组合 / 需中间步骤"分级（D3）。
6. **问题形式等价性证据矛盾**（Noul 归一化 vs Choice，医学 +、意图 −8.7）：每个原语在目标模型上都要单测（D4-B6）。
7. **等价措辞不变性无缓解**（D2/D4-C3）：规则语言要么模板化措辞，要么训练不变性；都没做。
8. **分解后的概率不自洽**（TV 0.219–0.349，重构 −22.9）：规则树的节点概率不能直接相乘（D4-C1）。
9. **按裁判编译**（SemTree 67.70→47.87）：业务规则与模型实际执行的树之间需要编译步骤，且随模型版本变化（D3-6、D4-A3）。

### 三级：决定部署与评估

10. **无统一一致性基准**；决策级配对评测不是规范（D4）。
11. **快慢协同的收益核算无标准**（D5-1）；置信不是"需要思考"信号（D5-2）。
12. **规则/逻辑回归基线常够用**，但没有工作系统比较（D5-4）。
13. **S1 训练数据要含错误后状态、S1 信记录不信观察**——未进任何配方（D5-5）。
14. **中文/企业场景证据接近零**：一致性、Agent、规则语言全是英文公开数据；中文只有 CJ-Bench 的准确率与 ECE（D4-E5、D5-7）。
15. **知识结构维护**（本体、规则库版本化）无工作（D5-6）。
16. **同参数量混合 vs 纯注意力的决策质量无对照**（08）。
