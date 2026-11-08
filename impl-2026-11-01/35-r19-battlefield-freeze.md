# 35 · R19 中断封存（2026-11-05 用户断网前）——review-loop 战场快照

> 范式：战场保存。恢复入口：本文件 + `git log` 三个本地提交 + 账本 R17/R18 段。

## 会话目标（用户原话）

「用空白子 4-lens 和 singularity 审核从上次我推 MR 到现在的新增代码，一直到 3 连 0blocker 0major。具体每个轮次如果遇到 blocker 和 major，就找到同类问题后修复再进入下一轮次。」

**进度：R17（3M）→R18（3M+2m）→R19（5M+2m，修复进行中被中断）。3 连 0 计数：0（三轮全有 M，streak 未开始）。**

## 提交链（本地 detached HEAD，未推送——推送须用户口令）

- `c919009`：先行批（P3+L23+T2 轴承 L39-L44+L47）——已推送过 MR
- `5f47936`：R17 清偿（L40 幻影→真知识检索断言；L42/L43 红探针；L44 fail-closed；反突变五连红）
- `3661235`：R18 清偿（findForNode sortedKeys；必填键 fail-closed；Atoi 严格解析；READ-4 真过渡形态；反突变 M1/M2/M3/A2 全红）
- **`<本提交>`：R19 半程 WIP**——5M 中 4M+2m 已修但未跑反突变、未记账、K-expired 未改

## R19 空白审核结论（agent 报告原文在会话里，此处摘要）

0B/5M/2m，全部实锤（空白子用 /tmp 隔离脚本实测过前提）：

- **M-1**：revisionNumber 的 Atoi 同族修复零探针耦合（"er-2x" 形态新旧两版行为相同——探针只耦合了 execute 半面）
- **M-2**：R18 的 sortedKeys 改动静默解除 TestT2K_ExpiredKnowledgeNotConsumed 武装（"method-current"<"method-expired" 字典序，去 Valid 检查突变下由 ~87% 概率红变恒绿）
- **M-3**：修正窗口（v2 发布、v1 未翻转）内最低 ID tiebreak **确定性服务 stale v1**；Replaces 零机制消费；F-04「superseded 不被消费」名实不符
- **M-4**：必填门声明驱动、解析门硬编码键——欠声明方法（InputFields 不含 overdue_months）缺键时静默过两道门=0（E0 缺键形态经声明缝重开）
- **M-5**：负值 overdue_months（"-4"）静默过 Atoi 门（-4>3 假→不否决）；注释「ALL corrupted forms」名实不符
- **m-1**：business_request_id 存在但空串过必填门（孤儿结果）
- **m-2**：翻转失效惯用法两态（整结构体覆写 vs range-mutate）——覆写会丢未列字段

## 已修（在 WIP 提交里，全绿：build/vet/e2e 全过）

- M-3：findForNode 机械化消费 Replaces（superseded 集合跳过）+ invalidate(id) 单一翻转写径 + TestT2FindForNode_SupersessionWindow 探针（窗口内必须返回 v2）
- M-4：execute 契约/消费分叉检查（欠声明 overdue_months 即 fail-closed）+ 探针
- M-5：负值检查 + badInputs 加 "-4"
- m-1：必填门空值检查（v=="" 报错）+ 探针
- M-1：TestT2Lookup_RevisionOrdering 加 "er-2x" vs "er-1" 子场景（前缀垃圾 revision 必须排最低）
- 注释同步更新（execute/parse 探针 doc）

## 未做（恢复后按序执行）

1. **M-2+m-2 收尾**：t2host_rk_test.go 的 TestT2K_ExpiredKnowledgeNotConsumed 改名（expired→"method-a-old" 排更低、current→"method-b-new"）+ 该夹具**删 Replaces**（纯 Valid 面——留着会被 supersession 机制掩蔽 Valid 突变）+ 循环改用 invalidate()；READ-4 的整结构体覆写改 invalidate()
2. **反突变六连**（须全红才算闭环）：M1（revisionNumber 回退 Sscanf→er-2x 红）、M2（去 Valid→K-expired 红）、M3（去 supersession 跳过→窗口探针红）、M4（去分叉检查→欠声明红）、M5（去负值→"-4"红）、m-1（去空值→空 brID 红）
3. 全量 race 回归（21 包）
4. 账本 R19 段记账 + 提交
5. R20+ 复审轮（空白子），直到 3 连 0B/0M 收官
6. 收官后：第二步六实验 E1/E2/E4/E5/E6/E-GR（全零 LLM 可排队）→第三步邢超回复+夏回执

## 等待面（不变）

- 【等对方】MR !2 复核；【等刘】三个窄问题；【等用户】T1-run3 启动授权；推送/记账须当次口令

## 过程教训（本会话新增，已入账本 R18 段）

- 反突变验证中 `git checkout --` 误杀未提交修复一次（从 /tmp 重建）——**持有未提交修复的工作树禁用 git checkout 恢复突变，用 /tmp 副本**
- 突变形态错误（追加语句落在 return 后成不可达死代码，Go 合法）被 -v 调试抓出——**突变本身要验证「真的改变了行为」**（debug 探针打印返回值）
- 反突变的红分确定性红与概率红（88/12 的红是掷骰子）——R19 的 M-1 探针设计要保证确定性红或记明统计功效
