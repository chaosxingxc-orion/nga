# 18-blank-r9 — 退出叠加守卫轮（全强度外环，连胜第 3 轮）

审核位：空白 agent（不携带任何先前结论；未读 impl-2026-11-01/ 下任何已存在文件、未读 BATTLEFIELD.md、未访问 ~/.zcode/、无网络、无 T1_* 变量）。
被审对象：`git diff baca2dd..HEAD` 全部（16 笔提交：P1-1 权限修复 / P1-2 断尾教义统一 / E3 control 事件 / R6 M-1+M-2 镜像对齐 / T0 两层 E2E / T1 真 LLM harness / 审核循环记账 docs）。
方法：review-loop 第 9 步（退出前最后一轮必须全强度外环）× 4-lens 四镜 + 严重度×可达性定级 × singularity 族复发判据。

---

## 一、机械门（全部通过）

| 门 | 结果 |
|---|---|
| `cd go && go build ./...` | PASS |
| `go vet ./...` | PASS |
| `go test -count=1 -race ./...`（未设任何 T1_*，先 grep 确认环境零 T1_） | 21 包全 ok；`TestT1RealLLMS1` 无 T1_ 时默认 SKIP（正确形态，单独复跑验证） |
| `python3 schema/_suite.py --self-test` | PASS |
| 逐模块：validate / ledger / adoption / judgment / release / replay / compose / evidlog | 全部 0 failures（ledger 9+33；adoption 2+5；judgment 2+19；release 3+14；replay 8+9；compose 10+36；evidlog 1+6） |
| `python3 tools/corpus_manifest.py --check` | OK（committed block == regenerated manifest） |
| 测试面计数 | **218 个 Go Test 函数**（baca2dd 基线 201 → +17：adopt 5 / evidlog 2 / replay 1 / e2e 9——恒积累 ✓） |

前置门（编译+测试+测试面恒积累）全过，评审有资格进行。

## 二、增量审查范围（实际过目的代码面）

- `go/internal/adopt/adopt.go`（全文重点段：Open/tornTail/TornTail/Dispatch/MarkUnresolved/finish/commit/refuse/append/durableMode）
- `go/internal/ledger/load.go`（全文：ParseLines torn 语义）、`ledger.go`（Errors 全规则族）
- `go/internal/evidlog/evidlog.go`（Append 全路径 + durableMode 孪生）
- `go/internal/replay/replay.go`（Inspect/Recover/Replay/Reevaluate/drive/eventsEqual）
- `go/internal/e2e/`（doc.go + e2e_test.go T0 九场景 + t1_llm_test.go T1 harness 全文）
- `schema/ledger.py`（全文）、`event-ledger.schema.json`、六个新夹具（含 `_expect_match` 钉）
- 测试增量（adopt_test/evidlog_test/replay_test/main_test 计数钉）
- docs：conformance-fixture-format.md / minor-ledger.md / schema/README.md（doc↔code 交叉）

### doc↔code 交叉维度核验（全一致）

- 夹具计数钉三处互洽：docs 表 9+33（合计 157 / 全仓 211）== Python 钉 (9,33) == Go main_test 钉 == manifest 再生成。
- minor-ledger 已登记 L23-L26 逐条对码复核**全部属实**（见 §四）。
- schema/README.md「rejected（control 事件承载）」== E3 实现（ControlStatuses + CONTROL_IDEM_FORBIDDEN + transition skip）。
- e2e doc.go 宣称的 §11.B 八场景 + happy path == 9 个测试函数一一对应。
- refuse() 注释宣称「checker's transition loop skips them / CONTROL_IDEM_FORBIDDEN」== ledger.go:276-281 / ledger.go:318 实况。

## 三、Findings（本轮）

**BLOCKER：0。MAJOR：0。**

新增 minor 4 条（按律只积累入台账，不进修复循环，不重置连胜）：

### m-1（Fidelity 镜｜文档声明-实态差｜本地构造）
`go/internal/adopt/adopt.go:175-183` — `TornTail()` 文档宣称「While true the machine is read-only: **every mutation is refused** until the file is repaired and the machine is re-Open」。实态：该宣称只在「未修复」窗口成立；**外部修复后未 re-Open 的窗口**里 flag 仍为 true，但 Adopt / MarkUnresolved / finish 的变更可以成功——append 的写时复核（adopt.go:506-517 tornNow + :518-535 seq 门）看的是字节真相，修复后的字节健康且 seq 连续，写入通过；只有 Dispatch 被 flag 入口门（adopt.go:345-348）拦下。方向安全（写时字节级验证兜底，恰是教义自己说的「the bytes are the truth」），但文档把「字节级可验证的写」说成了「全部拒绝」。复现：构造 torn → 外部修复回原字节 → 不 re-Open → 同一 Machine 实例调 Adopt（成功）与 Dispatch（拒绝）对照。severity=minor（文本与行为差，无不良行为后果）。

### m-2（Consistency 镜｜同因异形报文族｜git 可跟踪）
同一 torn 条件四种报文形态：①Dispatch 入口门（adopt.go:345-348）纯散文无 `[键]`；②append 写时复核（adopt.go:515-517）`[ADOPT.TORN_TAIL]`；③refuse 路径包装（adopt.go:456-458）`(refusal not recorded: [ADOPT.TORN_TAIL]…)`；④Adopt/commit 路径（adopt.go:287-288/326-328/423-425）`ledger append failed: [ADOPT.TORN_TAIL]…`。按错误键过滤的宿主在①形态下失配。行为全部一致（rejected、零写入、零状态变更）。severity=minor（与已登记 L24 同域不同面：L24 是 fail-loud 网漏接，本条是键族不齐）。

### m-3（Bearing 镜｜测试面缺口｜git 可跟踪）
E3 的 replay 层面零探针：`schema/examples/replay/{valid,invalid}` 中含 `"control"` 事件的夹具为 **0**（grep 实测）。机器层（TestRefusalWritesControlEvent 等 3 处）、checker 层（6 个新 ledger 夹具）、e2e Inspect 层（TestT0RestartWhileWaiting 对含 control 流的 gaps==0 断言）均已钉；唯 mode-2 重驱（replay.go:434-464 drive）+ eventsEqual 对 control 事件的等值比较无夹具。E3 后一条含拒收步骤的真实 run 其 record 必含 control 事件——该面当前无红探针护体。severity=minor（覆盖缺口，非缺陷）。

### m-4（Fidelity 镜｜doc 指针脆性｜git 可跟踪）
`go/internal/e2e/t1_llm_test.go:10-12` launch 命令把密钥路径硬编码为 `providerRules[4]`（~/.zcode/v2/provider_config.json 的第 5 条规则）。配置重排后静默指向别的 provider 的 key——失败形态是响亮的（HTTP 401 → harness fail-loud 门 → FAIL 非静默绿），无错误结果风险，纯文档脆性。severity=minor。

## 四、对既有登记 minor（L23-L26）的独立复核——全部属实

- **L23** ✓：t1_llm_test.go:78-79 宣称「exactly the semantics the T0 stand-in embodies」，但 s1Judge（e2e_test.go:48-65）先查缺证、t1Spec 优先级 0 压缺证——C8 形输入两 S1 实现分歧（on_missing_evidence vs deny），等价宣称不实。
- **L24** ✓：drive 的 fail-loud 网（replay.go:459）只匹配 `ledger append failed`；refuse 路径 append 失败报文是 `(refusal not recorded: …)`——mid-run I/O 故障在 refuse 路径可被当合法拒收。commit 路径有 TestScratchWriteFailureIsLoud，refuse 路径无对称探针。
- **L25** ✓：EVENT_BEFORE_ADOPTION 非 adoption 分支（ledger.go:382-384；Python ledger.py:262-266 同形）报文硬编码「effect event」——control 前置时行为正确但文案错标（双 oracle 同形，非分叉）。
- **L26** ✓：t1Call 180s×2 尝试×12 用例最坏 72min ≫ go test 默认 600s，launch 命令未带 `-timeout`。

## 五、对抗验证记录（假阳性过滤——被 REFUTED 的候选）

1. **「replay.go:290-293 注释在 E3 下失效」**——REFUTED：注释字面仍真（非拒收步恰发一事件）；E3 使带身份的拒收步也发一事件，反而**收窄**了破坏「事件下标==步下标」重合的步形集合（只剩无身份拒收步零事件）。非漂移。
2. **「Open 与写之间注入合法外源事件可穿透 seq 门」**——REFUTED：外源事件 seq == m.seq（复尾）→ 重写后下次 Open 被 SEQ_NOT_INCREASING 响亮拒绝；seq == m.seq+1 → STALE_WRITER 当场拒绝。全路径 fail-loud。
3. **「Python `e.get("idempotency")` 对空 dict 假值 vs Go 非空指针判定分叉」**——REFUTED：空 idempotency 对象被 schema required（operation_id/payload_digest）先行拒绝，schema 合法文档上两 oracle 同判。
4. **「ParseLines torn 边界漏洞」**（尾随空格/多空行/带换行垃圾/`{}` 尾行/纯 torn 文件五种形态逐一推演）——REFUTED：分别落入 torn=true / 空行容忍 / 硬错误 / checkLoaded 拒绝 / (nil, torn, nil) 五个既定分支，与文档声明一致。

## 六、Singularity 判决

- **族复发判据现状**：「事件类型词表增长 × 手镜像规则位点传播不完整」族在本战役内已复发 **≥2**（M-1 attribution 漏 control + M-2 Python transition 分叉——已在 minor-ledger L26 的 singularity 登记块中立案，结构方向候选=①每侧 event_type×规则族分派表 ②规则枚举 parity 网，未启动）。≥2 触发条件成立，按律该族**停止打补丁、升级换结构**——但结构转移属新战役，立案归档为正确处置（R15/R17 先例：候选档不阻塞收卷）。
- **本轮族复发检查**：无新复发。我对两侧 oracle 的全部规则位点做了穷举对照（STATUS_FAMILY / GRANTS_ON_NON_ADOPTED / ILLEGAL_TRANSITION / CONFLICT+CONTROL_IDEM_FORBIDDEN / IDEM_REQUIRED / IDEM_IDENTITY_MISMATCH / ATTRIBUTION_DIVERGENCE / DOUBLE_ADOPTED / EVENT_BEFORE_ADOPTION / SEQ 三族）——control 事件在每一位点的传播均已到位且被夹具/测试钉住（含 R6 M-2 的跨 oracle 错集钉：control-effect-status-transition 的 `_expect_match: LEDGER.ILLEGAL_TRANSITION` 把双侧错集分叉钉死）。
- **奇点后义务**：本增量不含结构转移（E3/R6 是补丁级修复），不触发奇点后全强度义务；本报告本身即增量后的全强度外环。

## 七、总裁决

**0 BLOCKER / 0 MAJOR / 4 新增 minor（m-1 文档过颁、m-2 报文键族不齐、m-3 replay 层 control 探针缺口、m-4 T1 launch 指针脆性）+ 4 条已登记 minor（L23-L26 复核属实，按律积累不修）。**

- 机械门：全绿（build/vet/-race 21 包/Python 八组+self-test/manifest；测试面 201→218 恒积累）。
- R7、R8 两轮 0B/0M + 本轮 0B/0M = **连胜 3 轮，按 3 连口径：可收卷**。
- 收卷附带：m-1~m-4 入 minor 台账；singularity 候选（event_type×规则族分派表 / 规则枚举 parity 网）随卷归档，授权到来→新战役开卷；L24 与 m-3 同属「E3 拒收路径的下游消费面网」——若未来启动结构战役可合并考虑。
- 诚实边界：本报告的 B/M=0 结论以机械门全绿 + 上述四镜穷举为背书；torn/E3/P1-1 三条承重线各有活探针（TestCrashRecoveryTornTail 反转钉、TestRefusalWritesControlEvent+6 夹具、双包 umask/StatError 探针），守恒律未发现违例（本轮探针存量净增 17）。
