# Nimble 初始参考模型：身份纠正与执行前检查

2026-10-30。当前任务是恢复文献对应版本并执行原生参考推理；不是新训练。

## 1. 本地别名不能代表初始模型

两套本地镜像的 `bespokelabs__Bespoke-Nimble-9B/` 虽无版本后缀，实际都是
**v3-12026**：`provenance.json` 指定 release v3，权重 SHA256 为
`29ef39b072dee97287947455337879c1e916705c2f727287922a2d81f5e2f20a`，schema v2，12,026 训练行。
此前队列把该路径作为“初始 checkpoint”的入口不充分，不能用它对齐初始模型的公共 benchmark。

上游 `docs/PUBLIC_BENCHMARKS.md:301` 的执行命令明确指定 revision
`594dfdcfb6f94e3d0c0db7535180d3c71689169a`，其 adapter SHA256 为
`ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b`，schema v1，2,676 训练行，2048 上限。
该权重也对应后续校准文档中的 `93ec5d6…`，但公共 benchmark 使用 **T=1.0**。
这里恢复原 benchmark 命令指定版本，不将后续 fitted T=2.179078721266035 当作原成绩设置。

已通过现有 HTTPS 代理恢复七个必需文件到隔离目录：

```
/mnt/cephfs/xingchao/experiments/jev/reference_inference/nimble_initial_inventory_20261030/adapter/
```

`DOWNLOAD_VERIFIED.json` 记录每文件字节数、下载耗时和哈希；所有文件逐一匹配该 revision 的
`SHA256SUMS`。约 173 MB adapter 下载耗时 17.44 秒。旧镜像未覆盖。
基座 `Qwen/Qwen3.5-9B` revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`
已在两套本地镜像，`.complete` 与 adapter config 一致；不能替换成同尺寸 Base 模型。

## 2. 原生执行路径与正在进行的探测

原生路径为：保存的 schema/prompt contract → 独立完整 prompt → BF16 merged backbone →
最后 token hidden state → LM head 对应候选 token 行的 **FP32 projection** → T=1 softmax。
这不是 Kev pointer head，也不是 Open-Jev scalar head。

新 [E16](../wiki/E16-nimble-native-probe-20261030.md) 使用四个预先固定的合成 fixture，各执行两次；
保存原 prompt token 哈希、候选 token IDs、logits、概率、每 chip 吞吐、reserved memory 和
同 hidden state 的 CPU FP32 projection 差异。只适配设备和同步，不替换 prompt/readout。
初始 adapter 身份检查会拒绝当前 v3 别名。测试覆盖身份正反例与无效概率。

探测目录 `reference_inference/nimble_initial_probe_20261030/`，175 chip 3，固定 retained container
`nga-reference-nimble-initial-probe`。15:56 UTC 已完成八次推理，正式终态、wrapper 和 Docker
退出均为 0，136 个冻结文件和八个 receipt 哈希已复核。加载合并 35.68 秒，reserved 18.2051 GiB。
重复 logit 差 0，同 hidden 的 CPU projection 最大差 4.3869e-5；不推定 CUDA/NPU 等价。
吞吐记录存在已注明的计时范围差异，详见 E16，不能把探测耗时外推为完整测试性能。
合成探测不能当作公共测试成绩、硬件数值等价或训练收益。

## 3. 七个真正 test 子集

| 子集 | n | 原生数据完整性依据 |
| --- | ---: | --- |
| massive-en-US | 350 | 原 MASSIVE 1.1 tar 源哈希；manifest 固定 ids |
| massive-de-DE | 350 | 与 en-US 同 ids，保留 locale |
| paws | 250 | labeled_final test；固定 ids、原 converter |
| civil_comments | 300 | test 原人类标签分布；固定 ids |
| aegis2 | 250 | test，原人审／过滤及 token 规则 |
| summeval-relevance | 240 | test，完整 article families，原 tokenizer 长度规则 |
| summeval-consistency | 144 | test，完整 article families，原 tokenizer 长度规则 |

总计 **1,884**；不能拿包含 validation/dev/train 抽样的 3,880 行总表当全 test。
全部七份原 manifest 在上游 `docs/assets/public-benchmarks/subsets/`，包含 ids、source_sha256
与 dataset_sha256。已找到其他本地 Jev 数据中的 MASSIVE／PAWS／Civil Comments 转换行，
但它们不是已验证的原输入，未直接替换。必须恢复 raw source，经原 converter 按 manifest ids 取出，
完整输出 dataset_sha256 对齐后才进入文献对应正式推理。缺失 raw source 不填零、不重采样。

后续先完成原生探测，再恢复七个子集、冻结数据与计分协议，执行完整分区并独立重算。
本文件没有声称数据恢复或正式测试已完成。

## 4. 2026-10-30 原测试数据恢复与正式执行

七个子集共 **1,884 行**已恢复到 `reference_inference/nimble_public_restore_20261030_v2/`。
每个 `all.jsonl` 的 SHA256 和有序 IDs 均与原 manifests 完全一致，父目录
`RESTORE_COMPLETE.json` 为 rc 0；独立二次核对通过。MASSIVE、PAWS、Civil Comments、SummEval
的原 converter 输入 source SHA256 也与原文相同。Aegis 从 pinned revision 的 JSON 数组导出，
中间 JSONL 字节不等于历史 parquet 导出（显式记录 `original_export_byte_equal=false`），
但最终固定 250 行数据逐字节完全相同；不将这个源格式差异隐藏或称原始源文件完全复现。
选择只使用原 manifest IDs、保留完整 families，没有重新抽样或根据标签选择。
正式推理前将对全部原 prompt 再检查 2048 token 限制。

第一次下载容器因 CA 信任缺失和超时失败，原目录及容器保留；其结构化恢复终态 rc 1
优先于错误返回 0 的旧 wrapper。v2 使用现有可信 CA bundle，不关闭 TLS 校验，并修正
不完整恢复的进程返回码。下载与转换均在 retained CPU 容器完成，没有占用 NPU。

[E19](../wiki/E19-nimble-public-test-20261030.md) 已预登记，正式推理容器
`nga-reference-nimble-public-test` 在 175 chip 3 启动，目录
`reference_inference/nimble_public_test_20261030/`。149 个输入与执行文件冻结；五项 receipt
负例/正例测试通过。完整测试成绩和独立指标重算尚未完成，不能称为已复现文献指标。
