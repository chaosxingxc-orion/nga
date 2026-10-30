# JEVal Kev-0.8B / Nimble：实际 Astra 结果审查

记录时间：2026-10-30T22:19:39.125579+00:00。实际 CLI 使用 `codex exec --model gpt-6-astra --sandbox read-only`；runner 终态及 `Popen.wait` 实际子进程退出均为 0。模型身份指固定 CLI 请求与记录，不是服务端内部路由的额外证明。

本次仅审查已完成 E33 两模型的保存结果。下方原始审查给出具体结论及限制；运行成功不等于审查无问题，也不改变已有 6/30 个审计标记或原预注册。

- 冻结证据包：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031`。
- MANIFEST 文件 SHA-256：`a4f9ec8476dfca250244d1b6372467c1b1d1787de41874663a376a4e27cfca5d`。
- 包内 22,667 个文件在审查后逐一复核大小及 SHA-256，全部一致。
- Kev-0.8B 与 Nimble 各 11,257 条回执，共 22,514 条。
- 原始审查目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_astra_20261031`。
- 原始 review SHA-256：`a2bbbd95d1627b1196347d0aaa5ce8a89009499e6cd80c9484abb55ee5d946f9`。
- COMPLETE SHA-256：`175a06b43d67a35a070d4ad6ec8ae3c38f8e90a11217bb5f117df18d273e2030`。
- CHILD_EXIT SHA-256：`a17b052586af0f2343d9086b0aa9aca560555b9b2ffbe6674f44b32440a4e5a3`。
- 完整机器记录：[JSON](ASTRA-JEVAL-RESULTS-REVIEW-2026-10-31.json)。

**记录者勘误（2026-10-31）：** Astra 发现冻结 closeout README 将 Nimble 的 2,253 条 unsupported 全部归为候选超限；实际为 2,047 条候选超限、206 条空 context。记录者再次逐条统计确认，并在 [E33 wiki](../wiki/E33-jeval-reference-inference-20261030.md) 追加带日期勘误。指标、预测、冻结包及 6/30 个 flags 均未改动。Astra 的结论是更正原因表述后支持限定发布，原报告完整保留如下。

原始 closeout 目录已新增可追溯勘误 `/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_results_closeout_20261031/ERRATUM-20261031.md`，SHA-256：`73a81a296f3dc39acd61303023b671e2bea7f8ff342b33c8002db537d5781015`。主结果报告原先只写 unsupported，计数没有错误；新增原因分项说明并未改变原冻结数据。

以下为实际 Astra 原始报告全文，逐字保留。其文件引用指向冻结证据包。

---

本次独立复核的结论是：**指标数值与逐题证据通过复算，支持作为有界参考指标发布；现有发布说明须先更正一项 unsupported 原因归类错误，不能原样无条件放行。** 两模型的审计状态均须保留为 `VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED`，Kev 的 6 个、Nimble 的 30 个 flags 均不得删除。

本次审查对象是**已经完成的 E33 JEVal 结果**，不是正在运行的 OOD 实验，也不是正式训练或训练收益验收。证据未被修改；未运行新推理、训练、重分词或新的 Docker 检查，未访问外部权重、网络、秘密或 NPU。

**优先级最高的实际发布阻断项，是 Nimble unsupported 原因的错误表述。** [closeout/README.md:14](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/closeout/README.md:14) 将 2,253 条全部称为 candidate-limit；独立逐条统计实际为：

| Nimble 状态／原因 | 数量 |
|---|---:|
| valid | 8,006 |
| unsupported：`native_v1_candidate_limit_26` | **2,047** |
| unsupported：`native_nonempty_context_required` | **206** |
| overlength：`native_prompt_limit_2048` | **998** |
| 合计 | **11,257** |

206 条空 context 来自 `ai2-arc-challenge` 95 条、`ai2-arc-easy` 111 条。我核对了这些行的原始 state 确为空、候选数不超过 26；例如 [receipt 000201:1](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/nimble/inference/records/000201.json:1) 明确记录 4 个候选及 `native_nonempty_context_required`。这也符合[资格检查源码:44](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/source/jeval_reference_preflight.py:44)规定的原因优先级。

因此，必须保留“**2,253 条 unsupported、998 条 overlength**”的覆盖限制，但不能把前者全部归因于候选上限。这项错误不改变总体准确率、有效分母或其他主指标。应在发布文本中更正或附勘误，保持原冻结证据不变。

我实际完成了以下检查：

- **全量清单认证。** 逐文件重算全部 **22,667** 个 manifest-bound 文件的 SHA-256 和字节数，核对完整文件集合；没有缺失、额外文件、重复清单路径或符号链接。另行重算 `MANIFEST.json`，得到指定值 `a4f9ec8476dfca250244d1b6372467c1b1d1787de41874663a376a4e27cfca5d`。
- **逐题身份认证。** 两模型各有且仅有 `000000.json` 至 `011256.json` 的 11,257 条 receipts。逐条核对 envelope 哈希、index、原始 ID、完整 gold 行输入哈希、请求哈希、配置哈希，以及 E31 eligibility 中的来源、类型和 source-item 身份。原始人口为 choice 9,582、noul 1,356、score 319，无掉行或重复身份。
- **独立计分。** 使用 `python3 -P` 的独立 CPU 计算，从 `data_rows.json` 的 gold 和实际返回答案重算主指标、每模型 66 个聚合单元、全部 flags，以及 flagged population 的实际记录集合与原因分布，未调用原审计器的 PASS 作为替代。
- **原生输出交叉验证。** 对 Kev 全部 10,230 条、Nimble 全部 8,006 条有效输出检查 logits→概率、候选顺序、概率范围、返回字段、答案、confidence、score 和 consumed-token 哈希。最大 softmax 差分别约为 `1.44×10⁻⁷`、`2.28×10⁻⁷`，均在冻结校验容差内。非有效记录未伪造预测。
- **认证链。** 重算 ordered receipt manifest 及其根哈希，核对 inference terminal、report、config、launch/wrapper、finisher audit、hardened audit、closeout 与结果汇总的绑定。每模型 closeout 的 12 项文件哈希均匹配；Nimble ACCEPTED 中 13 项绑定均匹配。保存的退出状态与身份记录相符，但这是静态证据核对。
- **flag 与汇总一致性。** hardened audit、closeout、结果 JSON 中的指标、单元和 flags 相符；结果 JSON 对诊断中的逐题索引列表作首尾／数量压缩，压缩内容也与原列表一致。

两份 Parquet 均匹配协议数据哈希；提取 JSON 及其与 Parquet 的绑定匹配 [EXTRACT_COMPLETE.json:2](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/EXTRACT_COMPLETE.json:2)。**本地没有 PyArrow，因此未独立重新解码 Parquet**；本次 gold 复算依据的是经过清单和提取记录认证的 `data_rows.json`。

重算指标如下，报告、finisher、closeout 与结果汇总一致。Brier 的独立浮点累加与报告最大差约 `2.4×10⁻¹⁵`，不影响任何公布位数。

| 指标 | Kev-0.8B | Nimble v1 |
|---|---:|---:|
| 完整分类人口 | 10,938 | 10,938 |
| 分类正确数 | 5,089 | 5,394 |
| **完整分母准确率** | **46.525873%** | **49.314317%** |
| 有效分类数 | 9,911 | 7,694 |
| valid-only 准确率，仅描述性 | 51.346988% | 70.106577% |
| valid-only raw summed Brier | 0.598302104 | 0.433576240 |
| valid-only ECE10 | 0.163216356 | 0.135360806 |
| 有效 score／完整 score 人口 | 319／319 | 312／319 |
| valid-only 原尺度 MAE | 1.121768025 | 0.842948718 |

直接证据为 [Kev report:1](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/kev08/inference/report.json:1)、[Nimble report:1](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/nimble/inference/report.json:1)。按类型复算也匹配：Kev choice 为 4,070／9,582、noul 为 1,019／1,356；Nimble 分别为 4,381／9,582、1,013／1,356。

公式符合[冻结协议:56](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/source/JEVAL-REFERENCE-INFERENCE-2026-10-30.md:56)及[计分源码:21](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/source/jeval_reference_inference.py:21)：

- 分类以实际 choice 或 `noul ≥ 0.5` 判定；unsupported／overlength 在完整分类分母中按错误计入。
- Brier 使用原始 wire 概率的 one-hot 平方误差之和，不重新归一化；noul 重建 `[1−p,p]`。
- ECE10 使用 Kev 的 chance-adjusted choice confidence、Nimble 的 selected probability，以及 noul 的已选二元概率；采用 `min(int(confidence*10),9)` 分箱。
- Kev 保留四位小数原生响应，score 是期望等级；Nimble score 是选中的整数等级。MAE 使用原始等级单位，不除以 `K−1`。
- Brier／ECE 只覆盖有效分类行，MAE 只覆盖有效 score 行。它们不能替代完整分母准确率，也不能被解释为相同有效人口上的受控模型比较。

**全部 36 个 flags 均已逐项复核，未发现需要清除的标记。** 标记规则见[审计源码:402](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/source/audit_jeval_inference_hardened.py:402)，完整列表分别位于 [Kev audit:45879](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/kev08/hardened/HARDENED_AUDIT.json:45879) 和 [Nimble audit:45880](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/nimble/hardened/nimble_hardened/HARDENED_AUDIT.json:45880)。

| 模型／cell | 核对结果 | 保留 flags |
|---|---|---|
| Kev 27，finqa-yes-no | 有效 22／22，正确 15 | 总人口小、有效人口小，共 2 |
| Kev 39，jevbench score | 有效 16／16，MAE 0.4365375 | 总人口小、有效人口小，共 2 |
| Kev 49，longbench-retrieval-en | 有效 0／200，全部 overlength | 有效人口小、完整准确率边界，共 2 |
| Nimble 4、8、29、36、45、49、51、52、53、57 | 每 cell 均 0／200 有效，全部候选数超限 | 每 cell 2，共 20 |
| Nimble 48，longbench-lsht | 0／200 有效，全部 overlength | 2 |
| Nimble 50，longbench-retrieval-en-e | 0／200 有效；153 overlength、47 候选超限 | 2 |
| Nimble 20，CUAD | 有效 31／200，正确 31 | valid-only 准确率边界，1 |
| Nimble 27，finqa-yes-no | 有效 22／22，正确 18 | 总人口小、有效人口小，共 2 |
| Nimble 39，jevbench score | 有效 13／16，3 overlength；MAE 0.230769231 | 总人口小、有效人口小，共 2 |
| Nimble 46，lex-glue-scotus | 有效 8／200，正确 4，192 overlength | 有效人口小，1 |

上表 Nimble 的十个纯候选超限单元依次为 aida-testc、clinc150、go-emotions、helmet、lex-glue-ledgar、longbench-retrieval-en、longbench-retrieval-zh、longbench-trec、longbench-trec-e、nlu-eval-68。合计准确复现 **Kev 6、Nimble 30** 个标记。

这里必须保留两个容易被误读的结果：

1. **Kev 有 1,027 条 overlength。** `longbench-retrieval-en` 为 **200／200 overlength**，记录的 state 长度为 10,052–15,248，超过 8,192。该 cell 完整准确率为 0，**valid-only 准确率为 `null`**。Nimble 的 12 个零有效分类 cell 同样不能得到有效样本准确率或有效概率指标，不能把未定义值写成 0。
2. **Nimble CUAD 为有效子集 31／31，但完整 cell 为 31／200＝15.5%。** 另有 **169 条 overlength**。我核对了全部 31 条有效记录及其哈希：gold 为 29 false、2 true，预测全部匹配，31 个不同原生概率向量，noul 概率范围为 0.0002647662–0.9996658564，与 [CUAD 诊断:3](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/jeval_results_candidate_20261031/closeout/nimble_cuad_flag.json:3)一致。这支持有效子集上的观测事实，不支持“CUAD 全人口完美准确率”，也不能仅凭该检查证明没有训练重叠。

**其余发布边界属于必须随结果保留的限制，不要求为本次有界发布重新运行模型。** Kev 温度为 2.3510958125672174，预算为 8,192 state／branch、16,384 packed；Nimble 温度为 1、预算为 2,048 tokens、最多 26 候选且要求非空 context。unsupported 判定先于长度检查，不能推断这些行若解除候选限制就一定能放入上下文。

外部权重及外部原生依赖本次没有重新哈希；仅核对了包内副本和配置中保存的依赖绑定。保存的 Docker 成功记录没有被重新现场验证。包内记录了 closeout 脚本哈希但未提供该脚本，因此本次不声称重跑了 closeout；数值结论来自独立逐题重算。**本地 ECE、响应适配和公式约定不具备 paper-exact 等价性。**

允许发布的精确表述是：

> 在冻结 E33 协议、原生发布温度和原生预算下，对原始 JEVal 11,257 行完成了 Kev-0.8B 与初始 Nimble v1 的本地响应公式测量。每模型均保留 11,257 条身份绑定 receipts；完整分类人口为 10,938，准确率分别为 5,089／10,938＝46.525873% 和 5,394／10,938＝49.314317%。Brier、ECE10 与 score MAE 按各自有效人口报告。Kev 有 1,027 条 overlength；Nimble 有 2,253 条 unsupported，其中 2,047 条候选数超限、206 条空 context，另有 998 条 overlength。CUAD 的 31／31 仅适用于 Nimble 有效子集，完整 cell 为 31／200。审计状态保留 `VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED`，并保留 6／30 个 flags。

该表述必须同时注明：**没有测得 paired consistency，没有独立 raw-T1、NOTA 或 permuted panels；不支持训练增益、业务增益、业务就绪或精确文献复现声明。** 更正 unsupported 原因后，我支持以上范围内的参考指标发布。
