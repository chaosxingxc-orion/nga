# schema/

L3 capability contract 的机器形态。设计依据见 [ADR-0001](../docs/adr/0001-l3-capability-contract-minimal-schema.md)。

| 文件 | 作用 |
|---|---|
| `capability-contract.schema.json` | 契约 0.1.0：四段 provides / requires / effects / bounds，资源-动作-副作用矩阵，机器判定硬闸 |
| `contract-envelope.schema.json` | 信封 0.1.0：`{envelope_version, contract, contract_hash, signatures[]}`；签名对象逐字复用 A2A 1.0 AgentCardSignature |
| `execution-graph.schema.json` | 执行图 0.1.0：`{nodes, edges, plan, caller_holds, parent_bounds}` 的文法（`plan` 是 seq / par 树，组非空且只含一种模式）；形状规则（节点全部入 plan、供给边顺序与 plan 一致、delegate 目标在图内）由 compose.py 强制 |
| `rfc8785_min.py` | 最小 RFC 8785 规范化（ES6 数字格式、UTF-16 键序、拒绝非有限数），签名与哈希的输入。模块名刻意不叫 `jcs`：PyPI 有同名包，脚本用 `sys.path.insert(0, …)` 会遮蔽它（code-rules G.PSL.03） |
| `validate.py` | 校验器：契约 schema + 跨字段规则（含 selector 规范编码形态：大写两位十六进制、不编码非保留字符、转义可按 UTF-8 解码；任何环节不解码 selector，D40；`NaN` / `Infinity` 在解析层拒绝）；信封哈希重算 + 每条签名 JWS 验签 + 可信密钥库（`subject_of` 签名人-主体绑定：至少一条 owner 签名，绑定 kid 不得为他人签；JWK 的 `use` / `key_ops` / `alg` 与保护头对账；`crit` 拒绝；同 kid 只算一条背书；重复 kid / 无 kid 的密钥库拒绝加载） |
| `sign.py` | 用临时密钥重新生成信封样例与密钥库；无效样例由有效样例程序化变异得出 |
| `examples/valid`, `examples/invalid` | 契约样例：7 必须通过 / 23 必须拒绝 |
| `examples/envelopes/valid`, `examples/envelopes/invalid` | 信封样例：4 必须通过（带 `_expect_verified_kids`）/ 16 必须拒绝 |
| `examples/compose/valid`, `examples/compose/invalid` | 执行图样例（含 NGA §10 A001 credit-slice 1+4）：10 必须通过（带 `_expect_composed`：effects、bounds、逐原子 requires、并行时每个叶子签发到的 shares）+ 36 必须拒绝（未持有 / 提权 / 多动作 / 无边的 upstream / 幻影 upstream / upstream 动作提权 / upstream 副作用提权 / 链上多重假声明 / 并行超份额 / 切分舍入边界 / 串行超时 / 节点违契约闸 / 孤儿节点 / 重复调度 / 空组 / 双模式组 / 并行兄弟供给边 / 反向供给边 / 多币种 / 父预算单位不符 / 求和不精确 / delegate 到图外 / caller_holds 非规范转义·编码非保留·非 UTF-8 / 父预算 Infinity / 60 位计数切分不可整除） |
| `event-ledger.schema.json` | 账本 0.1.0（增长层件4，NGA 供件）：adoption/effect 事件文法——三层业务身份 + P5 五维版本 + idempotency（operation_id+payload_digest）+ grants_at_decision（只骑 adoption 事件且 adopted 必带、if/then 钉死）+ outcome 必填 + D31 责任三元组；跨事件规则八族（以 ledger.Errors docstring 枚举为准源：seq 严格递增+int64 域+整数字面量门（R16 数值域章程：浮点语法一律拒） / 同 op 单 digest / idempotency 在场性双向=非 conflict 必带且 conflict 禁带 / idem↔identity 键耦合 / status 家族不越界 / 钉照只骑 adopted / effect 归因=adopted 钉照 / 单写者文法=每 op 恰一 adopted 开头+转移序镜像机器 DAG；查序不查密度为明示裁定；载入侧行级 UTF-8 拒收在机器侧）在 ledger.py 与 go/internal/ledger 双侧镜像；status 词汇与 grant/identity/versions/accountability/payload_digest 五共享原子各有双侧 lockstep 直比 |
| `ledger.py` | 账本 oracle：schema + 跨事件规则八族双侧镜像（同 ledger.Errors docstring 枚举，含 idempotency 在场性双向与 effect 归因一致），与 Go 侧（go run ./cmd/ledger）双验证器交叉；附 status+五共享原子 lockstep 直比（剥 description 递归比语义子树）+ D93 计数钉 |
| `release.schema.json` | 发布清单 0.1.0（增长层件5，NGA 供件）：NGA v0.2 §5 版本连续性链接的机器形态——release_id/agent_identity（链接链两端）/references 十类具名引用（模型·读出·语义·采纳四核心钉 minItems 1 + 能力·工作流·图·上下文·控制器·执行六类 relevant-only 可空——仅引用非部署单元，字段形状即声明）/rollout 双决策（新任务策略+in-flight 三选一封闭枚举：complete-under-pinned-definitions·explicit-state-migration·hold-and-revise——字面 token）/rollback 三通道（新工作路由+活跃工作处置+外效果纠正契约——确认的登记不可撤销）/evidence 三分离（版本兼容·策略符合·业务改善——技术兼容≠业务验收）；§5 系统不变量（撤销优先于钉版等）记 description、机制落在件2 闸与件6 replay |
| `release.py` | 发布清单 oracle：schema 校验，与 Go 侧（go run ./cmd/release）交叉 + D93 计数钉（版本 lockstep 三方钉住在 go/internal/release/release_test.go） ；件5 无机器无跨文档规则——任务记录/晋升/replay 属消费方（件6 只读） |
| `replay-case.schema.json` | 重放用例 0.1.0（增长层件6，NGA 供件）：输入/记录分离——steps（驱动生产状态机的调用序列，记录族输入内嵌）与 recorded_events（账本事件流）两栏；expected 钉 fidelity×conformance 双裁决组合（四象限皆合法，四象限全有夹具钉（match+pass×3/divergence+pass×3/divergence+fail×1——recorded-violation-forks：终态复活违规真机不可复现/match+fail×1——unknown-field-in-record：typed 字段全等+走私属性，兼作 raw 视图判定的回归钉））+divergence_at 定位钉；机器操作集枚举封闭（不可坍缩为一个泛化调用，无计数措辞——op 集演化不漂移）；Python oracle 只做格式面（schema-as-source + R16 数值字面量门——章程来源的格式规则；行为判断在 Python 侧出现即第二实现走私——Go 单侧诚实边界） |
| `replay.py` | 重放用例 oracle：格式面校验（replay-case.schema.json 驱动 + R16 数值字面量门）+ D93 计数钉；行为面=go run ./cmd/replay（internal/replay 四入口：Inspect 投影族/Replay·Reevaluate 生产机重执行族/Recover 恢复到可派发不派发） |
| `judgment.schema.json` | 判断规格 0.1.0（增长层件3，NGA 供件）：§6/§6.1 具名信息逐字段映射——问题身份+版本（不可分）/术语+单位+证据源+参考时+窗口约定（§6.1 五项全）/等级名+定义+类型（boolean·nominal·ordinal）/候选集语义（exclusive·stackable，裸枚举）/优先序（良序整数无下界）+覆盖+例外/输出态与许可动作（缺证据/未定义规则不自动否定——§6.1）/示例四类（边界·等价·竞争·未解）/适用范围/owner+评审权+生效范围+变更理由+受影响链接+规格版本（§6.1 尾项含 version——schema 的 judgment_version 与 question.spec_version 分承）；无 rule_id（无 NGA 出处零消费——第一性原理删除）；语义分类非权限证明——schema 不含任何授权字段；闭环契约 additionalProperties:false 封死 authority_hint 类旁路 |
| `judgment.py` | 判断规格 oracle：schema 校验，与 Go 侧（go run ./cmd/judgment）交叉 + D93 计数钉；件3 无机器无跨文档规则——语义所有权归知识工作流（先验边界） |
| `adoption.schema.json` | 采纳契约 0.1.0（增长层件2，NGA 供件）：请求=三层身份+P5 版本+payload_digest（JCS-sha256 同基座形制）+grants_at_decision（14-A4 派发时复核的授权钉照）；闭环契约 additionalProperties:false |
| `adoption.py` | 采纳请求 oracle：schema 校验，与 Go 侧（go run ./cmd/adopt）交叉；状态机语义（单写者/14-A5 四反例/崩溃耐久）在 go/internal/adopt 测试所有权 |
| `evidlog.schema.json` | 取证记录族 0.1.0（件7 spike，夏裁决落地）：S2 调查的授权工具调用 append-only 日志——封存件完整性声明的机器旁证（声明「查过银行流水」→ 本日志必有对应调用记录；差集告警）；带内 writer 分配 seq（密度=覆盖是纯函数，codex rollout 形态）；与件4 事件账本刻意两原子两日志（词义碰撞的分离解——夏裁决 §2）；夹具样例：1 必须通过 / 6 必须拒绝 |
| `compose.py` | 执行图合成 oracle：图文法+requires(G) 原子推导+预算切分与衰减判定+程序化守卫双套（NaN parent_bounds 拒绝/shares 无 parent_bounds 大声失败），与 Go 侧（go run ./cmd/compose）交叉 + D93 计数钉；金额按整数语义（数值域章程 v2 待裁登记面） |
| `evidlog.py` | 取证日志 oracle：schema+密度规则+R16 数值字面量门双侧镜像，与 Go 侧（go run ./cmd/evidlog）交叉 + D93 计数钉；件7 是 spike——S2 集成属对方半场，仓内只供日志原子与覆盖检查 |
| `_suite.py` | Python 侧共享夹具 harness（非 oracle）：镜像 go/internal/suite 的两相套件纪律与 V28 F-1/V32 M-1 pin 硬化，ledger/adoption/judgment/release/replay/compose/evidlog 七 oracle 复用（R13 B-m2 rebase：evidlog 入族后「五」已陈）；checker 各自独立实现以保交叉验证 |
| `examples/ledger/valid`, `examples/ledger/invalid` | 账本样例：8 必须通过（高 seq 跨 2^53 合法链 + DAG 三条链——纯整数字面量） / 28 必须拒绝（合法侧同上；拒绝侧：浮点语法 seq 三形态（整值域内 0.0/2^53 相邻偶孪生 ..992.0/超域大数——R16 数值域章程后一律字面量门拒） / 旁路直写两形态 / 孤儿 reused / 双 adopted / status 家族越界 / effect 携 grant 钉照 / adopted 无钉照 / 事件侧 grant 形状违规 / digest 形状 / 缺版本 / 缺 outcome / seq 逆序 / 2^53 相邻 seq 序坏钉 / int64 溢出钉 / idem-identity 键错位 / 转移序三形态：completed 无 dispatched 前驱 + 终态后再生 + unresolved 后再 dispatched / 终态复活 / re-unresolved / reused 携钉照 / idem 缺席两形态（adopted/effect）/ conflict 反向携 idem / effect 归因偏离钉照） |
| `examples/release/valid`, `examples/release/invalid` | 发布清单样例：3 必须通过（credit 试点第二发布全字段+hold 变体——rollout 三 token 各有正例/最小形态——六类 relevant-only 合法空+首次发布的业务改善证据声明）+ 14 必须拒绝（五段缺席钉：rollout/release_id——链接链自有链/agent_identity——链头/rollback——三通道/evidence——三分离/缺 in-flight 决策/杜撰第四模式/缺外效果纠正契约/空核心钉/缺证据维度/auto_approve 根旁路/缺 references/空 release_id/references 内嵌走私——嵌套旁路类代表） |
| `examples/replay/valid`, `examples/replay/invalid` | 重放用例样例：8 必须通过（五族可证伪：篡改结论/输入变异定位/意外参数拒配/竞速两结局/divergence+fail 象限/match+fail 象限+raw 判回归钉/正常链 control）+ 9 必须拒绝（杜撰 op/负 divergence_at/缺 conformance 钉/case 文档未知字段/divergence 不带定位/match 带定位/case_version 错值——const 语义臂钉/divergence_at 浮点语法——R16 字面量门/divergence_at 超 int64——R16 内环 M2 bignum 孪生钉） |
| `examples/judgment/valid`, `examples/judgment/invalid` | 判断规格样例：2 必须通过（NGA §6 credit 示例全字段+§6.1 全部点名缺口含双截断与带间区间/最小形态含 nominal+ordinal+change_rationale 词汇正例）+ 19 必须拒绝（九段缺席负钉：§6 具名信息段+judgment_version 外全部 root 段逐段有钉——resolution/question/rules/scope/ownership/conventions/levels/candidate_set/examples；四类代表钉（每类至少一枚，嵌套 required 与 minItems 各实为两钉——类内第二钉为 R1 期旧夹具归位）：嵌套 required（question_id+evidence_sources 缺席）/minLength（terms/0/name）/minItems（levels+terms 空数组）/嵌套 additionalProperties（ownership 内 authority_hint）；值域与旁路：杜撰 level 类型/第三种候选集语义/authority_hint 根旁路/杜撰示例类别。类代表制豁免裁定：嵌套 required·minLength·minItems·嵌套旁路四类各至少一枚代表即类级承重——无机器件上逐键 exhaustive 钉违反反过度设计先验；judgment_version 的 const 由版本 lockstep 钉、required 豁免（家族形制）） |
| `examples/adoption/valid`, `examples/adoption/invalid` | 采纳请求样例：2 必须通过 / 5 必须拒绝（缺版本 / 坏 digest / 空授权 / 未知旁路字段 / 杜撰效果烈度） |
| `examples/keys/trusted.jwks.json` | 样例用可信公钥库：JWKS（publisher、tester、enc-only、ops-enc、alg-rs、other-publisher）+ `subject_of` 绑定；私钥不落盘 |
| `examples/keys/invalid/*.jwks.json` | 必须拒绝加载的密钥库（重复 kid / 无 kid / 绑定指向不存在的 kid） |


```sh
python3 schema/validate.py            # 契约 + 信封 + 密钥库三套样例 + 程序化 NaN/inf 守卫，双向断言
python3 schema/compose.py             # 执行图合成 + ⊆ 判定样例 + 程序化守卫（NaN 父预算 / 钉 shares 无父预算），双向断言
python3 schema/validate.py FILE...    # 校验指定文件，自动识别契约 / 信封
python3 schema/compose.py GRAPH...    # 合成指定执行图并打印 requires(G)/effects/bounds
python3 schema/sign.py                # 换密钥重签全部信封样例（连同密钥库一起提交）
python3 schema/ledger.py              # 账本事件样例（件4），双向断言
python3 schema/adoption.py            # 采纳请求样例（件2），双向断言
python3 schema/judgment.py            # 判断规格样例（件3），双向断言
python3 schema/release.py             # 发布清单样例（件5），双向断言
python3 schema/replay.py              # 重放用例样例（件6，格式面），双向断言
python3 schema/_suite.py --self-test  # 夹具 harness 硬化臂自检（V28/V32 pin 纪律）
python3 schema/evidlog.py            # 取证日志样例（件7 spike），双向断言
```

Go 侧同套件与状态机：`cd go && go run ./cmd/ledger && go run ./cmd/adopt && go run ./cmd/judgment && go run ./cmd/release && go run ./cmd/replay && go run ./cmd/evidlog && go test ./...`（夹具套件纪律在 go/internal/suite；引擎与懒编译在 go/internal/schemalib）。

依赖：`jsonschema`（含 `referencing`）；信封验签另需 `pyjwt[crypto]`。

签名内容 = `JCS(contract)`，不含信封其他字段。`contract_hash = "sha256:" + hex(SHA-256(JCS(contract)))`，Agent Card 在 `capabilities.extensions[].params.contract_hash` 里引用它。多个签名 = 多个背书方，**全部必须通过**（与 A2A 名片"多签名 = 密钥轮换"语义不同）。

`compose.py` 的 selector 覆盖判定在 0.1.0 是**精确匹配**（健全但不完备：绝不放行父没有的，但会拒绝语义上被覆盖的前缀 / 子域）；0.2.0 按 D32 的按类文法扩展为前缀 / 主机后缀匹配。子集判定与预算切分经 mutation-RED 证非恒真（见 `docs/02-build-log.md` 第 15 轮）。


## 顶层立法：事前结构化优于事中裁量

本仓全部 schema 与夹具遵循的元原则（夏架构师从生产治理侧独立推导，与我们六件战役的验证纪律独立收敛——两条路径碰到同一结构）：

> 能在雇佣时刻（无具体案件、无利益冲突）写进规格的，不留到运行期临时判断；运行期必须裁量的，裁量本身也要结构化（预注册阈值、封闭枚举、必填字段）；裁量只在**规格失灵**时兜底，且每次裁量的产出是**修规格**——系统单向收敛，越用越不需要人。

实例：件2 幂等键预注册、件3 封闭枚举+全节点 additionalProperties:false、件5 三选一 rollout 枚举、件6 divergence_at if/then 双向、件7 取证日志带内 seq。人裁→规格补丁的治理闭环见 impl-2026-11-01/05-edge-grammar-prior.md §四。

## 漂移登记（canonical 唯一点）

NGA 2026-10-31 文档合并（旧 12/13/14/15 号+旧总体设计 §6/§7.2 → 现行唯一提案+总体设计新文）造成的语义漂移，全仓在此登记一处；schema description 只放短版+指向。上游恢复后逐行销账。

| # | 语义 | 旧出处 | 现行文档状态 | festival 立场 | 状态 |
|---|---|---|---|---|---|
| L1 | 语义分类非权限证明（"A semantic classification must not be treated as proof of authority"） | 旧总体设计 §6 原句 | 未落位（最近义句为 §5 "No invented business conventions"，不同命题） | 机器已固化（judgment 全线零授权字段、authority_hint 拒收）；生态滑坡实证：codex 生产代码消费 MCP readOnlyHint 免批（requires_mcp_tool_approval） | awaiting-upstream（issue #1 碰撞回应 L1） |
| L2 | 判断规格 owner 责任族（owner/review_authority/effective_scope/change_rationale/impacted_links） | 旧总体设计 §6.1 具名 | 无落位句（§2 名责任不名字段） | 语义承重（无 owner 的规格=无问责），按旧出处保留，judgment.ownership description 已注 | awaiting-upstream（L2） |
| L3 | evidence 是否版本维度 | 旧 P5 五维 | 总体设计新文 P5 五维 vs 提案 §6 J1/D1 四维，两文并存未决 | 按五维实现（件4 versions 全必填），event-ledger $defs.versions 已注 | awaiting-upstream（L3） |
| L4 | in-flight 处置词汇 | 旧 v0.2 §5 三枚举 | 提案 §6 四词散文（多 reevaluation） | 保三值封闭枚举+拒绝杜撰第四模式（负例夹具钉），release.rollout 已注 | awaiting-upstream（L4） |
| L5 | 重放按记录序重演、不重新仲裁 | 旧 12号 §3 步骤6 | §8 四模式表仅 "compare transitions and intents" | 按旧语义实现（件4 arbitration_seq 严格递增+件6 将按序重放），event-ledger description 已注 | awaiting-upstream（L5） |
| E3 | 提供者回执归属 | —（festival 先验裁定） | 提案 §6 B1/§8 retention 把 receipts 列入保留清单 | 账本精瘦（S1 岔路裁决）：回执归件6 记录族夹具，不入账本 schema；按 §3 "observations distinct from commands" 分流 | festival-ruling（明示分层非沉默分歧） |

出处锚定形态：本仓用双锚——语义复述为主锚（原则句随锚走，节号断了语义不断）+ 现行节号辅锚 + 旧编号 superseded 溯源（不静默删除）。节号级「旧节→新节」映射表属上游文档的职权，本仓不维护镜像（单一真源）。

## 状态词汇分层映射

festival 事件**事实态**（账本持久层，机器写）与 NGA 命令**结果报告态**（API 返回层）是两个层次的词汇——同形处含义不同，逐对声明一次，代码/夹具不重复定义：

| festival 事件事实态（入账本） | NGA 命令结果报告态（API 返回） | 同异说明 |
|---|---|---|
| adopted | committed | 同义异名：采纳已落账 ↔ 命令已提交 |
| reused | duplicate | 同义异名：同键同载复用原回执 ↔ 重复命令返还原 receipt |
| conflict | conflict | 同形同层：同键异载冲突（两侧语义一致） |
| dispatched / completed / failed | accepted / pending | 层差：festival 记效果生命周期事实；NGA 的 accepted/pending 是命令受理层报告，不入事实账本 |
| unresolved | unresolved | 同形同层：结果未知一等态（两侧语义一致） |
| —（永不入账本） | rejected | 分层铁律：rejected 是机器答案词汇，不是事实——账本只记已发生的事；07 若持久化 rejected 则与本分层冲突（待 NGA 明示 rejected 是否落盘） |

分离理由：两套词汇的文法不相交——事实态由状态机守卫与八族跨事件规则校验（只含已发生的事），报告态含未发生的可能（pending/rejected）；若混入同一层，账本规则将无法区分「机器想过什么」与「世界发生了什么」。
