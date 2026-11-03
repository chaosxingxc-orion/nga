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
