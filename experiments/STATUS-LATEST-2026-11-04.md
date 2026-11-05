# Jev 工程与实验最新状态（2026-11-05）

> 主矩阵事实截点：2026-11-05 03:34 UTC；2026-11-05 增量更新七成员 CPU 派发和 27B 资源方案。完成、发布和科学验收分别报告；0.8B 冻结同 TEST 报告已限定范围科学验收。协作结论入口：[Current Conclusions](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions)。

## 当前状态

| 工作 | 当前事实 | 尚未完成 |
| --- | --- | --- |
| 固定基座参考评测 | Qwen3.5 四规格 × 28 面板 112/112 验收；Jev-bench 88 格是其中子集；大候选五任务 × 四规格 20/20 验收 | 完整异构模型 × 数据集 × 协议矩阵仍未完成；D1 36/38，其余两格 Open-Jev × JEVal 为 blocked/null |
| 0.8B 七成员最终同 TEST | 七个 score 终态与 retained 容器均 exit 0；decision-v7 TEST 1200、transfer-v4 TEST 656，另有独立 calibration | 独立 CPU 重算与 Astra 统计复核完成：63 份文件、49,448 行、12 组配对比较/区间及 49 个概率面板算术一致。release 修复 v7 的独立精确工程审查通过，394 项原始绑定不变，K0/K1/PT 完整合成事务通过；主会话已接受，七成员初次 CPU 接续全部 exit 0 且 publication_complete=true，生成原始来源/算子重建及发布产物；Astra 独立科学验收通过；Primary对Base +28.5/+4.725610个百分点，迁移ECE变差，外部参考原始语义等价仍未证明 |
| 交叉候选接口 DEV | 四规格各 672 请求的 NPU 推理均已完成；2B/4B 各 336 条 exploration CPU 重建及计分完成；0.8B 原协议 confirmation 已消费 | 独立限定范围复算完成：2B/4B exploration 为负，confirmation 保持锁定；0.8B 诊断 confirmation 的 18 项要求全部失败 |
| 交叉候选 9B 诊断 | 原协议 confirmation 的 18 项筛选中 17 项失败；不晋级、不调整阈值或映射 | 原冻结记录的辅助分析哈希与最终分析不同；score/reconstruction 两个生效 pin 仍一致，已追加日期化说明，原记录保留 |
| 新增 Kev 参考覆盖 | documents-v1/devtools-v1 × 四规格，共 8 个缺失单元已制作静态包，完整保留 936/1073 问题与重复原始 ID | 首格 v7 完整进程链与实际主机入口经独立审查 PASS；175 物理卡0已实际启动 0.8B documents，936题/395对，主机监督与CPU watcher回执齐全。其余七格待共享配置化展开 |
| Qwen3.8-27B 新增分支 | 本地 18 个 BF16 分片及运行文件匹配官方固定版本；现有 Ascend 镜像的离线配置、tokenizer、processor、模型类导入通过 | 已授权 2/4 卡，首轮 4 卡 FP32 工程推理、LoRA 按 4 卡准备；2 卡待实测选择。v7已在物理卡4–7启动，加载报告与可读遥测已落盘，但仍exit 1并释放四卡；尚无有效forward；诊断确认过滤后的加载报告与过滤前15个MTP差异校验不当，22项CPU回归复跑通过，严格修复在推进；不宣称整个模型目录逐文件一致 |

数字口径保持此前冻结记录不变：112 格、88 格子集和 20 格大候选结果不可相加为新的总体完成数。详见 [参考基线](REFERENCE-BASELINE-LATEST.md)。上述 DEV 与固定模型结果不代替训练收益验证。

## 工程瓶颈与处理

NPU 计分完成后的 CPU 交接存在版本契约缺陷：原 release 没有携带下游要求的 claim 哈希。修复保持原始 release、claim、模型、TEST 输出和闭包不变，用单独版本的证据核对绑定历史 claim/容器/计划/终态；独立审查通过后才恢复 CPU 发布，不重复推理。CPU 重建必须允许后继 NPU 同时执行。

新任务供应也存在缺口：规划图有 51 节点、20 个新 NPU 工作，但全部仍是准备或阻塞状态，不能当作可执行队列。8 个 Kev 单元优先做完；已完成的 2B/4B/9B 工程训练不重复运行以填满队列。27B 四卡首轮已实际启动并失败退出，资源已释放；Kev 首格已在物理卡0启动，其余七格未ready，不能声称 NPU 满载。

监控已修复并部署：600 秒/事件触发，读取日志、阶段心跳、终态、释放记录以及嵌套结果，输出异常率和证据指针。运行进程的退出不等于结果验收。

## 下一步与证据

1. 已完成七成员源数据/算子重建、正式发布及独立科学验收；发布的指标与限制见 [结果产物](FINAL-SAME-TEST-RESULTS-2026-11-05.json)。后续补齐外部参考原始语义对应，保留历史审计限制。独立统计复核已通过其限定范围，不重复 NPU 推理。
2. 完成 8 个 Kev 单元的可执行资源绑定与独立审查，在实际可用资源上并行启动；CPU 评分与 NPU 后继异步。
3. 保留已完成的限定范围负结果与分母；2B/4B confirmation 继续锁定，不用 TEST 结果重新选择训练方案。
4. Qwen3.8-27B 按 [2/4 卡资源策略](configs/qwen38-27b-resource-policy.json)推进：已接受控制器 v5 并取得四卡启动及失败释放回执，先定位运行时错误；测每卡峰值显存、吞吐和完整租用卡时，再决定 2 卡适用范围。LoRA 先按 4 卡准备；保留 Qwen3.5 对照。

最新过程证据留在本地或 CephFS：`.local/preparations/final-release-repair-20261105-v1/`、`.local/preparations/kev-executable-20261105-v1/`、`.local/preparations/interface-cpu-rest-20261105-v1/`；最终原始输出位于 `/mnt/cephfs/xingchao/experiments/jev/r3_runs/final_test_seven_20261104_v2/runs/`。这些路径用于追溯，不将过程日志推送为远程结论。
