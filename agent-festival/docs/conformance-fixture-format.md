# Conformance 夹具格式与跨语言消费指南

> 目的：本仓 205 件 JSON 夹具（全仓含密钥库；增长族 151 件——三种口径见机生成清单）是**可执行行为规格**（executable behavior spec），不是静态测试数据。本文定义夹具格式、钉子纪律、双 oracle lockstep 模式，以及任何语言（包括 NGA Java SDK）如何消费同一批夹具做 conformance 验证。这是 issue #1 碰撞回应提议 1（"95 夹具升格跨语言 conformance 基准"）的落地说明。
>
> 先例：langgraph 的 checkpoint-conformance 套件、本仓 Python/Go 双 oracle（17+5 轮空白审查验证）——"夹具即规范"已被三方独立到达。

## 一、夹具目录与语料计数

| 目录 | 内容 | 计数（D93 双侧钉） |
|---|---|---|
| `schema/examples/ledger/{valid,invalid}` | 事件账本文档 | 9 + 31 |
| `schema/examples/adoption/{valid,invalid}` | 采纳请求文档 | 2 + 5 |
| `schema/examples/judgment/{valid,invalid}` | 判断规格文档 | 2 + 19 |
| `schema/examples/release/{valid,invalid}` | 发布清单文档 | 3 + 14 |
| `schema/examples/replay/{valid,invalid}` | 重放用例文档（件6） | 8 + 9 |
| `schema/examples/evidlog/{valid,invalid}` | 取证日志文档（件7 spike） | 1 + 6 |
| `schema/examples/compose/{valid,invalid}` | 执行图（基座件1） | 10 + 36 |
| `schema/examples/{valid,invalid,envelopes,keys}` | 基座契约/信封/密钥库 | 其余 |

计数钉三处同原子维护：`cmd/*/main_test.go` 摘要行、各 `*.py` oracle 的元组断言、`schema/README.md`。**语料增减必须同笔 rebase 三处**——这是防静默缩水的硬闸（D93，源于 4b04cea/4e52a20 教训）。


<!-- corpus-manifest: machine-generated from schema/examples/**; regenerate with
     python3 tools/corpus_manifest.py (do not hand-edit counts below);
     verify with python3 tools/corpus_manifest.py --check (rc=1 on drift) -->
| 族 | valid + invalid |
|---|---|
| `ledger` | 9 + 31 |
| `adoption` | 2 + 5 |
| `judgment` | 2 + 19 |
| `release` | 3 + 14 |
| `replay` | 8 + 9 |
| `compose` | 10 + 36 |
| `evidlog` | 1 + 6 |
| 增长族合计 | 155 |
| 基座契约/信封 | 50 |
| 全仓合计（含密钥库） | 209 |
## 二、夹具的钉子语法

每个夹具是一份带内嵌钉的 JSON 文档：

```jsonc
{
  // ...被测文档本体...
  "_expect": "ACCEPT: 一句人读的语义说明（为什么必须通过/拒绝）",
  "_expect_match": "拒绝原因里必须出现的子串（invalid 夹具）",
  "_expect_composed": { /* 基座执行图专用：合成的期望输出 */ },
  "_expect_verified_kids": [ /* 基座信封专用：必须通过验签的 kid */ }
}
```

规则：
1. `_expect*` 键在**校验前被剥离**（loader 层统一弹出，被测文档本体不含下划线键）
2. `_expect_match` 必须是**字符串**——非字符串类型是响亮的夹具作者错误（fail LOUD，绝不静默降级为"无钉"——否则错因检查被绕过；V28 F-1 立法）
3. **单一违规纪律**：每件 invalid 夹具只含一处违规（唯一设计内例外：effect-before-adoption 一个旁路事实合法触发文法+转移两族，双侧同集同序）——否则 wrong-reason 钉会退化为碰巧匹配
4. **wrong-reason 检查**：invalid 夹具被拒后，其错误列表中**至少一条**含 `_expect_match` 子串——拒绝了但理由不对 = FAIL。钉子应取**守卫专属短语**（如 `conflict event carries idempotency`），不能取会被子串误配的宽泛词（如 `type`——曾因 "not of type" 击穿过）
5. valid 夹具被接受即过；invalid 被拒且理由命中即过——**双向断言，只判接受是假承重**（D35）

## 三、双 oracle lockstep 模式

同一批夹具被两个独立实现的验证器消费：

| 侧 | 验证器 | 运行方式 |
|---|---|---|
| Python | `schema/{ledger,adoption,judgment,release,replay,compose,evidlog}.py`（jsonschema）+ 共享 harness `_suite.py` | `python3 schema/<name>.py` |
| Go | `cmd/{ledger,adopt,judgment,release,replay,compose,evidlog}`（santhosh+regexp2 经 internal/schemalib）+ 共享 runner `internal/suite` | `go run ./cmd/<name>` |

（上表枚举以机生成 manifest 的七族为准——R13 B-m2：手写四族表曾把 evidlog/replay/compose 三族隐身。）
**历史注记（R13 F3→R16 退役）**：归一化规则同步义务段（normalizeSeqDomain/normalizeIntegralNumbers 的独立拷贝与突变合同差异）随 v1 charter 一并退役——两函数已删，条目留此防考古误导。

**数值域章程 v2（用户立法 2026-11-02，R16）**：本仓一切业务数值域**禁止 float/double**——必须 int/long 替代。JSON 整数字面量是唯一合法数字形态：写者只发（Go `int`/`int64` 字段序列化）、双侧 checker 只收（Go `json.Number.Int64()` 拒一切浮点语法 `[X.SEQ_FLOAT_SYNTAX]`；Python `isinstance(int)`——json.loads 恰好按字面量区分 int/float）、整数字面量超 int64 走 `[X.SEQ_INT64_OVERFLOW]`。JSON Schema 的 integer 类型按值判定会收 1.0——字面量门在 checker 层补位（schema pattern 无法表达：JSON Schema 的 pattern 只作用于 string 实例）。本章程废除 v1 double charter（曾以 RFC 8785 类推收容域内整值浮点语法——JCS 只管签名 payload，从未管过计数器域；归一化层与 ±2^53 子域规则随之整体退役）；旧 charter 时代的夹具（seq-float-syntax / seq-odd-float-twin 由 valid 转 invalid、seq-float-beyond-2e53 键族并入字面量门）保留为章程变更的行为钉。**豁免清单（逐面显式，防隐含依赖）**：① `go/internal/rfc8785`（RFC 8785 JCS 签名规范化器——外部协议的数字序列化规则，非业务数值；是否连签名面一并清除待用户另行裁定）；② schema 引擎关键字域（Go validate 的 santhosh 与 Py jsonschema 的 number/integer 关键字实现——JSON Schema 规范语义按值判定，章程的「字面量门在 checker 层补位」正是骑在该按值行为之上；动引擎=动规范实现）。**Decimal 残留 grep 注记（防幻影误判）**：章程叙事短语（「金额用 Decimal」「50 位金额」「parse_float=Decimal」于 schema/README）已清零；全仓宽 grep "Decimal" 仍有 ~10 命中——均为活代码（validate.py 的 schema 引擎 Decimal 面=豁免②）、Java BigDecimal 消费者文档、compose 墓碑注记与历史夹具 _expect——均为已知面（豁免②/消费者示例代码/墓碑/历史夹具钉），无静默回归。

**待裁登记**：① compose 的 bounds 数值域（max_cost.amount/max_seconds/max_downstream_calls/max_bytes_out——整值浮点语法收容；compose.py docstring 已改引本登记，2026-11-03）——用户裁定扩豁免或排期转换；② judgment 的 rules[].precedence 等无 checker 层补位的 schema-only 整数字段（双侧按值同收 3.0——无判决分叉但无字面量门，章程全称断言的登记例外）。
关键纪律：
- **checker 各自独立实现**（双验证器交叉是防单引擎语义漂移的机制），**harness 共享单源**（套件纪律不是被验语义）
- 引擎 parity 立法：regexp 引擎用 .NET 语义（`$` 匹配尾换行前，与 Python re 一致）——Go 默认 RE2 会在 pattern 面分叉（基座 V3 MAJOR-1 教训）
- 解码纪律（R16 章程）：文档解码必须 `UseNumber`（Go）/原生 int（Python）——plain float64 解码会把每个数字变 float64，字面量门不可判定（0.0 与 0 不可分）
- 聚合契约：两侧 code-rule 族聚合同序；Go 在 schema/浮点语法/typed 解析三处短路、Python 追加继续——错误**集**构成可能不同、**判决**永不分叉；夹具按单一违规设计即免疫此差异

## 四、跨语言消费（NGA Java SDK 接入方式）

**错误匹配的规范面（E3 处方，2026-11-02 落地）**：`[LEDGER.*]` 中性键是错误匹配的规范面，英文文本是兼容层——键与文本的稳定面以仓内双 oracle 为准。sunset 条款：0.2.0 各族键钉全迁后，短语钉收卷。
**缓存边界（R13 立法）**：Go 测试缓存键只覆盖测试二进制+参数+环境，不含运行时读的夹具/文档——夹具或 manifest 的改动在裸 `go test ./...` 暖缓存下静默过门。机械门只在 `-count=1`/冷缓存/CI 下承重；本仓规范用法一律带 `-count=1`。

消费方（任何语言 X）需要实现的全部接口：

```
load(fixturePath) -> (doc, expectMatch, parseError)
  1. 读 JSON；解析失败 → doc=nil + parseError（invalid 夹具计为 rejected-at-parse，
     其 _expect_match 仍可对 parseError 文本匹配——从原始字节提取钉，别静默丢弃）
  2. _expect_match 必须为 string，否则 fail LOUD
  3. 剥离全部 _expect* 键 → doc

check(doc) -> errors[]          // 你被验证的验证器/状态机
suite(dirs, check) -> 0|n       // 双相循环 + wrong-reason + 计数钉
```

验收口径（消费方自己的 conformance 套件）：
- 全部 valid 夹具：check 返回空
- 全部 invalid 夹具：check 非空 **且** 至少一条错误含 `_expect_match`
- 语料计数与 D93 钉一致（防消费方悄悄裁剪语料）
- **行为规格级**，不是静态 schema 校验级：对件2 采纳闸类夹具，消费方应驱动自己的状态机产生等价行为（同键异载=conflict 事件、断尾治愈、撤销拒发），而非仅跑 JSON Schema
- **断尾教义按包分工**（R9 裁定记录，两包有意不同、勿互抄）：件2 采纳闸/事件账本＝**治愈**——重写自解析行重建，残尾字节消失，丢尾自反证（状态转移表拒非法重放、重发即 14-A5 unresolved 一等态）；件7 取证日志（evidlog）＝**记忆+拒写**——断尾被跳过的字节可能载着未入账查询，写者拒绝追加、coverage 拒绝判绿，修尾归人裁。跨语言消费方实现取证日志类时照拒写教义，勿照治愈教义。

## 五、语义漂移防线（为什么必须共享夹具）

两套实现各自测试全绿**不构成收敛证据**。当前唯一无自然纠正力的摩擦环是语言双轨下的双重实现漂移——共享夹具 + wrong-reason 钉是唯一硬机制：
- 语义若分叉，某一侧必然在某个夹具上判决或错因漂移 → 套件红
- 上游语义演化时，夹具先改（单一违规纪律），两侧实现跟着对账
- 漂移登记（schema/README.md）记录的是**上游文档**的缺口；夹具锁住的是**实现间**的一致——两层互补

## 六、已知边界（诚实清单）

- 夹具不证明外部效果的真实幂等（provider 侧保证出界——两侧共识："a client key alone gives no server guarantee"）
- 夹具不证明模型语义一致性（Model readiness is a separate gate——双打夹具不得宣称生产语义用途，见碰撞回应 D1）
- append-only 不等于防篡改（账本件 description 立法）；完整性是另一个证据面
