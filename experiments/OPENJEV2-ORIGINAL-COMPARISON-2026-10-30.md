# Open-Jev-2B 原始 test 与上游对照核查

2026-10-30。此项是保存结果的只读对照，不启动新模型推理，不改原实验。机器证据见[JSON](OPENJEV2-ORIGINAL-COMPARISON-2026-10-30.json)，复算工具为 [compare_openjev_reference.py](../tools/compare_openjev_reference.py)。

## 已建立的对应关系

原始 test 数据 SHA256 与上游相同，覆盖全部 10,532 行、10,046 个 hard labels。模型为 Qwen3.5-2B，base revision `15852e8c16360a2fea060d615a32b45270f8a8fc`；温度 1.518796342858676。上游 `2b-audit.json` 的五个 `package_bound_inference_files` 与本地冻结 checkpoint 全部逐字节匹配：adapter config、adapter weights、head、model config、temperature。

原 evaluation commit `99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e` 不在当前浅镜像可用对象中。另一个公开目录 `reports/full-data-eval-expansion-n1-v1/pinned-source/` 的 api、model、data、metrics、serving 文件逐一匹配原 audit 的源码 SHA256，因此可作为原始源码的有依据副本。当前运行的 data／metrics 与它相同；api／model／serving 字节不同，不称为相同源码版本。

对全部 10,532 原始记录分别应用原始和当前 `candidate_prompts`，**30,570 个候选 prompt 完全一致**。两个函数都只从其已核查 AST 提取后执行，未运行下载目录入口脚本。原 api 的变化在 `compile_request` 对部分 noul descriptions 的接受条件；本轮原始 test 已经是编译好的记录，直接 forward，不经该编译函数。此结论只针对本次完整原始 test 的实际 prompts。

model 的主要差异是增加量化、分片、meta/offload 支持和参数加载保护。冻结驱动明确清除量化／device map 环境开关，并设置 BF16、单 NPU、SDPA、unmerged adapter。当前非 meta forward 保留相同 tokenizer/padding 和末有效 token readout；新增显式设备搬移。这个静态检查不证明库、kernel 或数值等价，不能据此把差异归因于 Ascend。

## 数值差异

| 指标 | 上游原生温度 | 本地原生温度 | 本地−上游 |
| --- | ---: | ---: | ---: |
| hard correct／10,046 | 9,515 | 9,507 | −8 |
| hard accuracy | .947143142 | .946346805 | −.000796337 |
| expected accuracy | .919525356 | .918765767 | −.000759590 |
| NLL | .195380034 | .195621588 | +.000241554 |
| soft Brier | .076116976 | .076288049 | +.000171073 |
| expected Brier | .104167940 | .104339013 | +.000171073 |
| ECE15 | .011605590 | .012282068 | +.000676477 |

本地 9,507 hard correct 从合并的原顺序 logits 与原数据独立计算，不只读取汇总。−8 是净正确数差，**不等于已经定位八次翻转**；可能存在双向翻转。

## 尚缺的逐项证据

上游 audit 记录了 `merged-test.jsonl` 的 SHA256 `b6065d9478107f73eca1d0e45a1cc383c5603245f77f56ee46f0ad12825422a2`，大小 12,554,388 bytes。capture 脚本指定保存到忽略的 `runs/full-data-eval-n1-v1/2b/`；公开 compact audit 仅保留摘要。搜索 `omni/` 以及另一个 models／repos 镜像和 experiments 树，未定位这个文件。搜索范围、枚举数量与读取错误数保留在 JSON；这不证明文件在所有外部位置不存在。

因此当前不能列出上游与本地逐题翻转、tie margins 或概率距离；不访问原作者脚本中另一个私有主机来弥补缺口。checkpoint 相同、输入 prompt 相同，支持按原 test 和公式报告差异，但不支持数值完全复现、硬件因果归因或新训练收益。原审查标记仍保留；本文不是 Astra 审查放行。

175 上可复算脚本与 report 保存在 `reference_inference/openjev2_original_comparison_20261030/`，原运行目录只读。首次 175 检查因主机未安装 `rg` 未产生报告；增加文件枚举 fallback 后重试，保留完整搜索边界。
