# Astra：递归交接 P2 限定关闭

指定 `gpt-6-astra` 实际只读复审，进程退出 0。以下结论按原文范围使用，不认证模型指标或未审查的链路。

**限定结论：此前“再次交接标签继承”P2 可关闭；本次静态复审未发现新增阻断项。** 冻结 manifest 的三项 SHA-256 全部一致。

- [role_label_hash / check_handover](/tmp/nga-astra-queue-chain-rereview-38heyncw/tools/jeval_reference_queue.py:205)：A→B→C 按角色追溯原始标签；逐级绑定 config 路径及哈希、controller 实际 ID、`exited`、`FinishedAt`、spec、wrapper 和 receipt。必需的 inference 继承链覆盖全部祖先，A 恢复运行或停止代次改变会被拒绝。
- [handover_snapshot](/tmp/nga-astra-queue-chain-rereview-38heyncw/tools/prepare_jeval_reference_queue.py:30) 与 [spec](/tmp/nga-astra-queue-chain-rereview-38heyncw/tools/jeval_reference_queue.py:348)：继承角色保持原始标签，B 新建角色保持 B 标签；实际标签、容器 ID、回执须一致，未见静默接纳其他身份的路径。
- 新代使用独立输出目录；B 的失败终态仍阻止同代 resume，交接路径不删除或覆盖 B 的失败证据。

仅关闭递归交接这一项。42 项通过属父级提供证据，本次未重跑测试或现场验证；auditor 权限及其余未变队列代码不在本次复审范围，不构成全流程部署放行。