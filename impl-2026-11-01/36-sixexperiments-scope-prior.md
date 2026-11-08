# 36 · 六实验范围框定（2026-11-05）：E1/E2/E4/E5/E6/E-GR

> 范式：xuefanfan 八段（本文件）。出处：33 号 §三 B1/B2/B4/B5/B6/B7（定义/步骤/度量/判定全有，本文件只做落 Go 的工程框定+frame-bench 碰撞+攻击面预登记）。
> 写码纪律：SETools 精神——Go 仓无 Java xlsx 直接适用面，取其精神：**写前看本仓已过闸先例**（e2e 包既有形态：错误信息 `[T2.X]` 前缀、探针命名 TestT2X_YYY、反突变注释「Mutation probe: …」、账本引用行内注），**写完 mental check**（G.ERR 不吞错/G.TYP 判别不手写/G.FMT 声明序——Go 侧对应：error 显式返回、map 迭代 sortedKeys、struct 字段序）。

## IN（六实验逐个：落点+新码量+红探针）

### E1：验证席位原型（B1——E0 极性翻转：存在性证明→拦截性证明）

- **落点**：新文件 `go/internal/e2e/verifier.go`（测试内组件，非生产件）+ `verifier_test.go`。
- **形态**：`verify(spec *fixtureSpec, raw rawEvidence) checkResult`——确定性函数，读夹具 JSON（P3 修正后的无界 veto）+原始证据结构（**不读 S1 提取产物**）。
- **布线**：图内 judge→verify→adopt（taskHarness 扩展一环）。
- **极性翻转**：`correctnessLayerLanded` 翻 true（correctness_probe_test.go:37）——E0-sick 双测试的 skip 守卫触发后**重写测试体**（R20 B-1 教训：翻 flag 必须拆守卫/重写断言，绝不留死代码）。
- **提取陷阱臂**：S1 喂 extractedEvidence（漏逾期）、verify 喂 rawEvidence（含逾期）→ 断言拦截（杀「验证器继承提取错误」）。
- **度量**：WGR 1/1→0/1；拦截位点=verify 层采纳前零外部调用；控制事件 +1；**阳性对照不受损**（健康 grant 不被误拦）。
- **红探针**：撤 verify 门→sick grant 直通采纳（红）；撤提取臂→拦截消失（红）。

### E2：证据覆盖声明×规约要求差集（B2——反例 B 的机器面）

- **落点**：`verifier.go` 内 `coverageGap(spec, presentSources) []string`（差集函数）+ E2 测试文件。
- **形态**：夹具 evidence_sources 声明必需（历史全量台账）；输入快照声明在场源；差集≠∅→路由 on_missing_evidence（判定前拦截）。两形态跑表对比择一预声明：S1 未被询问（前置拦）vs S1 收结构化缺口。
- **度量**：反例 B 错授 0/1；缺证记录带差集明细；差集为空正常放行（阳性对照）。
- **红探针**：撤差集门→反例 B 产生 grant（红）。

### E4：拦截频次健康度+守卫死亡探针（B4——夏 2.5 补条一的机器面）

- **落点**：`go/internal/e2e/health.go`（测试内读数组件）——`aggregate(events []ledger.Event) frequencyReport`（按策略类别聚合 rejected/control 频次）+ `guardDeath(report, trafficVolume) bool`（频次归零而流量持续→告警）。
- **形态**：纯函数读 Machine.Events() 输出；零机器改动（读数面在 e2e 层，机器不膨胀）。
- **度量**：聚合正确性（已知事件集逐类对账）；守卫死亡检出率 1/1；健康流不误报。
- **红探针**：撤死亡检测条件→死亡场景静默（红）；聚合键错→对账红。

### E5：读取授权变体（B5——D-04 缺口验收面；**L39 已在先行批落地**，本实验=验收面独立化）

- **落点**：`t2host_test.go` 现有 nodeEntry(callerGrants) 之上——新测试组 `TestE5_ReadAuthorizationVariants`：撤销后读取拒（空 grants/降级 grants 两形态）+授权读取对照+**降级 grants 形态**（先行批只测了空/非空）。
- **新码量**：极小（tests only）。价值=向邢超展示宿主侧形态完整（Q5 点名要求 R/K 反例纳入）。
- **红探针**：nodeEntry 撤 grants 检查→未授权读取被服务（红）。

### E6：C4 条件提交+双窗口声明（B6——邢超 §一.4 收口）

- **落点**：`adopt.go` Dispatch 提交门（**唯一一处生产件改动**）+ e2e 竞态注入测试。
- **形态**：Dispatch 携带被检序版本（op 当前期望 revision）；宿主持序存储只接受「被检版本仍当前」的提交；竞态注入=检查后提交前 D2 生效（模拟：第二操作完成→版本推进→旧版本提交）→断言拒绝+控制事件。撤销后 API 前窗口：14-A4 同型再检（Dispatch 已有 grantsCover——补声明句）；已发出未确认：MarkUnresolved 既有（T0 场景 5 已钉）——只补声明句。
- **度量**：陈旧提交率 0；两窗口行为与声明逐字一致。
- **红探针**：撤版本检查→陈旧提交成功（红）。
- **先验三条见下**——这是六实验唯一动生产件的，攻击面最大。

### E-GR：坟场回捞触发器（B7——夏 2.2 护栏一）

- **落点**：`health.go` 内 `graveyardSweep(entries, maxCount, maxAge) []string`——台账条目计数/计龄→阈值触发回捞清单事件。
- **形态**：纯函数+测试；第一个用户=minor 台账自身（L1-L47）——跑一次真实回捞清单作为演示输出。
- **度量**：触发确定性（阈值边界恰好 N/N+1）；清单完整性（超限条目全列）。
- **红探针**：撤阈值比较→超限不触发（红）；边界 off-by-one（N 条不触发、N+1 条触发）。

## OUT

- T1-run3（真 LLM——用户启动，另线）；B8 粒度二通道 A/B（先决条件挂起）；C1/C2（清单三分析量大未裁决）；0.2.0 schema 批次（第三步）。
- E6 不做：宿主侧序存储的真实进程间竞态（e2e 层用确定性注入模拟时序，非并发压测）——声明边界。
- E4 不做：持久化 metrics 后端（内存报表函数即可，运维面是演示形态）。

## 复用清单（不重设计）

- E1：fixtureSpec/fixtureVetoRule 解析（correctness_probe_test.go 既有）；creditEvidence/rawEvidence 形态（e2e_test.go）；control 事件通道（adopt.refuse 既有）。
- E2：evidlog CheckCoverage 差集告警同型（声明 vs 足迹→来源覆盖对账）；fixtureSpec.Conventions.EvidenceSources。
- E4：Machine.Events()（adopt.go:466）；ControlStatuses（ledger.go:35）。
- E5：nodeEntry（t2host_test.go，先行批 L39 已建）；chainGrants。
- E6：commit/refuse（adopt.go 既有）；grantsCover（14-A4 检查同型）；T0 场景 5 的 MarkUnresolved 钉。
- E-GR：ParseLines/LoadDocument（ledger/load.go）。

## 依赖 DAG

E1 → E2（同一 verifier.go；E2 的差集在验证席位内或判定前跑表）；E4/E-GR 独立（health.go，只依赖 ledger 公开面）；E5 独立（t2host 层）；E6 独立（adopt 层，唯一生产件）。**并行序：E6 先做（攻击面最大、先验最厚）→ E1 → E2 → E4 → E-GR → E5（最小收尾）。**

## 骑轮子检查（frame-bench 碰撞·支持项）

- **E1 确定性约束门**：hermes-self-evolution `evolution/core/constraints.py:1-7`——「Every candidate variant must pass ALL constraints… Failed constraints = immediate rejection」确定性硬门+LLM 仅咨询的同型分层。生态先例支持 verify 作为确定性门、LLM 仅咨询位。
- **E4/E-GR 确定性聚合**：langgraph `pregel/_algo.py:254-255,480` 全部 sorted() 键序——聚合读数按类别键序输出（与本仓 sortedKeys 纪律同型）。
- **E6 提交门**：无直接生态先例（宿主持序单源+版本化提交是本仓控制语义域内形态）——按 13 号设计注记+认领的 CAS 修正自建，属领域语义合法区（非通用轮子）。
- **E2 差集**：evidlog CheckCoverage 同型推广（声明 vs 足迹→来源覆盖）——零新概念，仓内先例。

## 验证协议（做完后）

1. 每实验红探针先红后绿（修复落地后跑反向突变变红）。
2. E1 极性翻转后：`correctnessLayerLanded=true` 且 E0-sick 重写体活断言（grep 无 skip 残留——B-1 教训的机械自检）。
3. 全量 race 21 包绿；E6 改动后 adopt 包原测试全绿（无回归）。
4. 六实验各有「预期产出」对账（33 号 B1/B2/B4/B5/B6/B7 逐条勾）。

## 先验三条（预登记攻击面）

1. **E6 是唯一生产件改动**：Dispatch 加版本参数改签名——所有既有 Dispatch 调用点（e2e 包 10+ 处、t2host 3 处）须同步；竞态注入是确定性时序模拟非真并发（边界声明）；版本语义若与 EvaluationRevision 混淆会引入 L42 同族字典序病——版本比较必须数值域（revisionNumber 同族教训）。
2. **E1 极性翻转的重写纪律**：correctnessLayerLanded 翻 true 后两处 skip 守卫必须重写测试体（B-1 的病就是翻 flag 不重写）；verify 读 raw 不读 extracted 的边界若含糊，提取陷阱臂会假绿。
3. **E-GR 阈值边界**：N/N+1 off-by-one 是经典病；maxAge 的「天」语义在测试内须确定性（注入固定时钟或按条目序号模拟年龄——真时钟不可测）。
