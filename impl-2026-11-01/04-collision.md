# 空白碰撞报告：七件执行批 × frame-bench 15 样本（2026-11-01）

碰撞方法：4-lens（先例形态/反例警示/新颖面/范围修正）+ singularity（生态无覆盖面）+ 第一性原理 + 系统动力学。被碰撞批：`03-priors-exec-batch.md` 七件。只读，全部结论带路径与行号。

---

## 主题 1（E1）：机生成计数——pi 双生成器先例，形态完全覆盖

**先例（强）**：pi 有两个生成器，同一形态各跑一套：

- `~/frame-bench/pi/packages/coding-agent/scripts/generate-schemas.ts` + `test/config-schemas.test.ts:33-47`——「matches the four committed artifacts」测试**在 CI 里重新渲染并与已提交产物逐字节对拍**，stale 即失败，失败消息直接给修复命令：`"${relativePath} is stale; run npm run generate:schemas"`（:44）。
- `~/frame-bench/pi/packages/coding-agent/scripts/generate-references.ts` + `test/references.test.ts:13`——派生文档同款 stale 钉（`is stale; run npm run generate:references`）。生成物头部带防手写声明：`"This file is generated from TypeScript source. Do not edit it manually; run npm run generate:references."`（generate-references.ts:29-30）。
- 两个生成器都挂 npm script（package.json:39-40）。generate-references 从 schema/目录**枚举派生**内容（:48 对 `CompatSchemasByApi` 枚举建组）——「从枚举派生」覆盖计数这一特例：计数只是派生标量之一。

**第一性原理裁定**：pi 的关键不是「对账」而是**单源**——已提交文件被重新定义为生成产物，手抄副本不存在而非被核对。03 批文写的「对账脚本（对拍 pi 先例）」是对 pi 形态的弱化转述：对账脚本=两源核对（第四副本仍在，只是被检查）；pi=一源渲染（第四副本被消灭）。

**范围修正（E1）**：
1. 不写「文档 vs examples 对账」脚本；写 render 函数（输入=examples 目录枚举，输出=conformance-fixture-format.md 的计数表段落），CI 测试重新渲染+对拍，失败消息给重跑命令。
2. 若计数表嵌在人写文档中间（当前形态），最小可行版=生成**可嵌入片段**（如 `<!-- generated:counts -->` 锚点区块），文档其余部分人写；生成区块带 do-not-edit 头。pi 是整文件生成，因为其产物本就是纯生成物——我们的格式文档是混合体，锚点区块是忠实形态。
3. release 计数行（2+9→3+14/170→195 类）全部改从 examples 目录派生，禁止出现手抄数字。

**反例**：无。15 样本未见机生成产物回滚案例；pi 双生成器长期共存即稳定性证据。

---

## 主题 2（E3）：中性错误键——三样本三形态，键位裁定「同一错误对象内的兄弟字段」

**先例（三个互补形态）**：

1. **codex（数字码封闭集 + 自由消息同对象）**：`~/frame-bench/codex/codex-rs/exec-server-protocol/src/rpc.rs:269-274` `JSONRPCErrorError { code: i64, data: Option<Value>, message: String }`；构造器封闭集 5 个：`-32600/-32601/-32602/-32004/-32603`（exec-server/src/rpc.rs:761-806，invalid_request/method_not_found/invalid_params/内部两个）。键与人读消息**并排在同一错误对象里**，不拆两层。另一细节：capability_discovery.rs:33-36 协议级错误是**极小封闭枚举**（仅 `TooManyRoots` 一个变体），而逐根降级信息走**成功响应内的自由文本 `error: Option<String>` 字段**（:83-135）——「部分失败当数据不当错误」。
2. **langgraph（字符串枚举 + 键尾拼进消息=向后兼容双轨的生态解法）**：`~/frame-bench/langgraph/libs/langgraph/langgraph/errors.py` `ErrorCode(Enum)` 仅 5 个 SCREAMING_SNAKE 成员；`create_error_message` 把键**确定性地拼在人读消息尾部**（`".../errors/{error_code.value}"`）。这是「老钉仍命中」的机制化方案：老短语保持为消息前缀原样不动，键只增量附加——任何钉老短语前缀的消费者零破坏。
3. **agentscope（与 E3 意图最贴）**：`~/frame-bench/agentscope/src/agentscope/types/_reply.py` `ErrorType(StrEnum)` 9 个**中性分类键**，类文档明言「Not model-specific: the status-derived members apply to any upstream service」——键做分类不做描述；`ErrorInfo { type: 稳定键（"the frontend localizes off it"）, message: sanitize 后人读文本 }`。且有 `UNKNOWN` 兜底吸收不可分类错误——**封闭集抗膨胀的关键设计**。
4. codex OS 错误用枚举匹配不用字符串：capability_discovery.rs:350 `error.kind() == io::ErrorKind::NotFound`。

**反例/警示（两处）**：
- codex 的 `data: Option<Value>` 槽：全 exec-server **无任何构造器填它**（grep `data: Some` 仅 rpc_tests.rs:35 的 round-trip 序列化测试）——预留字段只被测试养着，是「为未来留槽」投机通用性的活标本。E3 的每个 error_key 必须从第一天起由真实代码路径产出，不许预留空键。
- zcode 遥测 errorCode 大小写漂移（`v4ConversationTelemetrySupervisor.test.ts:1903 "CHILD_FAILED"` vs `:2410 "tool_timeout"` vs `:3503 "USER_INTERRUPT"`）——无注册表持有的命名会漂。

**范围修正（E3）**：
1. 键放**错误对象内兄弟字段**（agentscope ErrorInfo 形态：`error_key` + `message` 并排），不建顶层平行结构。
2. 兼容双轨采 langgraph 机制：老 11 短语保持原样做消息（前缀），`error_key` 是新增并列字段——这样 17 个老 PROSE 钉天然继续命中，α 攻击面（键改了钉没跟）被结构性压缩。
3. 封闭集 11 键 + 1 个 `uncategorized`/`unknown` 兜底（agentscope 先例），杜绝「先收编后膨胀」。
4. 单一注册表文件（Go 侧 const 块 / Python 侧 Enum）持有命名规范，统一一种 casing——zcode 反例的直接教训。
5. 双轨期要有 sunset：生态里**没有**长期维持双钉目标的先例（langgraph 靠前缀稳定绕开了双轨），夹具 `_expect_match` 迁到键钉后，短语钉应在本批或下批收卷，不无限并存。

**新颖面（singularity）**：封闭键、同对象并排、UNKNOWN 兜底全部有覆盖；唯一无覆盖面是「**17 个既有短语钉 → 键钉的迁移期本身**」——langgraph 从未迁移过（它起步就带键）。这是 E3 真正的空白地带，靠 sunset 纪律管理。

---

## 主题 3（E4）：判定域声明——zcode 裁定「可执行钉在测试，但我们的合同文档必须双写」

**先例（强）**：`~/frame-bench/zcode/packages/services/test/conversationShareIntegrity.test.ts`——RFC 8785 golden 向量**内联硬编码在测试里**：

- :11-21 原始样本期望 canonical 串整串硬编码（`{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],...}`）；
- :29-33 数值判定域由用例钉死：`-0, 1e30, 1e-7, 0.000001` → `[0,1e+30,1e-7,0.000001]`（ECMAScript 序列化域）；
- :35-40 非有限拒绝、:42-45 孤立代理对拒绝——**判定域的边界由「拒绝用例」同样钉住**；
- 域声明的文字面写在**测试名**里（"uses ECMAScript JSON number serialization"），源码 `conversationShareIntegrity.ts` 只有实现（`Number.isFinite` 守卫抛 `"must be finite"`），无独立合同文档。

**关键差异（第一性原理）**：zcode/pi 是单语言仓——测试即合同，读测试的就是同语言维护者。我们的 conformance 格式文档是**跨语言合同**（E5 的 Java 消费器 + Python 侧都消费它），消费方读不到 Go 测试。所以判定域声明必须**双写**：golden 向量测试（可执行真值）+ 格式文档 §3 一句判定域声明（跨语言可读合同）。这是 03 批文已写对的（「格式文档§3 判定域声明」），本碰撞确认其必要性来自跨语言消费结构，不是文档洁癖。

**新颖面**：15 样本 grep `900719925474099` 无一处显式 2^53+1 奇数孪生夹具（zcode 的 RFC 8785 向量停在 1e30 量级，openclaw 的 MAX_SAFE_INTEGER 用例是 UI 表单域）。奇数孪生夹具是本批真空白，但**形态完全有先例**（golden 向量+拒绝用例成对），不是无锚设计。RFC 8785 §3.2.2.3 本身就是「IEEE 754 double 是判定域」的规范级出处。

**范围修正（E4）**：夹具成对——`9007199254740993.0`（奇数语法，钉 float64 判定域）+ 一个拒绝/折叠对照（若格式层语义是折叠到 9007199254740992.0 则钉折叠后值；zcode :35-40 拒绝用例先例：域边界两侧都要有钉）。文档 §3 声明一句话足够，别长篇。

---

## 主题 4（E5）：消费器进仓——codex/deepseek 双先例，位置惯例 `sdk/<lang>/` 或 `<lang>/`，`examples/` 是轻量合法位

**先例（强，两个）**：

1. **codex**（Rust 主仓）：`~/frame-bench/codex/sdk/typescript/`（src + `samples/{basic_streaming.ts,structured_output.ts,structured_output_zod.ts,helpers.ts}` + tests）与 `sdk/python/`（+ `sdk/python-runtime/`、`examples/`、`notebooks/`）。TS SDK 的本质就是「包 Rust CLI、spawn 子进程、stdin/stdout 换 JSONL 事件」（README:5-6）——**与 spike-java「消费 Go 产物」同构**。
2. **deepseek-harness**（TS pnpm 单仓）：`python/sdk` + `python/sdk-runtime` 顶层目录，含 README/development 文档——语言 B 消费器长在语言 A 仓的顶层惯例位。

**位置裁定**：重惯例是 `sdk/<lang>/`（codex）或 `<lang>/`（deepseek）；但两仓的 sdk 都是**受支持的发布物**（npm/pip 可装）。E5 收编的是一个 spike 样例，非发布 SDK——`examples/java-consumer/`（03 批文方案）落在轻量端，与 codex `samples/`（SDK 内样例子目录）同性质，合法。**不建议**为单个 spike 升格 `sdk/java/` 目录——那是发布物语义，名不副实。

**范围修正（E5）**：
1. README 必须含「跑一次的最小入口」（codex sdk README Quickstart 形态：装→三行代码→期望输出），03 批文已写对。
2. **诚实标注 CI 状态**：codex/deepseek 的跨语言件都在自家 CI 里构建测试；Go 仓里的 Java 样例若无 Java 工具链 CI，README 首行注明「样例，不在 CI 门内，已验证于 <日期+JDK 版本>」——否则它会在半年后变成静默腐化的第五副本（与 E1 的 stale 钉同一病根，但无生成器可救）。
3. E2（go.mod 域名化）联动：样例 README 里的 `go get` 路径在 E2 落地后要同步——收编顺序上 E5 应在 E2 后或同批校对。

**反例**：无回滚案例；两仓多年维持双语言。

---

## 主题 5（E6）：取证日志——codex rollout 给骨架，hermes 给裁决语义；「sidecar vs .git 对账」在 15 样本中不存在

**先例（两个半）**：

1. **codex rollout（写者分配 seq 的完整形态）**：`~/frame-bench/codex/codex-rs/rollout/src/writer_lock.rs:1-50`——跨进程独占写者所有权（per-thread 锁文件 + `WouldBlock` + 陈锁清理 + coordination lock）；`ordinal.rs:19-28` `RolloutOrdinalState { Legacy, Paginated { next: Option<u64> } }`——**写者分配的单调 u64 序**，fork/续跑从 `history_base.end_ordinal_exclusive` 续号；recorder.rs `append_rollout_item_to_path` 追加式。
2. **codex 的差集告警形态（关键）**：ordinal.rs:82 resume 时扫尾部断言 `"final paginated rollout record at {} is missing an ordinal"`——**带内（in-band）seq 的密度/缺失检查**，无任何外部对账文件。
3. **hermes（告警的裁决语义）**：`~/frame-bench/hermes/hermes_state_health.py:1-16` 模块文档——单一闩（"the single place that fact is recorded"）、**永不自愈**（"a store that flickers between ok and corrupt is the silent failure this replaces"）、不在盘上写标记（"the file it would describe is the one that is damaged"——损坏文件上写标记是无意义动作）。`hermes_state_reconcile.py:382-388`——"never write into a store that is not verified clean"、"additive DDL is not corruption recovery"：**告警先于任何修复写，修复永不伪装成对账**。

**任务假设证伪（诚实报告）**：碰撞主题里假设的「hermes 声明 sidecar vs 实际 .git 对账」在 15 样本中**不存在**——hermes 的 provenance 是会话收据/请求身份对账（hermes_state_local.py:94-105 `same_create_request`），hermes-self-evolution 仓也无 git-sidecar 对账。这不是损失：**E6 根本不需要 sidecar 对账**——采 codex 带内单调 seq 后，差集告警退化为「seq 集合必须是稠密区间」的纯函数检查，比 manifest-vs-artifact 对账少一整个状态源。

**范围修正（E6）**：
1. 骨架采 codex 形态：JSONL 行带写者分配的单调 seq（temp+rename 耐久沿用件4 先例，03 批文已写对）；差集告警函数=seq 稠密性检查（+可选行数上限预算，hermes BROWSE_INTEGRITY_BUDGET 先例）。
2. 告警语义采 hermes：**闩住不复振**（发现过的差集是永久事实，不因下次读正常而清除）、**告警不触发修复写**（spike 范围内告警函数只返回裁决，不做任何修复——03 批文「不做 S2 集成」与之相容，建议显式写「无修复路径」）。
3. γ 攻击面（与件4 账本词义碰撞）：包文档第一段写分家声明——件4 账本=业务状态机对账（有状态、有修复），evidlog=取证事实流（无状态机、无修复，只有告警）。hermes 闩语义（只记录不治疗）正好是分家的教义证据。
4. 单写者假设写进 schema 文档：codex 用锁文件保证；evidlog spike 若不做锁，文档如实写「单进程假设，多写者未定义」——不要静默假设。

**新颖面（singularity）**：append-only 日志、seq、告警全有先例；空白面是「**框架层自动记录的取证日志**」（调用方无感、由框架埋点）——codex rollout 是会话记录（框架埋但面向重放），hermes 是健康裁决。取证目的（事后审计差集）×框架自动埋点这个组合无直接先例，但它是两个已验证件的组合，非无锚设计。

---

## 主题 6（E7）：三边类型——langgraph 9 种 channel 是最近先例；裁定量级合适但须「每类型一夹具一行为差异」

**先例（强）**：`~/frame-bench/langgraph/libs/langgraph/langgraph/channels/` 共 9 种类型——LastValue、LastValueAfterFinish、EphemeralValue、Topic、BinaryOperatorAggregate、AnyValue、NamedBarrierValue、UntrackedValue、DeltaChannel。**类型=行为差异**（不是数据类型标签）：EphemeralValue「存上一步的值，读后即清」（ephemeral_value.py:15-16），UntrackedValue「存最后的值，永不 checkpoint」（untracked_value.py:15-16），AnyValue「多值并发到达时假定全等」（any_value.py:15-17）。基类契约抽象在 ValueType/UpdateType/checkpoint/from_checkpoint（base.py:15-50）。参数化优于增殖：EphemeralValue 用 `guard: bool` 参数吸收变体（:23），不另立类型。

**系统动力学裁定**：9 种类型是**反应式生长**的结果——每种都对应一个运行时需求（中断恢复、并发汇入、内存节省），且新增语法成员仍被 Beta 闸门管着（delta.py:26-28 `!!! warning "Beta"`）。三边类型 a priori 设计处于生态规范的**低端**（3 vs 9），量级无过度设计之虞；真正的风险不在数量在**税基**：三类型 × 三属性 = 9 格文法，每格都需要夹具与双侧 oracle 覆盖，验证负担按格数增长而非按类型数增长。

**范围修正（E7）**：
1. 每个边类型必须能指向一个**具体行为差异**（langgraph 式一句话：「X 边的行为是 Y，其它边不是」）+ 一个钉该差异的夹具；答不出行为差异的属性先降级为参数（EphemeralValue.guard 先例），不进类型学。
2. 三属性优先做成「类型上的参数」而非正交轴——除非存在某属性×某类型的组合确实无意义或有独立语义，9 格文法才被迫存在；设计文档里逐格给一行「此格语义/此格非法」表，非法格要在 schema 层拒绝（比事后文档约定硬）。
3. evidence_gap 作为**一等症状产出类型**（而非 absence/空值）有先例背书：langgraph 把「无值可读」「图耗尽」「节点取消」全部做成显式类型（EmptyChannelError/GraphDrained/NodeCancelledError 在 errors.py `__all__`）而非静默空——缺证据是可判定事实，就该有类型。进判断规格 schema 的提案方向正确。
4. E7 是提案不是发出（03 批文 OUT 已钉）——langgraph 的 Beta 闸门启发：提案里给三边类型各标「成熟度：spec-only / 有夹具 / 有双侧实现」，让评审看到哪些格子只是纸面。

**反例**：langgraph 无类型回滚痕迹（静态可证范围内）；Beta 闸门本身就是生态对文法增生的防御机制。这支持「先闸门后扩张」而非「先砍类型」。

---

## 主题 7（反例总检：七件里生态做过又回滚的？）

逐件扫描结果——**没有一件命中「做过又回滚」**；命中的是三类**纪律警示**（均为「没做好会怎样」，不是「做了被撤」）：

| 件 | 反例检验结果 | 警示来源 |
|---|---|---|
| E1 机生成计数 | 无回滚案例；pi 双生成器稳定共存 | 唯一纪律：生成物必须带 do-not-edit 头 + stale 测试**挂在 CI**（不挂 CI 的生成器等于死代码） |
| E2 域名化 | 无碰撞主题，未深扫 | pi 侧教训（`config-schemas.test.ts:13` 固定 `https://pi.dev/schemas` URL）：对外可见路径改动会钉进消费方测试——β 攻击面已预登记，成立 |
| E3 错误键 | 无回滚案例；错误码**膨胀**有活反例（zcode 遥测大小写漂移=无注册表之祸）+ 预留空槽反例（codex `data` 字段只被 round-trip 测试养着） | langgraph 恒 5 键 + agentscope UNKNOWN 兜底 = 抗膨胀的两个机构设计，E3 都要抄 |
| E4 奇数孪生 | 无（bench 无 2^53+1 先例，无从回滚） | 拒绝用例与接受用例必须成对（zcode :35-40 先例） |
| E5 消费器进仓 | 无回滚；codex/deepseek 长期维持 | 警示是无 CI 的样例会静默腐化——README 标注验证日期 |
| E6 取证日志 | 无回滚；hermes #72046 是「分散告警各猜各的」反例（health.py:3-5 记载：修复前每个 surface 自行猜测、无人说「库坏了」），已被闩机制治愈 | 告警裁决必须收敛到单点单语义 |
| E7 三边类型 | 无回滚；DeltaChannel 带 Beta 闸门=生态防线而非悔痕 | 纸面格不入文法，入文法必须有夹具 |

**结论**：七件无一件踩过生态已知的回滚坑；三件（E1/E5/E6）的先例在各自样本里已运行多年。本批的生态风险不在「做过被撤」，全在**执行纪律**（stale 挂 CI、双轨 sunset、注册表持名、闩不复振）。

---

## 对七件的范围修正汇总（delta 形式）

1. **E1**：升级「对账脚本」→「render+stale-test」（pi 双生成器形态）；计数表做成文档内生成锚点区块带 do-not-edit 头；stale 测试必须进 CI 门。
2. **E2**：无修正（无碰撞主题）；唯一联动=E5 样例 README 的 `go get` 路径同步。
3. **E3**：键位=错误对象内 `error_key`+`message` 兄弟字段；老短语原样保留为消息（langgraph 前缀稳定机制）使 17 老钉天然命中；11 键 + `uncategorized` 兜底；单一注册表定 casing；**双轨 sunset 写进本批**（夹具迁键钉后短语钉收卷），不留无限并存。
4. **E4**：夹具成对（接受 9007199254740993.0 + 域外/折叠对照）；判定域双写——golden 向量测试（可执行）+ 格式文档 §3 一句（跨语言合同，Java/Python 消费方读文档不读 Go 测试）。
5. **E5**：位置维持 `examples/java-consumer/`（codex `samples/` 同性质，勿升格 `sdk/`）；README 加跑一次入口 + **CI 状态诚实标注**（不在 CI 门内则写明验证日期/JDK 版本）。
6. **E6**：seq 采 codex 带内单调序（写者分配、resume 续号）；差集告警=seq 稠密性纯函数；裁决语义采 hermes（闩住不复振、告警不触发修复写、无修复路径显式声明）；包文档首段与件4 账本分家；单写者假设如实写进 schema 文档；**不需要 sidecar 对账**（15 样本亦无此先例，带内 seq 使其多余）。
7. **E7**：三类型量级合适；每类型一句行为差异+一个夹具，答不出的属性降级为参数；三属性默认是类型参数，9 格表逐格给语义/非法裁定且非法格在 schema 层拒绝；evidence_gap 一等症状类型方向确认（langgraph 显式结果类型先例）；提案内给每格标成熟度（Beta 闸门启发）。

## 总评

本批七件的先例密度显著高于平均水平：E1/E3/E5/E6 四件在 15 样本里有**运行多年的同构物**（pi 双生成器、codex/langgraph/agentscope 三套错误键形态、codex+deepseek 双语言 SDK 仓、codex rollout+hermes 闩的完整取证骨架），骑轮子检查全部成立，无一件需要发明新机制。真正的空白面有三处且都窄：E3 的**短语钉→键钉迁移期**（生态都起步即键，没人迁移过，靠 sunset 纪律管理）、E4 的**奇数孪生具体值**（形态有锚、值是空白）、E6 的**框架自动埋点×取证目的**组合（两个已验证件的乘积）。第一性原理上本批最值钱的一刀是 E1 从「对账」升格「单源渲染」和 E6 从「sidecar 对账」降为「带内 seq 稠密性检查」——两处都是把两个状态源压成一个，与底层判别不定制立法同向。系统动力学上唯一要盯的税基在 E7 的 9 格文法：类型数不是风险，格数才是——参数化优先、逐格夹具、纸面格不进 schema，三道闸都在本次修正里落了位。七件无一踩生态已知回滚坑，风险面全部收敛到执行纪律（stale 挂 CI、双轨收卷、注册表持名、闩不复振），批可以放行。
