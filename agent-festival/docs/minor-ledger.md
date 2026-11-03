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

（singularity R21/R22 两轮判定一致：无可达奇点；R22 新增最强候选=F-A 输入契约结构化（LiteralDoc newtype，最便宜关闭 L8 窗口）+F-B 生产者包含性（writer ⊆ checker 闭包钉）；R21-F1 差分生成器维持首选杠杆。全记录见外环 R21/R22 报告 Part II。）六分叉——F1 差分生成器为下一杠杆推荐、F4 文法层严格性为待裁①同步收编、F6 单源代码生成按框架价值否决；无可达奇点，当前框架仍为正确收敛框架。全记录见外环 R21 报告 Part II。）
