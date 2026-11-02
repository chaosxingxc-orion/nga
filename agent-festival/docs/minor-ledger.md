# 未修 MINOR 台账（R20 循环宪法：minor 一律不修只记账）

记账规则：外环/内环发现的 MINOR 一律不入修复循环——修 B/M + 同族穷举，
minor 只记账。本文件即台账；每轮新增追加，不删除（退役另标）。

## R20-R21 前转入（R18 内环六 m + R19 内环二 m 的遗留）

| # | 位置 | 内容 | 来源 |
|---|---|---|---|
| L1 | examples/java-consumer/README.md:4,20 | 83→81 算术错+「wrong-reason pins hit」残句重复 | R18 内环 m1/m2（fa18315 算术错，81 才是真数） |
| L2 | examples/java-consumer/src/main/java/spike/Main.java:37 | FORMAT_DOC_CLAIMS release 行尾注释同文双写 | R18 内环 m3 |
| L3 | examples/java-consumer/src/main/java/spike/Main.java:155 | COUNT-FAIL 消息钉值 200 未随比较值改 205 | R18 内环 m4 |
| L4 | examples/java-consumer/src/main/java/spike/LedgerChecker.java:120-129 | family-4 节头 v1 ±2^53 NOTE 未随章程重写（与 R16 新注释互斥） | R18 内环 m5a |
| L5 | examples/java-consumer/src/main/java/spike/LedgerChecker.java:37-39 | TWO_POW_53 孤儿字段（唯一消费者已退役） | R18 内环 m6 |
| L6 | schema/replay.py:4-5 | docstring「drives ONLY from schema」全称残句（与 R16 字面量门矛盾） | R19 内环二 m1 |
| L7 | schema/compose.py:423 | 尾句「non-integral float reaches dec() and raises」与行为不符（3.5 在 schema integer 面即拒） | R19 内环二预存注记 |

## R21 起新增记账

| # | 位置 | 内容 | 可达性 | 来源 |
|---|---|---|---|---|
| L8 | go/internal/validate/validate.go:952（LoadFixture 裸 json.Unmarshal，compose 族经 WithLoader 骑此面） | 解码纪律双轨：章程全称条款「解码必须 UseNumber」存在未豁免违反面——七族唯 compose 骑非合规 loader。今日零后果（bounds schema 上限 2^53-1 恰为折叠边界，域内折叠精确/超域折叠后仍超上限双侧同拒）；开窗条件=待裁①转 literal-only（字面量门在 float64 map 不可判定）或新增无 2^53 上限数值域（2^53+1 Py 精确/Go 折叠成 2^53 判决分叉）。修法挂待裁①落笔时同步（WithLoader 换 UseNumber）或章程显式登记「base loader=已知违例面」 | 趋零可达（双条件才开窗） | R21 外环 MINOR-1 |
| L9 | go/internal/evidlog/evidlog.go:240 + go/internal/adopt/adopt.go:475 | durable 文件权限位静默翻转：os.CreateTemp 恒 0600 + rename 整文件替换丢原 0644 权限位——一个 Append 即触发（探针实测），审计记录消费方组/他者读预期静默失效。修法（两包一次）：CreateTemp 后 os.Chmod(tmp, 原 mode 或 0644&^umask) | 本地构造 | R21 外环 MINOR-2 |

（singularity R21 判定记录：六分叉——F1 差分生成器为下一杠杆推荐、F4 文法层严格性为待裁①同步收编、F6 单源代码生成按框架价值否决；无可达奇点，当前框架仍为正确收敛框架。全记录见外环 R21 报告 Part II。）
