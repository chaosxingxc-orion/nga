# 34 · 我方先行批范围框定（2026-11-05）：P3 夹具修正+L23 对齐+T2 轴承修复 L39-L47

> 范式：xuefanfan 八段（本文件）。出处：33 号 §5.3 路由优先序第一步。

## IN

### P3+L23（内部一致性——所有正确性工作的地基）

1. **judgment-spec-credit.json:47 veto 去窗口化**：coverage 从「any overdue longer than three months in the window」改为「any overdue longer than three months at any time in the applicant's credit history on record」（对齐 08:183+10:145 出处）。同时修 time_window 约定+term overdue 定义解耦+`_expect` 改真+补 R14 反例为用例。
2. **L23 修正**：e2e_test.go s1Judge 的 C8 优先序对齐 t1Spec（否决先于缺证检查——当前 T0 先查 assetReportOK 返回 on_missing_evidence，t1Spec 把否决放 precedence 0）。
3. **p3FixtureCorrectionLanded 翻转**（correctness_probe_test.go:40 的极性守卫触发）。
4. **correctnessLayerLanded 不翻**（验证席位是 E1 实验的事，本批只修规格+替身）。

### T2 轴承修复（L39-L47 中可修的 7 项）

5. **L39 PermissionRevoked 补真断言**：T2 节点入口加 caller 授权参数→真撤销→真拒绝。
6. **L40 READ 4 独立断言**：纠错场景补第四读（知识消费面）——注册表发布修正后方法→检索→断言当前有效。
7. **L41 node entry 提为组件**：从 t2host_rk_test.go 内联重提交逻辑提为 t2host_test.go 的 `nodeEntry` 方法。
8. **L42 revision 比较改数值域**：lookupByBusinessRequest 的 revision 比较从字典序改为数值域（er-10 vs er-2）。
9. **L43 findForNode 迭代序确定化**：加确定性键序（sorted keys）。
10. **L44 Sscanf 响亮**：overdue_months 解析失败返回 error 而非静默为 0。
11. **L47 E0 extraction-miss 补极性守卫**：加 correctnessLayerLanded guard。

## OUT

- L45 resultStore 原子写（非阻塞——T2 是验证夹具不是生产件，文档声明即可，留为 minor 不修）
- L46 店-账本一致性交叉核（同上——跨持久面声明，非本批）
- 验证席位/E1 实验不在本批（第二步）
- 0.2.0 schema 批次不在本批（第三步）

## 复用清单

P3 夹具修正方案=issue#1 碰撞回应 Q4 时已备（veto 去窗口化+term 解耦+_expect 改真+反例补用例）；T2 node entry 提升=把 e2e_test.go:68-77 的 host-side check 逻辑搬为 t2host_test.go 的方法。

## 验证协议

1. P3 后 E3-window 极性翻绿（p3FixtureCorrectionLanded=true → E3 skip→重写为断言无界）——极性守卫的翻转验收
2. L23 后 C8 场景（T0 场景 8+T1 C8）行为一致（都是 deny）
3. L39-L47 修复后 T2 全量复跑绿+全量 -race 绿

## 骑轮子检查（frame-bench 碰撞结论）

**L42/L43 确定性**：langgraph `pregel/_algo.py:255/481/612` 全部用 `sorted()`——生态在状态调度层全部做确定性键序。T2 的 map 迭代序不确定性是非主流形态。修法：`sorted(keys)` 循环。

**L39 读取授权**：claude-sdk `canUseTool` 是宿主级检查回调（sdk.d.ts:1246: "Per-tool permission policy the host declares"）——读取授权是宿主面，不是工具面。T2 的 nodeEntry 加授权参数是同型。

**L44 静默吞**：无生态直接先例（都不是解析场景）——但这是 SETools 元纪律（G.ERR 族：不吞错误）的适用面。修法：返回 error。

## 先验三条（预登记攻击面）

1. **P3 修正可能破坏既有夹具套件**：credit fixture 是 valid 夹具，改 coverage 文字+time_window 后 schema 校验应仍过（schema 只查结构不查语义文字），但 _expect 内容变化可能触发 oracle 对置——跑完看。
2. **L23 优先序修正会翻转 T0 场景 2 的 C3 场景行为**：缺证+有历史逾期时 s1Judge 现在返回 deny 而非 on_missing_evidence——T0 场景 2（TestT0MissingEvidenceThenSupplement）可能需要调整（如果它的输入不包含历史逾期就没事——回查）。
3. **T2 nodeEntry 提升可能引入新的接口边界**：从内联代码提取为方法时，参数/返回值的形态设计是接口设计——过度参数化=失简。最简形态：`nodeEntry(op, brID, revision, evidence, digest, receipt, facts) Outcome`——保持与 adoptAndDispatch 相同的签名。
