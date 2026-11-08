# 52 · 架构碰撞第四轮（零上下文独立分析）：NGA 架构完成度补强稿

> 分析者：零上下文独立分析席位（未参与本战役）。日期：2026-11-08。基线：`/Users/yaojun/nga-impl-wt` HEAD `92c9f69`（Go 1.27.3 darwin/arm64）。
>
> **独立性声明（供计分）**：本稿全程**未读**以下四份前轮碰撞产物——`44-collision-*.md`、`45-collision-*.md`、`46-collision-integrated.md`、`51-architecture-collision-round3.md`；亦未读取它们的任何摘要、引用块或转述。全部结论由下列一手材料重建：邢超五条评论（`/tmp/nga-inputs/issue1-1987896{53,82}*`、`19879{9782}*`、`1990383{03,867}*`）、夏第四/五轮裁决、仓库代码与夹具、台账与 runbook、frame-bench 判定真源、review-loop/4-lens/singularity 方法论正本。本稿唯一"二手"输入是操作员给出的文件清单与提纲，未含结论。
>
> **本稿的复核记录（全部亲自执行，输出见文末附录 A）**：
> 1. `go test ./... -count=1` → 21 包全绿（与操作员所述一致；未加 `-race`，为省时，`-race` 一项未独立复核）；
> 2. `testdata/p0a_scan.tsv` → 558 数据行、`windowOnly=63`、`veto=279`（数值复现），但**分解后发现 63 只有 21 是"实现意义上的窗口面独有"**（见 §7.2）；
> 3. 用 Go overlay 写**组合探针** `verify(s1Judge(e))`（不改工作树）→ **P0-A 的 cell1/cell7 上，两个"互证实现"分叉，且验证席位对 cell1 的五种判定 kind 全部拒绝**（§7.1，本轮最重发现）；
> 4. 用 Go overlay 重放邢超四反例 → CX1 在其断言形式下通过，CX2/CX3/CX4 仍 FAIL（与操作员所述一致）。

---

## 一、输入回答了什么、打通了什么

### 1.1 逐输入的"闭合 / 语义桥 / 新义务"

| 输入 | 闭合的争议 | 成型的语义桥 | 新打开的义务 |
|---|---|---|---|
| 邢 `198789782`（独立复核＋六撤回要求） | "历史否决包含半年检查"这条业务层结论**已撤回**，我方 47 号逐项接受；"提取陷阱死亡"降为条件命题；"陈旧提交率 0"降为局部行为 | 业务谓词二元化：`RecentAnyOverdue(e,t_ref)` 与 `HistoricalLongOverdue(e)` **互不蕴含**——这条成为后续所有规约改动的公理 | 预期必须独立于实现；实验对象变了要新开版本；变异变红要问"为什么红" |
| 邢 `198789653`（复现附件） | 四反例的可执行形态落地（不再是我方口头复述） | **overlay 变异**作为"入口是否被消费"的判定手段；**阳性对照**作为"变异是否生效"的判定手段 | 我方须把这些探针收编为常驻件；修复后须更新其预期（旧脚本"应继续 PASS"作废） |
| 邢 `198799782`（正向采纳七项＋责任矩阵＋一体三态四面） | "五层技术栈"误解关闭（改为对象×责任矩阵）；"框架保证 100% 正确"这一稻草人正式排除 | **检查结果与执行状态分离**、**查询足迹与事实覆盖分离**、**历史与当前有效性分离**——三条分离律；"没有 violated ≠ 满足" | 三份交接契约（判断输入／采纳与生效／结果与有效性）须有生产者/消费者/失败语义 |
| 邢 `199038303`（R1-R3） | 首版最小集的边界：复杂依赖图、动态检查器选择可后置；"建 K_min 不等于建六个服务" | `x=(ι,a,r,e,t_ref)`、`K_min=(Bind,Q0,CheckRecord,CheckOK,Commit,H0)`、`B_v=(T,C,I,O,S,E)`、`Component=(Interface,A,G,V)`、`Compose` 检查单、扩展函数 `X_θ` ＋活性义务 | 每件须映射到现有组件；系统验收与组件验收分离登记 |
| 邢 `199038867`（R4-R6＋§五 MR!4 异议＋§八） | E7 canary 的"局部观察"可接受但不可升级为健康证明；评审机器可退役但"实验代码不再验"不可作一般原则 | `E_v=(S,D,Y,U,P,Γ)`＋`Admissible`；审计八元组；`Close(i,k)=PositivePass∧NegativePass∧EvidenceBound`；`Detect=Pass∧ValidMutation∧TargetFailure` | 结论表八列化；§五.2 的表述收敛；活性义务 `GovernedHandoff` 的最小字段 |
| 夏 R4 | 验证席位**不在**"判定方只收粒度一"辖域（角色类型而非开洞）；守卫存活＝三层组合（能力/存活/线索） | 独立性由**确定性＋判据预注册＋输入源分离**构造；"通道按产出去向定，不按读什么定" | 两条纪律（发现回流封存件、反馈禁写结论方向）＋"验证席位与规格同版本" |
| 夏 R5 | E1 引用收窄为条件证明（她自查补到五处）；canary 缓行≠豁免；撰写期独立性三件 | **本体独立**判据："评审者不共享被检术语表"；缓行/豁免语义分立；对称通知义务（触发词＝证明力变化） | 术语锚定规则（零消费者术语禁发布）——**这条直接命中我方 P3 病根，也命中邢超 B_v 的六个文档维度** |
| 我方战场（代码） | — | — | 见 §1.3 真差异总账：四反例中 3 个的根因是**同一个缺席对象** |
| 方法论资产（frame-bench/review-loop/4-lens/singularity） | "预期先行"的工程形态已被 `state-matrix.tsv` 证明可跑（10 行终态矩阵＋跑表器把"从实现反推期望"变成不可表达） | 判定真源＝**输入×预期终态表**，与实现分件；"新发现补行即收敛" | 我方 50 号只借了形态的一半（表在 doc 里、断言在 Go 里、两者同一作者），未借到"独立可执行"这一半 |

### 1.2 术语同构表（三方概念全对照）

符号约定：`✓` 有载体且被断言消费；`◐` 有载体但语义弱于名称或未被消费；`✗` 无载体。

| # | 邢超 | 语义 | 我方现有载体（file:line） | 夏侧 | 判定 |
|---|---|---|---|---|---|
| 1 | `x=(ι,a,r,e,t_ref)` | 待采纳对象的完整绑定 | `adopt.Request`（adopt.go:71-78）：`Identity{BR,ER,Op}`＋`Versions{Evidence,Rule,Model,Readout,Policy}`＋`PayloadDigest` | 封存件＋判断规格 | **◐ 缺 `a` 与 `t_ref`**（见 #2/#3） |
| 2 | `a=(action_kind,target,arguments)` | 被授权的动作本体 | 无。`PayloadDigest` 只是内容摘要，不区分"授信 5 万"与"授信 10 万" | 拟执行动作 | **✗**。后果：`grantsCover` 比对的是"读账本/执行转账"的工具权限，不是"这次批了多少"的动作权限 |
| 3 | `t_ref` 业务参考时间 | 判断的时间锚，≠ 运行时刻 | 无。夹具 `conventions.reference_time` 只是散文（judgment-spec-credit.json:20）；证据字段是**相对年龄** `monthsAgo`（e2e_test.go:24-27） | 参照时点 | **✗ 且是活缺陷**：同一份卷宗在不同墙钟重放会得到不同结论（见 §6.3） |
| 4 | `b(x)=Bind` | 对象与依据的不可歧义绑定 | `PayloadDigest`＋`Identity`＋`Versions` | 粒度一/封存 | ◐：摘要可识别、不可证明内容真实（邢超自己承认此边界），但**动作与时间不入绑定** |
| 5 | `Q_r(x)` 必需检查集 | 发布清单，不得由被检查方删减 | 无数据形态。`verify()` 里的 per-kind `switch`（verifier_test.go:418-527）**就是**实际检查集 | 检查清单 | **✗ 关键**：检查集由实现枚举，不由发布数据声明——这是 P3 病（定义随实现走）的同族 |
| 6 | `z_q=(q,b,w,s,v,p,L)` | 检查记录 | `checkResult{ok,reason}`（verifier_test.go:336-340） | 验证席位产出 | **✗**：六个字段只有 `v` 的半截（bool）＋一条人读 reason；无 `w`（检查者/版本）、无 `s`（执行状态）、无 `p`（依据引用）、无 `L`（适用期） |
| 7 | `CheckOK(z_q,x,σ,t)` | 记录可支撑推进的谓词 | `verify()` 函数体 | — | ◐：是**函数**不是**记录谓词**——事后无法对"当时凭什么放行"重新判定 |
| 8 | `Z(q)=Select_r(...)` | 同检查多回执的当前可用选择 | 无 | 当前有效性 | ✗ |
| 9 | `Commit_r(σ,x,Z,expected_epoch)` | 权威提交的条件边界 | `Adopt`（adopt.go:268）＋`dispatchGated`（:352） | 控制面/控制事件 | **✗ 且不可达**：`observed>=0` 恒拒（:369-376），成功路径自认"by construction 不可达"（:346-351） |
| 10 | `Current_r(ι,σ)` 当前有效修订 | 作用域内的生效关系 | `lookupByBusinessRequest`（t2host_test.go:105-132）取 `max(rev)`，**不查 machine state** | 当前有效性 | **✗ 强名称弱语义**（邢 R3 §3.3 明令禁止的形态） |
| 11 | `Authorized_r` | 动作当前权限 | `grantsCover`＋`grantsCoverRead`（t2host_test.go:504-535） | 权限 | ✓（本表唯一满分级） |
| 12 | `H_r(reason,x,σ)` | 不可放行时的确定归属 | `refuse()` 写 control 事件（adopt.go:536-553）；未知操作**裸返回无事件**（:363-366） | 受控交接/回捞 | ◐：拒绝可审计一半；无 owner、无时限、无等待态 |
| 13 | `Eligible_r = Ready∧Authorized∧Current∧∀q CheckOK` | 生效许可 | 无组合载体 | 准入 | ✗（四项中只有 `Authorized` 有） |
| 14 | `GovernedHandoff` | 受控交接（≠业务成功） | `MarkUnresolved`（adopt.go:460-471） | 受控交接 | ◐：只表达"外部效果未知"，不表达"责任已交接" |
| 15 | `Component=(Interface,A,G,V)` | 组件契约 | 无任何 `A_i` 声明；`G_i` 隐含在测试名里 | 支撑性 | ✗ |
| 16 | `B_v=(T,C,I,O,S,E)` | 权威契约基线 | 分散在 fixture／47 号／50 号／台账；无单一版本化入口 | 单据/台账 | ◐：逻辑单源未落地（我方 R2 已接受合并，未做） |
| 17 | `E_v=(S,D,Y,U,P,Γ)` | 实验契约 | 50 号 §三（S/D/Y 部分）＋测试（P 部分）；`U/Γ` 无载体 | 配方/预注册 | ◐ 见 §4.2 |
| 18 | `a=(id,subject,kind,producer,causes,basis,outcome,order)` | 审计八元组 | `ledger.Event{EventType,ArbitrationSeq,Identity,Versions,Accountability,Idempotency,Outcome}` | 事件账本/控制事件 | ◐：缺 `causes`（因果前驱指针）；`kind` 只有 adoption/effect/control 三类 |
| 19 | `I_v/T_v/M_v/V_v`（R6） | 契约-测试-变异-证据 | runbook v4 的"变异先行手动形态"＋台账 | 变异/证伪耦合门 | ◐：**变异结果不落档**（只在注释里写"Mutation probe: …会红"） |
| 20 | `Pending∧Assumptions∧FairScheduling ⇒ ◇(Terminal∨GovernedHandoff)` | 活性 | 无（无调度器、无等待超时） | 回捞 aging | ✗ |

### 1.3 真差异总账（按承重排序，不按符号表顺序）

| 排序 | 真差异 | 为什么是"真"差异（不是改名） | 承重后果 |
|---|---|---|---|
| **D1** | **决策作用域（scope）这个对象不存在** | 我方 `Identity` 里 `business_request_id` 只是事件上的一个字符串，机器**从不以它为键**（adopt.go 全文只在 schema 校验处引用它，:744）；`ops` 以 `operation_id` 为键（:105）。因此"同一请求下哪一版生效"在系统里**不可表达** | 一次建件可关：CX2、CX3、C4 验收、R1 `Current_r`/`Commit_r`、有效性投影、replay 的"当前视图"权威性。**六个待办同一根因** |
| **D2** | **检查记录是布尔值，不是记录** | `checkResult` 活在函数栈上，进程结束即消失；无检查者版本、无执行状态、无依据引用 | 一次建件可关：CX4、R5 审计行、R1 `CheckRecord/CheckOK` 载体、E4"哪个守卫死了"盲区、E7 canary 归属、夏"声明面能力证明"的持久形态 |
| **D3** | **动作 `a` 与时间 `t_ref` 不在绑定里** | 摘要绑定了"内容"，没绑定"这次批多少、以哪个时点为准"；证据是相对年龄，重放随时间漂移 | 授权比对退化为"工具权限比对"；piece 6 replay 的"同一输入同一输出"在全称意义上不成立 |
| **D4** | **拒绝的归属不完整** | 未知操作拒绝无事件（E7a① 实测）；无 owner/时限；无等待态 | 活性义务无载体；夏的 aging 机制只能挂在"补丁队列"和"坟墓队列"上，挂不到"业务未知队列" |
| **D5** | **`Q0` 是代码不是数据** | 检查集由 `verify()` 的 switch 枚举，发布清单不存在 | P3 病（定义被实现改写而无人察觉）在**检查集层**仍然活着；任何规则前提变更都会漏改某个 hand-written mirror（§7.1 已实证一次） |
| **D6** | **判定词表三处分裂且未锚定** | `levels`（夹具）／`resolution`（夹具，**未被解析**，`verify` 硬编码，verifier_test.go:369-372 自认）／`State`（adopt.go:57-63）三套词表 | 夹具改名静默漂移；`on_undefined_rule` 在宿主侧**零消费者**（t2host*.go/health/e7 全为 0 引用）——"诚实的不知道"没有控制面后果 |

**一句话**：三方争的多数是"名字对不对、公式全不全"，而我们真正的完成度瓶颈是 **D1/D2 两个缺席对象**；D3/D5/D6 是它们的衍生；D4 是缺一个总函数。公式族（R1-R6）之所以看起来庞大，是因为它在替缺席的对象"记账"。

---

## 二、架构完成度现状测度

### 2.1 按邢超 §八优先序逐项（含 R4-R6 §八 的收敛序）

| # | 优先序项 | 状态 | 文件级证据锚 | 说明 |
|---|---|---|---|---|
| 1 | 原业务语义恢复（半年任意逾期 vs 历史长期逾期） | **部分** | `schema/.../judgment-spec-credit.json:16`（term 不再含 "three months"）、`:21`（窗口只挂上带）、`:48`（否决无界）；`e2e_test.go:64-93`（s1Judge 双谓词）；`p0a_window_test.go:36-87`（8 行矩阵）；`verifier_test.go:428-447`（席位窗口面） | 判定侧已恢复且三处锚定（术语/规则文本/窗口条款，`p0a_window_test.go:94-121`）。**但组合之后席位拒绝正确判定**（§7.1），故系统级未闭合 |
| 2 | R/K 真实统一入口 | **未动** | `t2host_rk_test.go:66`（R 主场景直取 store）、`:333-342`（K 主场景直取 registry），`nodeEntry`（`t2host_test.go:542-563`）只在 `TestT2R_PermissionRevoked:136,144` 被调用 | 与邢超 overlay 结论一致；我方 47 号已接受，代码未改 |
| 3 | 有效修订的权威条件提交 | **未动** | `adopt.go:369-376`（`observed>=0` 恒拒）、`:388-396`（pin 无活着读者）、`:443-452` | 不是"没做好"，是**当前数据模型下不可做**（无 scope/epoch） |
| 4 | 基于生效事实的投影 | **未动** | `t2host_test.go:105-132`（`max(rev)`，注释自称"最新已采纳"但从不查采纳） | CX3 复现："candidate"（未采纳 er-99）胜出 |
| 5 | 真实拒绝持久审计 | **未动** | CX4 复现：Adopt 后 `Events()` 共 1 条、control 0 条 | 验证结果仍是局部值，不进账本 |
| 6 | 证据与对外状态同步 | **部分** | 47 号 §二（六撤回）已成文；`43-experiment-proposal-matrix.md` 是覆盖矩阵但**过度声明**（"四反例全部落地/全验"，见 F9/§7.6） | 撤回做了；换版未做；内部矩阵本身需要按八列重写 |
| 7 | 抽取三臂（共用错误/独立来源/原始材料） | **未动** | `correctness_probe_test.go:114-160` 只有 hand-built 的"独立正确来源"一臂 | arm1/arm3 无载体；arm3 需真模型（用户启动） |
| 8 | openJiuwen 复用与适配责任 | **未动** | 仓库内无映射文档（47 号 §四 R3 承诺"随换版提交"） | 属交付件，不属代码 |

### 2.2 完成度的三个候选测度

**M1 契约承载率**＝`K_min+B_v+E_v+Audit` 的逻辑要素中，具备"具名、可定位、被至少一个断言消费"载体的比例。
- 优点：可枚举、可机械统计。缺点：**奖励纸面符号**——加一个符号加一个空壳载体就涨分；与邢超自己警告的"公式漂亮互替"同构。
- 当前诚实值（按 §1.2 表 20 项）：`✓`4 + `◐`7 + `✗`9 → 加权 ≈ **0.30**。

**M2 证据阶梯覆盖**＝对每个验收面给出最深证据层级，再统计覆盖与均值。
- 阶梯：`L0` 声明／`L1` 单元断言／`L2` 变异耦合（删守卫即在该面红）／`L3` 组合（经声明接口端到端，双向）／`L4` 第三方可执行（外部评审不读我方代码即可复跑）。
- 优点：**可棘轮**（每级都有定义、有反例）；直接对应邢超 R6 的 `PositivePass∧NegativePass∧EvidenceBound`。缺点：层级需要人判。
- 当前诚实值（14 个面，见 §2.3）：≥L1 的 9 个，≥L2 的 6 个，≥L3 的 **2** 个，L4 的 **1** 个；均值 ≈ **1.4/4**。

**M3 强名称兑现率**＝代码/文档中出现的"强名词"（current / valid / effective / checked / durable / authorized / conditional / unified / zero-call）中，存在一个**能拒绝错误**的对象承载的比例。
- 优点：**最上游**——它不问"公式齐不齐"，只问"这个名字敢不敢拒绝"。这正是邢超 R3 §3.3"不能同时保留强名称与弱承诺"的可测形态，也是 singularity 的判据（问题是否被重定义成可证伪）。
- 缺点：是快照不是过程；名词清单需要维护（但清单本身极短）。

| 强名称 | 承载 | 能否拒绝错误 |
|---|---|---|
| current（当前有效） | `lookupByBusinessRequest` | ✗（选未采纳的最大版本） |
| checked（已检查） | `verify()` | ✗（不在采纳路径上；且拒绝自己的正确答案） |
| conditional commit（条件提交） | `DispatchIfCurrent` | ✗（成功路径不可达） |
| unified entry（统一入口） | `nodeEntry` | ✗（不在主路径上） |
| zero-call（零调用） | `failingProbe` | ✗（探针从未接线，`invoke` 全仓无调用点） |
| durable（持久终态） | `resultStore.put` | ✗（非原子写；见 §7.3） |
| authorized（已授权） | `grantsCover` | ✓ |
| audit（可审计） | `refuse()`→control 事件 | ◐（未知操作无事件） |
| window premise（窗口前提） | `verify:428-447` | ✓（但组合后与判定侧互斥） |
| versioned spec（版本化规约） | fixture `spec_version` | ✓ |

→ **M3 = 3.5/10 ≈ 0.35**。

**推荐**：以 **M3 为主指标（月度快照，防"强名称通胀"）**，以 **M2 为工作指标（每轮棘轮，防"证据通胀"）**，弃用 M1 作为对外指标（只作内部完备性检查）。

理由：M1 会被本战役自己的成功路径污染——过去七天新增的公式（K_min/B_v/E_v/R4-R6）没有新增一个可拒绝错误的对象，M1 会因此上涨，M3 不动。**M1 与 M3 的剪刀差，就是"形式化先行"退化成"纸面完备性"的可观测先兆。**

### 2.3 14 个验收面 × 证据层级（当前诚实值）

| 面 | 层级 | 证据锚 | 缺口 |
|---|---|---|---|
| A1 否决无界（反例 A） | L3 | 夹具 rule0＋s1Judge＋verify 三处一致；`e2e_test.go:64-69` | 无第三方件（L4） |
| A2 窗口前提（反例 1） | **L1→分叉** | `p0a_window_test.go:36-87` | 组合后席位拒绝（§7.1）→ 实际 **L1** |
| A3 术语本体不回吸收 | L2 | `p0a_window_test.go:94-121`（改回 "three months" 即红） | 只锚 overdue 一词；resolution 词零锚定 |
| A4 覆盖不足路由（反例 B） | L1 | `verifier_test.go:560-575`＋`p0a_window_test.go:81-86` | 只比"来源名集合"；无分页/主体/时间覆盖 |
| A5 R 持久回执 | L2 | `t2host_rk_test.go:31-94`＋overlay 变异（邢超） | 不经入口；探针未接线 |
| A6 K 零调用复用 | L1 | `t2host_rk_test.go:307-367` | 同上；且无"确实需要模型"的正向对照 |
| A7 幂等同键异载荷 | L2 | `t2host_rk_test.go:98-108`＋adopt 内部 | 组件级 ✓（这一项是本仓最扎实的） |
| A8 条件提交 | L0 | `adopt.go:369`（拒绝面有测试，成功面自认不可达） | 无正向可提交形态 → 不是 L2 |
| A9 有效性投影 | L0 | `t2host_test.go:105`；`t2host_rk_test.go:206-217` | CX3 反证；且 READ-2 是 **wrong-reason green**（见 F9/§7.6） |
| A10 拒绝审计 | L0 | CX4 反证 | 无 |
| A11 E5 读授权 | L2 | `t2host_test.go:504-535`＋`TestT2R_PermissionRevoked:144-148` | 授权面通过入口（唯一一条真经入口的路径） |
| A12 解析失败闭合 | L2 | `t2host_test.go:760` 起 | ✓ |
| A13 守卫存活（E4） | L1 | `health_test.go:108-180` | 无真实守卫、无 per-guard 标识（:64-76 自认盲区） |
| A14 canary 掩蔽解药（E7b） | L2 | `e7_canary_test.go:497-553` | 无生产注入通道（E7a①） |
| A15 全量套件绿 | L1 | 21 包 | 对本稿全部命题**零信息量**（e2e 包内自证） |

均值 1.4 的来源：`(3+1+2+1+2+1+2+0+0+0+2+2+1+2)/14 ≈ 1.35`；A15 不计入。

---

## 三、补强架构设计方案（核心交付）

### 3.1 目标架构（文字版）

```
                ┌───────────── 管理面（发布即治理，运行期只读）─────────────┐
                │  语义规约 r (term/rule/time_window)                      │
                │  Q0 检查清单（数据，非代码）   H0 处置表（数据，非代码）    │
                │  阈值与边界授权签署（owner signoff 引用）                 │
                └───────────────────────┬────────────────────────────────┘
                                        │ 版本化发布（不可变引用）
   S2 调查 ──封存件（粒度一）──► S1 判定 ──x=(ι,a,r,e,t_ref)──► 验证席位
   （证据通道）                    │                            （检查器）
                                   │                              │ z_q
                                   │                     ┌────────┘
                                   ▼                     ▼
                        ┌──────────────── 控制面 ─────────────────────┐
                        │  作用域头 σ = (scope_key, head_rev, epoch)   │
                        │  Commit(x, Z, expected_epoch) → permit|refuse│
                        │  H0(reason) → 声明处置（补证/等待/复核/交接）  │
                        └───────────────┬─────────────────────────────┘
                                        │ 准入事实（持久、有序）
                                        ▼
                        运行面：统一入口 ──► 端口（Model/Tool/BusinessAPI）
                                        │        （唯一外部通道，计数强制）
                                        ▼
              事件账本（adoption | check | effect | control | handoff）
                                        │
                    ┌───────────────────┴────────────────────┐
                    ▼                                        ▼
        有效性投影（读作用域头，不读 max(rev)）        H0 扫描 / aging（读 handoff 事件）
```

与现状的差别只有三处，但都不是"加服务"：
1. 账本事件类别从 3 类（adoption/effect/control）扩到 5 类（+check/+handoff）——**一次 grammar 版本变更承载三个待办**；
2. 控制面新增**作用域头**这一个持久对象（不是服务，是 adopt 包内的一张表＋一种事件）；
3. 验证席位从"函数返回"改为"产生 check 事件"，其余（确定性、输入源分离、判据预注册）不变。

### 3.2 `K_min` 六件 → 现有组件映射（每件：现有承载／缺口／落点）

| K_min 件 | 现有承载 | 缺口 | 落点（新件编号） |
|---|---|---|---|
| **Bind** | `adopt.Request`（adopt.go:71-78）＋`ledger.Identity`（ledger.go:100-104）＋`Versions`＋`PayloadDigest` | 无 `a`、无 `t_ref`；`r` 是 5 个字符串而非不可变发布引用 | **N6** |
| **Q0** | 夹具 `rules[].coverage` 散文＋`verify()` 手写 switch（verifier_test.go:418-527） | 无数据形态；检查集由实现枚举；`resolution` 段零解析 | **N2-a**（Q0 投影） |
| **CheckRecord** | `checkResult{ok,reason}`（:336-340） | 无 `q/b/w/s/v/p/L`；不落盘 | **N2-b** |
| **CheckOK** | `verify()` 函数体 | 是函数不是记录谓词；事后不可审 | **N2-c** |
| **Commit** | `Adopt`（:268）＋`dispatchGated`（:352）＋`grantsCover` | 无 scope、无 epoch；`observed>=0` 恒拒 | **N1** |
| **H0** | `refuse()`→control 事件（:536）＋未知操作裸返回（:363-366） | 未知操作无事件；无 owner/时限；无等待态；无"路由到谁"的数据 | **N5** |

**简单性审计（4-lens 简单性）**：`K_min` 作为元组有冗余——`Bind` 同时以函数形式出现（`b(x)`）和记录字段形式出现（`z_q.b`），是同一对象的两次计数；`CheckOK` 不是对象而是 `Commit` 的前置谓词。**不可约集是 5 件：`X`(绑定，含 a/t_ref) ／ `Q0`(集) ／ `Z`(记录＋选择) ／ `Commit`(原子边界) ／ `H0`(总函数)**。这不是语义让步，是提醒："六件"这个数会把工作量估高 20%，而真实瓶颈是**两个缺席对象**（D1/D2）而不是"六件里缺四件"。

### 3.3 新增／改造件清单

> 编号 N1-N8；优先级 P0（本轮）／P1（下一批）／P2（随 0.2.0 schema）。

#### N1 · 决策作用域头（scope head ＋ epoch）— **P0，最高杠杆**

- **职责**：让"同一业务请求下哪一版生效"成为可查询、可条件提交、可重放的持久事实。
- **数据**：`scope_key = business_request_id`（可选 `+node_instance_id`）；`head_revision`；`epoch int64`（单调，每次生效变更 +1）；`admission kind ∈ {candidate, effective, superseded, revoked}`。
- **接口**：
  ```
  Admit(req, kind) → (epoch' | conflict)     // kind=effective 时推进 head+epoch，否则只记账
  ScopeHead(scope) → (headRev, epoch)
  CommitDispatch(op, expectedScopeEpoch) → permit | refusal
  ```
- **假设-保证**：`A`＝单写者＋既有 torn-tail/stale-writer 闸（adopt.go:160-174, append 内 seq 连续性闸）；`G`＝若 `CommitDispatch` 许可，则在提交的仲裁点不存在"该作用域内已生效且 revision 高于 op 的 revision"的修订，且 `expectedScopeEpoch` 与该点一致。
- **验证**：4 格真源表（epoch 未变→许可；epoch 变→拒；独立作用域变更→不误伤；重启后 epoch 持久）＋2 枚变异（删 epoch 比较→格 2 红；把 epoch 恒置 0→格 2 红）＋阳性对照（今天**不存在**的那个成功格）。
- **为什么是 P0**：它一次关闭 CX2、CX3、C4 验收、R1 `Current_r`/`Commit_r`、有效性投影、以及 `DispatchIfCurrent` 的"成功路径不可达"这一自认死结。这是本稿唯一的"奇点级"改动。

#### N2 · 检查记录事件（check record）＋ Q0 投影 — **P1（与 N1 同批 grammar 变更）**

- **职责**：把"检查发生过、谁检查、依据什么、结果如何、是否还适用"变成账本事实。
- **接口**：
  ```
  type CheckRecord struct {
      CheckID, CheckDefVersion string
      Scope string; Revision string          // 绑定到 N1 的作用域/修订
      CheckerID, CheckerVersion string       // w
      Status   string                        // completed|failed|timed_out|pending  (s)
      Verdict  string                        // satisfied|violated|undetermined|absent (v)
      Basis    struct{ Evidence, Rule string } // p 的引用面
      Applies  struct{ Until string; ScopeNote string } // L
  }
  Host.RecordCheck(CheckRecord) error       // 追加 check 事件
  Host.CheckOK(scope, rev, checkID) (bool, reason)
  ```
- **假设-保证**：`A`＝检查器经 `TrustedFor` 授权、经受控端口调用（N3）；`G`＝`Commit` 许可 ⇒ 对 `Q0(scope,rev)` 中每一项存在 `Status=completed ∧ Verdict=satisfied ∧ Applicable` 的记录（邢 `AdmissibilityReceipt` 的落地形态）。
- **验证**：拒绝后重启读回（CX4 转正）＋篡改记录（改 verdict）→ 拒绝＋删 check 事件→Commit 拒（变异耦合）。
- **Q0 投影**：从夹具 `rules[]` 生成 `Q0`（每 rule 一条检查项，`check_id = rule.precedence`，`check_def_version = spec_version`），使"检查集是数据"。同时把 `resolution` 段解析进 `fixtureSpec`，消掉 `verifier_test.go:369-372` 自认的硬编码漂移。
- **为什么与 N1 同批**：两者都改账本 grammar，分成两次做要两次 schema 迁移＋两次 checker 重写。**一次 grammar bump 承载三个事实（scope/check/handoff）**，这是我方"骑标准协议/结构性预防"家法在本仓的第一次应用。

#### N3 · 统一入口＋端口（把 `nodeEntry` 变成真入口）— **P0，最便宜**

- **职责**：首次执行／重试复用／新任务方法消费三条路都必须经过同一函数，且模型/工具调用只能经端口发生。
- **接口**：
  ```
  type Ports struct{ Model ModelPort; Tool ToolPort; API BusinessAPI }
  NodeEntry(op string, callerGrants []Grant, p Ports) (NodeOutcome, error)
  // 分支：completed → store 回执（零调用）
  //       method 适用 → execute（零模型调用）
  //       其他 → p.Model(...)（必然调用，计数器 >0）
  ```
- **假设-保证**：`A`＝端口是唯一外部通道（编译期：`e2e` 包内不允许直接 import 模型客户端）；`G`＝`NodeEntry` 返回"复用"⇒ 端口零调用；返回"新判断"⇒ 端口调用 ≥1。
- **验证**：三件必须同时在场——① 计数基线（T0 形态，`e2e_test.go:689-692` 已是正确范式）；② **阳性对照**（"确实需要模型"的输入使探针必红）；③ overlay 破坏 `NodeEntry` ⇒ R/K 在目标处红（邢超脚本收编）。
- **顺带清理**：`failingProbe.invoke`（t2host_test.go:174）全仓无调用点——它不是"按构造证明"，是**死代码**。改为"计数器＋基线＋阳性对照"单一机制，删掉第二套。

#### N4 · 有效性投影（读作用域头）— **P0（N1 之后，10 行级）**

- **接口**：`CurrentResult(scope) → (result, revision, validity, supersededBy, err)`，实现为 `ScopeHead(scope)` → 取对应 op 的 `storedResult`，并校验 `admission=effective ∧ ¬revoked`。
- **假设-保证**：`A`＝admission 事实已持久（N1）；`G`＝返回的修订是"已生效且未失效"的，`max(rev)` 不再参与判定。
- **验证**：CX3 转正＋变异（删 admission 校验→红）＋"先写后采纳"中间态＋撤销态。

#### N5 · H0 处置总函数（数据驱动 ＋ aging）— **P2**

- **形态**：`H0` 是一张发布表（reason_class → {next, owner, deadline, user_visible_status}），不是代码分支；执行体是"写一条 handoff/control 事件"，aging 是**对账本的扫描**（复用 `graveyardSweep` 形态，health_test.go:247-298），不新建服务。
- **关闭**：未知操作拒绝可追踪（E7a① 的 grammar gap）、等待态、owner 缺位上报、夏的第三个 aging 消费端、`on_undefined_rule` 从"死值"变成"ticket"。

#### N6 · `x` 补齐 `a` 与 `t_ref`（schema 0.2.0）— **P1**

- `Request.Action{Kind, Target, Arguments}`；`Request.ReferenceTime`（RFC3339）。
- 证据侧：事件存**绝对时点**，`monthsAgo` 改为派生量（`floor((t_ref - event_at)/month)`）。这使 piece 6 replay 在全称意义上成立。
- 授权比对从"工具权限"升级为"工具权限 ∧ 动作范围"（例如 `grant-50000` 需要 `credit.limit>=50000` 的授权项）。

#### N7 · 独立可执行的判定真源（conformance kit）— **P1，便宜且高杠杆**

- `conformance/<spec_version>/truth.tsv`（输入 × 期望 verdict 集合 × 翻译依据）＋ `cmd/conformance`（读一份 JSON dossier 列表，输出判定）。
- 关键性质：**外部评审者不读我方 Go 测试代码即可复跑**（L4）。今天的 50 号 §三是 doc、断言在 Go 里、二者同一作者——邢超只能把探针**拷进我们的包**才能跑，这正是 L4 缺失的症状。
- 直接满足 `E_v` 的 `Y`（集合而非单值）与 `U`（被测实现版本可标）。

#### N8 · 语义授权（owner signoff）— **P2，流程件**

- `B_v.O` 增加 `q0_signature: {authority, ref, date}`；未签署的 Q0 项标 `provisional`，其 `on_undefined_rule` 走 ticket。
- 这条不是代码，是把 `business-owner-credit`（夹具 ownership 里的字符串，无收件人）变成**有到期日的欠账**。

### 3.4 依赖与"一次建件关闭多个验收面"

```
N6 ──► N3（入口需要动作绑定来比对授权）
N1 ──► N4（投影读作用域头）
N1 ──► N3（条件提交格）
N1 ──► N5（handoff 需要 scope 才能挂责任）
N2 ──► N5（拒绝的 reason_class 由 check 记录产生）
N7 ──► 依赖 N1+N2 已有可观察对象（否则无物可 conformance）
```

| 建件 | 一次关闭的验收面 | 计数 |
|---|---|---|
| **N1** | CX2、CX3、C4 条件提交验收、R1 `Current_r`、R1 `Commit_r`、有效性投影、`DispatchIfCurrent` 死结、replay 当前视图权威 | **8** |
| **N2** | CX4、R5 审计行、R1 `CheckRecord`/`CheckOK`、E4 per-guard 存活（`health_test.go:64-76` 自认盲区）、E7 canary 归属、夏"声明面能力证明"持久形态 | **6** |
| **N3** | R/K 验收、zero-call 强名称、探针接线、统一入口强名称 | **4** |
| **N5** | E7a①、R1 `H_r`、活性义务、aging 第三消费端、`on_undefined_rule` 路由 | **5** |
| **N6** | 动作授权、`t_ref` 重放稳定性、R1 `b(x)` | **3** |
| **N7** | R4 `Admissible`、L4 第三方可执行、M2 阶梯整体上移 | **3** |

**建议实施顺序**：`N3（1 天，独立）` → `N1+N2+N4（同一 grammar 版本，1-2 周）` → `N7` → `N6` → `N5` → `N8`。
理由：N3 不依赖任何新对象，且立刻把"入口"这个强名称兑现；N1/N2 共享一次 grammar 迁移成本，且互为验证（check 记录要绑 scope）。

---

## 四、实验设计清单

### 4.1 清单（每项：目的／判定真源／零 LLM／预注册／依赖）

| 编号 | 目的 | 判定真源（期望先行、冻结于实现前） | 零 LLM | 预注册要点 | 依赖 |
|---|---|---|---|---|---|
| **X1 SCOPE-CAS** | 条件提交真有正向与负向两格 | 4 格表：`epoch 未变→permit`／`epoch 变→refusal`／`独立作用域→permit`／`重启后 epoch 仍单调`；冻结在 `impl-*/NN-scope-prior.md` | 是 | N=4 格＋2 变异（删比较/恒 0）＋"成功格必须存在"这一条本身是验收项 | N1 |
| **X2 CHECK-REC** | 拒绝可持久取证，且不可伪造 | 3 格：`refusal→重启读回→记录存在`；`改 verdict→CheckOK 拒`；`删记录→Commit 拒` | 是 | 记录字段表（q,b,w,s,v,p,L）先冻结；每字段至少一个断言消费者（夏的术语锚定规则） | N2 |
| **X3 ENTRY-PORTS** | 统一入口是真入口，零调用是被测出来的 | 3 支路 × 2 向：复用→端口 0 次；方法→0 次；新判断→≥1 次；overlay 破坏入口→对应测试在目标处红 | 是 | 阳性对照（"确实需要模型"输入）与 overlay 脚本**收编为常驻件**，不是一次性脚本 | N3 |
| **X4 VALID-PROJ** | 当前有效性 = 生效关系，不是最大编号 | CX3 转正＋撤销态＋"先写后采纳"中间态＋重启 4 格 | 是 | 每格写"允许集合 Y"而不是单一值（候选/已生效/已失效可能共存） | N1,N4 |
| **X5 HANDOFF/AGING** | 每个不可放行都有归属与到期 | H0 表（reason_class→owner/deadline）＋扫描 3 格（未到期不报/到期报/owner 缺位聚合） | 是 | 表本身先冻结；aging 阈值预注册（复用 `graveyardSweep` 的 threshold 形态） | N5 |
| **X6 TREF-REPLAY** | 同一卷宗同一 `t_ref` 结论稳定；`t_ref` 变则结论按规则变 | 2×2 表：（t_ref=T1,T2）×（窗口内/外）；期望由原规则独立翻译 | 是 | **必须先证明当前实现会漂**（病存在性），再改 | N6 |
| **X7 COMPOSE** | 判定与席位组合后一致（今天不一致，见 §7.1） | 7 格 × {`verify(s1Judge(e))` 必须 ok}；在冻结表里新增一列"组合期望" | 是 | 期望列先改（先红），再改席位 | 无（今天就能做） |
| **X8 SEMANTIC-AUTH** | 每个语义项有授权人或显式欠账 | S 表：`term/rule/threshold → authority/ref/date 或 provisional+到期` | 是 | 零消费者术语扫描与 provisional 清单机检 | N8 |
| **X9 EXTRACT-3ARM** | 三组对照（共用错误/独立来源/原始材料） | arm1：期望＝穿透被如实暴露（**不是**期望拦截）；arm2：独立来源覆盖哪些错误；arm3：真模型，另册预注册 | arm1/2 是；arm3 否 | arm3 的标注、保留题、重复次数与统计口径**另行**预注册 | 真模型（用户启动） |

### 4.2 把邢超 `E_v=(S,D,Y,U,P,Γ)` 套到我方现有实验

| 字段 | 含义 | 我方现状（以 P0-A 为例） | 缺什么 |
|---|---|---|---|
| **S** 业务语义/适用范围/未决项 | 语义真源与未决清单 | ✓ 强：夹具 v1.1.0＋50 号 §三（逐格翻译依据）＋原文引注 | 缺**授权**：`SemanticTraceable` 只要求"可追溯到文档"，没要求"文档由谁批准"。`on_undefined_rule` 的归属方是空字符串 |
| **D** 样本/边界/构造方法 | 输入域 | ◐：8 格＋558 扫（生成器参数已入库） | 输入域窄：**单事件**、资产 3 点、无多事件组合、无覆盖维（`creditEvidence` 里根本没有"台账覆盖到几年"字段）。cell6 的"覆盖不足"只能用一个**不同对象**（`coverageGap([]string)`）近似 |
| **Y** 允许结果集合＋独立判据 | 期望 | ◐：7 格单值＋1 格（cell6）不可表达 | 不是**集合**；未覆盖情形的"允许控制结果集"（补证/复核/等待）没有表达；翻译只有一名译者的版本 |
| **U** 被测实现/模型/配置版本 | 被测物 | ◐：git 提交可指，夹具 `spec_version` 有 | **仪器本身无版本**（`s1Judge`/`verify` 是测试文件里的函数，无独立标识）；环境（Go 版本/OS）未记 |
| **P** 执行协议/对照/环境/重复 | 协议 | ◐：`go test -race` 有 | **变异结果不落档**（"Mutation probe: 撤窗→cell1 红"只写在注释里，无执行记录/无提交绑定）；无重复性声明 |
| **Γ** 预注册指标/失败判据 | 判据 | ✗（最弱） | 没有"失败判据"层：断言失败＝测试红，但"什么算实验失败"（如 `windowOnly` 低于多少即拒）从未预注册；`Admissible` 五条里 `ProtocolFixed` 与 `ResultsRetained` 靠约定 |

**结论**：我方实验在 `S` 上最强、`Γ` 上最弱；`Y` 的单值化是"未覆盖情形"被压成"已知答案"的机制；`U` 的"仪器无版本"使"跨提交复用证据"（邢 R6）无法论证。**最省力的补强顺序：Γ → P → U → Y（集合化）→ D（扩域）**。

---

## 五、证明了的 / 证伪了的 / 需进一步裁决的

### 5.1 证明了的（每条挂证据锚）

| # | 命题 | 证据锚 |
|---|---|---|
| P1 | 反例 A（历史长期逾期否决无界）在夹具文本、S1、席位三处一致 | 夹具 `rules[0].coverage`；`e2e_test.go:64-69`；`verifier_test.go:394-403`；`e2e_test.go:296` |
| P2 | overdue 术语不再吸收 >3 月阈值，且该性质被机械锚定（改回即红） | `p0a_window_test.go:94-121`；夹具:16 |
| P3 | 半年窗口谓词在 S1 侧恢复，边界含端点（monthsAgo≤6 在窗内） | `e2e_test.go:82-86`；`p0a_window_test.go:61-62` |
| P4 | 反例 1 在**判定侧**已关闭（不再 grant） | 我的组合探针输出：`judge=on_undefined_rule`，`!(kind==grant-50000 && ok)` 成立 |
| P5 | E7b 掩蔽面真实存在且解药有效（活 canary 顶掉死探针的 lastIntercept） | `e7_canary_test.go:335-553`；`health_test.go:82-91` |
| P6 | E4"频次判死亡"不可行，是我方自我证伪（诚实边界） | `health_test.go:181-246`；夏 R5 §2 收讫 |
| P7 | 105 号退役的成本/收益判断成立（机器保证被"当轮绿跑"覆盖） | `minor-ledger.md:1098-1120`；`runbook:16` |
| P8 | 账本的 torn-tail / stale-writer 纪律是真纪律（拒绝而非愈合） | `adopt.go:135-174`＋append 内 seq 连续性闸；单测存在 |
| P9 | 我方对四反例的复现是诚实的（逐字一致），且未把它洗成"组件缺陷" | 47 号 §一；我的 overlay 复现：CX2/CX3/CX4 仍 FAIL |

### 5.2 证伪了的（含本轮新证伪）

| # | 原声明 | 证伪证据 | 性质 |
|---|---|---|---|
| F1 | "六格表对 s1Judge 与 verify **分别断言且必须同红同绿——分叉即红**"（50 号 §1.3/§四.3） | **分叉已存在且无测试可见**：cell1/cell7 `verify(s1Judge(e))` 返回 `false`，理由为"rule 1 covers this assets point — on_undefined_rule contradicts the rules"；矩阵只断言 `verify(grant-50000)`，从不组合（`p0a_window_test.go:72`）。更重：cell1 上**五种 kind 全被拒**（附录 A.3） | **新证伪（本轮首报）** |
| F2 | "窗口面独立可达＝63 行 window-only"（`p0a_window_test.go:149-157`、`verifier_test.go:517-526`） | `windowOnly=63` 是**输入谓词的算术恒等式**（3 时长 × 7 年龄 × 3 资产），与实现无关；按资产分解：21 行（asset=0→grant-10000，窗口分支根本不进入）、21 行（asset=5→on_undefined_rule，原因带间而非窗口）、**只有 21 行（asset=35）是实现意义上的窗口面独有** | **新证伪（量级 3× 高估）** |
| F3 | "零模型调用由恒失败探针按构造证明" | `failingProbe.invoke`（t2host_test.go:174-178）全仓**无调用点**（grep 仅定义）；探针注册后无人消费 | 新证伪（比邢超的"不经入口"更深一层：**测量仪未接线**） |
| F4 | "R/K 经统一入口验收" | `t2host_rk_test.go:66`（store.get）、`:333-342`（findForNode+execute）；邢超 overlay 实证 | 邢超已证，我方已认 |
| F5 | "当前有效投影" | `t2host_test.go:105-132` 取 `max(rev)`；CX3 复现 `selected="candidate"`、`machineState=""` | 邢超已证 |
| F6 | "E1 拒绝作为 control 入账" | CX4：`control events=0 of 1` | 邢超已证，我方已撤 |
| F7 | "21 包全绿覆盖其全部保证"（邢超对我方 105 表述的读法） | 我方原话是"清偿证明＝当轮绿跑"（`runbook:16`），指**修复的效果**，不是**架构保证**；但对外表述未加限定词，读法可成立 | **表述缺陷，非主张缺陷**（见 §5.3 待裁） |
| F8 | "术语锚定规则已落地"（隐含） | 只锚了 `overdue` 一词；`resolution` 段从未解析（`verifier_test.go:369-372` 自认），`levels` 由 `spec.Levels` 解析。**P3 的病原体在判定词表层仍活着** | 新证伪（我方自认的边界之外） |
| F9 | "T2R 四读分立……有效性读指向 er-2＝全验"（`43-experiment-proposal-matrix.md` §一 Q3） | `TestT2R_StaleResultCorrection` READ-2（`t2host_rk_test.go:206-217`）里纠正版恰好是**更大的修订号** `er-2`，因此"取 max(rev)"与"取生效修订"在该场景下**输出相同**——测试绿在错误的原因上。把纠正版改成 `er-0`（或插入一个未采纳的 `er-99`）即红，但没有任何断言这样做 | 新证伪（wrong-reason green；与 R19 M-2 的"探针必须耦合"同族，但发生在语义层而非过滤层） |

### 5.3 需进一步裁决 / 待外部

**待邢超**

| # | 事项 | 我方建议立场 |
|---|---|---|
| X-A | `Admissible(E_v)` 是否增一条 `SemanticAuthorized`（语义由谁批准，而非仅"可追溯"） | 建议增。否则 `on_undefined_rule` 的"业务属主"永远是字符串 |
| X-B | `K_min` 是否接受"不可约 5 件"的压缩（`Bind` 与 `z_q.b` 是同一对象） | 建议接受；不改变语义，只减一次计数 |
| X-C | `H0` 首版用"发布表＋账本扫描"（不建等待态机）是否满足活性义务 | 建议接受。他还需要给"owner 缺位"一个可上报形态 |
| X-D | §五.2 的表述收敛：是否接受"此工具收益不足，保留必要契约验证，退役额外自动化" | 我方已同意他的措辞（47 号未逐字采用）；**"实验代码不再验"只作为本战役的成本决策，不作为一般原则** |
| X-E | cell1 的**系统级**正确输出到底是什么 | 我方主张：`on_undefined_rule` 且路由到 owner ticket；席位必须接受它（今天拒绝） |

**待夏**

| # | 事项 | 我方建议立场 |
|---|---|---|
| X-F | canary 缓行条件是否可收窄：`E7a②` 已证"已采纳操作上注入可达"，不可达的只有 unknown-op | 建议收窄。她的缓行记录把两类不可达混成一条 |
| X-G | "本体独立"的正面操作化：是否接受"oracle 作者溯源字段"（谁写的期望、写时是否读过实现/夹具）替代纯否定判据 | 建议接受。否定判据不可测，溯源字段可机检 |
| X-H | 验证席位"发现回流"的载体是否可用 check 事件（N2） | 建议用。她要求"回流成封存件"，check 事件可作为回流源而不进判定输入 |

**待刘 / 业务属主**

| # | 事项 | 现状 |
|---|---|---|
| X-I | 阈值 30/1/3/6 是否成立；"近半年"是否＝6 个日历月 | 夹具 `_expect` 自认"demonstration assumptions"；`business-owner-credit` 无收件人 |
| X-J | 半年度内短期逾期的正确业务处置（补证？复核？拒？） | 我方与邢超一致取"未覆盖/复核"；**尚无授权人签字** |
| X-K | 资产报告缺失但历史否决已成立时，是否允许直接 deny | t1Spec 定 precedence 0 优先；无 owner 确认 |

**待用户**

| # | 事项 | 理由 |
|---|---|---|
| X-L | 是否引入 **scope 作为新实体**（N1） | 这是数据模型级改动，不是测试修复；影响 schema、replay、projection 三处 |
| X-M | 是否同批做 0.2.0 grammar（scope＋check＋handoff 三类事件） | 一次迁移 vs 三次；建议一次 |
| X-N | conformance kit 是否对外发布（L4） | 涉及对外承诺与维护责任 |
| X-O | X9-arm3（真模型三组对照）是否启动 | **真 LLM 实验由用户本人启动**（本稿不代按） |

---

## 六、对当前实验方向与实现方向的"新打开"（7 条）

**O1 · "架构完成度的瓶颈是一个缺席对象，不是公式不全"**
`scope`（业务请求作用域＋生效指针＋epoch）在系统里不可表达，于是 `Current_r`、`Commit_r`、supersession、有效性投影四个"强名称"被迫寄生在 `max(rev)`、`observedSeq`、`storedResult` 三处，各自都弱。**建 scope 头不是新增平台，是在 adopt 包里加一张表＋一种事件**，一次关 8 个验收面（§3.4）。这是本稿的奇点判断：过去两周的公式族（R1-R6）在替这个缺席对象记账；补上对象后，公式里约一半的"待确认边界"自动消解。

**O2 · 验证席位的本体已经过期——P0-A 改了本体，没改席位的"覆盖模型"**
席位在 `verifier_test.go:507-509` 仍认为"资产>30 ⇒ rule 1 覆盖该点"。P0-A 之后 rule 1 的 coverage＝"资产>30 **且** 窗口干净"，于是"资产>30 但窗口脏"变成一个**规则未覆盖**的点，而席位把它当作"规则已覆盖、你说 undefined 就是逃避"。这不是一个 bug，是**方法**：per-kind mirror 是手写的，规则前提一变就漏。修法不是再补一个 `if`，而是把 mirror 从 `Q0`（数据）生成（N2-a）——**让"漏改某个 mirror"不可表达**。这是 singularity 意义上的结构改动，而非补丁。

**O3 · `t_ref` 缺席使 piece 6 replay 在全称意义上不成立**
证据用相对年龄编码（`monthsAgo`），参考时间只是散文（夹具:20）。同一份卷宗今天与三个月后重放，`monthsAgo` 不变而业务答案应当变——"同一输入同一输出"只对"同一墙钟"成立。这不是测试瑕疵，**是 replay 产品级缺陷**：`internal/replay` 的三模式（Inspect/Replay/Reevaluate）在跨期重放时会把时间维度压掉。补 `t_ref` 后，"同一输入"才有一个与墙钟无关的定义。

**O4 · 验收拓扑只有一个执行者，所以判定真源必须是便携件而不是 Go 测试**
邢超既是需求席位又是验收席位（并且是唯一**能跑**的外部席位：夏五轮全部"我方未重跑"，她自己也声明了）。这形成一个只有一条边的验证回路。今天"独立复现"的实际形态是他把探针**拷进我们的包**（`nga_external_review_test.go` 放 `internal/e2e`）——也就是说，所谓的外部判定在**我们的命名空间、我们的 helper、我们的夹具加载器**里运行。结果：他能发现"你没接线"，但发现不了"你的期望本身错了"（因为他复用了你的 `s1Judge`）。**判定真源必须与实现同仓但可独立执行**（N7）——`state-matrix.tsv` 已经证明这个形态可行，我们只借了一半。

**O5 · P3 的病原体在第三个层还活着：判定词表**
我们修了 `overdue` 术语，加了术语锚定探针。但 `resolution`（`on_undefined_rule`/`on_missing_evidence`）从未被解析（`verifier_test.go:369-372` 自认硬编码），`levels` 走 `spec.Levels`，`State` 走另一套。于是"诚实的不知道"在夹具里叫 `on_undefined_rule`，在机器里没有对应态，在宿主里**零消费者**（`t2host*.go` 0 引用）。修 overdue 是修了一个词；**判定词表是同一病的第二个宿主**。把夏的"零消费者术语禁发布"套到本方：`on_undefined_rule` 今天就是零消费者的规范术语，按她的规则**不许发布**——应该是 `handoff` 事件（N5）或 ticket，而不是一个字符串。

**O6 · 测量机制必须唯一：计数器＋基线＋阳性对照，而不是"按构造"**
同一个"零调用"命题，T0 用真实计数器和基线（`e2e_test.go:689-692`，写得好），T2 用"恒失败探针"（未接线，死代码）。两套机制并存，弱的那套承担了更重要的验收面。夏 R5 §五.2 的"探针接线证明（阳性对照必红）"正是这个：**注册≠消费，接线本身需要阳性对照**。统一为"端口计数器＋基线断言＋一个必须触发的正向对照"，删掉第二套。

**O7 · `on_undefined_rule` 的两端都错：一端被席位拒，一端被机器当 grant 派发**
今天它的两个下场是：(a) 席位拒绝（§7.1），等价于 de facto deny——正是邢超明令禁止的"补写成必然 deny"；(b) 若绕过席位，`Adopt`+`Dispatch` 对它一视同仁（机器语义盲），它会像 grant 一样被派发。**"诚实的不知道"在系统里既不能通过也不能停下**。这条把一个"语义诚实"的成就变成了一个控制面空洞——也是 N5 存在的理由。

---

## 七、独立发现（提纲没问，但重要；全部带 file:line 与可复现命令）

### 7.1 【最重】P0-A 的"双实现互证"在组合处死锁：验证席位拒绝自己的正确答案

- **现象**：`verify(s1Judge(e))` 在 cell1（{dur:1, ago:1}，资产 35）与 cell7（{1,6}）返回 `ok=false`，理由 `"rule 1 covers this assets point (above the upper bound) — on_undefined_rule contradicts the rules instead of answering them"`。
- **机理**：`verifier_test.go:507-509` 的 band mirror 只看资产（`assetMillionsDeclared > hi` ⇒ 认为 rule 1 覆盖），而 P0-A 把 rule 1 的 coverage 改成"资产>30 **且** 窗口干净"（夹具:53）。于是"资产>30 且窗口脏"这个新生的未覆盖区，被判为"规则已覆盖所以 undefined 是逃避"。
- **更重**：对 cell1 **五种 kind 全被拒**（grant-50000→窗口前提违反；grant-10000→资产≥下界；deny→无否决是伪造；on_missing_evidence→报告在场；on_undefined_rule→规则覆盖）。**验证席位在这个输入上有一个不可满足的定义域。**
- **为什么没被发现**：六格矩阵对两者**分别**断言（`p0a_window_test.go:67-75`：s1 断 `v.kind`，verify 断 `verify(grant-50000)`），从不组合；组合形态只存在于 E1 病灶测试（`correctness_probe_test.go:83,147`），而那两条不走窗口分支。
- **后果**：P0-A 的"反例 1 已关闭"只在判定侧成立；系统级它从"错误放行"变成"正确判定被拒"，仍然是邢超禁止的"补写成必然 deny"的一种（拒绝＝事实上的 deny）。
- **复现**：附录 A.3（overlay，不改树）。
- **定性**：这是"组件保证≠系统保证"在我方**单个测试文件内部**的实例——不需要宿主、不需要集成，两个测试层组件之间就已经裂开。它同时证伪了 50 号 §1.3"分叉即红"的机制声明。

### 7.2 `windowOnly=63` 是算术恒等式，不是实现行为（3× 高估）

- `p0a_window_test.go:149-151`：`if dirty && !veto { windowOnly++ }`——`dirty`/`veto` 都由测试自己按循环变量算出（`d=a<=6`、`d>3`），**从不读 `s1Judge` 的输出**。63 = 3×7×3 是循环边界的乘积。
- 真实分解（`awk`，附录 A.2）：asset=0 的 21 行 `s1Judge` 返回 `grant-10000`（窗口检查在 `assetMillions>30` 分支**内部**，`e2e_test.go:73-86`，根本不会进入）；asset=5 的 21 行返回 `on_undefined_rule`，但**原因是带间**，去掉窗口分支结果不变；只有 asset=35 的 21 行是真正由窗口谓词决定的。
- **归档比对**（`:170-172`）确实能抓到"删窗口分支"（因为 `s1Kind` 列会变），所以敏感性还在；但**"63 行独立可达"这一被反复引用的量化证据虚高 3 倍**，且它被用来反驳 R37（"零可达"）——用一个与实现无关的计数去反驳一个关于实现的结论，逻辑上不成立（它只反驳了"输入域内无可达组合"，没有反驳"实现里窗口面不承重"）。
- 附带：`50 号` §三 cell6 的期望是"on_missing_evidence 路由"，但 `p0a_window_test.go:81-86` 只断言 `coverageGap(...)` 非空——**既不是 s1Judge 也不是 verify**，且 `creditEvidence` 结构里没有"台账覆盖"字段，该格在 S1 输入模型里不可表达。50 号 §五.1"六格+边界 8 行全绿（双断言）"因此不准确：7 行双断言 + 1 行单断言（且是另一个对象）。

### 7.3 结果存储非原子，且"已派发但结果丢失"无修复路径（邢超问过、无人建）

- `resultStore.put` 直接 `os.WriteFile(rs.path, raw, 0o600)`（`t2host_test.go:84-93`）——整表重写，**无 temp+rename**。对照账本 `append` 有 temp+rename＋torn-tail＋stale-writer 三道闸（`adopt.go` append 体）。
- 顺序：`adoptAndDispatch`＝Adopt→Dispatch→`store.put`（`t2host_test.go:567-587`），`MarkCompleted` 是另一个调用（`:591-593`）。崩溃在 Dispatch 与 put 之间：账本说 dispatched，存储无结果 → `nodeEntry` 返回 "no stored result"（`:558-561`），**没有任何恢复/对账入口**。
- 这正是邢超 `198789782` §五 How 末句要求的"结果写入与采纳/完成记录之间的中断"处理。当前 21 包绿对此零覆盖。
- 语义上的不对称也值得记：**决定账本是 crash-safe 的，结果存储不是**——R5 的 `ReportedComplete ⇒ Durable(TerminalEvidence)` 只在账本侧成立。

### 7.4 "重启"不含知识面：registry 是内存指针，跨 reopen 共享

- `reopen()` 明确共享 registry 指针（`t2host_test.go:464-469`，注释诚实自认："a real process restart would re-publish into a FRESH registry"）。
- 后果：K 场景的"新任务零模型调用"在**重启后**不成立（registry 会空）；`mustPublish` 的"重发布闸"（R22）只在同一进程内有效。K 目前没有失败路径的验收。
- 这与 R5 的 `Critical_r` 直接冲突：知识适用性（哪个方法版本在效）是准入前提，却不在持久面。

### 7.5 T0 与 T2 用了两套"零调用"测量机制，弱的那套承担了更重的验收

- T0：真实计数器＋基线断言（`e2e_test.go:689-692`，注释还自证"计数器坏了基线会红"）——好范式。
- T2：`failingProbe`（`t2host_test.go:164-190`），`invoke` 无调用点（附录 A.4 grep）。
- 建议：只保留一种机制，并把"正向对照"作为该机制的一部分（否则"零调用"与"探针从未接线"不可区分）。

### 7.6 「四反例」一词两指——同一短语在内部与外部指两个不同的集合

- 邢超的"四个契约反例"（`198789653` §2）＝ {近期短期逾期、已替代决策仍派发、未采纳结果成为当前、验证拒绝无持久证据}。
- 我方 `43-experiment-proposal-matrix.md` §一 Q5 的"四反例**全部落地**"＝ {E1 稳定错误拦截、E2 证据覆盖不足、T2R 纠错重试、K+E-GR 失效知识}。
- 两个集合**交集为空**。内部文档用"全部落地"描述后者，而外部文档（47 号）用"四个契约反例 4/4 FAIL"描述前者——同一次战役里，同一句话在两侧指向相反的事实。这不是措辞问题：它是"内部收官记录诚实、对外声明保留宽口径"（47 号 §一.3 自认的分叉）的**术语级活体**，且恰好发生在我方最需要精确的地方。
- 建议：术语表（`B_v.T`）里对"反例"加限定词——`external-contract-counterexample`（邢超集）／`internal-experiment-counterexample`（我方集），并用 `B_v.T` 的机检（术语锚定规则）保证每个出现处带限定词。

### 7.7 READ-2 的 green 是"构造让弱实现通过"

详见 F9。补充机理：`lookupByBusinessRequest` 的唯一判据是 `rev > bestRev`，而 `TestT2R_StaleResultCorrection` 把纠正版命名为 `er-2`（`t2host_rk_test.go:187`）——场景作者无意中让"数字更大"与"已生效"共变。这与邢超 §七.4"变异变红也要问为什么红"是**同一纪律的镜像面**：**测试常绿也要问为什么绿**。补法不是加断言，而是让两个候选在场景里**不共变**（纠正版 `er-0` 或插入未采纳 `er-99`），使弱实现必然输出不同结果——这与 P0-A 在 cell7/8 上钉边界是同一手法。

---

## 附录 A · 复核命令与原始输出

### A.1 全量测试

```
$ cd /Users/yaojun/nga-impl-wt/agent-festival/go && go test ./... -count=1
ok  .../cmd/adopt ... ok  .../internal/adopt ... ok  .../internal/e2e ...
（21 包 ok，无 FAIL；未加 -race）
```

### A.2 扫描计数分解

```
$ wc -l testdata/p0a_scan.tsv                      → 561（558 数据行 + 3 注释）
$ awk -F'\t' 'NR>3 && $4==0 && $5==1'              → 63
$ awk -F'\t' 'NR>3 && $4==0 && $5==1 {print $3}'   → 21×0, 21×5, 21×35
$ ... {print $3, $6} | sort | uniq -c
      21 0 grant-10000
      21 35 on_undefined_rule
      21 5 on_undefined_rule
$ awk ... $3==35 && $4==0 && $5==1 | wc -l          → 21
```

### A.3 组合探针（Go overlay，未改工作树）

```
cell1-recent-short   s1=on_undefined_rule  verify(ok)=false
    reason=rule 1 covers this assets point (above the upper bound) — on_undefined_rule contradicts the rules instead of answering them
cell2-historic-short s1=grant-50000        verify(ok)=true
cell3-recent-long    s1=deny               verify(ok)=true
cell4-historic-long  s1=deny               verify(ok)=true
cell5-clean          s1=grant-50000        verify(ok)=true
cell7-boundary-in    s1=on_undefined_rule  verify(ok)=false   （同上理由）
cell8-boundary-out   s1=grant-50000        verify(ok)=true

cell1 五种 kind 全拒：
  grant-50000         ok=false  rule 1 (upper band) premise violated: … inside the 6-month window …
  grant-10000         ok=false  … contradicts rule 2 (the level-band consistency face)
  deny                ok=false  … rule 0 is the only deny path in this spec, so this deny is fabricated
  on_missing_evidence ok=false  … the spec's resolution scopes on_missing_evidence to the asset report alone …
  on_undefined_rule   ok=false  … rule 1 covers this assets point …
```

### A.4 四反例重放（同一 overlay 手法）

```
CX1 closed-in-his-form=true  (judge="on_undefined_rule", composed-verify-ok=false)
CX2 status after er-2 admitted="dispatched"   (closed=false)
CX3 selected="candidate" machineState=""      (closed=false)
CX4 control events=0 of 1                     (closed=false)
```

### A.5 探针接线检查

```
$ grep -rn "\.invoke(\|probes\[" internal/e2e/*.go
t2host_test.go:477:	h.probes[name] = p
（结果：`.invoke(` 零调用点；只有注册语句）
```

### A.6 禁读清单合规

未打开：`impl-2026-11-01/44-collision-xingchao-xia-experiments.md`、`45-collision-round2-blank.md`、`46-collision-integrated.md`、`51-architecture-collision-round3.md`（及任何含其内容的摘要/引用）。已读的我方材料：`47-reply-xingchao-r5-archived.md`（全文）、`50-p0a-scope-prior.md`（全文）、`43-experiment-proposal-matrix.md`（**仅头部 20 行**，用于核对"四反例"一词；其结论已被本稿 F9/§7.6 反证，未采信）、`docs/minor-ledger.md`（按需 grep）、`docs/review-loop-runbook.md`（全文）、`docs/attack-corpus.md`（§一/§二）、`loop-progress.log` 尾 8 行。

---

## 结尾：三句话

1. **完成度不是公式覆盖率**：10 个强名称里只有 3.5 个敢拒绝错误；决定这一点的不是 R1-R6 写得全不全，而是 `scope` 与 `check record` 两个对象在不在。
2. **最深的裂缝在"两个组件之间"，而且已经裂在单个测试文件内部**：判定说 undefined，席位说 undefined 非法，五种判定全拒——这一条比任何外部反例都更能说明"组件保证不能相加成系统保证"。
3. **判定真源必须便携**：只要外部评审者还得把探针拷进我们的包、复用我们的 helper，他能发现的就永远只是"你没接线"，发现不了"你的期望本身就错"——而后者才是这一轮真正发生的事。
