# Typed Decisions 六模型：实际 Astra 有界结果审查

审查完成：2026-10-30T21:13:39.528282+00:00（北京时间 2026-10-31）。实际执行固定 `codex exec --model gpt-6-astra --sandbox read-only`，CLI 子进程 `Popen.wait` 返回 0，runner terminal `rc=0`。模型身份记录来自实际 CLI 参数、终态及实质报告，不是对服务端内部模型的额外证明。

**限定结论：六模型保存面板可表述为“经独立复核、有明确边界的 Typed Decisions 参考指标”；本次未发现阻断该限定发布口径的算术、receipt 人口或包内绑定错误。** 不扩展为训练收益、业务收益、严格 wire/HTTP 复现、全量 JEVal/OOD 完成或正式训练启动许可。

## 实际证据绑定

- 原审查目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_astra_20261031`。
- 原 `review.md` SHA-256：`e4330a6892011ba8ff85a2ea2dbd3f80453dda32e31adcef9d10d53c8fad2052`。
- `COMPLETE.json` SHA-256：`d2b0a6fe4fffb3ab08f5b29b2b8c20cb6ae81185a509bce9edfc7415f7997610`。
- `CHILD_EXIT.json` SHA-256：`a3c7899d58681c03cd9157cac7c99f6dc2ea571e165fea2d864d4228c1c10be7`。
- `PROCESS.json` SHA-256：`54e9e09398554201dfecb2cd7111ef49cc360ffbc82396e66cf666726c38eced`。
- 冻结 bundle：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031`。
- `MANIFEST.json` 文件 SHA-256：`799243b7b91a937ac50840896f3c1f2b1f04c9ca1944c79177d5f8a503765c71`。
- bundle 含 2,547 个列入清单的文件，另有 MANIFEST 自身。审查后再次核对所有清单文件字节数与 SHA-256，未发生变化。

完整结构化证据、runner 终态、原审查全文和限制清单见 [JSON 记录](ASTRA-TYPED-RESULTS-REVIEW-2026-10-31.json)。原审查全文逐字保存在下方；文件路径及行号指向被冻结的 bundle。正文中“我”指实际 Astra reviewer。

## 记录者补充与历史说明

下方第五项指出清单内 `meta.manifest_sha256` 含义未在包内解释。其实际口径为：对 `files` 数组执行 `json.dumps(files, sort_keys=True, separators=(',', ':')).encode()` 后取 SHA-256，结果 `28da3706a1913cfe3774c4e3af31004c03f8cb8e0c4bbbbccd5a16f36c410a10`；它不是 MANIFEST 文件本身的哈希。此补充已重新计算核对，未改动被冻结 bundle，也不删除原审查发现。对外引用使用完整文件哈希。

旧结果文档及准备说明中的“尚无 Astra 实质审查”对应原时间截点，保留为历史事实。本次日期追加更新的是实际审查状态。此前关于推理和验收容器均退出 0 的历史核查声明也保留；本次 bundle 只足以独立核对复制的推理容器退出记录，不能把其结果当成对验收容器本身 Docker 退出的再次确认。

## Astra 原始审查全文

**有限结论：可以将这六模型的保存面板描述为“经独立复核的、有明确边界的 Typed Decisions 参考指标”。本次未发现阻断这一限定发布口径的算术错误、收据缺失／多余、指标不一致或包内哈希绑定断裂。** 这不构成对原始运行全过程、接口复现或训练用途的全面批准。

本次审查对象是**已完成的 Typed Decisions 六模型结果**，不是 E37 代码，也不是正在运行的 JEVal／OOD 实验。审查仅使用指定证据包，执行短时 CPU 算术检查；没有修改证据、重新推理、访问外部权重或查询 Docker。

以下文件路径均相对于证据包根目录。

**按重要性排序的发现与限制**

1. **Kev 的原始 wire 与原评分器确实不兼容；这是严格接口复现声明的阻断项，不是当前原生概率指标的错误。**  
   我检查了三组 Kev 全部收据：每模型 600 个 noul wire answer 均没有 `probabilities`；例如 [Kev-0.8B 收据 000000:1](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_kev08_inference_20261030/records/000000.json:1)。原评分函数在 [score_with_jobs.py:29](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/source/score_with_jobs.py:29) 直接读取该字段。  
   因此，可以发布“原方法算术作用于保存的原生概率”；不能发布“原 HTTP／vLLM／wire scorer 完全复现”。结果文档在 [第25行](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/source/TYPED-REFERENCE-RESULTS-2026-10-30.md:25) 已正确披露此限制。

2. **三类既有 verifier 的独立性范围不同，不能统一表述为六模型均完成独立重分词和完整 wire 验证。**  
   Kev verifier 比较的是预检与实际收据中的 token 数量和哈希，[verify_typed_reference.py:121](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_kev08_inference_20261030/source/verify_typed_reference.py:121) 没有独立重分词；其 [audit:164](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_kev08_inference_20261030/finish/INDEPENDENT_AUDIT.json:164) 明确说明 wire 未独立验证。  
   Nimble 既有代码包含完整 schema 的 prompt 重建及重新 tokenize（[verify_typed_nimble.py:43](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_nimble_inference_20261030/source/verify_typed_nimble.py:43)）；Open-Jev 还包含 native wire 重建比较（[verify_typed_openjev.py:29](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_openjev2_inference_20261030/source/verify_typed_openjev.py:29)、[第49行](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_openjev2_inference_20261030/source/verify_typed_openjev.py:49)）。这些是**原有审计的范围**，本次没有重跑它们。

3. **退出证据支持六个推理容器的已保存成功退出记录；对验收容器自身的实际退出，包内证据较弱。**  
   六份 `finish/INFERENCE_CONTAINER_EXIT.json` 均保存完整 container ID、`status=exited`、`exit_code=0`；我逐一核对 ID 与各自 launch receipt 一致，且退出文件哈希被 `FINISH_COMPLETE.json` 绑定。示例见 [退出记录:2](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_kev08_inference_20261030/finish/INFERENCE_CONTAINER_EXIT.json:2) 和 [完成记录:7](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_kev08_inference_20261030/finish/FINISH_COMPLETE.json:7)。finisher 源码确实先检查容器身份和实际退出状态，再保存该记录（[typed_reference_finish.py:48](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_kev08_inference_20261030/source/typed_reference_finish.py:48)、[第130行](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/typed_kev08_inference_20261030/source/typed_reference_finish.py:130)）。  
   六个验收 wrapper 的 `finish/EXIT` 也均为 rc=0，但包内没有对应验收容器自身的独立 Docker 退出记录。因此，结果文档 [第3行](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/source/TYPED-REFERENCE-RESULTS-2026-10-30.md:3) 关于推理与验收容器均退出0的更广声明，本次不能全部独立确认。**这是证据缺口，不是已证明容器退出失败。**

4. **本次确认的是快照完整性及内部来源一致性，不是原运行的全部外部依赖。**  
   所有复制源码、数据、scorer、配置、报告和终态之间可检查的哈希均一致；但外部权重与部分依赖只保留在配置中的路径／哈希清单内。六个 finisher plan 中的 `run.sh`、`LAUNCH_EXACT.sh` 也没有复制实体。不能据此声称重新验证了完整依赖闭包或原执行环境。  
   此外，当前 Python 没有 `pyarrow`，本次未重新解码 Parquet；指标使用已绑定的完整 `rows.json`。我核验了 Parquet 和 JSON 的实际哈希、提取代码以及提取完成／退出证据（[extract.py:3](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/extract.py:3)、[EXTRACT_COMPLETE.json:5](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/EXTRACT_COMPLETE.json:5)）。没有发现二者不一致的证据，但不把哈希绑定说成本次独立完成了 Parquet 语义解码。

5. **低优先级：清单内部的 `meta.manifest_sha256` 含义不明确。**  
   [MANIFEST.json:12749](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/MANIFEST.json:12749) 保存的是 `28da3706…`，并非当前文件 SHA-256 `799243b7…`；包内没有说明该字段的计算口径。不能推断它一定代表当前文件或据此认定篡改。发布引用应使用用户给定且本次实测一致的完整文件哈希，不应使用这个未解释的内部字段。

**实际完成的完整性与人口核验**

- `MANIFEST.json` 的 SHA-256 精确等于  
  `799243b7b91a937ac50840896f3c1f2b1f04c9ca1944c79177d5f8a503765c71`。
- 清单中 **2547 个文件**逐一通过字节数及 SHA-256 校验；无重复路径、缺失项或额外未列文件，只有 MANIFEST 自身未列入文件项。
- 六模型各有且仅有 `000000.json`—`000399.json`，合计 **2400 条收据**。逐条核对了 envelope checksum、config identity、index、row ID、完整输入哈希、request 哈希和题目／候选顺序。
- 每模型覆盖相同 **400 个唯一 test state、2000 个问题**；choice=600、noul=600、score=800。四个 workflow 各100个 state、500题。
- 所有保存分布、logits 均有限且形状正确；没有缺失／额外问题。逐项 preflight 与 receipt 的 token 元数据绑定一致，记录的长度在配置上限内。这支持保存人口中的有效性计数，不证明原运行历史从未出现瞬时错误或重试。
- 实际重算了配置 canonical identity，并核对 report、audit、推理终态、finisher 终态、launch、退出记录及所有终态输出哈希。配置中的数据／scorer 身份与包内实体一致。

数据文件 SHA-256 为 `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`；原 scorer 为 `6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8`。

**公式与分母审查**

我阅读了原 scorer 和 `recompute.py`，随后：

- 在内存中运行捆绑重算，输出与 `RECOMPUTED.json` **完全一致**。
- 另写独立的标准库计算实现，不导入原 scorer、推理或 verifier，重新计算全部11面板的 overall、3个 by-type、4个 by-workflow 单元。
- 对 report、audit、RECOMPUTED 共作 **1485 次标量比较**；最大绝对差为 **9.992×10⁻¹⁶**。

确认的口径如下，与 [score_with_jobs.py:26](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/source/score_with_jobs.py:26)、[第83行](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/source/score_with_jobs.py:83) 一致：

- prediction 按题归一化；gold 保留原数值，**不归一化**。
- Accuracy：按 gold 候选顺序取预测与 gold 的**首次 argmax**，比较硬标签。
- Brier：每题对候选维度求 \(\sum_k(p_k-g_k)^2\)，再按题平均；不除以候选数。
- KL：\(\sum_{g_k>0}g_k\log[g_k/\max(p_k,10^{-9})]\)，再按题平均。
- ECE10：以最大预测概率分10个等宽箱，使用硬 argmax correctness；置信度1归最后一箱。
- 总体问题等权，题型权重为 **0.3／0.3／0.4**。Accuracy、KL、Brier 可由分项按人口加权还原；总体 ECE 必须重新汇总分箱，不能简单平均分项 ECE。

实际数据中，**455题**的 gold 概率和偏离1超过 \(10^{-12}\)，范围约为0.999999—1.000001；**35题**存在 gold 最高值并列。这两个口径不是无关紧要的文字说明。Open-Jev-9B raw-T1 还有1个正 gold 坐标实际触发 \(10^{-9}\) floor。

温度处理也正确：Kev 保存的是温度缩放后的 logits，raw-T1 使用保存温度乘回后 softmax；Open-Jev 保存 raw logits，serving 使用配置温度；Nimble T=1只计一个面板。六模型 logits→概率最大差不超过 **1.408×10⁻⁷**。五个双温度模型逐题硬正确性完全一致，并非只检查了总准确率相等。

**六模型、11面板的分数复核**

每行均为2000题；下表保留9位小数，与结果文档 [第11行起](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031/source/TYPED-REFERENCE-RESULTS-2026-10-30.md:11) 一致。

| 模型 | 面板／温度 | Accuracy | KL | soft Brier | ECE10 |
|---|---|---:|---:|---:|---:|
| Kev-0.8B | serving，2.351096 | 45.95% | 0.349523040 | 0.195493398 | 0.045770036 |
| Kev-0.8B | raw-T1 | 45.95% | 0.498068065 | 0.260309344 | 0.155169722 |
| Kev-4B | serving，2.406050 | 66.45% | 0.223109423 | 0.124564683 | 0.089533926 |
| Kev-4B | raw-T1 | 66.45% | 0.504515027 | 0.201069093 | 0.091401498 |
| Kev-9B | serving，2.193650 | 68.05% | 0.213789510 | 0.116320990 | 0.064928038 |
| Kev-9B | raw-T1 | 68.05% | 0.519308862 | 0.187224530 | 0.091135501 |
| Nimble initial v1 | serving，1 | 65.10% | 0.706027650 | 0.254995374 | 0.172864315 |
| Open-Jev-2B | serving，1.518796 | 58.25% | 0.410910644 | 0.193816502 | 0.081003319 |
| Open-Jev-2B | raw-T1 | 58.25% | 0.659782229 | 0.245027524 | 0.159234993 |
| Open-Jev-9B | serving，1.896912 | 67.80% | 0.369436036 | 0.147618002 | 0.058201569 |
| Open-Jev-9B | raw-T1 | 67.80% | 0.885942246 | 0.224382522 | 0.148582028 |

对应正确题数依次为 **919、1329、1361、1302、1165、1356**。分项不支持“尺寸越大每项越好”：Kev-9B 对 Kev-4B 总体高1.60个百分点，但 noul 低1个百分点，agent_trace_observability 为50.2%对56.0%。Kev-9B 对 Open-Jev-9B 的总体差只有5题；这里没有显著性、机制因果或训练收益结论。

**可直接发布的精确声明**

> 在指定 SHA-256 固定的 Typed Decisions 证据快照中，六个已完成参考运行各覆盖同一400-state／2000-question test 集。独立只读审查核验了2400条保存收据的完整人口、输入／配置身份和包内报告—审计—终态哈希绑定，并从保存的概率与logits重算了11个明确区分 serving 与 raw-T1 的指标面板及题型／workflow分项，未发现超出浮点舍入的差异。结果可作为该快照、该数据及已声明原生读出口径下，经独立复核的有限参考指标。原推理容器退出证据为复制保留记录；本次没有重新检查原容器、重算外部权重哈希、重新 tokenize 或重新推理，Kev 既有审计也未独立重分词或完整验证 wire。

该声明**不包含**硬件等价、严格 wire／HTTP 复现、业务或训练收益、完整 JEVal／OOD 完成，也不授予正式训练许可。
