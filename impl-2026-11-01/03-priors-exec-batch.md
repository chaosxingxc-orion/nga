# 执行批先验：范围框定（2026-11-01，worktree ~/nga-impl-wt）

批 = 夏裁决落地 × GEPA 遗留执行项 × spike 收编，七件按依赖排序。范式：xuefanfan（先验→碰撞→编码→空白循环）。

## IN（七件，依赖序）

1. **E1 计数第四副本收编**（1h）：conformance-fixture-format.md 全部计数行 vs 实测对账修复（release 2+9→3+14/补 replay 行/170→195）；**机生成方案**：从 examples 目录派生计数表（对拍 pi 先例），消灭手抄第四副本
2. **E2 go.mod 域名化**（0.5d）：festival-dev/go → github.com/openjiuwen/agent-festival/go（或等价可 go get 路径）+全 import 更新+打包验证（go mod tidy/go build/gateway 检查）
3. **E3 0.2.0 中性错误键**（1d）：ledger 代码族 11 去重短语→中性错误键（error_key 字段或错误码）；双侧（Go ledger.Errors+Python ledger.py）；PROSE 钉全部迁中性键（17 钉/11 短语——GEPA spike 实测清单）；夹具 _expect_match 同步
4. **E4 奇数孪生夹具**（0.5d）：9007199254740993.0（奇数 float 语法）valid 夹具——钉 float64 判定域（RFC 8785 规范级先例/zcode golden 向量形态）；格式文档§3 判定域声明
5. **E5 spike-java 收编**（0.5d）：~/nga-gepa-wt/gepa-explore/spike-java → agent-festival/examples/java-consumer/（含 README：跑一次的入口）
6. **E6 件7 spike：取证记录族**（1d）：go/internal/evidlog——append-only 取证调用日志（框架层自动记录形态的最小版：类型+最小 schema+JSONL 耐久+差集告警函数）；夏方案的机器面预研（不做 S2 集成——那是对方半场）
7. **E7 受控交接边文法先验**（1d）：三边类型+三属性的设计文档（0.2.0 执行图输入）+evidence_gap 产出类型进判断规格的 schema 增量提案

## OUT

- 不做 A/B 双臂实测（依赖 E3 完成，另批）
- 不做 S2 集成/调查专家任何实现（对方半场）
- 不改七件已收卷件的语义面（E3 是增键不是改语义；错误键向后兼容——老钉仍命中）
- 不动冻结基座（V0 四 schema+三 Go 包）
- 不发任何对外物（回复已发的除外；E7 是提案不是发出）

## 骑轮子检查

E1 机生成=shell/python 对账脚本（无新库）；E2 纯路径改名；E3 中性键=字符串字段（无新机制）；E4 纯夹具；E5 移动+README；E6 JSONL append-only（复用件4 的耐久形态先例：temp+rename/断尾容忍——但独立实现不引 adopt 包，取证日志无状态机）；E7 纯文档+schema 提案。

## 预登记攻击面

- α：E3 错误键与现有 PROSE 钉的双轨期漂移（键改了钉没跟）
- β：E2 路径改名破坏现有夹具/go test 的 CWD 探针（SchemaPath 相对路径）
- γ：E6 取证日志与件4 账本的职责混淆（词义碰撞复发——包文档必须显式分家）

## 验证协议

每件：双侧 oracle+go test -race 全绿+计数钉同步；批尾：空白子智能体 4-lens+singularity 循环至 3 连 0B0M 或 10 轮。
