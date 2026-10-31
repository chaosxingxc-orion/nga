# E39 actual Astra bounded result review — complete

**Bounded pass for current saved evidence and 28-panel metric reconstruction, with dated publication clarifications appended.** The runner and actual child exited 0 at 2026-10-30T23:54:43.046664+00:00; duration 641.689 s. This actual `gpt-6-astra` invocation is independent of prior experiment reviews.

The reviewer independently rehashed all 8,930 bundle files and reconstructed all 28 metric panels from 8,462 original receipts and 11,495 questions. Maximum absolute difference from the old matrix was 1.1102230246251565e-16. Original CPU scans covered 8,952 inputs / 30,910,366,106 bytes; this reviewer directly re-read only the included 8,875 inputs / 31,876,988 bytes, with 77 inputs explicitly excluded. The full bundle is 45,876,752 bytes including other audit/source records.

The required [dated source-result clarification](LEGACY-KEV-DATED-REAUDIT-RESULTS-2026-10-31.md) has been appended without changing the frozen review package or metrics: auditor source is modified by the bounded read adapter after its original bytes are verified; per-file journaling covers the two hash_phase scans; cross-scan equality is path/SHA/bytes rather than stored inode/mtime identity. Resume/cache paths were not actually exercised and unattended safe relaunch is not approved. Small and perfect subgroups reported by the reviewer remain scoped diagnostics, not headline metric changes.

| Evidence | SHA-256 |
| --- | --- |
| Frozen bundle MANIFEST | `dfcf9aa9355e2563895f2e489c92acac18523fbacbaefe47583c95bf257d9f58` |
| Actual review | `588a9431baa419735055b76943fef841a015cae9d2829fa9d9d28c2dd16bf6d0` |
| Runner COMPLETE | `49c9584ba95b599df571f6ad93c223ef8b122faf284fcf8fceffc740ec3f1dac` |
| Actual CHILD_EXIT | `79f4f984b2bf761cf090d340ae1e31d7f2ffd54c37e4fec93706d578bf3957b9` |
| Additive erratum | `61a0c621cad1af89b029f53b6695c684b35298c29a8194f958bef80ccdcc7885` |

Runner: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_astra_20261031`. Bundle: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031`. Additive erratum: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/e39_legacy_kev_current_reaudit_20261031_v2/ERRATUM-ASTRA-SCOPE-20261031.md`. The [machine record](ASTRA-LEGACY-KEV-DATED-REAUDIT-REVIEW-2026-10-31.json) retains exact process/terminal evidence and the full text. Post-review checks rehashed all bundle members and all terminal-bound runner outputs. CLI identity documents the requested model, not provider-internal attestation.

## Actual reviewer report (verbatim)

**结论：E39 v2 generation 0001 的“当前保存证据完整性及 28 面板指标重建”有界通过。未发现阻断这些指标发布的错误；发布时须附下述 dated erratum 和验证范围。恢复路径、历史 finisher 绑定及模型执行复现不在通过范围内。**

本轮实际重新读取、哈希和计算了冻结证据，没有沿用 Kev4/9 或其他实验结论，没有调用被审 driver／auditor 作为独立证明。校验通过 `python -I` 的内存 stdlib 脚本完成，cwd 保持在 reviewer 目录；没有写回冻结包、修改阈值、运行 NPU、读取外部权重、访问网络或重新查询 Docker。

**实际独立核验结果**

[MANIFEST.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/MANIFEST.json) 的 SHA-256 为指定的：

`dfcf9aa9355e2563895f2e489c92acac18523fbacbaefe47583c95bf257d9f58`

审查开始和结束各完整校验一次：**8,930 个登记文件、45,876,752 bytes，全部 hash／bytes 匹配**，没有重复登记、遗漏或额外文件；清单自身单独计算，不包含在这两个登记总数中。

独立读取了全部 **8,462 份原推理回执**，验证：

- 原 test JSONL 与 manifest／config 的哈希、records／questions 数量。
- config canonical SHA 与 CONFIG_RECEIPT、payload stamp、原终态及报告的一致性。
- EXPECTED 集合、回执文件集合、每份 payload SHA 和 input SHA。
- 每个问题及候选项覆盖、标签、候选顺序、概率与 logits、原温度。
- 从回执重建的 11,495 行与保存 rows 的元数据、概率和 logits。
- 原 rows／report 与终态哈希绑定，以及原报告、8 份旧 audit、本轮 7 份 audit 和矩阵的一致性。

| 原 run | 回执 records | questions | 重算面板 |
|---|---:|---:|---:|
| kev08_test | 1,940 | 2,204 | 4 |
| kev08_extended | 1,274 | 2,024 | 4 |
| kev08_devtools | 900 | 1,073 | 4 |
| kev4_extended | 1,274 | 2,024 | 4 |
| kev4_devtools | 900 | 1,073 | 4 |
| kev9_extended | 1,274 | 2,024 | 4 |
| kev9_devtools | 900 | 1,073 | 4 |
| **合计** | **8,462** | **11,495** | **28** |

这 28 项是七次原 run 保存预测的不同温度／子集计分，**不是 28 次新推理，也不是 28 个独立重复实验**。

**独立数学重算通过**

我单独实现了 question-weighted first-argmax accuracy、逐题类别平方误差求和后平均的 Brier、top-confidence ECE10，以及稳定 log-sum-exp NLL。native 使用归一化的保存概率；T1 将保存的 native logits 乘回原温度后重新 softmax。ECE 保留原边界表达及最后一箱包含 1 的规则，没有重新选温度、阈值或过滤条件。

原温度逐条一致：

- Kev-0.8B：`2.3510958125672174`
- Kev-4B：`2.406050072164233`
- Kev-9B：`2.193649959389252`

28 面板的 n／accuracy／Brier／ECE10／NLL 全部通过原 `1e-10` 容差：

| 比较对象 | 最大绝对差 |
|---|---:|
| 原保存 rows 的概率／logits | 0 |
| 原 suite report | 1.1102230246251565×10⁻¹⁶ |
| 原固定矩阵 | 1.1102230246251565×10⁻¹⁶ |
| 旧 audit、本轮 audit、本轮 panels | 0 |

全部预测的概率和偏离 1 最大为 `2.3079337552189827e-7`；保存概率与 logits softmax 的最大差为 `2.273361170423982e-7`，均在既有 `1e-5` 检查范围内。

分母也从原记录重建：decision clean **1200**、transfer clean **656**、hard clean **1088**、documents clean **936**、devtools full **1073**／release **1071**。矩阵所有相关 `dataset_identity` 和 `denominators` 字段一致。

devtools 的 900 条记录只有 899 个不同文本 ID：零基位置 **570、622** 同为 `codereviewer/cls-test/19245`，内容及 input SHA 不同。两条均保留在 full，并按原 release policy 排除；没有按 ID 去重。另一 drop ID `13657` 不在该 test 中。证据见 [原 devtools 协议](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/runs/kev08_devtools_20261030/PROTOCOL.md:5)。

**原 CPU 全量扫描与本次验证范围必须分开**

我验证了 [BEFORE.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/reaudit/generations/0001/BEFORE.json)、AFTER.json 逐字节相同；各自 journal 均有完整、有序的 **8,952 条**，路径、index、hash、bytes 与 PLAN 对应，总计 **30,910,366,106 bytes**。

其中：

| PLAN 输入范围 | 文件数 | bytes | 本次验证方式 |
|---|---:|---:|---|
| 冻结包包含 | 8,875 | 31,876,988 | 实际读取并重哈希，与扫描记录比较 |
| 冻结包排除 | 77 | 30,878,489,118 | 仅核对 PLAN、EXCLUDED_INPUTS、前后扫描记录 |
| 原 CPU 扫描总计 | 8,952 | 30,910,366,106 | 保存记录内部一致 |

385 个不同原 config 依赖中，308 个在包内、77 个被排除。**不能将本次审查写成独立重新读取了全部 30.9 GB。**排除项也不只是权重，还包含 tokenizer／配置和部分 development 等依赖；具体以 [EXCLUDED_INPUTS.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/EXCLUDED_INPUTS.json) 为准。

七份 result／binding 的 plan SHA、canonical manifest SHA、结果 SHA 均正确；七个 `resumed_from_verified_result` 均为 **false**。报告、COMPLETE、LATEST_COMPLETE、EXIT、wrapper exit、机器索引及 POSTRUN_IDENTITY_CHECK 相互吻合。

保存的七个原 Docker GET 观察均与 PLAN 的完整 ID、image、wrapper 和 exited/0 匹配；其中六份历史 LAUNCH_RECEIPT 的 config／wrapper hash 及命令也匹配。Kev-0.8B test 缺少历史 launch receipt，这一缺口仍然存在。

新容器 startup 与 [ACTUAL_CONTAINER_EXIT.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/reaudit/ACTUAL_CONTAINER_EXIT.json) 的 ID、image、命令及 StartedAt 一致，保存终态为 exited/0、无 OOM。host/local 同次观察差为 **98.395255 秒**；没有修正或混用原时间。

v1 的保存失败证据确为 **0/8952、rc=1**，缺失本地 repository matrix 路径。v2 portable matrix 与原矩阵字节相同；0644 修改在代码及 dated 记录中独立保留。没有将 v2 成功改写为 v1 成功。

**代码审查结论与必须澄清的声明**

[legacy_kev_dated_reaudit.py](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/reaudit/code/legacy_kev_dated_reaudit.py:46) 的实际成功路径支持本次结果：

- `checked_bytes` 将 path stat 与打开后的 fd、读取后的 fd／path identity 比较；JSON 从同一次读取、同一次哈希的 bytes 解析。
- 两个 auditor 源码各只有一处指定 `test.jsonl` 表达式。AST 比较确认替换只改变 `audit` 的输入读取；`build_rows`、softmax、metrics 等数学未变。六个包内原 auditor 的这些数学函数也与本轮一致。
- auditor／driver 为 stdlib 路径；依赖文件仅作字节哈希，没有加载权重或调用模型。
- cache 命中分支确实对 `result_bytes` 同读哈希并解析，检查 plan／manifest／result 三个绑定。但它依赖保存 binding 的可信性，不能等同于重新执行数学。
- full-before／after 与两次 receipt 集合检查均存在。generation 新建及锁机制支持保留正常历史代次；这不构成任意中断、掉电或恢复场景的实测保证。

必须以 **dated erratum／发布附注** 澄清以下文字，保留冻结原文：

1. [E39 文档第 41 行](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/source/E39-legacy-kev-current-reaudit-20261031.md:41) 的 “executing its exact bytes” 不准确。实际是**校验冻结原源码 bytes，随后进行一处受限的内存替换，再编译执行修改后的源码**。数学未变已经独立核实，无需因此改指标或重写冻结源码。
2. 同文第 43 行 “Every file scan appends a durable journal entry” 应限定为 **BEFORE／AFTER 的 `hash_phase` 扫描**。auditor 内部额外 dependency digest、JSON 和源码读取并非每次都记 journal。
3. “before/after file identities unchanged” 应明确表示保存的 **path→SHA256/bytes 相等**；fd/stat identity 是单次读取内检查，不是跨扫描持久保存的 inode／mtime／ctime 相等证明。

[RESUME_EXACT.sh](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e39_legacy_kev_candidate_20261031/reaudit/RESUME_EXACT.sh:3) 只有按名称 `docker start`，没有自动实施 ID／spec／exit 核验或保存旧实际退出观察。现有文档已要求恢复前人工核验，因此**不阻断本次首次成功运行**；但不能发布“自动安全恢复已验证”的结论。如要支持无人值守 relaunch，必须另行实现这些保护并验证。

我阅读了测试源码，**没有重跑 11 项单测，也没有执行 cache reuse、restart、故障注入或恢复路径**。测试中的“真实 auditor 加载”仅检查 callable，不能单独证明数学正确；本轮的数学证明来自上述原始回执重算。

**零 flags 的边界**

28 个固定面板和整套 constant-vector 检查确实没有触发原 flags；这不能扩展到任意子群。例如实际核查发现：

- devtools `aegis_category` 仅 **25** 问；0.8B／4B／9B 分别正确 **22／23／21**。
- 0.8B transfer clean 中 native confidence≥0.99 只有 **13** 问，恰好全部正确。
- 0.8B decision 的 dbpedia14 子群 **80/80** 正确。

这些不改变 headline 指标，但必须保留小样本、边界准确率及泛化解释限制。

可发布的精确结论为：

> 对指定冻结包进行新的只读 CPU 独立审查后，8,930 个登记文件全部通过 SHA-256／bytes 和集合核验；从 8,462 份原回执及原 test 数据独立重建 11,495 个问题，原 28 面板的 native／T1 accuracy、summed Brier、ECE10、NLL 及分母均与原矩阵在既有容差内一致。本轮 E39 v2 的保存扫描记录、结果绑定和实际退出观察内部一致，且该代次未复用缓存数学。结论仅支持当前保存证据及上述计分口径；77 项包外依赖未由本审查重新读取。

原矩阵全部 **28 项 `absent_legacy_inline_audit` 必须保留**。本次通过不补造历史 finisher，不证明历史不可变、无污染、原生 tokenization／设备数值复现、全部上游诊断、配对一致性、训练或业务收益，也不授予 OpenJev JEVal 准入。