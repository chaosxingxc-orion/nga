# NGA 实验入门：资源、运行与协作

当前经验证的启动入口见 [`EXPERIMENT-STARTUP-REPORT.md`](EXPERIMENT-STARTUP-REPORT.md)。启动新任务时先按启动报告执行。

同事现在就可以参与已保存结果的统计和 bad case 分析、数据及配置准备，并在已支持的范围内使用现有路径。工程基座 `engineering-base-rc1` 仍为 **`released=false`、stabilizing**；镜像与现有控制器并非可移植的任意新任务一键工具。主要技术约束是固定的身份、路径、配置摘要和 receipt 绑定；新任务需要相应集成，而不只是改几项 JSON。具体实验能否运行及其科学结论仍以对应协议和证据为准。

研究背景见 `survey/`，研究计划见 `proposal/00-research-proposal.md`，实验的指标、分割和阈值以 `experiments/` 预注册为准。远端结果记录放在 [GitHub Wiki](https://github.com/chaosxingxc-orion/nga/wiki)：在相关页面原位更新最新结论及证据链接，不把运行日志堆积在页面上。本地 `wiki/` 和 `experiments/` 中的过程文件按每三天归档；归档不改变预注册的规范地位。`AGENTS.md` 在当前工作区未跟踪，GitHub 克隆不保证包含它，无需把它作为读者入门前置条件。

## 快速定位与第一次交付

| 你要完成什么 | 本文对应章节 | 完成时交付什么 |
| --- | --- | --- |
| 找到服务器、模型、数据和镜像 | 资源与入口 | 可访问的路径及任务采用的 manifest；无需重新下载 |
| 验证镜像能够启动 | CPU Docker smoke | 独立的容器名、Ceph 输出目录、exit code 与 terminal |
| 理解和设置一次实验 | 如何开展实验设置 | 预注册、任务 JSON、宿主 JSON、接受的摘要及准备回执 |
| 启动受支持的实验 | H2：配置、只读检查与受支持的启动 | 操作员交付的准确命令、任务身份、资源绑定与输出路径 |
| 跟踪进度、判断完成、进行评分 | 生命周期与监控、完成一个实验 | terminal、release、冻结评分结果及独立复核 |
| 协作提交 | 分工与交接 | 结论、限制、证据位置和 Wiki 当前状态 |

首次接入需要已有的仓库访问权限、175 的 SSH 账户、Docker 操作权限，以及所用模型/数据的读取权限和个人输出目录的写入权限。`npu` 是维护者的 SSH 别名；同事须使用自己的已配置别名或管理员提供的主机入口。受保护 stage 访问失败时，由维护者交付可访问的任务包或配置相应权限，不修改现役目录的保护方式。

先完成一个 CPU 环境自检，再复核一个已发布的模型/任务结果格：记录模型、TEST population、指标定义、参考工作的计算口径与负面结果。数据同事可同时准备来源和 split 清单；操作员只对已经准备好的受支持任务启动 NPU。新模型、新目标或新增配置字段仍需维护者完成对应集成，不能把文中的 H2 示例直接改名后运行。

## 参与前拿到什么、完成后交付什么

| 环节 | 参与者拿到的输入 | 可以自己完成的操作 | 完成依据 |
| --- | --- | --- | --- |
| 环境接入 | 仓库权限、个人 SSH 入口、175 Docker 权限、Ceph 读写目录 | 登录 175，运行本文 CPU smoke | Ceph terminal 的退出码与保留容器身份一致 |
| 设置实验 | 预注册、模型/数据清单、对照、DEV/TEST 用途 | 准备参数差异和任务说明，核对本文真实字段表 | 维护者交付对应 adapter、任务/宿主配置及接受的摘要；未支持项明确列出 |
| NPU 执行 | 完整任务包、独占输出、已准备好的输入 | 使用该任务交付的 validate/start 命令 | 真实 lease、绑定、心跳、终态与 release；CPU 准备不占卡 |
| 评分与分析 | 已释放设备的推理输出、冻结 scorer 和统计协议 | 在 CPU 上并行评分、汇总对比与 bad case | 样本/分母可追溯、不同计算口径分列、失败和反例保留 |
| 结果协作 | 独立复核后的表格、机器可读结果、证据位置 | 原位更新 Wiki 对应结果格及状态 | 最新结论可独立阅读；过程文件留 Ceph/本地，三天周期归档 |

接入时仍需维护者完成的事项：个人访问权限；新实验尚未支持的 adapter/recipe；任务专属的启动与评分入口。固定镜像已在 175，本报告不要求同事重新构建镜像；当前没有可公布的 registry pull 地址。27B 保留在技术方案内，其 2/4 卡资源组及训练/评测资格须使用专门集成，不能套用单卡 H2 设置。

本次公开验证摘要见 [EXPERIMENT-STARTUP-VERIFICATION.json](EXPERIMENT-STARTUP-VERIFICATION.json)。2026-11-07 12:19 UTC 再次确认镜像 ID 一致、H2 validate 返回 VALID、两次既有 CPU smoke 终态均 exit 0；这次复查没有重新启动 smoke 或 NPU 实验。

## 资源与入口

| 资源 | 位置和范围 |
| --- | --- |
| 代码 | `git clone git@github.com:chaosxingxc-orion/nga.git`；需已有 GitHub SSH 访问及本地网络配置。 |
| 计算主机 | `ssh npu` 使用本地 SSH 配置中的别名，指向 175 主机 `100.100.135.175`；别名不是仓库自带配置。使用已有认证，不输出凭据。 |
| 设备 | 175 的记录为 8 张 Ascend 910B3、每张 64 GiB；这不是实时占用状态。实际使用依控制器的 lease、设备映射和释放回执。 |
| Base 模型 | `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-{0.8B,2B,4B,9B}-Base`，分别为 `Qwen__Qwen3.5-0.8B-Base`、`Qwen__Qwen3.5-2B-Base`、`Qwen__Qwen3.5-4B-Base`、`Qwen__Qwen3.5-9B-Base`；同名目录也在 `/mnt/cephfs/xingchao/omni/models/jev/`，选择前核对接受的身份和清单。 |
| 27B | `/mnt/cephfs/models/Qwen3.8-27B` 的目录和 config 存在已于 2026-11-07 04:22 UTC 核实，仅是元数据检查。另一个 runtime 8190 镜像是历史四卡 fixture，不可与 RC1 镜像互换；有限 forward/更新也不代表完整训练资格。 |
| 数据 | 原始数据 `/mnt/cephfs/xingchao/omni/datasets/jev/`；已构建任务数据在 `/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/` 和 `transfer-v4/`。采用预注册指定的文件、顺序和清单。 |
| 宿主 Python | Python 3.12：`/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/half-lr-controller-2976573/venv/bin/python`。宿主默认 Python 3.10 并不适用于所有控制器。 |
| RC1 镜像 | `sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d`；175 上无 tag，`RepoDigests` 为空，没有可提供的 pull URL。镜像之外还需要对应任务的控制器、overlay、配置和 receipt。 |

记录实际模型和数据身份、split、清单摘要、镜像、源码 overlay、配置、设备映射、输出与回执。复用已接受的资源凭据，不在每次调度时重复全量重算大型 payload；身份或保护链变化时按相应准入流程重新验证。不要记录代理凭据、token 或完整环境变量。下载内容视为不可信，脚本放在其目录之外，通过路径参数读取。

## 第一天：先取得可交付结果

1. 克隆仓库并读目标实验的 `experiments/` 协议和 [Wiki](https://github.com/chaosxingxc-orion/nga/wiki) 当前页面，确认问题、缺陷登记表行、分割和接受范围。
2. 立即从已发表的 [accepted TEST comparison JSON](https://raw.githubusercontent.com/wiki/chaosxingxc-orion/nga/RC1-Full-Family-Same-TEST-comparison.json)、[numerical analysis JSON](https://raw.githubusercontent.com/wiki/chaosxingxc-orion/nga/RC1-Full-Family-Same-TEST-analysis.json) 与 [完整数值附录](https://github.com/chaosxingxc-orion/nga/wiki/RC1-Full-Family-Same-TEST-Appendix) 复核一项注册比较，记录 population、配对结果、反例和限制。现有 TEST 结论不能用于选择新方案。
3. 在 175 执行下面的 CPU smoke 与只读 validate，留存各自输出位置和结果；二者不占用 NPU，也不启动训练。
4. 分工准备数据映射、配置与 receipt 集成、分析和独立复核。为具体任务固定身份和独占输出，再由 NPU 操作员使用该任务支持的控制器。

## CPU Docker smoke：在 175 上执行

先 `ssh npu`，再复制以下整段。它创建带 UTC 时间和 shell PID 的独有目录及容器名，挂载只读配置，保留退出容器；`run.log` 和带容器退出码的 `terminal.json` 写到 Ceph。此命令是短时间 CPU 检查，不是 NPU 启动模板。

```bash
set -eu
NAME="nga-onboarding-cpu-$(date -u +%Y%m%dT%H%M%SZ)-$$"
DIR="/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/onboarding/$NAME"
IMAGE=sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d
mkdir -p "$DIR"
cat > "$DIR/config.json" <<'JSON'
{"schema":"nga-unified-config-v1","adapter":"environment-check-v1","runtime":"cpu"}
JSON
docker run -d --runtime=runc --network=none --cpus=1 --memory=1g \
  --name "$NAME" \
  --mount "type=bind,src=$DIR/config.json,dst=/run/nga/config.json,readonly" \
  "$IMAGE" /run/nga/config.json
EXIT_CODE=$(docker wait "$NAME")
docker logs "$NAME" > "$DIR/run.log" 2>&1
python3 -c 'import json,sys; json.dump({"container":sys.argv[1],"exit_code":int(sys.argv[2])},open(sys.argv[3],"w")); print()' "$NAME" "$EXIT_CODE" "$DIR/terminal.json"
printf 'container=%s exit=%s evidence=%s\n' "$NAME" "$EXIT_CODE" "$DIR"
```

历史单次观察 `20261107T041908Z`：exit 0、无设备、`tbe_available=true`。这只说明当次 CPU 默认入口可启动，不证明 NPU 挂载、训练或恢复；也不能替代运行期间约 600 秒的监控。日常协调查看 digest 而不是打印原始日志，异常时才按指针读取有限片段。

## H2：配置、只读检查与受支持的启动

在 175 上运行以下只读检查；它不启动任务。2026-11-07 的首次验证及本次补充核验均为 `VALID`，当时文件摘要为 `f8a31c065fc7e1a8017b87c8172b4899c1d96531fc4b27c288aa2a2cb925e6d8`。如现在摘要不同，应调查身份变化，不要以重算摘要绕过固定身份或准入门禁。

```bash
STAGE=/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/h2-reviewed-training-fixes-3065900
PY=/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/half-lr-controller-2976573/venv/bin/python
CFG=$STAGE/host-s2.json
SHA=f8a31c065fc7e1a8017b87c8172b4899c1d96531fc4b27c288aa2a2cb925e6d8
"$PY" -P "$STAGE/host/h2_host.py" validate --config "$CFG" --sha256 "$SHA"
```

以下是实际 H2 seed 2 **任务 JSON**，路径为容器内路径，展示字段与固定身份，不是可以直接复制启动新任务的模板：

```json
{
  "schema": "nga-unified-config-v1",
  "adapter": "k2-family-h2-v2",
  "recipe_id": "k2-base-4b-3116-v2",
  "owner": "rc1-h2-4b-k2-s2",
  "seed": 2,
  "model": {
    "id": "Qwen3.5-4B-Base", "path": "/model/base",
    "manifest": "/opt/nga/components/training/family-assets-v2/model-4B.json",
    "manifest_sha256": "9edaa5cde3375a0882ef28d7247d96d7778294628cae67e4df33aa653a248290"
  },
  "dataset": {
    "id": "decision-v7-train", "path": "/data/train.jsonl",
    "manifest": "/opt/nga/components/training/family-assets-v2/dataset.json",
    "manifest_sha256": "2d71ef2dee50883d6e42c4b3a2e8217c8c0e69aea41d447071fe945881431831"
  },
  "resume": null,
  "engineering_stop_after": 3116,
  "output": "/run/nga/output/result",
  "learning_rate": 0.0001
}
```

宿主 JSON 另行描述设备、lease、挂载、宿主输出及绑定；任务 JSON 不负责这些。固定训练实现与 recipe 对应的方案为 batch 10、micro_tokens 12000、max length 4096、LoRA r16 / alpha 32 / dropout 0.05；schema 不接受随意增加字段。H2 需要受审 overlay：`adapter.py`、`schema.json`、`components/training/family_h2.py`、`family-registry-h2.json`、`family-schema-h2.json`，以及已准备的 receipt。裸镜像不支持此 H2 组合。`prepare_receipt.py` 固定 seed 2/3、owner `rc1-h2-4b-k2-sN`、4B 和学习率 1e-4，会拒绝任意 owner、seed、模型和学习率；H2 host 还固定 overlay 和 config pins。任意新实验需要负责人准备受支持的 adapter、配置和 receipt 集成，目前没有通用生成器。

对于已经完整准备的**独立且受控制器支持**的新任务，启动接口如下；`NEW_HOST_CONFIG` 必须是该任务的宿主配置，不能指向上面现役 seed 2 配置重放。这些启动命令在本指南中没有重新执行：

```bash
# NEW_HOST_CONFIG 和 NEW_SHA 由该任务的已接受交付包提供。
: "${NEW_HOST_CONFIG:?缺少该任务的宿主配置路径}"
: "${NEW_SHA:?缺少已接受的配置 SHA256}"
ACTUAL_SHA=$(sha256sum "$NEW_HOST_CONFIG" | cut -d' ' -f1)
test "$ACTUAL_SHA" = "$NEW_SHA" || { echo '配置与已接受摘要不一致' >&2; exit 1; }
"$PY" -P "$STAGE/host/h2_host.py" validate --config "$NEW_HOST_CONFIG" --sha256 "$NEW_SHA"
"$PY" -P "$STAGE/host/h2_host.py" start --config "$NEW_HOST_CONFIG" --sha256 "$NEW_SHA"
```

`supervise` 是由 `start` 调用的内部后台入口；启动后不要再手动执行第二个 supervise。中断恢复先查看该次 `RELAUNCH.json` 并确认旧监督进程已退出。

`start` 通过 `Popen(start_new_session=True)` 后台启动 supervise 并保留 Docker 容器。长任务必须脱离 SSH、无 `--rm`、日志和终态落 Ceph、可按项恢复并保存准确重启命令；控制器也可使用 Docker create/start，不必假设所有控制器都用 `docker run -d`。Ascend 容器内 Python 用 `-P`，不要用会丢弃 CANN/TBE `PYTHONPATH` 的 `-I`。

## 如何开展实验设置

设置分三层：预注册定义比较什么；任务配置定义模型计算；宿主配置定义在哪里运行。
镜像摘要、任务配置、源码 overlay 与回执共同确定实际执行内容。只有镜像相同，不能
推断两次实验采用了相同实现。

| 设置 | 当前 H2 的真实字段或来源 | 新实验应如何处理 |
| --- | --- | --- |
| 任务与指标 | `experiments/RC1-CANDIDATE-LOSS-DEV.md`；宿主 `prereg` 引用 | 写明对照、split、指标、统计口径和预期反例，启动前固定 |
| 模型与数据 | 任务 `model`、`dataset` 的 ID/path/manifest/hash | 复用已接受的清单；更换输入时只补受影响的准备和校验 |
| 目标与训练方案 | `adapter=k2-family-h2-v2`、`recipe_id=k2-base-4b-3116-v2` | 当前是 K2 专用路径；不同目标需要受支持的 adapter |
| 随机性与步数 | `seed=2/3`、`engineering_stop_after=3116`、`resume` | 预注册种子、停止规则和恢复身份；不能更改现役配置 |
| 学习率 | `learning_rate=0.0001` | 当前 host 明确固定该值；改值需要该路径支持的新实验包 |
| batch、长度、LoRA | 固定训练实现及其 recipe/保留 plan；batch 10、micro_tokens 12000、maxlen 4096、LoRA 16/32/0.05 | 这些不是当前任务 JSON 的自由字段，直接添加字段不会启用新参数 |
| 镜像和源码 | 宿主 `image`、`entrypoint`、`mounts`、配置摘要 | 使用固定镜像及该实验接受的 overlay，不覆盖正在运行的源码 |
| 设备 | `lease.device_count=1`、`eligible_device_ids=[2,3]` | 当前每个 seed 单卡；新资源组由对应控制器配置，27B 不能只将这里改成 4 |
| 输出与恢复 | `name`、`output`、`lease_id`、`RELAUNCH.json` | 使用任务自己的独占命名和输出；已存在运行先核对回执，避免重复启动 |

H2 路径映射如下，帮助参与者定位输入和产物：

| 175 宿主路径 | 容器内路径 |
| --- | --- |
| `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-4B-Base` | `/model/base` |
| `/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl` | `/data/train.jsonl` |
| `$STAGE/inputs/s2/container-receipt.json` | `/run/nga/h2-prepared.json` |
| `$STAGE/overlay/configs/q4b-k2-s2.json` | `/run/nga/config.json` |
| `$STAGE/q4b-s2` | `/run/nga/output`，训练结果位于其 `result/` |
| `$STAGE/overlay/` 中的受审源码文件 | 对应 `/opt/nga/` 文件，按宿主 `mounts` 逐项绑定 |

接手一个新实验时，负责人需要交付以下完整任务包；这是一份交接清单，不是执行器 schema：

```text
任务 ID / 负责人 / 对照与实验目的
预注册文件及固定摘要；模型、数据、split 和参考统计口径
固定镜像 ID；受支持 adapter/recipe；源码与资源清单
任务 JSON + 宿主 JSON + 各自摘要 + 该任务的准备/准入回执
CPU 准备 → NPU 训练/推理 → 释放 → CPU 评分的节点与真实依赖
准确的 validate/start 命令；独占输出目录；摘要与 RELAUNCH 路径
评分入口及冻结参数；结果文件和独立复核方法；Wiki 结论页
```

同事可以先独立提交预注册和配置差异，由路径维护者补齐尚未支持的配置能力。当前还
不能承诺任意新实验全程自助。已支持路径应复用脚本和资源；新增需求只补必要功能，
不借接入工作更换 RC1 版本或重复已有验收。CPU 准备完成后才进入 NPU ready 队列，
评分和文档不作为无关 NPU 任务的前置条件。

## 生命周期与监控

下表以 H2 seed 2 为例，路径均相对于上述 `$STAGE`；配置中的 `output` 为 `$STAGE/q4b-s2`。

| 路径 | 作用 |
| --- | --- |
| `q4b-s2.host-v1/RELAUNCH.json` | 固定重启信息。 |
| `q4b-s2.host-v1/heartbeat.json` | 宿主容器状态心跳；训练 step、每卡吞吐和 reserved 显存读取下列 result 心跳。 |
| `q4b-s2.host-v1/container-log-*.log` | 容器输出；由 digest 指向需要诊断的片段。 |
| `q4b-s2.host-v1/terminal.json` | 完成后才出现的终态和退出码；终态标记是完成依据。 |
| `q4b-s2/result/heartbeat.json`, `progress.log`, `losses.jsonl`, `manifest.json`, `attempts/` | 训练进度、损失、身份和各次尝试；保留 checkpoint，供后续 CPU 交接。 |
| `journal/h2-k2-s2/{claim,binding,release}.json` | 设备声明、绑定与释放回执；检查 release 后交接资源。 |

宿主控制器内部约 30 秒轮询与 agent/watchdog 约 600 秒兜底监控是不同层次。当前 H2 的 `training-progress-v1` 心跳应读取已部署的专用摘要：

```bash
ssh npu 'cat /mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/_watchdog-h2/bounded-digest.md'
```

同目录包含 `bounded-digest.json` 和 `bounded_monitor.py`；无需重复启动监控。通用
`tools/watchdog.py` 尚未正确适配这一 H2 心跳，不能用它的 `unknown` 推断训练停止。脚本先生成带异常指针的 digest；协调者常规只看 digest，诊断者按指针读取有限日志。心跳中的训练 **step** 数不等于任务完成数；明确标注单位。比率恰为 0 或 1、各格指标完全相同及样本量不足都需排查。效率变更只能改变速度，loss/梯度须在测得的 bf16 噪声范围内，否则先修订预注册。

## 完成一个实验

1. 预先固定问题、假设、缺陷登记行、数据和顺序、等价类、基线、seed、分割、指标、阈值和排除规则。不变性目标必须配区分能力测试；先写不受约束的最优策略及可能的退化解。用户的研究判断作为可证伪假设。决策一致性使用决策级配对协议，而不是汇总准确率。
2. 训练结束时核对目标 checkpoint、manifest、终态和资源 release。exit 0 只是执行终态，不等于科学成功；中断时使用身份匹配的 checkpoint 和控制器恢复流程。
3. 对固定 DEV panels 生成并保存向量；CPU 计分使用有界 worker，不占 NPU。已配置 pipeline 可在设备释放后异步衔接计分、分析和报告。校准数据按协议使用，DEV 用于方案选择。
4. TEST 只按固定预注册运行，不能据 TEST 调参；复核 population、顺序、控制组、配对统计、失败和负面结果。`K-REPORT.json`、`INFER-EXIT.json`、`CPU/OPERATOR-FIT.json`、`INFERENCE-READY.json` 和 `HOST-RELEASE-VERIFIED.json` 是已有 TEST 流程的产物，并非每个 H2 训练都会生成。
5. 目前没有面向任意任务的自助 scorer 或任务生成入口；使用已经配置并验收的 pipeline，或由负责人完成对应集成。不要臆造计分命令。`tools/functional_test/rc1_ready/README.md` 的源码保存和 CPU fixture 本身不构成 NPU 部署或科学验收。

## 分工与交接

| 角色 | 可立即开展的工作及交付物 |
| --- | --- |
| 数据与参考映射 | 数据来源、split、问题/参考答案身份和顺序映射表，清单及摘要，缺失与歧义清单。 |
| 已保存结果分析 | 基于已发布 JSON 的统计复核、决策级配对表、bad case 与反例、复现所需输入和方法。 |
| 配置集成 | 任务/宿主 JSON、adapter 与 schema、receipt 和固定路径对应表，验证结果及待支持项。 |
| NPU 操作员 | 独占 run/容器/输出、设备 lease 与映射、重启信息、心跳、checkpoint、终态和 release 回执。 |
| 审查与 Wiki | 对照预注册和产物的独立复核、结论与限制、GitHub Wiki 原位更新和证据链接。 |

交付完成前检查：协议及 defect 行已链接；输入身份与分割固定；配置、receipt、输出和重启路径可追溯；checkpoint、终态及 release 已核对；DEV/TEST 用途未混淆；配对统计、失败和限制经过独立复核；Wiki 页面指向最新结论及证据。未完成项注明负责人和下一步，避免将“配置已准备”“运行结束”和“科学结论已接受”混为一谈。

## 验证记录与当前协作边界

验证日期：2026-11-07 UTC（主机会存在时钟差，以下标识按记录保留）。本次没有重新启动完整训练或 TEST，也没有申请 NPU。实际完成：

| 检查 | 结果与证据 |
| --- | --- |
| 精确镜像身份及默认入口 | image ID 与文中一致；入口 `/opt/nga/entrypoint.sh`；无仓库 tag/pull digest |
| 默认入口 CPU smoke | exit 0；TBE 可找到；无 NPU devices；保留容器 `nga-onboarding-cpu-20261107T041908Z` |
| 本文命令逐字复跑 | smoke 容器 `nga-onboarding-cpu-20261107T042503Z-519357` exit 0；H2 validate 再次返回 VALID |
| 模型及数据位置 | 四种 Base 在两处镜像目录、27B 目录及 config、8个列明的数据文件元数据已核对；未重算权重 payload |
| 公开结果读取 | 对发布 comparison JSON 的8个模型/任务格 × 2口径 × 2seed，32项准确率差值算术检查通过；不等于重新评分 |

前两个 smoke 的证据分别保存在 `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/onboarding/<上述容器名>/`，含配置、日志与 terminal；首个还含完整命令。接入自检属于短任务，不替代长任务的脚本监控和可恢复性验证。汇总核验文件在维护者工作区 `.local/releases/engineering-base-rc1/evidence/onboarding/VERIFICATION.json`，不随仓库克隆；同事优先查175上的证据和本表。

当前标准数据文件：decision-v7 的 `train.jsonl`（15,576题）、`dev.jsonl`（1,264题）、`test.jsonl`（1,200题）、`calibration.jsonl`（1,148题）及各 split variants；transfer-v4 的 DEV/TEST 各656题。题目数不是候选前向次数。具体九组面板、控制条件和各口径依[DEV协议](https://github.com/chaosxingxc-orion/nga/blob/main/experiments/RC1-FUNCTIONAL-DEV.md)、[TEST协议](https://github.com/chaosxingxc-orion/nga/blob/main/experiments/RC1-FUNCTIONAL-TEST.md)和[H2协议](https://github.com/chaosxingxc-orion/nga/blob/main/experiments/RC1-CANDIDATE-LOSS-DEV.md)执行。参考工作的 native、T1、候选续文及其他统计方法分列，不能合并为相同指标口径。

同事现在可以独立完成环境自检、已发布结果复核、数据和评测协议设计；使用既有路径运行实验由熟悉该路径的同事对接。新增任意模型/数据/seed的完全自助配置和评分入口仍是工程缺口，不能承诺克隆后即运行。此报告不新增发布门禁、不要求重做已接受的资源检查，也不暂停正在运行的实验；后续只补实际接入所需的功能。

[最新研究状态与计划](https://github.com/chaosxingxc-orion/nga/wiki/Research-Status-and-Plan) · [当前结论](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions) · [十二成员同TEST结果](https://github.com/chaosxingxc-orion/nga/wiki/RC1-Full-Family-Same-TEST) · [固定候选状态](https://github.com/chaosxingxc-orion/nga/blob/main/configs/experiments/engineering-release-candidate.json)
