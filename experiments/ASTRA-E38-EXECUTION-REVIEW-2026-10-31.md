# E38 两尺寸 exact-plan 执行闭包：实际 Astra 审查

实际 `codex exec --model gpt-6-astra --sandbox read-only` 审查已完成，runner和实际子进程退出均为0。记录时间：2026-10-30T22:50:28.813722+00:00。**实际结论为 BLOCK：两份冻结v2计划均不得按当前字节启动。** 需修复四项P1及明确中断恢复语义，生成新代次后重新审查。本记录不生成批准文件，也未启动NPU。

审查针对以下冻结计划，其原文件与副本在审查后重新核验，SHA均未改变：

| 模型 | plan SHA-256 |
| --- | --- |
| Open-Jev-2B | `14b95a2f9c4f8c25aecd46c01077d2f94045d926c43b0535abd6bbd5ee81662f` |
| Open-Jev-9B | `0f839e1153a968f81c8033ff2463c982648ffc8152e381ef369eda6303c198b5` |

冻结包：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2`。含434个清单文件，审查后逐项大小/SHA验证通过。MANIFEST SHA：`37c512e5d9279edf8942ebb20e318735e1ed5f02d28c148cfb2be95bdb5b4da4`。
原始审查SHA：`702e9f6cd1b7e177d91e10c9fbd4a263a157d1839104b0abc219973ad98f6ced`；runner终态SHA：`f65bcb843222680a14c1ab1bdc487901baf1da6bf19f77c11b1fa149083dad9e`。

外部权重文件9项未重复复制或重新哈希；其expected hashes与CPU preparation full_closure_verified来源明确保留。完整路径、实际CLI/终态、遗漏清单及原文见[JSON](ASTRA-E38-EXECUTION-REVIEW-2026-10-31.json)。这些审查不改变E36 admission=false，也不证明完整JEVal、kernel因果或训练收益。

记录者说明：原文末尾所称“无法归档”指reviewer自身处于只读沙箱。外层CLI `-o`与detached runner已保存原文、实际退出和终态；记录者已完成434文件及两计划、终态输出的哈希复核。该限制原文保留，不冒称reviewer写了审批文件。

以下为实际Astra原始报告全文，逐字保留。

---

审阅结论：**BLOCK，两份冻结计划均不应按当前字节启动。** 已确认 native 回答契约不兼容、畸形回执误接受、trace 合同不完整及文件读取竞态。以下结论来自冻结包字节核验、源码审查和纯内存反例，不是依据 PASS 标签推断。

实际审阅的计划：

| 规模 | 冻结包内计划 | 实测 SHA256 |
|---|---|---|
| 2B | [plan.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v2/plan.json) | `14b95a2f9c4f8c25aecd46c01077d2f94045d926c43b0535abd6bbd5ee81662f` |
| 9B | [plan.json](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev9_20261031_v2/plan.json) | `0f839e1153a968f81c8033ff2463c982648ffc8152e381ef369eda6303c198b5` |

原始路径分别为 `/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev{2,9}_20261031_v2/plan.json`。复制文件中的原始绝对引用保持原样，读取通过 PATH_MAP 映射。

MANIFEST 实测 SHA256 为 `37c512e5d9279edf8942ebb20e318735e1ed5f02d28c148cfb2be95bdb5b4da4`，与指定值一致。434 个包含文件的大小、哈希全部匹配；无额外或缺失文件。2B 的 196 项计划依赖中，193 项实际字节通过、3 项权重省略；9B 为 193 项通过、6 项权重省略。九项省略权重的预期哈希与计划一致，**未读取或重新哈希权重**。

1. **P1：验证器错误拒绝正确的 native choice 回答，直接阻塞正常完成。**

   [verify_openjev_path_trace.py:78](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v2/verify_openjev_path_trace.py:78) 要求 `confidence == probabilities[choice]`。但冻结 native 实现使用：
   \[
   confidence=(p_{\max}-1/K)/(1-1/K)
   \]
   见 [metrics.py:69](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_test_20261030_v3/code/jev/metrics.py:69)。此外，[api.py:108](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_test_20261030_v3/code/jev/api.py:108) 会重新归一化 wire probabilities，验证器却要求它们与归一化前的 `native_probabilities` 完全相等。

   最小实际反例：2B 的 E37 `4200_original_0`，所选 ACD 的概率为 `0.1964647970946813`，native confidence 为 `0.1390694254585871`；9B 对应值为 `0.23613964640709884` 和 `0.1815781925790345`。两种规模各四份实际 index4200 回执全部被当前 `check_prediction` 拒绝为 `Invalid native wire prediction`。

   完整运行在 driver 第269行调用该验证器；恢复也会先验证已有回执。因此这是执行契约缺陷，不能靠实际 NPU 前向解决。需要独立重建被冻结的 native 格式化语义，并加入两种规模实际 E37 回答的回归检查。当前测试夹具将 confidence 人为设为选中概率，正好复制了错误假设。

2. **P1：内部重新计算封装哈希后，无效概率和错误决策仍能通过。**

   同一验证器第67—82行检查有限性和单值范围，却没有验证概率归一化、native 温度下的 logits→probabilities 关系，以及 native 的 argmax／并列选择规则。

   已执行纯内存反例：保留实际计划身份、完整八任务和有效封装哈希，将所有概率改为零、confidence 改为零，八份回执全部通过，重建结果为 `trace_valid=true`。另一个反例使用非 argmax choice，并让非均匀概率对应全零 logits，同样通过全部11项 controls。

   需要独立验证这些数值与 wire 关系，不能仅验证八次结果彼此一致。修复不得放宽重复、hook 或 trace 的精确比较要求。

3. **P1：trace 合同没有冻结逐事件布局、dtype 和实际执行顺序。**

   [openjev_path_trace_run.py:87](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v2/openjev_path_trace_run.py:87) 生成的合同只有层数、事件列表和模块列表。[verify_openjev_path_trace.py:46](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v2/verify_openjev_path_trace.py:46) 对执行顺序只检查集合及跨 chunk 一致性；形状只要求正整数，dtype 接受四种浮点类型。

   已复现：保持全部696个事件和每事件15个候选哈希，将所有 traced 回执统一改为 `row_shape=[1]`、`torch.float64`，并反转执行顺序，仍被接受为 `trace_valid=true`。这会使“第一个 observed divergence”的顺序依据失去独立约束。

   应从固定 native 实现和模型配置冻结逐事件的执行顺序、dtype、布局及 folded 映射，并由 producer、verifier 分别校验。事件注册列表不能直接充当实际执行顺序。

4. **P1：完成验证存在可复现的单次文件替换竞态。**

   [verify_openjev_path_trace.py:190](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v2/verify_openjev_path_trace.py:190) 先解析 report，随后才读取输出哈希和建立 `committed` 基线。解析对象与被承诺的字节没有绑定。

   在纯内存文件系统中执行原始 `verify_complete`：稳定存在的错误报告被正确拒绝；但在报告读取返回后仅替换一次文件，把 `original_untraced_repeat.logits_max_delta` 改为 `999`，并使 terminal 引用替换后字节，验证器仍用旧对象通过重建，最后返回错误报告的 SHA256。测试仅替代外部权限、容器及依赖检查，没有调用 Docker。

   修复应从同一次读取的字节完成解析和哈希，并对这些确切字节建立、复核承诺；文件类型与 symlink 检查也应绑定实际打开的对象。仅在解析之后增加前后哈希不能修复这个窗口。计划、terminal、review 等同类读取也需一起审查。

5. **P2：NPU publication-gap 无恢复路径；八份回执不能证明总共只执行八次前向。**

   [openjev_path_trace_run.py:276](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v2/openjev_path_trace_run.py:276) 发布 report 后，才在 finally 发布 COMPLETE。若其间被终止，[prepare_openjev_path_trace.py:502](/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/e38_execution_candidate_20261031_v2/files/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev_path_trace_openjev2_20261031_v2/prepare_openjev_path_trace.py:502) 因 report 已存在而拒绝恢复。CPU preparation 有报告发布后的恢复处理，NPU driver 没有。这里是安全拒绝造成的恢复限制，不是证据覆盖。

   另一个窗口是前向已完成、item 尚未提交。恢复会归档下一项 `.tmp` 并重新执行缺失任务，因此最终八份回执只证明八个已提交任务，不证明累计八次实际前向。若要求严格八次，应将这种不确定尝试判为失败 generation；或明确登记尝试历史和恢复语义。报告发布后的收尾应走独立、无新增前向的恢复审计，保留原有失败／中断证据。

其余关键检查结果如下：

- **协议与来源正确绑定。** 两份计划均固定4200、15×186、正确八任务顺序；候选顺序为 `A,B,C,D,AB,AC,AD,BC,BD,CD,ABC,ABD,ACD,BCD,ABCD`。未发现按标签重新选择任务。2B／9B 分别绑定正确 E37 配置；native temperature 为 `1.518796342858676`／`1.8969118766347646`。
- **完整 mask 已独立重算。** 15行长度为十二行185、三行186；补齐到186后的全部 mask 行哈希匹配。request、候选顺序、token hashes 与相应 E37/eligibility 记录一致。计划保存完整 padded ID 行哈希，但本机缺少 tokenizer、PyArrow 依赖，因此未重新分词、重算 ID 行哈希。
- **插桩主路径符合设计。** pre/post hooks 不返回替换值；GDN wrapper 原样返回原始结果 tuple；嵌套为 input guard→trace_path→candidate_chunks(observer)，没有第二次手工 splitting。正常及异常退出均有恢复 hooks/core/forward 的 finally。每个 untraced baseline 也经过同一个完整输入 guard。native load 使用 eval、BF16 backbone／FP32 head，forward 使用 inference mode、`use_cache=False`。
- **资源与恢复基本防线存在。** launcher 检查精确 parent/independent plan references、CPU preparation 实际退出、固定 spec、allocation ownership 和锁；仅允许chip0—5，明确排除6/7，并检查 Docker 与成功的 npu-smi 空闲查询。创建容器后的 receipt gap、分配后 start gap 有恢复分支；信号恢复绑定 container ID、FinishedAt 和 EXIT hash。两份具体计划都选择chip4，不能据此同时启动。E38 路径未自动释放实验资源。
- **科学边界保持正确。** E36、E37 报告和两份 E38 计划均保留 false admission。精确 control 失败的纯内存检查得到 `trace_valid=false` 和非空 `review_flags`，状态为 `COMPLETED_SCOPED_REVIEW_REQUIRED`，不会因执行 rc0 被升级为有效 trace。

本次实际完成的检查包括：434文件哈希／大小与完整目录清单核验；全部计划非权重依赖交叉绑定；两种规模共32份 E37 item 封装核验、各13项比较独立重算并与报告完全一致；CPU request、launch receipt、terminal、report、EXIT 和准备审计绑定；219个 Python 文件内存编译、41个 shell 文件仅语法检查；六个纯 CPU 合同测试全部通过；上述畸形回执和单次替换竞态反例。

额外尝试的宿主 softmax 精确重算**没有全部通过**：当前 Python 3.11.6 与固定镜像运行时不同，最大绝对末位差分别为 `1.11e-16`、`2.22e-16`。这没有被解释为 NPU 差异，也没有通过放宽阈值转成通过结果。

`PARENT-CHECKABLE-EVIDENCE-v2.json` 的修正成立：两份计划的 canonical input 实测摘要都是 `bb54ecd6f4dafbda582b4a81a5b9c9a68fc3b1a8f62f7b455f51506bb807c0bb`；v1 确实错误重复各自 plan digest，且被保留。它属于已说明的摘要记录错误，未发现源计划因该修正而变化。

v3 fixture 的13项 source manifest 全部匹配，三个测试文件合计定义65个测试。归档 `VERIFICATION.json` 声明65 pass、0 skip，退出与终端哈希绑定正确；但快照未包含逐项测试日志，本次未独立重跑固定镜像的65项测试，因此不能把该声明提升为本次亲验。CPU preparation 的 `actual_exit=0`、`full_closure_verified` 同样是已核对绑定的历史 provenance，不是本次重新检查 Docker 或权重的结果。

启动前仍必须：修复上述四项 P1，明确中断／publication-gap 处理；以新 generation 冻结源码、测试、计划和哈希；在固定镜像中补做 native 回答、畸形重哈希回执及文件竞态测试并保留逐项结果；重新完成精确计划审阅。实际资源释放、chip4 所有权和新鲜占用检查必须在随后获授权的启动流程中完成，本次未认证。

未执行启动／恢复命令，未访问 live Docker、NPU、外部权重或资源分配文件，未创建审批。最初默认登录 shell 曾产生 netlink 权限拒绝信息，随后读取均改为非登录 shell。

**归档要求尚未完成：当前沙箱全盘只读，无法创建、冻结并哈希本报告及 reviewer runner terminal 文件。** 本回复和工具输出保留了阻断结论及失败检查，但不能冒称已经生成冻结审阅工件。审阅完成不构成启动授权，也不改变 E36 admission=false。
