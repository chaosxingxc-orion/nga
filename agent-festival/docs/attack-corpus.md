# 攻击语料（单一真源——判据 × 攻击用例 × 机器面）

> R57 C4' 落地（收敛元分析 v2 的 R2/R3/R4/M9 为语料+回放+植入三件）。
> **本文件是攻击语料的单一真源**：pattern doc 的机器面映射已并入此处（模式文档只留指针）；
> 每轮空白子 prompt **引用本文件，不转抄**（m-4 转抄漂移的教训）。
> 协议文本（清偿证明协议/修复义务协议）的单一真源在 docs/minor-ledger.md 头部。

## 一、机器面清单（M1-M7）

| id | 面 | 命令（cwd=agent-festival，M4/M6 cwd=go） | 杀什么 |
|---|---|---|---|
| M1 | registry-gate | `python3 tools/guard-battery.py --check` | 未注册守卫 / spec 锚漂移 / **消费者锚漂移（调用方绕过守卫路径——R58 M-5）** |
| M2 | battery | `python3 tools/guard-battery.py` | 守卫退化十形（探针对形式无关红面的回归）+ 编译检查（BROKEN≠红）+ **基线 vet（不可达死代码——第三机检路径，R58 采纳）**；**真树零接触（副本化——R58 M-3，并发互踩面结构性消解）** |
| M3 | battery-selftest | `python3 tools/guard-battery.py --selftest` | 电池自身面（A 未注册/B 锚漂移/C 良构/D 破损不计红/**E 消费者计数漂移/F vet-dirty baseline-red**） |
| M4 | settlement-audit | `go test ./internal/settlement/ -run 'TestSettlementAudit$'` | token 在场/语法/**围栏惰化**/执行失真/陈旧（内含 M1-M3、M5、M7 的 token 重跑——**回放=纵深非最小集**） |
| M5 | audit-tamper | `python3 tools/settlement-audit-tamper.py` | 审计本体的篡改面（违规台账红/对照绿；R58 增 letter 条目面+围栏面） |
| M6 | audit-selftest | `go test ./internal/settlement/ -run TestSettlementAuditSelfTest` | ledger 解析器面（进程内；R58 增 letter-条目面+围栏面） |
| M7 | seed-anchors | `python3 tools/seed.py --check-anchors` | 植入目录锚漂移（开轮面——锚失配开轮即响，不再等有人手跑 seed；R58 采纳 S3 提案） |

**机械回放（开轮保留率门）**：`python3 tools/replay.py` —— 七面（M1-M7）全 PASS 才开轮。
replay 是编排件（自身无新检查，红面在组件工具里、各有 ledger token）；其组件清单若被
删面，本表（M1-M7 七行）即对账基准——人工对表是声明的边界。

## 二、判据 × 用例映射（20 行——机器面行给命令，审查面行给出处+探查动作）

> R58 增五行（20 行）：letter 闸/围栏=文档/调用方绕过/两个下轮待实现项。

| 判据 | 面 | 攻击用例 |
|---|---|---|
| 构造即断言 | 审查 | R47 B-1——挑一个 helper，把被断言字段与 helper 写死的字段逐一对（grep 探查） |
| 观测面失明 | 审查 | R48 M-1——失败成因经哪条路径读什么字段？断言面能观测到吗（走读） |
| 可达性声明须有代码锚 | 审查 | R48 M-2——「only yields」「cannot」逐字找实现支撑（grep+走读） |
| 守卫谓词完备性 | 审查 | R50 M-1/R51 M-2——被测件定义式每条次序逐条对表（表驱动核对） |
| 守卫自身需红面 | M1+M2 | 删检查→什么红？电池各形即答案 |
| 连接层是惯例层 | M2 | `guard-battery.py` 十形（C1' 后=探针对，形式无关） |
| 修恒真的替换件自带新恒真 | M2 | `--only ignore_param` / `--only hardcoded_nil` / `--only hardcoded_err` |
| 复制式归位不是归位 | 审查 | R53 M-1/R54 M-3/R55 M-1——声称已删的原文 grep 唯一命中核对 |
| 0.2.0 门错挂 | 审查 | R55 m-1——测试文件内签名改动 ≠ schema 依赖（diff 分辨） |
| t.Fatal 期望不可断言 | 设计面 | C1' 错误返回式（探针对）——新守卫禁 tFatal 形红面声明 |
| 架构批声明同受突变协议辖 | M4 | doc 里的红面声明实测过吗（审计 token 语义） |
| 第七形：早退死代码 | M2 | `--only seventh_early_return` |
| 形态钉的开放集 | M1+M2 | 新守卫必须注册 spec；文字钉/AST 钉禁用（要钉就换观测面） |
| 声明失实是最大族 | M4+审查 | 「已做/✅/已存/已推」当轮机械核验（台账级=审计；doc 级=审查） |
| 声明先于调用 | 审查 | 说「已存/已提交/已跑」时工具调用返回了吗（自检动作） |
| letter 条目在场闸 | M4+M5 | R58 M-1——`- **M-A**` 形无 token 条目必须红（bulletRe 放宽 `[BM]-[A-Za-z0-9]+`；tamper LETTER 面+selftest 面） |
| 围栏=文档 | M4+M5 | R58 M-2——围栏内 `[mutation-proof: …]` 不是 token（presence/grammar 双跳过；tamper FENCE 面）；**R59 B-1/R60 B-1 增**：围栏内活格式真命令无 retired-by=响（fence kind）、`<` 前缀真命令不豁免（形状封闭：仅单 `<name>` 占位符+紧随箭头）、violation 携带条目 id |
| 调用方绕过面 | M1+审查 | R58 M-5——调用点换裸构造器全包绿（亲手实证 0.068s）；consumers 锚计数漂移=--check 红 + docstring/模式文档边界声明（新调用点须同 diff 更新锚或声明绕过） |
| 返回已检被改流 | 审查（待电池形） | R58 S3 提案采纳——「检查后改写返回流的 Outcome」今日无电池形；审查面核对 AcceptsHealthy 投影含 seq/type/outcome 三字段（丢 Outcome=ood-loose-assert 本体） |
| E7a② 负孪生 | 审查（待实现） | R58 S3 提案采纳——伪造 pin 的手工 control 事件必须被 Open 以 ATTRIBUTION_DIVERGENCE 拒；今日唯一红面在 cmd/ledger 语料套件，e7 无本测（下轮补） |

## 三、植入标定（seed.py——泛化率测量，每 ~3 轮一轮）

**克隆式植入**：缺陷打在**一次性副本**上（树零接触——忘恢复结构性不可能）；manifest 写在克隆**旁**
（克隆内不可见；旁路文件可枚举——有效性靠审查者不知情+诚实，非「不可读」——R58 m-2 真实边界标注）。
R58 标定实证：仓内 seed 族描述可被审查者引用为证据——OOD 检出带**分布内成分**，泛化率按上限读；
OOD 植入优先取本 campaign 之外模式（本轮池中无外族，如实声明）。

```
python3 tools/seed.py --list                                   # 目录
python3 tools/seed.py --family <id> --out <dir> --keep        # 植入+留克隆派审查
python3 tools/seed.py --family <id> --out <dir> --verify      # 植入+证预期色+清理
```

| 族类 | 色 | 验证语义 | 现有目录 |
|---|---|---|---|
| `battery:<form>` | RED | 克隆内探针红（机器可检——测审查者是否跑机械检查） | 十形全可 |
| `ood-*` | GREEN | 全套件 -short 仍绿（**CI 抓不到、只有审查能抓**——泛化探针） | ood-skip-subtest（静默跳测）/ ood-loose-assert（断言静默变弱）/ known-doc-drift（doc 越权声明——已知族但 prose 无机器面，如实标注） |

**检出率记账格式**：`## R<N> 标定（植入 a+b，检出 x/y）`——泛化率是**近似度量**
（oracle 递归不消解：分布外≠真值；植入者与审查者同源时是分布内测量——诚实声明）。
OOD 植入优先取本 campaign 之外的模式（SETools/agent-solution 的 B/M 族）。

**锚纪律**：injector 锚与 battery/token 锚同构——失配=verify 红=更新目录，陈旧响亮不静默。
