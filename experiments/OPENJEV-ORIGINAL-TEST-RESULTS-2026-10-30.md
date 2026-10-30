# Open-Jev 原始完整 test 本地复测

2026-10-30 17:48 UTC。2B 的公共推理、176 行补测、逐项身份合并及独立重算均完成；9B 仍在公共推理。原数据 SHA256 `fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b`，10,532 行＝10,046 hard＋486 soft。此表可以对照上游原始 test，不能与公共投影 10,356 行直接相减。

| 来源／温度 | hard accuracy % | expected accuracy % | NLL | soft-target Brier | expected Brier | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 上游 2B／原生 T | 94.714314 | 91.952536 | .195380034 | .076116976 | .104167940 | .011605590 |
| 本地 2B／原生 T | 94.634680 | 91.876577 | .195621588 | .076288049 | .104339013 | .012282068 |
| 本地 2B／raw T=1 | 94.634680 | 91.876577 | .213531433 | .080689145 | .108740110 | .024149612 |

原生 T=1.518796342858676。hard accuracy 分母 10,046，其余列分母 10,532；ECE15 的正确性为目标分布在预测类别上的质量。上游答对 9,515 个 hard，本地 9,507 个，少 8 个；不能称数值完全复现。差异尚未定位到上游逐项预测，不归因硬件，也不从差异中推断训练收益。

公共部分覆盖 10,356 行，补测覆盖原位置缺失的 176 行；合并按原有序身份与内容检查，没有重抽样或重复计数。公共运行、补测均保留容器且退出 0；补测结构化终态 17:41:34 UTC、wrapper 17:41:39 UTC；自动合并 `JOIN_COMPLETE.json` 于 17:42:33 UTC 成功。父代理在 17:48 UTC 核查原计划与输出哈希、组件身份及补测容器，队列 2B 已 `complete`，9B 仍 `waiting_public`。

合并状态保留 `VERIFIED_ORIGINAL_TEST_REVIEW_REQUIRED`：公共组件的两个标记以及完整表相应标记均保留。customer-control hard 574／574、但包含 32 条软目标；trex 仅 4 行、答对 1 行。详见[限定范围诊断](OPENJEV2-PUBLIC-FLAG-REVIEW-2026-10-30.md)。审查标记并不由合并或总分稀释消除；尚无 Astra 实质放行或新训练收益。

证据目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_original_test_join_20261030/`。

- 合并 report SHA256：`63896d28aeecdc6f95d02c4e8783eaf949b034c102e4688c4b5e89f8c557853d`。
- 合并逐项结果 SHA256：`ed79e8a9dee667557603ef61f5bdc61402fc083daf936a17bb6bbf227cb708b6`。
- 补测 report SHA256：`7815eb127d1e1ee4350eb8525597659e8933632ba56508d64571aa3a44521db4`。
- 上游 `reports/full-data-eval-n1-v1/2b-audit.json` SHA256：`e8b0583b12ee00e8031e7ea5388d935389c3ce9681e3099da0cafe30329ff472`，取 `metrics.test.probability_metrics_all_rows`；原始数据哈希与本地一致。

OOD 15,920 行已恢复但本轮尚未推理，不能用本表补齐 OOD 成绩。原 native 模型/接口/温度和双分区合并协议见 [E24](../wiki/E24-openjev-original-test-supplement-20261030.md)。

18:03 UTC 对照补充：[checkpoint 与原提示核查](OPENJEV2-ORIGINAL-COMPARISON-2026-10-30.md)已验证五个 checkpoint 文件逐字节匹配上游 audit，原始与当前源码在完整 test 上生成的 30,570 个候选提示相同。源码版本仍有差异；已枚举的可读镜像未找到上游逐项预测，搜索有权限错误且未递归符号链接，故不作绝对不存在判断。净少 8 个正确回答不等于已定位恰好八次翻转。
