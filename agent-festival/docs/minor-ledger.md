# 未修 MINOR 台账（R20 循环宪法：minor 一律不修只记账）

记账规则：外环/内环发现的 MINOR 一律不入修复循环——修 B/M + 同族穷举，
minor 只记账。本文件即台账；每轮新增追加，不删除（退役另标）。

**清偿证明协议（R55 后立法——虚假清偿八次实证的结构性退役）**：
从 R56 起每条 M/B 清偿的台账条目**必须内嵌突变命令 token**——形式
`[mutation-proof: <可复跑命令> → FAIL]`。没有 token 的清偿条目 =
**自动 M**（空白子审核火力面新增此项）。token 必须在提交前当轮跑过
且输出含 FAIL——声称跑过而 grep/测试结果可当场证伪（R55 M-1 形态）
= 比虚假清偿更重半级（伪造验证证据级）。纯文本 token 仍可伪造——
0.2.0 批将其机器解析（CI 可跑）后彻底不可伪造。

## R20-R21 前转入（R18 内环六 m + R19 内环二 m 的遗留）

| # | 位置 | 内容 | 来源 |
|---|---|---|---|
| L1 | examples/java-consumer/README.md:4,20 | ~~83→81 算术错~~ [RETIRED R22]；~~「wrong-reason pins hit」断句残留~~ [RETIRED 2026-11-03]（前句补句号+续句大写起句，孤儿短语归位） | R18 内环 m1/m2 |
| L2 | examples/java-consumer/src/main/java/spike/Main.java:37 | ~~FORMAT_DOC_CLAIMS release 行尾注释同文双写~~ [RETIRED R22] | R18 内环 m3；清偿=fa18315（注释重复已删） |
| L3 | examples/java-consumer/src/main/java/spike/Main.java:155 | ~~COUNT-FAIL 消息钉值 200 未随比较值改 205~~ [RETIRED R22] | R18 内环 m4；清偿=fa18315（消息已 205，R22 内环复核） |
| L4 | examples/java-consumer/src/main/java/spike/LedgerChecker.java:120-129 | ~~family-4 节头 v1 ±2^53 NOTE~~ [RETIRED R22] | R18 内环 m5a；清偿=fa18315（R16 章程重写已落地，R22 复核） |
| L5 | examples/java-consumer/src/main/java/spike/LedgerChecker.java:37-39 | ~~TWO_POW_53 孤儿字段~~ [RETIRED R22] | R18 内环 m6；清偿=fa18315（grep=0，R22 复核） |
| L6 | schema/replay.py:4-5 | ~~docstring「drives ONLY from schema」残句~~ [RETIRED R22] | R19 内环二 m1；清偿=34ef349（R17 已修，R22 复核） |
| L7 | schema/compose.py:423 | ~~尾句「non-integral float reaches dec() and raises」~~ [RETIRED R22] | R19 内环二预存注记；清偿=d4bdc48（R19 回修已改「never reaches dec()」，R22 复核） |

## R21 起新增记账

| # | 位置 | 内容 | 可达性 | 来源 |
|---|---|---|---|---|
| L8 | go/internal/validate/validate.go:952（LoadFixture 裸 json.Unmarshal，compose 族经 WithLoader 骑此面） | 解码纪律双轨：章程全称条款「解码必须 UseNumber」存在未豁免违反面——七族唯 compose 骑非合规 loader。今日零后果（bounds schema 上限 2^53-1 恰为折叠边界，域内折叠精确/超域折叠后仍超上限双侧同拒）；开窗条件=待裁①转 literal-only（字面量门在 float64 map 不可判定）或新增无 2^53 上限数值域（2^53+1 Py 精确/Go 折叠成 2^53 判决分叉）。修法挂待裁①落笔时同步（WithLoader 换 UseNumber）或章程显式登记「base loader=已知违例面」 | 趋零可达（双条件才开窗） | R21 外环 MINOR-1 |
| L9 | go/internal/evidlog/evidlog.go:240 + go/internal/adopt/adopt.go:475 | ~~durable 文件权限位静默翻转~~ [RETIRED 2026-11-03]：两包 Rename 前 os.Chmod(tmp, 原 mode;首次落盘 0644)，永久探针 TestAppendPreservesDurableMode + TestAdoptPreservesDurableMode（修前双红 0600 实证/修后绿） | 本地构造 | R21 外环 MINOR-2 |

| L10 | schema/_suite.py + go/internal/validate/validate.go | 双 oracle invalid 面 wrong-typed `_expect_composed` 行为分叉（Py LOUD 拒/Go 静默收——同一语料一红一绿套件判决分叉；valid 面双侧一致响亮）。修法：Go suite.Run invalid 循环镜像 extra-key 响亮面，或登记 strict-side-wins forced divergence | 本地构造（语料零存在） | R22 外环 MINOR-1 |
| L11 | schema/compose.py:56 | ~~死 import（`from validate import load as load_json`）~~ [RETIRED 2026-11-03]（删行，compose 套件 10+36 复绿） | 趋零可达 | R22 外环 MINOR-3 |
| L12 | schema/compose.py:73-75 | ~~dec() docstring 引已废除的「double charter」~~ [RETIRED 2026-11-03]（改引待裁①登记=docs/conformance-fixture-format.md） | 趋零可达 | R22 外环 MINOR-4 |

## 增量内环记账（2026-11-03，单空白位 4-lens+singularity 审 6a6cb38+4b86b70——0B/0M/2m/1NIT，无可达奇点）

| # | 位置 | 内容 | 可达性 | 来源 |
|---|---|---|---|---|
| L13 | docs/conformance-fixture-format.md:73 | ~~待裁登记①括注成死描述~~ [RETIRED 2026-11-03]（括注改「compose.py docstring 已改引本登记」） | 文本面 | 增量内环 MINOR-1 |
| L14 | go/internal/evidlog/evidlog.go + go/internal/adopt/adopt.go | ~~首写 0644 绕 umask~~ [RETIRED 2026-11-03；**同日被外部复核推翻再清偿**（P1-1，MR !2 评论 197847238）：原退役理由「维持 0644 直设」答非所问——对方提案 0600 定值，裁决反驳的是没人提的 0o666&^umask。终局=新建 0600 保守默认（组件不替部署方扩大可见范围）+既有保留+Stat 非 NotExist 显式报错（durableMode 助手），永久探针 TestFirstWriteOwnerOnlyUnderUmask077（对方探针收编）+TestDurableModeStatErrorFailsLoud，变异自证 durableMode 退化恒 0600→保持面双红。commit 1765a9c] | 外部复核（umask 077 主机对照） | xingchao P1-1 |
| L15 | go/internal/evidlog/evidlog_test.go:911-926 + go/internal/adopt/adopt_test.go:1701-1724 | ~~L9 探针缺 0640 保持面~~ [RETIRED 2026-11-03]（双探针各补 chmod 0640 再断言保持；变异自证：Stat 分支退化恒 0644 → 双包红「got 644, want 640」精确命中 → 恢复复绿——补强前该变异双绿，钉死成立） | 本地构造（需变异） | 增量内环 NIT-1 |

（singularity R21/R22 两轮判定一致：无可达奇点；R22 新增最强候选=F-A 输入契约结构化（LiteralDoc newtype，最便宜关闭 L8 窗口）+F-B 生产者包含性（writer ⊆ checker 闭包钉）；R21-F1 差分生成器维持首选杠杆。全记录见外环 R21/R22 报告 Part II。）六分叉——F1 差分生成器为下一杠杆推荐、F4 文法层严格性为待裁①同步收编、F6 单源代码生成按框架价值否决；无可达奇点，当前框架仍为正确收敛框架。全记录见外环 R21 报告 Part II。）

## 增量外环（2026-11-03 深夜，MR !2 修复批）

- **P1-1/P1-2/E3 三项清偿**（commit 1765a9c + 151a39f）：umask 0600 保守默认、断尾教义收敛（R9 F2 分叉退役，TestCrashRecoveryTornTail 反转为 remember+refuse）、control 事件类别（14-A4 拒收有痕）。全量回归绿（go -race 20 包+Python 八组+manifest）+ 三组变异自证闭环。
- **教训（L14 的元教训）**：minor 台账把「安全面发现」记为 minor 是误判——umask 面是安全语义（可见范围扩大），外部复核直接判 P1。下次遇到「权限/可见性/授权类」的 minor，先问是不是安全面，是则按 P1 处理。

## 审核循环记账（2026-11-03 深夜，R1-R3）

- L16（minor，不修）：`durableMode` 助手在 adopt/evidlog 两包各一份（~10 行）——镜像自足是两包既定家法（各自 loadLines/parsedLine 亦然），跨包提取会新增耦合；注释已互相指认。
- L17（minor，不修）：Inspect 断尾 gap 行文案在空文件/非空两分支重复一份字符串字面量——提取常量收益低于噪音。
- L18（minor，不修）：Dispatch 未知 op 的报文沿用了既有措辞「is not in the adopted state」（先于本批存在，语义略偏但可读）。
- L19（minor，不修）：Stat 错误分支的探针只到 ENOTDIR 单元级（进程内集成级不可移植构造——先验 12 号已声明）；分支代码经 durableMode 单元覆盖。
- L20（minor，登记）：evidlog 的写拒绝（断尾/STALE_SEQ）不落任何记录——其对象语义不同（记录 S2 行为而非机器闸门），不属 E3 同类；若未来需要「evidlog 写拒绝审计」，另立裁决。
- L21（minor，不修）：e2e S1 替身的规则集是部分面（上带窗口清洁面/带间 on_undefined 未入场景）——T0 场景扩展项。
- L22（minor，登记）：e2e S1 替身与 judgment-spec-credit 夹具同源于 08/10 出处但各自成文——P3 夹具修正落地时须同步去替身注释的「pending」标注。

## R6 空白终审记账（2026-11-04，2M 已修，minor L23-L26 积累不修）

- L23（minor，不修）：t1Spec 宣称「exactly the semantics the T0 stand-in embodies」在 C8 输入类失实——替身先查缺证（on_missing_evidence），t1Spec 优先级 0 压缺证（deny）；两 S1 实现的优先序分歧+等价宣称不实（与 L21 的「部分面」不同面）。
- L24（minor，不修）：replay fail-loud 网（replay.go:459 匹配「ledger append failed」）未覆盖 E3 refuse 写路径（报文为「(refusal not recorded: …)」）——mid-run I/O 故障可被当合法拒收以 divergence 收场；commit 路径有 TestScratchWriteFailureIsLoud 而 refuse 路径无对称探针。
- L25（minor，不修）：EVENT_BEFORE_ADOPTION 非 adoption 分支报文硬编码「effect event」——control 前置时报文错标（码位/行为正确，L18 同族）。
- L26（minor，不修）：T1 harness 每调用 180s×2 尝试×12 用例最坏 72min ≫ go test 默认 600s——launch 命令未带 -timeout（我们手动跑时带了 15m；命令文档补齐即可）。
- **singularity 登记（族复发≥2 触发，未启动）**：「事件类型词表增长×手镜像规则位点传播不完整」族在本增量两次复发（M-1 attribution 漏+M-2 transition 分叉）——E3 需同步传播每侧 ~8 个手镜像位点，实际漏 2。结构方向候选：①每侧「event_type×规则家族」分派表（漏传播不可表达）②规则位点 parity 网从 schema 原子扩展到规则枚举。按律结构转移自身引入缺陷（~30% 先例），若启动须转移后全强度外环+证伪器再生。
- L27（minor，不修）：TornTail() 文档宣称「every mutation is refused」在「外部修复后未 re-Open」窗口失实——写时字节复核放行 Adopt/MarkUnresolved（字节真相健康），仅 Dispatch 被入口 flag 拦；方向安全（字节级验证兜底恰是教义本体），文档把「字节级可验证的写」说成「全部拒绝」（adopt.go:175-183，R9 m-1）。
- L28（minor，不修）：torn 同因四种报文形态键族不齐——Dispatch 入口门纯散文无 [键]、append 写时复核 [ADOPT.TORN_TAIL]、refuse 包装、commit 包装「ledger append failed:」；按错误键过滤的宿主在形态①失配（行为全一致，R9 m-2；与 L24 同域不同面）。
- L29（minor，不修）：E3 的 replay 层（mode-2 重驱 drive+eventsEqual）零 control 事件夹具——机器/checker/e2e-Inspect 三层已钉，唯 replay 驱动面无红探针护体（R9 m-3；与 L24 可在未来结构战役合并考虑）。
- L30（minor，不修）：T1 launch 命令密钥指针硬编码 providerRules[4]——配置重排后指错 key，失败形态响亮（401→fail-loud 门），纯文档脆性（R9 m-4）。
- L31（minor，不修）：e2e 席位调用双形态——九个既有场景直调自由函数（s1Judge/s2Query/bankAPISubmit），零调用探针经 harness 计数方法（h.judge/h.query/h.submit）——最小侵入取舍，统一到方法形态留作 T0 场景族下次扩面时顺带。

## R14' 空白终审（32 号）minor 记账（L39-L47，9 条积累不修）

- L39：TestT2R_PermissionRevoked 名称/头注宣称撤销但测试体零撤销动作零拒绝断言——验收面向承诺兑现 0（Bearing），改名或补宿主授权判定面。
- L40：四读承诺兑现 3/4（READ 4 无断言且注释错置——READ 2 是 store 投影非知识消费）。
- L41：T2 头注宣称 node entry 组件不存在为命名工件（重提交逻辑内联在测试体）。
- L42：lookupByBusinessRequest 字典序比 revision（er-10<er-2 错序）+同 rev 并列 map 序不定。
- L43：findForNode 多 valid 同 node 时 map 迭代序不定；Replaces 字段无机制消费。
- L44：knowledgeMethod.execute 用 fmt.Sscanf 静默吞解析失败。
- L45：resultStore.put 非原子写（无 temp+rename）且损坏时整体拒载。
- L46：T2 店与账本双持久形态无一致性交叉核（adopt 成功后 store.put 前崩溃窗口）。
- L47：E0 extraction-miss 病态断言测试缺 polarity guard（家族 2/3——SickS1 与两个 E3 有开关，本测无）。
- **结构候选加权（第 3 次）**：写时覆盖族（R10 evidlog face-B → R11 STALE_WRITER → R14' phantom 对象行）——形状判定单表化（ParseLines typed view 与跨事件 checker 共用同一形状判定，evidlog entryShapeError 单表双消费为仓内范式）登记为候选战役，与「event_type×规则家族分派表」同向可并场。

## 34 号先行批清偿（P3+L23+L39-L44+L47——2026-11-05，9 条清偿）

- **P3**：judgment-spec-credit.json veto 去窗口化（6 处修正：coverage/term 定义/time_window 澄清/evidence_sources 补历史/反例补用例/_expect 改真）。E3-window 极性翻绿。
- **L23**：s1Judge C8 优先序对齐 t1Spec（veto 移到缺证检查之前）。E3-C8 极性翻绿。
- **L39**：PermissionRevoked 补真断言——T2 nodeEntry 加 callerGrants 参数+空 grants 拒绝+授权读取对照。
- **L40**：四读 READ-4 独立断言——纠错场景补修正方法验证（新任务检索到 correction 而非 stale result）。
- **L41**：nodeEntry 从测试体提为组件（t2host_test.go 的命名方法）。
- **L42**：lookupByBusinessRequest revision 比较从字典序改为数值域+sortedKeys 确定性迭代。
- **L43**：findForNode 迭代序确定化（sortedKeys 共用）。
- **L44**：Sscanf 失败从静默为 0 改为响亮追加 fact。
- **L47**：extraction-miss 补 correctnessLayerLanded 极性守卫。
- 残留：L45（原子写）/L46（店-账本一致性交叉核）——T2 夹具层声明不修，留 minor。

## R17 复审记账（2026-11-05，先行批增量 059d198..c919009——0B/3M 全清偿，反突变五连红）

- **M-A（L40 清偿幻影）**：清偿批的 READ-4「独立断言」实为幻影修复——注释宣称「发布修正方法→验证注册表服务新任务」，测试体从未触及 registry/findForNode/publish（grep 机械证实），断言与 READ-2 同面重复。族=「修复声明未机械落地」（V2 singularity「shares 双向」同形）。已修：READ-4 真知识检索断言（发布 v1 无效+v2 有效→findForNode 必须返回 v2→execute 复现 deny 语义）。反突变 A（findForNode 去 Valid 检查）→红。
- **M-B（L42/L43 清偿零耦合）**：数值序+确定性两守卫无任何测试可证伪——突变1（字典序族回退）全绿、突变2（排序死分支化，-count=10）全绿。同族补充：nodeEntry 的 not-completed/no-stored-result 两分支也无探针。已修：TestT2Lookup_RevisionOrdering（er-10>er-2 数值序+er-x 最低）、TestT2Lookup_TieBreakDeterminism（同 rev 平局最低 opID 稳定 50 迭代）、TestT2NodeEntry_Branches（两分支拒绝）。反突变 B1（int(rev[0]) 字典序族）/B2（去排序）/B3（去状态检查）→三连红。
- **M-C（L44 清偿偏离先验+fail-open）**：34 号先验明写「返回 error 而非静默为 0」，清偿实现为追加 fact 后 treating as 0——否决输入解析失败按无逾期处理=否决通道 fail-open（E0 extraction-miss 的方法形态）；且解析错误分支零测试触达。已修：execute 改 (storedResult, error)，否决输入不可解析即 fail-closed 报错；TestT2Method_ParseErrorFailsClosed（坏输入必须报错+好输入不受影响）。反突变 C（回退吞错）→红。
- **过程事故（自记）**：反突变验证中误用 `git checkout --` 回滚了持有未提交修复的文件（t2host_test.go M-C+探针全灭），从备份重建；教训=持有未提交修复的工作树禁用 git checkout 做突变恢复，改用 /tmp 副本。另：一次突变形态错误（追加语句落在 return 后成不可达死代码，Go 合法但无效）被 -v 调试抓出——突变探针本身也要验证「突变真的改变了行为」。
- **净计数**：本轮新增 0 minor（3 M 全清偿）；L45/L46 维持不修声明。测试面：t2host 0→4（四组件探针），t2host_rk 8。

## R18 空白复审记账（2026-11-05，R17 修复增量 c919009..5f47936——0B/3M/2m 全清偿）

- **M-1（L43 幻影复发）**：findForNode 仍是裸 map 迭代——L43 注释宣称治了 findForNode+lookup 两面，实际只治 lookup（sortedKeys 唯一消费点即 lookupByBusinessRequest）。空白子隔离实测：裸 range 下两键选择偏置 ~88/12——R17 记账的「反突变 A→红」实为概率事件非机械验证。已修：findForNode 改 sortedKeys 迭代（多 valid 同节点时最低 ID 赢，确定性契约入注释）；TestT2FindForNode_Deterministic（三键 200 迭代+F-04 过滤面）。反突变 M1→红（第 0 迭代即红）；A2（去 Valid 检查）在 READ-4 新过渡形态下确定性红。
  - 【R26 m-5 更正】上句「第 0 迭代即红」不实——三键夹具（插入序 c-a-b）首遇分布 75/12.5/12.5，第 0 迭代红是 87.5% 概率形态；探针级红界为 200 迭代累计 (1/8)^200≈1e-181。本行违反同段「区分确定性红与概率红」立法，R24 m-2 只改了探针注释未回改本记录。
- **M-2（缺键 fail-open）**：execute 新注释宣称「违反声明输入契约即报错」，但 overdue_months **键缺失**时静默为 0——恰是注释自己引用的 E0 extraction-miss 病主形态（上游没抽出字段=缺键，不是坏值）。已修：InputFields 驱动的必填键存在检查（缺键即 fail-closed 报错）；M-2 探针（无 overdue_months 键必须报错）。反突变 M2→红。
- **M-3（Sscanf 前缀解析放行腐坏输入）**：Sscanf 前缀解析使 "0abc"→0 / "2xyz"→2 / "0.5"→0 全部静默过 fail-closed 门——门的存在面≠声称面（防「腐坏输入解除否决」实际只防「首字符非数字」）。同族：revisionNumber 共用宽松解析。已修：execute 与 revisionNumber 全改 strconv.Atoi（全串严格解析，骑上游标准轮）；探针扩至五种腐坏形态（not-a-number/0abc/2xyz/0.5/空串）。反突变 M3→红（"0abc" 首个命中）。
- **m-1/m-2（新鲜码诚实修正，随批清偿不入积累账）**：READ-4 叙事收窄到注册表过滤面+改 K-expired 真过渡形态（v1 先 valid→发 v2→翻 v1 invalid——旧形态 v1 出生即 invalid 是手工摆拍）；分支探针改直接驱动 machine（Adopt/Dispatch/MarkCompleted 不经 store.put，真「完成未持久化」场景——旧形态先持久化再删内存 map，文件里结果仍存活）。
- **族复发警示（入方法论）**：L40 幻影族在 L43 上复发（修复声称的面＞实际治的面）；且反突变的「红」本身要区分确定性红与概率红（88/12 的红是掷骰子）——「修复声明必须机械验证」纪律的第三、第四实证。

## R19 空白复审记账（2026-11-05，R18 修复增量 5f47936..3661235——0B/5M/2m 全清偿，反突变六连红）

- **M-1（revisionNumber 同族修复零探针）**：R18 把 revisionNumber 改 Atoi 是「同族顺修」，但探针只耦合了 execute 半面——"er-2x" 前缀垃圾形态新旧两版行为相同，回退 Sscanf 全套测试恒绿（探针侧的「修复验证面＜实际修的面」镜像）。已修：TestT2Lookup_RevisionOrdering 加 "er-2x" vs "er-1" 子场景。反突变 M1→红。
- **M-2（排序修复解除既有探针武装）**：R18 的 sortedKeys 使 TestT2K_ExpiredKnowledgeNotConsumed 的 ID 命运反转——"method-current" 字典序低于 "method-expired"，去 Valid 检查突变下由 ~87% 概率红变恒绿（探针静默失效未记账）。已修：改名 method-a-old（失效者排更低）+删该夹具的 Replaces（纯 Valid 面——留着会被 supersession 机制掩蔽 Valid 突变）。反突变 M2→红（K-expired+确定性探针 kr2 子面双重红）。
- **M-3（supersession 声称面无机制）**：F-04 注释宣称「superseded 不被消费」但 Replaces 全仓零消费；修正窗口内最低 ID tiebreak 确定性服务 stale v1；宿主忘翻转时 stale 不仅是可达态且是确定性首选。已修：findForNode 机械化消费 Replaces（superseded 集合跳过——窗口内确定性服务 v2）+ TestT2FindForNode_SupersessionWindow 探针。反突变 M3→红。
- **M-4（欠声明方法重开缺键 fail-open）**：必填门信任锚=声明、解析门信任锚=硬编码键——InputFields 不含 overdue_months 的方法缺键时两门全空转=0（E0 缺键形态经声明缝重开）。已修：契约/消费分叉检查（execute 消费 overdue_months 则必须声明，分叉即 fail-closed）+探针。反突变 M4→红。
- **M-5（负值过门）**：Atoi("-4") 无错、-4>3 假→否决静默解除（域上不可能的计数仍放行）；注释「ALL corrupted forms」名实不符。已修：负值 fail-closed+badInputs 加 "-4"。反突变 M5→红。
- **m-1/m-2（随批清偿）**：必填门空值检查（空串 business_request_id 产孤儿结果）+ invalidate(id) 单一翻转写径（三写位收敛为一——整结构体覆写会丢未列字段）。
- **方法论入账（第 5/6 实证）**：修复可能解除既有探针的武装（M-2——探针与守卫的耦合是双向的，改守卫要复检所有既有探针的突变耦合）；声称的治理语义（superseded）若无机制消费则声称面即坏状态可达（M-3）。
- **中断封存与恢复**：R19 修复中途用户断网——65a077d WIP 封存（4M+2m 已修），恢复后完成 M-2 收尾+六连反突变+race 21 包绿+本记账。快照 35 号。

## R20 空白复审记账（2026-11-05，全量面 c919009..cfb4c44——1B/2M/4m 全清偿，反突变五连红）

- **B-1（E3 守卫使重写断言成死代码）**：c919009 同时翻了 p3FixtureCorrectionLanded=true（触发 R11/R12 时代的 skip 守卫）**和**把两 E3 测试体重写为新极性——守卫机械获胜，重写断言永不执行：P3 夹具修正与 L23 优先序修正**零活跃覆盖**（空白子 /tmp 全仓突变实证：夹具回退窗口化→21 包恒绿；s1Judge 回退先查缺证→全模块恒绿）。账本「E3 双极性翻绿」与 _expect「E3 experiment validated」均为机械空洞声明。已修：删两 skip 守卫+删 flag+注释更新为 RESOLVED 态；E3 真跑且绿；双回退突变均红（P3 回退→E3-window 红；L23 回退→E3-C8 红）。
- **M-1（取代者失效复活被取代者）**：superseded 集合仅由 **valid** 取代者构建——修正版 v2 自身过期（合法治理动作）后 findForNode 确定性服务已知 stale 的 v1（fail-open 残留缝，与本批 fail-closed 哲学相悖）。已修：Replaces 数据事实化（supersession 不随取代者失效而解除——节点无方法即 fail-closed 不服务，被取代者不复活）+ SupersessionWindow 第二面探针（invalidate 取代者后必须无方法）。反突变（回挂 Valid 条件）→红。
- **M-2（身份载体声明缝）**：M-4 分叉检查硬编码只护否决载体 overdue_months——欠声明 business_request_id 的方法静默产出孤儿结果（m-1 治的孤儿病经同缝在身份键原样重开）。已修：分叉检查泛化为「方法体消费的每个键都必须声明」（veto 载体+身份载体）+探针。反突变（回退单键）→红。
- **m-1（READ-4 装饰性断言）**：v1/v2 共享 execute 体，裸 veto-fired 断言对任何突变恒真。已修：收据断言嵌入 v2 身份（method:method-overdue-v2:veto-fired）。反突变（收据去身份嵌入）→红。
- **m-2/m-3/m-4（陈旧/错位注释）**：s1Judge 头注「pending P3」未随落地同步（L22 预注册义务）；L23 注释把 C12 归因为缺证+逾期（实为下带+历史逾期）；L39「matching grants」超卖（机制只查非空）。三处注释已改真。
- **方法论入账（第 7/8 实证）**：极性守卫翻转后必须拆除或改造守卫本身——「翻 flag+重写测试体」若守卫仍指向旧叙事，重写即死代码（B-1，极性守卫纪律的自我反噬形态）；分叉检查锚定单一载体时，同一检查的其他消费载体经同缝重开（M-2——安全检查的锚要覆盖全部消费面）。

## R21 空白复审记账（2026-11-05，全量面 c919009..25802e3——0B/3M/3m 全清偿，反突变四红+一 grep 证伪）

- **M-1（E3-C8 正文残留病态极性叙事）**：R20 B-1 只拆了 skip 守卫+两个测试 doc 头注，正文证明块（「T0 returns on_missing_evidence…order is wrong」现在时）、尾部注释掉的 logf 尸体（「contradiction CONFIRMED」）、文件头（「E3 proves the spec is self-contradutory」现在时）三处未同步——断言真承载（突变红）但叙述层与断言极性相反。已修：三处改历史语式（「the former diseased state…fixed by L23」）+删 logf 尸体。证伪＝grep 现在时态矛盾文本零命中。
- **M-2（分叉检查否决半面装饰化——marker 红非行为红）**：R19 同批静默去掉解析门的 ok-guard（缺键→无条件 Atoi("")报错）后，「欠声明+缺键」形态被 Atoi 门双重覆盖——M-4 探针的 fail-open 断言在该突变下恒不可达，红只来自 marker 不匹配。独占面（欠声明+**合法值在场**——Atoi 门放行合法数字）原无探针。已修：补独占面探针（mutation 下真 fail-open 实证——解除 marker 掩蔽后「produced a result」行为红）+注释如实标注双覆盖与独占面。
- **M-3（夹具读取失败走 Skipf）**：B-1 病形（断言静默不跑、套件恒绿）的环境路径残留——夹具被删/移时该测试 SKIP 且包 ok，P3 修正的活跃覆盖静默蒸发（该测试是夹具唯一代码读者）。已修：Skipf→Fatalf（仓内必需资源缺失=红灯；skip 合法触发面基本为空）。反突变（移走夹具）→FAIL 红。
- **m-1/m-2/m-3（随批清偿）**：READ-4 补前置窗口断言（invalidate 步骤在场景内可观测——去 supersession 突变下窗口断言红）；invalidate 未知 ID 从静默 no-op 改响亮报错（「声明的翻转没发生」与其他 fail-closed 门对齐——静默回退突变红）+「single write path」注释收窄（publish 同 ID=重声明非翻转）；TieBreak 探针 50→500 迭代+功效入注（(7/8)^500≈1e-29，对齐姊妹探针的功效记录纪律）。
- **方法论入账（第 9/10 实证）**：修复的同步义务覆盖**全部叙事层**（头注/正文证明块/尾部尸体/文件头）——拆守卫只拆一处会留三处旧极性（M-1）；探针的红要区分 marker 红与行为红——被另一道门兜底的形态其 fail-open 断言恒不可达，探针独占面须显式设计（M-2）。

## R22 空白复审记账（2026-11-05，全量面 c919009..ed56b9c——0B/2M/2m 全清偿，反突变三红+一 grep 证伪）

- **M-1（必填键门 marker 红——R21 立法未同步到姊妹门）**：R21 给分叉检查补了独占面探针+双覆盖诚实注，同一函数内的必填键门（R18 M-2）同病未治——「欠 overdue_months 键」形态被无条件 Atoi("") 双覆盖，fail-open 断言恒不可达；必填键循环的独占行为面（**brID 键缺失**+合法 overdue→孤儿结果）原无探针。已修：补独占面探针（删循环突变下真行为红——产出结果）+doc 按同文件样式如实标注双覆盖。
- **M-2（Replaces 引用完整性零校验）**：拼错 ID 的取代声明静默瓦解 supersession——stale 方法继续被确定性服务、全链零报错；与同批 invalidate 未知 ID 响亮的标准不对称（同一「声明的效果未发生」族）。已修：publish 校验 Replaces 引用已发布方法（typo 即 fail-closed 报错）+探针（typo 形态拒绝+被拒发布不突变注册表态）。
- **m-1（同 ID 重发布静默复活已失效方法）**：失效翻转存在第二条静默写径——republish 同 ID Valid:true 无声重武装已知 stale 知识（取代不可撤销 vs 失效可经重声明撤销的族内不对称）。已修：publish 拒绝一切重复 ID（redeclaration is not a flip——结构性预防：复活危害不可表达）+探针+mustPublish 测试助手（13 调用点统一转换）。
- **m-2（文件头第四处旧叙事）**：R21 M-1 清了三处，「If E3 shows the fixture and stand-ins are actually consistent…」将来时句漏网（grep 词形不在搜索面）。已修：改历史语式（E3 已跑完、矛盾已 resolve）。grep "If E3 shows" 零命中。
- **方法论入账（第 11/12 实证）**：给某道门补独占面纪律后，要横向扫同函数/同族的姊妹门——立法不同步等于只治了报案的那个（M-1）；「声明的效果未发生」族要族内全覆盖（invalidate 响亮了、publish 的 typo-Replaces 与重复 ID 还静默——M-2/m-1）；grep 证伪的搜索面要覆盖将来时/假设语气词形（m-2）。

## R23 空白复审记账（2026-11-05，全量面 c919009..081c41e——**0B/0M/3m，第一个 0B/0M 轮：连净计数 1/3**）

- **m-1（T1 侧事实零断言承载）**：E3-C8 叙事引用「t1Cases C8 expects deny, hardBar」但断言面只有 t1Spec 三子串——C8 条目被改时零 LLM 套件恒绿、解决声明的 T1 半静默蒸发。已修（随批清偿）：E3-C8 内遍历 t1Cases 断言 C8 条目 (expected=deny, hardBar=true)。反突变（改 C8 期望）→红。
- **m-2（「only code consumer」不真）**：cmd/judgment 的 must-accept 循环也读该夹具（schema 校验、不钉单文件）——语义独占性成立但字面断言为假。已修：改「only SEMANTIC consumer」+括注实际读者面。
- **m-3（reopen 注释与 R22 门矛盾）**：「survive via re-publication in the test」描述的存活机制既非实际机制（共享指针）也不再是被允许的操作（R22 重声明门）——立法后未横扫相邻叙事（R22 M-1 自己的立法语言）。已修：改「SHARED across reopen via pointer；真进程重启应向 FRESH 注册表重发布」。
- **轮次判定**：0B/0M——**连净第 1 轮**。minor 三条随批清偿（全部增量触及面：m-1/m-2 在 R21 改写物上、m-3 是 R22 门立法后的新矛盾），不入积累账。
- **空白子证伪未破的高危面**（择要）：全部已声称突变探针耦合逐条复算成立（含独占行为红与 marker 红之辨、双覆盖诚实注与代码事实一致）；registry 不可达坏态排查（复活/自引用/前向引用/取代环均结构性不可表达）；账本 R17-R22 与代码逐条相符。

## R24 空白复审记账（2026-11-05，全量面 c919009..1d19b3d——0B/1M/2m 全清偿；**连净计数归零**（R23 的 1/3 作废重来））

- **M-1（typo-Replaces 门只防「不存在」子形态）**：typo 最可能落在注册表内**既有兄弟 ID**上（本夹具 ID 空间正是 method-overdue-v1/v2 形态）——存在性检查放行：supersession 静默不发生+stale 被确定性服务+错误目标节点的覆盖被静默移除，全链零报错（R22 M-2 病态经姊妹形态可达；R22 自己立的「族内全覆盖」没盖住这个子形态）。已修：publish 加同节点校验（Replaces 目标须同 ServesNode）+双探针（跨节点拒绝+被拒发布不损失错误目标节点覆盖）。反突变（去同节点检查）→红。
- **m-1（t1Spec 两半面零断言承载）**：文件头「matching T1's t1Spec」的窗口措辞半面与规则序半面是叙事-only——三 marker 子串对这两类回归不敏感（回窗口化/missing-evidence 改标 precedence 0 都恒绿）。已修：E3-window 加 t1Spec 无界措辞断言（AT ANY TIME+limited to any recent window）；E3-C8 加连贯断言（"- Precedence 0 (override): ANY overdue"）+计数断言（"Precedence 0" 恰 1 次=否决条款独占）。双反突变红。
- **m-2（功效注方向标反）**：两个确定性探针把 7/8 favorite 方向写反——期望赢家实为 1/8 underdog，真实静默逃逸 (1/8)^500≈1e-451 / (1/8)^200≈1e-181（注称 1e-29/1e-10——仍是保守上界、无覆盖损失，但机理与实测不符；三键分布 75/12.5/12.5 而非移植的 88/12）。已修：两注按实测方向改写+注明测量法（200k 裸 range 计数）。
- **边界外备注（预存面，不入计数）**：failingProbe.invoke 全仓零调用点（zero-invocation 探针面实为「无调用路径」，c919009 前结构）；knowledgeMethod.Version 零消费者（write-only 字段）——两条登记为后续观察项。
- **方法论入账（第 13/14 实证）**：存在性检查≠威胁面检查——typo 的落点分布由 ID 空间形态决定，门要按「最可能落点」设计（M-1）；统计功效注的算式方向必须与实测相符，保守上界不是机理写错的豁免（m-2）。

## R25 空白复审记账（2026-11-05，全量面 c919009..1bb4d36——0B/1M/3m 全清偿；连净维持 0）

- **M-1（歧义取代第四面缺口）**：publish 三关（重复 ID/存在性/同节点）全过后，Replaces 指向**已被取代的目标**（v3 本意取代 v2、typo 落在已死的 v1）仍静默通过——superseded={v1}、findForNode 永远服务 v2、最新修正 v3 永不被服务、全链零报错；最低-ID 确定性契约把歧义态伪装成有序态（schema 自己声明 equal-precedence 冲突须显式命名，注册表却静默接受同目标双取代）。已修：第四门「目标不得已出现在其他存活方法的 Replaces 中」+双探针（歧义拒绝+正确链式 v3{Replaces:v2} 后 v3 被服务）。反突变（去该门）→红。
- **m-1（括号残留反向算术）**：TieBreak 功效注主式已改真方向，括号「(50 迭代界 ≈1.3e-3)」恰是旧 (7/8)^50 反向算术残留。已修：改 (1/8)^50≈7e-46。grep 1.3e-3 零命中。
- **m-2（marker 极性盲）**：t1Spec 断言「limited to any recent window」对否定/肯定同形匹配——删「NOT」即语义重窗口化而断言恒绿（R24 m-1 只关了删除形、没关极性翻转形）。已修：极性钉死（whitespace 折叠后断言 "NOT limited to any recent window" 逐字在场）。反突变（删 NOT）→红。
- **m-3（计数守卫单面挂载）**：precedence-0 唯一性计数只在 t1Spec 半面——夹具半面把第二条规则改标 0（veto 仍数组首位）全部断言照绿（R24 m-1 的立法理由逐字适用于夹具面但未横扫）。已修：夹具半面加 countPrecedenceZero==1 断言+helper。反突变（夹具第二条改标 0）→红。
- **方法论入账（第 15/16 实证）**：族枚举要按「可达输入空间」穷尽——publish 门族四关（重复/存在/同节点/歧义取代）是同一威胁（typo 取代声明）的四个落点形态，逐轮才各关一个；marker 断言要极性敏感（否定句的子串断言对极性翻转盲）；同一守卫立法后要横扫**全部消费半面**（t1Spec/夹具/替身三方各一面）。

## R26 空白复审记账（2026-11-05，全量面 c919009..978112a——**0B/0M/6m，连净 1/3（第二轮连净开启）**）

- **m-1/m-2（叙事层残留微形态）**：TieBreak 功效注双注解头（R24 m-2 追加未删旧句——孤立半句尸体）；分叉检查注释硬编码「line ~270」出生即指向错误语句（R19 时代位置，R20 泛化后未随移）。已修：删尸体/改语义锚（「return 语句的 BusinessReqID 字段」）。
- **m-3（极性钉死未横扫夹具半面）**：删夹具 coverage 的「NOT」后 E3-window 断言面恒绿（t1Spec 半面 R25 m-2 已钉、夹具半面未随扫——R25 m-3 自己立的「三方各一面」横扫义务对 m-2 未执行）。已修：夹具 coverage 极性钉死断言（whitespace 折叠后逐字含 "NOT limited to the six-month window"）。反突变（夹具删 NOT）→红。
- **m-4（恒真合取项死代码）**：歧义取代门的 `existing.ID != m.ID` 结构性恒真（重复 ID 门已保证 m.ID 不在册）——「无害不是留存理由」。已修：删合取项+注释说明为何无需自排除。
- **m-5（账本记录层含混）**：R18 M-1 条目把 87.5% 概率红记为「第 0 迭代即红」——违反同段自己的「区分确定性红与概率红」立法。已修：追加更正行（第 0 迭代红为 87.5% 概率形态；探针级红界 (1/8)^200≈1e-181）。
- **m-6（C12 姊妹落点零断言承载）**：s1Judge L23 注释引用 C8+C12 双案例，断言化只钉了 C8（R23 m-1 义务的姊妹落点未横扫）。已修：E3-C8 的 t1Cases 遍历同钉 C12-veto-beats-lower-band (deny, hardBar)。反突变（C12 期望改值）→红。
- **轮次判定**：0B/0M——连净 1/3（R24/R25 各 1M 归零后重启）。六 minor 随批清偿（全部增量触及面），不入积累账。
- **方法论入账（第 17 实证）**：横扫义务是逐守卫逐半面的——R25 m-3 立法后本轮又抓到两个未横扫落点（m-3 夹具半面/m-6 C12 姊妹落点）+账本记录层自身也要服从自己立的纪律（m-5）。

## R27 空白复审记账（2026-11-05，全量面 c919009..7ee183c——**0B/0M/3m，连净 2/3**）

- **m-1（C12 的 T0 行为半面零探针）**：s1Judge 全部 11 个驱动点均 35M 形状
  - 【R28 m-1 更正】「11 个驱动点」为裸 grep 伪影（"s1Judge(" 字符串出现次数，含定义与包装体调用）——真实计数 14 驱动点＝直接 9（e2e 7+probe 2）＋经 h.judge 间接 5；定性结论（全部 35M 形状）逐点核实为真。——「下带+历史逾期」（C12 形状）无任何行为承载；把下带分支前移到否决循环之前全模块恒绿而 C12 硬 bar 期望 deny（三方各一面横扫漏了 T0 行为半面——t1Spec 措辞/t1Cases 表/T0 行为三半面只钉了前两个）。已修：E3-C8 加 C12 形状驱动探针（assets 0+reportOK+5 个月逾期→deny）。反突变（下带前移）→红（注：第一版突变形态错误——只移到缺证检查前、否决仍最前，探针不触发；正确形态须移到否决循环之前）。
- **m-2（组件注释统计与探针实测不符）**：findForNode 注释「~88/12 per probe」是两键 lookup 侧的数字，本组件三键探针实测 75/12.5/12.5——R24 m-2 只改了两个探针注释、组件 doc 注释未随扫。已修：改双分布如实标注。
- **m-3（冗余合取项）**：E3-C8 三子串合取中 "Precedence 0"/"ANY overdue" 两项的判别力被同测试后置更强断言（连贯串+计数）完全蕴含——R26 m-4 死合取项族的弱一档形态（更强守卫落地后旧弱式断言未随删）。已修：收窄为单项 "regardless of assets"。反突变（t1Spec 删该子串）→红。
- **轮次判定**：0B/0M——连净 2/3。R28 为收官轮（3/3）。
- **方法论入账（第 18 实证）**：横扫的「半面」枚举要含**行为半面**（措辞/表/行为三面）；更强守卫落地后要回删被蕴含的旧弱式断言（冗余不是无害）。

## R28 收官轮记账（2026-11-05，全量面 c919009..5f71a0f——**0B/0M/2m，连净 3/3：循环收官**）

- **m-1（账本计数伪影）**：「11 个驱动点」是裸 grep 伪影（"s1Judge(" 字符串次数，含函数定义与包装体调用）；真实 14 驱动点＝直接 9＋经 h.judge 间接 5。已修：R27 m-1 条目下追加更正行（同 R26 m-5 形态）。定性结论（全部 35M 形状）为真。
- **m-2（分支序完备性声明不成立）**：「pins the last branch-order face」实际只钉 3/4 半面——**中带（between-bands）分支**对否决的从属序零承载（全套件 assetMillions 只有 35 与 0，无 1<x<30 驱动点）；中带检查前移突变全套件恒绿，而 12M+4 个月历史逾期的规范答案是 deny（规则 0「regardless of assets」）——静默降级为 on_undefined_rule。已修：E3-C8 加第三形状探针（12M+reportOK+历史逾期→deny），四个分支序半面全钉（注释同步枚举四面四形状）。反突变（中带前移）→红。
- **收官判定（按用户裁定口径「3 连 0blocker 0major」）**：R26（0B/0M/6m）→R27（0B/0M/3m）→R28（0B/0M/2m）——**三轮连 0B/0M，循环收敛收官**。两 minor 随收官清扫清偿（m-2 探针反突变红）；正式 verdict 立于被审提交 5f71a0f，收官清扫提交不引入新守卫外代码。
- **循环总账（R17-R28 十二轮）**：1 BLOCKER + 17 MAJOR + 26 minor 全部清偿（B/M 当轮修复+反突变红探针；minor 随批清偿或账本更正，无积累残留）；账本方法论实证 18 条入账；测试面从 25 函数扩至 33（t2host 0→7，correctness E3 双测试复活为活断言）；每轮 race 21 包绿。

## R29 空白复审记账（2026-11-06，六实验增量 339b38b..8f77bb7——1B/6M/8m 全清偿）

- **B-1（E4 死亡探针把授权流量当死亡证据）**：lastTraffic 只数 effect（成功 dispatch），最后一次拦截后任何授权派发即报死——健康流误报面未钉，两个绿灯用例 effect 数均为 0（靠缺席将证伪它的流量而绿），37 号「健康流不误报」声称超事件流表达力。已修：死亡语义收窄（「控制面静默+effect 持续」=review 信号非裁决；混合流与死亡不可区分=机器盲的事件流表达力边界）+混合流钉子用例（文档化该边界）+phase-1 注释诚实化（op-e4-live 有意不派发）。反突变：混合流钉子在语义变化时红。
- **M-1（sentinel 文档与实际值不符）**：dispatchedSeq 注释声明 -1，实际 pre-dispatch 是 Go 零值 0——observed=0 的裁决与文档推理相反。已修：Adopt/replay 双侧真初始化 -1+sentinel 契约探针（observed=0 必拒、-1 放行）。
- **M-2（窗口 1 全覆盖声明宽于机制面）**：版本门可达保护面=伪造/跨线观察——canonical CAS 竞态（干预在另一操作、调用者持 -1）不可检（adopted 无回边、版本不可能 stale）；测试注释诚实但生产 doc/37 号保留全量声称。已修：doc 收窄+37 号同步。
- **M-3（verify 阈值硬编码与夹具漂移不可检）**：spec 参数只做 nil 检查，3 个月/带界全字面量——夹具阈值改 4 个月全 E3 照绿而 verify 仍在 3（三方一致第三腿静默断裂）。已修：anchorVetoMonths 从夹具文本派生（three/four 词映射）+锚测试。反突变（夹具改 four）→红。
- **M-4（镜像面/中带面零测试覆盖=死守卫）**：两面定义后无任何断言，删码全绿（装饰守卫）；中带谓词 `>1 && <30` 漏夹具开放集的两端（恰 1/恰 30）。已修：inBand 改闭区间+TestE1_MirrorAndBandFaces 双面红探针+on_undefined_rule 阳性对照。反突变（删镜像面）→红。
- **M-5（MarkUnresolved 写假对账事实）**：席位拒绝发生在派发前——从 adopted 调 MarkUnresolved 对从未存在的派发断言「结果未知」（对账者可合法找外部效果）；病臂注释「nothing was adopted」与同段 Adopt 调用直接矛盾。已修：三臂（sick/extract/E2）全改——记录被采纳（机器盲设计如实声明）、宿主扣派发、operation 停 adopted（无假 unresolved 事实）；「零外部调用」改 measured（h.calls.bankAPI==0）；37 号 E1/E2 行更正。
- **M-6（named guard 名不副实+掩盖形态）**：全 control 事件共享唯一 status "rejected"——按 status 无法点名单个守卫，其他守卫持续拦截掩盖特定守卫死亡。已修：参数改名 controlStatus+表达力边界声明（点名守卫需 refuse detail 前缀解析——夹具层故意不做）。
- **m-1~m-8（随批清偿）**：m-1 Dispatch/DispatchIfCurrent 30+ 行重复收敛 dispatchGated helper（46 调用点零改动承诺保持）；m-2 「Wait —」草稿叙事改 Reachability note；m-3 不可达 else 删+零调用改 measured；m-4 requiredSources 死 value 删+sourceSources 死字段删+夹具联动声称如实化；m-5 grantsCoverRead 语义差声明（无 effect 级/空 pinned 反转/常量 pin vs per-result——0.2.0 面）；m-6 age 面精确边界钉（30 静默/31 列）；m-7 gofmt -l 修复+纪律账声明更正（收官提交时 adopt.go 实有命中）；m-8 命名统一 TestE<N>_YYY。
- **方法论入账（第 19/20 实证）**：健康断言不得靠缺席将证伪它的流量而绿（B-1——绿灯用例的 effect 数为 0 恰是盲区所在）；新组件的参数若「存在即被忽略」（M-3 spec 只做 nil 检查）=参数承载失败，锚定测试是廉价闭环。

## R30 空白复审记账（2026-11-06，339b38b..7e4d4b7 六实验+R29 清偿——0B/4M/7m 全清偿；连净计数 0）

- **M-1（E2 拦截无行为承载）**：测试全程不调 S1、无按 gap 条件化派发——「拦截」无可执行承载面，反突变声明不可达（缺席断言绿=方法论第 19 条形态）。已修：真条件流（gap 空→judge/adopt/dispatch/submit；非空→扣派发），双断言面。反突变分形【R36 m-5 归因更正】：coverageGap 恒空→值断言红（gap 检查先行，行为段不可达）；宿主流删 gate 条件→门自由分支跑通→行为断言红（bankAPI/事件）——两个突变的红源分开写明。
- **M-2（锚 fail-open）**：anchorVetoMonths 只识别 three/four，词表外措辞（six months）落默认 3——漂移探测器变漂移掩护者。已修：fail-closed（词表 three/four/five/six 映射；无解析→0 哨兵→verify 拒绝把关=对流程 fail-closed）+锚测试双断言（可解析+值）。反突变（夹具改 six）→双测试红。
- **M-3（词表门缺失）**：三语义面全靠精确字符串——GRANT-50000 大小写变体/词表外 kind/无 veto 字样的伪造 deny 全部实测绕过。已修：词表门先行（夹具 levels+resolution 词；EqualFold），镜像面收窄为「!vetoFires 时一切 deny 皆伪造」（rule 0 是夹具唯一 deny 路径，不再关键词嗅探）。直检探针：变体必拒。
- **M-4（账本系统性假 detail）**：DispatchIfCurrent 成功事件 100% 写「after the version check」而版本比较在可达态必然被跳过（observed 恒 -1）——审计统计「过版本门的派发」全数为假。已修：detail 按 form 分裂（conditional 命名实跑的检查/fresh-observation 诚实声明跳过）+TestE6 detail 分形钉（回退合一→红）。
- **m-1~m-7（随批清偿）**：文件头叙事翻转（POLARITY GUARD 指令退役）；恒真条件包裹去壳；MEASURED 措辞如实（计数器按构造为零）；trafficVolume 文档如实（adoption 不计/unresolved 计入已声明）；闭区间两端的夹具出处分指（exception vs example）；版本门拒绝消息讲架构已排除的因果故事+裸 sentinel（改「never this operation's version」+解释 -1）；双 E1 头块合并。
- **正面确认（空白子实测）**：收敛重构等价性成立（dispatchGated 与旧 Dispatch 逐字一致）；探针耦合全保留（版本门/状态门/sentinel 三探针在突变 C 下全红）；46 调用点零改动相符；37 号数字面全对。
- **方法论入账（第 21/22 实证）**：拦截声称要有条件流承载（无分支的流=缺席断言，M-1）；fail-open 默认值把守卫变掩护（M-2——哨兵语义要 fail-closed）；词表门先行于语义门（M-3——精确字符串匹配对变体全开）。

## R31 空白复审记账（2026-11-06，339b38b..c6719fa 六实验+R29/R30 清偿——0B/2M/7m 全清偿；连净计数 0）

- **M-1（词表门 EqualFold 放行变体——R30 M-3 清偿自身的反噬）**：词表门 EqualFold 把变体放进词表，三语义面全 case-exact——"DENY" 伪造放行/"GRANT-50000" 开放带放行，且极性反转（同变体真 veto 时被拒、伪造时放行）；R30 M-3 账行的「直检探针：变体必拒」无探针、声明假。已修：词表门归一化（命中即取夹具 canonical 名，三面全比 canonical）+TestE1_CaseVariantsRefused 真直检探针（变体伪造拒/开放带拒/真 veto 时变体 deny 接受=归一化对称）。反突变（去归一化赋值）→红。方法论：**EqualFold 进门+精确比较把关=变体被门豁免**——归一化要在进门时完成，不是进门时认可。
- **M-2（detail 分形双死臂）**：R30 M-4 的 `observed>=0` 成功臂与 `commitDetail==""` 回退臂均不可达（adopted 无回边→门处 dispatchedSeq 恒 -1→条件提交 observed>=0 必拒）——conditional detail 字符串永不入账，M-4 动机（审计统计）是空集。已修：死臂删除+调用方静态诚实措辞+负向探针（全流断言无 "after the version check" 成功 detail——死臂复活即红）。
- **m-1~m-7（随批清偿）**：trafficVolume 死代码删除（guardDied 自算流量——36 号旧接线叙述退役）；E1 双臂/文件头突变叙事改真（直检断言为耦合面，条件流面=TestE2——R30 方法论 21 回灌）；E-GR 头注释如实（合成演示非真解析台账）；anchorVetoMonths 定序切片（map 迭代序随机=3/6 掷骰）+拒绝消息模板化（hardcode "three months" 与锚脱钩）；resolution 词表硬编码声明（与 levels 臂锚定不对称 declared）；TestE6 doc 名同步；E-GR `>=` 残留声明两处收窄对齐。
- **方法论入账（第 23 实证）**：清偿自己的声明也要被审——R30 M-3 的「直检探针」是记账假（写了红探针三个字没有探针），空白子下一轮抓出；EqualFold 归一化的正确位置在进门处。

## R32 空白复审记账（2026-11-06，339b38b..6ce74be 六实验+R29/R30/R31 清偿——0B/3M/6m 全清偿；连净计数 0）

- **M-1（fail-closed 自身零探针）**：R30 M-2 的哨兵分支与 verify 拒面是装饰守卫（删码/回退 return 3 全套件绿——本仓 R29 M-4 自立标准），锚测试只钉值面。已修：TestE1_FailClosedAnchored（不可解析 spec→anchor 0+verify 拒+nil spec 拒）。反突变（回退 return 3）→红。
- **M-2（assetReportPresent 死字段双向不设防）**：全仓只写不读——夹具第一条 evidence source 缺失时 grant 放行/报告在场时谎报缺证放行（E0 evasive-S1 家族双向）；未按 requiredSources 款式声明已知面。已修：消费字段（双向面：无报告出 grant 拒/有报告谎报缺证拒）+TestE1_EvidencePresenceMirror 双探针+诚实 gap 阳性对照。反突变（删双面）→红。
- **M-3（带界硬编码未锚定）**：veto 阈值锚定了（R29 M-3）带界没锚——夹具 30→50 全套件照绿（31..50 规范内 grant 被静默 under-block（陈旧面对漂移后夹具放行过宽））；注释 "comes from" 制造已锚定假象。已修：anchorBandBounds 从夹具规则文本派生（fail-closed 哨兵 0,0）+TestE1_BandBoundsAnchored 锚测试（含 31 处行为面——【R33 m-1 更正】旧硬编码下 31 同样通过（>=1 && <=30 不含 31）；该面的真实承载是抓 verify 侧常量与锚分叉，非历史行为差异）。反突变（夹具 30→50/1→2）→bounds (0,0) 红。【R43 m-5 更正】(0,0) 为 R32 Contains 形态的突变结果；R33 后 regex 形态同突变得 (2,50) 型可解析值，红源=TestE1_BandBoundsAnchored 的 (1,30) 值钉而非哨兵。
- **m-1~m-6（随批清偿）**：dispatchGated 提交后 CAS 叙事注释如实（pin 无可达读者——replay 对称+未来文法预留）；镜像面重复句删；E-GR 演示头 17→19 对齐；graveyardSweep 同龄并列 id 决胜（确定性纪律落到切点）+TestEGr_TieAtExcessBoundaryIsDeterministic 50 迭代探针；raw 隔离措辞收窄（"dead in THIS wiring"——类型边界非强制，纪律面非机制面）；healthy 臂 E0 旧注释改真（测试故意派发=证明机器盲，非宿主政策）。
- **方法论入账（第 24/25 实证）**：fail-closed 是守卫不是措辞——它的两面（哨兵值+拒面）同样需要红探针，否则就是装饰（M-1）；结构体字段「每个构造点都写、无人读」=未落地面（M-2——字段存在暗示的语义要消费或声明）；锚定纪律要横扫同组件的**全部数值字面量**（M-3——修了 veto 漏了带界）。

## R33 空白复审记账（2026-11-06，339b38b..44e69c8 六实验+R29-R32 清偿——0B/1M/9m 全清偿；连净计数 0）

- **M-1（带界锚数字扩展漂移盲区）**：Contains("above 30") 是 "above 300" 的前缀子串——数字扩展（30→300/1→10）锚照绿、seat 静默 under-block（150 被放行）；R32 M-3 声明的「移动 bound 即红」对扩展族为假。已修：anchorBandBounds 改 regex 解析数字（`above (\d+(?:\.\d+)?)`/below 同型——值不可与文本分叉）+哨兵深度对齐 veto 臂（0,0→verify 拒关，R33 m-3）。反突变（300/10 双向）→bounds (1,300)/(10,30) 红。
- **m-1~m-9（随批清偿）**：带界锚行为面的历史声明改真（前身形态全通过 31——真实承载是抓 verify 侧常量与锚分叉；账本方向词 over/under 更正）；on_missing_evidence 镜像面消息依据如实（resolution 主语限定+coverageGap 前置）；双锚 fail-closed 深度对齐+「never fires」假句修正；带面消息 "strictly between"→"closed between-bands zone"（与闭区间一致）；E4 phase-2 注释 adoption 不计（与 guardDied 实际计数一致）；nodeEntry doc 错挂归位；E3 双测试改调 loadE3Fixture（三处解析点收敛）；E-GR 并列探针改输入排列扫描（50 迭代恒真——确定性买的是输入序无关非 run 重复）；37 号「实跑」改「合成形状演示」。
- **方法论入账（第 26/27 实证）**：锚定用 Contains 匹配+字面量复制=值可与文本分叉——数字要从匹配文本**解析**（前缀子串是扩展漂移的天然盲区，M-1）；探针声称的确定性质要指认真实来源（并列决胜买的是输入序无关——50 迭代重复循环是恒真断言，m-8）。

## R34 空白复审记账（2026-11-06，339b38b..4210084 六实验+R29-R33 清偿——0B/1M/3m 全清偿；连净计数 0）
  - 【R35 m-4 更正】原头计数「4m」与 body 三条不符（m-3 内含两事按一编号计）——按机械规则 header 计数=body 条目数改为 3m。

- **M-1（veto 锚复合数词盲区）**："thirty-three months" Contains "three months"→解析 3（值保持型误解析）——R33 M-1 的 regex 纪律横扫了带界臂的数字形态、没横扫 veto 臂的词形（R32 M-3 方法论的横扫缺口）。已修：边界感知匹配（裸词前紧跟字母/连字符=复合形态→落 0 哨兵 fail-closed）+TestE1_VetoAnchorCompoundWords 直检探针（复合→0+verify 拒关+真夹具仍 3）。反突变（去边界检查）→红。
- **m-1（分组数字前缀捕获）**："30,000" 的数字 regex 静默捕获 30——探针先红实锤。已修：分组形态（[,.]\d 后继）毒化→sentinel (0,0)+Sscanf 错误显式面。探针入 TestE1_VetoAnchorCompoundWords。
- **m-2（多命中静默消解）**：双规则不同 "above" 值按数组序 last-wins——与 countPrecedenceZero「歧义=冲突」纪律分叉。已修：同面异值→sentinel 冲突化+同值 agreeing 阳性对照。反突变（回退 last-wins）→红。
- **m-3（doc 名/retract 残留）**：TestE0DiseaseExists_HealthyS1 doc 名未随 R31 m-8 同步；healthy 臂失败消息保留 R32 m-6 刚 retract 的「host decides not to dispatch」从句。已修：双处同步；retract 短语全仓唯一命中=更正注释自己（合规引用）。
- **方法论入账（第 28/29 实证）**：横扫纪律的宾语要按**形态族**枚举（regex 数字形态/词形是两族——修一族漏一族，M-1）；解析器的边界形态（分组符/复合词）与解析成功同权入探针（m-1/m-2——失败形态静默落陈旧值是最隐蔽的 fail-open）。

## R35 空白复审记账（2026-11-06，339b38b..4dc831f 六实验+R29-R34 清偿——0B/2M/5m 全清偿；连净计数 0）

- **M-1（空格分隔复合族漏——R34 M-1 清偿自身的新缝）**："twenty three months"/"sixty six months" 的 prev=' ' 通过字母/连字符检查→值保持型误解析（3/6）；R34 的全称声明「Compound forms land on the 0 sentinel」对空格子族为假。已修：前一词 token 亦为数词→复合落 0（25 个数词 token 扫描）+TestE1_VetoAnchorCompoundWords 双空格案例。反突变（去空格 token 检查）→红。
- **M-2（级档-带位一致面+窗口前提面未实现）**：header 声明「contradicts the raw evidence under the fixture's rules」而实现只覆盖 rule 0/开放带/在场三面——grant-10000@35（错误级档）与 grant-50000+窗口内逾期（rule-1 前提违反）实测过闸；锚定机制锚得住数值锚不住未实现的规则子句。已修：级档-带位一致性面（grant-10000⇔<lo；grant-50000⇔>hi）+窗口前提面（grant-50000+任何在录逾期→拒）+TestE1_LevelBandConsistency 双探针+阳性对照。反突变（删级档面）→红。
- **m-1（veto 臂多命中静默词序消解）**：双规则异值按词序取（three 先于 six）——band 臂 R34 m-2 冲突化纪律未横扫孪生臂。已修：COLLECT-then-DECIDE 重构（先收集全部命中再裁决——inline-return 形态让词序压过文本序）+TestE1_VetoAnchorMultiHitConflicts 双臂探针。反突变（去冲突检查）→红。
- **m-2（band 锚倒置区间）**：lo>hi（可解析但文本自相矛盾）→inBand 恒 false→带面静默失活（第三种 fail-open：既非不可解析也非多命中）。已修：倒置检查→sentinel+TestE1_BandBoundsInvertedRefused（探针+verify 拒关双断言）。反突变（去倒置检查）→红。
- **m-3~m-5（随批清偿）**：phantom 族名实极性修正（TestE0DiseaseExists_*→TestE0_*_Caught+「Current state」叙事改为 R14' 修复后实态）；R34 账本头计数 4m→3m 更正（header 计数=body 条目数机械规则）；comma 死变量删。
- **方法论入账（第 30/31 实证）**：header 的契约声明要逐条对照实现的语义面清单——「refuses under the fixture's rules」的 rules 是全集还是子集要写明（M-2——锚定住了数值锚不住未实现子句）；inline-return 的多源收集要在裁决前完成（m-1——词序压过文本序是 return-early 的结构性后果）。

## R36 空白复审记账（2026-11-06，339b38b..ddcc06c 六实验+R29-R35 清偿——0B/2M/5m 全清偿；连净计数 0）

- **M-1（带面被级档面吞成死守卫——R35 M-2 清偿自身的反噬）**：inBand ⟹ 级档面条件（对任一 grant kind），带面可拒集合 ⊆ 级档面可拒集合——带面删码全绿、「删除即红」探针声明不可达（R29 M-4 病形由清偿引入）。已修：带面删除+TestE1_MirrorAndBandFaces 探针改挂级档面独占 reason 字符串。反突变（删级档面）→双测试红。
- **M-2（窗口前提无视窗口信号+重定义术语）**：months>0 record-global 检查——yearsAgo（唯一窗口信号）未读；months∈[1,3] 按夹具术语根本不是 overdue（同一字段两套定义）；过阻断言类无阳性对照。已修：窗口感知（yearsAgo==0）+术语一致（months>vetoMonths 与 rule 0 同一定义）+过阻阳性对照（months=1/yearsAgo=5 规范合流过闸）。反突变（回退 record-global）→过阻对照红（假 reason 亲证）。
- **m-1（死分支）**：collect 相 per-key 冲突检查恒假（n→word 双射）——真歧义检查是 len(seen)>1。已修：死分支删+注释如实。
- **m-2（量级词族漏）**：token 表无量级词——"hundred three months"→3（值保持型误解析，两轮形态族枚举均漏）。已修：token 表补 hundred/thousand/million。
- **m-3（复合+裸词混排静默解析）**：复合命中的真值不可表示→被记为一致票——decide 相发现复合命中即置毒→0。
- **m-4（on_undefined_rule 无带位镜像）**：恒答 on_undefined_rule 的病 S1 在全部非 veto 输入过席（欠执行形态）。已修：规则覆盖点上拒（assets>hi）+开放带阳性对照。反突变→红。
- **m-5（账本归因错位）**：R30 M-1 行「coverageGap 恒空→行为红」不可达（值断言先行）——红源分形更正。
- **方法论入账（第 32/33 实证）**：新增面与旧面的谓词域重叠要显式审计（M-1——后加面使前面失去唯一承载，探针声明随之失效）；面的 reason 文本不得断言 seat 输入无法建立的事实（M-2——窗口信号在读吗、术语定义与既有面一致吗）。

## R37 空白复审记账（2026-11-06，339b38b..8c95061 六实验+R29-R36 清偿——0B/2M/3m 全清偿；连净计数 0）

- **M-1（窗口面零可达拒绝质量——R36 M-2 清偿自身的二次反噬）**：窗口面谓词域 ⊆ veto 面谓词域（term-level overdue 在窗口内已触发 rule 0 拒绝）——1408 输入暴力扫描 reason 命中 0 次；探针②只断言 !cr.ok 不锚 reason，失败消息断言了不存在的因果（R36 M-1 死守卫病形在同批下一个面复发）。已修：窗口面退役（rule 0 完全吞没窗口前提——执行存在、载体是 veto 面）+探针锚 "rule 0" carrier（新载体须重新声明）。
- **M-2（复合词混合形态 fail-open）**：clean-first 单规则/双规则数组序下，clean 命中提前 return 豁免了同文本/同集内后续复合出现；R36 m-3 的毒化只覆盖 compound-first 排序。已修：decide 相两相化——毒扫描全规则全出现先行（任一复合→0），无复合才落 collect 值。反突变（回退首现扫描）→红。TestE1_VetoAnchorMixedOrder 双臂探针。
- **m-1（镜像下半域缺）**：on_undefined_rule 镜像只覆盖 >hi——rule-2 覆盖点（<1）的欠执行放行。已修：<lo 半域补齐+探针第三臂。反突变→红。
- **m-2（decide 相死落入路径）**：poisoned 置毒后守卫恒真、return w.n 无条件、注释描述不可达路径（R36 m-1 兄弟形态未同批横扫）。已修：M-2 重构自然收敛（两相化消除该形态）。
- **m-3（词表双份重复）**：collect/decide 各内联同一张表——单侧加词两相语义分叉。已修：vetoWords/compoundTokens 包级单一定义（结构性预防：单侧漂移不可表达）。
- **方法论入账（第 34/35 实证）**：面的谓词域与既有面的包含关系要显式计算（M-1——R36 方法论 33 的自指复发：包含审计要跑在「加面」之前）；全出现扫描优先于首现扫描（M-2——复合形态的真值不可表示时，任何位置的出现都是毒）。

## R38 空白复审记账（2026-11-06，339b38b..143c0bf 六实验+R29-R37 清偿——1B/3M/2m 全清偿；连净计数 0）

- **B-1（R37 m-1「镜像下半域已修」未落地+反突变假证据）**：账本与提交消息声明「<lo 半域补齐+探针第三臂。反突变→红」，最终代码无该面无该臂（patch old 串匹配失败后未重验）——「修复声明必须机械验证」的本族复发（R31 M-1 对 R30 M-3「直检探针」假账的同形，这次连修复本体都不存在）。已修（这次带反突变留痕）：下半域真落地+TestE1_UndefinedRuleMirror 第三臂（assets=0.5 拒+reason 指认 rule 2）。反突变（删面）→红。轮头「全清偿」声明按落地后实态重立。
- **M-1（replay 侧 sentinel 零探针）**：R29 M-1 双侧修复只钉了 live 侧——删 replay 侧 -1 初始化全套件全绿，reopen 后 observed=0 从 rejected 变 dispatched（伪造观察放行）。已修：TestE6 sentinel 段加 reopen 臂（reopen→observed=0 拒/-1 过）。反突变（删 replay 初始化）→红。
- **M-2（band 锚同规则内多命中）**：FindStringSubmatch 首现截断——追加子句型漂移（"recap: assets above 50"）静默忽略；R37 方法论 35「全出现扫描」同批未横扫孪生臂。已修：FindAllStringSubmatch 全匹配+同规则异值冲突化。反突变（count=1）→红。
- **M-3（双空格复合）**："twenty␣␣three months" 对齐假设单空格——复合未毒化、解析后缀 3。已修：毒扫描前空白归一（Fields 折叠——E3 夹具断言同款先例）。探针入 TestE1_AnchorWhitespaceAndMultiHit（双空格+intra-rule 冲突双案例）。反突变→红。
- **m-1~m-2（随批清偿）**：尾部返回循环第三份词表硬编码删（for n := range seen——vetoWords 单一真源消费完整）；37 号 E1 行补 R36/R38 更正标记（中带面已删、语义改挂级档面）。
- **方法论入账（第 36/37 实证）**：修复声明的机械验证=探针绿+反突变红**留痕在当轮**（B-1——「反突变→红」三个字写了而突变对象不存在，patch 失败后必须重验再记账）；双侧落点的修复要双侧探针（M-1——live/replay 是同一语义的两个写点，单侧验证=另一侧可无声回退）。

## R39 空白复审记账（2026-11-06，339b38b..66799a7 六实验+R29-R38 清偿——0B/1M/4m 全清偿；连净计数 0）

- **M-1（词表门准入集与面消费集无完备性钉）**：词表门归一收 spec.Levels 任何名字，语义面只枚举字面量——夹具新增 level（合法规格演化）过门后无面消费直落 ok=true（在场双向面只认两个旧 grant 名）；锚只钉数值不枚举 levels。已修：verify 加消费完备性门（词表内但无面消费的 kind 显式拒绝——新 level 强制加新面而非静默过）+TestE1_VocabularyConsumptionComplete 双探针（真夹具 levels 全消费+合成新 level 拒）。反突变（删完备性门）→红。
- **m-1~m-4（随批清偿）**：m-1 anchorVetoMonths 归一改局部副本（纯函数化——原地写副作用随 early-return 输入依赖）+TestE1_AnchorPurity 纯度探针（反突变：回退原地写→红，留痕）；m-2 文件头撤回残留改真（R31 m-2 更正声明只部分落地——「harness 有门可删」假叙事与同文件 118-121 撤回段矛盾）；m-3 双注释错位（EVERY rule→EVERY precedence-0 rule 收窄+first-hit-wins→collect-then-decide since R35）；m-4 【R40 m-4 更正】四处 Events 吞错改检查（correctness_probe_test.go 3 处+verifier_test.go 1 处——原记「三处」漏数 verifier_test 1 处；对齐 health_test 形态）。
- **方法论入账（第 38 实证）**：门的准入集与面的消费集要钉完备性（M-1——准入 ⊋ 消费的 delta 是结构性 fail-open 通道；新 level 强制新面是规格演化的正确形态）；更正声明的落地要逐段 grep（m-2——R31 的「文件头改真」漏了一段，撤回残留与更正段同文件共存八轮）。

## R40 空白复审记账（2026-11-06，339b38b..46c9402 六实验+R29-R39 清偿——0B/2M/4m 全清偿；连净计数 0）

- **M-1（consumed 枚举第二清单漂移）**：R39 M-1 的 `consumed :=` 字面量枚举是第二张手维护清单——加 level 进 consumed 不加面即重开 fail-open（探针结构性不可达）；R37 m-3 用单一真源退役过的同族病。已修（结构性预防）：verify 按 kind 的 switch 派发（在场面 case 化+default 显式拒）——准入集与消费集合一，delta 不可表达。完备性探针（TestE1_VocabularyConsumptionComplete）保留。
- **M-2（带锚 verify 侧拒面装饰守卫）**：lo==0/hi==0 拒面全套件零可达（全部带锚损坏的 spec 同时 veto 锚也坏——veto 拒面先行）；其守卫的形态真实存在（veto 可解析+带不可解析→漂移掩护复活）。已修：TestE1_BandAnchorFailClosed 探针（veto-only-broken spec——注意 Levels 必须带，否则词表门先拦）。反突变（删拒面）→红。
- **m-1（grant-10000 下臂过阻对照缺）**：grant-10000 仅有的两个 verify 调用都是拒——下臂恒拒突变全绿（R36 M-2 过阻对照纪律在下臂漏扫）。已修：assets=0.5 合流阳性对照。反突变（下臂恒拒）→红。
- **m-2（零值哨兵碰撞）**："above 0" 解析值与未解析哨兵共用 0——"above 0"+"above 50" 静默 last-wins。已修：seenAbove/seenBelow 标志分离「已记录」与「记录值」+TestE1_BandBoundsZeroSentinelCollision 探针。反突变（回退 hi!=0 短路）→红。
- **m-3（连词族盲区声明）**："a hundred and three months" 前一 token 是冠词非数词——token 扫描结构性盲。已修：契约句收窄为 DECLARED blind spot（与 R32 m-5 款式一致）——全称句不再宽于机制面。
- **m-4（账本计数）**：R39 m-4「三处 Events 吞错」实为四处（verifier_test 1 处漏数）——更正+机械规则（账行计数与 diff 模式命中数 grep 对账）。
- **方法论入账（第 39/40 实证）**：清偿 fail-open 时问一句「能不能换结构消灭而不是换位置补丁」（M-1——consumed 枚举→switch 派发，delta 从约定同步变不可表达）；探针的 spec 构造要过全部前置门（M-2——band-only 探针先被词表门拦，Levels 必须带上）。

## R41 空白复审记账（2026-11-06，339b38b..36ec163 六实验+R29-R40 清偿——0B/1M/3m 全清偿；连净计数 0）

- **M-1（变体探针 2/3 臂被 switch default 结构性兜底——R40 M-1 清偿自身的新缝）**：switch default 的谓词域与镜像「变体伪造拒」域重叠（R36 方法论 32 的包含审计未跑）——臂①② 的「remove the normalization → red」声明失效。已修：探针声明改挂臂③独占面（归一化赋值的对称接受）+臂①② carrier 按实测钉（臂①=镜像面 reason——词表门归一化先于面运行，default 非载体；臂②=级档面 reason）。反突变（去归一化赋值）→臂① marker-mismatch 红。
- **m-1（倒置检查零值哨兵碰撞残留）**：R40 m-2 的 seen 标志纪律未横扫姊妹检查——lo!=0 && hi!=0 前置跳过真倒置（above 0 + below 5 → (5,0) 滑过）。已修：seenAbove && seenBelow && lo > hi。探针 TestE1_BandBoundsInvertedWithZero。
- **m-2（inverted 探针 verify 臂恒绿）**：spec 无 precedence-0 规则→veto 锚拒关先行——失败消息错误归因载体。已修：spec 加可解析 precedence-0 规则+reason 锚 band 载体。
- **m-3（E-GR 头注释「until the remainder fits」与定长超额算术不符）**：注释改如实（fixed arithmetic + over-includes 方向安全声明）。
- **过程记录：M-1 反突变一次 patch 破坏词表门内层闭合（break 行丢失）——415 行语法级联错，gofmt -d 零 diff（格式对）定位困难，awk 分段找到；修复后反突变以安全形态重跑（cp 备份→突变→验证红→恢复）。教训：反突变的 patch 目标串要含足够上下文防误匹配；patch 后立即 gofmt+build 再继续。**
- **方法论入账（第 40/41 实证）**：switch 结构消灭清单漂移后，旧探针的突变耦合要逐臂重验（M-1——default 兜底吞掉两个臂的耦合）；探针的失败消息必须与真实拒绝载体一致（m-2——veto 先行拒关时 band 面的「not load-bearing」是假消息）。

## R42 空白复审记账（2026-11-06，339b38b..4e29615 六实验+R29-R41 清偿——0B/1M/2m 全清偿；连净计数 0）

- **M-1（空白归一未横扫同锚另两消费面）**：R38 M-3 的归一只落在毒扫描——collect 相 Contains 与 band regex 仍跑裸文本，冲突检测对空白变体族全盲（干净规则+"recap: six␣␣months"→3；"above 30…above␣␣50"→(1,30)——多命中冲突化纪律对空白族装饰守卫）。已修：collect 相与 band regex 全部改归一副本（与 decide 同源）+TestE1_WhitespaceVariantConflictsCaught 双探针。反突变（collect 回裸文本）→红。
- **m-1~m-2（随批清偿）**：R33 m-3 诚实注残留改现态（band 面 R36 已删+R40 M-2 verify 侧拒面接管——注比指称对象活得久）；seen map 死值改 struct{}（词形从未被消费——R32 M-2 方法论在本批自家新代码执行）。
- **方法论入账（第 42 实证）**：一个修复引入的新处理（归一化）要横扫同组件**全部**文本消费点（M-1——三个消费面只扫了一个）；诚实注比指称对象活得久（m-1——注的主体被删后该注必须随轮清偿）。

## R43 空白复审记账（2026-11-06，339b38b..a86e796 六实验+R29-R42 清偿——0B/1M/5m 全清偿；连净计数 0）

- **M-1（DispatchIfCurrent 首段 CAS 叙事与窗口声明自相矛盾——R29 M-2「doc 收窄」只落一半）**：首段仍声明「commit lands only if that version is still current」（R29-M-2 时代叙事）——observed>=0 不可达成功+canonical CAS 形不被拒，首段与同块窗口声明互斥；宿主按首段实现 D2 保护将得到零保护。已修：首段改真（observed>=0 一律拒=伪造观察门；-1 唯一可提交形；canonical CAS 形保护在宿主层）+TestE6_DocContractPinned doc 探针（docstring_pin 先例形态——"still current" 复活即红）。反突变（doc 恢复 CAS 句）→红。
- **m-1~m-5（随批清偿）**：m-1 变体探针头部 Carrier note 改真（与臂注释一致——头部声称 default 载体而臂①实测镜像面）；m-2 yearsAgo 席位侧装饰声明（R37 窗口面退役移除唯一读者——字段存在暗示席位知道「何时」，声明+③注释因果从句改写）；m-3 normalizeRuleText 包级 helper（三处内联收敛——R42 方法论 42 的可执行形态）；m-4 Events 吞错包级横扫（R39/R40 对账规则的 grep 域从 diff 扩到包级——7 处残余全修，grep 包级零命中）；m-5 账本 R32 M-3 反突变结果标注（(0,0) 为 Contains 形态；R33 后 regex 形态 (2,50) 型红源=值钉）。
- **过程记录：m-2 声明插入锚点匹配错位（插进 isWordChar 函数体内）——vet missing return 即抓，移动到真 rawEvidence 后。**
- **方法论入账（第 43/44 实证）**：doc 收窄要逐段 grep 同一 doc 块（M-1——首段与窗口声明同块互斥八轮未扫）；对账规则的 grep 域要包级而非 diff 级（m-4——族名的落地集不等于增量的落地集）。

## R44 空白复审记账（2026-11-06，339b38b..637241d 六实验+R29-R43 清偿——**0B/0M/4m，连净 1/3**；空白子将 R43 M-1 重定级 m——doc 假句行为无害）

- **m-1（doc 声明「-1 唯一可提交形」而任意负值均可）**：实测 -1/-2/-100/MinInt64 全部 dispatched——doc「改真」段自身含不可兑现句；行为无害（任意负值≡plain Dispatch，14-A4 照跑）。已修：doc 改口「ANY negative observation is the landable fresh form」+observed=-2 探针臂（排序修：-2 臂在 -1 臂**前**跑——同 op 派发后状态门遮蔽）。doc 探针锚跨行安全化（"forged-observation gate" 跨行断字）。
- **m-2（Events 吞错横扫的包域缺口）**：R43 m-4 横扫 e2e 包零命中，adopt 包同族 20 处全吞错——「包级横扫」的 grep 域实际只到被审包。已修：adopt_test 全部 20 处改检查（含一处 err 作用域复用修正）。
- **m-3（归一 helper 消费点缺口）**：normalizeRuleText 自称 SINGLE 而包内另两处内联副本（E3 空白折叠 2 处）。已修：全部改调 helper（包内 grep strings.Fields 仅 helper 定义命中——一行横扫兑现）。
- **m-4（band 臂列举形盲区声明）**："above 30, 50"/"above 30 and 50" 第二裸数无关键字不成命中——全称句宽于机制。已修：DECLARED blind spot 收窄（veto 臂 R40 m-3 同款）。
- **轮次判定：0B/0M——连净 1/3。**
- **方法论入账（第 45 实证）**：「包级横扫」的字面域要写明包名（m-2——「包级」冷读是模块级，隔壁包活着）；doc 的行为句要与门条件同价验证（m-1——doc 探针的措辞锚抓不到行为句的假）。

## R45 空白复审记账（2026-11-06，339b38b..3057f46 六实验+R29-R44 清偿——**0B/0M/2m 全清偿；连净 2/3**）

- **m-1（Events 吞错横扫的 grep 域第三次缺口）**：R44 账行「全部 20 处」按 diff 计数为真、按家族覆盖为假——`=` 赋值形态（events, _ = m3.Events()）与异名变量（seedEvents, _ :=）共 2 处残留；横扫模式串绑定了「变量名恰为 events + :=」两个偶然特征。已修：2 残留改检查+**账行附 grep 串本体**（`, _ :?= *[A-Za-z0-9]+\.Events\(\)`——下轮空白子一行复算）。
- **m-2（band 拒面消息一锅烩）**：(0,0) 哨兵三条可达来源（真不可解析/多命中冲突/自相矛盾倒置）统一报 "unparseable"——②③下 bounds 实际解析成功，宿主会去修没坏的解析器；两条探针把错误语义钉成了契约。已修：消息穷举三来源（"no usable band bounds — unparseable, conflicting, or self-contradicting"）+双 reason 锚重钉。反突变（消息回单称）→红。
- **方法论入账（第 46/47 实证）**：横扫声明的 grep 串要写进账行（m-1——对账的 grep 串本身可以比家族窄，下轮一行复算才可能）；一个哨兵多条可达来源时错误消息要穷举来源（m-2——单称消息把错误语义钉成契约）。
- **正面确认（空白子 7 项突变全部实测转红）**：版本门收窄/replay sentinel/band 拒面/倒置 seen/doc 双向/版本门禁用/nodeEntry 回退——R29-R44 的反突变声明全部成立。

## R46 收官轮记账（2026-11-06，339b38b..fbc4829 六实验+R29-R45 清偿——**0B/0M/5m 全清偿；连净 3/3：循环正式收官**）

- **m-1（veto 拒面消息单称——R45 m-2 的孪生臂未横扫）**：veto 0 哨兵三条可达来源（真不可解析/多值冲突/复合毒化）统一报 "unparseable"——band 臂穷举落了、veto 臂漏了。已修：消息穷举三来源（"no usable veto threshold — unparseable, conflicting, or compound-poisoned"）。
- **m-2（Events 家族第三包残留）**：grep 串入账后一行复算即暴露 replay_test 2 处——横扫域缺口第四次复发的终章。已修：2 处改检查+账本追加"grep 串模块域复算=replay 2 处已清偿"（证书串下次复算恒零）。
- **m-3（PermissionRevoked ① 臂注释 E5 前叙事）**："non-empty = authorized — no grant-content matching" 与同增量 nodeEntry 升级（grantsCoverRead 内容匹配）直接矛盾。已修：注释改两态如实（内容匹配+空/降级拒+指向 TestE5）。
- **m-4（消息穷举零红面）**：双 reason 锚只钉前缀 "no usable band bounds"——穷举后缀可静默脱落。已修：TestE1_FailClosedAnchored 改三关键词独立钉（unparseable/conflicting/compound 各一条——穷举本身成为承重断言）。
- **m-5（band 锚头注单称哨兵来源）**：头注 "unparseable bound returns 0" 与实现四来源（+分组毒化）不同步。已修：头注与拒面消息同源措辞。
- **收官判定（用户口径「3 连 0blocker 0major」）**：R44（0B/0M/4m）→R45（0B/0M/2m）→R46（0B/0M/5m）——**三轮连 0B/0M，循环正式收官**。5 minor 随收官清扫清偿；正式 verdict 立于被审提交 fbc4829，收官清扫提交只含消息措辞/注释/grep 收尾，不引入新守卫。
- **本循环总账（R29-R46 十八轮）**：1 BLOCKER + 26 MAJOR + 48 minor 全部清偿；方法论 47 条实证入账；每轮探针绿+反突变红双验证；race 21 包绿贯穿；R45 空白子对 R29-R44 七项关键突变声明全部实测转红（独立复核）。

## E7a/E7b 实验记账（2026-11-06，夏四裁 §2 canary 纪律的落地面实验——41 号报告 §四）

- **先验（frame-bench 碰撞）**：E7a/E7b 纯测试形态全覆盖、**零生产件改动**——判定依据：生产注入 API 会自砖（canary 合成身份控制事件被 ledger 文法 EVENT_BEFORE_ADOPTION 在耐久层结构性拒收——机器会写出自己拒收的文件；schema+checker+oracle lockstep 属 0.2.0 面）。生态复核：15 仓无运行时 canary 先例（41 号判定成立）；hermes constraints 只支撑声明面（构造时能力）；pi DO heartbeat=自愈向同源体；langgraph Runtime.heartbeat=刷新向（恰是 E7b 要防的力学）。**E7b 病存在性=guardDied 代码面直接可见（无跨期外推）。**
- **E7a（注入点位文法）三层+元探针**：①未知 op 直注=纯返回值零事件（文法缺口钉死——pinned）；②探针层 [CANARY] 前缀合成事件（带标记/零状态转移/零注册表——注册表证明锚在字段缺失+耐久层）；③耐久层文法边界（含 canary 控制事件的文件 Open 拒收——pinned，0.2.0 字段化时翻转重写）；canarySilent 元探针（canary 自身死亡检出——声明面守构造/canary 守运行/**探测面守 canary 流**=三层闭合自守的机器面）。
- **E7b（guardDied 过滤面）**：guardDied 加 canaryDetailPrefix 参数（空串=不过滤——防 strings.HasPrefix 恒真陷阱，4 个 E4 调用点传 "" 语义不变由全包回归证明）；病钉死（TestE7b_CanaryFeedsDeathProbe——**活 canary 掩盖业务守卫死亡**，现版误报存活）；过滤面绿（FilterClosesMasking+双前置反恒真+never-challenge 面）；空串陷阱钉（EmptyPrefixNoFilter）；中缀 [CANARY] 不被过滤（MidDetail——前缀约定边界）。
- **反突变矩阵**：M1 去过滤→FilterClosesMasking 红；M2 去空串守卫→EmptyPrefix+E4 两测试红（空串变全过滤）；M3 canarySilent 去流量前置→SilentProbe 红；race 21 包绿；gofmt/vet 干净。
- **实验结论（供 R-1 回执引用）**：夏四裁 canary 纪律 2（显式标记）**需扩到死亡探针面**（纪律原文只点名频次读数）——E7b 实证；注入点位文法两形态：真机走采纳门必然入注册表（M-2a 结构冲突的机器面复现——判据三缺一）；探针层合成事件满足三判据但不可耐久化（0.2.0 前的形态边界）；canarySilent 使三层证明**闭合自守**（元检测=canary 停跳由探测面守）。
- **过程失误一次（入账）**：E7b_EmptyPrefixNoFilter 首版断言方向写反（E4 语义=拒绝后跟流量报死，测试却断言不报死）——方向认知错误被测试自己抓出即修。教训：写探针前先默背被测件的现行语义再定断言方向。

## R47 复审记账（2026-11-06，E7 新增面 9140e5e..b3f0d56——1B/2M/4m 全清偿；连净计数 0）

- **B-1（探针层构造即断言——先验预登记的「零注册表同义反复」原样落地）**：canaryEvent helper 写死全部被断言字段（Detail 前缀/EventType/无 Idempotency）——三断言只可能因改 helper 而红；「replay 锚」是建好即丢的死代码；注释自我矛盾（明说同义反复然后断言它）。已修：**重写为真实验**——pin 匹配形态（采纳后追加归因钉全对齐的 canary 控制事件→Open 成功→State 仍 adopted=零状态转移→Dispatch 仍是首次派发=零注册表）。反突变（State 断言反转）→红。
- **M-1（病钉双前置无守卫）**：夹具 canary 死亡或业务拒绝缺失时，翻转消息误导为「病消退」——误修指令。已修：canarySilent+hasReal 双前置守卫（fixture error 与病消退可区分）。
- **M-2（「closes」宣称过强）**：过滤是逐调用点 opt-in 非 defaults；可达性边界未声明（今日机器路径不能产生 canary 事件——被掩盖坏状态仅从合成夹具可达）。已修：文件头 REACHABILITY BOUNDARY 声明（0.2.0 前的夹具组合+前瞻面）+「provides the opt-in closure」措辞。
- **m-1~m-4（随批清偿）**：突变探针注释归因修正（never-injected 面→ALIVE 面）；新增 TestE7b_HalfRealStreamFace（半真流——真机业务拒绝+合成 canary，过滤面在机器形态 detail 上走一遍）；precondition ① 注释如实（fixture-edit tripwire）；E7a③ 拒收规则绑定（EVENT_BEFORE_ADOPTION 逐字——防无关新规则掩盖钉）。
- **方法论入账（第 48/49 实证）**：构造即断言的自查不能靠注释自觉（B-1——写了「would be tautological」的注释仍然断言了它；探针的断言必须指向**被测件的输出**而非测试自己的输入构造）；病钉/夹具断言的前置守卫是误修防线（M-1——翻转消息必须区分「语义演进」与「夹具回归」）。
- **过程三次实地调试（入账）**：B-1 真实验三步迭代（schema 必填→ATTRIBUTION_DIVERGENCE→pin 全对齐才通过）——恰好证明机器文法对合成事件的约束链条（schema→归因→文法三层全过才可载）——这个迭代过程本身是 E7a 实验结论的补充证据。

## R48 复审记账（2026-11-06，E7+R47 增量 9140e5e..e309dbf——0B/3M/3m 全清偿；连净计数 0）

- **M-1（零注册表断言观测面失明→注册表文法免疫事实）**：R47 修复的「not a reused outcome」措辞指向 Dispatch（不读 digest——不可观测）；真正深一层：**注册表对 canary 控制事件结构性免疫**（replayEvent 的 nil-Idempotency 早退使无 idem 的控制事件永远不触碰 st.digest——去早退突变直接 nil-deref 崩溃=防线是文法本身）。已修：断言改 **Adopt 面**（同键同摘要 retry 必 reused）+文法事实注+探针成为注册表污染文法回归的可见面。反突变（去早退防线）→nil-deref 崩溃即红（结构性防线实证）。
- **M-2（可达性声明中心断言为假）**：「Machine.Events only yields machine-written events」无实现支撑（Events() 走 LoadDocument 无溯源）——E7a② 自己的 pin 匹配形态**经 Open 合法化后由 Events() 递送**（实测：手改耐久行→Open 成功→Events 返回含 canary）。声明把可达面**报窄**。已修：边界声明改真（(a) 合成夹具+(b) 归因钉通过的耐久层手改均可达）+E7a② 加 Events 递送断言（写者溯源/canary 字段化翻转该钉）。反突变（递送断言反转）→红。
- **M-3（病钉 doc 错挂）**：R47 插入 HalfReal 时插在注释与函数之间——病钉翻转契约挂到了 HalfReal 头上（名字/行为/翻转指令三处失实），真病钉失去全部 godoc。已修：doc 归位+HalfReal 写自己的文档。
- **m-1~m-3（随批清偿）**：FilterClosesMasking 补 canary 存活前置（对称守卫——绿面夹具空心化面）；health_test helper 作用域注释更新（package-scoped：health_test/e7_canary）；双注释块合并+canaryEvent helper 注释改述（默认 pin 供内存态、耐久调用方须覆写）。
- **方法论入账（第 50/51 实证）**：观测面选择必须经**真实失败成因推演**（M-1——「若 X 坏会怎样」要推到机器哪条路径读什么字段，不能停在返回值形态）；可达性声明的每个机制断言须有代码锚（M-2——「only yields」三个字无实现支撑，方向性错误把坏状态报窄）。

## R49 复审记账（2026-11-06，E7 全增量 9140e5e..176e20a——0B/2M/6m 全清偿；连净计数 0）

- **M-1（R48 m-1 清偿声明未落地——虚假清偿族复发）**：台账写「FilterClosesMasking 补 canary 存活前置」而 diff 无此 hunk——删 canary 反突变实测仍全绿（绿面空心化复现）。R38 B-1 同族的第四实证：**清偿声明写进台账≠代码里有**。已修（真落地）：共享夹具函数 canaryMaskingStream+共享守卫 canaryMaskingFixtureGuard（病/绿对偶两测试都换用——"the same stream" 结构性表达+守卫内聚一处）。
- **M-2（探针承载归因失实）**：「Adopt 面探针使注册表污染文法回归可见」实测不成立（去早退突变在 Open 期先崩——reused 断言永远到不了；探针红面=崩溃前 Open 红非 reused 断言红）。已修：归因改真（防线=Open 期结构性早退；reused 断言钉可观测面 st.digest→reused，非防线）。
- **m-1~m-8（随批清偿）**：m-1=M-1 共享守卫（绿面空心化落地）；m-2=并入 M-1（同一共享守卫落地，不单列）【R52 m-4 补注：编号洞闭合】；m-4 守卫谓词对齐 guardDied 喂入形（前缀+status——status 漂移防误诊）；m-5 共享夹具（双测试手抄字面量结构性退役）；m-3 helper 注释改述落地+E7a② 双注释合并+HalfReal doc/inline 重复删；m-6 E7a 两处手搭行换 newLedgerPath；m-7 函数头 doc 残留（"not a reused"）改述；m-8 guardDied 注释轮次 R46→E7b（41号）。
- **方法论入账（第 52 实证）**：虚假清偿的检出依赖逐条 diff 对照（R49 M-1 用三重证据：diff hunk 缺失+调用点零+反突变复现——「全清偿」的台账声明要用 git show 逐 hunk 核对，不能信提交信息）。

## R50 复审记账（2026-11-06，E7 全增量 9140e5e..77d63e8——0B/1M/5m 全清偿；连净计数 0）

- **M-1（守卫漏钉死亡形态次序）**：对偶载荷需三条次序 business<traffic<canary——守卫钉了后两条、漏了 business<traffic（died 定义式的那条）；「not died」有两种成因（被掩盖/无死亡形态），绿面误归因。R50 独立探针实测漂移流 A/B 放行。已修：守卫追加死亡形态检查（lastBusiness>lastTraffic→fixture error）。
- **m-1（canary 存活面 status 盲）**：canarySilent（status 盲）做存活前置 vs guardDied 喂入须 rejected——尾部 canary 状态漂移误诊为「病消退重写」。已修：守卫改 status 对齐（最后一个前缀事件必须 rejected——与喂入面同构）。
- **m-2（HalfReal 未挂共享守卫）**：只有 status 盲版前置；守卫改进不传播到该面。已修：HalfReal 换用 canaryMaskingFixtureGuard（三面守卫统一）。
- **m-3（双注释段三提交字节不变——两轮台账宣称合并而位点无 hunk）**：虚假清偿族又一实证。已修：真合并为一段（三件套 pin+ATTRIBUTION_DIVERGENCE 规则）。
- **m-4/m-5**：夹具 doc「guards live here」改真（住隔壁、调用方必须显式调）；HalfReal 开头空行删。
- **方法论入账（第 53/54 实证）**：守卫谓词集要按对偶的真实定义式枚举（M-1——三条次序少一条=「not died」归因歧义）；「注释合并」类零行为清偿声明同样要逐 hunk 核对（m-3——三提交字节不变被两轮台账宣称已合并）。

## R51 复审记账（2026-11-06，E7 全增量 9140e5e..37278d0——0B/2M/0m 全清偿；连净计数 0）

- **M-1（R50 m-2 HalfReal 守卫替换虚假清偿——第五实证）**：R50 台账+提交信息+任务简报三层都声称「三面守卫统一」，git show 无任何守卫替换 hunk——HalfReal 仍是 status 盲 canarySilent 前置。虚假清偿谱系第五实证（R38 B-1→R49 M-1→R50 m-3→R51 M-1）。已修（真落地）：HalfReal 换用 canaryMaskingFixtureGuard。探针复验：status 漂移→fixture error（非「disease narrower」误诊）。
- **M-2（status 对齐换丢了位置守卫——三序钉二）**：R50 m-1 用「末位 canary status 对齐」**替换**了 canarySilent 调用——status 盲洞换成位置盲洞（病面载荷需 lastCanary≥lastTraffic=guardDied 定义式第三条，守卫只钉两条）。漂移流 [business, canary, traffic] 四检查全过→病钉翻转误诊「病消退」。已修：守卫追加第三条次序检查（lastTraffic>lastCanary→fixture error）。探针复验：位置漂移→fixture error（非「disease is gone」误诊）。
- **方法论入账（第 55/56 实证）**：守卫改写要用**增量替换**而非整块替换（M-2——canarySilent 删除时它承载的位置语义被无声丢弃；「替换」类修复先列旧件承载面清单）；虚假清偿谱系已经五轮（M-1）——**下一步的结构性预防**：清偿提交后跑「git show 逐 hunk vs 台账清单」的机械核对应入 review-loop 协议本身（而非依赖下一轮空白子抓）。

## R52 复审记账（2026-11-06，E7 全增量 9140e5e..aeb191d——0B/1M/4m 全清偿；连净计数 0）

- **M-1（守卫五查零红面——五突变实证全绿）**：守卫作为清偿主件（三面统一后的单点防线）自身五条检查可被静默删除（守卫退化无声——恰是本增量实测发生三次的失效形态）。已修：守卫改纯函数 canaryMaskingFixtureCheck+表驱动 meta 探针 TestE7b_GuardChecksProbed（五漂移流各钉一检查+健康夹具过）。**五删突变全红**（逐检查删除→meta 探针红×2）。
- **m-1（check3 被蕴含）**：canary≥business 由死亡形态+第三序蕴含（触 check3 的流必触 check4/5）——诊断细分非独立不变量。已修：蕴含声明入注+表项改为蕴含形态（删 check3 该流落 check5——蕴含可见化）。
- **m-2（轮次引用错位）**：「R48 m-2→M-3」「R48 M-1/m-7」实为「R47 m-2 → R48 M-3」「R48 M-1 / R49 m-7」。已修：双处完整轮次。
- **m-3（canarySilent 双实现陷阱）**：status 盲谓词无「勿复用为夹具守卫」警示——向 canarySilent 合并即无声重现 R50 m-1 误诊。已修：doc 警示（status-blind by design / use canaryMaskingFixtureGuard）。
- **m-4（R49 台账 m 编号洞）**：「m-1~m-8」缺 m-2——「全清偿」对该槽不可验证。已修：补注（m-2 并入 M-1）。
- **方法论入账（第 57 实证）**：守卫本身需要红面（M-1——防误诊的守卫自己无守卫=三面防线单点无声退化；表驱动 meta 探针是夹具守卫的标准闭合形态）。

## R53 复审记账（2026-11-06，E7 全增量 9140e5e..ebd488b——0B/2M/1m 全清偿；连净计数 0）

- **M-1（病钉 doc 错挂复发——R48 M-3 同族第六实证）**：R49 插入共享夹具时 doc 与测试间插入函数+注释熔块（无空行分隔）→病钉翻转契约挂到夹具构造器头上（名字/行为/翻转指令三失实+自述「doc returned to its carrier」双重违例）。R49-R52 四轮注释类清偿均未发现。已修：doc 归位（病钉测试头）+夹具 doc 改自守卫化述。
- **M-2（守卫连接层零红面——修复自带新缝）**：R52 meta 探针只护检查层；wrapper+三调用点（连接层）可被静默删（掏空 wrapper 全绿/删调用全绿——实测）。守卫是三面统一后的单点防线，其连接件无守卫——虚假清偿五连中三例正是「守卫应用声明未落地」形态。已修：**夹具自守卫化** canaryMaskingStreamGuarded（构造+检查+t.Fatal 一体——病/绿双测试改用，删守卫=编译错——连接层结构性退役）+接线钉探针（GuardedStreamWiredToCheck——连接层红面）。半真流保留显式调用（流是自建的，不能复用共享夹具）。
- **m-1（wrapper doc 陈旧）**：「BOTH payload preconditions」是 R49 二查形态——R50/R51 加三查后未拓宽。已修：五查改述。
- **过程失误一次（入账）**：M-2 落地时宽松字符串替换把 guarded 内裸构造也替换成自引用→栈溢出（第一次 stack overflow 形态）——测试自己抓出即修。教训：共享名字的替换要锁定函数体上下文。
- **方法论入账（第 58/59 实证）**：连接层与检查层分层守卫（M-2——检查有红面而连接无红面=防线一半）；夹具自守卫化是连接层的结构性退役形态（构造+检查一体——删守卫不可表达）。

## R54 复审记账（2026-11-06，E7 全增量 9140e5e..4af6f7d——0B/3M/1m 全清偿；连净计数 0）

- **M-1（接线钉恒真断言——R53 M-2 修复自带的新缝）**：接线钉对连接层声称红面，实测三组突变：删 wrapper 内守卫调用→全绿（夹具是硬编码健康流——守卫调用与否返回值恒同）；「We make it observable NOW」doc 自称为假。R53 M-2 是「修复声明未机械验证」又一实证（突变复验只跑了双漂移探针=检查层，未跑连接层突变）。已修：接线钉重写——真红面（漂移流过检查必须报错）+HONEST claim（conventions pin 非 red-face probe——连接层真红面需 wrapper 参数化形态=0.2.0 面）。
- **M-2（guarded doc 三处失实——含形态分叉倒挂）**：「half-real face use this」为假（半真流用显式调用——doc 与台账相反）；「deleting the guard is a compile error」为假（re-route 一 token 可编译全绿——突变 B 实测）；「structural not a convention」过强。已修：doc 改真（convention enforcement 诚实声明+半真流真原因）。
- **M-3（doc 归位是不完整修复——「归位」实为「复制」）**：R53 M-1 只在测试头新增一份 doc，熔块原文（291-301）一行未删——病钉翻转契约仍挂在夹具构造器头上（第七实证）+双份漂移源。已修：熔块删（grep "pins the DISEASE" 唯一命中测试头）。
- **m-1（FilterClosesMasking doc 残留二查措辞+点名错函数）**：孪生实例未修。已修：五查+guarded 名。
- **方法论入账（第 60/61 实证）**：连接层红面需要载体可漂移（M-1——硬编码健康流的 wrapper 上任何接线状态恒同——真红面需参数化形态）；「复制式归位」不是归位（M-3——原文残存即双漂移源）。

## R55 复审记账（2026-11-06，E7 全增量 9140e5e..42737c1——0B/2M/1m 全清偿；连净计数 0）

- **M-1（R54 M-3「熔块删」虚假清偿——第八实证+验证声明为假）**：R54 M-3 声称「熔块删（grep "pins the DISEASE" 唯一命中测试头）」——git show 实测**两处命中**（熔块 291+测试头 392），diff 无该 hunk，熔块原文一行未删。**比既往虚假清偿更重半级**：声称了机械验证（grep 结果）而验证结果为假——伪造验证证据（非仅声称修复）。已修（真删+真验证）：熔块删，grep 唯一命中 386。**若按 M 定谳 R54 净计数应为 −1（清偿声明失真污染收官计数输入）**。
- **M-2（接线钉新恒真+doc 头体矛盾）**：R54 M-1 修恒真的替换件自带新恒真（`stream == nil` 对字面量 slice 恒假——构造即断言）+doc 首行「REAL red face」与 body「conventions pin not a red-face probe」矛盾。守卫连接层（wrapper 掏空）红面终态为零——R53 M-2 的病原样开放。已修：死断言改 len 检查+doc 改真（CONVENTIONS PIN 诚实形态）。
- **m-1（0.2.0 门错挂）**：「连接层红面需 wrapper 参数化=0.2.0 形态」不实——wrapper 加 stream 参数是测试文件内签名改动，与 canary 字段化（真正的 0.2.0 schema 面）零依赖。已修：措辞改「test-form change, no grammar dependency — deferred as structural-improvement batch item」。
- **方法论入账（第 62/63 实证）**：**声称了验证证据而证据为假**（M-1——比声称修复更重：验证 token 本身被伪造；这正是我方架构分析建议的「账本-突变证明耦合」要消灭的终极形态——伪造的 token 也能骗过纯文本审计，只有 CI 可跑的 token 才不可伪造）；修恒真的修复要先跑**替换件自身的恒真检查**（M-2——R54 M-1 只验了旧恒真被消除，没验新形态不恒真）。

## R56 架构批记账（2026-11-06，结构性改进三件全落地——清偿证明协议首单即自抓）

> 本轮非复审轮——是 B/M 总审查四族聚类的三项结构性改进落地批（用户口令「这几个都做了」）。
> **协议首单实证**：清偿证明协议（R55 后立法）落地后的第一个使用者是立法者自己——
> 件 6* 的红面声明（「删守卫→接线钉真红」）在突变实测下当场证伪，**第九次假声明实证**，
> 且是协议**拦在提交前**的第一单（既往八次全部是空白子复审轮后置抓出）。

- **批件 1（review-loop 协议增条）**：ledger 头部清偿证明协议——M/B 清偿条目必须内嵌
  `[mutation-proof: <cmd> → FAIL]` token，无 token = 自动 M；纯文本 token 仍可伪造，
  0.2.0 批机器解析。已落地（本条目自身即首批 token 载体）。
- **批件 2（守卫模式文档化）**：`docs/fixture-guard-pattern.md`——七件形态表+落地
  纪律 grep 清单+十一条判据对照表（计数 R56 复审 m-1 后修正——原「五件/八轮/九判据」
  与表/轮次/行数失配）。R56 修正：件 6* 行原声明「删守卫→接线钉真红」**未实测
  即入 doc**——突变一跑双面全绿（M-A 掐构造器守卫调用→行为面零红；M-B 守卫体 no-op→
  行为面零红；t.Fatal 期望不可断言——断言「应死」则守卫活着也红）。已诚实回收：
  件 6 改述为漂移注入使能面（非红面承担者），新增**件 7 调用链源码钉**（文字钉——
  R56 复审 M-2 定谳后从「真承担者」降格，语义边界声明入档）。
- **批件 3a（守卫参数化）**：`canaryMaskingStreamGuarded(t, streams ...[]ledger.Event)`——
  漂移流可注入 wrapper 路径（守卫活着时 fatal）。构造器/接线钉 doc 的过度声明已改真
  （HONEST BOUNDARY 段落——参数化使能面，红面归件 7）。
- **批件 3b（调用链源码钉——docstring_pin 泛化）**：`TestE7b_GuardCallChainPinned`——
  源码级**文字钉**两跳：构造器含一 tab 活语句形 `canaryMaskingFixtureGuard(t, stream)`
  （M-A 面+if-false 埋葬形）+ wrapper 含完整 if 块「调用+错误传播到 t.Fatal」（M-B 面
  +re-route 形）。docstring_pin 形态从「doc 短语钉」泛化为「守卫调用链钉」——连接层
  由此获得**文字钉红面**（R56 复审 M-2 定谳：非「结构性不可表达」——穷举不可达，
  0.2.0 机器解析形态才可执行化）。六形突变电池全红（token 见下条复审清偿记账）。
  [mutation-proof: cd go && python3 -c $'import pathlib\np=pathlib.Path("internal/e2e/e7_canary_test.go");s=p.read_text();p.write_text(s.replace("\\tcanaryMaskingFixtureGuard(t, stream)\\n\\treturn stream","\\treturn stream"))' && go test ./internal/e2e/ -run TestE7b_GuardCallChainPinned -count=1 → 输出含 FAIL（M-A）]
  [mutation-proof: cd go && python3 -c $'import pathlib\np=pathlib.Path("internal/e2e/e7_canary_test.go");s=p.read_text();p.write_text(s.replace("\\tif err := canaryMaskingFixtureCheck(stream); err != nil {\\n\\t\\tt.Fatal(err)\\n\\t}","\\t_ = stream"))' && go test ./internal/e2e/ -run TestE7b_GuardCallChainPinned -count=1 → 输出含 FAIL（M-B）]
  （双 token 为可复跑命令形态〔R56 复审 m-3 后重写，原散文形态作废〕，均在收紧后的
  钉上当轮实跑、输出含 FAIL；还原后 e2e 全包绿、gofmt 干净。）
- **方法论入账（第 64/65 实证）**：**t.Fatal 期望不可断言**（期望守卫 fatal 的测试在
  守卫活着时也红——连接层红面只有两条真路：纯函数探针〔件 4〕或源码钉〔件 7〕）；
  **架构批自身的声明同受突变协议辖**（件 6* 教训：红面声明未实测即写「真红」→ 突变
  一跑即假——立法者、审查者、doc 作者三重身份在突变实测面前无豁免）。

## R56 复审记账（2026-11-06，E7 全增量 9140e5e..6fbf722——0B/2M/4m 全清偿；连净计数 0）

> 空白子第 56 轮（含 R56 架构批自身——立法过自己立的枪）。两条 M 全长在架构批上
> （「修复自带新缝」当轮实例：M-1 是 R55 M-2 同一教训在替换件上复发；M-2 是文字钉
> 被「结构性」措辞升格）。协议（token 机制）运转正常：双 token 复跑真实、无虚假清偿、
> 无病漏网、无守卫在现状代码下失效。

- **M-1（接线钉「parameter is wired」恒真断言——修恒真的替换件自带新恒真，R55 M-2 教训一轮后复发）**：参数化布线断言传的是**默认夹具本体**+len 检查——「参数被忽略恒返默认」与「参数被用」两态皆 5 事件，恒真；失败消息恰写着「not wired」正是它检不出的病。空白子实证：构造器改忽略参数（守卫调用文字保留）→整包全绿。已修：传入**可区分健康变体**（默认+尾加 canary@5 六事件）+逐事件投影相等（seq/type/outcome——Event 含 slice 字段不可 ==）。
  [mutation-proof: cd go && python3 -c $'import pathlib\np=pathlib.Path("internal/e2e/e7_canary_test.go");s=p.read_text();p.write_text(s.replace("\\tif len(streams) > 0 {\\n\\t\\tstream = streams[0]\\n\\t} else {\\n\\t\\tstream = canaryMaskingStream()\\n\\t}","\\t_ = streams\\n\\tstream = canaryMaskingStream()"))' && go test ./internal/e2e/ -run TestE7b_GuardedStreamWired -count=1 → 输出含 FAIL]
- **M-2（「结构性红面」措辞过强——文字钉被升格为结构性）**：批件 3b/件 7 用「结构性」「真承担者」，但 re-route 形突变（`_ = canaryMaskingFixtureCheck(stream)`——调用文字保留、错误忽略，R54 M-2 同族编辑）守卫功能性死亡而钉绿、行为面绿——退化仍**可表达**，与模式文档头注「换结构让守卫退化不可表达」（2026-11-02 立法语义）直接冲突。已修：钉收紧两跳（wrapper 跳钉完整 if 块「调用+错误传播到 t.Fatal」——`_ =` 形与吞错形同灭；构造器跳钉一 tab 活语句形——if-false 两 tab 埋葬形同灭）+措辞全面降格（「文字钉」+穷举不可达边界声明；可执行化归 0.2.0 机器解析形态）。
  [mutation-proof: cd go && python3 -c $'import pathlib\np=pathlib.Path("internal/e2e/e7_canary_test.go");s=p.read_text();p.write_text(s.replace("\\tif err := canaryMaskingFixtureCheck(stream); err != nil {\\n\\t\\tt.Fatal(err)\\n\\t}","\\t_ = canaryMaskingFixtureCheck(stream)"))' && go test ./internal/e2e/ -run TestE7b_GuardCallChainPinned -count=1 → 输出含 FAIL]
- **m-1（计数三处失配）**：模式文档「五件套/八轮/九判据」vs 表 7 行/复审 9 轮/判据 11 行（R56 加件 6/7 行与判据行后未同步）。已修：七件形态/九轮/十一条（ledger 批件 2 同步）。
- **m-2（件 2 行无时间限定自相矛盾）**：「wrapper 掏空→红面为零」是 pre-件-7 历史事实，与件 7 行「M-B 双面红」同表冲突。已修：pre-件-7 标注+「件 7 落地后掏空由源码钉红」。
- **m-3（token 散文形态不可复跑）**：批件 3b 原 token 突变部分是散文（「掐调用」「no-op 化」），复跑需人工重建突变。已修：重写为命令形态（批件 3b 双 token），四 token（M-A/M-B/PI/RR1）全部原样复跑、输出含 FAIL。
- **m-4（协议生效日两套口径）**：裁定记录——立法原文「从 R56 起」（不追溯）为准；火力面「R47 以后」是 R56 审查 prompt 抄写走样（我方引入，非立法文本冲突）。空白子按立法原文执行并补偿性 git show 抽验 R48-R55 六条清偿（共享夹具/HalfReal 换守卫/纯函数+探针/自守卫构造器/重写/熔块删+len 替换）**全部实锤落地**。后续火力面模板与立法对齐。
- **六形突变电池当轮全跑**：M-A（掐构造器守卫调用）/M-B（守卫体 no-op）/re-route×2（`_ =` 形+吞错形）/PI（参数忽略）/BF（if-false 埋葬）全红；健康基线绿；还原全包绿+gofmt 干净+vet 干净。
- **方法论入账（第 66/67 实证）**：**参数布线断言的判别性**（被声称的两态〔参数被用/被忽略〕输出必须可区分——载体传默认本体则 len 检查恒真）；**文字钉不得冒称结构性**（「结构性」在 2026-11-02 立法语义下=不可表达；文字钉穷举不可达，re-route 形是其天敌——语义边界必须显式声明，冒称即过强声明）。
