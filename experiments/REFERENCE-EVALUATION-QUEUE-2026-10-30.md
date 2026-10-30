# 参考模型推理队列：可执行入口、分区与下一步

日期：2026-10-30。性质：本地只读盘点形成的执行队列，不是已经运行的结果，也不替代每次实验的预注册。
遵循 D1：参考模型 test 指标先汇报，不同方法分开统计；实际推理继续自动执行，新训练方案随后讨论。
“完整交叉评测”范围尚未得到用户答复，当前先完成文献直接对应组合，并准备共同公开测试集。

## 1. 排队顺序及可交付范围

| 优先级 | 模型 × 数据 | 当前依据／可执行下一步 | 完成后能够声称什么 |
| --- | --- | --- | --- |
| P0 | Kev-0.8B／4B／9B × decision-v7／transfer-v4 | 复用 `tools/reference_kev_eval.py` 与独立 verifier；0.8B／4B 已完成，9B 正式全量已启动。按各 run 终态核实，不以本文件冻结运行状态 | 相同官方 test、原生 pointer head、发布温度下的本地复测；raw T=1 单列 |
| P1 | Open-Jev-2B，然后 9B × release-v2 公共投影 test | 先做 2B 原生 scalar-head loader 的 Ascend 适配和开发集探测；解压现有原生 JSONL，核验 export manifest；跑完整 **10,356** 行公共 test | 公共投影上的新本地结果；不能直接称为已发布 **10,532** 行完整 old test 的复现 |
| P1b | Open-Jev-2B／9B × 完整 old test／OOD | 查找本地 Wikispeedia archive；若可得，按固定源哈希和恢复工具重建缺失行；完整 split SHA 必须与 original manifest 一致，再跑或复用身份完全一致的公共行 | 才能与原 **10,532 test／15,920 OOD** 总体指标同分母比较；test 与 OOD 各自报告 |
| P2 | 初始 Bespoke-Nimble-9B × 原文七个真正 test 子集 | 先还原相同 ids/checksum 的公开子集，适配原生候选 token scorer 到 NPU，并验证 prompt/schema；初始 checkpoint 优先，v2/v3 另行标记 | 文献对应 test 子集复测；不能把原 3,880 行混合分区总数当 test |
| P3 | 已跑通原生接口的模型 × JEVal／typed-decisions | 用现有完整公开 test 形成共同评测面，先冻结 adapter、字段映射、无效输出计分和原生方法；独立记录新 protocol | 同一公共任务集下的新跨模型比较，不冒称复现各模型自家内部 test |

P1 与 P2 的适配／数据核验可以在 Kev 正式推理运行时并行推进。缺少某个完整数据分区不会阻断其他已经就绪的组合。
本队列不把文献摘表当实际推理，也不要求无意义地反复推理：已有同配置逐项预测可以按不同公式重算。

## 2. Kev 直接执行入口

- 模型目录：`/mnt/cephfs/xingchao/omni/models/jev/jaredpalmer__kev-{0.8b,4b,9b}/`；基座还要核对 `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-{0.8B,4B,9B}-Base/` 与 `omni/models/jev/`。
- 原生源码：`/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev/kev/{checkpoint,predictors,benchmark,metrics}.py`。
- 数据：`/mnt/cephfs/xingchao/datasets/jev/jaredpalmer__kev-suites/v7/decision-v7/` 和 `v4/transfer-v4/`。
- decision 完整 1,176 records／1,440 questions，clean 主表 1,200；transfer 完整 764 records/questions，clean 主表 656。
- 不把原生 pointer readout 换成 NGA label-logprob；保持 option order，permuted／NOTA 单独统计。服务温度与 raw T=1 是设置差异，不是两种 Brier 公式。

2026-10-30 追加：4B 已完成运行及独立验收；下一步完成 9B 对应运行及独立验收。hard-v1、devtools-v1、documents-v1 可列后续覆盖，但本次没有确认这三者完整本地 test 文件，不以存在报告推定能运行。

## 3. Open-Jev：可运行的模型与不可混同的分母

精确模型入口为：

```
/mnt/cephfs/xingchao/omni/models/jev/ZefanCai__Open-Jev-2B/package/checkpoint/
/mnt/cephfs/xingchao/omni/models/jev/ZefanCai__Open-Jev-9B/package/checkpoint/
```

目录含 `model.json`、`head.pt`、`temperature.json`、`adapter/adapter_model.safetensors` 和 adapter config。
不要把模型仓库根目录误传成 checkpoint 目录。原生实现是
`/mnt/cephfs/xingchao/omni/repos/jev/Zefan-Cai__Open-Jev/jev/model.py` 的 `DecisionModel.load`；其接口是独立候选 scalar head，不能套用 Kev pointer-head loader。
读取 checkpoint 的 base ID/revision 后在两套镜像查找**完全对应**基座，不能用同尺寸 Base 自动替代 Instruct。

原始计分可参考同 repo 的 `scripts/evaluate_internal_full.py`、`scripts/evaluate_internal_shard.py`、
`scripts/evaluate_checkpoints_parallel.py`。但原完整执行器固定 N1 主机、CUDA 0–3 和四 rank，**不能直接在 175 上运行原命令**。
应冻结原生 model／encoder／metrics，仅把设备与调度适配为既有 Ascend 容器和本项目资源契约；写独立 NPU wrapper，保留超长失败、不截断。

现成本地数据：

```
/mnt/cephfs/xingchao/omni/datasets/jev/ZefanCai__Open-Jev/raw/release-v2-redistributable/test.jsonl.gz
/mnt/cephfs/xingchao/omni/datasets/jev/ZefanCai__Open-Jev/raw/release-v2-redistributable/ood.jsonl.gz
```

对应 parquet 为 `data/release-v2-redistributable/{test,ood}-00000-of-00001.parquet`；其 `record_json` 保留原记录。
优先解压 raw 到新的实验目录，对照 `export-manifest.json` 的 `raw_uncompressed_sha256`，不修改镜像。
公共 test **10,356**、OOD **15,701**，分别比旧完整集合少 **176／219** 个 Wiki 行。
原文 2B／9B hard accuracy 的完整 test 分母是 **10,046**，另有 **486** 个 soft-target 行，不能把它搬给公共投影。

**2026-10-30 实际数据核验更新：** 已将 public test 原 gzip 解压到
`reference_inference/openjev_public_inventory_20261030/test.jsonl`，逐字节 SHA256 与 export manifest
一致（`0c4b953282a4292272110536ca543fe6e2736ab729b81d9b0464dd8ab4eec86a`）。10,356 条 ID 全唯一，
split 全为 test，source 计数与 manifest 一致；one-hot 硬标签 **9,995**，软标签 **361**。
来源 hash、计数和公开投影限制已记录到同目录 `VALIDATION.json`。这是数据校验，不是推理成绩；
未更改原始镜像、未重新采样，也未把缺失 Wiki 行补成零。

原协议逐 decision row 加权，硬标签 accuracy 只统计 one-hot targets；soft 行仍进入 expected accuracy、NLL、Brier／expected Brier，ECE 使用 15 个 top-label bins。完整输出必须同时记录 total/hard/soft/failed 数量。
test 的 `accuracy_all_rows_failures_incorrect` 字段名具有误导性，不能凭名字认定分母就是 total_count。

恢复完整旧集合的现成入口：

```
.../ZefanCai__Open-Jev/reproduce/source-code/jev/case_wikiracing.py
.../ZefanCai__Open-Jev/reproduce/restore_original_mixture.py
.../ZefanCai__Open-Jev/REPRODUCTION.md
.../ZefanCai__Open-Jev/provenance/original-manifests/release-v2.json
```

Wikispeedia 源 archive SHA256 为 `97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5`。
先搜本地；该工具按原位置插回 Wiki 行并验证完整 split 哈希。没有恢复到原哈希，就明确报告公共投影新结果。
`Open-Jev-v1.1` 是另一扩展版本，不能拿它的分区混充 2B／9B 的旧完整 test。

## 4. Nimble：先锁初始 checkpoint 与温度，恢复真正的 test 子集

模型：`/mnt/cephfs/xingchao/omni/models/jev/bespokelabs__Bespoke-Nimble-9B/`。
这里是 adapter，不是现成 merged backbone；含 `adapter_model.safetensors`、`schema_config.json`、`serving_config.json`、`temperature_config.json`。
v2、v3 目录同时存在，但不能把初始模型的文献成绩贴到 v3。

代码根：`/mnt/cephfs/xingchao/omni/repos/jev/bespokelabsai__nimble/`。执行链：

1. `nimble/scoring/merge_local_adapter.py`，传本地 adapter 和明确 revision 的本地 base；它会检查 schema 与 prompt 的匹配。
2. `nimble/datasets/public_benchmarks.py` 与 `public_sources/` 重建子集；对齐 `docs/assets/public-benchmarks/subsets/*-manifest.json` 的 ids 和 checksum。
3. `nimble/evaluation/evaluate_public.py`，输入 `<subset>/all.jsonl`，保留 `model-id`、`revision`、temperature、2048 token 限制和原生 schema。

现成 backend 仅 `mlx|cuda`；`nimble/scoring/cuda_scorer.py` 明确调用 `torch.cuda.is_available()`、CUDA 放置和同步。
需要独立 NPU scorer 适配并验证候选 token projection／prompt，不可只把 CLI 的 backend 改名就声称等价。

原文真正 test 子集如下，合计 **1,884 records**：

| 子集 | n | 分区依据 |
| --- | ---: | --- |
| massive-en-US | 350 | MASSIVE test |
| massive-de-DE | 350 | MASSIVE test，与 en-US 相同 ids |
| paws | 250 | labeled_final test |
| civil_comments | 300 | test |
| aegis2 | 250 | test，原人审／红删／token 规则 |
| summeval-relevance | 240 | test，完整 article families |
| summeval-consistency | 144 | test，完整 article families |

BoolQ／SQuAD2／HelpSteer2 是 validation，MultiNLI／VitaminC 是 dev，PubMedQA 是 train 抽样；它们可另报，但不纳入此 test 表。
本次所查 repo 的 `data/` 仅见 train/eval/manifest，未见已重建的 `data/public/`；其他本地 Jevify 集合虽有 MASSIVE／PAWS／Civil Comments，但不能自动替换原 ids、原格式和原人类标签分布。
需要先比对 raw source 与 pinned subset manifests，缺失才补下载或恢复，不重新抽样。

**原文公共 benchmark 使用 T=1.0**；2.179078721266035 是后来拟合温度，文档明确当时没有在这些子集重跑。
因此第一张本地对齐表用 T=1.0；可以从同 logits 另算发布温度，但分列标新统计。
`data/eval.jsonl` 的 324 个合成例子可作初始版本单独 holdout，不能把它当上述公共 test 的代用品。

## 5. 共同公开测试集的后续入口

- JEVal：`/mnt/cephfs/xingchao/omni/datasets/jev/carlosxiang__JEVal/data/test.parquet`，完整 11,257 条，classification 10,938／score 319。集合自己的 split 为 test，但 `source_item_id` 仍可能来自上游 test/dev 等；同时保留两层分区语义。ACC 无效回答计错，概率指标有效回答分母另列。
- typed-decisions：`/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/all/test-00000-of-00001.parquet`；官方 400 states×5 questions=2,000。原 scorer 位于 `bench/score_with_jobs.py`；软标签 Brier 与 Kev one-hot Brier分开。

这两个共同评测面有完整现有数据，优于拿不可取得的私有 benchmark 填空；但跨模型 adapter 尚未核验，不能把它们写成已就绪的推理命令。先各跑开发／合成接口探测，固定 mapping 和无效处理，再运行完整分区。没有官方 dev 时，接口测试用不进入正式成绩的合成 fixture，不从 test 试到满意后再声称未见。

## 6. 每个队列单元的交付要求

运行前：精确 model revision、数据 split hash、原生 prompt/readout、温度、计分公式、无效与超长策略、预期分母、资源和wiki预注册。
运行中：175 上 retained detached container，逐 item receipt 和恢复，CephFS heartbeat／每chip吞吐／reserved memory；修复效率问题后再开展受影响的全量运行。
运行后：完整终态、独立主要指标重算、逐项／分母核对、与文献差异及适用范围。主表逐格区分文献值、上游重算、本地推理；没有原始题目或权重的格注明缺失，不填零。

本文件只新增队列分析，未启动任务、未修改原始模型／数据，也未读取 NGA 尚未准入或锁定候选 test。
