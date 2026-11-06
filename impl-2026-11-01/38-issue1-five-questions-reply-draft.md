# 39 · issue1 五问实验答复（草稿——待 yaojun 过目后发）

> 状态：**草稿 v2——五问原文已从 issue 198232012 逐字取回填入（占位清零）**。待 yaojun 过目确认后发 issue1。
> 数据来源：全部实验结果取自 docs/minor-ledger.md R29-R46 段 + impl-2026-11-01/37 号对账 + 各测试文件本体，与 MR !2 head ee58bfb 逐字核对。

---

**对 198232012 §七五问的实验答复**

邢架构师：

本回复只做一件事：把为回答你五问所做的实验、实验装置、实验结果、以及每个结果的边界，逐条呈报。原则三条：**一切以实验结果说话**；每个可证伪声明附反突变探针（我们对自己声明的"已修/已验"同样可证伪——包括承认其中一笔曾经是假账，见 §七）；全部装置在 MR !2（head `ee58bfb`）内可复跑，复跑命令随装置索引给出（§六）。

四层证据声明自适用：本回复主张**组件符合性**与**实验事实**；宿主集成（制品 B）、业务语义（业务属主座位）、模型能力（T1 单点读数）各自独立验收。

---

## 一、Q1

> 【你方原文】"**正确性的依据和最终责任在哪里？** 请按判断类型列出规约、权威事实来源、可验证约束、不可独立验证部分，以及由谁批准生效。允许不同业务域采用不同能力，不能统称由 S1 或宿主负责。"

**我们的回答分两半：用实验关闭了前置条件；用诚实声明交代了无法单方关闭的主体。**

**1.1 实验关闭的前置：规格自相矛盾时一切正确性机制失效（E3）**

回答 Q1 之前必须先回答一个更前置的问题——规约本身错了怎么办。E3 实验给出了确定性答案：我们的授信规格夹具曾经**自相矛盾**（夹具文本写否决限"窗口内"六个月、T0 替身按无界实现、t1Spec 声明优先级 0 压缺证——三方各自"正确"，整体矛盾）。装置：`go/internal/e2e/correctness_probe_test.go` 的 TestE3SpecSelfContradiction_WindowScope / _C8Precedence。

结果：矛盾被证明后修正（P3——含你的 35M/近窗干净/两年前 4 月逾期反例，现为夹具正式用例；L23——否决优先序对齐）；修正后的三方一致**被突变探针钉死**：否决阈值与带界数字**从夹具文本解析派生**（anchorVetoMonths / anchorBandBounds，verifier_test.go），夹具阈值漂移（"three"→"six"）或带界扩展（30→300）都使锚测试变红——规格与执行方的第三条腿不再可能静默分叉。

**为什么先说这个**：Q1 要求"按判断类型列出规约"——E3 证明规约自身的一致性是 Q1 表的第一行；规格自相矛盾时，表的其他列（权威来源/可验证约束）无从填起。这不是推诿，是实验排出的依赖顺序。

**1.2 诚实交代的主体：逐类型表（我们的 C1 提案）需要三个座位**

schema 草案位已备（verifiability_class / authority / approves_effective 字段——提案随制品 A 线）；授信否决规则的样例行已由 P3 夹具示范（coverage / exceptions / examples / 反例用例俱全）。但逐类型表需要：**业务属主座位**（现无人坐——激活请求已提）、你侧管理面的批准权定义、夏的规格框架收口。三方各持一角，任何单方先写都会被另两方推翻重排——我们选择先把实验能钉死的部分（一致性、样例行、字段位）钉死，把座位激活作为联合请求。

---

## 二、Q2

> 【你方原文】"**面对稳定错误且不自报 unknown 的 Jev，生效前由什么机制发现并处理？** 用上述 A/B 反例说明；哪些能确定拦住，哪些只能降低风险，哪些仍无法检测，分别声明。"

**这是五问中实验证据最完整的一问。按第一性原理拆解：稳定错误的发现是三层问题——(a) 错误能否进入系统（入口）(b) 进入后能否被拦（拦截）(c) 拦截动作能否被审计（审计）。三层各有独立实验。**

**2.1 入口层：病的存在性证明（E0）**

sick S1（恒返回 grant-50000，无视卷宗中 4 个月逾期）驱动真实组件走完全链：采纳 → 派发 → 业务 API → 完成。结果：**WGR = 1/1，3 个事件、0 个控制事件**——采纳门语义盲视被实验钉死，不是断言。装置：`go/internal/e2e/correctness_probe_test.go` TestE1_BlocksSickS1（前身病态断言已重写，历史在 git）。

这直接证实你的"consistent but wrong"批评：控制语义（幂等/撤销复检/断尾拒绝）对**判定对错**结构性失明——且这是设计而非缺陷（控制面不发明业务含义，三处文本共守的层界）。

**2.2 拦截层：验证席位的存在性→拦截性证明（E1）**

修复的正确层位是**宿主侧验证席位**：确定性函数 verify()，规格驱动（阈值/带界从夹具解析——见 §1.1），**读原始卷宗而非 S1 的提取产物**（hermes-self-evolution 的"确定性硬门+LLM 仅咨询"同型分层）。结果：

- **WGR 1/1 → 0/1**：sick grant 在派发前被拒，操作停在 adopted、零 API 调用（bankAPI 计数断言）；拒绝作为宿主层事实记录，不伪造账本事件
- **提取陷阱臂**：S1 收到的输入漏掉逾期记录（E0 时代的"独立性陷阱"——验证器若消费同一提取产物则继承错误），席位读 raw 卷宗照样拦截——**陷阱死亡**
- **对称面**：伪造 deny（干净记录谎称否决）同拦；错误级档（grant-10000@35M）同拦；窗口前提由 rule 0 承载（独立面在谓词域上被完全包含——1408 输入暴力扫描零可达，已退役并声明）
- **阳性对照**：正确的 deny 与规范的 grant-50000 过闸不受损——新门不伤健康流

装置：`go/internal/e2e/verifier_test.go` verify() + TestE1_BlocksSickS1 / TestE1_SeatKillsExtractionInheritance / TestE1_MirrorAndBandFaces / TestE1_VocabularyConsumptionComplete。

**2.3 审计层：拒绝是控制事件，不是返回值**

每次拦截以 control 事件入账（携带操作全归因钉），重放投影为零状态——"多少次已撤销/越权/伪造的尝试被拦下"可审计。装置：`internal/adopt/adopt.go` refuse() + TestE6_ConditionalCommit 的 control-event 断言。

**2.4 诚实三分类（回应"哪些能发现、哪些不能"）**

- **能确定拦住**：形式化约束（否决阈值/带位一致性/级档映射/词表——全部规格驱动且锚定）、证据覆盖差集（E2，见下）、证据在场双向（无报告出 grant 拒/在场谎报缺证拒）
- **只能降低风险**：开放语义（带间资产——on_undefined_rule 出口，无默认授予）
- **无法检测**：上游数据自身失真且无独立核验源——你反例 B 自己承认的边界。但 E2 把它的机器可拦部分关了：**"只有 6 个月材料"≠"历史上无逾期"**——夹具声明的必需证据源与输入快照声明在场源做差集，缺口在判定前路由（S1 未被询问形态）。装置：TestE2_CoverageGapBlocksCounterexampleB。

**2.5 可证伪性声明**

本节每个面的探针带反突变：verify 恒通过→双臂红；镜像面删除→红；夹具阈值漂移→锚测试红；完备性门删除→合成新 level 直通红。R45 轮空白复审将 R29-R44 **七项关键突变声明全部实测转红**（独立复核，非自报）。

---

## 三、Q3

> 【你方原文】"**怎样把纠错与 R/K 兼容？** 请走通"正确复用原记录"和"停止把错误结果/过期方法当作当前有效依据"两个需求，明确原记录、当前状态、关联修订与业务请求的区别。"

**实验证伪了"矛盾"：复用与纠错在四读分立下共存。**

第一性原理：矛盾只在"复用=记录不可变=不可纠"的读法下成立。我们的语义是**决策记录不可变 + 当前有效性可投影**——四个词各指一个查询面：

| 读 | 语义 | 断言 |
|---|---|---|
| 幂等读 | 同键同载重试 → 原 receipt 不变 | 原记录不可变 |
| 有效性读 | 当前有效投影 = 最新已采纳修订 | 纠错修订 er-2 是当前 |
| 历史重放 | 原事件与纠错事件**并存**（不重写） | 双方在账本可追溯 |
| 知识消费 | 新任务检索到修正方法，非 stale 方法 | 注册表过滤面 |

场景：错误结果 er-1（wrong-grant）→ 纠错修订 er-2（deny，否决触发）→ 四读全绿。装置：`go/internal/e2e/t2host_rk_test.go` TestT2R_StaleResultCorrection（四读）+ TestT2R_PermissionRevoked（授权镜像：授权读服务/空拒/**降级 selector 拒**——D-04 缺口从认领变已拦，TestE5_ReadAuthorizationVariants）。

术语对齐：用你的词——原记录（original receipt）/当前状态（validity projection）/关联修订（correction revision）/业务请求（business request）。

---

## 四、Q4

> 【你方原文】"**S2/人工复核的权限与证据增量是什么？** 谁可以提出、谁可以批准、分歧如何处理、未决如何提供服务；不能让"人工/另一个模型同意"成为没有依据的真值开关。"

**诚实声明：这是五问中实验承载最薄的一问——权限是授权代数（领域语义、无标准轮子），我们只有场景形态，没有独立实验。**

已有实验面：T2 纠错修订场景是"复核产出新修订"的机器形态（er-2 的采纳 + control 事件入账）；复核权限的字段位已在 schema 草案提案中预留。

框架映射：你的"复核必须说清新增了什么独立依据"与我们收到的独立裁决中"独立互证的价值恰来自未通气却查到同一处"是同一判据的两侧独立结晶——这句对合流值得明说。补证上限预注册、规格失灵三情形人裁入口，映射到该框架的对应条目。

剩余：纠错权限的授权代数（谁能发起纠错、需要什么证据增量、增量由谁判定充分）——0.2.0 schema 批次 + 与框架的权限条目联合作业。我们不预判，先交场景形态。

---

## 五、Q5

> 【你方原文】"**哪些由 openJiuwen 复用、哪些由领域知识/工具承担、哪些才需要 NGA 增补？** 请给最小映射和验收点，不强制新产品或新服务。R/K 实现中至少纳入稳定错误拦截、证据覆盖不足、错误结果纠正后重试、失效知识拒绝新任务复用这些反例，并声明证明范围。"

**先答你点名的四个 R/K 反例——全部已落地且各有实验**：

| 你点名的反例 | 我方实验 | 装置（MR !2 head ee58bfb） |
|---|---|---|
| 稳定错误拦截 | E1 验证席位（WGR 1/1→0/1）+ E0 病存在性证明 | verifier_test.go TestE1_BlocksSickS1 |
| 证据覆盖不足 | E2 覆盖差集（判定前路由，反例 B 机器可拦） | TestE2_CoverageGapBlocksCounterexampleB |
| 错误结果纠正后重试 | T2R 四读分立（er-1 错误结果 → er-2 纠错修订采纳） | TestT2R_StaleResultCorrection |
| 失效知识拒绝新任务复用 | K 变体（superseded/invalid 方法不被新任务消费）+ E-GR 坟场回捞 | TestT2K_ExpiredKnowledgeNotConsumed / TestEGr_GraveyardSweep |

证明范围声明：以上为**组件级+参考宿主级**验证（控制语义+宿主形态）；业务语义（规格内容正确性）归业务属主座位（E3 已证其前置性），openJiuwen 侧执行能力映射归制品 C 联合作业。

**你 §七 Q5 点名要纳入 R/K 验收的两面，恰好是已落地的两个实验：**

- **E5 读取授权变体**：宿主侧检查（grantsCoverRead——kind/selector/actions 内容匹配）+ 机器盲边界钉（State() 无授权——设计声明）。三形态断言：授权读服务/空拒/降级 selector 拒。
- **E6 条件提交**：DispatchIfCurrent——伪造/跨线观察（observed≥0）一律拒绝并记控制事件；任意负值为 fresh 形；**双窗口逐字声明**：撤销形干预在派发前拦截（窗口 1 覆盖）；"已发出未确认"窗口不预假装可撤——MarkUnresolved 路径 + 残留窗口如实声明（窗口 2）。46 个既有 Dispatch 调用点零改动（opt-in 独立方法）。

**制品 C 联合作业认领**：我方控制语义底单已备——采纳/幂等/对账/回放/取证五面全部组件化、夹具双 oracle（Go+Python）、T2 参考宿主现状。请求你方供 openJiuwen 侧行（执行/状态/恢复能力 → 五控制面的映射）；"等待驱动/终态观察者"类缺口的判定需要你方确认，我们不预判。参考宿主不作新基座的边界句接受（原文引用你的 §一.5）。

---

## 六、实验装置索引（全部在 MR !2，head `ee58bfb`，`cd go && go test ./... -count=1 -race` 全绿 21 包）

| 实验 | 装置（文件:测试） | 反突变（删除修复即红） |
|---|---|---|
| E0 病存在（历史） | correctness_probe_test.go（git 历史 R20 前形态） | — |
| E1 验证席位 | verifier_test.go verify() + TestE1_BlocksSickS1 / SeatKillsExtractionInheritance / VocabularyConsumptionComplete | verify 恒通过→红；完备性门删→红 |
| E1 锚定 | anchorVetoMonths/anchorBandBounds + TestE1_VetoThresholdAnchored / BandBoundsAnchored / CompoundWords / MultiHitConflicts / MixedOrder / WhitespaceVariantConflictsCaught / AnchorPurity / FailClosedAnchored / BandAnchorFailClosed | 夹具漂移→红（阈值/带界/扩展/分隔符/复合词/空白变体） |
| E2 覆盖差集 | coverageGap + TestE2_CoverageGapBlocksCounterexampleB（真条件流） | coverageGap 恒空→红 |
| E3 规格一致 | TestE3SpecSelfContradiction_WindowScope / _C8Precedence | 夹具回退/替身回退→红 |
| E4 守卫健康 | aggregateControl/guardDied + TestE4_* 三测试 | 死亡条件移除→红 |
| E5 授权变体 | grantsCoverRead + TestE5_ReadAuthorizationVariants + TestT2R_PermissionRevoked | 回退非空检查→红 |
| E6 条件提交 | DispatchIfCurrent + TestE6_ConditionalCommit / NoVersionCheckDetailEverLands / DocContractPinned | 版本门删→红；doc 复活→红 |
| E-GR 坟场回捞 | graveyardSweep + TestEGr_* 三测试 | excess 膨胀→红 |
| T0 控制环 | e2e_test.go 十场景（TestT0*） | 各场景历史反突变 |
| T2 R/K | t2host_rk_test.go 八场景 | E5 缺口实证 |

## 七、方法论与自我纠错记录

十八轮空白复审循环（R29-R46），三连 0 BLOCKER/0 MAJOR 收官（R44/R45/R46），总账 **1 BLOCKER + 26 MAJOR + 48 minor 全部清偿**，方法论 47 条实证入账（docs/minor-ledger.md）。

**我们自己的两笔假账被这套流程抓出并纠正**——这部分如实写，因为它证明声明的可证伪性不是姿态：R38 B-1（"镜像下半域已修+反突变红"的账本声明，修复本体未落地——patch 未匹配后未重验，真落地+反突变红留痕后才重立账）；R30 M-3（"直检探针"写进了账本而探针不存在——下一轮空白复审抓出）。对"已修"的声明与对"有病"的声明适用同一条纪律。

## 八、请求

1. 五问按本回复逐条核对；每条末的剩余缺口（C1 逐类型表 / C5 openJiuwen 侧行 / 纠错权限代数 / T1-run3 题库）请确认联合作业形态与排期
2. T1-run3（题库扩至两位数+掺"应无法判定"题，掺题比例预注册）已备好待启动——跑前冻结、绝不暗改
3. 如对任何实验装置或结果有疑，指定测试名，我们提供逐行走查或现场复跑
