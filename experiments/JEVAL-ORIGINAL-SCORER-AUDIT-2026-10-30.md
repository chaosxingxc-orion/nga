# JEVal 原始论文计分与源码审计

2026-10-30。只读获取源码及论文，没有执行下载的 Python、模型推理或训练。此前共同评测预检中的“原 ECE／score 公式待核查”现已部分解决；**论文公式已取得，精确原测试 scorer 尚未取得**。本文件不修改任何已冻结实验。来源清单见 [JSON manifest](JEVAL-ORIGINAL-SCORER-AUDIT-2026-10-30.json)。

## 1. 固定来源与源码边界

- 论文：[arXiv 2610.03935v1](https://arxiv.org/pdf/2610.03935v1)，PDF SHA256 `7f9b996e30cc61898bd3e23836fea5717a9addf73aeb470643a5647ac5079e04`。
- 数据卡链接的 [InnerJev 仓库](https://github.com/amazingljy1206/InnerJev)，本次 HEAD 固定为 `1723d83cbda69f48641c273280b5a2d06d6b3510`。API 返回的 10 个提交显示仓库于后续提交更名为 SII-Decision。
- 所有来源保存在 `/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_scorer_audit_20261030/`，包含 GitHub tree/history、7 个静态源码文件、PDF、`pdftotext -layout` 文本及 SHA256。未运行下载代码。

[当前 evaluation.py](https://github.com/amazingljy1206/InnerJev/blob/1723d83cbda69f48641c273280b5a2d06d6b3510/sii_decision/evaluation.py#L1) 明确写“validation; no test inputs”。它在行 18–26 计算 score normalized MAE / soft-noul MAE，行 31–50 先 source 内平均、再 capability 内平均、最后 capability 等权；没有 JEVal 的 ECE/Brier。这是训练验证计分，不能拿它冒充 JEVal Table 1 的问题级测试计分。

## 2. 已由原论文明确的指标

论文 §4.1、公式 (4)–(6) 和 Appendix D 公式 (13)；本地 `paper.txt` 行 313–328、383–389、2389–2406。

| 指标 | 原始计算 | 分母及限制 |
| --- | --- | --- |
| classification accuracy | `100 × Σ(valid 且 returned_label == gold) / 10,938` | 包含所有 choice／noul；skip、最终失败、无效回答计错 |
| ECE | 10 个等宽 confidence bins；`Σ (n_bin/n_valid) × abs(acc_bin − mean_conf_bin)` | 仅有效 classification；精确边界归属尚无 scorer 源码证明 |
| raw Brier | `Σ_i Σ_k (p_ik − onehot(y_i)_k)^2 / n_valid` | 仅有效 classification；候选维度求和，不除 K；原始返回概率不重归一化 |
| score MAE | `Σ abs(returned_score − gold_score) / n_valid_score` | 319 个 score 中的有效回答；保留每题原始等级量纲，不除以 K−1；无效排除，不填补 |

不要把仓库 validation 的 normalized MAE 或 capability-equal score 代替 Appendix D 的 MAE。没有有效样本时应明确未定义，而非填 0；这属于本项目需预注册的实现边界，不冒称论文已有该分支实现。

## 3. 原响应校验及对统一 scorer 的影响

论文 Appendix C.2（`paper.txt` 行 2235–2251）明确：缺失／额外字段、重复 key、非有限值、非法候选、超范围值均无修复拒绝；**概率向量不归一化，也不因总和不等于 1 而拒绝**。具体含义：

- choice accuracy 使用 returned choice，不能改用概率 argmax；两者可能不一致。
- score MAE 使用 returned score，不能改成候选概率期望值。对本身定义为 expected readout 的决策模型，必须说明其原生输出就是期望值。
- 独立 confidence 字段不要求等于所选候选的概率；因此不能把所有模型 ECE 自动改成 `max(probabilities)`，精确采用哪个返回字段仍需原 scorer 证据。论文公式只称 confidence。
- noul 的二元预测规则在 Figure 12 明确为 `true iff noul >= 0.5`；这与 false 在先的 argmax 在精确 0.5 时不同。候选向量顺序仍须固定，不应靠字典重排解决。
- 对生成模型，解析最终 message.content，不解析 reasoning。只重试失败请求，保留首个有效响应。

当前共同评测如果同时给出“统一有效分布”统计，须与上述 paper-native 口径分列；额外要求概率和为 1、改选 argmax、重算 confidence、以 uniform 填缺失，都会改变论文的指标定义。

## 4. 原文模型／设置与当前队列不是全部相同

论文 Appendix C.3 / Table 9（`paper.txt` 行 2257–2304）记录 8×H100 与 vLLM 0.29.1rc1，决策模型保留 checkpoint 精度和 calibration，但显式调整输入预算：Kev 输入 24,576／context 32,768；Nimble 等从原 encoder 限制扩展到 24,576。OpenJev 还使用 24,000 字符窗口、2,000 字符 overlap。该段的 OpenJev 指论文 §4.1 脚注 5 的 **AlexWortega/openjev 4B v5**，不是当前 Zefan-Cai Open-Jev-2B／9B。

Table 9 的 Kev-9B 温度为 **2.2974**；当前本地 v2/r27 的冻结 checkpoint 温度为 **2.193649959389252**。温度差异足以证明配置不完全相同，但仅凭四位小数表不能推定原权重确切 revision。0.8B／4B 表中分别 2.3511／2.4061，与当前值四位小数一致也不足以证明权重相同。

因此后续 JEVal 应分清：

1. 论文原行：原模型版本／预算／响应计分，保留引用值。
2. 当前六个 checkpoint 在 JEVal 的新共同评测：明确本地版本、native budget 与新复测口径；不得称逐项重现论文所有原行。
3. 如要求严格复现指定论文行，另找 exact revision 和扩展 encoder／window 聚合源码。不能静默改当前原生协议来对齐分数。

初始 Nimble 的 26 候选限制与 JEVal 2,047 条超限仍是真实待解决的兼容性问题；论文中有 Nimble 行不证明当前初始 revision 可全量原生执行。应先确认论文模型版本和 adapter，再判断扩展实现。

## 5. 下一步与尚缺证据

已具备独立实现论文公式的依据：classification micro accuracy、10-bin ECE、raw one-hot Brier、native-scale score MAE，以及明确的 invalid 分母。启动前仍须冻结 ECE 边界实现及 confidence 字段选择；若无原 scorer，这两项标为本项目实现约定，不报告“完全源码等价”。

当前 GitHub tree 未提供 JEVal 测试 scorer，只有训练验证 scorer。无需因此停下已授权参考推理；可以先实现明确部分并保留结果来源标签。这里没有新的训练批准、业务依赖或训练收益声明。
