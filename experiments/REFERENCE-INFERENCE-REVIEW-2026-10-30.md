# 参考推理执行器的对抗检查与修复记录

日期：2026-10-30。审查身份：继承上下文的可用模型代理，**不是指定 Astra 的实质审查**。
指定 Astra 的多次调用只返回仓库规则确认，没有给出文件级发现，因此仍不能记为 Astra 通过。
本记录保留已经取得的实际反证及修复，避免把审查缺口误写成全部工作停滞。

## 发现与处置

| 问题 | 反证 | 修复与验证 | 适用边界 |
| --- | --- | --- | --- |
| 恢复工具只检查包含目标 chip，没有绑定任务容器 | 同镜像、映射目标 chip 加另一个 chip、执行另一任务的容器能通过旧检查 | 精确匹配物理芯片集合；绑定 container ID、image、command、entrypoint、config／wrapper hash；检查 frozen files；拒绝已成功运行重启。测试覆盖错误任务、额外 chip、替换容器、修改 entrypoint、资源被占、所有权已撤回 | 不修改 E7／E9 已冻结执行文件。后续恢复使用修正后的仓库工具和容器身份回执 |
| 心跳与 finally 可能同时写 STATUS，复用固定临时文件 | 并发写入可使另一线程的 replace 找不到临时文件 | 原子写入改用每次唯一 tempfile；终态写入前 stop + join 心跳线程。8 线程×20 次写入验证无异常、无残留临时文件 | E7 完成时 structured marker、wrapper 和 Docker 均 rc 0，没有观察到该竞态影响其结果；E9 已冻结旧版，完成时须同样三方核对 |
| 独立审计仅验证配置列出的哈希，未证明依赖列表完整 | 原 synthetic 正例只有 test 与 manifest，也能返回 VERIFIED_SCOPED | 已加入 base／checkpoint／code／运行脚本角色的必要依赖核验，缺权重、tokenizer 或源码哈希会被拒绝。18 项审计测试通过；E7 再审识别 58 个必需依赖，66 个冻结文件均校验通过，主要指标不变 | 完整性针对当前原生 Kev LoRA loader 所声明的文件类别；镜像内包以 image identity 和 runtime versions 绑定，并非逐个包文件哈希 |

实质审查还指出现有 synthetic 主指标测试偏重 choice，需覆盖 noul／score、argmax tie 和 ECE 分箱边界。
这些用例已补入，分别验证 typed label 映射、并列取候选原序首项及 0.6 附近浮点分箱边界。
实际中断恢复验证单列 [E10](../wiki/E10-reference-recovery-20261030.md)，不以 CPU 合成测试冒充真实重启通过。

## 与现有结果的关系

E7 是原生 Kev-0.8B 的本地参考推理，不是训练收益。两个 clean accuracy 与发布值一致，Brier／ECE
仍有差异。独立审计范围限于输入／逐项证据和 native/raw clean accuracy、Brier、ECE10、NLL；其他
上游诊断仍不能统称已独立验收。后续修复不回写该次冻结代码，也不把重新运行后的文件伪装成原始证据。

E9 运行时识别到恢复工具缺口，已在原容器仍 live 时记录身份回执。回执明确标为启动后采集，
不冒称启动前证据。镜像具有用于设置 CANN 的 entrypoint，因此正确校验是与回执精确一致，
不是要求 entrypoint 为空。

另一个边界：逐 record 的 canonical JSON hash 排序对象键，不单独区分候选插入顺序；当前完整
suite 字节哈希与配置 stamp 会检测题目文件改序，因此不构成已执行 E7 的已证实缺陷。
未来跨格式迁移或脱离原 suite 的记录复用必须显式绑定候选顺序，不能把无序对象哈希当作完整语义身份。

## 2026-10-30 16:53 UTC 追加：审查身份与温度绑定

本次指定 Astra 的有界只读任务仍只返回仓库规则确认，没有实际文件发现或验收意见；不记为实质审查。跟进任务遇到代理线程数量限制，未得到补充评审。该限制不阻断其他参考实验，但 Astra 验收要求仍未满足。

主会话复核发现 `verify_reference_kev_devtools.py` 的温度取自 `ENVIRONMENT.json`，检查有限、正数并核对预测／报告的一致性，未直接独立读取冻结 `head.pt` 的温度。因此独立算术验收本身不能单独证明“确为 checkpoint 发布温度”。冻结 driver 通过原生 `Checkpoint`、无温度覆盖的 `LoadOptions` 加载；还需核对 checkpoint 元数据。

本次使用现有 CPU 容器、`TORCH_DEVICE_BACKEND_AUTOLOAD=0` 和 `torch.load(..., map_location="cpu", weights_only=True)` 独立读取三个 `head.pt`，随后核对它们仍匹配 E22 启动前冻结哈希，温度分别为：

| 模型 | checkpoint 温度 | E22 运行记录 |
| --- | ---: | --- |
| Kev-0.8B | 2.3510958125672174 | 相同 |
| Kev-4B | 2.406050072164233 | 相同 |
| Kev-9B | 2.193649959389252 | 相同 |

三个 base ID／revision 也读出为对应 Qwen3.5 Base 尺寸；没有发现本次采用错误温度。该复核是对已执行运行的补充证据，不回写原配置或冒称启动前新增检查。后续验收器应把独立 checkpoint 元数据绑定纳入自动检查；现有 `VERIFIED_SCOPED` 仍不是完整防伪或实质 Astra 放行。
