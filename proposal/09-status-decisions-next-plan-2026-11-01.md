# 当前任务状态、待决策事项与下一阶段计划

更新时间：2026-11-01 UTC。运行快照截至 03:14 UTC；以下工程验收更新来自该日独立收据。本文覆盖当前结论；旧版过程记录保存在本地 archive，历史测量值不改写。

## 当前结论

参考基线入口已经恢复并同步到 [GitHub](https://github.com/chaosxingxc-orion/nga/blob/main/experiments/REFERENCE-BASELINE-LATEST.md)：固定 38 个模型×数据集单位中，36 个有结果；Open-Jev-2B×JEVal 和 Open-Jev-9B×JEVal 仍为 blocked/null。不同温度、公式、有效分母和发布掩码单列。36 个有结果不等于所有历史证据都通过完整验收，缺失的历史 audit-SHA 绑定等限制保留在基线页。

工程训练和推理已经启动，开发集有明确收益信号，但尚无获准发布的候选测试集训练收益。K1 相比 K0 的开发结果更好；共享 K2 未建立优于 K1 的证据。工程版 QO/PT 控制训练正在进行，新的正式控制计划和独立准入仍不完整，不能把工程运行等同正式实验通过。

## 当前执行与效率

03:14 UTC 有界检查记录 host175 的 3 个训练容器、5 个推理容器；watchdog 最近一轮无失败或停滞告警。这是任务运行数量，不证明持续满载。

| 工作 | 已核实状态 | 下一依赖 |
| --- | --- | --- |
| 逐候选 K2，0.8B seeds2/3 | 1,356 / 1,298 步，各目标 3,116 步 | 实际终态、后继推理、开发计分 |
| K1，4B seed2 | 3,116 步，真实 exit0；后继推理已启动 | 推理完整收据及 CPU 计分 |
| K1，4B seed3 | 2,460 / 3,116 步 | 队列自动接续 |
| 首轮六路候选推理及 0.8B K0 | 各 148,542 条记录 | 该计数不是测试集样本数或收益 |
| 2B K0 | 46,198 / 148,542 条，31.1% | 完整推理收据 |
| 工程 QO/PT 控制 | QO seed2 在 01:46:46 UTC 真实 exit0，已自动接续推理；PT seed2 也已接续推理，PT seed3 状态以其队列为准 | 各自恢复/重建与比较证据 |
| CPU 选择队列 | 10 done、6 waiting_reports、10 waiting_inference | 按依赖有序消费 |

NPU 任务队列与 CPU 分析异步运行，CPU 复审不阻塞无依赖的 NPU 后继。主会话例行巡检共享约 600 秒窗口；只有明确终止、故障、空闲等事件才定向提前检查。队列脚本持续执行，不依赖模型每轮唤醒。芯片 4 命名导致的接续故障已修复，不能继续列为待修复事项。

已有 watchdog 的 02:32 UTC 利用率摘要显示：chip0–5 的 60 分钟 AICore 均值为 83.0%–94.7%，逐候选 K2 所在 chip6/7 为 58.7%/49.6%，每芯片 6 次采样。因此八芯片驻留不等于持续满载。02:41 结构化训练摘要显示 K2 seed2/3 分别为 0.241/0.232 基础问题/s/chip（各 1 芯片），AICore/HBM 摘要为 14.5/14.4 GiB 使用量，后者不是 reserved memory。源码中的逐问题 forward/backward 和逐问题标量同步是待测效率假设，尚未证明瓶颈。下一步需要同样本、同 loss/gradient 噪声容差的批处理性能验证，不能未经等价性核验替换运行中的冻结代码。

吞吐使用每芯片口径并注明芯片数；不同候选展开方式不能直接比较 token/s。01:40 摘要没有完整 reserved-memory 数据，不据此给出全面效率达标结论。后续速度优化必须保持 loss/gradient 在登记 bf16 噪声范围内。

## 开发集比较里程碑（2026-11-01 01:16 UTC）

实际开发集比较与输出终态已核对，输入报告哈希一致。K0 为同骨干确定性基础模型；候选使用 seed2/3 等权平均。下表是开发集准确率，不是测试集成绩、真实业务收益或一致性指标。

| 开发集 | n | K0 | K1 均值 | K1 − K0 | 共享 K2 均值 | 共享 K2 − K1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| decision-v7 | 1,264 | 58.3861% | 82.9114% | +24.5253 pp | 83.0696% | +0.1582 pp |
| transfer-v4 | 656 | 60.5183% | 64.1006% | +3.5823 pp | 62.9573% | −1.1433 pp |

K1 相对 K0 的配对 90% bootstrap 区间分别为 [22.1519, 26.9778]、[0.2287, 7.0122] pp，两者下界均大于 0。共享 K2 相对 K1 的区间分别为 [−0.5934, 0.9098]、[−2.5915, 0.2287] pp，未建立优于 K1 的证据，而且 transfer-v4 的点估计退化超过登记的 1.0 pp 界限。不能只挑 decision-v7 的微小正差宣称共享 K2 更优。

两种训练均通过 K-floor；K1 通过开发 K-align，但这些门槛不是正式科学验收。共享 K2 另缺 R0 gating，候选未锁定，同测试集收益未评测。下一步保留 K1 作为开发比较参考，不采用共享 K2 替代，不事后修改阈值；继续已有逐候选 K2、模型规模及控制实验。详细逐 seed、CI 和原始报告路径保存在 `.local/reports/dev-findings-current.md`，结论同步到远程 Wiki。

## 恢复与工程验收

旧 Base K1 step2200 恢复的 NPU 退出和资源释放为 0，但原 checkpoint 被 keep=2 清除，CPU 重建退出 1。旧失败保留，不回填原路径，也不以剩余 SOURCE.pt 副本自动替代原始证据要求。保留副本方案的独立审查要求补足来源、完整 recipe 和状态验证，当前不采用它绕过阻塞。

新的 Base K1 恢复使用真实保留的 step3000：仍为 20 步、3 replicas、10+10 分段及原阈值。固定镜像无设备 CPU 结构预检退出 0，核对 372 个 LoRA tensors 和 372 个 optimizer states、scheduler step3000；这不等于恢复后的数值一致性通过。新计划 33 项冻结依赖已逐项复哈希，已排队等待 chip1 的 R0 释放。实际 NPU 恢复、独立 CPU 数值重建和精确计划验收仍未完成。自动 CPU 接续现已部署：`base_retained3000_cpu_queue_20261101_v4`，host175 PID `3076653` 的实际命令已核对，状态 `waiting_restart`；每 600 秒检查实际退出/释放后，使用固定镜像无 NPU 设备容器重建。13 项相关测试通过。最新代次已包含源码边界与共享容器校验，第五轮代码审查发现的执行前校验缺口已修复并部署到新代次；源码修复已通过后述第七轮有限范围复审，实际数值结果仍待完成。

Astra 第二轮为 CHANGES_REQUIRED，六类问题涉及实际数值重建、执行源码身份、保留容器配置、目标一致性、scope 矛盾与禁止文件的读取顺序。对应修复已提交；现有证据包括：

- 固定镜像无设备 CPU 的 53 项重建相关测试，124 个冻结源文件哈希复核一致。
- K0 禁用依赖读取顺序修复及相关 30 项 CPU 测试。
- 真实保留容器的有效配置与启动收据校验通过。
- 使用校验过的源代码重新生成和消费 K0：exit0，95 项输入、6 项检查，复哈希一致。范围仅限 dev/calibration。

第三轮及第四轮托管 Astra 均只返回规则确认，记为 NOT_REVIEWED；任务管理 MCP 接口也连接失败。第四轮只读 CLI Astra 已真实完成：exit0，输出哈希一致，review SHA `94117950ad68821696e7337fc36021899ac0b0e5dd2f5357cd38213e57a2b2c9`，结论 **CHANGES_REQUIRED**。它核验了 108 文件，确认目标身份与 scope 矛盾的原反例关闭；仍有外层 helper 字节码绕过、嵌套证据测试路径读取、正式保留容器有效配置不完整、CPU 接续校验较弱及审查包缺少 successor helper 五类问题。

`2a2035c` 已修复前两类路径：外层 admission/readiness/CPU helper 直接编译源码，嵌套 inventory 和单独 review/checkpoint 路径在内容读取前拒绝测试文件，原 checkpoint 限定到对应训练目录与步数。固定镜像无设备 CPU 新代次 70 项测试通过，真实容器 exit0，294 个冻结源文件复哈希一致。首轮因测试仍模拟旧导入接口失败，保留失败代次后修正测试再运行；未删改失败记录。`388cbcc` 已将 CPU/NPU 接续接到共享有效配置规则，补充 healthcheck、资源限制、runtime、init、额外环境变量等检查，并从真实 Docker daemon 读取默认 runtime/cgroup namespace。host175 实际默认为 ascend/private；旧保留 NPU 与 CPU 容器的只读正向检查均通过。固定镜像新代次 81 项回归通过、真实 exit0、冻结源哈希一致。首轮遗漏 synthetic fixture 的 daemon 默认值导致失败，保留记录后修正测试再跑；不改变生产默认值。02:17 UTC 已部署新的 CPU 验证代次：Base v2、QO/PT v4。旧控制器实际命令核对、暂停并确认没有 worker/准备意图/完成恢复后才停止，新服务 PID `2960970` / `2960999` 与命令已核对；均 waiting_restart。旧证据未改写，新收据尚待产生。

## 最终评测源码身份补充修复

在准备最终测试入口时复现了独立问题：旧 final closure 校验只检查预加载模块的路径，伪造相同路径的 `r3_final_metrics` 对象可以被接受。`e0f7277` 改为执行已校验源码字节，并统一 adapter、transaction、日志和 admission 的本地模块身份；反例包括预加载伪模块和恶意 unchecked-hash `.pyc`。50 项相关测试通过，新 41 文件评测代码闭包在 CPU 中实际导入 29 个模块，未访问数据或执行推理。

首版 41 文件 closure manifest 为 `8bb413901b01cb389a658bdde3dcfce072382075aa3529d76c35e5e29355f1a9`。其独立 Astra 已真实 exit0，review SHA `69d5ab37615d0a0d2a73d76f189f2023258f04b030dbc42195a140b716e3f98e`，仍为 CHANGES_REQUIRED：driver 启动/向量导出和 supervisor admission 存在外层字节码加载与旧 alias 问题。`2f13906` 已修复这些出口，25 项相关测试通过；旧 closure 不被追改或宣布通过；新 v2 closure 已冻结 41 文件并在 CPU 实际导入 29 个模块，manifest `90a3f779e4aaa49f4f095d148b42cb392f0f3f269aba143cd9ca01e6e25a8528`，仍 deployable=false。实际 scorer 中断恢复验证仍未完成。原排队探针绑定旧 closure，现已切换到 `dev_scoring_recovery_20261101_v2`，使用上述最新 v2 closure，仍固定两套开发集各前 4 条、chunk=2、1e-3 nats 容差，执行 reference→SIGKILL→resume。`162ef1d` 将恢复探针和 launcher 的 helper 改为直接编译源码；31 项相关测试通过，含恶意 unchecked-hash 字节码反例。新后继服务 host175 PID `3054827` 的实际命令已核对，保持原 chip3 前驱，状态 waiting_previous_release；旧控制器无 worker/意图/输出时才安全替换。新 execution SHA `90b88f7e37cadc4d3e31294183cc9a8c10525f2dcc8b94163351fb4a414ee314`。本补充修复晚于第六轮封包，已纳入第七轮独立审查并获得源码范围 PASS_WITH_SCOPE，真实恢复结果仍待产生。

第五轮统一代码复审已真实完成，410 文件全部复哈希一致，结论 **CHANGES_REQUIRED**，review SHA `a5864dcd89400a4bac1f82f064d0dc8de7e739d55331cdb77b58c7e909a9719b`。此前字节码、嵌套读取和 final bootstrap 的主要反例关闭；新发现三点：CPU 队列在可信验证前执行已准备的控制器、launcher 单独 review 路径可经软链接绕过读取保护、CPU 挂载缺少 propagation 检查。当前源码已补上执行前配置/库存/当前哈希校验并执行同一份已核验字节，读取边界拒绝相对路径/软链接/父级遍历，挂载要求 rprivate。14 项 CPU 接续测试、12 项 formal 测试及 4 项读取边界测试通过；固定镜像扩展回归 exit0：共收集 108 项，实际通过 96 项、12 项因镜像未挂载其源码 fixture 而跳过，不计为通过；294 个冻结源码与当前源码哈希均一致，保留容器实际 exited/0。首代因测试清单文件名写错失败，保留原失败记录后新建代次修正。02:32 UTC 已安全切换为 Base v3/控制 v5，实际命令与 waiting_restart 摘要已核对；正式准入和数值验收仍未完成。

已完成的开发报告正在独立源码重建：7 份均已重建 exit0，完整 JSON 和哈希均与原报告一致；原报告及其历史终态哈希也已独立复核未变。不覆盖历史报告，不读取候选测试集。下一轮复审将使用新的不可变包，并明确区分源码修复、实际部署和数值证据。

本轮将修复测试、报告核验、文档同步分别交给三个托管子智能体，但三个都只回复规则确认，未交付执行证据。主会话已接回必要工作；不将确认消息计作进展，不继续重复 ACK 循环。

镜像中跳过的 4 项 final closure 与 8 项 final admission 已在本机实际补跑全部通过。第六轮独立复审已完成，417 文件完整复哈希，review SHA `c14b5f5f700e46049e8501c8280a87ab42403fff24ea96f26d0a7cd4ade6652b`，结论 CHANGES_REQUIRED：三个原始 v5 反例均关闭，尚余 launcher 的 source_module 未复用统一路径读取保护。审查注明现有生产调用链会拦截这些路径，未证明实际启动绕过。`1892efc` 已令该 reader 复用 safe_content_path，并同步 CPU policy pin；14 项 CPU、12 项 formal、4 项读取边界、31 项 scorer 恢复测试全部通过、无跳过。最新 reader 修复已进一步部署到 Base v4/控制 v6；旧空闲控制器确认无 worker/输出/意图后才替换，新 host175 PID `3076653` / `3077221` 实际命令已核验，均 waiting_restart。第七轮已合并此修复和 `162ef1d` scorer 补充修复，冻结 422 文件，manifest `6276edd8bb3142200541b336717503e5bb4f09612ea54a0facce108612000306`；第七轮已实际 exit0，review SHA `fb18607bdfdcaa81bc73e3cac9d9aeff0eb8e41dfcb617fb5ef25e637642ceea`，结论 **PASS_WITH_SCOPE**，源码修复范围内无阻断发现。独立反例验证了全部读取边界、11 类 prepared-controller 变异、28 类 propagation 变异和恢复 helper 字节码排除。主会话额外核对审查源码与当前源码及 Base v4/控制 v6 的实际冻结文件完全一致。审查报告中的“未部署”描述反映封包时点，部署一致性由后续独立哈希核对补足。范围不含实际 tensor/scorer 恢复、正式计划批准或测试收益。托管路径仍不执行，沿用已披露的受监控 CLI 后备路径，不将其称作托管子智能体。

K2 效率候选已实现（`f756f52`）：保持每问题 forward/backward 与 dropout 顺序，仅将每问题 loss 标量传输延后为步骤末一次传输。固定镜像 CPU 的 3 项合成测试通过、无跳过，loss/梯度/RNG/调用顺序一致且 K1 源码路径不变；不能据此推断实际 Qwen/NPU 提速。真实 NPU 配对 benchmark 已冻结为 `k2_deferred_sync_benchmark_20261101_v2`，plan SHA `691269c4964fdb9ad51dda470e015789fdc0df92ed8ecd53b3bbe55373a8e0d6`：3 对 warmup、10 对测量、至少 60 秒、每芯片吞吐/reserved memory、逐元素完全相同的 loss/gradient 门槛、速度至少 1.05× 才保留为候选。不更新模型权重，仅检查初始 LoRA 的固定训练步骤；该初始代次随后由下述 v3/v4 执行代次承接，目前仍无真实运行结果，也不在第七轮审查范围内。后续需独立审查和 NPU 实测后才能决定是否替换训练实现。`0601db4` 已补齐脱机资源执行器：固定镜像、保留容器、按实际退出释放、缺少 driver marker 时失败、启动不确定时不重复发射；4 项生命周期测试通过。完整执行代次为 `k2_deferred_sync_benchmark_20261101_v3`，execution SHA `52648b63e63d352b01ef57d5519ef87951919f85353aa4b956aca45275636bb9`；后继队列 pin `e0484cb9709940686292293536aed46213426325534597c07c785428bde20434`，计划接在 chip3 的 scorer 恢复之后，配置校验通过但尚未激活。独立审查包为 23 文件，manifest `d4fff588e73f7ee99453d7ea0c4ba9c3c8798b159825bf2888b288b9d2022db5`，该轮实际 exit0、输出哈希已复核，review SHA `17d77a3f9a25c62de7a85638ed16ef56c565fa40e84b870c5519daeea64054c6`，结论 CHANGES_REQUIRED：释放未绑定容器 ID、shm/ulimits/device 配置校验不完整、后继混淆 supervisor 125 与容器退出 0。 固定镜像已进一步执行完整 benchmark 合成编排测试：`k2_benchmark_orchestration_cpu_20261101_v2` 共 11 项通过、零跳过，冻结源码哈希一致，保留容器实际 exited/0。覆盖 28 次参考/候选调用、3 对 warmup 排除、10 对指标计算、梯度不一致拒绝、错误结果标志与释放收据拒绝。计时和模型均为合成 fixture，不是实际 NPU 性能。首代挂载路径 `/test` 被正确拒绝，失败记录保留，改为 `/validation` 后重跑；生产代码未为测试放宽保护。新增测试晚于当前审查封包，不声称由该轮独立复跑。


2026-11-01 修复增量：`13b3855` 已绑定释放与恢复证据的容器 ID、逐项核验共享内存/ulimits/设备映射，并区分任务失败状态与容器实际退出状态。29 项 CPU 回归测试通过（resource 11、successor 11、launcher 7），含释放账本写入前后崩溃恢复、伪造 proof/intent 和错误成功标记拒绝。修复后的固定镜像验证进一步完成 34 项测试、零跳过，13 个冻结文件与当前源码/原始 fixture 哈希一致，保留容器实际 exited/0（`k2_benchmark_repair_cpu_20261101_v2`）。首代漏带原始 trainer fixture 导致 3 项错误，失败保留；补齐哈希一致 fixture 后重跑，生产逻辑未变。该补充验证晚于 v2 审查封包，不宣称独立审查已覆盖此新增运行证据。真实训练输入 CPU 预检也已 exit0，保留容器实际退出 0：13 步、130 个基础问题、160 个增强示例，最长 1,036 tokens，21 项冻结依赖核验；未加载模型权重或使用 NPU。

新冻结执行代次 `k2_deferred_sync_benchmark_20261101_v4` 的 execution SHA 为 `bb1dbfef4584d53f88d71e5f53fea4159714762ff1a9339888970751f909bc0d`；后继 v2 pin 为 `0a18f3f865c94058483d32e16f19b0dcfbb9e9e38de596790cd44ce94b6ba2dd`，仍接在 chip3 scorer 恢复之后，**未激活**。独立复审 v2 已启动：29 文件，manifest `0c8ef2f0a4fe462c638faf74aac36373c5795279261dc1b7c73d643c3808cdaa`，该轮已实际 exit0、输出哈希一致，review SHA `b75809f6ca1dde7a5d785d6417e2475da6fe0cb7ab74f8edac3679659b68af51`，仍为 CHANGES_REQUIRED：首次身份检查后同名容器替换可逃过设备扫描，导致错误释放。其他配置、恢复及退出码修复通过独立探针。旧失败和冻结代次保留。当前无 NPU 提速、训练轨迹等价或候选测试收益的新结论。


后续修复 `176c666`：释放扫描不再豁免同名容器，在账本锁内及写入前重新核验实际容器身份、终态和设备占用。实际 supervisor→release 回归反例确认替换时账本不变、无释放/完成证明；固定镜像 v3 共 37 项测试通过、零跳过，13 项冻结文件哈希一致，保留容器实际 exited/0。新 benchmark v5 execution SHA `1ae7944ec5d07d1f1c6a94384b364e348ce500ebf297e2876623115f40393147`，successor v3 pin `309f5634a49cbb330d1c9fe8666ad928dd29dcbacd383d18b1ce98387501dfbd`，均 verify 通过，冻结时未激活。独立复审 v3 已完成，27 文件 manifest `7ad10eeffba29778b8241c5787f4ae79c1e3c22619c494cf61f8db62c554c55e`，实际 exit0、全部输出哈希一致，review SHA `fe2c68253dcfc881d5ca75d59a7a0ef90d8a0c036765290a9b8559f5c209775d`，结论 **PASS_WITH_SCOPE**。独立实际函数探针拒绝同名运行容器替换、写入前身份替换和新设备占用，未发生账本/证明写入。审查环境无可用临时目录，unittest 初始化失败，不将其计作独立复跑 37 项测试；前述固定镜像测试证据仍单独成立。主会话核验当前、冻结和被审查工具源码一致后，已激活 successor v3：host175 PID `3250629` 实际命令已核验，状态 `waiting_previous_release`。队列接在 chip3 scorer 恢复之后，benchmark 容器尚未启动；按真实退出/释放自动接续，不需模型轮巡发令。旧 PREPARATION 混入新版审查的问题已清理，历史输入预检明确标为历史证据。容器观测与账本并非操作系统级原子事务，保障依赖合作调度器遵循资源锁，不能声称阻止任意外部 Docker 管理员并发改写。

## 需要负责人决策的内容

当前没有必须追加授权的事项。继续沿用：38 个参考单位不扩展；不设置算力预算上限；先验证公开任务下 Jev 训练方案；暂不接入真实业务；开发集用于选择，测试集用于最终指标；不同文献统计方式单列；每个 milestone 更新最新报告和 Wiki，本地过程文稿每三天归档。

只有需要新增模型/数据集、改变业务问题定义、修改预注册指标或阈值、或全部已登记方案无法支持收益目标时，才提交具体证据供负责人决策。负结果照实报告，不事后调整口径。已授权的修复、队列接续和 GitHub 同步不重复请示。

控制实验的开发计分队列也已更新为 `control_cpu_reports_20261101_v2`，报告工具 pin 为 `6e44272fefd6fdab21540c39fd84f105386e54cfe9fd9c01a38f41fb46c3cd78`。旧服务确认尚无 worker、启动意图或报告后替换；新本地 PID `2633925` 与实际命令已核验，QO/PT 三项均等待推理。推理完成后自动使用源码身份修复版计分。该更新不重标历史报告，也不表示全部其他计分队列已升级；正式汇总仍需独立来源重建。

PT/R0 报告队列也已安全更新为 `pt_r0_cpu_reports_20261101_v3`，pin `19b6f3b022b3a32cfba2c0ec1203a2bdc9d6a9aeb08371f2d7c4fa077cdc14a5`；本地 PID `2643074` 的实际命令已核对，三项均 waiting_inference。7 项 PT 消费与 21 项报告队列测试通过，报告生成器采用已完成七份一致性重建的版本。主 CPU 选择队列已升级为 `cpu_selection_queue_20261101_v11`，pin `83cdee3edfdc0d5b565b3823055161063cf627a57a809874f468db55a52b714d`，本地 PID `2649053` 实际命令已核验。10 项历史完成终态逐项复哈希后继承并标记来源，未重新标注为新版验收；其余 6 项等待报告、10 项等待推理，将使用新版计分工具。后续正式汇总仍要求完整来源重建。

PT 正式准备的异步依赖已补齐一项：新增 `fresh-instruct-k0-prechecks`，在 instruct K0 报告成功且哈希一致后自动用同底座重建六项 K0 检查。复用已在 Base 路径执行的预检工具，未新增科学阈值。PT/R0 CPU 新队列 `pt_r0_cpu_reports_20261101_v4` pin `58e08d4b592830769007dc3fd725a165cbf71156d091935b71b47967ed9ade88`，本地 PID `2678295` 实际命令已核验；旧服务确认无 worker、启动意图或输出后安全替换。三个原任务 waiting_inference，新增任务 waiting_reports。产物尚未生成，不能当作 PT 预检通过。

正式准备路径已核对并留存本地依赖表：K1 的 Base K0 检查、训练证据与恢复计划存在，缺实际 CPU 恢复重建；QO 有 Base 检查与独立训练证据，尚待其恢复计划及重建；PT 有独立训练证据，尚待 instruct K0 检查及自身恢复/重建。存在性清单仅定位缺口，完成后仍需逐项哈希、数值验证及精确计划独立审查。未生成正式批准或候选测试许可。

## 下一阶段执行计划

QO/PT CPU 队列已进一步升级至 `control_resume_cpu_queue_20261101_v6`：原空闲服务确认无 worker 后安全停止，新 PID `3077221` 与命令已核对，两个任务均 waiting_restart，600 秒轮巡，包含执行前校验修复。Base v4 的新 PID 为 `3076653`。未改旧冻结证据或中断 NPU。

1. **保持工程队列持续消费。** 等已启动训练/推理的真实终态，按资源所有权接续；继续 2B/4B/9B 规模与逐候选 K2、控制实验。出现效率或调度问题先修复；不靠重复发射任务维持表面利用率。
2. **完成恢复证据链。** 新 Base 自动 CPU 重建队列已接上，等待真实完成并验收输出；QO/PT 各自产生恢复和终态，不能用 Base 代替。新版验证器需要新冻结代次，不重标旧收据。
3. **完成 K2 执行器复审并实测效率。** 第七轮读取边界审查已有限范围通过；K2 v3 独立复审已有限范围通过，后继队列已激活，等待前驱真实释放后实测。按同样本 loss/gradient 完全一致及至少 1.05× 的登记标准判断速度候选，保留失败结果。真实恢复/正式精确计划验收仍分别完成。
4. **补齐正式目标计划与开发比较。** 每个 control/seed 明确模型、输入模式、chip、container、evaluation 与精确代码闭包，完成 K0、恢复、独立重建及具体计划审查。开发集继续比较，保持共享 K2 不替代 K1 的现有结论。
5. **冻结候选后一次性测试。** 只在选择、来源、终态、准入完整后读取候选测试集，与同骨干 K0 和同口径参考表对齐；分别报告配对收益、校准和样本覆盖。当前不能提前填入训练收益。
6. **再推进业务缺口与学习方法。** 明确现有公开任务无法承载的要求，先做冻结数据集和直接驱动基线，再登记学习/优化及 RL；保持任务定义、无约束最优和鉴别对照完整。

## 验收与证据入口

退出当前阶段需要：全部 38 单位状态可解释；对应 K0 计分可核验；每个正式目标计划及独立审查完整；实际恢复/重建/终态一致；候选锁定后按冻结测试协议形成可发布收益。工程测试通过、exit0 或完整进度计数都不能单独满足这些条件。

- [最新参考指标](../experiments/REFERENCE-BASELINE-LATEST.md)；[远程 Wiki 四维结论](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions)。
- 本地巡检：`.local/reports/inspection-20261101T031433.json`；开发明细：`.local/reports/dev-findings-current.md`；CPU 验收：`.local/reports/cpu-repair-acceptance-20261101.json`。
- 新恢复计划 identity：`2f9cd65081c15e7039216a809a1dbe64d6e553422bb8e058ea060d5503fa5271`。
- 新 K0 bundle SHA：`8f97ec9e559830cf62f9ec15e064cce959a42ee65b7ca66a56a3835efb8f7810`。
- 第四轮审查 manifest SHA：`d06092db16ea55e32a7519e5bf3cc164bc60a174cd9ef187d0a1cd734aa58339`；范围为代码修复，非测试发布批准。
