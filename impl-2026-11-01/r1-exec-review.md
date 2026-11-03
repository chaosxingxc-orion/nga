# R1 空白审查：执行批七件（E1-E7）——4-lens + singularity

审查人：空白子智能体（无历史上下文，只读仓 + /tmp 变异实验）。
范围：`~/nga-impl-wt` 七笔提交 c42c108 / b790fac / ca0c36a / 4c8817a / 3bafda9 / 0486ba7 / 1282873。
日期：2026-11-01。结论先行：**2 BLOCKER / 3 MAJOR / 8 MINOR**。七件中 E2、E7 干净；E4 的核心交付（判定域钉）经机械反证**不成立**；E1 立的计数法在同批内即被 E4/E6 破坏。

---

## 一、实跑与机械验证记录（全部可复现）

| 验证 | 结果 |
|---|---|
| 八 oracle（validate/ledger/adoption/judgment/release/replay/compose/evidlog） | 全 rc=0 |
| `go test -count=1 -race ./...`（go/，20 包：19 有测 + evidlog 无测文件） | 全 ok |
| `go vet ./...` / `go mod tidy` | 净 / 无漂移 |
| `examples/java-consumer ./run.sh` | SPIKE-GREEN（双臂、64/64 钉、loader 自检过） |
| 变异①：删 E3 键 [LEDGER.CONFLICT_IDEM_FORBIDDEN]（Go）+ [LEDGER.DOUBLE_ADOPTED]（Py） | 双侧 RED ✓ 守卫在 |
| 变异②：删 E4 夹具 seq-odd-float-twin.json | Py rc=1 + Go internal/ledger RED ✓ 守卫在 |
| 变异③：删 E6 密度规则（Go CheckDoc + Py evidlog_errors） | 双侧 RED ✓ 守卫在 |
| 变异④：整体删除 CheckCoverage+Declaration+CoverageReport | **全绿——零守卫**（见 M2） |
| 变异⑤：双侧删 [LEDGER.DIGEST_CHANGED_UNDER_KEY]（无钉之键） | **全绿——该键无守卫**（见 m4） |
| 精确十进制 oracle 模拟（Decimal 解析 + 同规则集）跑 ledger 全语料 | 四条 seq 族夹具判决与 float64 oracle **完全相同**——语料中不存在区分两种判定域的夹具（见 B1） |

---

## 二、分级 findings

### BLOCKER

```
[BLOCKER][声称-现实/机理][E4] 奇数孪生夹具发的是「偶数孪生」——判定域钉空转，且合同文本的拒收机理是假算术
证据: agent-festival/schema/examples/ledger/valid/seq-odd-float-twin.json（字面 arbitration_seq 三元组: 9007199254740991 / 9007199254740992.0 / 9007199254740994）
      同文件 _expect（自称 "..993.0 (float syntax) folds to ..992"）；docs/conformance-fixture-format.md §3 判定域声明（"精确十进制读者会判 ..993.0 > ..994 而 REJECT"）；go/internal/ledger/ledger_test.go:110-112 注释（"9007199254740993.0 folds to 9007199254740992"）；4c8817a 提交信息
机理: 文件里的浮点字面量是 9007199254740992.0——偶数、float64 精确可表示、无任何折损差；而夹具 _expect、提交信息、Go 测试注释、格式文档 §3 四处叙事全部描述 9007199254740993.0（奇数、折损到 ..992）。按文件现状：精确十进制域与 float64 域对 [..991, ..992.0, ..994] 判决完全一致（都 ACCEPT），夹具不区分任何域——「钉 float64 判定域」这一 E4 全部交付目的落空。机械反证：用 Decimal 精确域 oracle 重放 ledger 全语料，判决与现实现零分叉——把实现的判定域整体换成精确十进制，全部测试与夹具仍然全绿（无任何守卫）。此外 §3 的拒收机理是假算术：精确十进制下 9007199254740993.0 < 9007199254740994（不可能 "> ..994"）；真正能让精确读者拒收的是 SEQ_FLOAT_BEYOND_EXACT 规则（9007199254740993 > 2^53），即便按叙事版本（..993.0）写回文件，§3 给出的机理句也是错的。这是合同文本（跨语言消费方读的就是这份文档）上的假陈述 + 「声称-现实漂移」本体：唯一能守域的字面量被四处描述、零处落地。
建议: 夹具字面量改回 9007199254740993.0（双侧 oracle 实测仍 ACCEPT 且自此真区分两域），§3/测试注释/_expect 的机理句改为「精确读者经 float-syntax 超 2^53 规则拒收」并补一条 invalid 侧反钉。
```

```
[BLOCKER][机理/广度][E1←E4,E6] 计数 manifest 法在立法后第二笔即破——HEAD 上文档 195/141/9+26 对目录 200/142/10+26，生成器自身也开始少数
证据: docs/conformance-fixture-format.md:3（"195 件…六增长族 141"）、:26（ledger 9+26）、:32/:34（141/195）vs 实测目录 200 件、增长六族 142、ledger 10+26、evidlog 4；tools/corpus_manifest.py:12（FAMILIES 硬编码六族，无 evidlog）——HEAD 重跑输出 142/50/196，仍不等于目录 200
机理: E4 声称「语料 9+26→10+26 三处钉同原子 rebase」，只 rebased D93 三处（cmd 测试摘要行 / ledger.py 元组 / schema/README），没碰 E1 刚立的第四处（manifest 块+手抄表+头部总数句）——E1 文档自己写着 "Run after any corpus change"，无任何 CI/自检强制（04-collision.md 主题 1 的第一性原理裁定「单源渲染+CI 对拍，失败即红」未被实现，只落了「注释+人跑」的弱形态）；E6 新增 evidlog 族后既未把族加进生成器 FAMILIES（生成器的「全仓合计」从此永久少数 4），也未动格式文档。E1 要杀的病（静默陈旧计数副本）在立法后同批内原样复发，且副本数比立法前更多：格式文档手抄表（陈旧）、格式文档 manifest（陈旧）、生成器（缺族）、Java spike ORACLE_PINS（196）、根 README「95 夹具」（见 m2）。
建议: manifest 块改为生成器渲染产物并加一条机械对拍（_suite 或 go test 皆可：重渲染≠文档即 RED），FAMILIES 改目录枚举，然后重跑一次把 HEAD 五处数字全部对齐到 200。
```

### MAJOR

```
[MAJOR][声称-现实][E3] 「13 键双侧都在消息首段头部」在 HEAD 仍不成立——Python 侧 3/13 在中部；E4 的「残留一处」也是少数
证据: schema/ledger.py:89-90（DIGEST_CHANGED_UNDER_KEY 插在 "carries payload_digest X" 与 "but an earlier event recorded" 之间）、:133-134（ILLEGAL_TRANSITION 插在 "status X after" 之后、from-state 之前）、:221-222（EVENT_BEFORE_ADOPTION 插在 "event for operation X" 之后）；对照 Go 侧 13/13 全在串首、Java 侧 13/13 全在串首
机理: E3 提交即带病（自身提交信息承认「多行 f-string 插点错段 4 处…修复」，但机械验证只做了「13 键双侧计数+docstring 零泄漏」，从未验证位置）；E4「附带修 E3 残留一处」实际只修了 ATTRIBUTION_DIVERGENCE 一处、漏掉同病三处——「残留一处」的计数本身错。功能面无损（钉按 contains 命中、Java 亦 contains），但这是把「位置」写进合同声明的提交，且三侧形态不一致（Go/Java 头部、Python 中部）正是下个消费者踩的坑。
建议: 三处移到各自消息串首（对齐 Go/Java 形态），并把「键在串首」写进 conformance 文档的钉语法一节而不是只写在提交信息里。
```

```
[MAJOR][机理/singularity][E6] CheckCoverage/Open/Append 是零守卫死代码——件7 主交付面没有一条测试摸过它
证据: go/internal/evidlog/ 包无任何 _test.go（go test 输出 "internal/evidlog [no test files]"）；grep 全仓 CheckCoverage/evidlog.Open 除包自身外零调用（cmd/evidlog/main.go:22 只消费 CheckDoc）；变异④整体删除 CheckCoverage+Declaration+CoverageReport 后 build 通过、19 测包全 ok、八 oracle 全绿
机理: E6 的卖点是「CheckCoverage 差集告警+排除记录反向核验——『没有矛盾材料』必须是显式声明」，但该函数在仓内零执行路径：没有单测、没有夹具、没有 cmd 消费。更进一层：CoverageReport.OK 只看 Missing（evidlog.go:CheckCoverage 尾部 `rep.OK = len(rep.Missing) == 0`）——「排除声明隐瞒了日志里另有查询」这一 E6 点名的对抗情形只落进 information 性 Unaccounted，机器闸门对此全盲。spike 边界（S2 不做）不豁免「交付声明必须可机械验证」——这正是 V2 singularity 教训（「shares 双向修复」两轮无人发现）的结构复刻。
建议: 给 Open/Append/CheckCoverage 补最小表驱动测试（含「排除声明漏列→必须可判负」一条），或把未测面从提交信息交付清单里降格为「附带的未验证草稿」。
```

```
[MAJOR][声称-现实][E5] Java spike 的 Part-3「陈旧探测演示」自身两个方向都在说谎——探测列是硬编码虚构，非解析
证据: examples/java-consumer/src/main/java/spike/Main.java:35-37（FORMAT_DOC_CLAIMS 硬编码：ledger {10,26}、release {2,9}）、:152（"format-doc header claims 170"）；实跑输出：release 行打 "2+9 STALE"（文档自 E1 起实为 3+14——虚构陈旧）、ledger 行打 "10+26" 无标记（文档实为 9+26——真陈旧漏报）、头部句打 "170"（文档实为 195）
机理: 该列的存在目的就是演示计数漂移探测，但它既不解析文档也不随 E1/E4 rebase：自 E5 提交当刻起，「文档声称」三行里两行与真实文档不符——陈旧探测器自身成了最陈旧的副本（第五份手抄）。这直接削弱 E5 的证词价值：它用来证明「Java 生态一天可接上」的那份对照表，恰是手抄复发的展品。
建议: FORMAT_DOC_CLAIMS 改为运行时解析 docs/conformance-fixture-format.md 的对应行（夹具作者一天能写 loader，解析一张表是同一量级），或删掉该列只留 oracle-pin 对目录。
```

### MINOR

```
[MINOR][声称-现实][E1] 「三口径显式命名」——191（非密钥库）在文档中零出现
证据: grep agent-festival/ 全树无 "191"；docs/conformance-fixture-format.md manifest 块只有 141/50/195 三个数
机理: 口径「非密钥库 191」只活在提交信息里，文档消费者只能自己算 141+50；「一次说清」没有完全兑现。
建议: manifest 块补一行「非密钥库合计 191/192/…」（随重生成）。
```

```
[MINOR][广度][E1] 计数收编只扫了 format doc——根 README 与 schema/README 基座行的同类陈旧副本原地未动
证据: agent-festival/README.md:67（"三 schema + 95 夹具"——实为 7 个 schema 文件+密钥库、200 件夹具）；schema/README.md:14-15（契约 5+15、信封 2+16——实测 7+23、4+16，批前即陈旧，E1 未审计）
机理: E1 的使命是消灭计数副本，但只圈了增长族；基座行 5+15/2+16 合计 38 与新 manifest 的「基座契约/信封 50」在同一仓里互相矛盾；根 README 的「95 夹具」是 collision 时代化石（留档文档除外——archived 明示冻结，豁免）。
建议: 下一次动 schema/README 时顺带对齐基座两行与根 README 那一行（三者皆一行改动）。
```

```
[MINOR][机理][E4] §3 判定域声明插在双 oracle 表中间，把 markdown 表拦腰截断
证据: docs/conformance-fixture-format.md:61-66（Python 行与 Go 行之间插入段落+空行，"| Go | …" 成为无表头孤儿行）
机理: GFM 中该 Go 行不再按表行渲染，跨语言消费方读「Go 侧运行方式」时格式破碎；合同文本的排版也是合同面。
建议: 段落移到整表之后。
```

```
[MINOR][机理][E3] 13 键中 2 键无键级删守卫（DIGEST_CHANGED_UNDER_KEY、GRANTS_ON_NON_ADOPTED）
证据: schema/examples/ledger/invalid/same-key-different-digest.json 钉 "payload_digest"、adopted-without-grants/effect-with-grants/reused-with-grants 钉 "grants_at_decision"（字段名子串在消息里幸存）；变异⑤双侧删 [LEDGER.DIGEST_CHANGED_UNDER_KEY] 后 Py/Go 全绿
机理: 这两条钉是字段名（中性）而非键，删键不红——键集的守卫覆盖是 11/13，E3 声称的键合同在这两键上是裸的。
建议: 这两枚夹具的 _expect_match 迁到键钉（老字段名子串继续命中，零破坏）。
```

```
[MINOR][声称-现实][E5] README "80 fixtures / 80/80" 是 E4 前旧数——实为 81
证据: examples/java-consumer/README.md:4,:20 vs 四族实测 10+26+2+5+2+19+3+14=81（run.sh 输出四行 "[x] N must-accept + M must-reject" 亦证）
机理: 代码里的钉 rebased 了、README 散文没跟——同提交内代码与文档又一次分叉（E5 提交信息「计数钉随 E4 语料 rebase」只对代码为真）。
建议: 80→81 两处。
```

```
[MINOR][机理][E5] 17 个构建产物入库（.class/jar/cp.txt/maven-status），无 .gitignore；README "clean rebuild" 名不副实
证据: git ls-files examples/java-consumer/target（17 文件，含 spike-java-consumer-0.1.0.jar、cp.txt——后者是本机绝对路径 /Users/yaojun/.m2/...）；run.sh 用 `mvn -q -DskipTests package`（无 clean）
机理: 产物会随源码演进静默腐烂，cp.txt 泄漏机器路径；无 clean 时陈旧 .class 可跨构建幸存（本地跑不受影响，因为总在重编译，但「clean」一词与行为不符）。
建议: git rm -r --cached target + .gitignore（target/），run.sh 加 clean 或 README 改口。
```

```
[MINOR][声称-现实][E5] 「四个已知合同缺口已登记驱动 0.2.0」——仓内找不到登记处
证据: grep docs/ 与根 README：networknt/pattern-face 等四缺口仅出现在 spike README 自己那一句；无 backlog/registry 文档
机理: 「已登记」若只在 spike README 一句话里，0.2.0 战役起稿时（E7 那样的种子文档）检索不到，登记等于没登记。
建议: 在 docs/ 或 impl 目录立一张一行的 gap 清单文件。
```

```
[MINOR][广度/singularity][E6] evidlog 规则消息是英文散文、无中性错误键——E3 刚消灭的病在新族原样重生
证据: go/internal/evidlog/evidlog.go:CheckDoc（"…breaks the dense writer-allocated sequence — a gap or a foreign writer"）、schema/evidlog.py:26-29 同文；现夹具钉 "dense"/"at"/"fabricated" 恰好中性，掩盖了消息面的英文耦合
机理: 第一个想对齐 evidlog 的外部消费者会撞上与 GEPA spike 完全相同的墙（措辞耦合）；spike 边界可以推迟但不必再造一遍债。
建议: 0.2.0 把 E3 键制（[EVIDLOG.XXX] 串首）套用到新族，夹具钉直接用键。
```

---

## 三、逐件核对汇总（提交信息 vs diff）

| 件 | 声明 | 核对结果 |
|---|---|---|
| E1 | 三口径命名/机生成 manifest/手表保留解释性 | 三口径缺 191（m1）；manifest 已被 E4/E6 滞后成陈旧（B2）；「手表保留解释性」实际连数字列一起保留——第四副本未消灭、只是复制（B2 机理） |
| E2 | 域名化 27 文件、festival-dev 残留零 | **属实**：全仓 grep 仅先验文档提及旧路径（合理）；go.mod/import 一致；vet/tidy/build 净；CWD 探针不受影响（FindSchema 相对路径实测在 /tmp 副本同样工作） |
| E3 | 13 封闭键双侧、17 钉迁、老文本保留、键在消息首段头部 | 键数 13/13 双侧属实；17 夹具钉迁属实（26 invalid = 17 键钉 + 9 schema 侧字段钉保持）；老文本保留属实（消息串键后原文未动）；**「都在首段头部」不成立（M1）**；2 键无删守卫（m4） |
| E4 | 奇数孪生钉 float64 域、双侧 oracle 一致、§3 合同+测试双写、三处钉 rebase、附带修 E3 残留一处 | 双侧 ACCEPT 属实但**夹具不区分域（B1）**；§3 有假算术句（B1）；三处 D93 钉 rebase 属实、第四处 manifest 未动（B2）；「残留一处」实为至少四处（M1）；表被截断（m3） |
| E5 | run.sh 重锚仓内路径、LedgerChecker 13 键同步、计数钉 rebase、诚实边界 README、SPIKE-GREEN | run.sh ../../schema 属实（实跑过）；13 键同步属实且全在串首；计数钉 rebase 属实但 README 散文 80≠81（m5）；诚实边界段属实（且措辞与 collision 修正一致）；SPIKE-GREEN 属实；**Part-3 探测列虚构（M3）**；target/ 入库（m6）；缺口登记无处落地（m7） |
| E6 | 两原子两日志、密度规则双侧、CheckCoverage 差集告警、S2 不做、D93 钉 | 与件4 分家干净（包零 import ledger、$id 独立、包文档明示两原子两日志——singularity 通过）；密度规则双侧+删守卫红（变异③）✓；1+3 夹具与钉属实；**CheckCoverage/Open/Append 零守卫死代码（M2）**；S2 边界诚实（schema/README 明示）；消息无键（m8） |
| E7 | 三边类型+三属性、evidence_gap 提案、三裁决点悬置不推演 | **全部属实**（05-edge-grammar-prior.md 逐节对上；悬置三点原样列出、无推演；纯文档零代码） |

## 四、总评

批的工程质量一半很好：E2/E7 干净，八 oracle + race 全绿，钉守卫在该守的地方（E3 钉键、E4 夹具存在性、E6 密度规则）删之即红，Java spike 真跑通且诚实边界写得到位。

但两处 BLOCKER 都是「声明-现实漂移」本体，且都发生在**为治漂移而立的法**上：E4 交付的「判定域钉」被机械反证为不钉任何东西（发出去的夹具是偶数孪生，四处叙事描述的奇数孪生不在文件里；合同文本的拒收机理是假算术）；E1 立的计数法在同批第二笔（E4 漏 rebase manifest）与第六笔（E6 缺族）后即告失守，HEAD 上文档 195 对目录 200、生成器输出 196 三数互不一致——04-collision.md 自己写下的第一性原理裁定（单源渲染+CI 对拍）没有被实现，弱形态（注释+人跑）按预期的方向失败了。M2/M3 同源：件7 的主交付函数零守卫、E5 的陈旧探测器自身最陈旧——「修复/交付声明必须机械验证」这条 V2 立法在本批有四处未达标。

收卷建议：不收。B1 一行字面量+一句机理文的修复量极小；B2 是一次重渲染+一条对拍钩子；两 BLOCKER 清偿后本批可到 0B0M 首轮（M1/m4 顺 E3 域、m5-m7 顺 E5 皆一行级）。
