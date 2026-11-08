# 30-blank-r14 — 空白审核位终审报告（review-loop 叠加守卫轮，连胜第 3 轮）

- 审核位：blank agent（无先前结论携带），全强度外环
- 对象：`agent-festival` 仓 `git diff baca2dd..HEAD` 全部增量（约 20 笔提交：P1-1/P1-2 权限与断尾教义、E3 control 事件、polarity guard、E0-E3 正确性实验、T0 十场景、T1 真 LLM harness）
- 方法：review-loop（退出判据+前置门+证伪耦合门）× 4-lens（四镜+严重度×可达性矩阵+doc↔code 交叉）× singularity（族复发判据）
- 禁区遵守：未读 `impl-2026-11-01/` 下任何已存在文件（本报告为唯一写动作）；未读 BATTLEFIELD.md；未访问 `~/.zcode/`；未联网；未设任何 `T1_*` 变量；未修改任何代码
- 日期：2026-11-04

---

## 一、机械门（前置门，全过）

| 门 | 结果 |
|---|---|
| `cd go && go build ./...` | PASS |
| `go vet ./...` | PASS |
| `go test -count=1 -race ./...`（无任何 T1_* 环境变量） | 20 包全 `ok`，0 fail（T1 默认 Skip，符合"未启动=跳过"的正确形态） |
| `python3 schema/_suite.py --self-test` | `[_suite] self-test PASS` |
| `schema/validate.py` | 4 programmatic must-reject，0 failures |
| `schema/ledger.py` | 9 must-accept + 33 must-reject，0 failures；lockstep（status enum==checker families；grant/identity/versions/accountability/payload_digest 形状==adoption 副本）绿 |
| `schema/adoption.py` | 2 + 5，0 failures |
| `schema/judgment.py` | 2 + 19，0 failures |
| `schema/release.py` | 3 + 14，0 failures |
| `schema/replay.py` | 8 + 9，0 failures |
| `schema/compose.py` | 10 + 36，0 failures + 2 programmatic |
| `schema/evidlog.py` | 1 + 6，0 failures |
| `python3 tools/corpus_manifest.py --check` | OK（committed block == 再生 manifest） |
| `gofmt -l go/` | 空 |

**测试面计数（守恒读义务口径：套件 runner 可输出的测试函数/夹具计数，相对上轮不减）**：
Go `func Test` 计 224（本增量新增 e2e 包 16 个 Test：e2e_test 10 + correctness_probe 5 + t1_llm 1，另 adopt/replay/evidlog 各有新增探针）；JSON 夹具 211 件（ledger 族 8+28 → 9+33，计数钉三处同步：ledger.py 计数门、cmd/ledger/main_test.go、manifest block）。**恒积累成立。**

---

## 二、逐 finding（四镜 × 交叉维度；本轮 B=0、M=0，新 minor 3 条 + 同步提醒 1 条）

### N1（minor，新）转换环的状态钉与 needsIdem 是"纯状态键"，未随 E3 收紧事件类型域——注释宣称与代码不符；仅非法文档上的错误集组成差，双 oracle 逐条同构、裁决不变

- **file:line**：`go/internal/ledger/ledger.go:276-279`（非 effect 分支 `if e.Outcome.Status == "adopted" { state[op] = "adopted" }`，无 event_type 检查）+ `ledger.go:321`（`needsIdem := e.EventType == "effect" || e.Outcome.Status == "adopted" || e.Outcome.Status == "reused"`）；Python 侧同构 `schema/ledger.py:159-163`（`if e["event_type"] != "effect": if ...status == "adopted": state[op] = "adopted"`）与 `ledger.py:200`（`needs_idem`）。
- **镜头**：Bearing（注释恒真性）+ Consistency（E3 词表增长后两条状态键规则位点的传播完整性）。
- **行为**：`ledger.go:267-272` 注释宣称 "only adoption+adopted pins the state"（ledger.py 的 R6 M-2 注释同句式），但代码对**任何**非 effect 事件只要 status=="adopted" 就钉状态。实测探针（本地构造文档 `[control status=adopted op1, effect status=dispatched op1]`，无 adoption）：Go 与 Python 错误集**逐条同构**各 4 条（STATUS_FAMILY + IDEM_REQUIRED(control 事件) + EVENT_BEFORE_ADOPTION×2），**ILLEGAL_TRANSITION 被状态钉压制**；基线文档（control status=rejected）双方各 3 条且含 ILLEGAL_TRANSITION。即：状态污染面真实存在，但 (a) 该文档本身已被 STATUS_FAMILY 判拒（裁决面零后果），(b) 双 oracle 完全一致（parity 零破坏），(c) needsIdem 面对该文档是**加**错误而非漏错误。
- **severity**：MINOR（按 4-lens 严重度规则：拒绝行为正确、退出码正确；失实的是注释叙述 + 仅非法文档上的错误集组成。文本/评论 vs 行为最高 MINOR）。
- **可达性**：本地构造（须手工构造 schema 合法但 family 违例的文档；git 正常路径不可达——机器的 refuse() 只写 status=rejected）。
- **红探针方案（确定性档，若获授权修复时落）**：以 `[control status=adopted op1, effect status=dispatched op1]` 构造文档，断言 `ledger.Errors` 含 `ILLEGAL_TRANSITION`——今日红（被压制）；修复=双侧 pin 条件收紧为 `event_type=="adoption" && status=="adopted"`（needsIdem 同步加 `event_type!="control"`），改后双侧探针同绿、既有 42 件 ledger 夹具回归不动。属 minor：按律只积累不修，方案存档。

### N2（minor，新）E3 自相矛盾证明测试对夹具缺失 fail-open（t.Skipf）——夹具改名/移动时"spec 自相矛盾"的证明静默蒸发

- **file:line**：`go/internal/e2e/correctness_probe_test.go:271-275`（`os.ReadFile` 失败 → `t.Skipf("E3: fixture not found at %s (running from wrong directory?)...")`）。
- **镜头**：Bearing（断言的存活条件）+ Fidelity（"此测试 PROVES the contradiction is real"的宣称 vs 静默 skip 的实态）。
- **行为**：实测探针（/tmp 副本摘除 schema 目录）：`go test -run TestE3SpecSelfContradiction_WindowScope` → **SKIP 且套件整体 PASS（绿）**。polarity guard 的 skip 语义覆盖"P3 修正落地"（正文有豁免注释），但**不覆盖夹具消失**。corpus manifest 只钉族计数不钉文件名——夹具改名时 manifest 依旧绿，E3 的窗口矛盾证明无任何信号地退场。
- **severity**：MINOR（测试基建的 fail-open；不涉产品代码行为；XM2"静默空批"教训的测试侧微缩影——但对象是"证明性测试"而非门禁）。
- **可达性**：git 可跟踪（夹具改名/移动是正常仓操作；P3 修正落地时的同族动线使该风险非纯理论）。
- **红探针方案（确定性档）**：`t.Skipf` 改 `t.Fatalf`（go test 恒以包目录为 cwd，路径确定性成立，"跑错目录"豁免场景在本仓不存在）；红探针=改名夹具后跑 `-run TestE3` 必红。属 minor：只积累不修。

### N3（minor，新）T1 读出 `truncate` 按字节切分——多字节 UTF-8（模型 reason 中文大概率）在切点裂 rune，审计读出/硬门失败消息中出现非法字节序列

- **file:line**：`go/internal/e2e/t1_llm_test.go:397-402`（`return s[:n] + "…"`，n=200 字节）；消费点 `t1_llm_test.go:340`（readout reason）与 `:350`（hard-bar 失败消息）。
- **镜头**：Bearing（该文件自我宣称"the full auditable record——won-face AND failure-face both logged"——审计载体的字节完好性）。
- **行为**：实测探针（确定性）：中文 reason 跨 200 字节切点 → 输出含 `\xbb\xbc…\xe4…` 非法 UTF-8。仅日志外观，不改判定、不改退出码（verdict 解析在 truncate 之前）。
- **severity**：MINOR。
- **可达性**：git 可跟踪（真实模型返回中文 reason 且长度跨切点即触发；T1 是用户启动的真 LLM 轮，正常路径）。
- **红探针方案（确定性档）**：`truncate` 单元测试：多字节字符串 + 切点落 rune 中间，断言输出 `utf8.ValidString`——今日红。修法（若授权）：`for !utf8.ValidString(s[:n]) { n-- }` 或按 rune 切。属 minor：只积累不修。

### 同步提醒（非 finding，派生数据计数副本）

`docs/conformance-fixture-format.md:3` 头部散文仍写"本仓 205 件 JSON 夹具（增长族 151 件）"，同文件 manifest block 与实态为 211/157——本增量只更新了 manifest block（manifest --check 绿）。计数属派生数据多处副本，按 4-lens 漂移规则不产 finding；且该行明示"三种口径见机生成清单"（委托机器清单为真源）。**一句同步提醒**：下次触碰该文件时顺手对齐 211/157。

### 已登记面的独立复核（对账确认，非新增）

本轮独立命中了 minor 台账已登记的下列面，逐条对码核实**记录为真**：L24（`replay.go:459` fail-loud 网只匹配 "ledger append failed"，refuse 包装报文 "(refusal not recorded: …)" 逃网——行号精确）；L25（EVENT_BEFORE_ADOPTION 非 adoption 分支双 oracle 硬编码 "effect event"，control 前置时错标——本次探针实测再次命中）；L27/L28（TornTail 文档"every mutation is refused"在写时字节复核窗口的失实 + 断尾四报文形态键族不齐）；L23（t1Spec"exactly the semantics"宣称在 C8 失实）；L26（180s×2×12 最坏 72min）。台账记录保真度良好。

### 同族穷举（E3 词表增长的手镜像位点，全量枚举）

schema enum ✓ / Go 状态族+lockstep ✓ / Python 状态族+lockstep ✓ / family 标签逻辑 ✓ / 转换环（M-2 已修；**遗留=N1**）/ CONTROL_IDEM_FORBIDDEN ✓ / IDEM_REQUIRED（**遗留=N1 同位点**）/ attribution（M-1 已修）✓ / EVENT_BEFORE_ADOPTION 行为 ✓（文案=L25 已登记）/ GRANTS_ON_NON_ADOPTED（control+grants 拒，双 oracle 同）✓ / DOUBLE_ADOPTED ✓ / digest 注册表（control 无 idem 天然隔离）✓ / seq 单调（类型无关）✓ / replay Inspect States 投影（family 过滤，control 不投影——`replay.go:128` 实证）✓ / replay drive 面（L29 已登记：无 control 夹具）/ adopt replayEvent（control 跳过投影、seq 前进——`adopt.go:209-215` 实证）✓ / schema if/then（adoption+adopted→grants，control 不适用且由 STATUS_FAMILY 兜底）✓ / 文档三处（README E3 行、fixture-format 计数、minor-ledger）✓（残留=同步提醒）。

### 四镜总检

- **Simplicity**：polarity guard 双开关（`correctnessLayerLanded`/`p3FixtureCorrectionLanded`）是最小机制，注释即文档；durableMode 双包重复=L16 已登记的既定家法取舍。无过度设计新面。
- **Consistency**：双 oracle 在全部新规则位点上逐条同构（含 N1 的"同构地松"）；九个 T0 场景与 doc.go 场景清单一一对应（10 测试=8 场景+happy path+F-02C 快路径）；T1 门注册与 hardBar 字段逐项核对一致（C1/C2/C3/C6/C7/C8/C9/C11/C12 硬、C4/C5 组内、C10 报告无门；一致性组 {C1,C5}/{C2,C4,C11} 与头注 triple 宣称一致）。
- **Bearing**：机器写路径全部有探针（P1-1 双包 umask 探针+ENOTDIR 探针、P1-2 Open/写时/字节保全三面、E3 control 事件四探针、STALE_WRITER 既有网）；E0 病存性测试带 flip-switch 防翻转遗忘（polarity guard 本体）。**断言恒真面未发现**。N1 是本轮唯一"注释宣称≠代码"位点。
- **Fidelity**：T1 配方中和核验——仓内仅占位符（`<your anthropic-messages endpoint>` 等），无端点 URL、无密钥位置路径、无 providerRules 指针残留；env 不全时 Fatalf 响亮（`<masked>` 处理 key）；5xx 单次重试、429 fail-loud、解析失败 fail-loud，无静默绿通道。教义文档（断尾统一、P1-1 推翻 L14）与代码行为逐条对得上（L27 的窗口面已登记）。
- **安全面扫查**：无新增端点/密钥物；`Fatalf` 打印 T1_ENDPOINT 值非密；权限语义（P1-1 0600 保守默认+durableMode 显式报错）双包一致且有永久探针。

---

## 三、singularity 判决

- **「事件类型词表增长 × 手镜像规则位点传播不完整」族**：台账已登记复发 ≥2（M-1 attribution 漏 + M-2 转换环分叉），结构升级触发器已武装（候选=①每侧 event_type×规则家族分派表、②parity 网从 schema 原子扩展到规则枚举；**未启动**，按律转移后须全强度外环+证伪器再生）。**本轮 N1 为该族第 3 次实例**（E3 传播遗漏转换环 pin 条件与 needsIdem 两个状态键位点，注释反而宣称了收紧后的形态）——零裁决后果、minor 级，不独立强制换结构，但使已登记的结构候选**证据加权**：若出现第 4 例或任一裁决承载面实例，应启动候选①。
- **断尾教义族**：本轮已收敛（heals/lossy-but-safe 分叉退役，remember+refuse 统一，三面探针钉死），零复发。
- **权限/可见性族**：P1-1 清偿带永久探针+变异自证记录，零复发。
- 其余族未见 ≥2 复发。**本轮无可达奇点**——当前框架（单 writer+双 oracle+夹具钉+探针网）仍是正确收敛框架。

---

## 四、总裁决

- **BLOCKER：0；MAJOR：0；新 MINOR：3（N1/N2/N3，均附可达性与确定性红探针方案，按律入台账积累不修）+ 同步提醒 1（派生计数散文）**。
- 可达性分布：N1=本地构造；N2=git 可跟踪（夹具改名）；N3=git 可跟踪（正常 T1 运行路径的日志外观面）。无趋零可达项充数。
- 退出判据：本轮为叠加守卫要求的**全强度外环**（机械门全过 + 25 个增量代码/schema/夹具文件全读 + 对抗探针实测 5 发〔M1 双 oracle、M2 skip、M3 rune 切分、双 fixture 负探针、安全面 grep〕+ 同族 20 位点穷举 + doc↔code 交叉 + singularity 判决）。**0B/0M 成立——连胜第 3 轮净轮，按 3 连口径收卷成立。**
- 诚实边界：变异重跑矩阵（审计轮形态的 diff 域变异清单）本轮以对抗构造探针替代而非全量变异清单落日志；N1 的修复将改变非法文档上的错误集组成（双侧同步改则 parity 不破），已写入探针方案防惰性。
