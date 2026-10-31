# 对齐债务清偿批：范围框定（2026-11-01）

批 = 碰撞回应（issue #1 评论）承诺的 festival 侧单方可做项：provenance 重锚（A1）+ 过程留档（A5）+ 漂移显式化（B1-B3）。范式：xuefanfan 八段（本文件）；写码纪律：SETools 精神——先看本仓已过闸先例（description 行文形态、README 表格形态），写完自检，纯文档编辑零机制新码。

## IN

1. **A1 provenance 重锚**：四份增长层 schema（adoption/event-ledger/judgment/release）的 NGA 引用从已删编号文档重锚到现行文档具名节。映射表（元碰撞已逐条核对）：
   - `12号 §1-§3` → `07 §3 命令段 + §8 四模式表/retention 段`
   - `13号 §5` → `07 §6 变更表 + §9 + M05`
   - `14号 A3/A4` → `07 §8 信任段 + §3 authority provider 端口`
   - `14号 A5` → `07 §3 命令段 + M03/M07/M08`
   - `15号 B4` → `07 §3 Task service 行 + §7 Idempotence 契约区`
   - `总设计 §6/§6.1` → `总体设计新文 §2 + 07 §10 夹具约定 + P4/P5`
   - `总设计 §7.2` → `07 §6 对象表`
   - `P5` → `总体设计新文 P5`（五维原文在此）
2. **无出处字段的显式记录**（不删不静默）：judgment 的 owner 责任族（owner/review_authority/effective_scope/change_rationale/impacted_links）在旧 §6.1 有具名出处、新文档无落位句（碰撞回应 L2 已提议恢复）——description 记「出处为旧总体设计 §6.1；现行 07 提案合并损耗（issue #1 碰撞回应 L2）；待 NGA 恢复，语义承重不删」。
3. **B1**：event-ledger versions description 增注「P5 五维（总体设计新文 P5）vs 07 §6 J1/D1 四维——evidence 是否版本维度属未决裁决，festival 按五维实现」（碰撞回应 L3）。
4. **B2**：release rollout description 增注「07 §6 为 hold/migration/reevaluation 四词散文，reevaluation 为三枚举外新词，待 NGA 裁决」（碰撞回应 L4）。
5. **B3**：schema/README 增「状态词汇分层映射」段：festival 事件事实态（adopted/reused/conflict/dispatched/unresolved/completed/failed）↔ 07 命令结果报告态（committed/duplicate/conflict/accepted/pending/rejected/unresolved）；rejected 永不入账本（机器答案词汇≠事实）；reused≈duplicate、adopted≈committed（碰撞回应 E3）。
6. **A5**：replies/2026-11-01-festival-collision-response.md 挪入 agent-festival/docs/ 并提交（过程为证；含三处外部证据已在发布前实证校验的说明）。

## OUT

- 不改任何 schema 语义字段/枚举/required（只动 description 与 README——lockstep 测试剥 description 比较，语义面零变化）
- 不动基座三 schema（冻结，已核无 NGA 编号引用）
- 不删 owner 责任族（语义承重+已向 NGA 提议恢复——「不静默保留」= 显式记录出处状态）
- 不做件6/夹具格式文档/六问回复（后续批）
- 不重锚正文引用为「新文档说 X」的语义改写——重锚只换指针，新文档缺失的语义（如「不重新仲裁」）以「07 未落位，festival 按旧 12 号语义实现」显式记录

## 复用清单（不重设计）

出处映射表（元碰撞产出）直接用；README 表格/description 行文本仓先例形态；零新代码。

## 依赖 DAG

```
四 schema description（互不依赖）→ README 词汇映射段（引 B1/B2 记录）→ docs/ 留档（独立）
```

## 骑轮子检查

无机制层新码；纯文本编辑。SETools 自检点：description 单行散文先例、README 表格列形态、无 unused（无代码）。

## 验证协议（做完后）

- 双侧 oracle 全绿且计数钉零变化（9+26/2+5/2+19/2+9——语料不增不减）
- lockstep 短语钉仍绿（剥 description 比较 + docstring 短语在 ledger.go/ledger.py 不动）
- go test -race 14+ 包全绿
- grep 复核：四 schema 无残留旧编号引用（12-replay/13-nga/14-A4 数字形态/v0.2 §5）

## 先验三条（含预登记攻击面）

1. 【攻击面 α】重锚的语义漂移：锚到新节时把新文档的语义损耗当作已确认——防线：重锚只换指针；新文档缺失语义以「未落位+按旧语义实现」记录，绝不借重锚静默改语义
2. 【攻击面 β】description 膨胀为散文论文——防线：每处增注 ≤3 句；详述只在 README/docs
3. 出处映射表是给 NGA 的共建提议物——festival 侧先按它执行，若 NGA 修正映射，重锚成本=再一轮文本编辑（预期内的 cheap）
