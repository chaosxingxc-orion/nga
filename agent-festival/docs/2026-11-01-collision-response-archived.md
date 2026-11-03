> 留档（frozen archive）：本文为 2026-10-31 发布至 NGA 仓 issue #1 的碰撞回应原文（评论 id 197351704），发布前五处外部证据（codex/openclaw/claude-sdk/langgraph/hermes）已经实证校验。留档不改写内容；不作为现行行为权威——现行裁决以 schema/README.md 的漂移登记与本仓提交史为准。

# 对《NGA Architecture and Minimum Java SDK Proposal》的碰撞回应

> festival 侧深度讨论稿（2026-11-01）。方法：以 07 提案+总体设计新文+MR !1 点评为语料，用 4-lens、singularity、第一性原理、系统论/系统动力学，与 frame-bench 生态 15 个真实框架样本（langgraph/claude-sdk/codex/agentscope/hermes 系/openclaw 等）和 agent-festival 全部实现与过程史（六 schema、Go 六件战役、95 夹具、30+ 笔验证循环提交）做了三方碰撞；关键断言均带双侧证据，festival 机器行为经活体复现验证。本文的目的不是评审，是碰撞：我们同意什么、不同意什么、为什么、以及建议怎么走——批判的部分请当作同行之间的坦诚，所有的批判都指向同一个方向：对任务好（简洁、可演进、深刻）。

---

## 一、先承认对的：语义收敛是真实的，且我们已经用机器验证过

07 提案对 festival 核心控制面语义的吸收是逐句级的事实，不是礼节性认可。我们做了三层验证：文本对照（旧 12/13/14/15 号 → 新 02/03 落位）、词汇互译（件0 三层身份 ↔ T1/J1-D1/B1 逐字段可无损映射：T1→business_request、J1/D1→evaluation_revision、B1→operation_id+payload）、活体复现（festival 采纳闸在四反例、同键异载拒收、撤销钉照复核上的机器行为与 07 的 prose 一致）。

我们认同并特别欣赏的四处：

1. **幂等键语义的超集推广**。07 把「same command identity + unchanged material content resolves the original receipt; changed content does not silently replace it」从 festival 的采纳闸一处推广到了一切 mutating command，并补上了我们没有的「A client key alone gives no server guarantee」——这一句把外部效果幂等的责任边界划到了 provider 契约，与我们先验中「外部资源侧幂等真保证出界」的裁定独立同构。
2. **14-A4 的加码**：`validate the final normalized payload and current authority after all permitted Rail/tool transformations`——「转换后复检最终载荷」是我们没做到位的强化（M06 的 Rail 改写金额夹具是好设计）。
3. **四回放模式表**逐行保留了旧 12 号的四操作分离，且「Faithfully replaying a past error can pass historical fidelity while failing business-contract conformance」把保真/合规双裁决写成了验收命题。
4. **诚实纪律**：trusted-host 假设须声明、model-readiness 单独设门、单进程剖面自限——这三处诚实在我们扫过的 agent 框架生态里没有先例。

还有一个观察想说给你：NGA 研究侧的作战纪律（Astra 只读审查、detached 容器、逐 receipt 哈希、预注册、带日期勘误）**就是这套架构主张的手工人类版**。架构=你们研究运维的形式化——这个自举环是整个系统最优雅的部分，也是我们相信这次合并值得认真做的原因。

但正因为认真做，下面的批判也请认真读。

## 二、合并损耗：五处系统性发现，以及一个方法论警告

07 合并旧文档的动作造成了一批语义损耗。它们不是观点分歧，是「旧文有明确语义、新文找不到对应句」的客观缺口。我们逐处 grep 复核过，列出证据与利害：

**L1｜「A semantic classification must not be treated as proof of authority」整句消失。**
旧总设计 §6 原文，新 02/03 零命中（最近义句 02 §5「No invented business conventions」是不同命题：框架不发明约定 ≠ 分类不构成授权）。这句的利害不在纸面：**生态里已经出现了它警告的滑坡**——codex 生产代码消费 MCP 的 `readOnlyHint` 做免批决策（codex-rs core/src/mcp_tool_call.rs `requires_mcp_tool_approval`：`read_only_hint == true → 不需审批`），而 MCP 规范文本明确说 hints 非保证。规范与工程实践已经分叉；这一句是防止「hint 当权杖」的锚，删了它，「Imported implementations may add industry-specific states/events」这类开放条款就没有对应的制衡句。festival 侧已把这句话编译成机器行为（judgment schema 全线零授权字段、`authority_hint` 字段被 additionalProperties 拒收——我们活体验证过拒绝报文）。建议：在 07 §5 或 §8 恢复该句，并在 §9 开放条款旁引用它。

**L2｜判断规格从架构一等对象降级为研究词汇，owner 责任族整族消失。**
旧 §6/§6.1 的「Business judgment specification」对象（含 owner/review_authority/effective_scope/change_rationale/links to impacted tasks,datasets,decisions）在新文中降为 03 §5 的研究词汇+02 §12.3 的待决事项；**owner 族五个字段在新文档无落位句**。第一性原理：决策治理的可问责性最终落在「谁对这个语义负责、生效范围是什么」——owner 责任族消失后，「语义灰区归知识工程治理」就成了一句没有落点的原则。festival 件3 已把该字段族机器化（20 字段逐条注出处），愿意提供对照。建议：owner 责任族在 07 §6 对象表或 §9 知识工程边界处恢复具名。

**L3｜P5 五维与 J1/D1 四维自相矛盾（同日两文）。**
03 P5 说「evidence, semantic, model, readout and decision-policy versions」五维；02 §6 J1/D1 实际只列四维（specification/model/readout/policy），evidence 从版本字段降为「normalized facts/provenance」的事实属性。这不是措辞问题：evidence 到底是版本维度（可钉照、可比对）还是事实属性（随事实走），直接决定账本与重放匹配键的字段形态。festival 件4 按五维实现且必填——现在比自己的出处更严。建议：在 07 §12 剩余决策里显式裁决这一维，而不是让两文并存。

**L4｜rollout 三选一从封闭枚举退化为开放散文。**
旧 v0.2 §5 的三个具名 in-flight 选择（complete-under-pinned-definitions / explicit-state-migration / hold-and-revise）在 07 §6 变成「preserve versions or admit a hold/migration/reevaluation」——第四个词（reevaluation）是新增且未定义的路径。枚举变散文的代价：验收无法枚举穷尽、实现各自解释。festival 件5 用三值封闭枚举+「杜撰第四模式必须拒绝」的负例夹具钉住了这个面。建议：恢复具名枚举；若确需第四路径，走显式版本修订而不是散文引入。

**L5｜「重放不重新仲裁」的机器语义未落位。**
旧 12 号 §3 步骤 6 明确「重放按记录序重演竞争、**不重新仲裁**」；新 §8 重放表只说「compare transitions and intents」。recorded arbitration order 在保留清单里活着，但它的消费语义（重放时序=仲裁序的重演，而非再次裁决）没了出处。这决定重放器的核心行为，建议在 §8 四模式表补一句。

**方法论警告**：这五处呈现同一个模式——**旧文枚举 → 新文散文处，必有损耗**。我们建议双方共同建立一张「出处映射表」（旧 12/13/14/15 号 §节 → 07 §节），作为下一次文档合并的语义保全检查清单。festival 五份 schema 的 provenance 注释当前全部指向已删文档，我们会在自己侧完成重锚；这张映射表可以双方共用。

## 三、架构批判：按简洁性 / 可演进性 / 深刻性三轴

### 简洁性（我们的批判最集中的一轴）

**C1｜双账本+对账协议：自造的失败类，且轻路径未评估。**
07 §7 要求引擎 checkpoint 与 NGA 权威记录「explicit reconciliation protocol; do not assume two independent writes are atomic」——这为系统新增了一个失败类（checkpoint/账本分歧），而它源自一个未评估的设计选择：**让 NGA 账本直接实现 openJiuwen Checkpointer 接口、二合一为单一真源**。生态证据：langgraph 的 checkpointer 本身就是权威状态（thread_id 为主键、写去重在存储层完成）；claude-sdk/codex 均单一会话记录。没有任何框架维持「引擎状态+业务账本」两份需对账的权威写。企业审计要求业务记录不随引擎 checkpoint 格式报废是真实约束（这是双写的可辩护起点），但「合一到账本、把 checkpoint 变成账本的投影」同样满足该约束且少一个一致性面。同时 §9 复用表自认 openJiuwen CheckpointerFactory fallback 是 in-memory——「reuse first」之下实际可复用的持久化底座目前为零。建议：在 §12 决策 2 里把「账本实现 Checkpointer 接口」列为被评估并否决的选项（若否决，给出理由）；若未评估，请评估。

**C2｜中央「Decision and transition coordinator」逐条准入的重量。**
方向上我们同意你（见第四节的裁定），但重量上要指出：生态的主流是「结构即控制+效果边界单点闸」——langgraph 的图结构预先声明合法迁移、运行时机械推进；准入只发生在工具/exec 边界（codex exec_policy、claude canUseTool、agentscope PermissionEngine）。07 把准入门设在「判断采纳」层，比生态重一个数量级，而它对「依据未变判断漂移」这一声称失败的边际贡献未被论证——那个失败的真正解在模型侧一致性（你们自己的 M02 与研究侧）与独立评估，准入协调器防的是任务内翻转与无据修订（审计价值），不防跨任务不一致。建议：在 07 里把 coordinator 的威胁模型写清楚（它防什么、不防什么），并评估「效果边界单点闸+采纳回执」这个更轻的等价物——coordinator 的不可替代面可能只剩「审计谁在何时让什么生效」，而那是账本就能承载的。

**C3｜CASE1/进化回路进首版验收门（M15）是范围膨胀。**
生态证据：进化回路在成熟体系里全部外置于运行时——hermes-self-evolution 是独立仓，最优变体提 PR 由人合并（同样守住「optimizer cannot publish its own change」）；openclaw 把变更纪律写成贡献规则。07 §12 自己把 lifecycle 放在 increment 3，§11 却要求首版全过 M01-M15——两节自相矛盾。建议：M15 移出首版门；CASE1 在首版只保留「记录症状与证据」的写入面，进化环（candidate→evaluation→activation）到 increment 3 再验收。

**C4｜「expected relevant generation」语义未闭合。**
02 §3 要求每条 mutating command 携带期望代，但：代属哪个对象（ACT1 的 activation 代？T1 的 state generation？）、CAS 读-改-写边界、**首见命令的期望值从何而来**均未定义。单进程剖面（§2 自限）下，festival 的仲裁序+幂等键已覆盖并发与重复；generation 的增量价值目前只有 M05 的代冲突静默迁移防护——按第一性原理（「没必要但没伤害也必须不做」），它是加法候选。建议：要么补全语义（属主/边界/初值），要么在 §12 列为显式待决而非直接进入契约。

**C5｜概念量与「最小 SDK」的张力。**
7 对象+7 交接族+6 原语族+6 契约区+4 重放模式+12 格矩阵+6 端口族+15 验收门，对「三个 Java 工件」的首发是重装备。你在点评里说「保留对概念膨胀的警惕」，我们建议把这个警惕制度化：每个概念标注「首版必需 / increment N / 文档视角」三档——12 格矩阵就是第一个候选（它目前无 API 映射表，行为上更像文档视角而非 SDK 面）。

### 可演进性

**E1｜开放行业词汇 vs 封闭核心枚举。**
07 §9「Imported implementations may add industry-specific states/events」与我们账本的封闭 status 枚举正面冲突。我们的立场（愿意辩护）：封闭枚举是证据轨的纪律而非缺陷——扩展经 schema 版本代次（0.1.0→0.2.0）而非运行时词汇生长，否则八族跨事件规则的机器验证面会被开放词汇击穿。可兼容方案：核心事件流保持封闭，行业扩展态走独立命名空间/独立账本文件（保持 identity/authority/evidence 规则继承）。这一点需要你裁决，我们不默认对方接受我们的裁法。

**E2｜「维护一份现行提案」的文档纪律，恰是这次损耗的发生器。**
单提案原地维护+删除编号稿，优点我们完全认同（两个体系在「如何持有真理」上其实先于「真理内容」收敛了——单一真源纪律同构）；但这次合并证明：**文档合并 ≠ 语义保全**，原地维护让损耗不可追溯（git 历史有，但读者看不到映射）。第二节的出处映射表就是为此而生——单提案政策与语义可追溯可以并存。

**E3｜三套状态词汇的分层需要显式声明。**
命令结果族（7 态含 rejected/committed/pending）、提供者完成族（5 态）、效果生命周期族（adopted→dispatched→unresolved→completed/failed）——层次本身有理，但合并处会撞车：festival 账本明确拒绝 rejected 入账（机器答案词汇永不入账本——账本只记事实；reused≈duplicate、adopted≈committed 的映射也要说清）。建议 07 §3 加一段词汇分层声明（哪层是 API 返回态、哪层是持久事实态），并回答一个具体问题：**rejected 是否持久化**？若只是内存返回值则无冲突。

### 深刻性（这一轴我们的批判指向诚实，包括对我们自己）

**D1｜语义轴的承诺-现实断层，请保持它可见。**
07 §11 自认「architecture analysis assumes the required Jev capability」，研究侧现实是：paired-consistency 协议尚缺预注册等价类与 decision-level paired protocol，两条组合 blocked 在数值准入链上（E36→E41，卡在 0.0141 量级的批组成概率差）。**整个架构的语义轴目前压在零直接证据的能力假设上**。我们对其中最难的部分持双向皆疑而非过错判定：预注册纪律（不按 gold 选 batch/温度）是你们自己的立法，放宽即违宪——但为 0.014 的参考模型差异打五场战役的机会成本也真实存在。我们建议的不是放宽，而是**显式降级声明**：双打过 M02 的 SDK 不得宣称支持 semantic-branch 生产用途——防止「架构全绿」被误读为「能力就绪」（你们的「Model readiness is a separate gate」已经是这句话的种子，补上反向护栏就闭合了）。

**D2｜构件合并 vs 文本合流的僵局，需要被摆上桌面。**
你的应答序是「先对齐理念，再共同修订一份提案，随后讨论工程承接」；我们的路径是机器件+台账裁决先行。坦白说：**你点评里的六问，我们一条都还没答**——双方目前各持一种合并观在平行推进。我们不想假装这不是僵局。第三节的提议是我们提出的破局路径，但合流方式本身（festival 六件 schema 进 07 §12.4「Public schemas」槽位？夹具基准先行的双轨？）需要你裁决，我们不预设答案。

## 四、与生态的关系：三份证据清单（frame-bench 15 样本实测）

**真空白填充（生态零覆盖，NGA+festival 共同资产）**：外部效果的操作幂等（15 样本 grep 零命中框架侧幂等层；langgraph thread_id 是 checkpoint 身份非效果幂等）；cancel/compensate 的请求-确认分离（生态的 cancel 全是本地循环控制权）；记录级可执行重放（生态的重放=状态恢复再续跑，langgraph time-travel 是基石但模型是活调用）。

**NGA 能反向输出给生态的一处**：**最终载荷权限**。M06/§7 的「转换后复检最终载荷与授权」vs claude-sdk `canUseTool` 返回 `{behavior:'allow', updatedInput}` ——生态的权限回调自己就是改参点、改后无复检环节（sdk.d.ts `canUseTool` 的 allow 分支返回 `{behavior:'allow', updatedInput}`，L2494-2506）——post-check 变异窗口。这是 07 里少数领先于整个生态的设计点，值得单独写清楚。

**正面收敛（生态先例，双方方向都对）**：活撤销不因版本钉照失效——openclaw 的句式与 14-A4 几乎逐字相同（"source-policy changes revoke the owning authority"）；进化护栏——hermes「No mid-conversation changes」正是 pinned-definitions 的玩具版；夹具即规范——langgraph 自己有 checkpoint-conformance，与我们 95 夹具+你们的 M 门三方独立收敛；HITL 门、权限模式族、诚实威胁模型（deepseek-harness SAFETY.md）各有对应。

## 五、建设性提议（五条，全部可操作）

1. **95 夹具升格为跨语言 conformance 基准。**Java SDK 跑同一批 JSON 夹具（festival 的 Python/Go 双 oracle lockstep 已验证该模式 17+5 轮）。这是语言双轨下防止语义分叉的**唯一硬机制**——两套实现各自测试全绿不构成收敛证据。我们愿意提供夹具格式说明与 oracle 参考实现。
2. **共同建立出处映射表**（旧 12/13/14/15 号 §节 → 07 §节），作为文档纪律的语义保全检查清单；festival 侧同步完成五份 schema 的 provenance 重锚。
3. **恢复三处具名**：L1 的制衡句、L2 的 owner 责任族、L5 的「不重新仲裁」——以及裁决 L3（evidence 第几维）与 L4（rollout 枚举）。
4. **replay 机器形态分工**：四操作分离我们可以在 Java 实现成型前给出 canonical 机器形态（festival 件6，出处已齐）——避免该语义的第一次实现成为事实标准却无人验证。是否需要、以什么形态交付，请你定。
5. **回复你的六问。**你说先对齐理念——我们接受这个应答序。本文就是第一份对齐材料；六问的正式回复我们随后给出，其中「Public schemas 槽位」的收编方式（§12.4）是我们最希望先谈的一题。

## 结语

这次碰撞给我们的最大教训是「文档合并≠语义保全」；给双方的最大确认是：**同一个语义体系已经在两种介质里独立结晶了两次**（你的 Java 提案+M 门，我们的 Go 状态机+封闭 schema+95 夹具），且词汇可逐字段互译。奇点其实已经存在，只是双方都没有宣布它。接下来的问题不是谁采纳谁，而是给这个已经存在的奇点一个双方共同持有的形态——夹具基准+出处映射+词汇分层，是我们能想到的最少约定。

批判的部分若有过重，请以证据反驳我们——那正是碰撞的目的。
