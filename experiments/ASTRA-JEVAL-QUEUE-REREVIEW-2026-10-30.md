# Astra queue 修订复审

2026-10-30。指定 `gpt-6-astra` 实际只读审查，进程退出 0。首次接续获限定范围正面判断；仍有 auditor 权限绑定、再次接续标签继承两项 P2，修复后再部署。空闲芯片查询成功尚未实测，不作全闭环放行。

三份源码的 SHA-256 **均与 manifest 完全一致**。首次接管精确模型/finisher IDs 的代码路径未见阻断，但完整闭环仍有两项 P2：

- **P2：新 auditor 仍漏验资源权限。** [audit_jeval_inference_hardened.py:339](/tmp/nga-astra-queue-rereview-23fdzi08/tools/audit_jeval_inference_hardened.py:339) 只比较 Binds/Devices，遗漏 `Privileged`、`DeviceRequests`、`DeviceCgroupRules`、`Mounts`。静态反例：其余校验字段保持一致，仅令实际 `Privileged=True`，该资源检查仍通过；队列对 probe 的检查（queue:344）也未补齐。因此不能据此证明 probe 未获 chips6/7 访问权限。**修复：对 inference、probe、finisher 统一执行完整资源权限绑定。**

- **P2：再次交接不支持继承的旧标签。** [prepare_jeval_reference_queue.py:56](/tmp/nga-astra-queue-rereview-23fdzi08/tools/prepare_jeval_reference_queue.py:56) 要求模型标签等于直接前任 plan 哈希。A→B 接管保留 A 标签，因此 C 以 B 为前任时必被拒绝。实际相关触发路径是：查询失败→queue:623 写终态→preparer:140 拒绝同代 resume→尝试新代交接。**修复：逐角色继承并验证原始标签归属，同时核验直接前任已停止；保留全部失败证据。** 当前拒绝资源变更本身是正确行为。

**结论：首次 CPU 接管可限定 GO；完整资源审计及再次交接恢复不能无条件 GO。** F2 的 11257 条回执重算、F3 的按代 EXIT137 审核归档，在静态路径上成立。

未执行测试或现场查询；40 项测试、CPU 恢复和 DCMI busy 均属用户提供证据。空闲 chip1 查询成功仍未验证；F4 不在本次范围。