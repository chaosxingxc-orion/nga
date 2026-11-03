# 先验：compose.go + sign.go 落地（xuefanfan 范式）+ 碰撞 + 空白验证循环

日期：2026-10-30。分支 impl/2026-10-30-go。用户指令：用 xuefanfan 开发范式指导；4-lens + singularity 与 frame-bench 碰撞吸有益避反向；空白子智能体循环至 3 连 0 BLOCKER 0 MAJOR。

## xuefanfan 范式提取（本任务的适用条款）

从 agent-runtime-acceptance/docs/AGENTS.md 提取对本任务的六条硬规则：
1. **单一真源**：代码即规格；不写「详见 Python 源码」——所有语义在 Go 侧自包含，Python 是对照 oracle 不是文档。
2. **不编造 API**：只用 Go 标准库真实存在的公开 API（零第三方依赖已达成）。
3. **双向核实（承重断言）**：每条规则有 must-accept + must-reject 双向样例钉住——这就是我们的 _expect_match 体系。
4. **坑位独立成节**：易错点用 ⚠️ 块记录——validate.go 四坑先例。
5. **机械校验必须全绿**：两检查器（Python oracle + Go 新实现）跑同一 76 样例全绿才算完。
6. **status 标注**：verified / experimental——compose.go 标 experimental 直到双实现 parity 差分跑通。

## 范围（IN/OUT）

IN：compose.go（图合成+⊆判定+预算切分+边校验+shares 钉位）、sign.go（ES256 签发+信封再生物）、cmd/compose 与 cmd/sign 驱动器、对照样例 8+28 全绿。
OUT：0.2.0 新规则（D82 四件+八错误码——下一件）、三张表、任何框架外依赖。

## 先验条目

1. compose.py 的核心逻辑（atomic_grants→compose_requires→fold_bounds→split_bounds→bounds_violations→leaf_allotments）可以直接 Go 化——纯数据变换无 I/O；最大风险在 plan 树递归（seq/par 嵌套）的泛型处理。
2. Go 的 map 迭代无序——requires 合成输出需排序保持 oracle 一致（Python dict 保插入序）。
3. sign.py 的 ES256 签发用标准库 crypto/ecdsa + crypto/rand 可达；JWKS 密钥库写入是 JSON 序列化——风险在 JCS 规范化的字节一致性（rfc8785.go 已过 20 向量）。
4. sign.py 每次运行换新密钥（AGENTS.md 规则 15）——Go 版保持同样行为，跑完须同步提交全部信封样例。
5. leaf_allotments（并行组 shares 钉位）依赖 plan 树遍历+split_bounds——整数化后是 int64 地板除，无 Decimal 语义歧义。
6. **先验外风险**：compose 的 `_expect_composed` 钉位比较在 JSON 序列化路径上可能有数字→字符串的形态差异（Python 的 str(v) vs Go 的 fmt.Sprint）——需要跑样例看。
7. frame-bench 碰撞预期：Go 标准库 testing 框架（testing.B/testing.T）是 E8 微基准的 native 形态；不引入 testify 等第三方断言库。
   - **修订（V2 碰撞后，2026-10-28）**：「零依赖」退役，限测试断言库。V1+V2 空白验证的 5+2 个 BLOCKER 全部长在手写底层判别上（RS256 条件反转、JWK 空指针、U+2028 转义、裸 NaN 词法、代理对折叠），正是 2026-10-15 立法（底层判别不定制）预言的自研子集失败形态；singularity 分叉 3 同判。裁决：JWS/JWK → `go-jose/v4`（verify+sign 双侧，V2 修复轮落地）；JCS 保留自研（已过 4016 值差分，F7 正向证据）；schema 引擎保留手写子集——测试向量钉的是 Python jsonschema 的精确错误文案（"'assurance' was unexpected"），换 santhosh-tekuri/jsonschema 须配文案翻译层，比手写子集更脆；0.2.0 扩面时若决定放松钉子到关键词级再换库。

## 方法

1. 读 compose.py 全文（539 行）→ 写 compose.go（目标 ~450 行 Go）→ 跑 8+28 样例至全绿。
2. 读 sign.py（244 行）→ 写 sign.go → 跑 sign --regen + 验证全绿。
3. 派 2 路碰撞（4-lens + singularity）对 Go 实现线与 frame-bench 九框架碰撞。
4. 空白子智能体验证循环（4-lens + singularity 各一路/轮）至 3 连 0B/0M 或 20 轮封顶。

**V3 修订（2026-10-28 换库轮）**：上方 V2 修订中的「JCS 保留自研 / schema 引擎保留手写子集」已被用户不造轮子立法覆盖——现行架构：JCS 判定权 cyberphone 参考实现（对象+数组），本地 ES6 序列化器降为差分对照（differential_test.go 常驻）；schema 判定权 santhosh-tekuri/jsonschema/v6（regexp2 .NET 模式，$ 语义与 Python re 一致），手写引擎降为文案渲染层，双引擎判定分歧 fail-closed。三方 regex 方言分歧由冻结 oracle 裁决（方言台账：.NET \w 收组合记号 / \Z 允许尾换行——当前 4 个 schema pattern 实测三向一致，0.2.0 新 pattern 须过三向矩阵）。format 边界的准确表述（V8 修正）：活体 oracle 强制 9 个 stdlib format（date/email/idn-email/idn-hostname/ipv4/ipv6/regex/time/uuid）；我们唯一用到的 uri 不强制仅因 rfc3987 不在钉死依赖集——不是「一律不强制」。0.2.0 任何 schema 新增 format 关键字前必须先双侧钉夹具（两 Go 引擎永远不查 format，分歧报警对 oracle 单侧强制是盲的）。
