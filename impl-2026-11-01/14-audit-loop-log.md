# 14 · 审核循环日志（session goal，2026-11-03 深夜）

> 协议（用户当轮指令）：每轮一个审核位（编译+测试+测试面恒积累+4-lens+singularity）；发现 B/M → 代码里同类穷举 → 修 B/M、积累 minor 不修；内层循环至 0M/0B；外层连续 2 轮 0B/0M 停止（或 ≤10 轮）。
> 审核对象：上次推 MR（baca2dd）至今的全部增量——1765a9c（P1-1+P1-2）+ 151a39f（E3 control）+ d727607（docs）+ ee7cba5（R1 修复）。

## R1（脏轮：1 MAJOR → 修复 → 变异自证）

- 机械门：编译✓、六包测试✓、测试面 36→40（adopt）/25→27（evidlog）单调增长✓。
- 4-lens+singularity 审增量：**0 BLOCKER / 1 MAJOR**——replay 的 Inspect/Recover 两处 `lines, _, err := LoadDocument` 丢弃断尾信号：审查/恢复工具对受损账本给出静默绿；replay.go:95 自陈旧注释承认此债（「closing this belongs to the loader」——loader 已报告，消费边界仍在吞）。同类=「信号在消费边界被吞」。
- 同类穷举：t.Parallel 无（umask 探针安全）；os.Stat 吞咽三处均为存在性探测（语义正确）；os.Chmod 仅两处已收敛；断尾标志丢弃点全仓扫（Events() 的 `_` 在其文档注释中已声明排除语义，非同类）。
- 修复（ee7cba5）：InspectReport/RecoverReport 增 TornTail 字段 + Inspect 的 Gaps 通道加断尾行；前缀投影语义不变（统一教义下机器损害后拒写=前缀即完整历史）。探针 TestInspectSurfacesTornTail + 变异自证（字段退化 false → 红）。
- minor 记账：L16-L20（五条，见台账）。

## R2（净轮）

- 机械门：锁步三面交叉（schema 枚举 {adoption,control,effect} ↔ Go TestStatusVocabularyLockstep/TestSharedSubtreeLockstep PASS ↔ Python check_status_lockstep OK）；TornTail() 重入安全（唯一外部调用方 Recover 无锁持有）；全量 -race 20 包绿；增量总账 28 文件 2037+/152-。
- 4-lens+singularity（含内层复审 R1 增量）：**0 BLOCKER / 0 MAJOR**。Simplicity（三修复均为病理净删除：加宽动作删/治愈教义删/无痕拒收变有痕）✓；Consistency（断尾教义三包统一、control 族双 oracle 封闭、L14 台账记推翻）✓；Bearing（四组变异自证红→绿+wrong-reason 钉）✓；Fidelity（doctrine 注释/README 词汇表/陈旧注释三处对齐）✓；singularity 无可达坏状态、无锁定。
- 内层循环关闭（R1 增量复审 0M/0B）。

## R3（净轮——连续第二次，停环）

- 机械门：全仓同类扫尾（断尾标志丢弃点全部已消费或文档声明；err==nil 静默分支仅剩 evidlog:673 的 try-parse 非吞咽）；全量 -race 20 包绿。
- 判定：**0 BLOCKER / 0 MAJOR**。

## 终态

- R1 脏（1 MAJOR 修复+变异自证）→ R2 净 → R3 净 = 连续 2 轮 0B/0M，按协议停止。
- 累计：4 组变异自证、5 个新探针、5 条 minor（L16-L20 入台账不修）、增量 28 文件 2037+/152-。
- 待口令：推送 MR !2（head baca2dd→本批）。session goal 原文为「3 连 0B/0M」——本轮协议取当轮指令的「连续 2 次」口径；若需 3 连口径，R4 一轮即补。

## R4（T0 增量轮，净——连续第三次，session goal 3 连口径闭环）

- 增量：internal/e2e（doc.go+e2e_test.go，九场景=§11.B 八场景+happy path，全 Go 模型替身）。
- 机械门：build/vet/-race 全绿（21 包）、manifest 绿、测试面 +9 场景。
- 4-lens：Simplicity（零新产线码、零新公共 API）✓；Consistency（替身实现修正后否决语义并标注 P3 依赖；deny 场景第一稿错把宿主层选择断言成机器拒绝——被测试失败当场纠正，终稿注释固化「框架不解释业务语义」原则）✓；Bearing（变异自证：否决窗口化退化→三场景红）✓；Fidelity（doc.go 声明 Tier-0 测试边界=四层证据纪律；场景名↔§11.B 逐条映射）✓。
- 同类扫尾（「测试断言错层语义」类）：逐断言过层——终稿全部断机器可观事实，C4 缺口如实钉注不掩盖。净。
- singularity：无产线码变更→无机器层可达性变化；替身业务语义只住测试层（P3 落地时同步=已登记 L22）。
- 判定：**0 BLOCKER / 0 MAJOR**（L21/L22 记账）。

## 终态（3 连口径）

R1 脏（1 MAJOR 修复+变异自证）→ **R2 净 → R3 净 → R4 净 = 连续 3 轮 0B/0M**——session goal 原文口径（3 连 0blocker 0major）达成。

## R6（空白终审·退出叠加守卫轮，脏轮：2 MAJOR → 修复 → 三组变异自证）

- 触发：R5 自审后按 review-loop 第 9 步叠加守卫（退出前最后一轮必须全强度外环）+ goal 原文「空白子」——R4/R5 系自审，4-lens 铁律自审只配 PLAUSIBLE，收口轮必须独立位。空白子 52 工具调用，禁读 impl 目录/密钥/网络。
- **发现 2 MAJOR（均 CONFIRMED，①确定性探针由审计位亲跑）**：M-1 control 事件绕过 attribution-divergence 规则（伪造归因的拒收记录双侧双绿+Open 放行——E3 传播漏点）；M-2 transition loop 双侧 guard 分叉（同文档 Go 2 错/Python 1 错，聚合契约排他性证伪）。4 minor（L23-L26）。机械门全绿。
- **自审盲区实证**：两 M 均长在 R4/R5 自审两轮看过的代码上——「退出守卫末轮必须独立全强度」的立法价值当场兑现。
- 修复（commit 见 git log）：双侧 attribution 扩展+Python guard 对齐 Go 形态+两永久 wrong-reason 夹具（含首个显式双违规文档）+计数钉三处 rebase。三组变异自证：Go 撤归因扩展→5 红；Python 撤归因→红；Python 撤 guard 对齐→M-2 探针+存量夹具双红。全量回归双侧绿。
- singularity 判决：族复发 ≥2（词表增长×手镜像规则位点）——结构升级候选登记未启动（规则位点 parity 网/分派表）；按律若启动须转移后全强度外环+证伪器再生。
- **连胜重置**（R2-R5 的 4 连清零）。重建从 R7 起：对 M-1/M-2 修复增量做单审核位轮。
