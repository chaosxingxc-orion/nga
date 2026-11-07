# 37 · 六实验收官记录（2026-11-06）：E1/E2/E4/E5/E6/E-GR 全落地，预期产出逐条对账

> 出处：36 号八段先验 + 33 号 §三 B1/B2/B4/B5/B6/B7。全部零 LLM、全部确定性、每实验配反突变红探针。

## 逐实验对账（33 号「预期产出」承诺 → 实态）

| 实验 | 33 号承诺 | 实态 | 反突变 |
|---|---|---|---|
| **E1** 验证席位 | 存在性→拦截性证明；WGR 1/1→0/1；correctnessLayerLanded 翻转；提取臂拦截；阳性对照不受损 | ✅ 兑现（R29 收窄后）：verify() 确定性门（读 raw 不读 extracted，hermes 同型）；**拦截于派发前**——【R29 M-5 更正】决策记录被采纳（机器盲设计），宿主扣的是派发（不写 unresolved 假事实，operation 停在 adopted）；E0 双测试重写为拦截断言（B-1 纪律同提交拆守卫）；阳性 deny 过门；镜像面+中带面有红探针（R29 M-4 前=死守卫）——【R36 M-1/R38 m-2 更正】中带面已删（被级档一致面包含性吞噬），between-bands 语义与红探针改挂级档面独占 reason；阈值锚定夹具（R29 M-3 前=硬编码漂移不可检） | verify 恒通过→双臂红；镜像面删除→红（M-4 补）；夹具阈值漂移→锚测试红（M-3 补） |
| **E2** 覆盖差集 | 反例 B 机器可拦；声明性缺证带差集明细；差集空正常放行 | ✅（R29 M-5 收窄）coverageGap(presentSources)（requiredSources 机器投影表+sorted 确定性）；反例 B 形态判定前拦截（记录采纳、派发扣留）；【更正】33 号承诺的「缺证记录带差集明细」实际落在宿主层 refusal（gap 是测试局部量，未入账本事件 detail）——账本面留待 0.2.0 输入快照 schema | coverageGap 恒空→红 |
| **E4** 频次健康度 | 夏 2.5 补条一机器面；聚合正确；死亡检出 1/1；健康流不误报 | ✅（R29 B-1/M-6 收窄）aggregateControl/guardDied 纯函数（零机器改动）；死亡语义=「控制面静默+effect 流量持续」——**混合流（拦截后跟授权派发）与死亡不可区分**（机器语义盲的事件流表达力边界，混合流钉子用例文档化）；按 status 无法点名单个守卫（全 reject 同 status，掩盖形态已声明）；「健康流不误报」更正为「纯控制尾流不误报」 | 死亡条件移除→红 |
| **E5** 读取授权变体 | D-04 从认领变已拦；L39 清账 | ✅ **实验价值实证**：先行批 L39 只测空/非空——E5 的降级形态（selector 收窄）当场被服务=真缺口。nodeEntry 升级为 grants 覆盖检查（grantsCoverRead：kind/selector/actions 全匹配）；三形态断言（授权服务/空拒/降级拒）+机器盲边界声明钉 | 回退非空检查→降级形态被服务→红 |
| **E6** 条件提交 | C4 从设计注记升为带对抗用例的实现；陈旧提交率 0；两窗口逐字声明 | ✅ DispatchIfCurrent（**opt-in 独立方法——46 个 Dispatch 调用点零改动**）；opState.dispatchedSeq 记忆（replay 同步重建，R29 M-1 后 sentinel -1 真初始化）；陈旧观察拒绝+控制事件入账；**双窗口声明写入 doc**——【R29 M-2 收窄】窗口 1 覆盖撤销形干预+伪造/跨线观察；**同操作 CAS 形在本状态机无可达态**（adopted 无回边、版本不可能 stale）——该形保护在宿主层，不在此门 | 版本门移除→陈旧提交成功→红 |
| **E-GR** 坟场回捞 | 夏 2.2 护栏一机器面；触发确定性；首个用户=minor 台账 | ✅ graveyardSweep（age 面+count 面独立+组合完备性）；边界 N/N+1 精确钉死；minor 台账合成形状演示（构造年龄 L-1..L-47，非解析真台账——R31 m-3/R33 m-9 更正；阈值 30/45→19 条回捞清单） | excess 膨胀→多列被抓→红 |

## 过程发现（实验自身的诚实记录）

1. **E6 测试第一版叙事错误**：「unresolved 后重派」违反既有钉（adopt_test.go:324 no-auto-retry）——重写为诚实的可达形态（cross-wired 观察），并把「版本门在普通流内不可达」作为 finding 记录。
2. **E5 抓到先行批的真缺口**：L39 的空/非空检查放行降级 grants——E5 不是复述已有断言，是实测出缺口并关闭（33 号预言「真断言非文档式」兑现）。
3. **E4 探针第一次写错**：phase-2 只有 adoption 无 effect——adoption 的 EventType 是 "adoption" 非 "effect"，死亡探针无流量可比。修正后死亡语义诚实（拦截史+持续 effect 流量+归零）。
4. **E-GR `>=` 突变不可检的函数形态属性**：恰在 maxEntries 时进入 count 面但 excess=0 不列——> 与 >= 行为恒等。诚实修正：突变声明收窄到 excess 算术（可检形态），不声称边界比较突变可检。
5. **E2 requiredSources 方向 bug**：key/value 写反被首个红测抓出（seTools 精神：探针先红即抓实现病）。

## 纪律账

- 每实验反突变红（6/6）；全量 race 21 包绿；vet 干净；gofmt ——【R29 m-7 更正】收官提交时 adopt.go 实有 gofmt -l 命中（新注释三空格缩进），R29 清偿批已 -w 修复；本行原声明与收官提交时点事实不符。
- SETools Go 精神：写前看仓内先例（adopt_test 的 testRequest/mustOpen、e2e_test 的 digestHex/chainGrants 形态全部复用）；E5 helper 命名 grantsCoverRead 避开 adopt 包私有同名。
- xuefanfan 八段（36 号）全程对照；预期产出逐条对账（本文件）。
- 过程失误一次：E5 反突变后用旧 /tmp 备份恢复，丢失 nodeEntry 升级——检出（grep grantsCoverRead=0）后重落。教训入账：**备份必须在每次升级后刷新，反突变恢复用副本前先确认其内容版本**。

## 提交

- E6：adopt.go（dispatchedSeq+DispatchIfCurrent）+ adopt_test.go（TestE6_ConditionalCommit）
- E1/E2/E5：verifier_test.go（verify/coverageGap/E2/E5 测试）+ correctness_probe_test.go（E0 重写+loadE3Fixture）+ t2host_test.go（grantsCoverRead+nodeEntry 升级）
- E4/E-GR：health_test.go（aggregate/guardDied/graveyardSweep+四测试）
