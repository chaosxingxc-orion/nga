# 37 · 六实验收官记录（2026-11-06）：E1/E2/E4/E5/E6/E-GR 全落地，预期产出逐条对账

> 出处：36 号八段先验 + 33 号 §三 B1/B2/B4/B5/B6/B7。全部零 LLM、全部确定性、每实验配反突变红探针。

## 逐实验对账（33 号「预期产出」承诺 → 实态）

| 实验 | 33 号承诺 | 实态 | 反突变 |
|---|---|---|---|
| **E1** 验证席位 | 存在性→拦截性证明；WGR 1/1→0/1；correctnessLayerLanded 翻转；提取臂拦截；阳性对照不受损 | ✅ 全兑现。verify() 确定性门（读 raw 不读 extracted，hermes constraints.py 分层同型）；sick grant 拦截于采纳前+宿主层面 unresolved 停车（零 dispatch/completed 事件）；E0 双测试重写为拦截断言（**B-1 纪律：同提交拆守卫，无 skip 残留**）；阳性 deny 过门不受损；镜像面（伪造 deny 也拦）+中带面（open question 出 grant 也拦） | verify 恒通过→双臂红 |
| **E2** 覆盖差集 | 反例 B 机器可拦；声明性缺证带差集明细；差集空正常放行 | ✅ coverageGap(presentSources)（requiredSources 机器投影表+sorted 确定性）；反例 B 形态（只有近期台账）缺证在判定前拦截（S1 未被询问形态）；阳性全源放行 | coverageGap 恒空→红 |
| **E4** 频次健康度 | 夏 2.5 补条一机器面；聚合正确；死亡检出 1/1；健康流不误报 | ✅ aggregateControl/guardDied 纯函数（Machine.Events() 输入，零机器改动）；死亡语义=「有拦截史+流量持续+拦截归零」（从未被挑战≠死亡——误报面钉死）；死亡检出+误报面双测试 | 死亡条件移除→红 |
| **E5** 读取授权变体 | D-04 从认领变已拦；L39 清账 | ✅ **实验价值实证**：先行批 L39 只测空/非空——E5 的降级形态（selector 收窄）当场被服务=真缺口。nodeEntry 升级为 grants 覆盖检查（grantsCoverRead：kind/selector/actions 全匹配）；三形态断言（授权服务/空拒/降级拒）+机器盲边界声明钉 | 回退非空检查→降级形态被服务→红 |
| **E6** 条件提交 | C4 从设计注记升为带对抗用例的实现；陈旧提交率 0；两窗口逐字声明 | ✅ DispatchIfCurrent（**opt-in 独立方法——46 个 Dispatch 调用点零改动**）；opState.dispatchedSeq 记忆（replay 同步重建）；陈旧观察拒绝+控制事件入账；**双窗口声明写入 doc**（窗口 1 全覆盖/窗口 2 诚实声明残留+MarkUnresolved 既有）；测试内如实记录一个设计发现：单操作内版本门从普通流不可达（unresolved 拒绝重派——14-A5 no-auto-retry），门的真实面=跨线/损坏观察 | 版本门移除→陈旧提交成功→红 |
| **E-GR** 坟场回捞 | 夏 2.2 护栏一机器面；触发确定性；首个用户=minor 台账 | ✅ graveyardSweep（age 面+count 面独立+组合完备性）；边界 N/N+1 精确钉死；minor 台账实跑演示（47 条 vs 阈值 30→19 条回捞清单） | excess 膨胀→多列被抓→红 |

## 过程发现（实验自身的诚实记录）

1. **E6 测试第一版叙事错误**：「unresolved 后重派」违反既有钉（adopt_test.go:324 no-auto-retry）——重写为诚实的可达形态（cross-wired 观察），并把「版本门在普通流内不可达」作为 finding 记录。
2. **E5 抓到先行批的真缺口**：L39 的空/非空检查放行降级 grants——E5 不是复述已有断言，是实测出缺口并关闭（33 号预言「真断言非文档式」兑现）。
3. **E4 探针第一次写错**：phase-2 只有 adoption 无 effect——adoption 的 EventType 是 "adoption" 非 "effect"，死亡探针无流量可比。修正后死亡语义诚实（拦截史+持续 effect 流量+归零）。
4. **E-GR `>=` 突变不可检的函数形态属性**：恰在 maxEntries 时进入 count 面但 excess=0 不列——> 与 >= 行为恒等。诚实修正：突变声明收窄到 excess 算术（可检形态），不声称边界比较突变可检。
5. **E2 requiredSources 方向 bug**：key/value 写反被首个红测抓出（seTools 精神：探针先红即抓实现病）。

## 纪律账

- 每实验反突变红（6/6）；全量 race 21 包绿；gofmt/vet 干净。
- SETools Go 精神：写前看仓内先例（adopt_test 的 testRequest/mustOpen、e2e_test 的 digestHex/chainGrants 形态全部复用）；E5 helper 命名 grantsCoverRead 避开 adopt 包私有同名。
- xuefanfan 八段（36 号）全程对照；预期产出逐条对账（本文件）。
- 过程失误一次：E5 反突变后用旧 /tmp 备份恢复，丢失 nodeEntry 升级——检出（grep grantsCoverRead=0）后重落。教训入账：**备份必须在每次升级后刷新，反突变恢复用副本前先确认其内容版本**。

## 提交

- E6：adopt.go（dispatchedSeq+DispatchIfCurrent）+ adopt_test.go（TestE6ConditionalCommit）
- E1/E2/E5：verifier_test.go（verify/coverageGap/E2/E5 测试）+ correctness_probe_test.go（E0 重写+loadE3Fixture）+ t2host_test.go（grantsCoverRead+nodeEntry 升级）
- E4/E-GR：health_test.go（aggregate/guardDied/graveyardSweep+四测试）
