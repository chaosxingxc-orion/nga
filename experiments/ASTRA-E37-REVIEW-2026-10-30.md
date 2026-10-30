# Astra E37 诊断代码复审

指定 `gpt-6-astra` 实际只读复审，进程退出 0。结论限于代码层有条件就绪；无芯片、无远程计划，不能据此开跑。后续仅调整可选物理芯片为 0–5，由父会话核对 diff 并复跑 38＋10 项测试；该资源选择修订不冒称已包含在本次 Astra 快照。

四个冻结文件的 SHA-256 均与 manifest 完全一致。**本次静态审查未发现影响科学含义、资源占用或结果验收的确定性阻断缺陷；结论限于代码层有条件就绪。**

- [chunk wrapper:19](/tmp/nga-astra-e37-review-lkr47hbz/tools/openjev_candidate_chunks.py:19)：按原顺序切行，保留全局 padding/mask；no-op 单块仍经过 wrapper，退出时恢复 forward。
- [driver:139](/tmp/nga-astra-e37-review-lkr47hbz/tools/openjev_batch_diagnostic.py:139)：hooks 不返回替换值且在 finally 清理；no-op、hook 效果以完整序列化预测精确核对。分层峰值与整次峰值明确区分。
- [driver:208](/tmp/nga-astra-e37-review-lkr47hbz/tools/openjev_batch_diagnostic.py:208)：Native 前重验完整冻结闭包并重新进行 metadata selection；恢复回执绑定 plan、实际 request、index、mode、rep、profile。预注册三项对应 **8+4+4=16 forwards/model**。
- [launcher:484](/tmp/nga-astra-e37-review-lkr47hbz/tools/prepare_openjev_batch_diagnostic.py:484)：要求 CPU 全量准备成功证据，并在分配锁内、启动前核验 Docker 与物理占用。短主机检查没有取代运行前全量校验。
- [验收:537](/tmp/nga-astra-e37-review-lkr47hbz/tools/prepare_openjev_batch_diagnostic.py:537)：核对实际退出、EXIT、终态输出哈希、完整回执集合和计数，并重算比较统计；`candidate_batch_admission=False`，E36 失败结论保持不变。

限制：未提供 Native/helper、原始 E31 元数据及远端证据，无法独立确认其实现或真实性；35+10 测试仅按外部通过信息记录，未重跑。当前无空闲芯片、无 E37 冻结远端计划，**本结论不构成开跑许可，也不证明实际 no-op/hook 数值一致性**。