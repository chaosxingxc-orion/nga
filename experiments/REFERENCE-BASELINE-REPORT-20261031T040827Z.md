# 参考基线累计报告：9B 诊断审查通过，E40 v2 修复完成并实际复审

截至 20261031T040827Z（UTC）。本报告汇总已有参考读数和最新工程进度；历史报告仅供追溯。**metric values unchanged**：38 个登记组合仍为 36 个有结果、2 个 Open-Jev×JEVal blocked/null。正式 Jev 训练尚未启动。

## 本次完成的 milestone

实际 Astra 对 9B 的诊断结果和冻结资源证据给出有界 PASS，审查 SHA `585041194dfb17193fa679165431c0f4e1db18e693ff593893f2dd17480cce27`。审查核验全部 99 个包文件、8 个 item/8 个 attempt，重建 11/11 控制和完整 928-event 跟踪人口，确认两个重复的差异及仅 chip 4 的释放事务。主会话核验实际 child/runner 退出与 COMPLETE 输出哈希；审查者未查询实时 Docker，也未重验包外 192 个依赖。详见 [结果审查](ASTRA-E38-RESULTS-REVIEW-2026-10-31.md)。

9B 于 UTC 03:40:15 启动、03:44:24 NPU exited/0，8/8 项完成；独立 CPU verifier 于 03:45:29 exited/0。两次整批/分批的最大 logits/probability/wire 差为 `0.13169223070144653`、`0.013869159693189886`、`0.01485981395698921`，decision 未变，首个不同观测事件均为第一层 `in_proj_qkv:output`、15/15 候选不同。wire 最大差包含 confidence，并非单纯概率差。观察到的首差不是 kernel 因果证明。

2B 和 9B 均完成 guarded release，现场已核对 free=[1,4]；所有容器保留可查。`candidate_batch_admission=false` 和两个 JEVal null 保持不变。本轮未增加测试分数或训练收益。

E40 v1 的实际 Astra 审查为 **BLOCK**，该代次发现的五项问题现已形成修复：原生 `cu_seqlens=None` 调用兼容；bootstrap 前清理不可信 Python 路径并保留 CANN；统一各模式的 guard 开销；保存被拒绝 forward 的观测数据；修复已运行容器及 pending receipt 的中断恢复。旧 v1 未启动且保留，新 v2 计划已冻结并启动实际复审，未启动 NPU。[审查原文](ASTRA-E40-LIFETIME-V1-2026-10-31.md)。原文建议容器内 `-I`，但仓库明确要求保留 CANN PYTHONPATH；实施采用干净、显式的固定镜像路径并验证导入，不直接套用该建议。

独立 CPU 验证启动器已实现并完成 12 项测试；固定镜像无设备 retained fixture 实际 exited/0。它是启动器测试，不是 E40 模型推理或验证结果，Docker 生命周期响应仍为测试模拟。新代码尚需独立审查。

## E40 修复验证与复审状态

- 本地主会话重跑 12 项启动事务测试、14 项协议测试、7 项 AST 测试、12 项独立 CPU 验证启动器测试，均通过。启动事务测试使用真实持久化文件与模拟 Docker；不宣称真实设备故障恢复已测。
- 固定镜像 retained CPU runtime 容器完成 6/6 测试、无 skip。原生调用 AST 的完整 15×186×16×128 bf16 算术在 original/L1/L2/L1L2 输出字节一致，各一次公共 guard；它不是完整 transformer/checkpoint 推理。主会话独立检查保存文件哈希与真实容器 exited/0。
- 固定镜像 clean-startup v2 实际 exited/0，验证 `-S -s -P`、显式 image site-packages/CANN 路径能导入 Torch、GDN 和 tbe；v1 曾因 `.pth` 增加 `/opt/verl` 而失败，保留。尚未据此证明 NPU 动态算子编译。
- 原 CPU runtime fixture 之后增加 terminal 的 rejected_manifest 字段，相关本地负例测试重跑；不将旧 fixture 冒充最终驱动完整运行。
- 新计划 `e40_lifetime_npu_openjev2_20261031_v2/plan.json` SHA `fc119e89b508a11af34023c9a20cbbaaf8251b8bcb92deca102151d4bab644cd`。实际审查 runner `e40_lifetime_astra_20261031_v2`，bundle SHA `6b5ee438eef270aaad48354d8d29413dcd72f99c88114d5d7d34dc5a5de5bc54`；已核验 runner 1787901 与 child 1787902 存活，结论待返回。详细启动记录见 [v2 审查启动](ASTRA-E40-LIFETIME-V2-LAUNCH-2026-10-31.json)。

## 累计工程进度与剩余工作

2B E38 已完成并释放，其同类最大 logits/probability/wire 差为 `0.05192685127258301`、`0.00351450921098978`、`0.003765545583203328`。两尺寸都提示保留完整计算形状继续做内存优化。E39 已完成 28 个历史 Kev 面板的当前独立 CPU 重算，最大差约 `1.11e-16`，不补造历史终态绑定。

E40 的 L1/L2/L1L2 候选仅插入删除死引用的语句，7/7 结构测试通过；固定镜像 CPU 已完成 32 cells/256 forwards、输出字节 exact。NPU 驱动与计划 v1 已完成但被实际审查 BLOCK，五项代码问题已修复、v2 实际复审进行中；尚无 NPU 显存下降或吞吐改善结论。0.8B 三步训练入口预检已完成并释放 chip 1，不属于正式训练或收益。

本轮只实际使用 chip 4，**持续八卡满载尚未实现**。历史占用的只读核验发现部分任务已退出但未完成资源关闭，另有 created 容器和未证明完成的 suite/probe。空闲读数不能替代释放条件；CPU 工作不计作 NPU 利用率。当前有效计算准备的主要缺口是 E40 v2 审查结论及随后现场启动核验。当前没有运行中的本项目 NPU 容器，不能将审查及 CPU 工作算作 NPU 满载。

下一步：取得 E40 v2 实际审查结论，通过后现场核验并启动完整形状对照，在已登记空闲卡运行全形状对照；按实测数值与内存边界逐级扩大，必要时另立字节搬运实验。完整 JEVal 路径准入后执行两个剩余 test 组合，再讨论并冻结 Jev 训练方案、seed、对照与收益阈值。9B 最大实际输入的清理后某阶段仍约 59.4 GiB core-only，不能直接跳到 full-test。

## 已确定的决策

当前无需用户新增决策：范围固定 38 组合，不扩展；取消算力预算上限；真实业务/生产接入/业务标注暂不纳入；推理同样必须自动驱动、恢复、独立验收和释放；每个 milestone 更新累计报告。若保持原协议的内存路线最终不可行，再提交具体替代口径选择，现在不默改阈值或分母。

## 阅读指标前的边界

主要对齐指标来自冻结 test；dev/calibration 仅用于诊断、效率或阈值拟合。历史参考 test 已向方案设计披露的限制继续保留，不声称无污染。不同论文公式、温度、hard/soft 目标、全人口/有效人口分开；不求跨协议总平均、不用模型尺寸差异声称新训练收益。下面直接收录既有表格与说明，保持读数原样，读者无需逐份翻阅旧报告。旧矩阵的 58 是历史计分面板数，不是当前所有增量相加后的统一总数。

## 1. Kev 原生五套 test

原生温度：0.8B = 2.3510958125672174；4B = 2.406050072164233；9B = 2.193649959389252。下表 Brier 为 one-hot multiclass 求和，ECE 为 10 bins。clean 分母：decision 1200、transfer 656、hard 1088、documents 936；devtools full 1073 与 release 1071 单列。accuracy 单位为 %。

| 模型 | test/子集 | 计分 | n | accuracy % | Brier | ECE10 | NLL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kev-0.8B | decision-v7/clean | native | 1200 | 83.750000 | 0.230501236 | 0.018980717 | 0.432024519 |
| Kev-0.8B | decision-v7/clean | T=1 | 1200 | 83.750000 | 0.261037402 | 0.100331076 | 0.608458534 |
| Kev-0.8B | transfer-v4/clean | native | 656 | 69.664634 | 0.396638059 | 0.046375031 | 0.673408794 |
| Kev-0.8B | transfer-v4/clean | T=1 | 656 | 69.664634 | 0.416444911 | 0.099264052 | 0.737529016 |
| Kev-0.8B | hard-v1/clean | native | 1088 | 66.636029 | 0.459719075 | 0.125548388 | 0.862586684 |
| Kev-0.8B | hard-v1/clean | T=1 | 1088 | 66.636029 | 0.435635257 | 0.045529392 | 0.810524748 |
| Kev-0.8B | documents-v1/clean | native | 936 | 85.149573 | 0.244001497 | 0.071009331 | 0.491122215 |
| Kev-0.8B | documents-v1/clean | T=1 | 936 | 85.149573 | 0.249443193 | 0.078570712 | 0.575928812 |
| Kev-0.8B | devtools-v1/full | native | 1073 | 63.653308 | 0.442394041 | 0.084400357 | 0.778104695 |
| Kev-0.8B | devtools-v1/full | T=1 | 1073 | 63.653308 | 0.455260263 | 0.101732828 | 0.799732281 |
| Kev-0.8B | devtools-v1/release | native | 1071 | 63.678805 | 0.442355104 | 0.084701034 | 0.778333869 |
| Kev-0.8B | devtools-v1/release | T=1 | 1071 | 63.678805 | 0.455251659 | 0.101601233 | 0.800022254 |
| Kev-4B | decision-v7/clean | native | 1200 | 86.500000 | 0.186240156 | 0.019310292 | 0.349844515 |
| Kev-4B | decision-v7/clean | T=1 | 1200 | 86.500000 | 0.210427075 | 0.080424065 | 0.486820042 |
| Kev-4B | transfer-v4/clean | native | 656 | 83.841463 | 0.224156698 | 0.016704248 | 0.416390719 |
| Kev-4B | transfer-v4/clean | T=1 | 656 | 83.841463 | 0.241839087 | 0.085532335 | 0.565515898 |
| Kev-4B | hard-v1/clean | native | 1088 | 80.330882 | 0.277582963 | 0.084146933 | 0.510298577 |
| Kev-4B | hard-v1/clean | T=1 | 1088 | 80.330882 | 0.266842485 | 0.048480941 | 0.488188227 |
| Kev-4B | documents-v1/clean | native | 936 | 90.277778 | 0.170655143 | 0.100830150 | 0.356801403 |
| Kev-4B | documents-v1/clean | T=1 | 936 | 90.277778 | 0.152238923 | 0.043752814 | 0.327753587 |
| Kev-4B | devtools-v1/full | native | 1073 | 75.582479 | 0.341847712 | 0.077333877 | 0.601768649 |
| Kev-4B | devtools-v1/full | T=1 | 1073 | 75.582479 | 0.343588899 | 0.071655211 | 0.609042328 |
| Kev-4B | devtools-v1/release | native | 1071 | 75.630252 | 0.341742656 | 0.077587568 | 0.601791620 |
| Kev-4B | devtools-v1/release | T=1 | 1071 | 75.630252 | 0.343650228 | 0.071546704 | 0.609269541 |
| Kev-9B | decision-v7/clean | native | 1200 | 87.250000 | 0.177665502 | 0.027077989 | 0.339478204 |
| Kev-9B | decision-v7/clean | T=1 | 1200 | 87.250000 | 0.202317375 | 0.075008302 | 0.467006358 |
| Kev-9B | transfer-v4/clean | native | 656 | 85.213415 | 0.198948836 | 0.036219393 | 0.370415604 |
| Kev-9B | transfer-v4/clean | T=1 | 656 | 85.213415 | 0.216393855 | 0.082492448 | 0.464310532 |
| Kev-9B | hard-v1/clean | native | 1088 | 83.455882 | 0.233743052 | 0.054294197 | 0.425359759 |
| Kev-9B | hard-v1/clean | T=1 | 1088 | 83.455882 | 0.240956076 | 0.062900228 | 0.451785035 |
| Kev-9B | documents-v1/clean | native | 936 | 89.957265 | 0.151423755 | 0.017013200 | 0.297516503 |
| Kev-9B | documents-v1/clean | T=1 | 936 | 89.957265 | 0.165813476 | 0.062541371 | 0.412029369 |
| Kev-9B | devtools-v1/full | native | 1073 | 79.123952 | 0.309081046 | 0.097419976 | 0.570114258 |
| Kev-9B | devtools-v1/full | T=1 | 1073 | 79.123952 | 0.295619355 | 0.059791610 | 0.564033677 |
| Kev-9B | devtools-v1/release | native | 1071 | 79.178338 | 0.309009188 | 0.096860831 | 0.570191985 |
| Kev-9B | devtools-v1/release | T=1 | 1071 | 79.178338 | 0.295580235 | 0.059480280 | 0.564234961 |

上游同口径的 native 汇总如下。full devtools 与 T=1 无匹配上游列。4B documents 仅验证准确率可比，概率指标留空；上游 NLL 未提供。汇总一致不能证明逐题输出一致。

| 模型 | test/子集 | 上游 accuracy % | 本地−上游 pp | 上游 Brier | 上游 ECE10 |
| --- | --- | --- | --- | --- | --- |
| Kev-0.8B | decision-v7/clean | 83.750000 | 0.000000000 | 0.230489268 | 0.018159859 |
| Kev-0.8B | transfer-v4/clean | 69.664634 | 0.000000000 | 0.396631916 | 0.044841305 |
| Kev-0.8B | hard-v1/clean | 66.544118 | 0.091911765 | 0.459717250 | 0.124636094 |
| Kev-0.8B | documents-v1/clean | 85.149573 | 0.000000000 | 0.243962854 | 0.071048121 |
| Kev-0.8B | devtools-v1/release | 63.678805 | 0.000000000 | 0.442331050 | 0.084693186 |
| Kev-4B | decision-v7/clean | 86.500000 | 0.000000000 | 0.186253097 | 0.019285055 |
| Kev-4B | transfer-v4/clean | 83.841463 | 0.000000000 | 0.224210081 | 0.016767486 |
| Kev-4B | hard-v1/clean | 80.330882 | 0.000000000 | 0.277644362 | 0.084265819 |
| Kev-4B | documents-v1/clean | 90.277778 | 0.000000000 | — | — |
| Kev-4B | devtools-v1/release | 75.630252 | 0.000000000 | 0.341793208 | 0.077716299 |
| Kev-9B | decision-v7/clean | 87.250000 | 0.000000000 | 0.177666824 | 0.027404630 |
| Kev-9B | transfer-v4/clean | 85.213415 | 0.000000000 | 0.199036337 | 0.034421006 |
| Kev-9B | hard-v1/clean | 83.363971 | 0.091911765 | 0.233727007 | 0.054143665 |
| Kev-9B | documents-v1/clean | 89.957265 | 0.000000000 | 0.151425379 | 0.017012350 |
| Kev-9B | devtools-v1/release | 79.084967 | 0.093370682 | 0.309060387 | 0.097878977 |

## 2. Nimble 七套原生 test

T=1，七套是各自上游 test 的冻结子集；不与包含 train/dev/validation 的 3,880 行混合集汇总比较。

| 子集 | n | 本地 accuracy % | 上游 accuracy % | 本地 Brier | 上游 Brier | 本地 ECE10 | 上游 ECE10 | 本地 NLL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| massive-en-US | 350 | 86.857143 | 86.900000 | 0.215612244 | 0.216000000 | 0.069903500 | 0.061000000 | 0.566444583 |
| massive-de-DE | 350 | 84.000000 | 83.400000 | 0.256618634 | 0.256000000 | 0.081899113 | 0.079000000 | 0.664880929 |
| paws | 250 | 82.800000 | 82.800000 | 0.279648319 | 0.280000000 | 0.100160241 | 0.100000000 | 0.541910675 |
| civil_comments | 300 | 70.000000 | 70.300000 | 0.413403503 | 0.413000000 | 0.135850765 | 0.133000000 | 0.641568115 |
| aegis2 | 250 | 81.600000 | 81.200000 | 0.289384455 | 0.289000000 | 0.098642061 | 0.102000000 | 0.568025637 |
| summeval-relevance | 240 | 48.750000 | 49.200000 | 0.676895632 | 0.678000000 | 0.090175031 | 0.102000000 | 1.305991113 |
| summeval-consistency | 144 | 75.000000 | 75.700000 | 0.419423051 | 0.421000000 | 0.171724079 | 0.177000000 | 0.905904174 |

Noul 的 binary Brier 仅取 true 类平方误差，与上表两类求和的 Brier 不同。score MAE 采用期望等级，不采用 argmax 等级或四舍五入。

| 子集 | binary Brier | 本地 expected-score MAE | 上游 expected-score MAE |
| --- | --- | --- | --- |
| paws | 0.139824160 | — | — |
| civil_comments | 0.206701752 | — | — |
| aegis2 | 0.144692227 | — | — |
| summeval-relevance | — | 0.695520387 | 0.698000000 |
| summeval-consistency | — | 0.567382163 | 0.569000000 |

Civil Comments（300 条）：JSD(base 2)=0.175792225，TV=0.292534998，human entropy=0.239331648 bits。上游 JSD/TV 为 0.176/0.292；不混入 one-hot Brier。

## 3. Typed Decisions 六模型共同 test

400 records / 2,000 questions；choice 600、Noul 600、score 800。每个问题等权，accuracy 比较预测与 gold 的 first argmax。gold 的原始舍入概率不重新归一化；Brier 为 soft-gold 求和，KL 使用 1e-9 floor；ECE10 仍使用 hard argmax correctness。原计分 arithmetic 与 strict 面板均保留在 JSON；本次各模型 strict 均 2,000 valid。此处是概率读出计分，不等于原生 wire/HTTP 完整复现。

| 模型 | 计分 | accuracy % | KL(gold||p) | soft-gold Brier | ECE10 |
| --- | --- | --- | --- | --- | --- |
| Kev-0.8B | serving | 45.950000 | 0.349523040 | 0.195493398 | 0.045770036 |
| Kev-0.8B | raw_T1 | 45.950000 | 0.498068065 | 0.260309344 | 0.155169722 |
| Kev-4B | serving | 66.450000 | 0.223109423 | 0.124564683 | 0.089533926 |
| Kev-4B | raw_T1 | 66.450000 | 0.504515027 | 0.201069093 | 0.091401498 |
| Kev-9B | serving | 68.050000 | 0.213789510 | 0.116320990 | 0.064928038 |
| Kev-9B | raw_T1 | 68.050000 | 0.519308862 | 0.187224530 | 0.091135501 |
| Nimble-9B | serving | 65.100000 | 0.706027650 | 0.254995374 | 0.172864315 |
| Open-Jev-2B | serving | 58.250000 | 0.410910644 | 0.193816502 | 0.081003319 |
| Open-Jev-2B | raw_T1 | 58.250000 | 0.659782229 | 0.245027524 | 0.159234993 |
| Open-Jev-9B | serving | 67.800000 | 0.369436036 | 0.147618002 | 0.058201569 |
| Open-Jev-9B | raw_T1 | 67.800000 | 0.885942246 | 0.224382522 | 0.148582028 |

每个 type/workflow 的完整分数见 JSON。Nimble 原生已是 T=1，不重复一个 raw 面板；expected-score MAE 尚未验收，保留 null。当前没有可直接配对的上游同检查点分数。

## 4. Open-Jev 原始完整 test

原始 release-v2 test 共 10,532 行（已恢复公共部分 10,356 + 缺失补集 176）；其中 hard 10,046、soft 486。hard accuracy 仅用 hard 行；expected accuracy、NLL、Brier、expected Brier、ECE15 用全体行。原生温度 2B=1.518796342858676，9B=1.8969118766347646。

| 模型 | 计分 | hard accuracy % | expected accuracy % | NLL | Brier | expected Brier | ECE15 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Open-Jev-2B | serving | 94.634680 | 91.876577 | 0.195621588 | 0.076288049 | 0.104339013 | 0.012282068 |
| Open-Jev-2B | raw_T1 | 94.634680 | 91.876577 | 0.213531433 | 0.080689145 | 0.108740110 | 0.024149612 |
| Open-Jev-9B | serving | 97.511447 | 94.686833 | 0.130800630 | 0.039047204 | 0.067098168 | 0.007524828 |
| Open-Jev-9B | raw_T1 | 97.511447 | 94.686833 | 0.138525373 | 0.040875415 | 0.068926379 | 0.011593197 |

同一原始 test 的上游 serving 汇总：

| 模型 | 上游 hard accuracy % | 上游 expected accuracy % | NLL | Brier | expected Brier | ECE15 |
| --- | --- | --- | --- | --- | --- | --- |
| Open-Jev-2B | 94.714314 | 91.952536 | 0.195380034 | 0.076116976 | 0.104167940 | 0.011605590 |
| Open-Jev-9B | 97.541310 | 94.715318 | 0.130947153 | 0.039112900 | 0.067163865 | 0.007706544 |

本地 hard 正确数 2B=9,507、9B=9,796；上游分别 9,515、9,799。净少 8/3 个正确不代表恰好 8/3 道题发生翻转，也不足以归因于硬件。原报告中的 perfect-source、小样本等 review flags 原样保留；通过结构化验收不抹去这些限制。


## 已完成的六组合增量及审查限制

以下收录包含带日期的测量与后续审查，最终状态以末尾后续审查段落为准；当前 6 个新增组合均已有实际 Astra 有界审查。

## 2. JEVal 原始 test：新增两个组合

完整人口为11,257行，classification=10,938，score=319。accuracy使用完整分类分母；Brier/ECE/MAE使用各自有效人口。表内分母不能互换，也不能把有效子集视作两模型相同题目的受控比较。

| 模型 | native温度 | 正确/全分类 | accuracy% | 有效分类n | raw summed Brier | ECE10 | score MAE | 有效score/全score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kev-0.8B | 2.35109581257 | 5089/10938 | 46.525873 | 9911 | 0.598302104 | 0.163216356 | 1.121768025 | 319/319 |
| Nimble v1 | 1 | 5394/10938 | 49.314317 | 7694 | 0.433576240 | 0.135360806 | 0.842948718 | 312/319 |

Kev有1,027条overlength。Nimble有2,253条unsupported，准确拆分为 **2,047条候选数超限、206条空context**（ARC-Challenge95、ARC-Easy111），另有998条overlength。原closeout README的候选超限单一归因已有追加勘误，冻结证据未改动。Kev longbench-retrieval-en为200/200 overlength，valid-only accuracy为null；Nimble CUAD有效子集31/31，但完整cell31/200=15.5%，另169条超长。

分类按实际choice或noul≥0.5计分，不支持/超长按全分母错误计入。Brier为原生wire概率对one-hot的平方差之和，不重新归一化；noul重建[1−p,p]。ECE10使用Kev chance-adjusted choice confidence、Nimble selected probability、noul已选二元概率，分箱`min(int(10c),9)`。Kev score为原生期望等级（保留响应精度），Nimble为选中整数等级；MAE以原等级单位计算。未追加raw T=1、NOTA或permuted结果。

## 3. Open-Jev 原始 OOD：新增两个组合

同一原始release-v2 OOD共15,920行：hard15,446、soft474，包含恢复的219条Wikispeedia；不是15,701行公开投影或10,532行test。hard正确数2B为13,288、9B为14,207。

| 模型/计分 | 温度 | hard accuracy% | expected accuracy% | NLL | Brier | expected Brier | ECE15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Open-Jev-2B/serving | 1.51879634286 | 86.028745 | 84.616890 | 0.802074062 | 0.246288900 | 0.263619640 | 0.105578241 |
| Open-Jev-2B/raw_T1 | 1 | 86.028745 | 84.616890 | 1.156734154 | 0.254766583 | 0.272097322 | 0.119212764 |
| Open-Jev-9B/serving | 1.89691187663 | 91.978506 | 90.413799 | 0.299676558 | 0.126747550 | 0.144078290 | 0.037592607 |
| Open-Jev-9B/raw_T1 | 1 | 91.978506 | 90.413799 | 0.451535465 | 0.137554553 | 0.154885293 | 0.058512809 |

hard accuracy仅对15,446条one-hot行；expected accuracy为全部15,920行的`q[argmax(p)]`均值。`p=softmax(logits/T)`；NLL自然对数及1e−15下限，Brier对候选维度求和，expected Brier加`1−Σq²`。ECE15用最大概率与expected correctness，15等宽箱`min(floor(15c),14)`，与JEVal的ECE10不是同定义。

coverage阈值为0.5/0.7/0.8/0.9/0.95/0.99，使用最大概率≥阈值；coverage分母为对应面板全体行，selected accuracy仅以入选hard行为分母，expected accuracy以全体入选行为分母，无定义保持null。JSON保留总体两温度、native来源与题型全部分项及coverage值，来源/题型均不当作独立推理次数。

2B原审计0个主面板flags不代表所有coverage子格没有精确边界；9B保留3个flags：customer-control hard560/560，以及agent_trace_observability hard/expected525/525。后者两标记来自同一面板；group结构也不支持把所有行当作独立业务场景。审查未发现计分/缺失等错误，不证明无数据污染。

## 4. 面板计数、审查证据与可比边界

本增量只计新增6个模型×数据集组合（6个已实际Astra限定审查、0个待审查）；**不把展示行直接相加到旧58面板**。OOD展示4个总体模型×温度计分面板，它们来自2次保存推理；JEVal每模型含分类和score，且全分母/有效分母不同，因此这里不设跨协议“新增面板总数”（JSON为null）。不能把温度重算当重复稳定性实验。

| 证据 | 实际Astra原文SHA-256 | 冻结包MANIFEST SHA-256 |
| --- | --- | --- |
| JEVal Kev/Nimble | `a2bbbd95d1627b1196347d0aaa5ce8a89009499e6cd80c9484abb55ee5d946f9` | `a4f9ec8476dfca250244d1b6372467c1b1d1787de41874663a376a4e27cfca5d` |
| JEVal Kev-4B/9B | `dd080fa863d95b8af45f4198f6f0a6b4b47796c46a7a39d8c4fef962def80c64` | `dc076f5ffa1e7979e26035868a8f6fb3b815b3e6551db0613fc641473a732c0d` |
| Open-Jev两尺寸OOD | `cbea46b7695117328836dbca5745505c83d718819b5fa7c17ab0f912736c5bc9` | `cc46408dcf5d0482fd4d1b84c8ad39d48d72433791cd6f67a6ba4d8ea4cbac26` |

[JEVal实际审查](ASTRA-JEVAL-RESULTS-REVIEW-2026-10-31.md)与[OOD实际审查](ASTRA-OPENJEV-OOD-RESULTS-REVIEW-2026-10-31.md)保留完整原文、真实runner/child退出和限制。指标、报告、审查记录的路径、SHA和JSON pointer见[机器索引](REFERENCE-BASELINE-INCREMENT-2026-10-31.json)。本增量读取各自独立验收报告，实际Astra状态逐项列明；不重新计分或创建实验结果。

Open-Jev两尺寸覆盖相同OOD，可描述其参考差异；仍不能视作新训练处理的收益。JEVal有效子集因原生接口预算不同，概率指标不构成同题受控比较。不同数据集、不同Brier/ECE定义不求总平均。没有训练收益、真实业务收益、paired consistency、精确论文复现或无污染证明。旧28个Kev面板的历史审计终态绑定缺口仍保留。D1要求继续完成余下登记组合或明确其影响，再讨论Jev训练方案。

## 5. 2026-10-30 22:43:17Z 历史测量增量（北京时间 10 月 31 日）：当时科学发布审查待完成

日期勘误：本节测量时间为 UTC 10 月 30 日 22:43:17，先前标题误将北京时间日期与 UTC 时刻并列；记录及指标未变。

来源为[正式结果](JEVAL-KEV4-KEV9-RESULTS-2026-10-31.md)，closeout于22:39:12Z完成22,514条回执，report SHA `8d2af0809eda8d1c7772051b33b91bb30e864fae8d972c119810109417de0649`。下面是已有测量，尚不能称这两模型获得实际Astra发布结论。

| 模型 | native温度 | 正确/全分类 | accuracy% | 有效分类n | Brier | ECE10 | score MAE | 有效score/全score | flags |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kev-4B | 2.40605007216 | 6741/10938 | 61.629183 | 9911 | 0.436118754 | 0.173661124 | 0.914080878 | 319/319 | 8 |
| Kev-9B | 2.19364995939 | 6931/10938 | 63.366246 | 9911 | 0.406847145 | 0.109838099 | 0.923336991 | 319/319 | 7 |

口径与第2节冻结JEVal协议相同；各有1,027条overlength。两模型审计状态保持 `VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED`。这里不从尺寸差异推导训练收益，不沿用Kev-0.8B/Nimble的Astra结论。Open-Jev两尺寸JEVal依然是blocked/null，旧30组合/58面板快照原样保留。

## 6. 2026-10-31 后续实际审查与勘误增量

实际Astra于2026-10-30T22:55:48.805489Z完成，真实child和runner退出0；[Kev-4B/9B审查原文](ASTRA-JEVAL-KEV4-KEV9-REVIEW-2026-10-31.md)裁决为**有限通过，附加长度表述勘误后可发布为本地原生预算参考结果**。本次6个新增组合现均完成实际Astra限定审查，待审查0个；旧30组合/58面板快照不变，索引合计36组合。原审计机器状态及8/7 flags仍保留，不能改写成无条件通过。

勘误不改变任何分数：第5节结果来源的长度范围仅覆盖非空 `state_tokens`。每模型helmet150条超长由102条state与48条state-plus-branch组成；retrieval-en-e100条由99条state与1条state-plus-branch组成。例如7,379+3,543>8,192，而state本身未超限。已在源结果MD/JSON和closeout追加带日期记录；冻结审查包未改动。勘误SHA `0813612a6d3db9bcd1e6db135fc5823e28204a2188d49ec352fb2f1850fa0343`。

实际审查核对22,598个文件、22,514条回执和每模型66个单元；完整分类准确率仍为61.629183%/63.366246%，校准指标仅使用9,911条有效分类，score各319条。未重新读取外部权重/原生代码/probe原件、独立解码Parquet或现场查询Docker；抽取源码未在包中。不能据此主张无污染、论文精确复现、paired consistency、训练/业务收益或准入。

剩余原登记无结果单元仍为Open-Jev-2B/9B×JEVal，两者blocked/null；E38诊断不能自动改变该准入状态。当前新增结果审查完成不等于整个D1完成，也不提前启动正式训练。

## 当前唯一未完成的两个结果组合

| 模型 | 数据集 | 当前状态 | 指标 |
| --- | --- | --- | --- |
| Open-Jev-2B | JEVal frozen test | blocked_numerical_and_memory_admission | null |
| Open-Jev-9B | JEVal frozen test | blocked_numerical_and_memory_admission | null |

缺失不是零分，E38 完成不改变此表。已有参考结果的局部 flags、历史终态证据限制和可比范围不因本报告刷新而升级。

## 本次可核验证据

Ceph 根目录 `/mnt/cephfs/xingchao/experiments/jev/reference_inference/`：

- 2B 释放：`e38_release_openjev2_20261031_v5/RELEASED.json` SHA `3ecfd844a8038e0152ca32cd5aed4cd4238d35e42f50103d7bb87fba22a5f4b2`；journal 外 anchor SHA `c35f2df31e0467ffb4e704b07a9562acd8ae50a1389e49135ceb7c5d736e0b5a`。
- 9B：`openjev_path_trace_openjev9_20261031_v7/report.json` SHA `5af001b068a57671f3e3f0d68945dcabff548fce80df1278a0ae8d61dddd7d98`；NPU ID `36fe2217fe1f994b7403a2ea26254f6dc90ea8380eebff84c72a1d7b29f8e861`。
- 独立验证：`e38_openjev9_verify_20261031_v1/report.json` SHA `27142cd19530a1ee95454a2154019dc151edc4f5832c64cab59c627b8d90205e`；CPU ID `2d18a8ef4e023cb743375e51598fa1b8c32165707b0ed5e2246ed84d9ce80b61`；退出后凭证 SHA `aff1910c3f8f8f4a154721efac62151161013d09837c5569fb9549ae04754ac1`。
- 主会话独立核对 NPU terminal 的输出哈希、8 个 item receipt/8 个 attempt 哈希、CPU report/terminal 绑定及实际 Docker 起止身份；没有重新执行模型。

参考机器索引未变：matrix JSON SHA `03459facf6f86a919e10d9a0acef413b89c5a5d4ffd232352260722b05d0266e`；increment JSON SHA `fd5fc213295de50d8ffe4a38fd5c8b4fbc81517474bbd378341412286e3ab74b`。

完整阶段计划：[当前任务现状与下一阶段计划](../proposal/08-task-status-decisions-and-next-plan-current.md)。

### 发布核验补记（2026-10-31 03:54 UTC）

9B release journal `e38_release_openjev9_20261031_v1` 已完成，`RELEASED.json` SHA `8b212111c4d06b4e770e889370bc220d5cd4914620e77452f7437aea054adef1`，外部 anchor SHA `f4359466aa97f700fd85f4e134c12178a13ac497ec59e0aa7dbb0cdeeea7358f`。主会话核验只有 chip 4 转 free、其他 owner 未改；现场 allocation SHA 为 `c8c94a2f63844df50b1fc72e6d9a0575aecb5cdd0e4a3db2d8819cca81ac60e8`，free=[1,4]。9B 已结束，当前没有正在运行的本项目 NPU 容器。E40 首阶段代码和计划已冻结候选，仍待实际 Astra 审查；未启动。此补记不改变参考读数。
