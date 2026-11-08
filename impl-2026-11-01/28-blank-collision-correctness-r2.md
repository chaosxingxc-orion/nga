# 28 号空白位碰撞报告（R2）：Jev 判断一致但判断错误时，NGA 如何处理

> 独立性声明：本文由空白位独立完成，未读取 `impl-2026-11-01/` 下任何既有文件（含 27 号同题碰撞）。所有结论只来自：对方 198232012 原文、festival 仓代码/夹具/台账、OpenJiuwen 认知智能体源码与设计文档、`~/frame-bench` 生态源码、双方历史协商文本，以及本仓已提交的测试实态。
> 基线：festival 仓 HEAD `239eaba`（代码基线 `fbf8dd5`，之后为 docs 提交）；`go test ./internal/{adopt,ledger,evidlog,replay,e2e} -count=1` 五包全绿（本次实测，2026-11-04）。对方引用的 MR head `fbf8dd5` 与代码实态一致。
> 写作纪律：每条关键断言带 `file:line` 或原文引用；推测标〔推测〕；只读分析，唯一写动作是本文。

---

## 0. 一页摘要

### 0.1 总裁定

1. **方向对，且比我方上一轮承认的更严重。** “幂等≠正确”不是补充条款，而是我方采纳闸的**结构性盲区**：闸从设计上就不看语义结论。错误一旦被幂等持久化，系统会以“更稳定、更可审计”的形态把错误放大——对方这句判断成立，我方认领。
2. **但对方的药方开错了层级。** 对方把“正确性”当成一种可以在运行时“生效前”统一拦截的属性。正确的第一性表述是：`Correct(decision, spec, facts, t)` 是一个**关系**，不是决策自身的谓词；框架只能检查这个关系的**已声明近似**。可检查的只有“可判定约束子集”，其余只能是评估、人工、事后纠错。
3. **我方第一缺口不是“缺一个正确性引擎”，而是“判断结果与前置条件不是采纳契约的一等字段”。** `adopt.Request` 只有身份/版本/digest/授权/归因，没有 verdict、没有前置条件、没有检查证明（`go/internal/adopt/adopt.go:71-78`）；`Adopt` 只做 schema 校验（`:261-332`）；`Dispatch` 只复检授权（`:337-360`）；执行图的 `plan` 只有 `seq/par`，没有条件边（`schema/execution-graph.schema.json:26` + `$defs.plan_node`）。因此“S1 结构化判断 → 声明式映射 → 框架推进”在机器层**只实现了前半段**：判断进去了，映射和图推进没有机器形态。今天任何“可判定的违反”都无法在闸上触发——这不是策略选择，是契约缺字段。
4. **三个反例在代码现状下的结论：A 在运行时可复现且必漏（除评估层 T1）；B 结构性未覆盖（无输入快照 schema、无事实覆盖检查）；C 结构性不可见（状态词汇封闭、无纠错事件、无有效性投影）。** 三者都不是“补个测试”能解决的，分别缺：前置条件字段、事实覆盖声明、追加式纠错通道。
5. **五层拆分方向可用，但不是划分。** 它把“输入充分性”藏进“判断正确性”的“事实范围”限定里，随后又在反例 B 里把它拿出来当独立问题——这是定义滑动：scope-relative correctness 与 world-relative correctness 不能同时成立。缺的层至少有：输入充分性/覆盖、事实真实性/来源可信、规格正确性/适用性、授权合法性、时效/当前有效性、可归因性。
6. **最深的上限是独立性上限：独立性 = 信息独立性 × 实现独立性 × 信任根独立性。** 同数据、同规格、同分布的两个模型会相关地错；进程内“自查证明”只是审计记录，不是保证。只有外部权威系统（业务 API 自己的不变量、登记库、账本旁证）在其自有不变量上同时具备三者。因此“多模型一致/人工同意”只能作为**证据**，不能作为真值开关。
7. **我方自证一个活缺陷：承重规则在我方两份资产里互相矛盾。** `judgment-spec-credit.json:45-49` 的 veto 是“窗口内”（six-month window）；T0 替身与 T1 规格是“无界历史”（`go/internal/e2e/e2e_test.go:39-56`、`go/internal/e2e/t1_llm_test.go:80-96`）。更严重：C8（缺资产报告 + 历史逾期）上 T0 替身先返回 `on_missing_evidence`（`e2e_test.go:49-51`），T1 却把 `deny` 钉成 hard bar（`t1_llm_test.go:164-170`）。台账 L23 已自认（`docs/minor-ledger.md:56`）。这说明“规格正确性”不是假设，是我方当前状态；也说明“谁验证规格”这个问题必须先于“谁验证判断”。
8. **结论：不做通用正确性引擎。** 做四件最小事：三值前置条件（pass/violated/undetermined）+ 覆盖声明（closed/open world）+ 追加式纠错与有效性投影 + 规格样例可执行化。采纳闸保持语义盲，只校验“已声明检查的在场与结果”；业务语义检查由宿主/领域件执行并把结果作为契约字段送入。这是对现有架构的自然延伸，不是新基座。

### 0.2 我认为最深刻的三个发现

- **F1（契约盲区，非能力缺口）**：闸看不到 verdict，图没有条件边。任何“正确性拦截”在今天都无处落地；最小修复是 `preconditions[]`（id/version/result/coverage/attested_by），不是规则引擎。`adopt.go:71-78`、`:261-332`、`execution-graph.schema.json:26`。
- **F2（规格自证失败，且是活的）**：fixture 与 T0/T1 在承重 veto 上互相矛盾，C8 上两个 S1 实现给出不同优先序。规格目前是“散文进、散文出”，`examples` 是字符串而不是可执行断言（`judgment.schema.json:192-224`），所以规格可以 schema-valid 却自相矛盾。把 examples 变成“结构化事实 + 期望 verdict + runner”，是成本最低、收益最高的一步。
- **F3（独立性天花板）**：验证的独立性不可能超过“信息 × 实现 × 信任根”三者之积。LLM 合议、S2 复核、人工同意，若共享同一份不完整数据和同一份被误读的规格，就是相关误差；进程内 attestation 只证明“有人填了表”，不证明“表是对的”。所以唯一诚实的承诺是：可判定约束必检、未定必路由、错误可发现可纠正、范围与残余风险显式声明。

### 0.3 验证计划一句话

先用**零 LLM 的 A0 对照 + 故障注入 + 覆盖率蒙特卡洛**证明“病存在、且各臂差异可测”，再比较 A1（三值前置闸）、A2（追加纠错+有效性投影）、A3（独立复核集成，仅作证据）；A3 的真 LLM 相关性实验由用户本人启动，智能体只准备到“万事俱备”。

---

## 1. 对方新议题的定性：新问题还是自然延伸？

### 1.1 判定：半新——结构层已有，语义层没有

| 议题要素 | 我方现有件 | 覆盖度 | 确切缺口（file:line） |
|---|---|---|---|
| 判断幂等/重试不重算 | `adopt` 状态机（同键同载 reused、异载 conflict） | 完整 | 无（这是已钉资产） |
| 判断/版本/依据入记录 | `ledger.Versions` 五维 + `payload_digest` | 部分 | 五维全是自由字符串，`versions.rule` 与 `question.spec_version` 无哈希/引用绑定（`ledger.go:106-113`、`judgment.schema.json:34-43`） |
| 判断结果进入采纳契约 | `adopt.Request` | **无** | 无 verdict/precondition 字段（`adopt.go:71-78`）；`Adopt` 只校验 schema（`:261-332`） |
| 判断 → 分支映射 → 图推进 | `judgment.schema.json`（levels/rules/precedence） | **无机器形态** | rules 的 `coverage` 是自由文本，`examples` 是字符串（`judgment.schema.json:143-172`、`:192-224`）；执行图只有 seq/par（`execution-graph.schema.json:26`） |
| 输入快照/证据充分性 | 无 | **无** | 上轮已自认“判断输入在我方全仓无 schema”；`evidence_sources` 是字符串数组（`judgment.schema.json:92-100`），`on_missing_evidence` 是字符串（`:182-184`） |
| 证据足迹对账 | `evidlog.CheckCoverage` 双向差集 | 部分 | 只覆盖“声明查过 vs 实际调过”（`evidlog.go:318-384`），不覆盖“查到的事实是否覆盖要求” |
| 纠错/当前有效性 | 无 | **无** | 状态词汇封闭（`ledger.go:33-35`、`adopt.go:57-63`）；`MarkCompleted` 终态（`:383-385`）；无 correction/notice 事件 |
| 跨修订排序/失效 | 无 | **无** | `TestT0LateStaleProposal` 明确“dispatch stale revision 在机器层合法，C4 归宿主”（`e2e_test.go:382-423`） |
| 读路径授权 | 无 | **无**（已认领） | `State()`/`Events()` 不收 grants（`adopt.go:243-250`、`:466-478`） |
| 规格正确性 | 无 | **无** | 无任何机制；且当前 fixture 与替身矛盾（见 §3.0） |

### 1.2 结论

- 对方要求的不是“另一个 R/K 场景”，而是**判断层的语义对象进入控制层**。这在架构上是一次真实的层间耦合，不是措辞问题。
- 但我方不应把它做成“控制层理解业务”。正确形态是**控制层只理解“检查的声明与结果”**，不理解“检查的内容”。这与现有设计的“语义分类非权限证明”同源（`schema/README.md` L1 漂移登记、`judgment.schema.json:5` 明说 schema 不含授权字段）。
- 对方把“框架不得因为 S1 稳定就派发”写成框架义务；我方只能承诺“框架不得在**已声明且结果为 violated** 的前置条件上派发”。差别在于“已声明、可判定、有覆盖声明”这三个限定词——这不是退缩，是把承诺写成可证伪的形式。

---

## 2. 三个反例逐个拆（带代码断言式推演）

### 2.0 先钉一个前提：承重规则本身在我方是矛盾的

对方反例 A 的成立依赖“历史任意一次 >3 个月逾期即否决”已发布。但我方仓内：

- `schema/examples/judgment/valid/judgment-spec-credit.json:45-49`：`"coverage": "any overdue longer than three months in the window denies credit regardless of assets"`——**窗口内**；`time_window` 是“six calendar months before the application timestamp”（`:21`）。
- `go/internal/e2e/e2e_test.go:39-56`：T0 替身注释与实现是**无界历史**（`historical veto ... the veto is unbounded by any window`）；注释自认“fixture's window-scoped wording is the pending P3 correction”。
- `go/internal/e2e/t1_llm_test.go:80-96`：T1 规格也是**无界历史**。
- `docs/minor-ledger.md:52`（L22）与 `:56`（L23）已登记该分歧；L23 进一步指出 C8 上 T0 替身先查缺证返回 `on_missing_evidence`，而 T1 期望 `deny`——**两个 S1 实现的优先序不同，且“exactly the semantics”的宣称失实**。

因此：对方的反例 A 若按“我方已发布夹具”判，正确结论是 grant（窗口内无逾期），不是 deny；若按“我方意图修正后的规格”判，才是 deny。**对方用了条件句“如果……已发布”，这在逻辑上成立；但它把“规格已发布且稳定”当成了背景事实，而我方实态是规格正在 P3 修正中。** 这不是替我方开脱——恰恰证明对方第 5 问“规格正确性归谁”必须排在“判断正确性”之前。

### 2.1 反例 A：证据在，S1 判错，高置信

**设定**：资产 3500 万，近 6 个月无逾期；可信材料记录两年前一次持续 4 个月的逾期；S1 稳定输出 grant。

**代码现状推演**（逐句可执行）：

1. S1 是宿主侧模型/替身，输出 `{kind:"grant-50000"}`。框架拿到的只是宿主构造的 `adopt.Request`：`Identity`、`Versions`、`PayloadDigest`、`GrantsAtDecision`、`Accountability`（`adopt.go:71-78`）。**verdict 不在请求里**。
2. `Adopt` 做 `checkRequest`（UTF-8 + adoption schema），schema 只要求身份/版本/digest/授权（`adopt.go:261-269`、`:597-612`；`schema/adoption.schema.json:8-14`）。grant 的 payload 是一个合法 digest，**schema 无法区分 grant 与 deny**。
3. `Adopt` 写入 adopted 事件，`Dispatch` 只比较 live grants 与钉照（`adopt.go:337-360`）。授权通过 → dispatched → 宿主调用业务 API → 外部效果发生。
4. 唯一可能拦住的是宿主的 if 代码；但 `TestT0HistoricalOverdueVeto` 的注释明说“HOST never dispatches a deny record”，这是**宿主纪律**，不是机器保证（`e2e_test.go:276-278`）。对一个“稳定错误的 grant”，宿主没有任何理由不派发。
5. 因此：**A 在运行时必漏**。不是概率问题，是契约里没有可供判断的字段。

**已有什么部分覆盖**：

- T1 真实 LLM 层：C2/C4/C11 把同一反例做了三重改写，C2 是 hard bar（`t1_llm_test.go:109-118`、`:35-40`）。这是**部署前模型可用性评估**，不是运行时拦截。它证明“这个模型在样例上会 deny”，不证明“生产中新案不会错”。
- T0 替身：`s1Judge` 在测试里会 deny（`e2e_test.go:52-56`），但这只是**验证框架控制语义**的替身，不进入生产。
- judgment spec 的 examples：是散文（`judgment-spec-credit.json:67-98`），无 runner，不能作为门。

**缺的到底是什么**：

- 缺一个**判断结果的一等字段**（或至少 `preconditions[]`），让闸能看见“这次采纳依赖哪些已声明检查、结果是什么”。
- 缺一个**可判定约束的执行件**：把“历史逾期 >3 个月”变成对结构化事实的纯函数，输出 `violated/satisfied/undetermined`。
- 缺一个**规格版本绑定**：`versions.rule` 目前是自由字符串，无法证明“这次判断用的是无界版还是窗口版”。

**探针（修前红/修后绿）**：

- 修前：注入 `alwaysGrant` 的 S1 替身 + 含 4 个月历史逾期的 dossier；断言 `Dispatch` 返回 `dispatched`（当前代码必然如此）→ **红**（复现缺陷）。
- 修后（A1）：同一注入下，`Adopt` 因 `precondition(historical-veto)=violated` 拒绝，或 `undetermined` 路由到补证；断言无 dispatch、无 external effect → **绿**。

### 2.2 反例 B：事实缺失，却被当作没有风险

**设定**：只拿到近 6 个月资料；S1、S2、规则校验器一致认为无逾期 → grant。

**代码现状推演**：

1. 输入侧：T0 的 `creditEvidence` 是 ad-hoc Go 结构体（`e2e_test.go:23-29`），没有版本、没有 schema、没有覆盖率字段。上轮回复已自认“判断输入在我方全仓无 schema”。
2. 证据侧：`evidlog.Declaration` 只有 `QueriedTool`/`Selector`/`ExcludedSelectors`（`evidlog.go:318-324`）；`CheckCoverage` 做的是“声明中的查询是否在日志里 / 日志中的查询是否被声明覆盖”（`:340-384`）。它检查的是**查询行为**，不是**事实覆盖**。一个诚实的 6 个月查询会得到 `OK=true`。
3. 规格侧：`conventions.evidence_sources` 是字符串数组（`judgment.schema.json:92-100`），`resolution.on_missing_evidence` 是自由文本（`:182-184`）。没有任何字段能表达“本规则要求 complete history / 窗口 / 来源权威等级”。
4. 结论：**B 在结构上不可检**。即使 S1 想输出 unknown，框架也没有“输入不充分”的机器判定；S1 输出 grant 时，闸同样看不见（同 A）。
5. 对方自己承认边界：“如果上游数据自身失真且没有可用的独立核验来源，框架无法凭空恢复真相”（原文 119 行）。这句话是对的，但它同时说明 B 的完全解决需要**来源权威契约**，不是 NGA 单方面能给的。

**已有什么部分覆盖**：

- `on_missing_evidence` 词汇与 T0 场景 2（`e2e_test.go:288-341`）证明“缺证不等于自动拒绝”这条语义已被建模；但它依赖 S1 **自己**报告缺证。稳定错误的 S1 不会报告。
- `evidlog` 的差集机制是正确形状，但对象错了：它该对账的是“事实覆盖声明 vs 事实快照”，不是“查询声明 vs 查询日志”。**同一形状可以复用，语义要换。**

**缺的到底是什么**：

- 输入快照 schema：事实 id、值、单位、来源、观测时间、覆盖窗口、来源权威声明。
- 规格中的 `required_facts[]`：每个判断问题要求哪些事实、覆盖到什么范围、closed-world 还是 open-world。
- 一个三值覆盖检查：`satisfied`（事实覆盖 ⊇ 要求且来源权威 ≥ 门槛）/ `violated`（明确缺失）/ `undetermined`（来源无法声明覆盖）。
- 一条策略：`undetermined` 不得自动转成 grant，也不得自动转成 deny；按已发布路径处理。

**探针**：

- 修前：构造 `coverage=6m` 的快照 + `required=history` 的规格；断言当前 `CheckCoverage` 返回 OK（因为它只看查询）→ **红**。
- 修后（A1）：同一输入，覆盖检查返回 `undetermined`；`Adopt` 因 required precondition 非 satisfied 而拒绝自动生效；断言进入补证/人审路径 → **绿**。

### 2.3 反例 C：首次结果错，快路径不断复用

**设定**：首次 grant 错误；之后同一业务请求重试/读取，快路径返回原回执；下游继续当作有效许可。

**代码现状推演**：

1. 快路径读面：`State(op)` 返回 `completed`（`adopt.go:243-250`）；`Adopt` 同键同载返回 `reused`（`:293-307`）；T0 断言“零模型调用、零外部调用”（`e2e_test.go:616-690`）。
2. **没有任何“纠错/失效”概念**：ledger 的 status 家族是封闭的 `{adopted,reused,conflict}`、`{dispatched,unresolved,completed,failed}`、`{rejected}`（`ledger.go:33-35`）；`MarkCompleted` 是终态（`adopt.go:383-385`、`:400-403`）；状态机没有 invalidated/superseded。
3. 跨修订：`requestFor` 用新 op 表示新 revision（`e2e_test.go:160-169`），但 op 之间只有 `business_request_id` 字符串相同，**没有排序、没有 supersession 链接**；`TestT0LateStaleProposal` 自认 C4 在宿主（`:382-423`）。
4. 因此：C 的下游读面**必然**看到“completed + 原回执”，没有任何字段能让它知道“这个结论后来被推翻了”。对方的判断成立。
5. 但要注意：**幂等接口返回原回执本身不是错**。错的是“没有关联状态查询”。对方原文也这么说（122 行）。所以修复不是改 idempotency，而是加一条旁路通知 + 读面投影。

**已有什么部分覆盖**：

- 历史不可改写：`ledger` 的 append-only 与 replay 的“按记录重演”已经保证“原记录还在”（`replay.go:15-27`、`:255-314`）。
- 新修订作为新 op：`TestT0NewEvidenceForcesRevision` 证明历史不被静默修改（`e2e_test.go:349-380`）。
- 但这些只保证“历史真实”，不保证“当前有效”。对方区分的正是这两件事（原文 126 行），我方代码只有前者。

**缺的到底是什么**：

- 追加式的 `notice`/`correction` 事件：指向原 op、记录发现依据、影响范围、责任处理状态；**不改原事件**。
- 一个有效性投影（read model）：`validity(op) = current | superseded | under-review | revoked`，由 notice 事件推导；原 `State(op)` 保持事实态不变。
- 快路径读面同时返回 `receipt + validity + linked_revision`；下游必须看到非 current 的标记。
- 跨修订排序：`business_request_id + revision_seq` 的单调比较，或者宿主侧 CAS（上一轮已认领 C4）。

**探针**：

- 修前：完成 op → 追加“发现错误”的外部记录（当前无事件可写，只能改文件/不改）→ 断言 `State(op)` 仍 `completed`、`Adopt` 仍 `reused`、读面只拿到 receipt → **红**。
- 修后（A2）：追加 correction 事件后，断言 `validity=superseded`、原事件字节不变、`replay` fidelity 仍 100%、新修订 op 可独立采纳 → **绿**。

### 2.4 三反例的共同结构

| 反例 | 缺的对象 | 缺的层 | 最小修复 | 不能修复的部分 |
|---|---|---|---|---|
| A | verdict/precondition 一等字段 | 采纳层 | `preconditions[]` + 判定执行件 | 新案上的开放语义错误（只能评估/事后） |
| B | 事实覆盖声明 | 输入层 | snapshot schema + required_facts + 三值覆盖 | 上游数据本身失真且无独立来源 |
| C | 纠错事件 + 有效性投影 | 事后层 | notice 事件族 + read model | 已发出的外部效果（只能靠业务 API 取消/补偿） |

三者不是三个独立需求，而是**同一条“声明—检查—记录—纠正”链上的三个断点**。对方的五层拆分没有把这条链画出来，所以看起来像三个新功能。

---

## 3. 五层概念拆分的批判

### 3.1 它对在哪

- 把“重试幂等”从“判断正确”里拆出来，是这轮最有价值的一刀。`adopt` 的 reused/conflict 只证明操作判重（`adopt.go:293-307`），不证明结论为真——这是事实。
- 把“执行正确性”与“业务实际结果”分开，也是对的：外部效果符合已采纳请求，不等于业务目标达成；账本只记前者（`ledger.go` 的 effect 状态），不记后者。
- 它明确拒绝“Jev 不保证正确，但框架保证 100% 正确”这种承诺（原文 43 行），这是诚实的。

### 3.2 它的三处概念滑动

**滑动一：scope-relative 与 world-relative 的正确性混用。**
表头定义“判断正确性”为“在指定语义规约、**事实范围**和参考时点下，结论是否成立”（原文 37 行）。这是 scope-relative：给定不完整事实，结论可以“正确”。但反例 B 又说“只拿到近 6 个月资料……输入覆盖仍不充分”（117 行），这是 world-relative：结论不成立。两者不能同时用同一个词。若按 scope-relative，B 不是“判断错误”，是“范围选择错误”；若按 world-relative，A 和 B 是同一类错误（事实不全导致结论错），五层表却把它们分成两行。**必须先声明：框架检查的是 scope-relative correctness；world-relative 只能由“范围声明 + 覆盖验证 + 残余风险接受”逼近。**

**滑动二：“判断一致性”被放错层。**
一致性是**跨样本的统计性质**（同一问题不同表述、不同实例是否稳定），不是单个决策的属性。运行时闸无法检查“下一次会不会一致”；它只能被评估（T1 的 C1↔C5、C2↔C4、C11 三重改写就是干这个的，`t1_llm_test.go:35-40`、`:358`）。把它与“重试幂等”并列，会误导读者以为它可以被 gate。

**滑动三：“业务实际结果”不是系统属性。**
最后发生了什么，只有外部世界/业务系统知道；NGA 能记录的是“观察到的终态”（receipt、对账结果），不是“业务目标是否达成”。把它列为一层，隐含了“系统可以判定业务结果”的承诺——这正是对方在第 2 节反对的“100% 正确”承诺的另一种形态。

### 3.3 它漏掉的层（按重要性排序）

1. **输入充分性/覆盖**：判断所依赖的事实是否覆盖了规则要求的范围。B 的真正名字。必须独立成层，因为它可以在判断之前被检查，而“判断正确性”不能。
2. **事实真实性/来源可信**：记录里的事实是否真实。对方承认“上游失真无法凭空恢复”（119 行），但没有给它一个层；没有这一层，“覆盖”会变成“覆盖了一堆假数据”的绿色。
3. **规格正确性/适用性**：规则本身对不对、是否适用于本案。对方在 §2 提到“错误规则”（43 行），但五层表没有它。没有这一层，A 的“正确”是相对于错规格的正确。我方 L23 就是活证据。
4. **授权合法性**：谁有权做这个判断/批准这个例外。对方把“授权”塞进“执行正确性”（40 行），但“正确的判断由无权者做出”与“错误参数执行” remedy 完全不同（重新授权 vs 修参数）。
5. **时效/当前有效性**：一个当时正确的结论，现在是否仍应被复用。C 的核心。它不是“业务实际结果”，是“结论的生命周期状态”。
6. **可归因性**：错误发生时能否定位到数据/规格/装配/S1/S2/分支/工具/API。对方在 §4 纠错段列了归因对象（105 行），但没有把它作为一层；没有归因，纠错只能变成“重跑”。

### 3.4 建议的替代：对象 × 认知状态 × 检查者

与其用五个互相重叠的“概念”，不如用三轴矩阵（这是最小完备形态）：

| 对象层 | 可检查的问题 | 认知状态（三值+） | 谁能检查 |
|---|---|---|---|
| 规格 | examples 是否自洽、版本是否绑定 | verified / contradicted / untested | 规格 owner + 可执行样例 |
| 事实/输入 | 覆盖是否 ⊇ 要求、来源是否权威 | covered / missing / undetermined | 事实覆盖检查（确定性） |
| 判断 | 在给定 spec+facts 下结论是否成立 | satisfied / violated / undetermined | 规则执行件（确定性）/ 评估（统计） |
| 采纳 | 身份/幂等/授权/前置条件是否满足 | pass / reject / hold | adopt 闸（结构） |
| 执行 | 参数/对象/时序/授权是否符合已采纳请求 | conform / deviate / unknown | 业务 API + 对账 |
| 结果 | 观察到什么终态 | observed / unobserved | 外部系统 + 观察者 |

这张表的好处：每一格都能回答“谁检查、检查什么、检查不了时去哪”；没有“正确性”这种跨层大词；`undetermined` 是一等状态，不是失败。

### 3.5 谁验证“输入充分性”、谁验证“规格本身正确”？

- **输入充分性**：目前**没有人**。`evidlog` 只验证查询诚实（`evidlog.go:340-384`）；`judgment.schema` 只声明证据源字符串（`:92-100`）。建议由“规格声明 required_facts + 快照声明 covered_facts + 确定性差集”三者共同验证；验证不了的部分（来源无法声明覆盖）落 `undetermined`，交管理面。
- **规格本身正确**：**没有任何机器能证明**。可行的三元组是：(a) 规格 owner/评审权（`judgment.schema.json:239-273` 已有字段，但只是字符串）；(b) 可执行 examples（把 `:192-224` 的字符串变成结构化事实 + 期望 verdict，跑 runner）；(c) 历史再评估（`replay.Reevaluate`，`replay.go:338-383`）——规格变更后，重算历史决策，量化“有多少旧结论在新规格下不成立”。(c) 不能证明新规格对，只能证明“变更的影响面”，这是诚实的上限。

---

## 4. 认知智能体战绩的迁移分析

> 结论先行：这四个（加 signature）给的是一套“**只拦可判定、未定要降级、失败要留痕、机制会腐化**”的工程纪律，不是“正确性”的解法。可移植的是形态，不可移植的是“把形态当保证”。

### 4.1 PEV（配对一致性评估）

| 机制 | 证据 | 可移植性 | 映射到本议题 |
|---|---|---|---|
| verifier 抛错/返回 null → `PerceptionUnreliable` → `AcceptPartial`，**不重试不可信判定** | `pev/docs/L1-High-Level-Design/process.md:131` | 直接可移植 | 校验器失败必须落 `undetermined`，既不能当 pass，也不能当业务 deny；这是三值逻辑的现成先例 |
| 终态四态闭集 `PASSED/ACCEPT_PARTIAL/MAX_RETRIES_EXCEEDED/INCONCLUSIVE`，永不 null | `pev/docs/features/FEAT-023-pev-selfheal-loop.md:47`、`:118` | 直接可移植 | 判断/采纳的终态也应是闭集，且 `INCONCLUSIVE` 是一等态，不是异常 |
| mock 承重 + real-LLM 软观察分层 | `pev/README.md:297-306` | 直接可移植 | 就是 T0（框架）/T1（模型）两层；不要把 T1 的读数当成框架保证 |
| `LocalReplan` 只重做 failed 节点 + feedback 注入 | `FEAT-023:41` | 可移植 | 纠错应定位到节点/检查，而不是整体重跑 |
| 不可信判定不能据以行动 | `process.md:131` | 可移植 | “模型自报 unknown”不可靠时，系统要有独立的 unknown 来源（覆盖检查/规则检查） |

**不可照搬**：`AcceptPartial` 是产品层的降级输出，不是“正确性保证”。在本议题里不能把“部分接受”说成“已验证”。

### 4.2 EDPA-alpha（确定性检查器）

| 机制 | 证据 | 可移植性 | 映射 |
|---|---|---|---|
| 分层验证：deterministic（compute）> keyword（coverage proxy）> LLM-judge（probabilistic） | `edpa-alpha/src/main/java/.../verification/GroundTruthVerifier.java:18-35` | 直接可移植 | 正是“规则 > LLM judge”；LLM 只处理开放语义 |
| `DeterministicChecker` SPI：`matches(criterion)` 声明归属 + `check` 纯函数、无副作用 | `.../verification/DeterministicChecker.java:11-24` | 直接可移植 | 前置条件也应有“归属声明”，避免重复检查和检查空白 |
| **诚实边界：当前全仓零生产 DeterministicChecker 实现（SPI 占位，等待业务接线）** | `GroundTruthVerifier.java:31-35` | 这是教训，不是机制 | 不要先建“检查器框架”再等检查器；没有具体 checkers 的闸只是空壳。先写 3-5 个真实检查（授信 veto/额度/时效），再谈框架 |
| key 词 fallback 只作 coverage proxy | `GroundTruthVerifier.java:18-22` | 可移植 | 覆盖代理不能当正确性证明 |

### 4.3 LoopForest（Veto / ReAnchor / GoalContract）

| 机制 | 证据 | 可移植性 | 映射 |
|---|---|---|---|
| 零提及纪律：拒绝消息只说“含签名外字段”，永不点名哪个字段 | `loop-forest/src/main/java/.../verification/VetoRail.java:22-36` | 条件可移植 | 对**模型可见**的拒绝消息要零提及（防提示即诱导）；对**人类审计**的 detail 必须精确。两个受众，不能混用 |
| 无契约工具 fail-open；只拦可判定的写入；非 JSON 对象不拦 | `VetoRail.java:40-48`、`VetoContract.java:39-42` | 直接可移植 | 闸只拦“有声明且可判定”的检查；无声明 = 不拦，但要记录“未覆盖” |
| 状态级拒绝配额（缺省 2）防死锁 | `loop-forest/.../FEAT-045-loop-forest-signature-forest.md` 第 2 节 | 直接可移植 | 正确性闸必须有逃生门：连续 undetermined/拒绝达到上限 → 暂停/升级，而不是永久阻塞 |
| 首次违规识别不是本机制的职责；本机制只拦“已知会坏/已发生”的重发 | `FEAT-045` 第 4 节 | 直接可移植 | 这是分工声明：确定性规则引擎负责首次判定；记忆/闸负责重复阻断 |
| 指纹域必须收窄到确定性子域；非确定数据不入指纹 | `FEAT-045` 第 4 节 | 直接可移植 | 正确性检查只对确定性事实子域做；行情/推测值不入闸 |
| ReAnchor 的教训：机制增益随模型/端点漂移；引用前先跑无机制对照 | `~/yaojun_wiki/01_Concepts/loop-forest-engineering-discipline-eight-lessons.md` + AGENTS.md 记忆 | 直接可移植（纪律） | 任何“正确性闸”上线前，先跑 A0 对照证明病存在；否则可能是在治一个已消退的病 |

**不可照搬**：ReAnchor 的 `+46pp` 是特定模型/任务/预算档的读数，不能外推为“加了闸就会更好”。同理，正确性闸的收益必须在本栈、本模型、本域重新测。

### 4.4 SmartResearch（零 LLM 判定器 + 三角色）

| 机制 | 证据 | 可移植性 | 映射 |
|---|---|---|---|
| `ReportChecker` 零 LLM：三轴 deterministic 画像（convergence/fidelity/breadth） | `smartresearch-alpha/src/main/java/.../ReportChecker.java:20-30` | 直接可移植 | 把“开放语义质量”分解为可确定性计算的代理指标；这正是“正确性”的可操作化路径 |
| verifier 角色“不添加新内容，只验证/标记”；用 web_search 核引用 | `smartresearch-alpha/docs/L1-High-Level-Design/logical-view.md` §3.2.2 | 直接可移植 | 复核者核事实、不重判结论；复核必须引入独立来源（web_search 是独立数据源，不是第二个模型） |
| writer 禁用 web_search，避免引入未验证信息 | 同上 §3.2.3 | 可移植 | 通道分离：判定者不能自己扩权去取数；取数走 S2/工具通道并留足迹 |
| 三角色管道（researcher → verifier → writer） | 同上 §2 | 可移植 | S1/S2/宿主的分工形态 |

### 4.5 signature（签名机制）

> 查找结果：`common/agents` 下无独立 `signature` 目录。代码载体在 loop-forest：`observability/BranchSignature.java`、`TraceForest.java`，以及测试树的 `WorldSignatureRail`；设计载体 `technical-af-docs/develop/02-features/FEAT-045-loop-forest-signature-forest.md`。另有一个同名但不同义的 `~/yaojun_wiki/signatures.md`（DSPy 风格签名注册表），属知识管理概念，不作为本议题机制证据。**结论：signature 不是独立认知智能体，是 loop-forest 的签名森林/世界指纹执法层。**

| 机制 | 证据 | 可移植性 | 映射 |
|---|---|---|---|
| 世界指纹 `(出发态, 动作)` 前置阻断，跳过工具执行 + 改道备忘 | `FEAT-045` 第 2、3 节 | 直接可移植 | 正确性闸的形态：在效果前，用确定性指纹判定“这个组合已知会坏” |
| 死胡同态的新动作恒直通；只拦已试过的对 | `FEAT-045` 第 2 节 | 直接可移植 | 闸不能一刀切拦截整个状态；只拦“已证明的坏组合” |
| fail-open 逃生门：状态级拒绝配额（缺省 2） | `FEAT-045` 第 2 节 | 直接可移植 | 防死锁 |
| 指纹域隔离：rejected/error 回执不入指纹域 | `FEAT-045` 第 2 节 | 直接可移植 | 闸自己的拒绝不能成为下一轮的“世界状态”，否则自我强化 |
| 实验证据（wasted ÷3~4，won 非劣；弱模型收益更大） | `FEAT-045` 第 6 节 | 条件可移植 | 说明“记忆型阻断”有效，但收益依赖模型强弱与任务族；正确性闸也要按域测 |

### 4.6 迁移总表

| 可移植（形态） | 不可照搬（结论） |
|---|---|
| 三值/多值终态（PEV） | “AcceptPartial 等于正确” |
| 确定性优先 + 归属声明（EDPA） | “有 SPI 就等于有检查器”（EDPA 零生产实现） |
| 只拦可判定 + 逃生门 + 指纹域隔离（Veto/Signature） | “闸越严越好”（会死锁/误杀） |
| 零 LLM 代理指标（SmartResearch） | “代理指标等于业务正确” |
| 独立来源核事实、复核不重判（SmartResearch） | “第二个模型等于独立来源” |
| 机制增益需同批对照（LoopForest/AGENTS.md） | “历史 +46pp 可外推” |

---

## 5. frame-bench 生态证据

> 索引方法：先读各仓 `.ra-state/REPO-MAP.md` 与 `tags`，再落到源码 `file:line`。

### 5.1 确定性规则/策略闸在 LLM 判决前后的位置

| 框架 | 机制 | 证据 | 对本案的含义 |
|---|---|---|---|
| **codex** | 执行策略（execpolicy）在命令执行**前**做确定性判定：`Allow / Prompt / PromptUser / Forbidden`；`check_multiple_with_options` 对整条命令链求值；`Forbidden` 直接拒绝，`Allow` 才跳过沙箱；托管 requirements 策略有独立层 | `codex/codex-rs/execpolicy/src/decision.rs:9-24`；`codex/codex-rs/execpolicy/src/policy.rs:301,314`；`codex/codex-rs/core/src/exec_policy.rs:415-480`；`codex/codex-rs/config/src/requirements_exec_policy.rs:1-50` | 生态最强先例：规则闸在动作前，判定是封闭枚举，且有“托管策略”层。**但它是命令前缀/沙箱域，不是开放业务语义** |
| **codex（失败面）** | 策略文件解析失败时：回退到 requirements 策略或空策略，并携带 warning；不是直接 brick | `codex/codex-rs/core/src/exec_policy.rs:671-686` | “校验器自身坏了”的生态答案：可用性优先 + 托管层兜底 + 响亮警告。不是 fail-closed 到全拒 |
| **hermes** | “质量门”：确定性 shell 命令必须 exit 0，**门在 judge 之前跑；门红则 judge 不被调用**；每次边界重跑失败门（不重放旧结果）；重试上限后暂停（转人工） | `hermes/hermes_cli/goals.py:1285-1355`；`hermes/website/docs/user-guide/features/goals.md:138-152` | 与本议题最同构：确定性证据优先于 LLM 判定；门失败不是“再判一次”，是“修或停”。**它的门是命令，不是业务规则** |
| **claude-sdk** | 权限模式封闭枚举；`permissionPrompts:'none'` 时任何要提示的调用**立即拒绝**；`canUseTool` 是宿主回调 | `claude-sdk/package/sdk.d.ts:2046-2080`、`:228` | “没有审批面就拒绝”是 fail-closed 的清晰先例；但审批面是工具级，不是语义级 |
| **agentscope** | `GoalPipeline`：executor 与 verifier 分离，verifier 默认每轮清上下文（独立性）；verifier 结构化输出失败 → 重试预算 → `RuntimeError`（fail-closed）；`impossible` 是一等结论 | `agentscope/src/agentscope/pipeline/_goal_pipeline.py:22-46,55-105,96-104,300-360` | “独立验证者 + 结构化输出 + 预算耗尽即失败”的完整形态；但 verifier 仍是 LLM，判的是“目标是否达成”，不是开放业务正确性 |
| **langgraph** | `interrupt` 暂停并从节点开头**重执行**；`Command(resume=...)` 必须有 checkpointer；多中断必须指定 id，否则 `RuntimeError` | `langgraph/libs/langgraph/langgraph/types.py:903-922`；`langgraph/libs/langgraph/langgraph/pregel/_loop.py:1021-1045` | 恢复是显式、有身份、有校验的；不是“静默重试”。对应我方的 unresolved/恢复纪律 |

### 5.2 校验器自身出错怎么办

| 框架 | 姿态 | 证据 |
|---|---|---|
| codex | 解析失败 → 回退托管策略/空策略 + warning（可用性优先，但托管层仍在） | `exec_policy.rs:671-686` |
| agentscope | verifier 输出不合法 → 重试，超预算 → 抛错（失败关闭） | `_goal_pipeline.py:300-330` |
| hermes | 门执行失败/工作区不可用 → 暂停并提示人工修（不是静默放行） | `goals.py:1307-1345` |
| claude-sdk | 无审批面 → 拒绝（失败关闭） | `sdk.d.ts:2070-2080` |
| deepseek-harness | 明确写“实验性、未审计、不得视为安全或生产可用”；沙箱不保证隔离 | `deepseek-harness/SAFETY.md:3-20` |
| pi | 明确把 prompt injection、恶意技能、本地写权限列为 out of scope | `pi/SECURITY.md:1-40` |
| EDPA（我方） | SPI 存在但零生产实现，诚实标注 | `GroundTruthVerifier.java:31-35` |

**结论**：生态没有统一的“校验器失败”答案，而是**按失败后果分级**：安全边界类 fail-closed（claude-sdk），可用性类 fail-open + 托管兜底（codex），任务完成类 fail-closed 到人工（hermes）。本议题应按“错误授权 vs 错误拒绝”的非对称代价选姿态，不能一刀切。

### 5.3 验证者环与独立判定

- agentscope 的 verifier 默认 `verifier_reset_context=True`（`_goal_pipeline.py:59-75`）——独立性靠“清上下文”，不是靠“换个模型”。
- langgraph 的 resume 校验（checkpointer + interrupt id）——恢复必须有身份，不能靠“再跑一遍”。
- PEV 的 verifier 抛错 → 不重试不可信判定（`process.md:131`）。
- SmartResearch 的 verifier 核事实、用独立来源，不重判结论（`logical-view.md` §3.2.2）。
- **没有框架做“开放语义正确性校验”。** 它们做的是：动作前策略（codex/claude）、完成门（hermes）、目标达成验证（agentscope）、人类中断（langgraph）、评估/进化（hermes-self-evolution）。
  - 这说明什么：**“开放语义正确性”在生态里被当作评估/治理/可逆性问题，不是运行时闸问题。** 若我方声称能 gate 它，就是在发明一个没有先例的机制；必须先证明其收益与误杀率。

### 5.4 知识/技能失效治理

| 框架 | 机制 | 证据 | 映射 |
|---|---|---|---|
| hermes-self-evolution | 候选变体必须通过**全部硬约束**（尺寸/增长/非空/结构）+ 全量测试套件 100% 才进入适应度评分；LLM judge 只做评分，不做门 | `hermes-self-evolution/evolution/core/constraints.py:13-45,55-95`；`fitness.py:10-70`；`config.py:38`（holdout 0.25） | 知识/方法发布：确定性约束 + 测试先于 LLM 评分；holdout 防过拟合 |
| openclaw（reef） | 审计链：`verifyReefAuditWindow` 校验头/窗口；trust store 有权威操作与投递状态 | `openclaw/extensions/reef/src/audit-state-format.ts:86`；`audit-state.ts:1-50`；`trust-store.ts:1-80` | 知识/信任治理走“可验证审计链”；对比我方账本明确声明“append-only 不是 tamper-evidence”（`adopt.go:32-35`）——这是显式范围差，不是缺陷 |
| loop-forest signature | 死胡同记忆按世界指纹阻断重复动作；配额逃生 | `FEAT-045` | 知识失效后，旧指纹仍会拦——需要按知识版本清理/失效，否则记忆会腐化 |

---

## 6. 我方真实缺口清单 vs 对方过度要求清单

### 6.1 我方真实缺口（带证据；区分“已认领”与“本轮新发现”）

| # | 缺口 | 证据 | 状态 |
|---|---|---|---|
| G1 | 判断结果/前置条件不是采纳契约的一等字段；闸语义盲 | `adopt.go:71-78`、`:261-332`；`e2e_test.go:276-278` | **本轮新发现（根因级）** |
| G2 | 规则无可执行形态：`coverage` 是自由文本，`examples` 是字符串 | `judgment.schema.json:143-172`、`:192-224` | **本轮新发现** |
| G3 | 输入快照 schema 缺失；无 required_facts / 覆盖声明 | 上轮已认领；`judgment.schema.json:92-100`、`:182-184` | 已认领，未交付 |
| G4 | 无纠错/失效事件；状态词汇封闭；无有效性投影 | `ledger.go:33-35`；`adopt.go:57-63`、`:383-385` | **本轮新发现（C 的根因）** |
| G5 | 无跨修订排序/supersession | `e2e_test.go:382-423` | 已认领（C4） |
| G6 | evidlog 只对账查询，不对账事实覆盖 | `evidlog.go:318-384` | **本轮新发现（对象错位）** |
| G7 | 规格与替身矛盾（窗口 vs 无界；C8 优先序） | `judgment-spec-credit.json:45-49`；`e2e_test.go:39-56`；`t1_llm_test.go:164-170`；`minor-ledger.md:52,56` | **本轮实证（活缺陷）** |
| G8 | 审批权/评审权只是字符串，无签名/角色/发布绑定 | `judgment.schema.json:239-273`；`adopt` 无 release_id 字段 | **本轮新发现** |
| G9 | 执行图无条件边，判断→分支映射无机器形态 | `execution-graph.schema.json:26` + `$defs.plan_node` | **本轮新发现** |
| G10 | 快路径“零外部调用”探针仍直调 `bankAPISubmit`，绕过计数 | `e2e_test.go:673` vs `:687` | 对方指出的仍在（HEAD 未修） |
| G11 | 回执未持久化、等待驱动/终态观察者未实现 | T0 存根 + `MarkCompleted` 直驱 | 已认领 |
| G12 | 读路径无授权 | `State()`/`Events()` 不收 grants | 已认领 |
| G13 | 新任务知识消费路径零代码 | compose 是纯函数授权合成 | 已认领 |

**优先级**：G1+G2+G7 是“正确性议题”的前置三件；G4 是 C 的前置；G3 是 B 的前置；其余可并行。

### 6.2 对方过度要求（附反驳论证）

> 先说明：对方大部分要求是合理的，以下只列“方向对但把 ought 写成 must、且未给可判定性边界”的部分。反驳不是拒绝，是把承诺改成可证伪形式。

| # | 对方要求 | 问题 | 我方回应 |
|---|---|---|---|
| O1 | “面对稳定错误且不自报 unknown 的 Jev，生效前由什么机制发现并处理”（Q2），隐含“所有稳定错误都可前置发现” | 不可判定：开放语义 + 不完整事实下，不存在通用前置检测器；只有可判定子集可检 | 接受“可判定约束必检”；对不可判定部分，承诺“覆盖声明 + undetermined 路由 + 事后纠错”，并逐类声明“能拦/只能降险/无法检测”。这正是对方 §2 自己的结论（43 行），Q2 的措辞比它更硬 |
| O2 | “S2 每次复核必须说清新增了什么独立依据”（72 行） | “每次”会制造表演性证据；同一材料重读不是独立依据；独立依据的成本需要计量 | 接受“复核必须声明增量来源”，但把“每次”改为“每次声称改变结论时”；并把“增量”定义为新来源/新查询/新事实，不是新措辞。用 evidlog 的差集可机检“新查询”，用 E5 实测“新信息” |
| O3 | “每个自动生效点至少应明确……谁具有最终批准权限”（92 行） | 这是发布治理字段，不是运行时组件属性；闸无法验证“谁批准”，只能验证“有没有签名/引用” | 接受为 release/manifest 字段（`release.schema.json` 已有 rollout/rollback/evidence 形态），并给 `adopt` 加 `release_id` 引用；不在闸里做“批准人”判断 |
| O4 | “校验能力本身也可能有缺陷，需要版本、测试及运营反馈”（78 行） | 方向对；但若推到底会变成“验证验证者的验证者”的无限回归 | 接受“检查器版本 + 变异测试 + 生产反馈”三件套作为停止规则；拒绝“元验证器”作为常设层 |
| O5 | “纠错……先归因，再选择改进对象”（105 行） | 归因对象九类合理；但“自动归因”会引入第二个模型及其误差 | 接受“纠错记录必须携带归因字段（人/运营填写）”；拒绝“系统自动判定根因”作为承诺 |
| O6 | “五层概念表”（33-42 行） | 不是划分（见 §3）；且“判断一致性”不可 gate | 接受为词汇表，不接受为架构分层；用 §3.4 的对象×状态×检查者矩阵替代 |
| O7 | “S2/人工复核的权限与证据增量”（Q4）要求“谁可以提出、谁可以批准、分歧如何处理、未决如何提供服务” | 这是治理流程，不是组件能力；组件只能记录角色与决策，不能决定组织权限 | 给出可记录的最小字段（proposer/approver/decision/basis/conflict-resolution），把“谁”落到 `accountability` 三元组 + release manifest；流程由管理面定 |
| O8 | “NFR 第 10 行不能整体标为全钉”（21 行） | 这条是对的，不是过度要求；我方已认领 | 已在上一轮修正为“防重复派发局部保证已有；等待/回执/恢复待宿主” |

### 6.3 对方论证里的隐藏假设（critical thinking）

| # | 隐藏假设 | 反例/反证 |
|---|---|---|
| H1 | “现有领域规则/验证方法应能发现冲突”（A 段）——假设存在一个可调用的确定性规则件 | 我方栈里没有；`judgment` 无机器、`compose` 只做授权（`judgment/check.go:1-30`、`compose.go:1-4`）。这句话把责任推给一个不存在的组件 |
| H2 | A 的“事实可核验结构化输入”与 B 的“输入覆盖不充分”可以同时成立 | 不能：A 假设完整历史可取，B 假设不可取。两者是同一约束的两种数据条件，不是两个独立反例 |
| H3 | “已发布策略”是稳定对象 | 我方 G7 证伪：fixture 与 T0/T1 不一致；策略正在 P3 修正 |
| H4 | 人工复核提供独立证据 | 只有“新来源/新事实”才独立；同一材料的人审是第二次阅读，且受同一规格误导 |
| H5 | 多模型一致提升真值 | 共享数据/规格/训练分布 → 误差相关；“一致”可能只是同一种偏差 |
| H6 | 拦截没有成本 | false block 的可用性成本、人工复核成本、延迟成本都未计入；五层表没有 FBR（错误拒绝率） |

### 6.4 我方论证里的隐藏假设（自审）

| # | 假设 | 风险 |
|---|---|---|
| S1 | “采纳闸语义盲是优点” | 在结构正确性面是优点；在本议题下是缺口。必须承认它只保证结构，不保证语义 |
| S2 | “evidlog 覆盖检查可复用到事实覆盖” | 形状可复用，语义不可：Tool+Selector 字符串身份不足以承载事实类型/窗口/来源权威；需要新声明结构 |
| S3 | “replay 可支撑纠错审计” | replay 只重放决策记录，不重判（`replay.go:15-27`）；它能证“当时为何”，不能证“现在是否仍有效” |
| S4 | “T1 全绿=模型可用” | T1 是抽样；且 t1Spec 与 T0 替身在 C8 上不一致（L23）。T1 绿只证明“这 12 个案例上对” |

---

## 7. singularity 分叉博弈（全盘采纳每个争议点的后果）

> 判定口径：全盘采纳后，问题是被“重新定义并治愈”，还是被“重新定义并制造可达坏状态”？可达坏状态是否可恢复？

| # | 争议点 | 全盘采纳后的重定义 | 可达坏状态 | 可恢复性 | 判定 |
|---|---|---|---|---|---|
| 1 | “生效前必须拦截所有稳定错误” | 采纳闸变成业务正确性 oracle | 规格 bug 或检查器 bug → 全量错误拒绝（信用线停摆）；或闸 bug 放行并盖“verified”章 → 系统性错误授权 | 规格回滚可恢复；但“已验证”章已进入账本，需纠错事件才能撤销 | **破坏性**（除非限定可判定子集 + 三值 + 已发布降级路径） |
| 2 | “两个模型/多模型同意可作为复核依据” | 一致=真值 | 相关误差 → 系统性错误授权，且“一致性”被记成证据，错误被合法化；成本 ×N | 可事后纠错，但规模化错误难回收 | **破坏性**（作为真值）；**可接受**（作为证据，需实测相关性 φ） |
| 3 | “人工复核可否决/批准一切” | 人成为最终开关 | 人无独立依据 → 橡皮图章；审计只显示“有人批准”，不显示依据；闸的保证名义化 | 可追责，但不可恢复“当时的依据” | **条件可接受**：人审必须生成新的决策记录（含依据/角色/范围），不是原地覆盖 |
| 4 | “纠错要改当前状态” | 历史可变 | replay 分叉、两个读者看到不同历史、审计不可能；这是唯一真正的不可恢复奇点 | 不可恢复（除非有原始副本） | **破坏性**；必须追加式 notice + 投影 |
| 5 | “五层拆分就是完整分层” | 正确性=判断正确性 | 检查结论而输入为空 → “verified”的错误授权；规格错误被漏掉 | 可纠错，但会长期误导建设方向 | **认识论上破坏性**；先补输入/规格层 |
| 6 | “维持现状（幂等即保证）” | 幂等=可信 | 稳定错误被持久化、可审计、可复用，看起来比实际更可信（对方 §2 的原话） | 可纠错但发现晚 | **不可接受**；对方的起点判断成立 |

**singularity 总判**：六个分叉里，唯一不可恢复的是“历史可变”（#4）。其余都可以通过“追加式记录 + 三值 + 声明范围”降为可恢复。因此本议题的设计底线是：**任何纠错/失效都不得改写既有事件；只能是新事件 + 投影。** 守住这条，系统没有可达奇点；守不住，一次纠错就会制造 replay 分叉。

---

## 8. 第一性原理

### 8.1 为什么“拦截”并不天然优于“事后纠错”

- 拦截的优势条件是：(1) 约束在效果前可判定；(2) 效果不可逆或纠正成本高；(3) 误杀成本有界且可承受。
- 拦截的劣势条件是：事实不完整（效果前信息少）、规格不稳定（判据本身在变）、误杀会停摆业务。
- 形式化：设检查点信息量 `I(t)`、效果不可逆度 `R`、误杀成本 `C_fp`、漏放成本 `C_fn`。最优检查点在 `argmax_t [P(可判定|I(t)) × C_fn − P(误判|I(t)) × C_fp]`。对授信，`R` 高、`C_fn` 高，所以“能判定就前置拦截”是对的；但 `I(t)` 在补证前很低，所以“所有判断都前置拦截”是错的。**正确形态是分层：能判定的前置，不能判定的补证/人审/事后。**
- 对方 §5 的结论（43-45 行）其实已经接近这个形式，但 Q2 的措辞把它又拉回“统一前置”。

### 8.2 校验的独立性上限由什么决定

`Independence = I_info × I_impl × I_root`

- **信息独立性**：验证者是否看到了与生产者不同的数据。共享同一份不完整快照 → 相关误差。这是 S2/S1 共享卷宗时最大的风险。
- **实现独立性**：验证者是否用不同实现/不同模型。换模型只提高这一项；若信息与规格相同，收益有限。
- **信任根独立性**：验证结论是否由生产者无法篡改的载体持有。同进程内的 attestation 由生产者填写 → 信任根不独立；只有外部权威系统（业务 API、登记库、独立账本）才提供。
- 推论：**“第二个模型”只在实现维独立；“人工复核”只在实现+信任根维可能独立（若人不看生产者材料则信息也不独立）；“业务 API 复核”在三維都可能独立，但只对其自身不变量。** 因此没有任何单一机制能覆盖全部正确性。

### 8.3 三值逻辑是被事实逼出来的，不是设计偏好

- 开放世界下，“未发现逾期” ≠ “不存在逾期”。二值闸只有两种错法：把 unknown 当 pass（fail-open，B 的错）或当 deny（fail-closed，误杀）。
- 因此闸的输出必须是 `{satisfied, violated, undetermined}`；`undetermined` 按已发布策略路由（补证/人审/有限服务/拒绝），而不是默认成任何一端。
- 这与 PEV 的 `INCONCLUSIVE`、agentscope 的 `impossible`、hermes 的“门失败→暂停”同构；生态已经在用三值/多值，只是没有把它命名为“正确性”。

### 8.4 “可检查”的三个条件

一个约束可被框架检查，当且仅当：
1. **事实可机读**：约束依赖的事实以结构化形式在快照中，且覆盖范围可知；
2. **规则可判定**：约束能表达为对事实的纯函数（无模型、无随机、无外部调用）；
3. **来源有权威**：事实来源能声明自己的覆盖与权威等级，或至少能被独立来源旁证。

三条缺一，就只能降级为 `undetermined` 或评估项。对方反例 A 在“完整历史可取”时满足三条；B 在“只有 6 个月”时不满足第 3 条；C 是事后问题，不满足“效果前”条件。这个三分法可以直接回答对方 Q2 的“哪些能确定拦住，哪些只能降低风险，哪些仍无法检测”。

### 8.5 为什么采纳闸必须保持语义盲

- 语义盲是**分层纪律**：闸只知道身份/幂等/授权/前置条件声明，不知道业务词。这样它才能跨域复用（授信/理赔/合规），不被某个域的规则污染。
- 语义盲不等于“不检查”：闸检查 `preconditions[]` 的**在场、版本、结果、覆盖声明**；它不理解 precondition 的内容，但能拒绝“required 且 violated”的采纳。这是“检查声明”与“检查语义”的分界。
- 若把业务规则放进闸：闸变成第二业务系统，规则变更要改闸，跨域复用破产，且闸的 bug 会全域放大。这是 §7 #1 的破坏性来源。

---

## 9. 系统论：正确性检查挂在哪一层、与谁耦合

### 9.1 挂载点

| 层 | 检查什么 | 谁执行 | 失败形态 | 与现有件耦合 |
|---|---|---|---|---|
| 规格层（发布前） | examples 自洽、版本/所有权、变更影响面 | 规格 owner + runner + `Reevaluate` | 规格矛盾/未测试 | `judgment.schema`、`release`、`replay.Reevaluate` |
| 输入层（判断前） | 事实覆盖 ⊇ required_facts；来源权威 | 覆盖检查（确定性） | missing / undetermined | snapshot schema、`evidlog` 差集形状 |
| 判断层（模型） | 在给定 spec+facts 下的结论 | S1（模型） | 可能稳定错 | `judgment`（目前无机器） |
| 采纳层（效果前） | 身份/幂等/授权/前置条件声明 | `adopt`（语义盲） | reject/hold | `adopt.go`、`ledger` |
| 执行层（效果） | 参数/对象/时序/授权 | 业务 API + 宿主 | deviate/unknown | 外部系统 |
| 事后层（效果后） | 是否仍有效、是否需纠正 | notice + 投影 + 人审 | superseded/revoked | 新事件族、read model、`replay` |
| 种群层（持续） | 一致性/漂移/错误率 | T1/评估管线 | 模型退化 | `t1_llm_test.go`、批跑纪律 |

### 9.2 新引入的一致性面（必须显式声明）

1. **前置条件声明 vs 实际检查**：闸只看到“声明”，看不到“算得对不对”。对策：检查器版本 + 变异测试 + 生产反馈；attestation 记为审计，不宣称保证。
2. **纠错通知 vs 原始记录**：两个真相源。对策：通知是追加事件，原记录不变；读面投影是唯一“当前有效”入口。
3. **规格版本 vs 采纳版本**：`versions.rule` 自由字符串。对策：改成 `sha256:` 内容哈希 + `question.spec_version` 绑定；`adopt` 加 `release_id`。
4. **覆盖声明 vs 查询日志**：两套对账（事实 vs 查询）。对策：同一差集形状，两个对象；不要混用一个 `CheckCoverage`。
5. **检查器版本 vs 历史判断**：检查器升级后，旧判断的“当时检查结果”不可重算。对策：attestation 里钉检查器版本；replay 只重放记录，不重算检查。

### 9.3 与幂等层/授权层/证据层的耦合关系

- 与幂等层：**正交**。幂等键仍是 `operation_id + payload_digest`；前置条件不进入幂等键（否则同一业务请求因证据补充变成新键，破坏重试语义）。前置条件进 `Versions`/`payload`，新证据 → 新 revision → 新 op，这是现有形态。
- 与授权层：**串联**。先授权准入（`compose` 的 ⊆ 判定），再前置条件；两者都通过才 dispatch。授权撤销仍由 `Dispatch` 的 live 复检兜底（`adopt.go:356-359`）。
- 与证据层：**形状复用、对象分离**。evidlog 继续管“S2 查了什么”；新的覆盖检查管“快照覆盖了什么”。两者都输出 Missing/Unaccounted/Undetermined，但日志不同、语义不同。
- 与重放层：**只读消费**。replay 不重算前置条件；它重放“当时的 attestation 与决策”。纠错通知是账本事件，replay 会重放它（fidelity），但不会重新判断它对不对（conformance 只查文法）。

---

## 10. 验证计划（用户只要计划）

> 目标：用代码 + 仿真验证“哪种方案在什么条件下有效”，并把“无效/有害”的方案也测出来。所有门槛**预注册**，跑完不改。所有真 LLM 实验标注“用户启动”。

### 10.1 方案族定义（至少三臂 + 对照）

| 臂 | 机制 | 代码面 | 预期效果 | 主要风险 |
|---|---|---|---|---|
| **A0 现状对照** | 语义盲采纳；无前置条件；无纠错 | 当前 HEAD | 复现“稳定错误必漏”；建立基线 WGR/FBR | 无（这是对照组） |
| **A1 前置可判定闸** | 宿主计算三值前置条件（satisfied/violated/undetermined）；`adopt.Request` 增 `preconditions[]`（id/version/result/coverage/attested_by）；闸只校验 required 的在场与结果；undetermined 按策略路由 | 新 schema 字段 + 检查器 + 宿主 wiring | 可判定违反的 WGR→0；undetermined 不再静默变 grant | 误杀（FBR）；检查器 bug；attestation 信任缺口 |
| **A2 追加纠错 + 有效性投影** | 新 `notice`/`correction` 事件（指向原 op、依据、影响、责任）；读面 `validity` 投影；原事件不变；快路径返回 receipt+validity | 新事件族 + read model + replay 夹具 | 纠错可见；历史不变；replay fidelity 100% | 两个真相源；下游不读 validity |
| **A3 独立复核集成** | N 个模型/agent 复判；一致/分歧作为**证据**记录；不直接作为闸；可用于 undetermined 路由 | 宿主编排 + 记录 | 若误差不相关，降低漏放；若相关，收益低 | 成本×N；相关误差被误当证据 |
| **A4 推荐组合** | A1 + A2；A3 只服务 undetermined 路由 | A1+A2+A3 的子集 | 前置拦截 + 事后纠正 + 未定分流 | 复杂度；需要分阶段验证 |

> 说明：A3 单臂不是“正确性方案”，是“证据方案”。把它作为真值开关是 §7 #2 的破坏性分叉。

### 10.2 仿真器设计（“仿真”部分）

**目的**：在写生产代码前，用参数化世界模型比较各臂的 WGR/FBR/可用性/成本，找到“什么条件下哪臂占优”，避免用单一场景下结论。

**输入参数**：
- `p_err`：S1 稳定错误率（0-30%）；
- `rho`：错误相关性（0-1；A3 两席之间的误差相关）；
- `coverage`：事实覆盖率分布（0/25/50/75/100%）；
- `closure`：closed-world / open-world；
- `decidable_ratio`：约束中可判定比例（0-100%）；
- `reviewer_acc`：人审/复核的独立检出率；
- `correction_latency`：纠错从发生到可见的步数；
- `cost_model`：每臂的 CPU/模型/token/延迟成本。

**输出**：WGR、FBR、UCR（undetermined 捕获率）、可用率、MTTD、MTTR、每案成本。

**校准**：用 E1 的真实 harness 结果校准仿真器（至少 3 个点：A0/A1/A2 的 WGR/FBR）；校准误差 >20% 则仿真结论不可用于决策。

**运行量**：每臂 × 每参数组合 10,000 案（固定种子），Monte Carlo 置信区间；先跑 A0/A1/A2，A3 用 `rho` 扫描。

### 10.3 实验设计

#### E0 疾病存在性对照（零 LLM，先做）

- **目的**：证明“稳定错误会被派发”在当前代码上真实存在，而不是纸面推演。
- **步骤**：注入 4 类 S1 替身（alwaysGrant / highConfidenceWrong / missingAsNoRisk / staleReuse）× 20 个含可判定违反的 dossier；走 A0 全链（Adopt→Dispatch→stub API）。
- **度量**：WGR（应 >0）、dispatch 次数、external effect 次数、账本事件数。
- **判定**：若 WGR=0，说明注入或链路有误（先修 harness，不得下结论）；若 WGR>0，病存在，进入 E1。
- **纪律**：按 AGENTS.md，若引用历史“机制有效”结论，先跑 3-4 发无机制对照；本实验就是该对照。

#### E1 故障注入矩阵（零 LLM，核心）

- **步骤**：6 类注入 × 40 dossier（含 10 clean、10 可判定违反、10 缺证、10 边界）× A0/A1/A2/A4。
- **注入类别**：稳定错误、高置信错误、缺证当无风险、旧结果复用、规格误读（窗口 vs 无界）、越权判断。
- **度量**：WGR、FBR、UCR、MTTD（从错误发生到第一个 flag 的事件数）、MTTR（从 flag 到 superseded 的事件数）、审计完整率、replay fidelity。
- **预期**：
  - A0：可判定违反 WGR 高；无纠错可见性。
  - A1：可判定违反 WGR=0；FBR 取决于检查器精度（预注册上限）。
  - A2：前置 WGR 不降，但 MTTD/MTTR 显著下降；历史不变。
  - A4：两者兼得。
- **判定**：预注册门槛（见 §10.4）。

#### E2 覆盖率蒙特卡洛（零 LLM，仿真）

- **步骤**：覆盖率 0-100% × closed/open × 10k 案；对每案跑规则执行件，比较“有覆盖声明”vs“无声明”的 WGR。
- **产出**：一张“可检测性边界表”——在 coverage=x 时，哪些违反必检、哪些只能降险、哪些不可检。
- **用途**：直接回答对方 Q2 的三分声明；也是 B 的定量答案。

#### E3 规格自证（零 LLM，先修 G7）

- **步骤**：
  1. 把 `judgment-spec-credit.json` 的 examples 变成结构化 `{facts, expected_verdict}`；
  2. 写 runner，跑 examples 对检查器/T0 替身/T1 规格（T1 规格可静态解析为规则）；
  3. 断言三者一致。
- **预期**：当前 **红**（窗口 vs 无界；C8 优先序）。修规格后 **绿**。
- **价值**：这是“谁验证规格”的最小机器答案；也是防止未来规格与实现再次分叉的永久探针。

#### E4 变异测试（零 LLM）

- **步骤**：对检查器做 8 类变异（删比较、反转阈值、忽略覆盖、跳过 missing、错单位、错窗口、错优先级、异常吞掉）；跑 E1/E3 套件。
- **度量**：mutation kill rate（目标 100% 对承重变异）；gate 失败模式（检查器 panic/unknown 时必须落 undetermined，不得 pass 或 business deny）。
- **价值**：证明套件非恒真（PEV 的 mutation-RED 纪律）；发现“测试绿但逻辑坏”。

#### E5 独立性实验（真 LLM，用户启动）

- **步骤**：T1 的 12 案 + 每案 3 种改写；2-3 个模型（或同模型不同温度/种子）× 3 次；记录 verdict。
- **度量**：两两误差相关 φ、翻转率、agreement-accuracy 曲线、S2 复核的“新增来源 vs 重读”检出率。
- **判定**：若 φ ≥ 0.5，A3 的“一致”几乎不增加信息，拒绝作为闸；若 φ < 0.3 且增量 WGR 降低 ≥10pp，考虑作为 undetermined 路由的证据。
- **纪律**：**用户本人启动**；智能体只准备脚本、门槛、记录模板。真 LLM 一律标注“用户启动”。

#### E6 经济学（零 LLM + 实测参数）

- **公式**：`Net(A) = ΔWGR × L − ΔFBR × C_fb − C_check − C_ops`
  - `L`：一次错误授权的期望损失（额度 × 违约率 × 回收率，业务域给）；
  - `C_fb`：一次误杀的成本（人工复核 + 延迟 + 客户体验）；
  - `C_check`：检查器 CPU/运维成本；
  - A3 另加 `(N−1) × C_model + latency`。
- **产出**：各臂的盈亏平衡表；给出“在什么 L/C_fb 比值下 A1 值得做”。
- **判定**：A1 若在合理参数域内 Net>0，进入实现；否则只做 A2（纠错）并记录“前置拦截不经济”的负结果。

### 10.4 度量与预注册门槛

| 指标 | 定义 | 预注册门槛（示例，跑前冻结） |
|---|---|---|
| WGR | 错误授权数 / 应授权数 | A1 在可判定违反集上 = 0/40；A0 应 >0（否则注入无效） |
| FBR | 误杀数 / 正确授权数 | A1 ≤ 2/40（5%）；超过则需调检查器或降级为 undetermined |
| UCR | 正确路由的 undetermined / 全部 undetermined | = 100%（不得静默 pass/deny） |
| MTTD | 错误发生到第一个 flag 的事件数 | A2 ≤ 1 个读周期；A0 无 flag |
| MTTR | flag 到 superseded 的事件数 | A2 ≤ 2 个事件（notice + revision） |
| AC | 必需 attestation/notice 字段在场率 | = 100% |
| RF | replay fidelity | = 100%（所有臂，不可协商） |
| Kill rate | 承重变异被测试杀死比例 | = 100% |

**反作弊/防静默空批**（XM2 教训）：
- 每相后断言样本数 ≥ 预注册 N；`grep -c` 事件数；env 坏 → fail loud，不得 assumeTrue skip 到 rc=0。
- 双跑一致性：同一输入两次跑，事件流逐字节一致（除时间戳）。
- 变异自证：门槛测试必须能被变异打红；否则门槛是恒真。

### 10.5 零 LLM vs 真 LLM 分工

| 实验 | 是否需真 LLM | 启动者 | 说明 |
|---|---|---|---|
| E0 疾病存在性（注入替身） | 否 | 智能体 | 纯 Go/确定性 |
| E1 故障注入矩阵 | 否 | 智能体 | 替身 + stub API |
| E2 覆盖率蒙特卡洛 | 否 | 智能体 | 仿真器 |
| E3 规格自证 | 否 | 智能体 | examples runner |
| E4 变异测试 | 否 | 智能体 | 纯代码 |
| E6 经济学 | 否（参数可业务给） | 智能体 | 公式 + 表 |
| **E5 独立性/一致性** | **是** | **用户** | 真 LLM 矩阵；智能体只准备到“万事俱备” |
| T1 回归（已有） | 是 | 用户 | 现有 12 案，用户启动 |

### 10.6 成本与收益量化口径

- **代码成本**（估）：仿真器 + harness ≈ 1.5k LOC / 3-5 天；A1 ≈ 600-900 LOC / 3-4 天；A2 ≈ 300-400 LOC / 2-3 天；E3 ≈ 200 LOC / 1 天；E4 ≈ 200 LOC / 1 天。总计零 LLM 阶段约 2 周。
- **运行成本**：A1 每案 O(facts) 确定性计算，可忽略；A2 每案 O(notices)；A3 每案 N× 模型调用（成本与延迟线性）。
- **收益口径**：WGR 降低 × 单次错误损失；FBR 上升 × 单次误杀成本；MTTD/MTTR 降低 × 错误暴露时长。业务域给 `L`/`C_fb`，技术侧只给可测的比率。
- **不可量化项**（必须声明）：审计可信度、监管可解释性、客户信任；这些不进入 ROI，但进入发布决策。

### 10.7 交付顺序建议

| 阶段 | 内容 | 产出 | 依赖 | 预计 |
|---|---|---|---|---|
| **P0** | E0 对照 + E3 规格自证（先修 G7）；冻结指标/门槛/预注册 | 病存在证明 + 规格一致性报告 | 无 | 3-5 天 |
| **P1** | A1 前置闸原型 + snapshot/precondition schema + E1 + E4 | A1 vs A0 读数；变异 kill rate | P0 | 1 周 |
| **P2** | A2 纠错事件 + 有效性投影 + replay 迁移测试 + E2 | A2 读数；覆盖率边界表 | P0 | 1 周 |
| **P3** | A4 组合 + E6 经济学 + 仿真器校准 | 推荐臂 + 盈亏平衡表 | P1/P2 | 3-5 天 |
| **P4** | E5 真 LLM 独立性（**用户启动**）+ T1 回归 | φ/一致性读数 | P1-P3 | 用户排期 |
| **P5** | 决策：A3 收/拒；更新 0.2.0 路线图；写负结果 | 决策记录 | P4 | 1 天 |

**建议**：P0 的 E3 先行，因为它同时修 G7（活缺陷）并建立“规格可执行”的永久探针；P1 的 A1 只做 3-5 个真实检查（授信 veto/额度/时效/缺证/越权），不做通用框架——这是 EDPA 零生产检查器的教训。

### 10.8 判定“方案失败”的条件（预注册）

- A1：若 FBR > 5% 或可判定违反 WGR > 0，则 A1 不成立（不是调参能救，是检查器/事实源不满足三条件）。
- A2：若 replay fidelity < 100% 或原事件字节被改，A2 不成立（设计错误）。
- A3：若 φ ≥ 0.5 或增量收益 < 成本，A3 拒绝；记录负结果，防止下一轮重复提议。
- A4：若 A1/A2 任一不成立，A4 不成立。
- 全局：若 E0 显示病不存在（WGR=0），停止本议题的机制建设，转为规格/文档修正——这是 AGENTS.md 的疾病存在性纪律。

---

## 11. 4-lens 自审

### 11.1 对对方文档

| Lens | 评分 | 依据 |
|---|---|---|
| Simplicity | 3/5 | 核心机制三句话可说完；五层表 + 三反例 + 六步纠错 + 五问有重复；概念多、机器形态少 |
| Consistency | 2/5 | scope-relative vs world-relative 滑动；一致性层不可 gate 却与运行时层并列；“必须检查”与“无法独立验证”未收口 |
| Bearing | 3.5/5 | 每个主张都有可设计的测试（A/B 注入、R/K 场景），但无阈值、无 FBR、无成本；Q2 的“发现稳定错误”不可直接落探针 |
| Fidelity | 3.5/5 | 引用 MR head、区分已确认/待实现，对 我方缺口的判断准确（回执、等待、快路径）；但假设“现有领域规则”存在，且把规格当稳定对象 |

### 11.2 对我方代码

| Lens | 评分 | 依据 |
|---|---|---|
| Simplicity | 4.5/5 | adopt/ledger/evidlog/replay 各司其职、文档诚实；judgment 是文档不是机器；没有过度机制 |
| Consistency | 3/5 | G7 活矛盾；G10 快路径探针仍越界；L23 自认；其余强 |
| Bearing | 4/5 | 测试有变异纪律、双向夹具、torn-tail 探针；但“错误 verdict 被派发”“纠错不可见”没有探针（因为能力不存在） |
| Fidelity | 4.5/5 | 包文档明确非目标（fsync、tamper-evidence、并发），这种诚实应带到协商里 |

### 11.3 本报告的证伪条件

- 若 `adopt.Request` 实际上有 verdict/precondition 字段（我漏读）→ F1 不成立。
- 若 `judgment-spec-credit` 与 T0/T1 的规则在实际运行时被某个转换层统一（我漏读）→ F2 减弱。
- 若 E5 实测多模型误差相关 φ < 0.3 且增量显著 → F3 的“相关性”结论需修正（但“独立性上限”仍成立，只是数值变好）。
- 若 A1 的 FBR 在真实数据上不可接受 → “前置拦截”在本域不经济，应退到 A2+人审。

---

## 12. 附：关键证据索引

### 12.1 festival 仓

- `/Users/yaojun/nga-impl-wt/agent-festival/go/internal/adopt/adopt.go:71-78`（Request 无 verdict/precondition）
- `.../adopt.go:261-332`（Adopt 只做 schema 校验）
- `.../adopt.go:337-360`（Dispatch 只复检 grants）
- `.../adopt.go:57-63`（状态闭集，无 invalidated）
- `.../adopt.go:383-385`、`:400-403`（MarkCompleted 终态）
- `.../adopt.go:243-250`、`:466-478`（读面无授权）
- `.../ledger/ledger.go:33-35`（status 家族封闭）
- `.../ledger/ledger.go:266-300`（转移 DAG，无 correction）
- `.../evidlog/evidlog.go:318-324`（Declaration 只有 Tool/Selector）
- `.../evidlog/evidlog.go:340-384`（CheckCoverage 是查询对账）
- `.../replay/replay.go:15-27`（决策重算 vs 观察记录）
- `.../replay/replay.go:338-383`（Reevaluate）
- `.../e2e/e2e_test.go:39-56`（T0 替身：无界 veto）
- `.../e2e/e2e_test.go:49-51`（先查缺证）
- `.../e2e/e2e_test.go:276-278`（verdict 是 opaque payload）
- `.../e2e/e2e_test.go:382-423`（C4 宿主缺口）
- `.../e2e/e2e_test.go:673`（直调 bankAPISubmit）vs `:687`（计数断言）
- `.../e2e/t1_llm_test.go:80-96`（T1 无界规格）
- `.../e2e/t1_llm_test.go:109-118`（C2）
- `.../e2e/t1_llm_test.go:164-170`（C8 期望 deny）
- `.../e2e/doc.go:1-14`（T0 层声明：框架不证模型）
- `.../schema/judgment.schema.json:92-100`（evidence_sources 字符串）
- `.../schema/judgment.schema.json:143-172`（rules：coverage 自由文本）
- `.../schema/judgment.schema.json:182-184`（on_missing_evidence 字符串）
- `.../schema/judgment.schema.json:192-224`（examples 全字符串）
- `.../schema/judgment.schema.json:239-273`（ownership 字符串）
- `.../schema/judgment.schema.json:276`（0.2.0 路线图）
- `.../schema/examples/judgment/valid/judgment-spec-credit.json:45-49`（窗口内 veto）
- `.../schema/execution-graph.schema.json:26` + `$defs.plan_node`（仅 seq/par）
- `.../schema/adoption.schema.json:8-14`（请求字段无 verdict）
- `.../docs/minor-ledger.md:52`（L22）、`:56`（L23）
- `.../schema/README.md`（L1 语义分类非权限证明；件3 无机器）

### 12.2 OpenJiuwen 认知智能体

- `~/Documents/trae_projects/agent-solution/common/agents/pev/docs/L1-High-Level-Design/process.md:131`（不可信判定不重试）
- `.../pev/docs/features/FEAT-023-pev-selfheal-loop.md:47`、`:118`（四终态闭集）
- `.../pev/README.md:297-306`（mock 承重 / real-LLM 软观察）
- `.../edpa-alpha/src/main/java/com/openjiuwen/agents/edpa/verification/GroundTruthVerifier.java:18-35`（deterministic > keyword > LLM；零生产 checker）
- `.../edpa-alpha/.../DeterministicChecker.java:11-24`（matches 归属 + 纯函数）
- `.../loop-forest/src/main/java/com/openjiuwen/agents/loopforest/verification/VetoRail.java:22-48`（零提及、fail-open、可判定才拦）
- `.../loop-forest/.../verification/VetoContract.java:39-42`（无契约 fail-open）
- `.../loop-forest/.../reanchor/ReAnchorRail.java:30-55`（B 臂、回滚、cap）
- `.../loop-forest/.../observability/BranchSignature.java`（签名森林）
- `~/Documents/trae_projects/technical-af-docs/develop/02-features/FEAT-045-loop-forest-signature-forest.md`（签名机制边界/实验）
- `.../smartresearch-alpha/src/main/java/com/openjiuwen/agents/smartresearch/ReportChecker.java:20-30`（零 LLM 三轴）
- `.../smartresearch-alpha/docs/L1-High-Level-Design/logical-view.md` §3.2.2/§3.2.3（verifier 核事实、writer 禁搜索）
- `~/yaojun/yaojun_wiki/signatures.md`（同名不同义：DSPy 签名注册表，非本议题机制）

### 12.3 frame-bench

- `~/frame-bench/codex/codex-rs/execpolicy/src/decision.rs:9-24`（Allow/Prompt/PromptUser/Forbidden）
- `.../codex/codex-rs/execpolicy/src/policy.rs:301,314`（check_multiple）
- `.../codex/codex-rs/core/src/exec_policy.rs:415-480`（decision → approval requirement）
- `.../codex/codex-rs/core/src/exec_policy.rs:671-686`（解析失败回退托管策略 + warning）
- `.../codex/codex-rs/config/src/requirements_exec_policy.rs:1-50`（托管策略）
- `.../hermes/hermes_cli/goals.py:1285-1355`（质量门先于 judge；失败重跑；重试上限暂停）
- `.../hermes/website/docs/user-guide/features/goals.md:138-152`（门是确定性命令）
- `.../claude-sdk/package/sdk.d.ts:2046-2080`（权限模式；无审批面即拒）
- `.../claude-sdk/package/sdk.d.ts:228`（canUseTool）
- `.../agentscope/src/agentscope/pipeline/_goal_pipeline.py:22-46,55-105,96-104,300-360`（独立 verifier、结构化输出、预算耗尽抛错、impossible）
- `.../langgraph/libs/langgraph/langgraph/types.py:903-922`（interrupt 重执行节点）
- `.../langgraph/libs/langgraph/langgraph/pregel/_loop.py:1021-1045`（resume 需 checkpointer；多中断需 id）
- `.../deepseek-harness/SAFETY.md:3-20`（实验性/未审计/沙箱不保证隔离）
- `.../pi/SECURITY.md:1-40`（out of scope：prompt injection、恶意技能）
- `.../hermes-self-evolution/evolution/core/constraints.py:13-45,55-95`（全约束 + 测试套件门）
- `.../hermes-self-evolution/evolution/core/fitness.py:10-70`（LLM judge 只评分）
- `.../hermes-self-evolution/evolution/core/config.py:38`（holdout 0.25）
- `.../openclaw/extensions/reef/src/audit-state-format.ts:86`（verifyReefAuditWindow）
- `.../openclaw/extensions/reef/src/audit-state.ts:1-50`（审计链头/窗口）

### 12.4 协商与裁决文本

- `/tmp/nga-new-198232012.md:29-45`（五层拆分）、`:107-126`（三反例）、`:140-146`（五问）
- `/tmp/nga-issue1-reply-d01-05.md`（我方上轮认领：输入快照、D-02/D-03/D-04、C4）
- `/tmp/nga-new-198178087.md`（Jev 输入契约、R/K 场景、交付分层）
- `~/Documents/S2-S1证据通道形态-裁决意见与实证建议-2026-11-01.md`（封存-揭示、足迹对账、受控交接）
- `~/Documents/S2-S1证据通道-第二轮裁决意见-2026-11-01.md`（质证出口、待查事项、可证伪性门槛、规格失灵三情形）

---

## 13. 结语（给发起人的一句话）

这不是“要不要加一个正确性校验器”的问题，而是“要不要把判断的语义对象接进控制层”的问题。接法只有一种是对的：**声明可检查的部分，检查它；把未定变成一等状态，路由它；把错误变成追加事件，纠正它；把不能证明的部分，写进发布范围。** 任何试图在运行时证明开放语义正确的方案，都会在第一次规格变更或第一次模型漂移时变成新的错误源。
