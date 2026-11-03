# 六件先验：范围框定（2026-10-31）

> 任务：NGA 语义六件在 agent-festival Go 基座上落地。语言 Go；骑轮子不手搓；与 festival
> 领域重合处复用 xingchao 说明与 festival 既有设计；逐件独立无交叉依赖；做完空白智能体
> 循环至 3 连 0B0M 或 20 轮。

## IN（件0 + 六件与形态）

0. **件0：迁移事件身份契约**（一页纸先行，singularity 碰撞裁定）：事件身份/幂等键语义/
   仲裁序记录/版本绑定纪律——件 2/4/5/6 必须共同符合。主脊的载体，防切香肠漂移
   （六件是同一原子「可归因有效迁移事件」的六个投影，身份契约是它们共享的键）。
   **S1 岔路裁决**（4-lens 最高优先项）：件 4 覆盖账本事件 schema + correlation keys
   （identity/digest/依赖版本/仲裁序——由件 6 匹配需求反哺设计，设计期联合非运行时
   依赖）；件 6 的记录族输入（模型输出/工具响应/guard 实耗）由夹具自备。件 4 保持
   精瘦，件 6 输入来源钉死为「账本事件 + 夹具自备记录」。

1. **credit-graph 夹具**：NGA 总设计 §7 / 13 号 §7 的 credit 示例写成 execution-graph
   样例——nodes=六类 typed capability（S1 判定节点只读进 requires、采纳边界、外部操作
   节点 effects 一等声明）、caller_holds=员工授权集、parent_bounds=预算。跑现有 compose
   判定 + ⊆ 闸。**形态：schema/examples/compose/valid/credit-*.json + invalid 反例**。
   _expect 钉死覆盖面=credit 案例的**授权/预算/效果包络面**（非决策语义=件3 领地、
   非采纳时序=件2 领地）；缺口清单补「0.1.0 plan 文法无分支——B3 绕 veto 路线
   在文法层不可表达」；引用修正：credit 规则本体在总设计 §6.1 + 10 号 walkthrough。
   注意：NGA adoption 边界节点/保护性义务在 0.1.0 schema 无槽位——夹具先覆盖可表达
   部分，槽位缺口记 finding 待件 2。
2. **adoption 契约 + adopt 门**：新 schema `adoption.schema.json`（三层身份
   business_request/evaluation_revision/operation + 单赢家 current-winner 字段）+
   `go/internal/adopt` 状态机（acquire→adopt→dispatch→**unresolved**→effect 含超时
   对账一等态 + 幂等键）+ NGA 14-A5 **四反例**夹具（并发双采纳/崩溃恢复/超时对账/
   **同键换载荷**——15 号 B4「reject changed material parameters」的机器化）。
   **账本事件写入走件 4 的记录格式**（两套身份词汇 join 预登记：三层业务身份 +
   D31 问责三元组在同一事件并列携带）。**并发夹具用真 goroutine + -race + 确定性
   仲裁**（12 号「recorded arbitration order」）；**崩溃耐久契约**：行界 JSON
   append-only + 原子写（temp+rename，stdlib）+ torn-file/lost-flush 夹具；
   **effect 态授权复检**：内存态授权集快照复检（14 号 A4 刀的机器化）；
   **单写者纪律**：adopt 状态机是账本采纳事件的唯一写入方，夹具含旁路反例
   （绕状态机直写账本→加载时拒绝）；文件级防篡改明示出界（12 号 §6）。
3. **判断规格 schema**：`business-judgment.schema.json`（NGA 总设计 §6 完整字段：
   question identity/levels/candidate set/precedence/owner + terms/units/temporal
   conventions + coverage and exception rules + examples（含边界/等价/竞争规则/未决例）
   + supported scope——本期裁剪须逐字段声明理由）。**形态：第四份 schema + 夹具 +
   检查器消费 validate 导出 API（SchemaErrors/SetRootSchema/LoadSchema）+ 直接用
   santhosh 编译——禁改基座行**。schema 自含 $defs（冻结引擎跨文档 $ref 只解析进
   契约 schema）；只用 string enum（EQUALITY-SEMANTICS LEDGER）；禁 format 关键字
   （FORMAT LEDGER）；签名出处显式登记 deferred gap（未来复用件 5 信封形态）。
4. **账本**：`event-ledger.schema.json`（festival D31 三元组 session/skill/role +
   NGA P5 **五维**版本字段 evidence/rule/model/readout/policy——先验原文漏 evidence
   已补 + correlation keys：事件身份/digest/依赖版本/仲裁序——件 6 匹配器反哺设计）。
   **schema+Go 类型（事件追加逻辑归件 2 单写者），adopt 写、replay 读**。记录族的
   完整输入（模型输出/工具响应/guard 实耗）不在本件——件 6 夹具自备。
5. **release manifest**：`release.schema.json`（NGA 13 号 §5 兼容版本绑定+rollout/
   hold/retire 状态）。**新写 release 信封**（同 AgentCardSignature 形态+go-jose/JCS/
   sha256 栈——冻结信封 schema 的 body 硬钉为契约，不能复用 EnvelopeErrors 验签
   路径）；诚实标注「暂无端到端消费者」，排期最后。
6. **replay runner**：`go/internal/replay`——从账本事件+夹具自备记录（模型/工具/
   事件输入）重算控制器裁决（adopt 状态机重跑），**禁真令牌**（NGA 12 §3
   recorded-response 适配：按 identity+digest+依赖版本匹配，记授权响应不记凭据）。
   **可证伪夹具族预登记**（12 号 §3/§7——否则「重算≠回放」是口号，退出判据被自恰
   夹具满足）：(a) 篡改账本结论→重算必须分歧（防退化成 reader）；(b) 单记录输入
   变异→分歧定位在正确步骤；(c) 意外调用/参数变更→拒绝匹配该响应；(d) 重放录下的
   违规→**fidelity 过 conformance 挂**（双裁决分离，12 号 §3 末段）；(e) hold/
   dispatch 竞速两种仲裁结局。四操作分离落为四个不可互换的结构化入口。
   **不变量 1 分裂叙述**：判定（gate/幂等裁决）不经模型——保持；判断（S1 语义
   观察）经模型但以记录形态进重算——新增，包注释三层治本。

## OUT

- NGA 四面/三态/agent evolution 写成代码（glossary 派生说法）
- S1/S2 模型训练、Jev 复现（NGA project 1，他的 Ascend 栈）
- AgentLoop 对接（阿里云产品，正交）
- 外部资源侧幂等真保证（action idempotence 要对账协议，我们只做框架侧操作身份）
- 修改基座任何一行（MR !1 已落的六包冻结）
- 令牌/吊销三件套（信任根 D67 嫁接案——等邢超裁决后另立件，不在本六件）

## Go 强项对齐检查

六件全落在 schema+夹具+检查器+状态机层（festival 已证的强项）；判定权分配：
- schema 校验：复用 santhosh-tekuri 引擎（件 2/3/4/5 的 schema 校验零手搓）
- JWS 签名：复用 go-jose（件 5 信封）
- 状态机（件 2 adopt、件 6 replay）：手写是合法区（领域语义，业界无对应物——D84 自研合法区判定）

## 复用清单（不重设计）

- 三 schema 模板/夹具纪律/检查器模式 → 件 2/3/4/5 照抄
- D22 整数预算域+饱和加法 → 件 1 夹具的 parent_bounds
- D31 账本三元组设计 → 件 4 起点
- D78 包络（深度/存活/派生/预算）→ 件 2 S2 节点的包络表达（若夹具需要）
- NGA 14 号对抗审查五刀（A3/A4/A5）→ 件 2 的三反例就是 A5 的机器化
- NGA 12 号重放契约（四操作分离/十族记录/recorded-response）→ 件 4/6 直接消费
- NGA 13 号 §5 版本连续性链 → 件 5
- NGA 总设计 §6 七对象+§7 credit 示例 → 件 1/3

## 依赖 DAG（无交叉）

```
基座（冻结）
  └─ 件0 身份契约（文档，约束所有件）
  └─ 件4 账本 ←─ 件2 adopt（写事件）←─ 件6 replay（读+重算）
  └─ 件3 判断规格 schema ────────────→ 件6（读 schema 实例）
  └─ 件5 release schema ────────────→ 件6（读 schema 实例）
  └─ 件1 夹具（独立，用现有 compose）
```
件 6 是集成点（必须最后做）；件 3/5 互不认识但都被件 6 消费——「无交叉」=
件 3/5 零横向依赖、件 6 只读不写、件 4 由件 2 单写。

## 骑轮子检查

- schema 引擎：santhosh（已有）✅
- 签名：go-jose（已有）✅
- JCS：cyberphone（已有）✅
- 状态机：无业界轮子可骑（领域语义）——手写合法区，但实现上**不发明持久化**
  （内存+JSON 文件，与基座夹具同等待遇，不引数据库）
- 新依赖：**零**（go.mod 不动）
- **D84 限定**（singularity 分叉四）：自研合法区=**语义契约层**（三身份/单赢家/
  四操作分离——九框架确实零覆盖）；**机制层**（幂等键比较/digest 拼接/原子写/事件
  匹配）业界全有轮子——全部走 stdlib 与已有库，不手写定制（V1/V2 BLOCKER 全长
  在手写底层判别上的教训）
- **冻结引擎三条暗桩**（C5——新 schema 必须遵守）：(a) 跨文档 $ref 只解析进契约
  schema（新 schema 自含 $defs 或只引契约）；(b) 禁 format 关键字（FORMAT
  LEDGER）；(c) 只用 string enum（EQUALITY-SEMANTICS LEDGER）

## 验证协议（做完后）

- 每件：六包+新包 `go test -count=1` 全绿、双侧 oracle（新增 .py oracle 或复用模式）
- 空白智能体 4-lens+singularity 循环：同问题扫清才推进（同类重扫 D91）
- 退出：3 连 0 blocker 0 major 或 20 轮

## 先验十条（含两条预登记奇点攻击面）

1. NGA 文档全是 proposed——六件是证据轨探针（D83），邢超裁决后 schema 可改，代价=改夹具
2. credit 夹具会暴露 schema 槽位缺口（adoption 边界/保护义务）——这是特性不是缺陷，缺口记 finding 喂件 2
3. adopt 门是六件最深处：14-A5 三反例写不出=账本升级需求单（issue #1 原话）
4. 判断规格 schema 的字段从 NGA §6 直接来，不自行发明字段
5. 账本版本字段从 NGA 12 号十族记录来
6. release manifest 的 rollout/hold 从 NGA 13 号 §5 来
7. replay 的四操作分离是 NGA 12 号的机器化——检视/重放/重评/恢复不得互换
8. 无交叉依赖：件 3/5 互不认识；件 6 只读不写
9. 【预登记攻击面 A】「adoption 语义可能被 schema 化吞掉控制时序」——单赢家是时序
   断言不是字段断言，状态机必须真跑并发场景夹具
10. 【预登记攻击面 B】「replay 可能退化成回放而非重算」——重放必须重新执行
    adopt 状态机从记录输入推导，不是从账本读结论
