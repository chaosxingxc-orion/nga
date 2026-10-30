# 参考模型推理队列：可执行入口、分区与下一步

日期：2026-10-30。性质：执行队列与已核对的运行快照（最新 16:29 UTC），不替代每次实验的预注册。
遵循 D1：参考模型 test 指标先汇报，不同方法分开统计；实际推理继续自动执行，新训练方案随后讨论。
“完整交叉评测”范围尚未得到用户答复，当前先完成文献直接对应组合，并准备共同公开测试集。

## 1. 排队顺序及可交付范围

| 优先级 | 模型 × 数据 | 当前依据／可执行下一步 | 完成后能够声称什么 |
| --- | --- | --- | --- |
| P0 | Kev-0.8B／4B／9B × decision-v7／transfer-v4 | 三个尺寸均完成两套完整 test 及独立核对；9B 于 15:37 UTC 完成自动后处理验收 | 相同官方 test、原生 pointer head、发布温度下的本地复测；raw T=1 单列 |
| P0b | Kev-0.8B／4B／9B × hard-v1／documents-v1／devtools-v1 | E20 的 0.8B 两套扩展 test 已完成；4B／9B 继续运行。E22 CPU 队列已在前驱完成后自动启动 0.8B devtools，其余等待各自依赖 | 具体 suite 的完整本地复测；devtools 完整 1,073／release 1,071 分母分列 |
| P1 | Open-Jev-2B／9B × release-v2 公共投影 test | 两尺寸原生 scalar-head 合成探测与完整长度预检已完成；均已启动完整 **10,356** 行公共 test；两尺寸的独立 CPU 后处理均已启动等待终态 | 公共投影上的新本地结果；不能直接称为已发布 **10,532** 行完整 old test 的复现 |
| P1b | Open-Jev-2B／9B × 完整 old test／OOD | E23 已完成原数据恢复，五个 split SHA 与 original manifest 匹配；下一步单独预注册缺失 176 行的推理及精确身份合并；完整 OOD 另列 | 才能与原 **10,532 test／15,920 OOD** 总体指标同分母比较；test 与 OOD 各自报告 |
| P2 | 初始 Bespoke-Nimble-9B × 原文七个真正 test 子集 | 原 revision 已恢复，七子集 1,884 行最终哈希与 IDs 全匹配；最长 1,356 tokens，原生 NPU 正式推理已启动。初版冻结恢复检查的限制见 E19，完成后须独立重算 | 文献对应 test 子集复测；不能把原 3,880 行混合分区总数当 test |
| P3 | 已跑通原生接口的模型 × JEVal／typed-decisions | 用现有完整公开 test 形成共同评测面，先冻结 adapter、字段映射、无效输出计分和原生方法；独立记录新 protocol | 同一公共任务集下的新跨模型比较，不冒称复现各模型自家内部 test |

P1 与 P2 的适配／数据核验可以在 Kev 正式推理运行时并行推进。缺少某个完整数据分区不会阻断其他已经就绪的组合。
本队列不把文献摘表当实际推理，也不要求无意义地反复推理：已有同配置逐项预测可以按不同公式重算。

## 2. Kev 直接执行入口

- 模型目录：`/mnt/cephfs/xingchao/omni/models/jev/jaredpalmer__kev-{0.8b,4b,9b}/`；基座还要核对 `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-{0.8B,4B,9B}-Base/` 与 `omni/models/jev/`。
- 原生源码：`/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev/kev/{checkpoint,predictors,benchmark,metrics}.py`。
- 数据：`/mnt/cephfs/xingchao/datasets/jev/jaredpalmer__kev-suites/v7/decision-v7/` 和 `v4/transfer-v4/`。
- decision 完整 1,176 records／1,440 questions，clean 主表 1,200；transfer 完整 764 records/questions，clean 主表 656。
- 不把原生 pointer readout 换成 NGA label-logprob；保持 option order，permuted／NOTA 单独统计。服务温度与 raw T=1 是设置差异，不是两种 Brier 公式。

2026-10-30 15:37 UTC 追加：0.8B／4B／9B 均已完成上述运行及独立核对。下一步推进 Open-Jev 与 Nimble，而非重复完成的 Kev 单元。

**2026-10-30 15:54 UTC 纠正库存遗漏：** hard-v1、devtools-v1、documents-v1 完整 dev/test 实际在 Kev 源码仓库的 `evals/<suite>/` 下，此前只看数据镜像而漏报。三个 test 均已逐字节核对 manifest 的 SHA256。不是缺少题目，应该进入后续实际推理队列。

| suite | 完整 test records／questions | test SHA256 | 运行前需要保留的区别 |
| --- | --- | --- | --- |
| hard-v1 | 700／1,088 | `246ee92234d33f8e3f10ac6e1542651531b128fd7cc66f3a9964589b77dfa22b` | 所有 ID 唯一；使用该 suite 的 7,552 state／9,216 packed context，不套 decision-v7 限制 |
| documents-v1 | 574／936 | `742d04a1abc2207bd3e4f24b281f483cdc69238e4da747cbbc3774e836f2e557` | 所有 ID 唯一；8,192 state／16,384 packed context，先验证长输入内存与吞吐 |
| devtools-v1 | 900／1,073 | `2fb7c2a239fef923bcb62c0eee9d6884a608ce30e5e74a4e6b9082787679767f` | 有两个内容不同的记录共享同一 ID；文献 release 排除这两行，headline 为 1,071 问题，不能混同完整分母 |

devtools-v1 test 第 571／623 行（1-based）共享 `codereviewer/cls-test/19245`，均有 `needs_comment` 问题，但记录不相同。原 `scripts/build_devtools_v1.py:38–46` 说明历史 ID 碰撞；三个 release spec 的 `drop_ids` 都包含该 ID 和 dev 中的另一个碰撞 ID。`scripts/release_numbers.py:42–45` 在计分前应用 `drop_ids`。因此需要保留按行位置和内容哈希区分的完整推理，再分别报告全部 1,073 问题与按原 release 排除后的 1,071；不能静默删题，也不能强行放宽现有 driver 的唯一 ID 检查而不修正结果身份。硬件探测和该协议修订在正式运行前登记。

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

**2026-10-30 15:58 UTC 身份纠正：** 原列 `/mnt/cephfs/xingchao/omni/models/jev/bespokelabs__Bespoke-Nimble-9B/` 虽无版本后缀，实际是 v3-12026（schema v2），不是初始公共 benchmark 的模型。不得以目录名代替 release 身份。

已恢复文献命令明确指定的初始 revision `594dfdcfb6f94e3d0c0db7535180d3c71689169a` 到隔离目录 `reference_inference/nimble_initial_inventory_20261030/adapter/`，七个必需文件逐一匹配该 revision 的 SHA256SUMS。adapter 权重 SHA256 为 `ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b`；v1 schema、2,676 训练行。原镜像未覆盖。详情见 [Nimble 执行前检查](NIMBLE-REFERENCE-PREFLIGHT-2026-10-30.md)。

这是 adapter，不是现成 merged backbone；基座为 Qwen3.5-9B Instruct revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`。E16 四个合成 fixture 各跑两次，结构化终态已为 rc=0；不把此探测算成七个公共 test 的成绩。

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

本文件记录队列与执行快照；实际运行由各 E 系列预注册约束。原始模型／数据未覆盖，NGA 尚未准入或锁定候选 test 不因参考队列而自动解锁。

**2026-10-30 16:29 UTC 更新：** E23 原始完整分区恢复已经完成，详情见 [恢复记录](OPENJEV-ORIGINAL-RESTORE-2026-10-30.md)。初始 Nimble 七个 test 子集也已恢复到原 manifest 哈希并正在执行；上文关于最初没有 `data/public/` 的描述是盘点历史，不是当前缺失。当前下一步是完成正在运行的参考推理、自动独立验收及 Open-Jev 补充协议；不新增正式训练。

**2026-10-30 16:36 UTC 更新：** Kev 三尺寸 hard／documents 已完成并通过 scoped 独立审计；devtools 三尺寸均已由队列自动启动，0.8B 已完成双分母审计，4B／9B 仍运行。Nimble 推理已完成 1,884 行，但 E21 独立审计失败，待诊断与重新验收。Open-Jev 两尺寸仍在运行；E24 补充 176 行 test 的协议与实现正在准备，尚未启动。下一步先完成这些推理与审计，之后再提交训练方案讨论。初版 E22 队列异常会停止整个调度器，恢复需核对已启动容器和资源归属，不能宣称通用故障恢复已完成。

**16:55 UTC 执行更新：** E24 CPU 队列已启动并检查公共依赖；公共预测与 176 条补测将按原身份合并，组件审查标记不会丢失。共同集合已完成[具体 schema／指标预检](COMMON-REFERENCE-EVALUATION-PREFLIGHT-2026-10-30.md)。下一项是 typed-decisions 原生 Kev adapter 与全量 token 预检，JEVal 原 scorer 同步核查；不是新正式训练，尚无共同集合推理分数。
