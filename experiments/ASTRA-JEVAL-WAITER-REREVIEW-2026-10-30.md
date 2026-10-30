# Astra waiter 修订复审：暂不放行 v4

2026-10-30。指定 `gpt-6-astra` 的实际只读复审。外层 runner 超时返回 124，未创建指定输出文件；有界日志诊断发现已产生完整 `agent_message`（item_20）和 `turn.completed`，以下逐字保存该最终消息。不能把 runner 写成正常退出；审查内容与运行器终态分别保留。该结论不影响现有模型继续推理，尚未部署 v4。

**结论：暂不批准 v4 waiter 在模型继续运行时按“已验证只读部署”上线。** 当前代码存在最终报告错误接受路径；只读挂载及设备隔离也未形成完整的强制检查。此结论不涉及队列／资源 F1/F3，不要求停止现有模型，也不认证任何模型分数。

已完整阅读 manifest 中的 **7 个文件**，开始及结束时逐一计算 SHA-256，全部匹配：两个实现文件、两个测试文件、两份审查／修订文档和 `launcher.py`。未修改冻结文件。

**本次发现如下。**

1. **P1：最终终态可能认证被替换、但未验证的公开报告。**  
   位置：[jeval_hardened_waiter.py:354](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:354)、[终态哈希:367](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:367)。  
   `reconcile_audit()` 返回已验证的内存对象 `a`；随后执行来源、依赖及 receipts 复核，但第 358 行仍验证内存中的 `a`。最后却重新读取公开 `HARDENED_AUDIT.json` 的哈希写入成功终态。因此，在 reconcile 返回后替换公开报告，会得到“旧报告的成功状态／flags + 新文件的哈希”。  
   **证据：** 纯内存桩复现中，最终验证器收到旧对象，生成的终态却为 `rc=0, audit_sha256=TAMPERED_REPORT_HASH`。这是控制流复现，不是实盘篡改实验。  
   **修复：** 最终提交时重新读取公开报告，核对 attempt／commit 已认证哈希并验证该对象；终态引用这份已验证字节的哈希，不能重新认证任意当前内容。下游仍须重新核对报告与 receipts。

2. **P1：`readonly_sources=True` 没有强制落实为只读挂载；启动检查允许危险 bind。**  
   位置：[launcher.py:22](/tmp/nga-astra-waiter-rereview-cbo1fntq/launcher.py:22)、[waiter 自检:318](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:318)。  
   launcher 直接使用 spec 中的 `Binds`，`binding()` 只验证实际配置与 spec 相同。额外检查拒绝 privileged、Devices、DeviceRequests 等，却没有检查 bind 的来源、目标、读写模式及嵌套覆盖。`readonly_sources` 只是布尔断言。  
   **证据：** 对实际 launcher 语句进行纯内存桩执行，配置包含 `/models:/models:rw`、`/dev:/host-dev:ro` 时仍到达 `docker start` 调用；没有实际执行 Docker。设备 bind 被接受不等于已证明 NPU 可访问，但足以说明该检查不能证明设备隔离。真实 Docker socket 即使挂为 `:ro`，也不会因此限制 API 为只读；当前被审代码使用 GET，但这不构成权限隔离。  
   **修复：** 启动前强制校验实际有效挂载：来源及依赖只读、仅 waiter 输出目录可写，拒绝设备目录及危险覆盖；需要隔离保证时使用只允许必要 inspect 请求的代理。  
   **部署证据缺口：** 本快照没有生产 `plan.json`、`CONTAINER_SPEC.json`、wrapper 和审批文件，无法判断真实配置是否已经规避这些风险。本项针对 waiter 自身，不是越界重审队列 F1。

3. **P2：生产 `COMPLETE.json` 不满足 no-clobber，测试 fixture 与生产路径不同。**  
   位置：[生产提交:368](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:368)、[atomic:51](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:51)、[fixture:221](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/test_jeval_hardened_waiter.py:221)。  
   生产仅在启动时检查终态不存在，最终使用 `os.replace()`。运行期间出现的终态会被覆盖；waiter 锁只约束遵循同一锁协议的写者。fixture 则调用 `no_clobber_json()`，因此 fixture 成功不能证明生产终态具备相同属性。  
   **修复：** 终态使用 no-clobber 发布；目标已存在时核验并保留，禁止覆盖。增加直接覆盖生产 `run()` 的竞争发布反例。

4. **P2：成功终态已写出、wrapper 尚未成功退出时，中断仍会堵死恢复。**  
   位置：[launcher.py:12](/tmp/nga-astra-waiter-rereview-cbo1fntq/launcher.py:12)、[恢复分支:42](/tmp/nga-astra-waiter-rereview-cbo1fntq/launcher.py:42)、[waiter:314](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:314)。  
   若 Python 已发布成功 `COMPLETE.json`，但返回 shell 前被 SIGKILL，wrapper 可记录 EXIT137。launcher 会先因 COMPLETE 存在拒绝，无法进入已有的恢复审批分支；直接重启 waiter 也被拒绝。完整审计可保留，但同代 wrapper／容器成功退出链无法恢复。  
   **修复：** 为“成功终态存在、外层退出中断”提供独立 reconciliation：复核完整证据及审批，保留原报告和终态，归档旧 EXIT 后完成外层恢复。补测终态发布后的故障点。

5. **P2：单独 SIGKILL auditor 被当作业务失败，不能进入中断 attempt 恢复。**  
   位置：[attempt_worker:163](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:163)、[失败终态处理:285](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:285)。  
   supervisor 存活时，auditor 被 SIGKILL 会返回 `-9`。worker 将其转换成 `ATTEMPT_COMPLETE.rc=1`；reconcile 随即要求 reviewed new generation，无法利用已有的有界中断重试机制。  
   **证据：** 纯内存桩模拟 `returncode=-9`，实际 worker 路径发布了 `rc=1`，没有保留可区分的子进程退出原因。  
   **修复：** 记录原始退出码／信号，将明确中断与审计语义失败分开；中断产物保留，在锁释放、来源复核后按策略进入新 attempt。

6. **P2：supervisor PID 被复用时，仍存活的 auditor 会导致错误的永久失败。**  
   位置：[jeval_hardened_waiter.py:258](/tmp/nga-astra-waiter-rereview-cbo1fntq/tools/jeval_hardened_waiter.py:258)。  
   supervisor 死亡、auditor 继续持有继承锁时，正常设计是等待。但如果旧 supervisor PID 已被其他进程复用，`actual` 非空且身份不同，第 264 行抛异常，生产 `run()` 随后写失败 COMPLETE，阻断后续恢复。  
   **修复：** 以继承锁判断 attempt 是否仍被占用；PID 身份不同只说明该 PID 不再属于 supervisor，不能据此认定持锁 auditor 失败。保持等待并记录诊断，锁释放后再处理结果。此项为静态路径推导。

原发现的复审判断：

| 原发现 | 本次判断 |
|---|---|
| **F2：逐题 receipts 未绑定** | auditor 已输出完整有序 manifest，waiter 在恢复、发布及最终提交前重核；稳态删除、修改、额外文件及 symlink 的拒绝逻辑已补上。但队列接受／释放消费者不在本次快照，且上述发现 1 仍留下报告认证缺口，不能宣布全链关闭。 |
| **F4：审计产物与终态之间中断不可恢复** | attempt 目录、继承 flock、完成收据及提交意图显著改善恢复；已完成 attempt 可复用，未完成 attempt 可保留后重试。但发现 4–6 表明恢复覆盖仍不完整。 |
| **F5：遗漏 valid_accuracy** | 本次范围内修复成立。代码分别比较 `accuracy`、`valid_accuracy`；100／200 总数、相同有效分母的负例已实际通过。 |

测试及证据边界：实际运行了有界 CPU 单测，**15 项无需写盘的 auditor 测试通过**。完整测试中的临时目录创建被只读沙箱阻止，waiter 21 项均未进入测试主体，不能记为通过。另完成上述纯内存控制流复现；没有 Docker、模型实验、网络或子代理。

您提供的 v2 CPU fixture 结果——发布控制器 SIGKILL 后 EXIT137、同报告单 attempt 恢复；supervisor SIGKILL 后保留 attempt0 并成功 attempt1；保留容器 exit0——均作为**外部供应证据**采纳，不冒充本人观察，也不外推为 v4 生产 launcher／wrapper 已验证。当前不足以放行只读部署；补齐真实启动闭包并修复上述提交、隔离和恢复问题后，才可作限定范围的部署判断。
