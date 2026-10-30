# Kev-9B 扩展测试逐题差异核对

2026-10-30。只读复算，未运行新推理、训练或拟合温度。对应 E20／E22 已完成的原生参考推理；不是指定 Astra 的审查结论。

## 结论与范围

hard-v1 的 1,088、documents-v1 的 936、devtools-v1 的 1,073 个问题，全部按原始顺序核对 ID、问题名、候选顺序、标签、source、task、type、variant，以及 group／control／pair／sibling／parent 元数据。两个重复 textual ID 的 devtools record 均保留；release 仍按固定规则排除 record 570／622，得到 1,071 问题。记录／问题／flattened row 索引均从 0 开始。

**hard 与 devtools 各仅有一题 argmax 不同，均从上游错误变为本地正确；documents 没有 argmax 差异。** 同一问题身份及标签一致，并不证明上游当时的完整输入字节与本地相同：上游 rows 不保存原始输入哈希。本地记录另与当前原始 test 元数据／内容哈希绑定。微小概率差和接近并列的候选解释了翻转位置，但不足以归因到某个硬件、算子或驱动。

## 温度及独立核对

上游三套 rows 的 `inference_temperature` 均为 1；本地保存的是发布温度 2.193649959389252 下的 logits／概率。依据固定原生代码 `kev/metrics.py:224–254`，记录的 logits 已除以温度，先乘保存温度恢复，再除目标温度。因此不能直接拿上游 raw 概率与本地 serving 概率做差。

本工具以独立 stdlib softmax 在 T=1 和发布温度分别比较；上游全量 accuracy 与原 report 相符，上游 release 的 accuracy／Brier／ECE 与发布 JSON 相符（概率指标误差小于 1e-10）。本地 accuracy／分母与独立审计完全一致；从保存 logits 重建概率与保存的 FP32 概率重归一化有舍入差，主要指标差值约 1e-10，逐项值保留在机器报告。检查上限 1e-6，不改变任何实验计分协议。

| suite | population | n | 目标温度 | 上游 accuracy | 本地 accuracy | argmax 翻转数 | 最大候选概率差 | ECE10 跨 bin 数 |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| hard-v1 | release | 1088 | raw_T1 | 0.833639705882 | 0.834558823529 | 1 | 0.006628449076 | 2 |
| hard-v1 | release | 1088 | serving | 0.833639705882 | 0.834558823529 | 1 | 0.003117616145 | 1 |
| documents-v1 | release | 936 | raw_T1 | 0.899572649573 | 0.899572649573 | 0 | 0.004087415934 | 2 |
| documents-v1 | release | 936 | serving | 0.899572649573 | 0.899572649573 | 0 | 0.002347347849 | 0 |
| devtools-v1 | full | 1073 | raw_T1 | 0.790307548928 | 0.791239515377 | 1 | 0.003109969721 | 3 |
| devtools-v1 | full | 1073 | serving | 0.790307548928 | 0.791239515377 | 1 | 0.001669792698 | 0 |
| devtools-v1 | release | 1071 | raw_T1 | 0.790849673203 | 0.791783380019 | 1 | 0.003109969721 | 3 |
| devtools-v1 | release | 1071 | serving | 0.790849673203 | 0.791783380019 | 1 | 0.001669792698 | 0 |

## 翻转题的完整定位

| suite | record / question / row 索引 | ID / question | 标签 | 上游 → 本地 | serving 上游 top1−top2 | serving 本地 top1−top2 |
| --- | --- | --- | --- | --- | ---: | ---: |
| hard-v1 | 309 / 1 / 476 | `hard-v1/long_policy/test/00020` / `amount` | b | e → b | .000133152169 | .000783159688 |
| devtools-v1 | 111 / 0 / 135 | `prompt_injection/deepset/train/109` / `injection` | true | false → true | .000551987901 | .000332087266 |

hard 翻转题 T=1 的上游／本地 top margin 为 .000340459504／.002001741676；devtools 为 .001210867767／.000728483116。两题均不在 release 排除名单。`prompt_injection/deepset/train/109` 的上游来源名称包含 train；它在 Kev 的 test 分区，不能改写为原始来源的 test。

## 可复核产物

机器报告：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev9_extended_row_comparison_20261030/report.json`。

SHA256：`6ee6dff9ed85340f4962228ba9c80e1c1e0a9b89f769eb41b93b1a828e9b6eec`。

报告保存全部源文件路径／SHA256、按序身份摘要、排除位置、两个温度的完整翻转记录和概率、发布值核对及本地重建舍入差。工具为 [compare_kev9_extended_rows.py](../tools/compare_kev9_extended_rows.py)，五项有效温度／重复 ID／错序／候选改序／ECE 边界测试通过。

```bash
python3 -P tools/compare_kev9_extended_rows.py --out /path/to/new-report.json
```

工具拒绝覆盖已有报告。未声称全部数值等价、硬件因果解释、训练收益或 Astra 放行。
