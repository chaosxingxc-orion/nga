# 战场状态存档（2026-11-01 断网快照）

## 本地状态（全部已提交，工作树干净）

- agent-festival @ b4cd338（feat/agent-festival-go-base，比远端 fork 多 2 笔未推送：02dd59d 对齐批+b4cd338 自纠）
- 内容：件0-5 全量 + 对齐债务清偿批（四 schema 出处重锚/漂移登记/词汇映射/碰撞回应留档 docs/）
- 先验：impl-2026-11-01/00-priors-alignment-batch.md（xuefanfan 八段）；碰撞裁决（frame-bench 形态学）在会话史——要点已固化进 README 漂移登记节的「出处锚定形态」段

## 远程状态

- MR !1（xingchao_ml/nga）：open/mergeable，head=3a8cec7（落后本地 2 笔，待推送）
- issue #1：正文=festival 原始议题；评论①=我们的碰撞回应（id 197351704）；邢超未回
- origin/main @ 5df0627（bind efficiency verifier——研究侧，与我们无关）

## 下次续做清单（按用户已裁排序）

1. **推送**：git push fork feat/agent-festival-go-base（02dd59d+b4cd338 上 MR）
2. **A3 夹具格式文档**：docs/conformance-fixture-format.md（钉子纪律/_expect 语法/双 oracle lockstep/Java 消费方式）——碰撞回应提议 1 的落地件，半天
3. **A2 件6 replay runner**（大战役）：internal/replay 四结构化入口+保真/合规双裁决+L5 按序重放；先写先验（xuefanfan 范式）+ frame-bench 碰撞（langgraph time-travel 是状态级对照物）再编码；完成后六件收官+验证循环
4. **A4**：compose 570 行 harness 迁 internal/suite（登记债务）
5. 可选：六问正式回复草稿（issue #1，我们承诺「随后给出」）

## 悬而未决（等邢超，不可推进）

夹具基准正式收编 / Public schemas 槽位（§12.4）/ L1-L5 漂移销账 / rejected 是否持久化

## 长期目标（session goal，未启动）

GEPA+singularity 双探索（语言方向 × 最大解锁角度）——建议在 A2 完成后启动（基线更完整）

## 纪律提醒（本阶段自纠实录）

02dd59d 虚报「旧编号仅存 superseded 句」被自己的 grep 复核抓到（字段级 5 处漏锚）→ b4cd338 自纠。教训固化：grep 复核必须逐处核对命中位置（不能只看计数）；提交信息「声称」必须与 diff 逐条对账。

## 协作分工轴（2026-11 会话结论，2026-11-03 补落盘——曾因零落盘跨会话丢失）

- **夏（架构师）＝协议面**：产出怎么在系统间流动·怎么封存·怎么质证——三边文法（controlled_handoff 命名）、封存件清单双测试准入、来历/查询足迹/排除记录三必填、质证协议 A 定向补证→B 无法判定→C 信任失灵人裁（人裁产出=规格补丁，单向收敛）、evidence_gap 可证伪性准入（confirm/falsify 查询对）、多体拓扑（调查侧各自封存+判定侧共享只读并集、盲判后合议）、元原则「事前结构化优于事中裁量」。载体：05-edge-grammar-prior.md（E7）+ 件3 schema 0.2.0/0.3.0 路线图 $comment + 件7 evidlog 机器面预研。
- **刘＝责任面**：谁担责·问责归谁——专家团共享中间结果（collaborative 边语义来源：不共享做不成一件事，责任在雇主个人，不摊给个体专家）。载体：L4 问责层设计锚（责任锚定在个人）+ collaborative 边语义。
- **xingchao＝语义真源**：07 提案（九对象/七交接族/四回放模式/M01-M15）、三态四面骨架。
- **festival（突突）＝全部实现**：实现归属仅两方——xingchao 侧待实现件（看板 X 徽章）之外，全部实现为我方供件。
- **教训（2026-11-03）**：此轴只在会话中讨论过、未落任何文档，上下文压缩后丢失，靠用户复述原话找回。纪要级结论（人物分工/裁决归属）必须当轮写入本档或看板，不得只留会话史。
