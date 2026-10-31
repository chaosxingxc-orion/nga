# Jev 当前进度、待决策事项与下一阶段计划

更新：2026-10-31，控制恢复后继已激活。最新例行NPU观测22:29 UTC：3训练+5推理，逐候选K2 961/906步，4B K1 seed2 1731/3116；2B推理93.4%/87.4%，共享K2 66.7%/65.0%，新0.8BK0 30.3%（均记录占比，非ETA）。无失败/停滞；驻留不等于满载。常规检查共享至少600秒，不因完成本轮工作增加查询。

0.8B K1双种子训练、开发集推理和CPU报告已完成；决策开发集均值82.91%、迁移开发集均值64.10%。这些仍不是测试集收益，同骨干K0比较尚待新基线。最终同测试集发布还缺正式资格、选择、真实恢复验证和有效独立审查。

QO/PT全量控制训练及普通评测已排队；新增PT seeds2/3的R0配置独立评分队列已部署175，PID1051352实际命令核验通过，等待对应训练和普通评测真实退出/释放后衔接。28文件闭包从钉住的R0评分代码复制，既有任务不变。B-4 CPU重建消费者及有序队列已部署，等待实际推理和R0报告；不宣称B-4已完成。0.8B最终成员校验更正为七项，补instruct K0，只验证结构，不批准测试。Astra本次仍只确认规则，NOT_REVIEWED。

远程累计结论入口：https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions 。后文保留明确标时的历史读数供回顾；当前状态以本摘要和最新来源证据为准。

## 1. 当前究竟走到哪一步

0.8B K1 两个种子均已完成3,116步、退出码0，两路真实模型开发/校准推理已自动启动；2B K1两个种子也已完成并接入推理，共享K2两个种子也已完成3,116步并自动接入推理；剩余两路逐候选K2训练继续执行。2B、4B、9B 的百步工程探针已经完成。训练后的推理、全新未训练基线 K0、CPU 报告和比较服务已经部署，本次核对了实际进程命令与最新队列摘要。

尚未完成的关键闭环是：完整训练 → 真实模型推理 → 同骨干 K0 比较 → 合格候选锁定 → 同一测试集收益汇报。当前已观察到完整训练→真实推理启动；0.8B K1两个种子的推理及CPU报告均已完成，新K0已自动启动，其他模型推理和基线比较仍待产出。因此没有新增候选测试成绩，也没有已证明的训练收益。已经验证了局部工程接口，0.8B双种子完整训练→推理→CPU报告闭环已观察到；同骨干比较闭环仍未完成。

两项工程目标应分别看：8 卡有活跃进程已达到当前资源覆盖要求；持续满载和实验效率最高尚未达到。15:18 摘要中训练卡 AICore 窗口均值约 34.7%–51.5%，推理卡约86.9%–93.0%，与“所有卡都忙”不是同一个指标。无证据支持把这解释为模型质量问题，也不能把占卡率当计算利用率。

## 2. 既有指令的逻辑和先后次序

1. **先建立参考事实。** D1 已限定范围，不再扩展；测试集指标按各论文原生公式、温度、标签和分母分别统计。
2. **启动可执行的工程基座。** 用户已允许准备好先跑、下一轮修复。工程运行不必等待无关 CPU 分析，但错误数据、来源不明、测试泄漏不能被当成有效实验结论。
3. **训练和推理都属于 NPU 实验。** 运行完成后自动接续就绪任务；CPU 的汇总、基线核验和审查独立有序处理。新的结果分析不会成为无关 NPU 任务的前置条件。
4. **最终主要汇报测试集。** 开发集负责预注册的选择和诊断，校准数据负责既定阈值；候选冻结后再读取测试集。先产生开发集报告，是为了防止用测试集挑方案，不是把最终目标改成开发集成绩。
5. **近期先证明公开任务收益，再补业务能力证据。** 业务要求的任务定义、数据集、直接驱动基线和学习优化仍在路线内；真实生产接入暂不考虑。公开任务提升不能直接称为业务收益。
6. **无算力预算，仍追求有效产出。** 取消费用上限不意味着慢方案无限占卡；需要比较每单位时间产生的有效证据。
7. **远程保留累计结论，本地保留过程。** 每个 milestone 刷新最新报告，三天归档；历史观测保留原时间和口径，归档不撤销冻结协议或原始证据。

## 3. 四个研究维度的实际进展

### 3.1 模型获益机制：分类已整理，因果验证仍需对照

| 类别 | 代表方式 | 当前判断与下一步 |
|---|---|---|
| 参数不动，改变驱动方式 | 候选呈现、概率归一化、温度、菜单约束、readout/harness | 参考结果已有；需与同骨干直接驱动 K0 对照，不能归为训练收益 |
| 改变模型结构 | 分支隔离、候选树、块因果读出、递归结构 | 文献梳理已有；Qwen3.5 混合骨干上的分支隔离尚有工程缺口，本轮未声称完成 |
| 设计任务和训练数据 | 决策样本、反事实、领域任务、SFT/LoRA | 当前 K1 是最先建立的可复用学习基线；0.8B/2B全量训练完成，推理进行中 |
| 设计学习方法 | 候选集合损失、proper scoring、蒸馏、RL | K2 已运行，其他方法与 RL 后续按同数据对照逐项推进 |

这个分组是我们的分析框架，一篇工作可以落入多类；不能从不同论文之间的分数差推断某一机制的因果收益。

### 3.2 任务与参考指标：固定矩阵已汇总，两个缺口保留

38 个模型×数据集单元中，36 个有结果，2 个 blocked/null：Open-Jev-2B×JEVal、Open-Jev-9B×JEVal。不扩展、不填零，不能说 38 格全部成功。

累计 Wiki 保留参考读数。例如 Kev 0.8B/4B/9B 在 decision-v7 clean 测试集的准确率分别为 83.750% / 86.500% / 87.250%，在 transfer-v4 clean 为 69.665% / 83.841% / 85.213%。这些是参考模型读数，不能当作当前 K1 的结果。

不同统计继续单列：原生温度与 T=1；hard 与 soft/expected accuracy；多分类 Brier 与二分类 Brier；Typed KL；不同有效样本数、超长/不支持样本分母。各自原生测试不能合并成跨任务总榜。完整参考表以 Wiki 及冻结矩阵为准，本报告不重复造一份数值权威。

### 3.3 业务要求：已有映射，任务承载仍不完整

现有任务可部分承载候选选择、输出类型、校准、风险排序、等价改写、拒答与回退。仍缺统一或足够的任务来验证：业务人员书写并修改规则；业务等价类；未知状态的明确表示；证据与决策审计；每个正确决定的成本；中文业务规则及数值/日期边界。

这些缺口将转成有训练/开发/测试划分、规则族隔离、等价与判别成对样本的任务。先报告直接驱动基线，再检验训练是否改善。当前既没有完整业务缺口基准，也没有业务收益证明。

### 3.4 我们自己的实验：工程基座运行中，完整 NxM 仍未完成

内部模型族拟按 0.8B→2B→4B→9B 逐级展开，任务使用冻结协议。这与 D1 不扩展不冲突：D1 是外部参考范围，内部 NxM 是我们自己的训练与直接驱动比较。

目前 0.8B/2B K1 全量双种子训练已完成；4B seed2全量训练已自动启动，seed3及后续推理、K0、CPU比较已排队；9B 百步探针完成，全量双种子→推理→K0已排队，尚未启动全量训练。开放学习/优化方案先建立 K1，再比较 K2 与其他方法；业务缺口任务和 RL 不抢在可信基线之前。

## 4. 首批八路训练进度（19:39 UTC；吞吐保留原窗口）

K0是未训练的同骨干直接驱动基线；K1是LoRA常规监督训练；K2是候选集合内的损失训练。seed 2/3是预先固定的随机重复。每路目标3,116步、1张卡。

| 方案 | 芯片 seed 2 / 3 | 完成步数 seed 2 / 3 | 问题/s/卡 seed 2 / 3 | 当前阶段 |
|---|---|---|---|---|
| 0.8B K1 | 1 / 4 | 3,116 / 3,116 | 完成吞吐见原始快照 | 两路推理及CPU报告完成 |
| 2B K1 | 3 / 5 | 3,116 / 3,116 | 3.173 / 3.118 | 两路推理中 |
| 0.8B K2共享提示 | 0 / 2 | 3,116 / 3,116 | 1.489 / 1.493 | 训练完成，两路推理中 |
| 0.8B K2逐候选 | 6 / 7 | 715 / 656 | 0.247 / 0.230（19:18） | 训练中 |

2B seed3在15:13:05 UTC结束，终止标记exit0；受控释放凭据确认训练容器退出，chip5在15:13:52自动启动后继推理。19:39现场确认3路训练、5路推理容器运行；0.8B K1双种子完整推理及CPU报告已完成，chip4已自动启动4B seed2训练，chip1已自动启动新0.8B K0推理。
吞吐为剔除前五步后的总工作量÷训练 step 总耗时，不含加载、检查点和后续推理。剩余时间按每步约十个问题估算，不是交付承诺。共享 K2 的逻辑 token 重复计入候选提示，不能直接拿它的 tokens/s 与其他实现横比。

结构化检查没有发现非有限 loss/gradient 或步号不连续；这不等于质量通过。两个 K2 实现存在分组、dropout 和版本差异，必须作为不同方案，不能合并为一对种子。

已完成的历史工程证据保留：0.8B 45 步探针剔除 5 步后为 844.079 tokens/s/卡、2.96681 问题/s/卡、峰值 reserved memory 6.66211 GiB；2B/4B/9B 百步探针的 95 步有效测量分别为 828.098 / 446.090 / 393.069 tokens/s/卡。上述均为各自配置下单卡测量，不是同配置受控规模比较。共享 K2 与逐候选在历史匹配的 110 个问题上的耗时比为 6.830，不能据此声称模型效果提升或训练轨迹等价。

## 5. 自动执行现在能做到什么

| 链路 | 当前状态 | 尚需观察的事实 |
|---|---|---|
| 首批 8 路训练→Track K/T 推理 | 2项推理及报告完成；4项推理中；2项等待训练 | 其余候选推理完成及来源校验 |
| 0.8B/2B 全新 K0 推理 | 0.8B已启动；2B等K1 seed2退出释放 | 新读数来源通过校验并产出有效报告 |
| 4B 全量双种子→推理→4B K0 | seed2已启动；seed3等待前序释放 | 真实自动交接和规模运行稳定性 |
| CPU v10：17 个报告＋8 组比较＋1项预检 | 管理主机PID2207331实际命令核验相符；2报告完成、24任务待依赖 | 双种子报告已生成；比较尚待K0 |
| 当前配置恢复验证 | 等 0.8B K0 释放 chip 1 | 训练态 20 步连续/10+10 重启及错误对照通过 |
| fast_ref 数值与效率探针 | 等 2B K0 释放 chip 3 | 先通过 loss/梯度合同，再测性能 |

已实际发生的自动交接包括短探针→全量训练和0.8B完整训练→真实推理。真实推理完成→CPU报告已观察到；同骨干CPU比较尚待K0。当前是有限的显式依赖队列，不能称所有任务和失败路径都已实现通用无人值守。

CPU v10 将已就绪报告与比较放在一条串行通道，跳过尚未就绪任务；NPU 后继不等待无关 CPU 分析。已经修复旧失败 marker 干扰重试、选择半集聚合越界、冻结目录生成字节码、较大模型误套 0.8B K-align 等问题。相关针对性测试已通过；真实实验输出仍是最终检验。

真实数据规模的 CPU 接口合同覆盖 11 组 Track K、1,920 个 dev 问题及每角色 46,342 条 Track T 记录，成功退出；但其中分数合成、模型来源被模拟，只证明接口，不是模型结果。

## 6. 从工程运行到正式结论，还缺哪些证据

| 缺口 | 为什么会影响结论 | 下一步责任 |
|---|---|---|
| 当前同骨干 K0 尚未完成 | 历史 146,246 条读数均缺现行来源标记，不能回填后冒充合格基线 | 0.8B已重新评分中，2B排队；CPU严格核验 |
| 独立 R0 gating 尚无完整读数 | R0 使用另一配置的 instruct 基线，不能由 K0 代替 | 完整R0评分已冻结并排队，接恢复验证v3后chip1；CPU最终报告接口已冻结并通过合成数据合同，等待真实输出 |
| 有效独立 Astra 审查缺失 | 既往子智能体只确认规则，没有对产物审查 | 多个精确产物审查请求仍只返回规则确认，最近一次为fast_ref v2；停止相同重试，保留未验收状态，后续需取得实际逐项裁决 |
| 正式运行资格未完成 | 现有运行按工程方案启动，不能事后悄悄改名为正式实验 | 明确与正式协议差异，完成预先审查；需要重跑则另发冻结版本 |
| 当前配置恢复与加速尚未实测通过 | 可加载检查点≠恢复轨迹等价，历史加速≠当前可用 | 执行已排队的有界恢复/数值/效率实验 |
| 三天归档已部署 | 每日检查、保留至少三天；保护当前报告/预注册/代码/依赖 | 定时器启用且Linger=yes，首次exit0；实际重启恢复未演练 |

归档采用用户级 systemd 定时器，已核验 active/enabled、Linger=yes 和首次退出0，下一次计划北京时间11月1日00:01左右。当前没有到期文件；仅自动处理有限目录的非受管过程文稿及指定监控快照，不扫描CephFS运行目录。证据 `.local/archive-service/DEPLOYMENT.json`。

工具没有仓库指南指定的 sonnet/opus/fable 别名，不能声称完成这些指定模型的审查。本轮只读辅助事实核对与独立正式验收是不同工作；任何确认规范的回复都不计为验收通过。

这些技术缺口由执行方补齐，不需要你逐项替我们决定，也不阻塞无关的已授权 NPU 实验。

## 7. 需要你决策的事项

**目前只有一项尚待意见的实验范围与资源取舍（没有停止现有任务）：是否保留两路逐候选 K2 全量运行。**

- **继续跑完：** 保留原逐候选实现的双种子证据；16:54时为469/426步，占目标3,116步约15.1%/13.7%，占用两卡。15:20时的剩余耗时估计仅保留在归档，不作为当前ETA。
- **确认可恢复且后继就绪后暂停（建议）：** 保留检查点和全部证据，将两卡优先交给基线、数值/效率验证等有效任务；代价是暂时缺少逐候选 K2 完整结果，共享版本不能替代它。

这是对已经启动实验的取舍，不是常规修复审批。尚未验证这两路满足安全暂停的全部条件，也未收到你的选择，因此现有两路继续运行。若选择暂停，先确认恢复能力、后继计划和资源交接，不会先停卡再准备。

不重复询问已决定内容：D1 不扩展、取消预算、暂不接真实业务、推理属于实验、NPU/CPU 异步、工程准备好先跑、Wiki 结论维护、三天归档。RL 方法和最终模型暂不要求你选，因为当前证据还不足。

## 8. 下一阶段任务计划和完成标准

| 优先级/阶段 | NPU 执行 | CPU 并行任务 | 里程碑完成标准 |
|---|---|---|---|
| P0：维持当前执行并补关键依赖 | 3路训练与5路推理继续；按冻结队列接续 | 准备真实 R0；明确正式资格；整理独立审查包；核对后继服务 | 有真实可执行 R0 方案；下一项任务可自动领取真正释放的卡 |
| M1：首个真实闭环（训练/推理/CPU报告已达成；K0仍在运行） | 0.8B K1 完成→开发/校准推理→新 K0 | 校验终止、权重、来源、分母，消费真实报告 | 首个完整训练和真实推理/CPU 报告成功；不提前叫测试收益 |
| M2：可信同骨干比较 | 其他训练、4B 与验证任务继续 | 双种子报告＋K0＋R0 gating；退化对照；有效独立验收；明确需重跑的正式方案 | 可追溯开发集比较；候选合格并按规则冻结，或明确未达标 |
| M3：同测试集结论 | 合格候选与同骨干 K0 按测试票据评分 | 独立复算、逐问题配对区间、校准与一致性分析 | 同测试集增益/负结果及全部验收证据；更新 Wiki |
| M4：扩大可用工程基线 | 4B 完整链路；9B工程链路已排队；每次只改一个优化因素 | 比较有效吞吐、恢复和质量，完善内部 NxM | 同口径规模结果及可复用学习/优化基线 |
| M5：业务能力缺口与 RL | 冻结业务任务上的直接驱动，再监督/学习优化，再 RL 对照 | 定义缺陷、最优解、退化反例、等价与判别对；冻结数据和奖励 | 业务问题定义下的能力提升，可与简单基线比较 |

M1–M3 是科学依赖顺序；M4 的就绪工程运行可与前面的 CPU 工作并行，不必等待整个报告完成。R0、审查、归档改进都应现在推进，避免训练结束后才发现缺口。

当前公开任务收益标准仍为：至少一个主测试集相对同骨干 K0 提高 ≥1.0 个百分点；另一个下降不超过 1.0 个百分点；报告逐问题配对 90% bootstrap 区间；双种子、来源、测试票据、独立评分与资源证据齐备。不达标同样应完整汇报。0.8B K1 的 K-align 判据不能直接套到 2B/4B；较大模型首先报告自身同骨干差值，正式选择按适用冻结协议执行。

## 9. 当前与历史证据入口

- 当前远程结论：https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions 。
- 本次训练结构化快照：`.local/reports/training-status-20261031T1654.json`，具体生成时刻以内容为准。
- 旧中文累计报告：`.local/archive/2026-10-31/reports/STATUS-before-1944-consolidation.md`。旧进度保留为历史观测，本文件汇总其有效结论并替换过期状态。
- 资源与执行：CephFS `CHIP-ALLOCATION.json`、各运行 terminal、队列 `digest.json` 与 `SERVICE.json`；本次另核对实际 PID/命令，不仅依赖状态文件。
- 当前队列：`posttrain_execution_queue_20261031_v3`、`cpu_selection_queue_20261031_v10`、0.8B/2B K0 后继、4B 链路、恢复验证和 fast_ref 后继。
- 正式协议仍在本地 archive 中有效；历史读数不会因归档被重新解释。归档/新预检代码提交 `f351b6f` / `f476b57`，CPU冻结校验修复 `df999e8`。

本报告只刷新事实和计划，没有更改训练、阈值、测试锁或既定实验范围。


## 10. 推理进度、效率与修复的累计结论

每路当前Track K/T推理的冻结人口为148,542条评分记录、32个结果文件；Track K为9,516条，Track T为139,026条（3个输入角色）。外层32问题调用共4,658次，不等于NPU前向次数。推理进度工具只读收据元数据与文件stat，不读质量分数；验证人口哈希、完整性及身份一致性。6项CPU测试通过（4152764）；即使计数100%也不替代终止与来源验收。

| 推理任务 | 19:39收据记录数 | 记录占比 | 状态 |
|---|---:|---:|---|
| 0.8B K1 seed2 | 148,542 / 148,542 | 100.00% | 已完成推理及CPU报告 |
| 0.8B K1 seed3 | 148,542 / 148,542 | 100.00% | 已完成推理及CPU报告 |
| 2B K1 seed2 | 45,686 / 148,542 | 30.76% | 运行中 |
| 2B K1 seed3 | 44,076 / 148,542 | 29.67% | 运行中 |
| 0.8B共享K2 seed2 | 28,512 / 148,542 | 19.19% | 运行中 |
| 0.8B共享K2 seed3 | 27,936 / 148,542 | 18.81% | 运行中 |
| 新0.8B K0 | 608 / 148,542 | 0.41% | 运行中 |

记录占比不等于耗时占比，无完成ETA或质量结论。进行中的任务各有正常未满收据，未发现身份异常；CPU v10为2项报告完成、15项等推理、9项等报告。新K0完成前尚无同骨干配对比较。

固定镜像CPU分词探针在64条decision开发样本×full/blank/drop上保持token和批布局完全一致。原始/首次缓存/重复缓存耗时1.497/0.717/0.044秒，首次只省0.780秒，不能称NPU加速。样本全部77候选，代表性有限；CPU复现布局为867次前向、13,725,406个含填充token，填充占0.0552%，重复提示占未填充token的99.5843%。因此下一步测提示复用；现行冻结评分器未改变。

| 修复或验证 | 已完成证据 | 当前边界 |
|---|---|---|
| 训练增强及LoRA构造 | 20样本×2种子×2epoch共80次增强零差异；CPU镜像186对/372张量、10,822,656可训练参数、其余冻结 | 证据包绑定正式prepare/launcher；不代表训练收益 |
| 新K0消费者 | 合成148,542行走真实来源校验与报告接口；篡改拒绝 | 合成分数不是模型结果；真实K0尚待推理 |
| R0消费者 | 3角色各102,654行人口合同，错行/错来源/错配置拒绝 | R0独立instruct基线，不能由K0替代 |
| 恢复验证v3 | 修复旧来源plan缺arm启动错误，4测试；正式消费者9项新测试及相关检查通过 | 仍待NPU 20步/10+10、3连续副本与2错误对照；不能称恢复通过 |
| prefix探针v3（身份修正） | 强制完整12样本/候选人口、有限值、重复token一致；5项测试含共同截断反例 | fp32/HF32off、24case，raw差≤1e-3且非近tie零argmax分歧；待NPU运行 |
| fast_ref探针v2 | 所有5组梯度/loss及派生量有限，零容差不除零，复用绑定命令/冻结输入；7测试；真实CPU镜像挂载/导入/身份检查exit0 | 两阶段显式HF32off；dropout/分块配置仍不同，不证明完整训练等价；待NPU运行 |

prefix只用0.8B K1 seed2适配器、decision/transfer开发集各6条、候选数2–77；full/blank/drop、原/逆序、rightpad/fast、首/重复调用。+0.01错误对照必须失败，显存峰值为进程累计。历史fp32通过与bf16失败及0.98–4.69倍历史计时均不作为当前收益。

当前后继版本：恢复v3→R0后继v2（chip1）；fast_ref v2→prefix后继v4所驱动的prefix探针v3（chip3）；4B/9B训练链已排队。fast_ref/prefix旧控制器是在无实验启动时切换，没有中断训练或推理。各运行保留原冻结代次；版本更新没有修改原样本或阈值。

正式恢复消费者绑定代码、模型、数据、镜像、环境、原检查点、设备挂载、终止/释放及7阶段收据，并复算标量门槛。它不独立重算张量距离，也不认证伪造收据，不能代替真实容器核验和Astra独立验收。最近Astra请求仍只有规范确认；所有此类回复均记NOT_REVIEWED。

共享K2接续配置预检已完成：冻结posttrain队列verify通过，seed2/3各自接chip0/2和各自适配器目录；CPU报告路径逐项匹配，比较对象是同骨干k0-08b和双种子0.8B K1，并另有R0 gating比较。该检查不查询NPU，也不证明未来交接已经发生。证据shared-k2-handoff-precheck-20261031.json。

共享K2完成里程碑：seed2于17:38:52 UTC成功结束，seed3于17:41:26结束；各3,116步、terminal及保留容器均exit0、结构化issues为空。chip0/2分别于17:39:29/17:42:08启动对应推理，约37秒/43秒完成自动交接；退出/释放/适配器来源/种子/实际推理容器均核验。这里的交接时间不是持续计算满载证明；当时尚无完整质量报告；现已由下述双种子完成里程碑更新。证据shared-k2-completion-20261031.json。

## 11. 双种子完整推理与CPU报告（19:44更新）

0.8B K1 seed3于19:26:46 UTC成功结束推理，terminal、attempt退出及保留容器均exit0，chip4释放凭据验证通过。CPU v10自动生成selection_report.json并exit0；其消费者验证32文件/148542记录、模型与评分器来源、文件哈希及逐行模型标记。4B seed2全量训练容器cf1077f5521b已实际运行，说明CPU分析与后继NPU启动保持异步。

seed2也于19:28:57 UTC完成推理，终止标记和保留容器均exit0，CPU报告完成；chip1新K0于19:29:37 UTC自动启动，约40.4秒接续。

| 开发集读数 | 问题数 | seed2准确率 | seed3准确率 | tie数 |
|---|---:|---:|---:|---:|
| decision-v7/dev | 1264 | 83.070% | 82.753% | 0 / 0 |
| transfer-v4/dev | 656 | 63.262% | 64.939% | 0 / 0 |

各自Kev/R0规则准确率一致；不将两个种子当成两倍独立样本。

这是开发集而非测试集，不与参考测试分数直接比较；当前缺新K0、配对比较和独立Astra验收，不能声称训练收益。Track T选择侧含fail/void及低样本单元，尚需逐单元分析；零值及完美值需要反例/分母核查，报告成功不等于门槛通过。

该推理1卡：11680.422含填充tokens/s/卡，7.316评分记录/s/卡，reserved峰值6.3848GiB，148542记录、评分耗时20302.575秒；记录不等于独立问题，评分耗时不含所有调度开销。证据first-inference-completion-20261031.json及其固定report SHA。最新运行总数在此里程碑为3训练+5推理，2B和共享K2候选推理未完整结束。

## 12. 当前证据与维护规则

最新统一快照：`inspection-20261031T201019.json`，保留实际Docker、训练摘要、推理收据摘要、CPU进程及队列。检查入口`.local/operations/inspect-once.py`使用共享时间锁，未到期直接返回；首次到期执行errors为空，输出约267tokens，完整证据本地保留。历史独立快照继续供查询。

- 历史逐候选训练快照：training-status-20261031T1818.json；共享K2完成快照training-status-20261031T1746.json；inference-progress-20261031T1818.json。此前16:22、16:33、16:44等读数完整保留在快照与归档，仍按原时点解释。
- 训练证据：CephFS current_training_evidence_20261031_v1/EVIDENCE.json，SHA256 `353de091878c0681b3ff0364c5a428e8424895735ebbf3ea54a46fce59f13f79`。
- CPU v10队列SHA256 `c490eddb939e6ffd11f12929b7729e950d01b13d81f1edebc078cf9796ef48c2`；最近实际进程核对19:39，PID2207331。
- fast_ref v2计划SHA256 `170a34741209c24368cb7778cfa30e56ac5d7ba4a405c7fd661b482569356ce5`，代码2dcaed4；部署证据fastref-v2-preparation-20261031.json，CPU镜像证据CephFS fastref_v2_cpu_mount_smoke_20261031_v1/VERIFICATION.json。
- 其他证据：resume-v3-preparation-20261031.json、prefix-v2-activation-20261031.json、inference-workload-20261031.json、astra-fastref-v2-20261031.json。prefix旧后继PID已由新后继取代，不按历史PID推断存活。
- 主会话和子智能体共用 `.local/NPU-MONITORING.json`，约600秒集中检查；明确事件才提前定向核验。后台队列独立运行，不等待模型轮询。下一例行检查≥20:20:19 UTC。
- 三天归档定时器继续执行；本次报告合并的完整旧副本在 `.local/archive/2026-10-31/reports/STATUS-before-1944-consolidation.md`，供历史查询，不作为最新状态权威。规范与冻结原始证据不因归档失效。

本次合并不改变范围、数据、指标、阈值或测试锁。远程Wiki保留累计结论；例行过程快照只在本地维护。

## 13. Track T零值诊断（已完成selection数据，非测试）

独立CPU算术复核seed3的openjev-synth ordinal primary：T1 original和T2 base各1,080题，argmax均403题正确（37.315%），阈值读出均1,080题拒答、准确率0。全T1变体为4,304/4,320拒答，random命名组16次决定中4次正确；T2为3,240/3,240拒答。不能将全T1写成全部拒答。

冻结tau=0.95；三个version拟合项在零效用平台上按较大tau破同分，question回退项的最优效用仍为−10。效用为正确+1、错误−1、拒答0，因此阈值结果与argmax结果必须分列。T1 argmax配对翻转率76.698%，阈值翻转率0.741%，后者受近乎全拒答影响，不能声称稳定性收益。没有修改阈值。

复核绑定冻结代码清单、数据/读数哈希、人口和分母，逐条独立重算ordinal区间决策并检查拟合网格选择。范围仅该selection单元，不是整个报告独立复现。证据seed3-trackt-diagnosis-20261031.json。最新Astra任务仍只返回规则确认，NOT_REVIEWED；子智能体报告整合任务亦未完成，以上由主会话基于证据补齐，不冒充独立验收。

## 14. 双种子开发门槛与参考来源复核（19:48 UTC）

CPU audit v2在19:47:28 UTC以exit0完成，重新验证权重/逐行来源/完整人口，重建两个selection报告并逐字段精确相等。双种子均值为decision-v7/dev 82.911%、transfer-v4/dev 64.101%，数值达到预注册K-align的80%/60%线。本轮评分为fp32，参考stage-1测量精度未知。K-floor也数值通过：每种子、每套任务分别领先常数和question-only对照至少5pp；最小实际差为21.646pp。正式准入、Astra验收及K0收益比较仍未满足，不能据此自动采纳方案或解锁测试。

本地Kev仓库2074cc44256200bb37540103fa4572901faa10f3的三个stage-1 result.json已逐文件匹配Git提交内容。源读数decision-v7为81.725%/81.962%/82.911%，transfer-v4为62.195%/63.415%/64.329%，分母1264/656；均test_evaluated=false。原预注册四位小数常量不改，精确原值另存以便追溯。

按§3.3保留差异：我们的label continuation对比Kev pointer head；提示格式不同；按问题而非record训练/加权；K1 full-vocabulary loss；既有LM head冻结；洗牌按问题。该参照是开发阶段范围，不能替代发布模型测试集成绩，更不能证明超过同骨干未训练K0。

seed2的ordinal独立CPU复算亦完成：原始1080题argmax正确392，operator全部拒答；T1变体4319/4320拒答，唯一random决定错误，T2全3240拒答。两个种子都显示命名敏感性及拒答退化，但因果上是否训练造成、是否较K0改善仍待对照。

额外审计v1曾引用推理闭包，被report-half检查拒绝；v2改用CPU v10 queue明确绑定的selection_cpu_closure_20261031_v2，源报告未修改。失败和修正均留存。证据：dual-seed-development-lines-20261031.json、kev-stage1-source-20261031.json、seed2-trackt-diagnosis-20261031.json；独立审查交接更新到.local/reviews/astra-handoff-20261031-v2。

## 15. 恢复验收补充与效率快照（19:54 UTC）

新增r3_resume_recompute.py（55ef2ef）：先执行已有完整收据验证，再用CPU从六路检查点和逐步loss独立重算三组重复距离、恢复距离及两个破坏对照；检查步号/调度器/LoRA库存、形状、dtype、有限性。使用weights_only=True加载，验证前后重算输入哈希；不改冻结门槛，也不自动授权正式实验。固定镜像6项CPU反例测试通过，旧收据验证9项测试通过；测试容器实际exit0且devices=[]。首次CPU测试因torch_npu自动加载失败，关闭TORCH_DEVICE_BACKEND_AUTOLOAD后通过，原失败保留。

冻结部署current_resume_cpu_recompute_20261031_v1；后继PID2376063实际命令核验通过，600秒纯脚本等待当前resume v3成功终止并释放后自动启动。真实恢复尚未完成，此处不是恢复通过。Astra最新回复仍无产物审查，NOT_REVIEWED。

19:49快照：4B seed2为188/3116步、无有限性/连续性异常；1卡有效step窗口429.116 tokens/s/卡、1.623问题/s/卡，不含加载与检查点。19:47摘要显示该卡HBM占用24.6GiB（不是框架reserved）；AICore窗口84%，样本19，未覆盖完整60分钟。两路逐候选K2为728/671步；AICore窗口52.6%/48.5%，仍是效率短板。推理卡均值87.5%–90.7%，新K0仅17样本，不当作完整60分钟窗口。8卡有任务不等于持续满载。近期fast_ref与提示复用保持冻结队列，不用未验证加速替换现行任务。

## 16. 后继身份修正与静态依赖核查（20:02 UTC）

prefix探针v2的run字段遗留v1，导致资源账本会归到旧代次。已在未启动时生成v3，代码及12条样本逐字节一致；阈值、24case与模型适配器不变。计划SHA为9e6b51b742fdb3826bea1fa57d81cc0f3f703e6ba3905ae20cb817ca765180ad，后继v4的queue SHA为57d6bcbe0547b37b44bf1403c6385e0972c6e196dd7270ac70883c251f6252d9。host175先完成launcher/queue校验，再核对旧PID命令且无launch/intent，pidfd停止旧空闲控制器；新PID169434和watchdog174433实际命令已核验。watchdog仍600秒。无NPU任务被中断。证据prefix-v3-identity-20261031.json。

当前12条显式后继边的plan pin、chip、out路径均通过静态核对。另有恢复v3沿用v2账本标签的追溯债务：claim/release与消费者均使用同一个plan.run，R0及CPU后继均等待真实v3目录，旧v2无启动记录。未发现实际释放/接续阻塞，因此保留已冻结恢复计划和消费者pin；明确记录别名，真实结束后仍需容器/释放核验，后续重建计划再修正，不静默改计划。

19:59运行摘要仍3训练+5推理，4B seed2 292/3116，逐候选K2 741/683；K0收据4028/148542。收据占比不是耗时占比或质量结果。下一例行检查20:09:31 UTC及以后。

## 17. 最终测试入口并发与恢复缺口

只读审计及临时虚构身份反例确认：旧testlock授权前不持久预约，完成日志写入前可为同模型同分区发两张票。未读取真实test。新增执行预约组件（ed9bd3f）绑定模型/suite、输出目录、plan和FINAL身份，锁跨完整执行；7项CPU测试含并发及SIGKILL后同身份恢复通过。它尚未接入最终评分入口，不代表测试锁已端到端修复。

还需完成双suite半完成事务恢复、exact-plan最终launcher及来源复算，并取得实际独立审查。旧run_full一开始取两套票，第一套已完成时整体重跑会被拒，不能用删日志或新目录绕过。详细需求见.local/reports/FINAL-TEST-READINESS.md，后续依其逐项集成验证。工程dev/calibration队列保持冻结；测试仍锁定。

## 18. 双任务提交恢复组件（20:13 UTC）

9d1af68新增r3_test_transaction.py：两个suite均在准入及评分前持有执行预约锁，全部结果来源核验并暂存后再写完成日志；崩溃恢复核对同一plan/FINAL/输出，已完成项只核验、不再评分。15项CPU测试通过，包括真实子进程第一套日志写入后SIGKILL、恢复补完第二套且合成评分调用总数仍1。

真实冻结评分器没有单suite测试选项，且旧run_full在暂存report之前先写TEST-READS日志，因此不能直接绕一层就宣布集成完成。新事务仍使用可注入的评分/来源/日志适配器；测试适配器是合成的。后续需接真实producer收据及原7列测试日志，冻结精确最终launcher并做真实入口合成集成验收；正式资格和Astra审查仍是前提。没有读取真实测试集，没有发布FINAL或测试票据。

20:10快照：3训练+5推理继续，4B seed2 395/3116，逐候选K2 761/699；新0.8B K0记录6008/148542（4.04%记录占比，不是剩余时间）；2B s2/s3为49918/46070，共享K2为32584/32392。无失败/停滞摘要，两个已完成CPU报告不变。

### 监控频率补充约定（2026-10-31）

主会话与子智能体共享600秒例行检查额度；到期只是允许检查，不要求唤醒模型，也不通过模型反复等待/查询来凑满10分钟。提前检查仅响应新完成标记、失败/停滞告警、队列耗尽/设备空闲告警或用户明确询问实时状态，并仅核验受影响任务。无变化不重复汇报。任务派发、资源释放和CPU结果处理继续由后台脚本驱动，不能等待模型巡检；不因此修改实验参数或停止现有任务。监控策略文件是.local/NPU-MONITORING.json；目前确认的是共享限频入口与策略，不能将其表述为已经实现新的外部事件推送服务。

## 19. 测试结果日志恢复适配（20:21 UTC）

beb0eee完成七列TEST-READS.log适配；持久意向记录绑定完整结果SHA，六位小数只用于原日志显示，不替代完整读数。22项CPU测试通过，实际SIGKILL半提交恢复时合成评分仅一次。冻结旧解析函数的格式兼容已验证。真实评分、同身份完成后的来源复核票据路径和exact-plan launcher仍未接入；calibration/operator不得因test-only入口而被省略。独立子智能体未交付实际审查，仍NOT_REVIEWED。证据test-log-parser-compatibility-20261031.json及FINAL-TEST-READINESS.md。

20:20:47 UTC共享例行检查：3训练+5推理，8卡驻留；摘要无failed/stalled。4B seed2 507/3116；逐候选K2 775/718；2B s2/s3为53342/47998条，共享K2为37076/35764条，新0.8B K0为10540/148542。两个完成CPU报告不变；这些是进度读数，不是质量/耗时比例。下次例行检查不早于20:30:47 UTC，期间仅明确事件定向核验。

## 20. 保留完整Track K的最终评分源码准备（20:24 UTC）

6bac4c8新增r3_final_eval_prepare.py，固定输入full_eval源码SHA 16e8401a2b90dbafbdbe6f82f0bbfa25aab48e51fb4ed1b4ce842e25d88d0b8c，生成独立副本，不修改运行闭包。生成副本SHA 1c129eb8b4ff40e02f3718cb3c4db7590e4ce4b6c589c249986a21a000aedfa8，位于.local/preparations/final-evaluator-20261031-v1。普通入口拒绝test；受控入口要求两套active/reserved预约、相同输出/FINAL/模型身份，精确calibration,test与k stage、fp32/HF32关闭/record-grade。授权仍通过原TL.authorize_test_read；不通过私有_TOKEN造票。原run_track_k及其数值函数AST保持相同，完整provenance/harness检查保留；返回未登记的完整报告和原tickets，交由后续事务层发布。6项CPU检查通过，使用真实生成函数与合成模型/producer，不代表真实推理验证。

该副本deployable=false。受控接口的Python预约对象用于防止误调用，不是抵御任意Python执行的安全边界。事务当前仍需接入live leases；完成后的只读来源复核、完整闭包/精确计划launcher及独立审查未完成。未读取真实测试数据、未发真实票据。未进行额外NPU巡检；上次20:20:47，下一次不早于20:30:47 UTC。

## 21. 真实入口控制流与恢复接口接通（20:27 UTC）

0503b13将事务有效预约传入新版评分入口，新增r3_final_test_adapter.py保存完整TEST-PRODUCER-REPORT.json并把其规范SHA写入两套暂存结果。首次执行通过原授权器取票、原verify_test_result核验；重启后通过新testlock的verify_reserved_test_result在同身份双锁下复核staged、完整日志意向、完成状态、FINAL及模型，再在函数内部创建仅供原来源验证函数使用的能力，不返回票据、不调用scorer。它是显式新增的恢复验证接口，不通过外部直接访问_TOKEN绕过；原authorize_test_read逻辑不改。

4项新增集成测试运行实际生成的guard/recovery控制流，合成producer、模型、FINAL及来源验证替身。模拟第一套日志提交后中断，再调用时授权累计2次、评分累计1次；改变FINAL/报告与来源验证失败均拒绝。连同准备器6项和原事务/日志22项共32项CPU测试通过。此证据不是实际冻结verify_test_result、完整指标CPU复算或真实NPU推理通过。

独立准备v2路径.local/preparations/final-evaluator-20261031-v2，生成testlock SHA dc38840f9c244521d0084631cedf87eac4796851792310e4658ed80f39dc34d6；full_eval与v1相同，组件SHA均落PREPARATION.json。deployable=false；仍缺完整闭包/精确计划launcher、真实来源及次级指标独立复算集成验证、正式资格与实际独立审查。未读取真实测试数据，未新增真实FINAL/票据，未额外巡检NPU。

## 22. 原始来源核验函数集成验证（20:30 UTC）

766de3d新增7项实际冻结源码验证测试：使用临时合成权重字节、FINAL、完整1200/656人口及variants/退化对照、逐行stamp和manifest，运行原model_identity、PV.verify、manifest检查、validate_population、headline与TL.verify_test_result，不替换来源检查函数。恢复验证入口在第一套日志落盘后模拟中断，重启后原来源检查通过，评分累计1次；错误headline、数据哈希变动、权重变动、producer文件哈希失配、同数量错误题目身份、存储决定错误均拒绝。数据读取guard拒绝临时目录外的jsonl。共39项相关CPU测试通过。

仍不能称真实模型验证：producer是合成函数，权重字节只用于哈希，calibration/operator及其他次级指标尚未独立CPU重建。LoRA model_identity只包含adapter与base revision/path，未包含base权重字节；最终launcher必须绑定完整基底文件库存和哈希。原prechecks代码读取manifest未显式关闭产生ResourceWarning，冻结代码保持原样，此非失败但记录为维护问题。source哈希及范围见final-source-fixture-verification-20261031.json。测试未读取真实测试数据、未改变现行任务。正式资格/独立审查仍缺失。

## 23. 完整Track K数值重算模块（20:33 UTC）

28e8ddb新增r3_final_metrics.py：用冻结C/E/D/V指标函数从raw readouts分别重算校准fit、主准确率与并列、近似并列、重复选项、金标分布、常数/均匀/question-only/empty-input、permutation/NOTA/operator及variant分母。输入人口逐行验证，数据哈希同时匹配manifest和producer header；多出未核验字段也拒绝。现为独立模块，尚未强制接入事务首次/恢复来源验证；不能称发布门完整。

4项新增测试执行原run_track_k源码AST（数据IO、scorer和precheck替身；数值函数真实），与新模块遍历存储读数的结果逐字段相等，包含并列分数及真实配对结构。篡改次级统计/常数对照/校准fit、producer data hash、新增无验证指标均拒绝。相关43项CPU测试通过。两边共享冻结公式，所以这是独立数据重建，不是公式独立实现或科学验收。没有真实test数据或模型推理。

20:31:03 UTC例行摘要：3训练+5推理，8卡驻留，failed/stalled均0；4B seed2 606/3116，逐候选K2 786/733；0.8BK0 16556/148542，2B s2/s3 59282/51294，共享K2 39500/39052。两份CPU报告完成，比较继续等K0。下一例行检查不早于20:41:03 UTC。驻留不是满载证明，记录占比不是耗时占比。

## 24. 完整数值重算成为发布必经检查（20:35 UTC）

0200faf在首次verify_result调用原来源核验后强制执行r3_final_metrics.verify；恢复的verify_reserved_test_result内部也强制执行同一重算，票据不返回给外部scorer。新增3项完整集成测试使用原run_track_k生成合成报告、原来源核验、完整重算及真实事务/日志代码：半提交恢复只评分一次；第二suite次级指标错误在任何日志写入前拒绝；报告及暂存SHA被一起改成自洽但错误校准时，恢复仍被原读数重算拦截。24项final测试加22项事务/日志测试，共46项通过。两个较窄fixture保留metric mock以隔离测试范围，不能与新增完整集成混淆。

准备v3独立保存所有组件和生成testlock哈希，deployable=false。当前尚缺完整冻结闭包、绑定完整base字节的exact-plan launcher、真实scorer中断恢复集成验证、正式资格与独立审查。没有真实test读取或模型评分，现行NPU队列不改。本轮无额外NPU检查。测试输出final-publication-tests-20261031.txt（含原prechecks的既有ResourceWarning）。

## 25. 完整最终代码闭包与实际base字节清单（20:39 UTC）

456f4c4新增r3_final_closure.py，验证原CPU闭包manifest 1c2f7d59dc365cbe52dcffe3fd9b734a8c09dc0612d35fe192703649710261df及全部27份源码，生成新评测/恢复代码、复制事务/指标等组件，并把旧公共R0绝对导入改为同级冻结r0_code。最终v2包含34文件，manifest SHA e58911da239b8e1041745103727a259679ac8753203387f3958baba0b21b265c，路径.local/preparations/final-closure-20261031-v2。真实进程导入核验通过；origins见final-closure-v2-imports-20261031.json。v1为加入inventory前的33文件历史准备，保留待查。

新增r3_model_inventory.py：无缓存读取完整目录所有常规文件，包含权重/config/tokenizer/index等；拒绝symlink及非普通文件；核对前后文件集、inode/ctime/mtime/size，计划绑定规范清单SHA，核验时再次读取所有字节。实际Qwen3.5-0.8B-Base生成13文件、1769913810字节清单，SHA60c18f0d586652119c7d64c9b7d41f9a90744978857b479a722b989d9ebe0436，存.local/preparations/qwen35-08b-base-byte-inventory-20261031.json。这是实际基底字节快照，不是准入或训练收益。

3项闭包测试和4项inventory测试通过，含实际新进程导入、外来预加载模块拒绝、文件增删改拒绝、相同长度且mtime恢复的权重变动仍识别。未改运行闭包；deployable=false，尚需最终exact-plan launcher使用外部pin绑定这些组件/模型清单，真实scorer断点验证及正式资格/独立审查。无真实test读取，无额外NPU检查。

## 26. 最终计划证据绑定预检（20:42 UTC）

ffea90b新增r3_final_admission.py，核对外部plan SHA、镜像/host/chip/固定评分配置、双suite/calibration,test、独立审查结构与exact-plan pin、eligibility/evidence/FINAL关联、完整闭包及实际执行的准入脚本来源，最后无缓存核对base及adapter完整字节。review独立于plan哈希避免自引用。它只验证文件绑定，不重算资格语义，也不能从JSON字段证明审查作者身份，尚不是可运行最终launcher。必须由上层实际独立评审确认资格与作者来源，不能靠测试fixture PASS授权。

5项CPU测试通过：计划/审查不匹配、审查无检查项/有blocker、证据变化、base权重变化、错误候选身份均拒绝；3项闭包回归通过。所有eligibility/review/FINAL均仅临时合成fixture，没有生成真实批准文件。新闭包v3 35文件，SHA7ed51e719352fd19f9b06e201f2a482fb6934f3e26095cd92c536f39deb9682a，实际导入核验记录final-closure-v3-imports-20261031.json。deployable=false，容器执行与资源领取/释放、真实scorer断点验收、语义资格复核和实际Astra审查仍待完成。

20:41:28 UTC共享例行检查：3训练+5推理；4B seed2 710/3116，逐候选K2 801/747；0.8BK0 20480/148542，2B s2/s3 67942/55070，共享K2 41548/41068；摘要failed/stalled=0，CPU仍2报告完成。下一例行检查≥20:51:28 UTC。未将驻留当作满载，未把进度作为收益。

## 27. 最终容器内驱动与提交前复核（20:44 UTC）

52546bb新增r3_final_driver.py：固定plan SHA后才创建输出，要求驱动从绑定闭包运行，核验所有runtime导入、准入证据与完整base/adapter字节，实际数据manifest路径必须匹配runtime KEV_DIR；评分参数只从固定配置构建，调用原make_score_fn及新事务。若已有staged结果，传入禁止评分的函数，不初始化NPU scorer。事务新增validate_publication钩子，完整来源/指标复核后、任一日志追加前再次校验准入与全部模型字节。改变模型/证据会留下staged并拒绝日志，不能自动替换结果。

driver持有输出锁，final-attempts分目录写持久日志、30秒脚本heartbeat、COMMAND与恢复说明、EXIT以及FINAL_EVAL_EXIT；失败尝试不覆盖，重复attempt拒绝。它不领取设备/启动docker、不生成review或FINAL；尚需外部最终监督器验证实际host/image/mounts、detached保留容器和资源claim/release。SIGKILL无法由Python finally记marker，必须由监督器在实际容器退出后补充终止证据，此路径未实现。

36项final及23项事务/日志测试通过，共59项；驱动测试用合成evaluate，非实际NPU执行。新闭包v4 36文件，SHA8203abf89dd63d5f55679179e5e7efa27aa26945086d169966689da7eec49dea，实际导入检查通过，deployable=false。仍待真实scorer中断验证与实际独立审查、正式资格。未做额外NPU巡检。

## 28. 最终容器监督与终止核对（20:48 UTC）

76c3106新增r3_final_container.py与r3_final_supervisor.py。固定pin容器名、原镜像、4个设备、network none、detached且保留；只挂载train/calibration与双suite clean/variants六文件，证据文件read-only，输出与round可写且FINAL单独只读覆盖。实际观察核对image/id/name/entrypoint/cmd/devices/mounts/env/非privileged。监督器复用原resource_adapter领取/释放；launch intent落盘后docker run不重发，失败/超时只观察原名，缺失已尝试容器拒绝重启；确认实际exit后核对driver marker再释放。

缺失marker时从实际容器exit产生明确失败证据：即使container exit0也记125，不伪造publication成功。既有driver exit与容器exit不一致拒绝覆盖。补写终止证据可幂等恢复。脚本30秒观察不会触发模型唤醒；模型例行600秒不变。

6项container测试、3项supervisor观察/identity测试、9项resource回归、3项closure回归通过。注意监督全流程尚未做真实容器集成，测试只覆盖契约和局部状态机，不能宣称实际test supervisor运行成功。代码闭包v5为39文件，SHA6043928ca980daf91b45588b9a8c684d031535af846e54a6db7c72de767f8a44，实际runtime import核验通过，deployable=false。仍缺完整监督集成/真实scorer中断验收、实际资格及独立审查。未启动真实test、未额外NPU检查。

## 29. 监督全流程模拟与真实CPU容器权限修复（20:51 UTC）

cf74bed增加5项监督全流程测试：Docker和准入使用替身，真实临时resource ledger、claim/release和原监督逻辑执行。覆盖claim→exit137补marker→release、同次监督恢复不再launch、docker run超时但容器已创建不重发、exit0无marker仍失败、driver/container冲突保留claim、既有容器消失不重启。5项通过。

实际host175固定镜像CPU容器检查v1发现root写入的mkstemp原子证据默认0600，宿主CPU不能读；非特权chmod失败，原现场保留。修复driver.atomic及transaction guard.atomic为0644，补权限断言。v2容器897a7340da464e096f4ca5cb96b4fa4aed373d9efb7433c4c7e1a7b6d723f21d实际exit1、devices=[]、AutoRemove=false，宿主成功读取terminal和heartbeat，未创建staged结果。此测试故意使用缺schema的合成plan，因此只验证实际启动/import失败留证与权限，不验证真实准入/评分。证据final-driver-cpu-failure-20261031.json，CephFS final_driver_cpu_failure_probe_20261031_v2/RESULT.json。容器内UTC与管理端clock有偏差，不据此推算耗时或队列效率。

驱动4项及执行guard8项通过，事务日志此前23项回归通过后增加1项权限断言。闭包v6 39文件，SHA ccd31fea09627c8f62b8258cad355389c068e255e9ca03fc79d3d4cdfeb033c0，包含全部权限修正；实际v2探针只含driver权限修正，guard权限尚无真实容器写入验证。deployable=false；实际完整final-supervisor、NPU评分中断恢复和独立资格/审查仍未验证。CPU探针定向检查不属于NPU例行巡检，运行NPU任务未变。


## 评分进程恢复：原始存储进程死亡验证（21:04 UTC）

提交3b2ba35运行原冻结core_r3/VerifiedStore/provenance代码，70条合成评分、chunk32，真实子进程SIGKILL。4项通过：已提交32条不重算；未提交尾部重新计算并与连续执行一致；已提交内容损坏拒绝；截断尾部恢复且保留已提交字节。它证明存储进程恢复行为，不证明NPU评分数值一致。

真实评分探针准备目录为CephFS dev_scoring_recovery_20261031_v1；39文件冻结闭包迁移后实际import-origin核验通过。使用Qwen3.5-0.8B-Base加已完成K1 seed2未合并LoRA，适配器3文件43,347,417字节、清单SHA ec2bcccc6319d1a8f8f6f80b8ab2d18d48d89a3a5c7a6aa84f87fa2969dd2bff。固定decision/transfer native dev各前4条，分别77/4候选，不能代表完整任务分布。计划reference→已提交2条后SIGKILL→resume，最大差1e-3、argmax/tie一致、已提交不重算。尚未激活，不声称真实评分恢复通过。

Astra专门请求仍只有规则确认、无工具/产物，继续NOT_REVIEWED；本轮工程子智能体实际产生了代码与测试，两者不可混淆。


## 开发集真实LoRA评分恢复已排队（21:06 UTC）

代码8987ae9：探针拒绝NaN/Inf、分数长度和人口错误、元数据/决策不一致、闭包外模块；中断标记绑定计划、前2条key和已提交字节。描述修正为实际chunk2。DONE绑定probe计划，base/adapter完整字节在评分前后核验。26项CPU测试通过（4存储进程死亡+9人口/数值反例+13启动器组件）。启动器三阶段实际全链尚未执行，不能由组件测试推断整链通过。

固定镜像CPU预检容器5d44e23b0d149ab1163da7c0d9f7a18718c45d4aca6e6217233175bc3cef9cb3已实际exit0、devices=[]、AutoRemove=false，验证实际挂载下的计划与依赖。实际source args解析接受未合并adapter/dev；未构造NPU scorer。首次宿主默认python3不支持-P，启动前失败；改用已有后继服务的/usr/bin/python3.12，未产生重复任务。

后继已激活并核验实际PID755638/完整命令；状态waiting_previous_release。链路chip3：现有2B K1推理→2B K0→fast_ref v2→prefix v3→评分恢复v1。执行计划SHA3667403538ec611533bb9d9fdccbd513efd0670fb524fdb1154f6f0d6e41102b，后继SHA1a5dc1fba8f175b10b4ec5c854f30dbdb4ec79abab3b404d9ab669b82fb27069。前序真实退出/释放后自动执行，不影响已运行任务。

恢复链持有一次资源claim，三容器均保留，只有interrupt的137且证明相符才继续；实际退出后才释放。观测未知只继续观察原容器，不能重发docker run。相同attempt恢复观察；失败评分需新计划，不自动改参数重试。整条链真实结果仍待执行，正式测试资格/Astra验收仍未完成。


## 配对测试向量和最终收益计算集成（21:21 UTC）

提交4778bc6：完整来源/指标重建返回两suite的有序key、binary correctness、test数据SHA、n及tie数；原始首次和受控恢复路径都返回相同向量，双suite完成后driver写TEST-VERIFIED-VECTOR.json。训练manifest在准入/评分前和提交前按实际训练来源核验并只读挂载，种子/方案不能由目录名称猜测。导出失败只能在同plan恢复核验，不能重新评分。

比较器要求seed2/3、同基底完整字节身份、相同数据/评分协议、1200/656逐问题人口；按问题先平均双种子，然后调用固定原始10000次/seed20261030/90% bootstrap。+1pp/−1pp边界用精确有理计数。数值条件满足不等于正式收益验收。最终campaign汇总/真实结果发布仍未执行。

62项final相关CPU测试通过，包含原始producer/来源/完整指标及恢复的合成集成；30项scoring-recovery测试通过，其中新增4项使用真实临时资源账本和模拟Docker验证三阶段/异常/监督器恢复。真实NPU三阶段探针仍排队。最终闭包v8含40文件，SHA22ea3e632c87d51725e1f674f05861a3bae6c1302afa95006ecd78ecc2e0cb70，真实import核验通过，deployable=false；不替换已排队dev恢复探针的冻结v6。

### 新确认的正式资格缺口

逐条复核R3 §8.4：0.8B最终测试要求K1-QO和K1-PT训练对照。当前队列尚未覆盖，最终准入白名单亦不能表示PT的instruct基底。须实现或经明确的日期化协议修订处理，不可静默忽略。未有训练QO对照，不作semantic-transfer声明。已有工程K1/K2不因后续JSON标记获得正式训练资格。当前正式准备器仅支持0.8B K1；K2/较大尺寸需相应正式方案。

本次审计依据与路径见.local/reviews/formal-eligibility-gap-map-20261031.md；它是工程核查，不是Astra验收。后续优先把控制组/规模协议差异具体化，再形成可审查方案；无新增用户决定前不删改原规范，也不停止已授权实验。


## QO/PT控制训练—推理—CPU链路激活（2026-10-31）

cfafc1d增加显式工程控制身份：K1-QO Base seed2训练--drop-state，评分原full_eval按arm自动drop；K1-PT instruct seed2/3完整input。训练器源码与原K1相同；启动/评测计划及实际manifest交叉验证，拒绝控制伪装普通K1、错误seed/base/dropflag。CPU控制报告标记非候选，不混入K1/K2均值。16项控制测试、30项posttrain回归、8项CPU报告测试通过。

实际PT CPU镜像容器95db62530cc932e6e11b3bfc952422114ff20c560cf24ccc3ca35c6d483f5a4b exit0、devices=[]、模型只读，186LoRA对/372张量/10822656fp32参数，非LoRA及embedding/lmhead冻结。QO训练20条×seed2×epoch0/1得到26/24增强样本：仅移除Input段，question/options/gold/response保持，重复构建确定性；两模型config结构相同不等于权重相同。

三路均3116步已冻结：QOseed2 chip0 SHA0e78cff856e892d2b6ea550b03b53e9e91ce1954aa216512955e1ea230cb0191；PTseed2 chip2 SHA9c7a1493b34e891e784b4c3d860aba3c6e4c89ea5b8939ebb6c45b50b993b871；PTseed3 chip0 SHA8a4de3b188b5415b621e31dd899b595638a85674376aa456d3cc0c80e0a9ee2b。

后继934466、训练后推理934446、CPU报告2435740实际命令均核验。chip0共享K2seed2推理→QO训练→QO推理→PTseed3训练→推理；chip2共享K2seed3推理→PTseed2训练→推理。三份控制报告在独立有限CPU队列串行处理，与现有报告服务/NPU队列解耦，不替换现有v10。当前等待前序释放/训练/推理，三路控制没有开始训练。

边界：这是已授权工程控制，不是正式资格或独立Astra验收。PT对R0的B-4需单独R0配置评分，普通r3配置报告不代替。正式测试准入对控制的支持、语义资格和最终campaign成员仍需补齐。最近21:25巡检3训练5推理，无失败停滞；4B1129/3116，逐候选K2为862/811，新0.8BK0为30144/148542；下次例行≥21:35:08UTC。


## PT R0 独立评分与最终成员检查（本轮增量）

代码f253c35。PT R0闭包28文件，manifest 7a5388bcfe283345d956a75c27620919d662691a757b1a6470eb71112e5a746d；后继queue SHA94e63f590d00017282176758b6ed74fee50c465d25853c31d24dc1780ae08348，PID1051352实际命令已核验。两项评分等待训练及普通评测退出释放；新after_eval依赖检查实际容器状态，不凭marker启动。原冻结队列不变。

PT准备/报告14测试、posttrain35、control16、六成员结构6测试通过。CPU B4库已补完整底座文件哈希与双方评分spec绑定，保留不同有效分母单列，不新增分母相等gate；仍缺完整执行消费者和R0源报告验证接入。六成员结构检查未接入final admission，不产生资格。Astra本轮仅确认规则，NOT_REVIEWED。PT CPU构造后14文件全量哈希复核一致，证据POSTRUN_MODEL_VERIFICATION.json SHAe4a666292ea3e06e6518d5d3603797ff1c26d9ea0489d0bf6008d30f7a2d074c。

下一阶段：接入PT CPU有序报告消费者；将完整campaign身份与正式资格/选择证据接入最终准入；消费已排队K0/R0/恢复验证实测结果；获得真实独立审查后才能锁定候选并发布同测试集收益。无需重新决定已明确的范围/算力/轮询策略。


## 日期更正与增量：补齐七成员及CPU消费者（2026-10-31 21:54 UTC）

此前“六成员”遗漏instruct K0；依据R3§2.1/§7.1/§8.4已更正为候选双seed、Base K0、instruct K0、QO seed2、PT双seed，共7项。旧六成员陈述仅作更正历史，不再是当前权威。instruct K0执行fc5c7c508d0b4941e210bfd050d219f6ff44f9b94e5589eeff0d811a5389b4bb，后继queue758c2d75f883d40b091c800d809c02bb15ed8b99f95de63b755affc9facc61a0，PID1133842实际命令已核验，排PT R0 s2后chip2。

代码7349e99。PT CPU消费队列b0c240457c29e7ec276d145f2f5de2186061f2aab212f08aa12ee1e023a80e46，配置d7cdf1c4638e2845b118be1794a0abd9c153c484750ae1117b9351d617c43cc9，PID2453257实际命令已核验；3任务等待推理。读取源读数重建R0并精确比对存档报告，核验双方28文件科学代码及底座bytes，再生成PT B4。修复scorer完整字典会因adapter不同必拒绝的问题：分别核对身份后比较其余协议。PT22+CPUqueue21+campaign7+instruct3测试通过，未代表实际报告已完成。

下一阶段是正式资格及control-aware final admission、QO输入模式与完整campaign源身份接入；真实NPU恢复和同底座比较继续由既有队列推进。Astra仍无有效审查，不生成FINAL或候选test读数。


## CPU消费者v2修复（2026-10-31 22:00 UTC）

工程独立审查真实复现冻结R0 E没有verify_task_manifest，原模拟stub掩盖此P1。e80e81a将builder逐行无LF哈希/记录数核验实现于独立PT库，并用实际冻结模块逐项API+synthetic population测试，24项PT tests通过。未改科学公式。v1 PID2453257核验实际命令且无worker后经pidfd停止，/proc确认消失；v2 PID2458931实际命令已核验，3jobs等待推理。当前queue SHA90fafd3619c711be888d4d066975b96953a5ae99f1e76877a26ee0e927732dc4，config67f617092e6b570a5f0cbcef768371dac47521d8928ed38fd25e863fcbbf3024。v1为保留过程证据，不再权威。没有NPU任务中断。审查属于工程验证，不是Astra验收。


## 监控频率约束确认（2026-10-31）

主会话与所有子智能体共享至少600秒的例行NPU检查间隔，沿用.local/NPU-MONITORING.json持久化时间和.local/operations/inspect-once.py文件锁入口。到期仅允许检查，不强制唤醒；不通过模型等待/查询循环消耗tokens。明确完成、失败、停滞、队列耗尽或设备空闲信号可提前定向核验；没有新变化不重复汇报。脚本派发、资源释放和CPU结果处理保持独立，不能因模型降频而延迟后继实验。此轮仅核对本地策略与代码，没有查询NPU实时状态；不声称新增了外部事件推送服务。该说明已补进CLAUDE.md协作规范。


## 七成员最终评测链路集成（2026-10-31，CPU工程里程碑）

最终准入现在要求七成员campaign与eligibility、FINAL、review清单精确一致；当前执行成员的基座、种子、训练manifest和配方均绑定。支持Base/instruct K0、QO seed2、PT seed2/3；更大尺寸最终协议仍不自动套用0.8B。QO评分和导出向量明确drop input，PT保持full，控制组不能进入候选收益汇总。发布与受控恢复在读数据前检查producer header和模型/scorer身份。

独立工程审查发现恢复代码把文件字节SHA与规范JSON摘要比较，会拒绝正常恢复；已修正为既有G.digest约定，未改变历史摘要协议。补齐恢复fixture并增加直接恢复错误输入模式在来源读取前拒绝的回归。NumPy CPU环境86项final测试全部通过，包含冻结producer指标重建与合成来源/恢复测试；没有读取真实候选测试集。新冻结闭包v9包含41文件，SHA b9a05125cbf61cd571f813fa32e57657c141d6b730468000ee152fc1812c286a，import验证通过，deployable=false；未替换已排队的恢复探针闭包。

这只完成工程绑定，不建立全体成员的来源真实性、正式训练资格、候选锁定或Astra审查。现有工程代次不能改标签升级为正式结果；仍等待新K0/R0、真实恢复证据和有效独立审查。最新NPU读数仍沿用21:56 UTC快照；本轮没有新增NPU查询，监控规则已同步远程。


## 全成员来源重建与正式恢复证据接入（2026-10-31）

新增r3_campaign_sources.py：由外部钉住的开发报告工具和冻结科学闭包，重建七个成员的开发/校准报告；验证完整base/adapter字节inventory、真实训练manifest、模型身份后组装campaign。输出仅工程来源证据，不生成ELIGIBLE/FINAL/审查，不把调用者请求的arm视为最终选择。真实七成员尚未齐备，未运行完整实证重建。

新增r3_resume_reconstruction_evidence.py，并接入正式K1 prepare/launcher：正式新计划必须绑定CPU张量重建结果及其原始target plan。原receipt validator同时校验原target和新正式target，完整输入inventory精确一致；重建数值、固定代码SHA和报告pin均校验。旧工程队列不受影响。产物绑定不认证审查作者或伪造文件的执行真实性。

QO/PT形式支持已完成规范/代码缺口审计，见formal-control-preparation-gap-20261031.md。两者不能复用Base/full恢复合同；QO需dropped-input证据，PT需instruct K0/LoRA；K2现恢复合同明确拒绝。不能只改engineering开关。现阶段继续已排队工程代次并准备正确证据，未扩大D1。

Astra v9实际子智能体只确认仓库规则，无审查文件或发现，记录astra-campaign-v9-attempt-20261031.json为NOT_REVIEWED；未构造PASS。


来源聚合审查发现P1：逐成员核验不能保证第七个完成时第一个仍未变化。正在补全原始输入快照和最终全成员复核；该工具尚不作为真实来源通过证据。恢复重建绑定组件未发现新增阻塞，已接入正式prepare/launcher并通过8项专项测试。


来源快照P1已修复：保留所有读取的原始文件/目录集合与模型字节快照，并在七成员重建结束统一复核。10项测试通过，覆盖第七成员处理时修改第一成员adapter/report/raw readout/manifest和文件增删；仍要求来源冻结，非文件系统原子快照。尚无完整真实七成员输出。

QO/PT恢复准备器已实现并通过4项测试，严格绑定seed2、输入模式、底座、代码和检查点pin，保留20步/10+10/三副本/腐败控制阈值。当前只生成deployable=false草案：通用launcher未支持控制恢复，源控制训练也尚未在最新快照启动。下一步补专门恢复准入与后继配置，然后在真实训练检查点就绪后生成新工程代次；不能称为已排队或已跑恢复。


## 控制恢复与CPU后继已激活（2026-10-31）

修复前文“未接入启动器”的状态：QO/PT工程恢复现在可finalize为真实计划，校验精确seed2/底座/输入模式/源checkpoint/冻结合同及container mounts/environment。源checkpoint事先固定3000，不是200：trainer仅保留最后2个，完整3116后保留3000+3116。原20步/10+10/三replica/腐败控制和阈值不变。

控制后继v1 queue SHA600839a3d45a392b76f86a60478a01603309b3ee87a845cecef78b0e9a4232a9，PID1574266实际命令核验。QO chip0等待PTs3 R0评分退出/释放（绑定原producer queue及动态执行身份）；PT chip2等待instructK0退出/释放（固定execution pin）。两者先等各自源训练成功。CPUqueue v1 SHAde997ff6f5e8777345ed928bf509eeed82e3ae711ccadc44d92faea28d12eb83，PID1575877实际命令核验，独立有序等待恢复完成。当前分别waiting_source_release / waiting_restart，没有开始恢复，也未占新NPU。

39项control-resume测试通过，另5控制训练+8正式重建准入+7launcher回归通过。fixed-image实际CPU synthetic tensor6tests容器exit0、marker0、devices=[]、保留可查。独立工程复核无新增阻塞；这不是Astra。已冻结的队列/工具与review产物字节一致并在175 verify通过。工作tree正式训练gate不放宽，不读取真实测试集。未来真实数值恢复、CPU重建、正式资格与Astra仍待完成。

## 2026-10-31 22:59 UTC — 控制组 CPU 证据里程碑

QO 真实 CPU 数据契约已通过：decision-v7 训练集 20 条记录，epoch 0/1 分别检查 26/24 个增强样本；删除输入状态后，问题、选项、任务、金标和 response 保持一致。PT 固定镜像 CPU LoRA 构造已通过：Qwen3.5-0.8B instruct、186 pairs、372 个可训练 tensor、10,822,656 个 float32 参数，非 LoRA 参数冻结且底座只读。两项均为准备证据，不读取测试集，不代表科学接受或正式训练完成。

正式 QO/PT 准入程序已接入控制角色、模型、输入模式和独立容器身份，并保留 K0、恢复重建、正式审查等门槛；代码提交 `3060b1d` 已推送。正式训练尚未启动，真实证据包和独立 Astra 精确计划审查仍缺失。例行 NPU 检查继续遵守共享 600 秒窗口，本次未追加 NPU 查询。
