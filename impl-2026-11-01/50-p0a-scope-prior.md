# 50 · P0-A 范围框定（2026-11-07）：逾期语义恢复——事件时间代数与六格判定真源

> 范式：xuefanfan 八段（同 36 号）。出处：邢超 198789782 §二（撤回要求）+198789653 反例 1/2+
> 我方 P3 考古（45 号 §2.3）+ 46 号 P0-A 设计。写码纪律：SETools 精神（36 号 §头注）。
> **判定真源冻结**：本文 §三 六格矩阵的期望列自原始业务规则独立翻译（翻译依据逐格留档），
> 冻结于任何 Go 实现之前——W1 的病（从改窄实现反推期望）的制度化防线。

## 一、IN（落点+形态+度量+红探针）

### 1. 本体变更（夹具 v1.1.0，`schema/examples/judgment/valid/judgment-spec-credit.json`）

- **term「overdue」重定义**：现行定义把「>3 月」吸收进术语本体（P3 病根）——改为「an unpaid
  obligation past its due date for at least one full month（台账最小粒度）；**持续时长与发生新近度
  是每条事件的自带属性，不是术语定义的一部分**」；
- 两谓词各归其位：**全局否决**（rule 0，既有）＝任意事件 durationMonths > 3（不限时间）；
  **上带干净前提**（rule 1，恢复）＝无任意时长事件落在近六月窗口内（monthsAgo ≤ 6，两端含）；
- rule 1 coverage 改述（明示「任意时长——近端一月逾期即挡上带」）；examples 增反例 2 格
  （近期短期→on_undefined_rule，不补写成 deny）；spec_version 1.0.0→1.1.0。

### 2. 事件结构（`e2e_test.go`）

- `overdueEvent{months, yearsAgo}` → `{durationMonths, monthsAgo int}`（持续/新近分离——
  yearsAgo 连「上月 vs 八月前」都分不清是反例 1 的输入表达缺陷本体）；全部字面量迁移
  （yearsAgo Y → monthsAgo Y*12；编译器找全迁移点——字段改名零遗漏的机械保证）。

### 3. 双实现互证（S1 替身与验证席位**各自**实现窗口谓词，不共享代码）

- `s1Judge`（e2e_test.go）：上带分支加窗口检查（硬编码 6，注释引 t1Spec 冻结文本
  "no overdue in the last six months"——与既有 ">3" 硬编码同纪律）；窗口不干净且否决未触发
  → **on_undefined_rule**（上带前提不满足=无规则覆盖，不自动 deny——邢超原文）；
- `verify`（verifier_test.go）：新增 `anchorWindowMonths(spec)`（从 time_window 文本解析
  「six」→6，anchorVetoMonths 同款 Sscanf 纪律）+ grant-50000 判定的窗口核验；
  **顺手修理由措辞**：现含「the only conforming verdict is deny」方向性表述（夏纪律 2 违例，
  49 号回执已认）——改为「违反规则 X+收到判定 Y 不符」（违规事实，不写结论方向）；
- R43 m-2「yearsAgo 装饰性」声明随之过时（monthsAgo 被席位消费）——改注。
- **互证设计**：两实现独立（S1 读 t1Spec 冻结文本/席位锚定夹具文本），六格表对两者分别断言
  且必须同红同绿——分叉即红。这是「独立实现+同一真源」形态（夏 1.4 互证/邢超独立性维度）。

### 4. 六格+边界测试（新文件 `p0a_window_test.go`）

- §三 矩阵逐行（双断言：s1Judge 输出 + verify 对 grant-50000 的裁定）；
- 反例 1（近期短期）转正 = 邢超探针 TestNGAReview_RecentShortOverdueMustNotPassUpperGrant
  的正式收编（引用其评论号）；
- **术语锚定探针**（E3 盲区封口）：断言夹具 overdue 定义**不含**「three months」（否决时长
  不得活在术语里）+ rule 0 coverage **含**之 + time_window **含**「six」——三方各锚各位；
- **千余输入扫描重生成**：输入域 durationMonths∈**1..6** × monthsAgo∈0..30 × asset∈**{0,5,35}**
  （全组合 6×31×3=**558** 行 × 双谓词结果；R67 M-3 纠正：原述 0..6/0.5/651 行失实——dur=0 不是事件（term 最小粒度 1 月，无事件=空 onRecord 形）；assetMillions 为 int，0.5 不可表达。实际生成器与入库 tsv 以 1..6/{0,5,35}/558 为准），产物**全量入库**（testdata/p0a_scan.tsv：生成器
  参数+每行输入+两谓词结果）+ 计数断言（sortedKeys 确定性）——**窗口面独立可达性恢复的
  机械化证明**（R37「零可达」在新本体下为假，计数差>0 即证）。
- 红探针（注释「Mutation probe:」惯例）：s1Judge 撤窗口分支→cell1 变 grant-50000（红）；
  verify 撤窗口核验→cell1 裁定 ok（红）；锚定探针撤→术语回吸收不红（红）。

## 二、OUT

- t1Spec 文本**不改**——其 rule 1 宽读（任意逾期挡上带）在新本体下由 s1Judge 实现，四处分叉
  （t1Spec/夹具/S1/席位）自消（45 号 §2.3 的分叉从夹具侧解决）；
- E6/DispatchIfCurrent、作用域生效权威（P0-B/C）——另批；
- 真实提取来源三臂（P2-F）与 T1-run3（P2-G，用户启动）；
- verify 拒绝持久审计面（P1-E，含双字段拆分的存储侧——本次只改理由字符串措辞）。

## 三、六格判定真源（期望列冻结——翻译依据逐格留档）

原始业务规则（邢超 198789782 §二原文）：「上带授信前提：资产 >3000 万，且过去 6 个月没有
贷款逾期。全局否决：历史存在持续超过 3 个月的逾期，即拒绝授信。」翻译：**上带干净**＝
∀e: ¬(e.monthsAgo ≤ 6)；**否决**＝∃e: e.durationMonths > 3。资产固定 35（上带相关带）。

| 格 | 输入事件{dur, ago} | 期望 s1Judge | 期望 verify(对 grant-50000) | 翻译依据 |
|---|---|---|---|---|
| 1 近期短期 | {1, 1} | **on_undefined_rule**（上带不满足，否决不触发——无规则覆盖；**不是 deny**） | **reject**（rule 1 前提违反） | 反例 1 转正；邢超「余下按未覆盖情形处理，不能补写成必然 deny」 |
| 2 历史短期 | {1, 24} | grant-50000 | ok | 两谓词均不触发（窗口外+时长≤3） |
| 3 近期长期 | {4, 2} | deny | reject（rule 0 违反） | 否决触发（时长>3 不限时间） |
| 4 历史长期 | {4, 24} | deny | reject（rule 0 违反） | 反例 A（邢超原始）——否决无界 |
| 5 无逾期 | — | grant-50000 | ok | 阳性对照（新谓词不伤健康流） |
| 6 覆盖不足 | 历史台账窗口<声明 | on_missing_evidence 路由（E2 面） | 判定前路由，非 deny | E2 既有；「六月材料≠历史无逾期」 |
| 7 边界 in | {1, 6} | on_undefined_rule | reject | 夹具 time_window「both ends inclusive」→ ago=6 在窗内 |
| 8 边界 out | {1, 7} | grant-50000 | ok | 窗外（>6）且时长≤3 |

**边界语义**：monthsAgo ≤ 6 皆窗内（inclusive，夹具原文）；durationMonths > 3 才否决
（=3 不触发——「超过 3 个月」）。格 7/8 由 singularity 反向风险 ② 补入（见 §四）。

## 四、frame-bench 碰撞（4-lens + singularity——支撑项与反向防线）

**支撑项（骑轮子检查）**：
1. **判定真源先行**：state-matrix.tsv 模式（预期断言先于实现冻结，M01-M10 同构）——本档 §三
   即 P0-A 的 state-matrix；六格=「构造初态→跑→验预期」同形态；
2. **评审新发现=表缺行**：REVIEW-LEDGER 收敛判据——新发现补行即收敛，不从实现反推期望
   （W1 的病恰是把实现输出当期望）；本批若审出新格，补格进 §三 即收敛；
3. **判定与实现分件**：run-matrix.sh 与 gen-maps.sh 分离——同构于六格表（p0a_window_test.go
   的表）与被测件（s1Judge/verify）分离；
4. **确定性跑表**：sortedKeys 键序（langgraph 先例，36 号 §骑轮子）——扫描重生成按
   (duration, ago, asset) 序输出，计数断言确定性。

**反向风险（singularity——严格避免，逐条防线）**：
1. **反向推导复发**（实现先写、期望从输出抄）→ 防线：§三 已冻结于 Go 之前；实现期任何
   期望变动必须回改本档并留「为何改」一行（表是真源，不是测试的镜子）；
2. **边界含糊**（ago=6 窗内？dur=3 否决？）→ 防线：格 7/8 已钉（inclusive/超过=严格大于），
   夹具文本为据——不许实现期默断；
3. **双实现变复制**（s1Judge 与 verify 共享谓词函数→「互证」变「复印」，P3「三方一致断言
   覆盖面小于名称」同族）→ 防线：两实现物理分文件、阈值来源不同（t1Spec 冻结文本 vs 夹具
   锚定解析），六格表分别断言——分叉即红；
4. **术语回吸收**（未来修夹具时又把时长写回 term）→ 防线：术语锚定探针（定义不含「three
   months」+rule 0 含之）常驻。

## 五、验证协议（做完后）

1. 六格+边界 8 行全绿（双断言）；反例 1 探针（收编形）绿；
2. 红探针三枚先红后绿（撤 s1Judge 窗口分支/撤 verify 窗口核验/撤术语锚定——各自行红）；
3. 扫描重生成：testdata 全量入库+窗口面独立可达计数 >0（R37「零可达」被机械证伪）+确定性
   复跑一致；
4. 全量 `go test ./... -race` 绿（字段迁移编译期全覆盖，无存量 yearsAgo 残留——grep 零）；
5. 反例 2/3/4（邢超其余探针）不受损——它们属 P0-B/C 范围，现状 FAIL 保持（不假装修复）。

## 六、先验攻击面（预登记）

1. **字段迁移的语义陷阱**：yearsAgo Y→monthsAgo Y*12 的乘法迁移若有一处手滑（Y+12/Y*10），
   格 4 的 24 会变错值——防线：迁移用 sed 全量+编译器找漏+格 2/4 的 24 值断言；
2. **s1Judge 窗口检查的位序**：必须在否决之后、missing-evidence 之前还是之后？t1Spec 优先序
   （L23：否决最先）既有——窗口检查属 rule 1 分支内部，位序天然确定（进上带分支才查）；
   但若放在 missing-evidence 前，C8 用例（缺报告+历史逾期）行为不变（否决先拦）——需过
   既有 T0/T1 全量回归确认零漂移；
3. **夹具 examples 增行触发 suite 计数**：correctness_probe 的 examples 计数断言（R24 m-1
   既有计数）会因新增 example 行 +1——同步改计数或改断言形态，留一行说明。
