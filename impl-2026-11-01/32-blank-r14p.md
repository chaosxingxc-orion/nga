# 32-blank-r14p — 空白审核位全强度终审（R14' 增量：baca2dd..HEAD）

审核位：空白（不携带先前结论）。对象：`/Users/yaojun/nga-impl-wt/agent-festival`，`git diff baca2dd..HEAD` 全部（约 24 笔提交：P1 权限修复 / 断尾教义统一 / control 事件（E3）/ polarity guard / E0-E3 正确性实验 / T0 十场景 / T1 harness / T2 参考宿主 + 场景 R+K / brID 修复）。重点=T2 宿主层（`go/internal/e2e/t2host_test.go` + `t2host_rk_test.go`）。方法=review-loop 十步中的外层全强度步（4-lens 四镜 + doc↔code 交叉 + singularity）。禁读件（impl-2026-11-01 既有文件、BATTLEFIELD.md、~/.zcode）全程未读。

---

## 一、机械门（全部实跑）

| 门 | 结果 |
|---|---|
| `go build ./...` | OK |
| `go vet ./...` | OK |
| `go test -count=1 -race ./...`（无任何 T1_* 变量） | **20 包全 ok**（e2e 包含在内；T1 真实 LLM 测试按设计 skip） |
| `python3 schema/_suite.py --self-test` | PASS |
| `validate.py`（无参夹具套件） | 0 failures |
| `ledger.py` | 9 must-accept + 33 must-reject，0 failures |
| `adoption.py` / `judgment.py` / `release.py` / `replay.py` / `evidlog.py` | 各自 0 failures |
| `compose.py` | 10+36，0 failures，count-pin 过 |
| `python3 tools/corpus_manifest.py --check` | OK（committed block == regenerated） |

**测试面计数（守恒读）**：Go 测试函数全仓 232；e2e 包顶层 Test：t2host_rk 8、e2e_test 10、correctness_probe 5、t1_llm 1（t2host_test.go 0 个顶层 Test，全是被测夹具工件）；schema 夹具 ledger 9+33（上轮 8+28，+6）、compose 10+36（钉）。**相对上轮只增不减——恒积累成立**。

注：`validate.py`/`compose.py` 无 `--help` 通道（arg 被当文件名），traceback 后 rc=0——`rc=$?` 在管道后失真，以无参实跑 rc=0 为准（ cosmetic，不计 finding，属调用习惯）。

---

## 二、Findings

### MAJOR（1 项，进修复循环）

#### M-1 adopt 写时复核对「合法 JSON 对象、非机器事件」形态的外部损坏不设防——假成功 + 与双子（evidlog）形状门不对称 + 与自身教义声明矛盾

- **四镜**：Bearing（写时门的承重声明与行为脱节）+ Consistency（同族双包 P1-2「unified doctrine」两侧分类器漂移）+ Fidelity（`load.go` 边界注释承诺的行为未被实现）。
- **file:line**：
  - `go/internal/adopt/adopt.go:510-517`（写时 torn-tail 复核，声明「out-of-band damage between Open and this write is caught here」）与 `adopt.go:150-154`（教义段「The append path re-checks the bytes at write time, so out-of-band damage between Open and write is caught too」）；
  - `go/internal/ledger/load.go:63-67`（typed view 接受分支：`json.Unmarshal(line, &ev)` 不带 `DisallowUnknownFields`，**未知字段对象/缺必备字段对象被当作完整事件行接受**）与 `load.go:31-34`（同一函数头注释声明「a line whose JSON parses but whose fields do not fit the event type … it fails」——`{"note":"x"}` 无任何事件字段却通过，注释与行为矛盾）；
  - `adopt.go:519-535`（STALE_WRITER 门只看**最后一行**的 seq——mid-file 插入的 phantom 行完全绕过两道写时门）。
- **行为链（代码迹线，逐行核过）**：外部在两次机器写之间向 durable 文件插入一行换行结尾的 `{"note":"out-of-band"}`（或任何 unmarshal 进 `Event` 但违反 schema 的 JSON 对象）→ 下一次 `Adopt/Dispatch/finish` 的 `append`：`ParseLines` 把 phantom 行收进 `parsed`（`load.go:66-68` 第一分支）→ `tornNow=false` → STALE_WRITER 门取 `parsed[len-1]`（真事件）seq，通过 → rebuild **逐字节保留 phantom 行**并追加新事件 → **写返回成功**。下次 `Open`：`checkLoaded` 跑 `ledger.Errors` → schema（event 级 `additionalProperties:false` + required，已实查 schema JSON）拒绝 phantom → **文件永久无法 resume，须手工修**。机器自己写出的/保留下的文件，自己的 loader 拒收——正是 `adopt.go:96-99` 给 STALE_WRITER 门定罪的原句形态（"a false success that poisons the file (detectable at the next Open)"，R11 以 MAJOR 立门把这类失败逼回 guilty caller），phantom 形态绕过了这道门。
- **双子不对称（加重项）**：P1-2 宣称两侧教义统一、adopt 写时门自称「the adopt-side twin of evidlog's R10 face-B byte re-check」（`adopt.go:511`）。实证 evidlog 侧**有形状门**：`evidlog.go:602-626 entryShapeError`（required keys + 非空 + seq 类型）挂进 `loadLines`（`evidlog.go:570-584`：mid-file phantom → `NON_OBJECT_LINE` 硬拒；EOF phantom → tail garbage → torn=true → 拒一切写）与 `conformantLine`（`evidlog.go:632-646`，写时复核用）。同一损坏字节：evidlog 判「拒写」，ledger/adopt 判「合法事件行、写成功、保留」——同一教义两个分类器，phantom 形态在 adopt 侧不可表达地漏网。
- **可达性**：**本地构造**（Open 与写之间对 durable 文件的外部位写——这正是 P1-2 教义自己点名的威胁模型，与已被处理的 torn-tail/invalid-UTF-8/不可解析三形态同模型同等级；非趋零）。根因（typed view 非严格接受）系预存（R2 时代），但**失实的覆盖声明与写时门是本增量新写**（R11/P1-2），按审增量口径入循环。
- **红探针方案（①确定性，一跑即红，in-package 测试两发）**：
  1. 主探针：`m := Open(p)` → 两次 `Adopt`（两行事件）→ 外部在第 1/2 行之间插入 `{"note":"out-of-band"}\n` → 断言 A：第三次 `Adopt` 必须 `rejected`（教义：Open 与写之间的外部损坏必须在写时被拒）——现状 returned `adopted`，**红**；断言 B：`adopt.Open(p)` 必须成功——现状 fail（"durable form rejected at load"），**红**。双断言双红，一次运行。
  2. 姊妹探针（EOF 形态）：追加 `{"arbitration_seq":<last>} \n`（seq 与最后一行相同→want=last+1 恰等于机器下一个 seq，两道门全过）→ 同型双红（写入成功 + `SEQ_NOT_INCREASING` 拒 re-Open）。
  - 修法方向（同族穷举）：在 `ParseLines` typed view 加严格形状判定（`DisallowUnknownFields` + 必备字段存在性——对齐 evidlog 的 `entryShapeError` 单表双消费形态），或在 `append` rebuild 前对每行跑 `ledger.Errors`；两发探针即永久守卫。修时注意 EOF-no-newline phantom 的三态归属（torn vs bypass）须与 evidlog 对表后统一，避免修出第三种分类。

### MINOR（积累不修，9 项）

| # | 位置 | 内容 | 镜 | 可达性 |
|---|---|---|---|---|
| m-1 | `go/internal/e2e/t2host_rk_test.go:104-132` | `TestT2R_PermissionRevoked`：名称+头注释宣称「read permission is revoked — the stored result is NOT returned」，测试体**零撤销动作、零拒绝断言**（只正向验证 store 有结果；尾部注释自认 registered gap）。验收面向的覆盖宣称与兑现为 0——改名（如 `...ResultPresentAuthorizationIsHostsCall`）或补宿主侧授权判定面。探针：宿主侧 `serveStoredResult(caller, op)` 类函数当前不存在，「撤销拒绝」行为写不出可编译探针=覆盖为零的机械证明 | Bearing | git 可跟踪（读测试清单即触） |
| m-2 | `t2host_rk_test.go:137-142, 220-224` | 同测头注释「the FOUR READS are asserted independently」实际 3/4——READ 4 无断言，且注释「already verified in READ 2」错置（READ 2 是 store 投影非知识方法消费；全程未 publish 任何 method，「corrected method is consumed」在此测不可测）。198232012 §四 How 的四读承诺兑现 3/4 | Bearing/Fidelity | git 可跟踪 |
| m-3 | `t2host_test.go:3-5` | 头注释宣称三组件「node entry, result store, failing adapter probes」——**node entry 不存在为命名工件**（重提交逻辑内联在测试体：State 检查+store.get）。doc→code 缺证据 | doc→code | git 可跟踪 |
| m-4 | `t2host_test.go:111-120` | `lookupByBusinessRequest` 用字典序比 evaluation_revision：er-10 < er-2 错序；同 rev 并列时 map 迭代序不定（投影结果不确定）。注释自declare 词典序假设——er-9 以上即破 | Consistency | 本地构造 |
| m-5 | `t2host_test.go:206-215` + `t2host_rk_test.go:294-323` | `findForNode` 多 valid 方法同 node 时 map 迭代序不定；`Replaces` 字段无机制消费——supersede 靠测试直改 map 的 `Valid`，registry 无 invalidate/retract API。注释「expired/**superseded** methods are not consumed」只兑现 validity 半边 | Consistency | 本地构造 |
| m-6 | `t2host_test.go:176-178` | `knowledgeMethod.execute` 用 `fmt.Sscanf` 静默吞解析失败（`"abc"`→0→不触发 veto，无告警）——静默吞是自家 SETools 纪律点名的形态 | Fidelity | 本地构造 |
| m-7 | `t2host_test.go:63-90` | `resultStore.put` 非原子写（无 temp+rename）且损坏时**整体拒载**（无 ledger 式边界投影）——put 中途进程崩溃丢全店收据；fail-loud 但数据丢失，与同增量给 ledger 立的 P1-2 教义不同档。夹具自declare 非生产件，故 minor | Bearing | 本地构造 |
| m-8 | `t2host_test.go:300-320` + `t2host_rk_test.go:167-180` | T2 店与账本双持久形态**无一致性交叉核**：adopt 成功后 store.put 前的崩溃窗口让有效性投影（store-only）静默回退到陈旧结果——「当前有效」权威分裂，无夹具钉该窗口 | Bearing | 本地构造 |
| m-9 | `go/internal/e2e/correctness_probe_test.go:175-227`（对照 36-40, 99, 266, 345） | E0 extraction-miss 病态断言测试**缺 polarity guard 开关**（家族 2/3：SickS1 与两个 E3 测有 `correctnessLayerLanded`/`p3FixtureCorrectionLanded` skip，本测无）——正确性层落地时它将以裸红而非带说明的 skip 出场。R11/R12 两轮修的都是同族（guard 缺失），这是第三员 | Consistency | git 可跟踪（层落地即触） |

另记 2 条不计 finding 的同步提醒（派生数据/文本类）：`correctness_probe_test.go:271-274` 对 fixture 缺失用 `t.Skipf`（路径漂移时 E3 证明无声消失，非 -v 不显 SKIP——E3 是实验性测试可接受，若转正建议改 Fatal）；`TestT0FastPathFullHitZeroModelCalls` read-face 直调 `bankAPISubmit` 绕 harness 计数——**minor-ledger L31 已登记同域**，不重复报。

---

## 三、对抗验证记录（M-1 的反驳尝试，全部失败）

1. 「append 时会跑 checker 兜底吗」——否：`append` 只做 ReadFile+ParseLines+tornNow+STALE_WRITER，无 `ledger.Errors`（`adopt.go:486-535`）。
2. 「schema 能在写时挡吗」——否：schema 只在 Open 的 `checkLoaded` 跑；event 级 `additionalProperties:false` 已实查（python 读 schema 确认），意味着 phantom 必死在**下一次** Open 而不是本次写。
3. 「STALE_WRITER 门会误中它吗」——仅 EOF 追加且 seq 不匹配时挡住（want 由最后一行 seq 决定）；mid-file 插入与 EOF+匹配 seq 两形态全绕过。
4. 「evidlog 是否同样漏」——否：`entryShapeError`/`conformantLine` 在 mid-file 硬拒、EOF 判 tail garbage=torn 拒写；adopt 侧无对应物。四路反驳皆不成立，按确定性口径 CONFIRMED（代码迹线级；本审核位受「唯一写动作=报告」约束未落可执行探针——探针方案已在上文预注册，落地后一跑即红即最终盖章）。

---

## 四、Singularity 判定

**写时字节复核覆盖族第三次现身，族复发 ≥2 条款触发**：R10（evidlog face-B byte re-check）→ R11（adopt STALE_WRITER）→ 本轮 M-1（phantom 对象行绕过两门）。前两员都是守卫补丁修复；第三员证明补丁式逐形态堵漏在该族**不可收敛**——损坏形态空间（torn/UTF-8/不可解析/phantom/伪造一致事件）每员一个门，门与门之间必有缝。结构方向（登记候选，不由审核位执行）：**把「一行是什么」收敛为单一判定表**——`ParseLines` typed view 与跨事件 checker 共用同一形状判定（evidlog 的 `entryShapeError` 单表双消费是仓内现成范式），让「新损坏形态漏网」不可表达：每行输出恰为三态（合规事件 | torn | bypass），两侧（adopt/ledger 与 evidlog）共享同一分类器。与 minor-ledger 已登记的「event_type×规则家族分派表」候选同向不同位，可并入同一场结构战役。按律：结构转移自身引入 ~30% 新缺陷，若启动须转移后全强度外环 + 证伪器再生。

其余面（E3 control 事件三层传播、P1-1 durableMode 双包、断尾教义、T0/T1 场景面、schema lockstep）四镜+交叉维度均未见新 B/M——R6 的「词表增长×手镜像位点」族本轮零复发（Python/Go 双侧 8 个镜像位逐一对过）。

---

## 五、总裁决

**1 BLOCKER 免；1 MAJOR（M-1）+ 9 minor。** 机械门与测试面恒积累全绿；T2 宿主层场景 R/K 的控制语义链路（R12' brID 修复、persisted receipt、conflict 拒覆盖、K 零调用、correction 四读）行为面兑现良好，但 T2 层的**验收面向文本承诺**（PermissionRevoked 场景、四读独立性、node entry 组件）有 3 处兑现缺口（m-1/m-2/m-3，全部 minor、建议在交付叙事前改名或补述）。M-1 是本增量新写的写时门声明与行为的实质缺口：外部损坏的 phantom-JSON 形态获得假成功并毒化文件，且与它自称的 evidlog 双子行为不对称——按 R11 自家先例定 MAJOR，红探针确定性一跑即红，随附结构转移候选（形状判定单表化）。连胜以本轮 1 MAJOR 计为重置；minor 9 项全走台账积累不修。
