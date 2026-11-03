# 件6 replay runner 先验：范围框定（2026-11-01）

六件收官件。语义出处（已重锚）：07 提案 §8 四模式表 + L5 漂移（按序重放不重裁）+ 00-priors 原始预登记（五族夹具 a-e/禁真令牌/四操作不可互换）+ 预登记攻击面 B「重放必须重算不退化成回放」。

## IN

1. **go/internal/replay 包**：四个不可互换的结构化入口（07 §8 四模式一一对应）：
   - `Inspect(path)`：读账本重建状态视图+暴露缺口（ledger.Errors 全量报告）——无重算无活效果
   - `Replay(case)`：**重算**——按 case.steps（adopt/dispatch/markX 调用序列+记录族输入）驱动一台**内存 adopt.Machine**（path=""），收集产出事件流，与 case.recorded_events 逐事件比对（seq/status/identity/digest/grants/accountability）；活效果天然禁用（内存机无外部世界）
   - `Reevaluate(case, substitution)`：steps 中声明的 versions/依据可替换的隔离重算——记录预期差异（原始历史不动）；差异报告=原 case 重算 vs 替换后重算的事件流 diff
   - `Recover(path)`：从账本恢复机器状态（adopt.Open）+ 对账出口报告（unresolved ops 的 reconciliation 路径）——0.1.0 到「恢复到可派发状态」，**不真派发**（派发是件2 Dispatch 职权且属活效果）
2. **双裁决分离**（12 号 §3 末段语义）：`fidelity`（重算产出==记录？）与 `conformance`（控制路径符契约？=ledger.Errors(recorded)+机器守卫判定）两个 verdict 分开输出——夹具 (d) 钉「fidelity 过 conformance 挂」的组合合法存在
3. **replay-case 夹具格式**（新 schema `replay-case.schema.json`）：{case_version, steps[]（调用序列：op+request/grants）, recorded_events[]（=账本事件流或内嵌）, expected{fidelity, conformance}}；steps/recorded 分离=「输入」与「记录」分离（S1 岔路：记录族输入由夹具自备，不入账本 schema）
4. **五族可证伪夹具**（原始预登记 a-e 全做，否则「重算≠回放」是口号）：
   - (a) 篡改账本结论（recorded_events 改 status）→ 重算分歧（防退化成 reader——纯回放器永远一致，抓不住篡改）
   - (b) 单记录输入变异（steps 里某 request 字段变）→ 分歧且**定位在正确步骤**（diff 报告指明第几 step/事件）
   - (c) 意外调用/参数变更（steps 与 recorded 的 digest 不匹配）→ 拒绝匹配该响应（幂等键规则重算侧）
   - (d) 重放录下的违规（recorded_events 本身违八族某条但 steps 重算产出与之一致）→ fidelity pass + conformance fail
   - (e) hold/dispatch 竞速两种仲裁结局（同一 steps 序列、recorded 两种合法结局各自 fidelity pass——按记录仲裁序重演不重裁）
5. **解析下沉**：JSONL 行解析（adopt.parseCompleteLines 三视图）移至 ledger 包导出 `LoadDocument(path)`——账本文件格式的所有权归 ledger；adopt 改引 ledger（依赖方向不变）；replay 读账本走 ledger 不引 adopt 的文件层
6. **cmd/replay 驱动**：跑 replay-case 夹具套件（expected 双裁决钉），suite 纪律复用
7. **oracle 分层（诚实边界）**：case 文档**格式面**双侧（Python jsonschema oracle）；**行为面**（重算引擎）Go 单侧——Python 无法复用 Go Machine，不伪装双侧；行为钉的删守卫反证在 Go 测试内做

## OUT

- 不做活效果 dispatch/recover 真派发（Recover 到可派发态为止）
- 不做记录族输入的完整 schema（记录族=夹具 steps 内嵌 JSON，S1 岔路维持）
- 不做引擎集成（不接 openJiuwen/langgraph——重放对象是控制决策不是图执行）
- 不做真令牌/凭据（recorded-response：按 identity+digest+依赖版本匹配，记授权响应不记凭据——禁真令牌）
- 不重开状态机语义（重算引擎=复用 adopt.Machine 零新状态机；八族规则=复用 ledger.Errors）
- Python 侧行为重算器不做（单侧诚实声明）

## 复用清单（不重设计）

adopt.Machine（重算引擎，内存模式）/ ledger.Event+Errors（conformance 侧+八族）/ suite.Runner（夹具纪律）/ schemalib（case schema 编译）。预计新增 Go 代码 <600 行（对照件2 2357——replay 是消费者不是状态机Owner）。

## 依赖 DAG（无交叉不变）

```
replay → adopt（内存机重算引擎）→ ledger（类型+八族+LoadDocument）
replay → schemalib（case schema）
cmd/replay → replay + suite
（replay 不写任何持久账本——内存机写临时路径 path=""）
```

## 骑轮子检查

零新状态机、零新规则族、零新持久化——全部机制复用件2/件4 已验证资产；新码=四入口的编排+diff 报告+case schema。

## 验证协议（做完后）

- cmd/replay 套件全绿（case 计数钉双侧）
- 五族夹具各自的**删守卫反证**：变异重算器为纯回放（跳过重算直接返回 recorded）→ 夹具 (a) 必红——这是攻击面 B 的机器化验收
- 全仓回归：六 oracle + go test -race 全包
- 空白子智能体验证循环（同件2/件3 节奏，用户裁定的轻量模式）

## 先验六条（含预登记攻击面）

1. 【攻击面 B·机器化】重放退化成回放：防线=夹具 (a) 的删守卫反证（纯回放器抓不住篡改账本）
2. 判定不经模型、判断经模型但以记录形态进重算（不变量 1 分裂叙述——包注释三层治本）
3. 按记录仲裁序重演不重裁（L5 漂移语义：重算器消费 recorded 的 seq，不重新分配仲裁）
4. 四入口不可互换：入口签名不同（path vs case vs case+substitution），无公共泛化入口——「Do not collapse into one generic call」（07 §6 同律）
5. 差异定位的精度承重（夹具 b）：diff 报告必须指明 step/事件序号，不是布尔「有分歧」
6. expected 钉的是双裁决组合（fidelity×conformance 四象限都是合法 outcome——不是「全过才算过」）

## 碰撞裁决修正（frame-bench，2026-11-01 追加）

1. **A 二分（最重要）**：Inspect 属投影族——独立投影 reducer 合法（codex rollout-trace 先例：reducer 隔离在 core 外只重建视图不重算决策）；Replay/Reevaluate 属重执行族——只许生产状态机重执行（langgraph time-travel "Re-executes nodes"/dsh "booting the real agent" 先例）。配套「无隐藏入口」规则：状态机不得长 replay-only 分支（dsh AGENTS.md 立法）。
2. **B 收窄**：只对真裁决结果（adopt 竞争 first-wins）记序消费；纯事件序（可稳定键排序的）禁入仲裁记录——否则给机器非确定性发执照。并发绑定危险写 Known Limitations（dsh deferred 先例：显式挂账不假装解决）。
3. **C 照抄三机制**：边界假件（replay-only adapter 实现 provider 契约，不 mock 整机）/全消费断言（未匹配查找与未消费记录双向 fail）/fail-loud。
4. **D 形状确认**：codex 瘦脊+外挂载荷（payloads 先于事件写、写入端分配 id）——账本已是瘦脊，夹具 steps=外挂，方向一致。
5. **E 刚性约束**：Python oracle 只从 replay-case.schema.json 驱动（schema-as-source）；Python 侧一旦出现行为判断即杀（防第二实现从格式层走私）。
6. **新颖面唯一**：双 verdict（fidelity×conformance）交互的 runner 输出契约——生态无先例（dsh expected-refusal inventory 是最近似物：conformance 钉成数据+其消失即失败），新投入集中处。
7. **防腐机制采纳**：夹具经生产路径生成（内存 Machine 驱动产出 recorded_events，不手写）；场景序列内联；全消费断言。
