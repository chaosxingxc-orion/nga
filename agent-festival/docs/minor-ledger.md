# 未修 MINOR 台账（R20 循环宪法：minor 一律不修只记账）

记账规则：外环/内环发现的 MINOR 一律不入修复循环——修 B/M + 同族穷举，
minor 只记账。本文件即台账；每轮新增追加，不删除（退役另标）。

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
