# Astra：v6 waiter 与 auditor 权限绑定限定放行

指定 `gpt-6-astra` 实际只读复审，进程退出 0。以下结论按原文范围使用，不认证模型指标或未审查的链路。

**结论：限定 GO。** 可部署这份 v6 Kev08 CPU waiter，让原推理／finisher 继续运行；auditor 资源绑定补丁在所审代码范围内可放行。未发现本次范围内尚未关闭的阻断项。

已自行计算 SHA-256：manifest **10/10 匹配**；生产 plan 中本地可对应的 **6 个冻结文件匹配**。以下判断来自实际控制流与配置核对，并非仅接受测试结果。

| 原问题 | 复审证据与结论 |
|---|---|
| **P1：公开报告与终态哈希错配** | [waiter:374](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/jeval_hardened_waiter.py:374) 从同一次读取的公开字节解析报告、计算哈希，核对提交状态及已认证 attempt，重新验证并复查文件未变；终态使用返回的认证哈希。**关闭。** |
| **P1：只读来源／危险 bind** | [waiter:86](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/jeval_hardened_waiter.py:86) 同时检查精确 Binds、有效 Mounts、设备／扩权／命名空间配置；launcher 在 start 前、waiter 在运行入口均调用。[实际 spec:43](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/production/CONTAINER_SPEC.json:43) 为 cephfs 只读、仅 waiter 输出目录宿主 bind 可写、socket 只读，无设备。额外设备 bind、嵌套覆盖均不符合允许集合。**限定关闭。** |
| **P2：生产 COMPLETE 被覆盖** | [waiter:449](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/jeval_hardened_waiter.py:449) 成功发布使用 `no_clobber_json`；失败终态同样使用该函数，其 `os.link` 原子拒绝已有目标。竞争时保留原终态并报错。**关闭。** |
| **P2：成功 COMPLETE＋EXIT137 无法恢复** | [launcher:60](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/production/launch.py:60) 校验恢复审批绑定 plan、容器、FinishedAt、EXIT；[waiter:416](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/jeval_hardened_waiter.py:416) 重验完整成功证据，归档中断 EXIT，保留原 COMPLETE 后返回成功。**关闭。** |
| **P2：单杀 auditor 被当作业务失败** | [waiter:198](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/jeval_hardened_waiter.py:198) 保存原始退出码及信号中断标记；317 行分支在取得锁后保留产物、进入有界新 attempt，并重新检查来源。普通失败仍拒绝自动重试。**关闭。** |
| **P2：supervisor PID 复用导致永久失败** | [waiter:285](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/jeval_hardened_waiter.py:285) 继承锁仍被占用时继续等待；PID 身份不同仅记录诊断，不再生成失败终态。**关闭。** |
| **P2：auditor 漏验资源权限** | [auditor:315](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/audit_jeval_inference_hardened.py:315) 精确比较 Privileged、DeviceRequests、DeviceCgroupRules、结构化 Mounts、VolumesFrom、capabilities、安全选项及命名空间等，并核对有效 bind 的来源／目标／RW。[523 行](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/tools/audit_jeval_inference_hardened.py:523) 实际覆盖 inference、probe、finisher；独立 probe 路径也调用。**本代显式 bind 配置范围内关闭。** |

**证据边界：** 17 文件完整冻结验证、26＋13＋26 测试及四处真实 CPU SIGKILL 恢复属于外部供应证据；已核对[结构化 fixture 报告](/tmp/nga-astra-waiter-v6-rereview-st_p4yr5/production/FIXTURE_COMPLETE.json:14)，其中成功终态保持不变，但 Docker／来源／指标控制为合成。此次未运行实验或访问现场 Docker，未独立核验全部模型源码闭包及三类容器现场配置。

真实 Docker socket 仍是特权 API；所审 waiter／auditor 使用 GET，不构成能力沙箱。此 GO 不认证模型分数，也不扩大为队列全链路放行。