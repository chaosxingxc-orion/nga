# E38 v4 冻结执行计划：实际 Astra v3 复审

**裁决：BLOCK 两份 v4 计划，均不得启动。** 主要新增阻断为目录持久化链与 native confidence 硬范围遗漏；另有实际镜像源码和审批时间来源的证据缺口。旧四项 P1 的主要修复成立，report-before-COMPLETE 明确失败的协议选择获接受。详细反例和范围见下方原文。

实际 `codex exec --model gpt-6-astra --sandbox read-only` 已完成，runner 与真实 child 退出均为 0；记录时间 2026-10-30T23:42:18.483932+00:00。执行成功不代表审查通过，裁决见下方原文。本次未启动 NPU、未写批准文件，不覆盖此前 v2 BLOCK。

| 模型 | v4 plan SHA-256 |
| --- | --- |
| Open-Jev-2B | `882b686ba62c75f1bb41c670b18fb4785f439273bbd32b4c5de29ff9a512a8df` |
| Open-Jev-9B | `b1afb0e81a5c3c77f6bb5892e8dfdb7da750220d6d44f17dc2a7e52b6d9afce3` |

冻结包 `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3`，676 个文件、134055556 bytes；审查后完整 membership、大小与 SHA 核验通过，原计划与副本未变。MANIFEST SHA `a64f3d0e94ec1d9518e7d494e31d1e130f87aeb156393c8c56de9aa7035e77a1`。
实际审查 SHA `512f8f77a977a281694b343e282b14708ea00fe5aff7637948bfa11273707758`；COMPLETE SHA `a7fdb605731e6764901d47d87f47d4cf9c51c04ee194db4dc3f0b08646bc726d`；CHILD_EXIT SHA `fa89e6a4be24be0bda889b7d06823bc7fbccb8bf6f3237f297d22a818b5dbe71`。

包内保留 clean fixed-image CPU v6 的 85 个源码测试方法、85 个逐项结果 JSON 和完整逐项日志，report 与日志逐一对应，0 skips。8 份真实 E37 native 输出 fixture、旧版数字/文件替换反例和独立旧 schema trace 漏洞复现均保留。测试是 CPU 工程证据，不是参考 checkpoint 或 NPU 结果。

外部权重 9 项未复制或重新哈希，沿用 frozen plan expected hashes 与 CPU preparation full-closure 的保存证明；另 1 项历史 Python cache 明确排除。CPU prepare 和 suite 的实际 Docker 退出采用工程保存的 ID/exit/时间/哈希摘要，而非 reviewer 现场 Docker 查询。builder 的实际 retained-container 退出与终态另外绑定。E36/E37 false admission、未执行 NPU、无训练收益的边界不变。
完整机器证据见 [ASTRA-E38-EXECUTION-V3-REVIEW-2026-10-31.json](ASTRA-E38-EXECUTION-V3-REVIEW-2026-10-31.json)。以下保留实际审查原文。记录者说明：原文末尾“未创建归档文件”仅指只读 reviewer 自身；外层 CLI runner 及本记录已保存真实审查和终态工件。

---

**结论：BLOCK。两份 v4 精确计划目前仍不应启动。** 旧版四项 P1 的主要修复成立，但本次发现一个可执行复现的 native 回答验收漏洞，以及严格尝试数协议的持久化缺口；另有两处证据闭合不足。此结论独立于先前 v2 审阅及 CLI 退出码。

本次只审查指定 v3 副本。实测 manifest SHA256 为：

`a64f3d0e94ec1d9518e7d494e31d1e130f87aeb156393c8c56de9aa7035e77a1`

| 精确计划 | 实测 SHA256 |
|---|---|
| Open-Jev-2B，`openjev_path_trace_openjev2_20261031_v4/plan.json` | `882b686ba62c75f1bb41c670b18fb4785f439273bbd32b4c5de29ff9a512a8df` |
| Open-Jev-9B，`openjev_path_trace_openjev9_20261031_v4/plan.json` | `b1afb0e81a5c3c77f6bb5892e8dfdb7da750220d6d44f17dc2a7e52b6d9afce3` |

以下源码引用均指包内副本；两模型相关实现字节一致。

1. **P1：首次 forward 前，durable intent 的目录持久化链不完整。**

   [openjev_path_trace_run.py:297](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v4/openjev_path_trace_run.py:297) 新建 `items/` 和 `attempts/`，随后发布 intent，再执行 prediction。[e38_evidence.py:102](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v4/e38_evidence.py:102) 确实 fsync 文件和直接父目录，但没有 fsync 新建 `attempts/` 所在的 generation 目录。我用完全虚拟的系统调用桩执行了实际 `publish_new`，确认这一调用顺序。

   最小崩溃情形：首次 forward 已执行、receipt 尚未提交，存储恢复丢失尚未被明确持久化的 `attempts/` 目录项。此时 [verify_openjev_path_trace.py:124](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v4/verify_openjev_path_trace.py:124) 把“无 attempts、无 items”接受为未开始状态，后续获准恢复可能重做该 forward。

   **这是源码级耐久性缺口，不是本次在 Ceph 上复现了数据丢失。** 包内没有更强的文件系统保证来排除此情形。最小修复是在首次可能执行 forward 前持久化新目录及其父目录，并增加目录项丢失的故障测试。同类问题还存在于 [prepare_openjev_path_trace.py:491](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v4/prepare_openjev_path_trace.py:491)：迁移旧 EXIT 后没有持久化源、目标目录，尚不能完整保证崩溃后的历史证据保存。

2. **P2：独立 verifier 接受 native 明确禁止的 confidence，已复现完整八回执误接受。**

   [verify_openjev_path_trace.py:115](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v4/verify_openjev_path_trace.py:115) 只检查 confidence 的数值类型、有限性和重建误差，没有检查 `0 <= confidence <= 1`。native 的 [jeval_reference_inference.py:30](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_openjev2_probe_20261030/jeval_reference_inference.py:30) 则明确要求该范围。

   本次纯 CPU、内存路径桩反例保留实际 2B 计划身份、全部696个事件布局、八任务及匹配 intents，设置全零 logits、均匀概率、正确首项 choice，仅把 confidence 设为 **`-5e-8`**，重新计算全部 envelope 哈希。实际 `validate_items(..., complete=True)` 接受八份回执，`reconstruct` 返回 **全部11项 controls=true、trace_valid=true**。

   最小修复是先检查 native 硬范围，再应用跨运行时重建误差界限，并加入上下界外数值的完整回执回归。不能用 `confidence_atol` 豁免协议范围。

3. **P2，证据缺口：冻结 trace 与镜像内实际 Qwen 实现的源码对应关系尚未完整提供。**

   包内含合同生成器、两种配置、E37 层身份以及 tiny 模型测试，但没有实际 `modeling_qwen3_5.py`／GDN fallback 源码。测试直接导入镜像安装包，见 [test_openjev_path_trace_run.py:220](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_execution_cpu_tests_20261031_v6/tools/test_openjev_path_trace_run.py:220)。

   我确认两份合同可以从各自配置和 E37 层列表重新生成，分别为696／928个事件；也确认 producer 和 verifier 强制执行合同。但“生成器重建自身结果”和 tiny24 日志不足以完成要求的**实际 native 源码逐事件核对**。这不是已证明顺序或形状错误。应补入固定镜像实际解析到的相关源码及来源／哈希绑定，才能独立核对两种模型的 GDN、norm 和投影调用顺序。

4. **P2，证据缺口：保存的 CPU preparation 审批时间晚于对应执行。**

   2B 的 [PARENT_REVIEW.json:3](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/e38_openjev2_prepare_20261031_v4/PARENT_REVIEW.json:3) 时间为 `23:27:25`，但保存的 [执行记录:7](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v3/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v4/PARENT-CHECKABLE-EVIDENCE.json:7) 显示 `23:26:11` 启动、`23:26:30` 结束；9B 同样如此。

   当前审批与 request 哈希匹配，但不能据此证明它就是启动前读取的审批字节。可能是事后更新记录；**不能据此断言实际未经审批启动**。需要保留原启动前审批及更新说明，或补充启动时绑定的审批摘要。

**对先前问题的逐项处置：**

| 先前问题 | 本次处置 |
|---|---|
| 正确 native 回答被拒绝 | 主要修复成立。八份实际 E37 原始 envelope 与副本逐字节匹配，全部原样通过本次重跑；chance-adjusted confidence、wire renormalization 已正确处理。仍须修复上述 confidence 硬范围遗漏。 |
| 全零、非单位质量、错误 choice、脱离 logits 的概率被接受 | 原反例已关闭。本次在完整八回执路径中重新封装哈希后，四类变异均被拒绝。首项并列选择、非法类型、NaN／Inf 也已检查。 |
| trace 仅检查相互一致 | 验证逻辑已修复：注册顺序与执行顺序分离，逐事件 dtype、row_shape、layout 被冻结；reverse、float64、`[1]`、错误 folded heads 均拒绝。实际镜像源码审阅仍受上述证据缺口限制。 |
| parse 后单次 atomic replace | 原漏洞已关闭。Snapshot 从同一 descriptor 读取字节并计算摘要，解析这些字节，并检查文件身份；逐级 `O_NOFOLLOW` 覆盖路径组件。保存的 stable-good、stable-bad、真实 replace 测试均通过，注入测试明确断言 `replaced == [True]`，不是 schema 提前失败。 |
| 八 receipts 不证明八 attempts | 进程中断路径明显改善：intent 先于 forward，receipt 绑定 intent，未匹配／partial intent 拒绝并标记失败；但目录持久化缺口使严格保证尚未闭合。 |
| report-before-COMPLETE | **接受当前明确失败的协议选择。** `publication_gate` 保留报告并标记 FAILED_GENERATION，普通恢复拒绝；完成 verifier 也禁止失败 generation 转成功。不要求自动 finalize。 |

两套旧版回归记录已分别检查：old-v2 日志确实记录 native／数值／读取竞态反例；独立 old-schema trace 日志包含一个通过的基线和三个错误接受的变异。没有把新版 layout 被旧 verifier 拒绝当成旧 trace 漏洞复现。历史 pyc 的明确省略不影响这些源码／日志绑定。

**其余核验结果：**

- manifest 的676个成员全部大小／哈希匹配，无额外或缺失文件；PATH_MAP 全部包含项匹配。两计划各有201项包含依赖通过，另分别省略3／6项权重，其预期摘要与遗漏清单一致。
- CPU_TEST_COVERAGE 的85个登记方法与源码方法集合完全一致；85份唯一收据、85份完整日志及 report 一一对应，零 skip。最终 v6 source manifest、terminal、EXIT 摘要链匹配，无 pyc；两模型计划和 preparation 的 Python 源码与该测试包一致。
- 本次实际重跑12个纯 CPU 回归；另执行类型／并列／signed-zero检查、完整八回执变异检查。259个 Python 文件内存编译、42个 shell 文件仅语法检查通过。
- 固定4200、15候选、宽186、八任务顺序、两模型原生温度正确；request 摘要和全部 padded mask 行哈希匹配。重复／hook 使用精确序列化摘要，one-ULP 与 signed zero 没有被数值容差掩盖。
- preparation request、wrapper、spec、receipt、report、terminal、EXIT 的摘要及保存的容器身份相互匹配；CPU spec 无 devices、network none，保留固定镜像原 entrypoint。实际 Docker 退出状态属于保存的 provenance，本次未重新查询。
- launcher 在资源锁内检查当前 owner、Docker 暴露和严格 npu-smi 空闲输出，仅允许chip0—5、逻辑 `npu:0`；不释放资源。**两计划都选chip4，不能同时占用。** 后续仍须重新认证实时所有权和占用。
- E36／E37 的 admission=false 保留；科学 controls 失败会产生 `trace_valid=false`、review_flags，不能由 rc0 推导科学成功。最早 trace 差异只定位观测边界，不能归因 kernel。

本机缺少 torch，且文件系统只读，未重新执行需要磁盘临时夹具的竞态测试或固定镜像张量测试；这些限制没有被记成测试失败，也没有被声称为本次亲验。未重新分词验证全部 padded token IDs，未访问或重新哈希外部权重；权重仅依据保存的 CPU `full_closure_verified` provenance。

包内没有两份 NPU 计划的审批、启动收据或运行终端，与保存的“未启动”记录一致。本次未启动／准备／恢复任何任务，未访问 live Docker、SSH、NPU、allocation 或外部权重，未创建审批或归档文件。**当前结论不授予完整 JEVal、chunk8 精确等价、kernel 因果或训练收益主张。**
