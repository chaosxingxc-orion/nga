# Jev 工程与实验最新状态（2026-11-05）

> 事实截点：2026-11-05 03:34 UTC。完成、发布和科学验收分别报告；同 TEST 训练收益尚未验收。协作结论入口：[Current Conclusions](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions)。

## 当前状态

| 工作 | 当前事实 | 尚未完成 |
| --- | --- | --- |
| 固定基座参考评测 | Qwen3.5 四规格 × 28 面板 112/112 验收；Jev-bench 88 格是其中子集；大候选五任务 × 四规格 20/20 验收 | 完整异构模型 × 数据集 × 协议矩阵仍未完成；D1 36/38，其余两格 Open-Jev × JEVal 为 blocked/null |
| 0.8B 七成员最终同 TEST | 七个 score 终态与 retained 容器均 exit 0；decision-v7 TEST 1200、transfer-v4 TEST 656，另有独立 calibration | release 缺少 CPU 接续所要求的 claim_sha256，CPU 发布被正确拦截；追加式修复已生成，Astra 对抗审查进行中。没有已验收的同 TEST 训练收益 |
| 交叉候选接口 DEV | 四规格各 672 请求的 NPU 推理均已完成；2B/4B 各 336 条 exploration CPU 重建及计分完成；0.8B 原协议 confirmation 已消费 | 2B/4B exploration 与 0.8B confirmation 的独立 Sol 分析进行中；2B/4B confirmation 仍锁定 |
| 交叉候选 9B 诊断 | 原协议 confirmation 的 18 项筛选中 17 项失败；不晋级、不调整阈值或映射 | 原冻结记录的辅助分析哈希与最终分析不同；score/reconstruction 两个生效 pin 仍一致，已追加日期化说明，原记录保留 |
| 新增 Kev 参考覆盖 | documents-v1/devtools-v1 × 四规格，共 8 个缺失单元已制作静态包，完整保留 936/1073 问题与重复原始 ID | CPU consumer 固定、ordinal pair 映射、资源绑定、可执行派发与独立审查仍在完成；目前不能算作已启动 |
| Qwen3.8-27B 新增分支 | 本地 18 个 BF16 分片及运行文件匹配官方固定版本；现有 Ascend 镜像的离线配置、tokenizer、processor、模型类导入通过 | 27B NPU 加载、显存和推理尚未验证；README/LICENSE 差异及缺失 .gitattributes 已记录，不宣称整个目录逐文件一致 |

数字口径保持此前冻结记录不变：112 格、88 格子集和 20 格大候选结果不可相加为新的总体完成数。详见 [参考基线](REFERENCE-BASELINE-LATEST.md)。上述 DEV 与固定模型结果不代替训练收益验证。

## 工程瓶颈与处理

NPU 计分完成后的 CPU 交接存在版本契约缺陷：原 release 没有携带下游要求的 claim 哈希。修复保持原始 release、claim、模型、TEST 输出和闭包不变，用单独版本的证据核对绑定历史 claim/容器/计划/终态；独立审查通过后才恢复 CPU 发布，不重复推理。CPU 重建必须允许后继 NPU 同时执行。

新任务供应也存在缺口：规划图有 51 节点、20 个新 NPU 工作，但全部仍是准备或阻塞状态，不能当作可执行队列。8 个 Kev 单元优先做完；已完成的 2B/4B/9B 工程训练不重复运行以填满队列。当前实验容器均已结束，下一批尚未启动，不能声称 NPU 满载。

监控已修复并部署：600 秒/事件触发，读取日志、阶段心跳、终态、释放记录以及嵌套结果，输出异常率和证据指针。运行进程的退出不等于结果验收。

## 下一步与证据

1. 完成七成员 release 修复的真实 Astra 审查，恢复独立 CPU 源数据重建、冻结比较及科学验收，再发布同 TEST 指标与收益。
2. 完成 8 个 Kev 单元的可执行资源绑定与独立审查，在实际可用资源上并行启动；CPU 评分与 NPU 后继异步。
3. 接收 Sol 的受限范围诊断，按各自冻结探索决策处理 confirmation，保留负结果与分母。
4. 准备 Qwen3.8-27B 的独立数值/资源准入，保留 Qwen3.5 对照和原始主目标。

最新过程证据留在本地或 CephFS：`.local/preparations/final-release-repair-20261105-v1/`、`.local/preparations/kev-executable-20261105-v1/`、`.local/preparations/interface-cpu-rest-20261105-v1/`；最终原始输出位于 `/mnt/cephfs/xingchao/experiments/jev/r3_runs/final_test_seven_20261104_v2/runs/`。这些路径用于追溯，不将过程日志推送为远程结论。
