# E33 Kev-4B / Kev-9B actual Astra result review — 2026-10-31

**Actual review complete; bounded publication supported with appended length-description erratum.** Both runner and real child exited 0 at 2026-10-30T22:55:48.805489+00:00. The original result metrics, all 66 cells/model and 8/7 flags are retained. This is a newly executed review of these checkpoints, not an inherited Kev-0.8B/Nimble or OOD verdict.

The actual command requests `codex exec --model gpt-6-astra --sandbox read-only`; process receipt and substantive output document this invocation, not provider-internal model attestation. Review duration: 437.094 s. The reviewer checked 22,598 files / 200,511,830 bytes and all 22,514 inference receipts. Post-review validation rechecked the manifest SHA, all terminal output hashes, real child wait result and wrapper terminal.

| Evidence | SHA-256 |
| --- | --- |
| Frozen MANIFEST.json | `dc076f5ffa1e7979e26035868a8f6fb3b815b3e6551db0613fc641473a732c0d` |
| Actual review.md | `dd080fa863d95b8af45f4198f6f0a6b4b47796c46a7a39d8c4fef962def80c64` |
| Runner COMPLETE.json | `02871287007e3cb889e97d6f03bf72f228647bbfee466af7d581ae02056dc021` |
| CHILD_EXIT.json | `be406bc287d5d837dcea184fcff6fc8246b8e75af895eefb273c5e61789a6091` |
| PROCESS.json | `47c362fb1196d3610e87c3287cfef7a0dd0bc9acda6ef8a46bc71eda34e99ced` |
| Additive length erratum | `0813612a6d3db9bcd1e6db135fc5823e28204a2188d49ec352fb2f1850fa0343` |

Runner: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_astra_20261031`. Frozen bundle: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031`. Erratum: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_kev49_closeout_20261031_v2/ERRATUM-LENGTH-20261031.md`. [Machine record](ASTRA-JEVAL-KEV4-KEV9-REVIEW-2026-10-31.json) binds the original report, process, terminal and appended correction; [result record](JEVAL-KEV4-KEV9-RESULTS-2026-10-31.md) retains the original dated snapshot and adds the correction.

The required correction has been applied additively: the historical length ranges cover only non-null `state_tokens`. Per model helmet has 102 state and 48 state-plus-branch overflows; retrieval-en-e has 99 state and 1 state-plus-branch overflow. For example, 7,379 + 3,543 > 8,192 despite the state alone fitting. No frozen evidence or metric was modified. External-weight/native-code/probe completeness, missing extraction source, lack of independent Parquet re-decoding and saved rather than live Docker observations remain explicit limits.

## Actual reviewer report (verbatim)

**裁决：有限通过，可发布为 E33 Kev-4B／Kev-9B 的本地原生预算、原生响应公式测量结果。** 未发现阻止这些数值发布的文件完整性、回执覆盖或指标算术错误。发布时必须保留全部单元、flags 和分母说明，并附加下述长度描述勘误。本次是对这两个新结果的独立审查，不沿用此前模型或 OOD 审查的批准。

优先需要保留的限制如下：

1. **有效子集的满分不能写成完整来源满分。** 两模型 helmet 都是有效 50/50，但完整 200 行准确率只有 **25%**；Kev-4B retrieval-en-e 有效 100/100，完整准确率 **50%**。两模型 retrieval-en 均为 200 行全部超长，没有有效预测，valid-only accuracy 必须为 `null`。
2. **发现一处具体文档表述不完整，数值指标不受影响。** [结果文档第39行](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/source/JEVAL-KEV4-KEV9-RESULTS-2026-10-31.md:39) 所列超长状态长度范围仅来自非空 `state_tokens`。每模型 helmet 的150个超长回执中，102个为状态超限，48个为状态加分支超限且该字段为 null；例如[006507.json:1](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/kev4/inference/records/006507.json:1) 明确保存了 `7379+3543>8192`。retrieval-en-e 的100个超长行也有1个这样的分支超限，见[008729.json:1](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/kev4/inference/records/008729.json:1)。应在新增发布说明中限定范围覆盖对象，保留历史文件不变。
3. **包内复核不等于完整执行环境复现。** 外部权重、原生模型源码及部分 probe 原件未打包；例如 inference terminal 绑定了 `PROBE.json`，但包中没有该文件。完整依赖检查依赖原独立 finisher／hardened 审计的保存证据。本次没有重新读取权重、重新分词或执行模型，也不能独立重做全部运行准入检查。参见[原验证器依赖检查](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/kev4/source/verify_jeval_reference_inference.py:53)及[原 hardened 审计范围](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/kev4/hardened/HARDENED_AUDIT.json:45924)。
4. **Parquet 文件身份已核对，抽取语义未独立重新解码。** 当前没有可用的 Parquet 解码库；本次使用摘要绑定的 `data/rows.json` 重算。原始 Parquet、抽取 JSON 的实际摘要均匹配[EXTRACT_COMPLETE.json:4](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/data/EXTRACT_COMPLETE.json:4)，且全部抽取行与 eligibility／receipt 输入摘要逐行匹配；但这不能冒充重新解码验证。该凭证中 `source_sha256` 对应源码也未随清单提供。这是证据边界，未发现 Parquet 与 JSON 已发生不一致的证据。

本次实际完成的只读 CPU 检查：

- `MANIFEST.json` SHA-256 为 **`dc076f5ffa1e7979e26035868a8f6fb3b815b3e6551db0613fc641473a732c0d`**，与指定值一致。清单 **22,598** 个文件、合计 **200,511,830 bytes**，逐个摘要和字节数全部匹配；无重复路径、缺失项，清单之外仅有 MANIFEST 本身。
- 每模型文件名严格覆盖 `000000.json`—`011256.json`，共11,257个回执；核对索引、唯一原始 ID、完整 gold 行、请求、payload、配置、eligibility 与 consumed-token 摘要，以及 hardened receipt manifest 根摘要。超长回执没有伪造答案。
- 核对包内 config、report、native audit、hardened audit、attempt、terminal、wrapper 和 closeout 绑定；另外验证了74项包内跨文件摘要引用。两模型预注册文件与所附规范文档字节一致。
- 核对保存的六个 inference／finisher／hardened Docker 记录及 closeout 记录，ID、镜像、命令、wrapper 和退出状态相互一致，均为 exited/0。这些是**准备方保存的实际 Docker 观察记录**，不是我重新查询 Docker 的结果。证据见[Kev4 Docker记录](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/closeout/kev4.json:1664)、[Kev9 Docker记录](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/closeout/kev9.json:1431)及[closeout退出记录](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/closeout/CLOSEOUT_CONTAINER_EXIT.json:2)。

**独立重算结果如下，均与保存报告一致：**

| 模型 | 原生温度 | 正确数／完整分类数 | 完整准确率 | 有效分类准确率 | Raw summed Brier | ECE10 | Score MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kev-4B | 2.406050072164233 | 6,741／10,938 | 61.629183% | 68.015336% | 0.436118754 | 0.173661124 | 0.914080878 |
| Kev-9B | 2.193649959389252 | 6,931／10,938 | 63.366246% | 69.932398% | 0.406847145 | 0.109838099 | 0.923336991 |

每模型共有10,938个分类行，其中9,911有效、1,027超长；完整准确率将全部超长行计错。有效分类准确率、Brier、ECE仅覆盖9,911行。Score为319/319有效，MAE使用原始等级单位。Choice 为9,582行、8,625有效，正确数分别5,640／5,825；noul为1,356行、1,286有效，正确数1,101／1,106。

我从 gold 和回执重新计算了每模型全部 **66个单元：63个 source/type 单元及3个 type 单元**，逐项核对人数、正确数、完整／有效准确率、MAE、不同概率向量数和 flags；与 hardened、closeout、源结果 JSON 全部一致。完整单元保留于[Kev4 cells](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/kev4/hardened/HARDENED_AUDIT.json:57)与[Kev9 cells](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/kev9/hardened/HARDENED_AUDIT.json:57)，没有筛除失败来源。

响应与计分约定也逐条检查：

- 保存的 Kev logits 标记为 `already_scaled`，重建 softmax 时不再次除温度；与 native probabilities 的最大绝对误差分别约 `1.79e-7`、`2.14e-7`。
- Wire 概率、noul、expected score及 confidence 符合原生四位小数规则；choice依据原生概率选择答案，score使用期望等级。
- Brier直接使用返回概率，不重新归一化；noul重建为 `[1−p,p]`。实际 choice/score wire 概率和并非总为1，这与舍入约定相符。
- Choice confidence按机会水平调整：`(max(p)/sum(p)−1/K)/(1−1/K)`，随后四位舍入；noul使用所选二分类概率。ECE使用 `min(floor(10c),9)`，内部精确边界进入右侧箱。两模型分别存在10／9个内部边界样本，已按此规则处理。

这些是[预注册的本地响应约定](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/source/JEVAL-REFERENCE-INFERENCE-2026-10-30.md:50)，不能称为论文 scorer 的精确复现。

**全部 flags 保留如下，合计 Kev-4B 8个、Kev-9B 7个：**

| 单元 | 必须保留的 flags／指针 | Kev-4B | Kev-9B |
|---|---|---|---|
| finqa-yes-no／noul | `small_population`：`/cells/27/total`；`small_valid_population`：`/cells/27/valid` | 18/22正确；2 flags | 19/22正确；2 flags |
| helmet／choice | `exact_boundary_rate`：`/cells/36/valid_accuracy` | 有效50/50；完整50/200；1 flag | 同左；1 flag |
| jevbench／score | `small_population`：`/cells/39/total`；`small_valid_population`：`/cells/39/valid` | n=16，MAE 0.296950；2 flags | n=16，MAE 0.26825625；2 flags |
| longbench-retrieval-en／choice | `small_valid_population`：`/cells/49/valid`；`exact_boundary_rate`：`/cells/49/accuracy` | 有效0/200；完整准确率0，valid accuracy=null；2 flags | 同左；2 flags |
| longbench-retrieval-en-e／choice | Kev4：`exact_boundary_rate`，`/cells/50/valid_accuracy` | 有效100/100；完整100/200；1 flag | 有效99/100；完整99/200；无此flag |

原 flags 及继承字段见[Kev4:47](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/closeout/kev4.json:47)、[Kev9:47](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_kev49_candidate_20261031/closeout/kev9.json:47)。两者 `inherited_review_flags=[]` 与原生 finisher 一致。原生主面板只对总体分类准确率恰为0或1设flag；hardened增加子单元、小样本和恒定输出检查。因此主面板零flags不表示子单元风险已解除。

对可疑成功的进一步检查显示：两模型 helmet 各有50个不同请求、50个不同原生及wire概率向量，答案分布在6个候选位置；Kev4 retrieval-en-e 有100个不同请求和概率向量，答案覆盖16个候选位置。全部答案均与 logits／概率重建及 gold 比较一致。因此，**在所保存证据内，未发现回执缺失、恒定输出或计分损坏造成这些有效子集满分**。但有效子集受原生预算选择，且本次没有训练语料证据；这些检查不排除训练污染或记忆。

可发布的精确声明是：**在固定 JEVal 原始11,257行、既定原生上下文预算和发布温度下，Kev-4B／Kev-9B 获得上述本地原生响应公式指标；完整分类准确率包含超长行计错，校准指标仅覆盖有效分类，所有66个单元及8／7个审查flags保留。**

本裁决不支持论文 scorer 精确复现、广泛泛化、无污染、paired consistency、训练或业务收益、资源释放或训练准入声明；没有新增 raw-T1、NOTA、排列或配对一致性面板，也没有修改历史证据。