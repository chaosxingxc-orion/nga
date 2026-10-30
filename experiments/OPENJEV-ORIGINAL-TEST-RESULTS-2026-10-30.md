# Open-Jev 原始完整 test 本地复测

2026-10-30 17:48 UTC 初版，18:41 UTC 更新：2B／9B 的公共推理、各 176 行补测、逐项身份合并及独立重算均完成，审查标记保留。原数据 SHA256 `fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b`，10,532 行＝10,046 hard＋486 soft。此表可以对照上游原始 test，不能与公共投影 10,356 行直接相减。

| 来源／温度 | hard accuracy % | expected accuracy % | NLL | soft-target Brier | expected Brier | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 上游 2B／原生 T | 94.714314 | 91.952536 | .195380034 | .076116976 | .104167940 | .011605590 |
| 本地 2B／原生 T | 94.634680 | 91.876577 | .195621588 | .076288049 | .104339013 | .012282068 |
| 本地 2B／raw T=1 | 94.634680 | 91.876577 | .213531433 | .080689145 | .108740110 | .024149612 |
| 上游 9B／原生 T | 97.541310 | 94.715318 | .130947153 | .039112900 | .067163865 | .007706544 |
| 本地 9B／原生 T | 97.511447 | 94.686833 | .130800630 | .039047204 | .067098168 | .007524828 |
| 本地 9B／raw T=1 | 97.511447 | 94.686833 | .138525373 | .040875415 | .068926379 | .011593197 |

原生 T=1.518796342858676。hard accuracy 分母 10,046，其余列分母 10,532；ECE15 的正确性为目标分布在预测类别上的质量。上游答对 9,515 个 hard，本地 9,507 个，少 8 个；不能称数值完全复现。差异尚未定位到上游逐项预测，不归因硬件，也不从差异中推断训练收益。

公共部分覆盖 10,356 行，补测覆盖原位置缺失的 176 行；合并按原有序身份与内容检查，没有重抽样或重复计数。公共运行、补测均保留容器且退出 0；补测结构化终态 17:41:34 UTC、wrapper 17:41:39 UTC；自动合并 `JOIN_COMPLETE.json` 于 17:42:33 UTC 成功。父代理在 17:48 UTC 核查原计划与输出哈希、组件身份及补测容器，队列 2B 已 `complete`，9B 仍 `waiting_public`。

合并状态保留 `VERIFIED_ORIGINAL_TEST_REVIEW_REQUIRED`：公共组件的两个标记以及完整表相应标记均保留。customer-control hard 574／574、但包含 32 条软目标；trex 仅 4 行、答对 1 行。详见[限定范围诊断](OPENJEV2-PUBLIC-FLAG-REVIEW-2026-10-30.md)。审查标记并不由合并或总分稀释消除；尚无 Astra 实质放行或新训练收益。

证据目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_original_test_join_20261030/`。

- 合并 report SHA256：`63896d28aeecdc6f95d02c4e8783eaf949b034c102e4688c4b5e89f8c557853d`。
- 合并逐项结果 SHA256：`ed79e8a9dee667557603ef61f5bdc61402fc083daf936a17bb6bbf227cb708b6`。
- 补测 report SHA256：`7815eb127d1e1ee4350eb8525597659e8933632ba56508d64571aa3a44521db4`。
- 上游 `reports/full-data-eval-n1-v1/2b-audit.json` SHA256：`e8b0583b12ee00e8031e7ea5388d935389c3ce9681e3099da0cafe30329ff472`，取 `metrics.test.probability_metrics_all_rows`；原始数据哈希与本地一致。

18:41 UTC 更新：OOD 两尺寸的 15,920 行正式推理及验收器已在运行，尚无最终成绩，不能用本表补齐 OOD。原 native 模型/接口/温度和双分区合并协议见 [E24](../wiki/E24-openjev-original-test-supplement-20261030.md)。

18:03 UTC 对照补充：[checkpoint 与原提示核查](OPENJEV2-ORIGINAL-COMPARISON-2026-10-30.md)已验证五个 checkpoint 文件逐字节匹配上游 audit，原始与当前源码在完整 test 上生成的 30,570 个候选提示相同。源码版本仍有差异；已枚举的可读镜像未找到上游逐项预测，搜索有权限错误且未递归符号链接，故不作绝对不存在判断。净少 8 个正确回答不等于已定位恰好八次翻转。

## 18:41 UTC：9B 原始完整 test 接续完成

E24 自动完成 176 行补测，于 18:39:16 UTC 按原始身份合并全部 10,532 行；队列自身、补测容器及 wrapper 均退出 0。父会话检查计划、配置、终态与全部输出哈希。9B 原生温度 1.8969118766347646；hard 本地 9,796／10,046，对照上游 9,799／10,046，净少 3 个正确回答，不能称已定位恰好三次翻转。概率指标有双向差异，不作硬件归因。

9B 合并保持 `VERIFIED_ORIGINAL_TEST_REVIEW_REQUIRED`，公共组件 8 个 flags 及完整表 8 个对应 flags 保留；补测自身独立审计无 flags。[定向诊断](OPENJEV9-PUBLIC-FLAG-REVIEW-2026-10-30.md)说明完美子集的合成／重复和场景组限制，不能据此宣称泛化或部署保证。

- join report SHA256：`24d88fe39bc8f3a897430ac025aec3706f48bf267862355c825c07c3f1fbb882`
- joined records SHA256：`edf73d9eb94fc47ff08b5a0a3bf2a03268c9f17d8d75317b6ee2658de6888e09`
- supplement report SHA256：`5c8a73e79729b8313d187a0874333ca4c5c7ffbd517929d6f21cea8085fdfc8d`
- 上游 `reports/full-data-eval-n1-v1/9b-audit.json` SHA256：`d490dd1636acebaf393fe181dfd0f65e66eb54edb7247b4abffd74a3d0891100`；原 test 数据 SHA 与本地一致，取 `metrics.test.probability_metrics_all_rows`。

证据目录：`reference_inference/openjev9_original_test_join_20261030/`。尚无新训练增益或 Astra 实质放行。
