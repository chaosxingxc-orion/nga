# 17-blank-r6 — 空白审核位·退出叠加守卫轮（review-loop 第 9 步：退出前最后一轮全强度外环）

- 被审对象：`/Users/yaojun/nga-impl-wt/agent-festival`，增量 `git diff baca2dd..HEAD`（10 笔提交：P1-1/P1-2/E3 修复批、断尾教义、两层 E2E、T1 真 LLM harness、R1-R3 审核循环收卷）。
- 审核位：空白 agent，不携带先前结论；未读 impl-2026-11-01/ 下任何既有文件（含 BATTLEFIELD.md），未访问 ~/.zcode/，零网络，未设置任何 T1_* 变量。
- 方法：review-loop 第 9 步 + 4-lens（四镜×严重度×可达性矩阵×证伪耦合门）+ singularity（族复发判据）。本报告为唯一写动作。

---

## 一、机械门（全绿）

| 门 | 结果 |
|---|---|
| `cd go && go build ./...` | RC=0 |
| `go vet ./...` | RC=0 |
| `go test -count=1 -race ./...`（未设任何 T1_*） | 20 包全 ok，RC=0；`TestT1RealLLMS1` 默认 Skip（形态正确：`t1_llm_test.go:294` 以 `T1_LLM != "1"` 显式 Skip 并指名启动路径） |
| `python3 schema/_suite.py --self-test` | PASS |
| 7 个 oracle 直跑 | ledger 9+31 / adoption 2+5 / judgment 2+19 / release 3+14 / replay 8+9 / compose 10+36 / evidlog 1+6 —— 全部 0 failures、rc=0 |
| `python3 validate.py`（无参全量：contract+envelope+keystore+guards） | rc=0（含 4 项 programmatic must-reject） |
| `python3 tools/corpus_manifest.py --check` | OK（committed block == regenerated manifest） |
| 测试面计数 | 改动文件：cmd/ledger 2 / adopt 40 / e2e 9 / t1_llm 1 / evidlog 27 / ledger 2 / replay 28 个 Test 函数；全模 27 个测试文件共 218 个 |

用法勘误（非仓缺陷）：prompt 所给字面命令 `python3 schema/validate.py ledger.py …` 与 validate.py 实际接口不符——它收 JSON 文档（传 .py 名抛 JSONDecodeError，见 validate.py:15-17 用法声明）。逐 oracle 的正确机械门是各模块直跑（上表），全绿。

---

## 二、Findings

### M-1【Bearing / doc↔code 承重 + 同族穷举缺口】control 事件不受 attribution-divergence 规则约束——伪造 attribution 的拒收记录双侧双绿通过，且通过 adopt.Open 的加载期完整性边界

- 位置：
  - `go/internal/ledger/ledger.go:350-362`——attribution 循环只在 `else if e.EventType == "effect"` 分支比对 adopted pin；
  - `schema/ledger.py:220-230`——Python 侧同构（`elif e["event_type"] == "effect"`），双侧一致地**不查** control 事件；
  - 机器级后果链：`go/internal/adopt/adopt.go:194-207`（checkLoaded → ledger.Errors）→ Open 接受。
- 行为后果：E3 新类别 control 事件（拒收记录=审计事实，`adopt.go:431-443` refuse() 声称携带"the operation's full identity/versions/accountability pin"）不受 ATTRIBUTION_DIVERGENCE 家族校验。手改 durable 文件插入一条伪造 attribution 的 control 事件（identity/versions/accountability 全部偏离 adopted pin，其余合规），双侧 checker 0 错接受、`adopt.Open` 正常恢复——一条"14-A4 撤销拒收"审计事实被归因到伪造的 session/skill/role（或把拒收嫁祸给受害 principal），永久驻留审计链。effect 事件同形攻击会被拒（`ATTRIBUTION_DIVERGENCE`，其存在理由即 "absorbing one forges the audit trail"，ledger.go:336-340）——同一攻击经 control 通道放行。E3 扩展传播了 status-family/idem-forbidden/grammar/grants/lockstep，独漏 attribution（review-loop 第 4 步同族穷举的缺口实例）。
- 可达性：本地构造（手改 durable 文件——正是 checkLoaded 声称防御的威胁模型："A file this machine did not write … fails the open"，adopt.go:185-193）。
- 探针（①确定性，已执行）：
  - checker 级：identical 文档（adoption+adopted → control/rejected+伪造 versions/accountability）→ Go `Errors` 返回 0 错、Python `ledger_errors` 返回 0 错（本轮亲跑）。
  - 机器级：同文件 `adopt.Open` 成功、state=adopted、events=2（本轮亲跑）。
  - 修复后红形态：attribution 规则扩展到 control 事件后，同文档双侧报 `[LEDGER.ATTRIBUTION_DIVERGENCE]`（新 invalid 夹具 `_expect_match` 即可永久钉住，两侧 oracle 同名码位）。
- 判定：CONFIRMED（①已执行，当前态即缺陷态的确定性展示）。

### M-2【Consistency + 契约证伪】transition loop 双侧 guard 在 control 事件上分叉——聚合契约的「组合分歧点排他性」声明被同文档两侧异象证伪

- 位置：`go/internal/ledger/ledger.go:276`（`if e.EventType != "effect"`——control 被跳过）vs `schema/ledger.py:159`（`if e["event_type"] != "adoption"`——control 进入 transition switch）。
- 机理：两类型世界（adoption/effect）下两种写法等价；E3 引入第三类型后等价性破灭。合法 status（"rejected"）下 switch 无分支命中、行为碰巧一致；**effect 族 status 越界时**：Python 会让 control 事件驱动 state 变更（如 status "dispatched" → state[op]="dispatched"），使后续本应 ILLEGAL_TRANSITION 的 effect 事件变"合法"；Go 则维持 machine 语义（control 不转换）。反向形态（control+"adopted"）Go 变 state、Python 不变。
- 行为后果：verdict（收/拒）两侧不变——都拒——但错误集合分叉：同一文档（adoption+adopted → control/status="dispatched" → effect/completed）Go 报 `[STATUS_FAMILY]+[ILLEGAL_TRANSITION]`、Python 只报 `[STATUS_FAMILY]`（本轮亲跑实证：Go 2 错 / Python 1 错）。两侧 docstring 的聚合契约（`ledger.go:177-185`、`ledger.py:22-30`："the code-rule families aggregate in the same order on both sides … error-set composition may differ on documents violating those two [float-syntax / typed-view-parse]"）被证伪：该文档两条声明点均不违反，错误集合仍分叉。错因钉（`_expect_match` wrong-reason 纪律）在此文档类上可fork——同钉 Go 过 Python 拒（或反），双套件一侧假红。
- 可达性：本地构造（多违规文档；语料纪律 single-violation 之外，但契约文本声称约束的正是全部组合面）。
- 探针（①确定性，已执行）：上探针亲跑，两侧输出异象即红。修复后红形态：Python guard 对齐 Go 语义（非 effect 跳过 switch）后两侧错误集合一致；或双侧 docstring 如实声明第三组合分歧点（契约诚实化路线）。
- 判定：CONFIRMED。

### minor（积累不修，按律入台账）

1. **【Fidelity】t1Spec 的跨层等价宣称失实**：`go/internal/e2e/t1_llm_test.go:77-78` 宣称 t1Spec 是 "exactly the semantics the T0 stand-in embodies"，但 C8 输入类（资产报告缺失+历史严重逾期）上两 S1 实现分歧：`e2e_test.go:48-51` s1Judge 先查 assetReportOK → on_missing_evidence；t1Spec Precedence 0（`t1_llm_test.go:82-84`）+ C8 hardBar 期望 deny。确定性探针：调 s1Judge 即红。注：minor-ledger L21 记录的是 T0 替身「部分面」（窗口/带间未入场景），与此（优先序分歧+等价宣称）不同面。
2. **【Bearing】drive 的 fail-loud 网未覆盖 E3 refuse 写路径**：`go/internal/replay/replay.go:459` 守卫按字符串 `"ledger append failed"` 匹配（commit 路径 `adopt.go:424` 的报文）；refuse 路径 append 失败报文为 `"(refusal not recorded: …)"`（`adopt.go:457`），不匹配 → refuse 写上的 I/O 故障被当合法拒收、以 divergence 判定收场——正是该守卫注释自己禁止的形态（"treating it as a legal refusal would forge a divergence verdict"，replay.go:455-458）。可达性：mid-run 故障注入（本地构造/趋零）。确定性探针可构造（adopt 成功后 chmod 目录只读再触发 refuse 路径）。与 commit 路径的 TestScratchWriteFailureIsLoud 不对称——E3 新写路径未入既有 fail-loud 网。
3. **【Consistency】EVENT_BEFORE_ADOPTION 报文失标**：`ledger.go:377` 非 adoption 分支硬编码 "effect event"——control 事件前置于 adoption 时（夹具 control-before-adoption.json 实走此分支）报文把 control 标成 effect；Python 镜像同文案（`ledger.py:254`）。码位/拒绝行为均正确，纯文案（同 L18 族）。
4. **【Simplicity/健壮性】T1 harness 超时预算越界**：`t1_llm_test.go:238` 每调用 180s × 2 attempts × 12 case，最坏 72 分钟 ≫ go test 默认 600s 包超时；launch 命令（`t1_llm_test.go:10-12`）未带 `-timeout`。慢端点下用户得到 timeout panic 而非干净读数（fail-loud 但失因）。命令级修复即可。

四镜归属汇总：M-1=Bearing（doc↔code 承重）+同族穷举；M-2=Consistency（双侧镜像漂移）+契约证伪；m1=Fidelity；m2=Bearing；m3=Consistency；m4=Simplicity。多镜独立命中：M-1/M-2 同被 Consistency+ Bearing 两镜覆盖（词表增长×手镜像规则位点族），可信度上调。

---

## 三、Singularity 判决

**族复发 ≥2 成立（本增量内两次），触发升级条款。**

- 族名：「事件类型词表增长 × 手工镜像规则位点传播不完整」。E3 引入 control 类型需同步传播到每侧约 8 个手镜像规则位点（status-family、idem-forbidden、needs-idem、grammar、grants、transition、attribution、lockstep union）。实际传播：status-family ✓、CONTROL_IDEM_FORBIDDEN ✓、grammar ✓（EVENT_BEFORE_ADOPTION 恰好覆盖 control）、grants ✓、lockstep union ✓、**transition ✗（M-2，双侧分叉）**、**attribution ✗（M-1，双侧漏）**。同根两成员=族复发 2 次。
- 结构病灶：规则行为按 event_type 字符串字面量散布在两侧各 ~8 个手写位点，词表每次增长都重演"漏点/错点"；与本仓慢性结构模式同源（R2 m-3 双内联 runner、R17 B-1 未键控镜像、check_lockstep 本身的存在、L16 durableMode 双份）。
- 结构方向（候选，未启动）：①每侧一张「event_type × 规则家族」分派表（单一真源，新增类型=表加一列，漏传播不可表达）；②把 check_lockstep 式机械 parity 网从 schema 原子扩展到规则位点枚举（新夹具族或生成）。无「问题被重定义」级奇点候选；本增量最便宜杠杆是规则位点 parity 网。
- 按律提示：结构转移自身引入缺陷（~30% 量级先例）——若升级，转移后须强制一轮全强度外环+证伪器再生。

---

## 四、总裁决

**2 M / 4 minor / 0 B；机械门全绿。**

- M-1：control 事件绕过 attribution-divergence 规则（双侧+Open 实证，①确定性探针已执行，CONFIRMED）；
- M-2：transition loop 双侧 guard 分叉、聚合契约排他性证伪（①确定性探针已执行，CONFIRMED）；
- singularity：族复发 ≥2 成立（词表增长×手镜像规则位点），建议按 review-loop 第 4→架构条款升级结构；
- minor ×4 积累不修（入台账候选：建议顺延编号 L23-L26）。

按退出判据：本轮非 0B/0M——连胜重置，M-1/M-2 须先进证伪耦合修复循环（红探针方案已附）再计连胜。
