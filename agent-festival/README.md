# agent-festival（Go 机器基座——统一架构的第一个合规适配器）

> 来源：[yaojun01/agent-festival](https://github.com/yaojun01/agent-festival)（设计仓，决策台账
> D1-D95、验证循环 V1-V36）。本目录把 festival 的机器基座——L3 能力契约/签名信封/执行图
> 三个 JSON Schema 的 Go 实现——落进 NGA，作为「决策智能 + agent loop + agent festival
> 统一架构」中 festival 侧的机器基座（对表结论见 [issue #1](../../issues/1)）。
> 按 NGA 的来源边界纪律：本目录是 owner-supplied 外部供件，其实现声明不是 NGA 证据，
> pending 保持 pending。

## 做什么

三个机器判定件，对应三份 schema（`schema/`）：

1. **契约校验**（`cmd/validate`）：L3 能力契约 + 签名信封 + 信任密钥库——cross-field
   规则（selector 规范/效果包络）、JWS 验签（ES256/RS256/EdDSA）、owner 绑定、
   contract_hash 重算
2. **图合成**（`cmd/compose`）：执行图 → 合成契约（requires 并集/最坏效果/预算折叠）+
   授权准入（子任务权限 ⊆ 父任务权限 ⊆ 发起员工持有）+ 父预算均分切分（shares）
3. **信封再签**（`cmd/sign`）：三算法签发 + 全套夹具再生物（语料唯一真源）

203 个双向夹具（全仓口径——见 conformance-fixture-format.md 机生成清单）（valid 必须 0 错、invalid 必须拒且拒绝理由逐字钉 `_expect_match`）
构成行为规格——**夹具即规范**。

## 与 NGA 架构的映射（V0.2 三态四面）

按 issue #1 碰撞对表：本基座覆盖统一架构的 L0 真源（目录三份：契约+图+判断规格的
机器载体）、L1 权限轴（⊆ 判定+预算签发切分+task:// 派生）、L2 执行载体（六类
typed 节点可表达的图 schema）；NGA 的语义轴（判断规格/采纳门/三身份/重放契约）
作为后续独立并列模块生长——**只消费本基座产出，基座永不反向依赖**。

## 怎么设计

- **判定权归业界库**：JWS=go-jose/v4，JCS=cyberphone/json-canonicalization（RFC 作者
  参考实现），JSON Schema 语义=santhosh-tekuri/jsonschema/v6（regexp2 .NET 模式，
  `$` 语义与 Python re 一致）。手写代码只做文案渲染（钉子锁 Python jsonschema 精确
  措辞）与差分报警——双引擎判定分歧即 fail-closed 拒绝
- **Python 冻结 oracle**：`schema/*.py` 与 Go 双侧对跑同一批夹具，行为逐点一致才算绿；
  Go `cmd/sign` 再生的语料被 Python oracle 全绿验收（pyjwt↔go-jose 双向签名互验）
- **整数预算域**（D22）：所有 bound 是最小单位整数（如 USD-cents），schema 上限
  2^53-1；折叠求和带 int64 饱和；均分地板除、余数丢弃
- **无交叉依赖**（单向分层 DAG）：`rfc8785 ← validate ← compose`，cmd 只消费不反向；
  与 NGA 仓其他目录零依赖

## 怎么用

```bash
cd agent-festival/go

go test ./... -count=1        # 20 包全测（含 JCS 差分、报警支柱、守卫电池）
go run ./cmd/validate         # 契约/信封/密钥库三套件（对 ../schema/examples）
go run ./cmd/compose          # 执行图合成套件（10+36 夹具+11 守卫）
go run ./cmd/sign             # 再生全部信封语料（换新密钥，需整批提交）
```
（包结构与依赖红线以 `cd go && go list ./...` 为单一真源——20 包：
9 cmd 入口 + 11 internal 库；schema/ 9 个 schema 文件 + 203 夹具）

Python oracle 侧：`pip install -r ../schema/requirements.txt` 后
`python3 ../schema/validate.py` / `../schema/compose.py`。
