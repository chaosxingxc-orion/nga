# 修复轮范围框定（2026-11-03 深夜）：P1×2 认领 + E3 control 事件类别

> 范式：xuefanfan 八段（本文件）。写码纪律：SETools——先看本仓已过闸先例（adopt.go/evidlog.go 的 doctrine 注释形态、错误返回形态），写完自检（Go 面：注释与代码间距、无 unused import、声明顺序、错误路径 seq 回滚一致性）。
> 出处：两个 P1=邢超评论②（197847238）+我方认领（issue#1 197976917）；E3=第三轮空白碰撞（10 号 §五）+对账（11 号 §二.2）；T2 教义收敛=11 号 §四.6。

## IN

1. **P1-1 umask**：adopt.go 与 evidlog.go 的首写权限分支——新建 0600（删 Chmod 加宽动作，回归 CreateTemp 自身默认）、既有保留、Stat 非 NotExist 显式报错（ENOTDIR 可作便携探针）。收编对方探针 TestNGAReviewFirstWrite 形态为永久测试（syscall.Umask 设 077 断言 owner-only）。
2. **P1-2 断尾 T2 教义收敛**：ledger.ParseLines/LoadDocument 回传 tornTail 信号；adopt.Open 记忆（TornTail() 访问器）；append 单闸拒绝一切变更（含 Dispatch 早闸专用报文）——拒写即证据保全（重建永不发生）；TORN-TAIL DOCTRINE 注释重写（R9 F2 分叉退役=收敛到 evidlog 单一教义）。收编 TestNGAReviewTornDispatchTail。
3. **E3 control 事件类别**（commit 3）：账本内第三事件族 control（14-A4 拒收/非法转换拒收/未知 op 拒收入账），无 Idempotency（replayEvent 现有 nil-skip 自动跳过）、不进状态转换、不进幂等；四面联动=ledger schema + Go ledger.Errors + Python ledger.py 镜像 + 一个 valid 夹具。

## OUT

- 授信夹具语义修正（P3）——业务语义面，挂 pending-confirmation 标记后另行批（历史覆盖期归 business-owner-credit，无权代持选值）
- C4 排序契约——仅设计注记（本档 §骑轮子），实现挂宿主侧
- 0640 保持面行为不变（对方实测通过，零改动）
- 不动 evidlog 断尾教义（已合规：记忆+拒写+拒绿）——只收敛 adopt 侧
- 不新增权限配置 API（审计可读=部署方显式 chmod，组件不建配置面）

## 复用清单（不重设计）

evidlog.go:71 tornTail 字段+167 拒写+328 拒绿=adopt 侧收敛的目标形态；evidlog loadLines(:78) 回传三元组=ParseLines 签名变更先例；14-A4 grantsCover 复检=control 事件的触发面；conflict 事件入账先例=control 事件的语义同型。

## 依赖 DAG

```
P1-1（adopt.go+evidlog.go 权限分支，互不依赖）
P1-2（load.go 签名 → adopt.Open/append 闸 → doctrine 注释 → 测试）
E3（ledger schema → Go Errors → adopt 拒绝路径写事件 → Python 镜像 → 夹具）
回归：go test -race ./... → Python 八组 → manifest --check → 三 commit
```

## 骑轮子检查（frame-bench 碰撞·支持项）

| 修复项 | 生态支持项（实机核验） | 判定 |
|---|---|---|
| P1-1 0600 默认 | codex 敏感文件全部 0600 且带权限断言测试：OAuth token（rmcp-client/oauth.rs:1134/1171，测试 :1428/1455）、企业凭据（enterprise_generation.rs:52）、私钥（network-proxy/certs.rs:697/981）、控制 socket（unix_socket.rs:34）；**非敏感 installation_id 才 0644**（installation_id.rs:28）——按内容敏感度分类；openclaw 运行时目录 mkdir 0o700（runtime-artifacts.ts:138/154/190） | 支持。我方账本/取证日志含业务标识/查询选择器/证据引用=敏感类。生态与「显式配置放宽」同构（codex 不替部署方放宽敏感件） |
| P1-2 证据保全+信号显式 | codex 会话恢复对损坏行 skip+parse_errors 计数+warn+**回传调用方**（rollout/src/recorder.rs:1142-1198），append-only 文件字节永不重写；I/O 级损坏=InvalidData→Fatal 带修复指引（session_rollout_init_error.rs:52-56）；列表/索引另有 ScanAndRepair 降级模式（列表可降级、恢复严格） | 半支持：证据保全+信号显式=生态实证；**拒变更比 codex 严格**——由我方契约第一性正当化（外部效果许可永不重发 vs 会话史跳行仅降级上下文），诚实标注为超出生态的必要严格 |
| E3 control 事件 | codex 审批拒绝=一等协议事件：ExecApproval/PatchApproval{id, turn_id, decision: ReviewDecision}（protocol/src/protocol.rs:808-830）——拒绝随事件流持久化 | 支持。被拒尝试=一等持久事件，非丢弃返回值 |

**4-lens 总判**：Simplicity——P1-1 删一个加宽动作、P1-2 删一种教义、E3 不新增持久面（全部净简化）；Consistency——P1-1 消内存域/磁盘域双姿态、P1-2 消 adopt/evidlog 双教义、E3 消「conflict 入账而 14-A4 拒收无痕」的不对称；Bearing——三个对方/新探针全部红→绿可机械验证；Fidelity——doctrine 注释、L14 裁决记录、issue#1 E3 表述三处声明与现实对齐。
**singularity 总判**：三修复均堵可达坏状态（umask 077 可读面/许可重发/无审计拒收），均不引入新失败路径——唯一新约束「损坏文件需外部修复后 re-Open」是显式恢复流程非隐式陷阱（Open 成功只读可用，写路径拒）。无可达奇点。

## 验证协议（做完后）

1. 三个新探针修前红修后绿（umask 077 断言 owner-only；torn-tail 后 Dispatch 不再 dispatched 且文件字节不变；拒收后账本含 control 事件）
2. 既有测试全绿：go test -race ./...（20 包）、Python validate/ledger/adoption/judgment/release/replay/compose/evidlog 八组 + _suite.py --self-test、corpus_manifest.py --check
3. 变异自证：P1-1 模式分支退化恒 0644 → 探针双红；P1-2 撤 append 闸 → torn 探针红
4. 提交三笔（P1-1 / P1-2 / E3）+ doctrine 注释与 L14 台账退役记录同步

## 先验三条（含预登记攻击面）

1. **断尾闸的粒度**：拒「一切变更」可能过宽——MarkUnresolved（对已知事实的记录）也拒？预登记：拒——损坏文件上任何写入都可能覆盖丢失行的语义，全量冻结是唯一不假装知道丢了什么的姿态（邢超：「不应假装能只隔离某个 op」）。
2. **control 事件的伪造面**：外部文件伪造 control 事件注入账本？预登记：checkLoaded 经 ledger.Errors 校验形状（字段齐全+status∈封闭集），且 control 不进状态/幂等——伪造价=可注入噪音审计行，无控制语义增益；与 conflict 同风险级，可接受。
3. **LoadDocument 签名变更的调用方遗漏**：除 adopt.Open 外若有隐藏调用方（测试直调），编译期暴露——Go 强类型保底。
