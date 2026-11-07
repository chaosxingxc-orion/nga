# 场景 R+K 范围框定（2026-11-05）：持久化结果复用 + 新任务知识消费

> 范式：xuefanfan 八段（本文件）。出处：xingchao 198178087（场景 R/K 规格书）+ 198232012（幂等≠正确补充）+ 29 号对账合成验证计划。

## IN

1. **T2 参考宿主层**（`go/internal/e2e/t2host_test.go`，明确标注 reference-host tier）：最小节点入口 + 结果存储 + 失败探针适配器。**不是新框架**——是 R/K 验收所需的最小宿主面。
2. **场景 R（持久化结果复用）**：第一次执行收到不可重推导的业务回执 → 终态提交节点结果 → **关闭宿主清空内存** → 重启 → 模型/工具/业务适配器全换"调用即失败"探针 → 同次节点重提交 → **从持久记录返回原结果+原回执** → 零模型零业务调用。变体：同键异载/权限撤销/尚在等待/部分内部调用已完成。
3. **场景 K（新任务知识消费）**：发布一项知识化方法（材料核验 Workflow）→ 创建**此前没有结果**的新任务 → 经声明消费流程命中方法 → 被测节点全部模型入口设失败探针 → 执行方法产生**新任务自己的结果** → 零模型调用（数据/API 可调用）。变体：知识过期/范围不匹配/相似不同请求/权限变化。
4. **纠错共存**（198232012 §四 How）：R 中追加纠错修订（同 business_request_id、新 operation_id）→ 有效性投影（per business_request 最新已采纳修订）→ 四读分立断言（幂等读/有效性读/历史回放/知识检索）。
5. **E3 修复联动**：p3FixtureCorrectionLanded 翻转开关就绪——若 P3 修正在本批落地，E3-window 翻转。

## OUT

- 不做通用正确性引擎（29 号对账裁定：只做可判定约束子集）
- 不做 preconditions[] schema（0.2.0 批次，与本批解耦——R/K 验控制语义不验 schema 面）
- 不替代 openJiuwen（T2 是验证参考宿主，明确标注不是新基座）
- 不实现 0.2.0 条件边/循环（图级执行实例——D-02 已认领待 0.2.0，R/K 在节点层验证不需要图循环）
- 不新增身份产品（执行实例 = f(运行, 节点, 迭代序) 由宿主派生，R/K 用 operation_id 即可——单节点单迭代场景）

## 复用清单（不重设计）

adopt 状态机（幂等/conflict/unresolved/控制事件）= R 的控制面；evidlog 覆盖检查 = K 的足迹对账；T0 taskHarness = 扩展为 T2 的骨架；ReAnchor A 臂纪律 = K 的病存在性对照。

## 依赖 DAG

```
T2 宿主层（nodeEntry + resultStore + failingAdapter）
→ 场景 R（持久复用+重启+变体）+ 场景 K（知识方法+零模型+变体）
→ 纠错共存（修订链+有效性投影+四读分立）
→ 全量回归 → 提交 → R12/R13/R14 后新审核轮
```

## 骑轮子检查（frame-bench + 战绩碰撞结论）

**langgraph `put_writes` 键控去重**（memory/__init__.py:497-512）：写以 (task_id, idx) 为键，存储层去重——「入口主动选择存储路径」的生态形态。R 的 resultStore 按同型设计：**结果键 = execution identity（business_request_id + operation_id），存储层裁决复用**。

**hermes 质量门 fail-open**：校验器坏了不能瘫业务——R 的失败探针适配器如果全部失败，宿主应走降级路径而非卡死。测试覆盖。

**SmartResearch ReportChecker**：零 LLM 判定器验证的是事实存在性（引用 ∈ 归档）——K 的知识方法消费同型：方法产出的事实必须 ⊆ 方法声明的输入契约。

**EDPA SPI 归属**：checker 声明 own 哪些 criteria——K 的知识方法声明 own 哪些节点（适用范围），适用性检查 = 节点 ∈ 方法声明集。

## 验证协议（做完后）

1. R：重启后同键重提交 → receipt 与第一次逐字节相等（非重推导）+ 零席位调用 + 适配器探针零触发
2. R 变体四条各一个测试函数
3. K：新任务零模型调用 + 方法产出事实 ⊆ 方法声明契约 + 本任务独立 operation_id
4. K 变体四条各一个测试函数
5. 纠错：修订链四读分立（幂等/有效性/回放/知识检索各自独立断言）
6. 全量回归绿（-race 21 包 + Python + manifest）

## 先验三条（预登记攻击面）

1. **R 的"持久化"边界**：T2 的 resultStore 是内存 map 还是真持久化？——内存 map + 重启=map 清空=必须从 ledger/记录重建。如果 resultStore 只是 map，重启后查不到 → 测试会诚实红。**正确形态：resultStore 从 ledger Events() 重建（record-family 引用存账本 outcome.detail 或新字段）**——但这改机器 schema……最小方案：resultStore 是 T2 层的独立 JSON 文件（不是账本），记录 {op_id → {receipt, facts, references}}——宿主层的持久化面，账本保持精瘦。
2. **K 的"知识方法"载体**：方法 = 结构化 JSON（输入契约+步骤+适用条件）还是 Go 函数？——**结构化 JSON + 解释器**过度设计；**Go 函数 + 声明结构**（适用条件字段+执行函数）最简。方法注册表 = T2 层 map[methodID]KnowledgeMethod。
3. **纠错的"有效性投影"**：per business_request 最新已采纳修订——需要按 business_request_id 聚合多 operation 的状态。**投影 = T2 层函数**（遍历 machine.Events() 按 brID 分组取最新 adopted），不改机器。
