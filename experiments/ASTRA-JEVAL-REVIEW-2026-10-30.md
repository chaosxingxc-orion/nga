# Astra 实质代码审查：JEVal 执行与验收

2026-10-30 19:58 UTC。通过 `codex exec --model gpt-6-astra --sandbox read-only` 对冻结六文件执行，进程退出 0，产生实际代码审查。快照来自提交 `f221e42`。该结果不等于模型／指标放行；发现与修复状态应分别记录。原审查仅静态推导，后续须负例复现与实测。

已完整审查 manifest.json 列出的六个文件，SHA-256 全部匹配。发现 **5 项问题：2 项 P1（高），3 项 P2（中）**。以下均为静态代码路径推导，未运行实验。

1. **P1：资源占用检查遗漏其他设备暴露方式，可能错误释放或认领芯片。**
   位置：[jeval_reference_queue.py:81](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/jeval_reference_queue.py#L81)、[资源释放检查:344](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/jeval_reference_queue.py#L344)。
   **证据：** `devices()` 只读取 `HostConfig.Devices`；认领和释放均只比较其中的 `/dev/davinci1`。具有设备访问权限、通过 bind mount 或 privileged 模式访问芯片的运行容器，可以没有这条 `Devices` 记录。此时即使芯片仍被使用，释放路径也会把它写入 `free`。分配锁无法补足这一观测遗漏。
   **修正：** 统一检查设备映射、bind mounts、privileged 等访问方式，并结合实际设备进程占用；无法确定归属时拒绝认领和释放。

2. **P1：最终验收未绑定逐题 receipts，审计后缺失或变化的数据仍可被接受。**
   位置：[jeval_reference_queue.py:309](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/jeval_reference_queue.py#L309)、[重启复核:365](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/jeval_reference_queue.py#L365)、[audit_jeval_inference_hardened.py:430](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/audit_jeval_inference_hardened.py#L430)。
   **证据：** 补充审计只在自身执行期间比较 receipts 集合和哈希；队列 `completion()` 的证据清单不包含 `records/*.json`，也不重新检查其数量或内容。因此，在审计退出后、队列下一次验收前删除或修改一个 receipt，只要报告和终态文件不变，最终验收仍可通过并释放资源。已有 `ACCEPTED.json` 的重启分支也存在同样遗漏。
   **修正：** 将完整 receipt 文件名集合、数量和内容哈希汇总写入审计结果，并在最终接受、重启复核及释放前核对；或使用不可变的产物快照。

3. **P2：控制器子进程被 SIGKILL 后，生成的 EXIT 会堵死已实现的恢复入口。**
   位置：[prepare_jeval_reference_queue.py:21](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/prepare_jeval_reference_queue.py#L21)、[恢复前置检查:88](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/prepare_jeval_reference_queue.py#L88)。
   **证据：** wrapper 等待 Python 命令返回，然后写 `EXIT`。若只杀死 Python 控制器，存活的 shell 会记录 `rc=137`，但 Python 无法写出 `QUEUE_COMPLETE.json`。随后 `--resume` 在第 88 行因 `EXIT` 存在而拒绝，根本到不了第 115–118 行的中断恢复及 `RESUME_REVIEW.json` 核验。即使已有匹配的恢复审批也无法继续。
   **修正：** 区分控制器中断与已记录的业务失败；对经过现有恢复审批核验的中断代次保留、归档旧 EXIT，再恢复同一容器及队列状态。

4. **P2：waiter 在审计产物写出与终态提交之间中断，无法继续恢复。**
   位置：[jeval_hardened_waiter.py:125](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/jeval_hardened_waiter.py#L125)、[审计及终态提交:160](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/jeval_hardened_waiter.py#L160)。
   **证据：** 子审计先生成 `HARDENED_AUDIT.json`，waiter 随后复核来源并写 `COMPLETE.json`。在两者之间遭遇 SIGKILL，重启会因已有审计 JSON 被第 125 行无条件拒绝；该检查还位于异常记录逻辑之外，不能生成新的失败说明。审计 JSON 写到一半时中断也有同样问题。
   **修正：** 持久化审计阶段和执行身份；完整产物经来源及哈希复核后允许补交终态，残缺产物保留后进入新的审计尝试目录，避免覆盖证据。

5. **P2：跨 source 的相同指标诊断遗漏 `valid_accuracy`。**
   位置：[audit_jeval_inference_hardened.py:334](https://github.com/chaosxingxc-orion/nga/blob/f221e42/tools/audit_jeval_inference_hardened.py#L334)；对应协议：[JEVAL-ADVERSARIAL-REVIEW-2026-10-30.md:57](https://github.com/chaosxingxc-orion/nga/blob/f221e42/experiments/JEVAL-ADVERSARIAL-REVIEW-2026-10-30.md#L57)。
   **证据：** cell 同时计算 `accuracy` 和 `valid_accuracy`，但跨 source 检查只选择 `accuracy` 或 `mae`。例如两个同题型 source 的总数分别为 100、200，有效数均为 50、正确数均为 25：`valid_accuracy` 都是 0.5，而 `accuracy` 分别为 0.25、0.125，不会触发预注册要求的同名指标相同标记。
   **修正：** 分类 cell 分别检查两个 accuracy 指标，并为命中的指标保留对应 cell 指针。

审查覆盖四个 Python 文件及两份协议，包括冻结闭包、容器/终态身份、资源锁与释放恢复、probe schema/算术/分词绑定、资格字段完整性、逐题证据稳定性，以及 cell flags 的生成和传递。原生 verifier、模型依赖及实际运行产物未包含在冻结六文件中，因此未独立验证其行为，也未复核文档所称测试通过情况。全程未编辑文件、启动实验、外部通信或创建子代理；本结论仅属于代码审计。

## 冻结审查输入

```json
{
  "tools/audit_jeval_inference_hardened.py": "04ecdebe1ea117c24fe1f0a66c6adb077902ef599606703a008cb902d8865b44",
  "tools/jeval_reference_queue.py": "556f250ae032ad9d4fd15e8379f6da33d15e669336387689f4c38f12f5340862",
  "tools/jeval_hardened_waiter.py": "b60f41ec9cbc2b352952f6d8feeadb4a7a74141db5aa3bb6468d7a479abbf6e8",
  "tools/prepare_jeval_reference_queue.py": "59ecce0326f98737c29a578723e8abc8640f5a4e8aac26f231572ec5ff93cbc2",
  "experiments/JEVAL-ADVERSARIAL-REVIEW-2026-10-30.md": "0e7e4a31c4143e4dad757b03621c017412464c562b1e7ab6a0cc4e39fb47d4e5",
  "experiments/JEVAL-QUEUE-2026-10-30.md": "96b46b254830ed971be721274f88e1e5f25887c1396adfc2dc00c67d911d37db"
}
```
