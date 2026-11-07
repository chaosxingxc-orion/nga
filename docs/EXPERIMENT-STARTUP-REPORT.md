# NGA 实验启动报告（engineering-base-rc1）

验证时间：2026-11-07 UTC。本文是同事参与实验的操作入口，使用固定的
`engineering-base-rc1` 工程基座。验证范围包括资源路径、固定镜像的 CPU 默认入口、H2
宿主配置校验和当前 NPU 运行快照；它不把 CPU smoke、配置完成或容器 `exit 0` 当作
NPU 数值或科学结论。

## 当前可用状态

RC1 仍处于 `stabilizing`，`released=false`。固定镜像摘要为：

```text
sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d
```

已验证的协作范围是：复核已发布结果、准备数据和配置、运行 CPU 自检、使用已经集成
并经过准入的实验路径、在设备释放后进行 CPU 评分和结果分析。镜像本身不是任意任务
的一键运行器；每个 NPU 任务仍必须绑定自己的模型、数据、源码 overlay、配置、设备
lease、输出目录和回执。

当前 H2 正式训练没有停止：

| 物理卡 | 容器 | 设置 | 2026-11-07 07:52 UTC 快照 |
| --- | --- | --- | --- |
| 2 | `nga-h2-4b-k2-s2` | Qwen3.5-4B，seed 2，K2，global batch 10，micro tokens 12000，max length 4096，LR `1e-4`，LoRA `r16/alpha32/dropout0.05`，3116 updates | `342/3116`，约 `31.1 GiB` reserved，单卡运行 |
| 3 | `nga-h2-4b-k2-s3` | 同上，seed 3 | `314/3116`，约 `31.3 GiB` reserved，单卡运行 |

这两个任务不得重启、迁移或修改配置。其它物理卡是否可用，只能由实时 lease、Docker
冲突和控制器锁内检查确认；历史快照不能证明空闲。

## 资源位置

| 类型 | 固定位置 | 使用规则 |
| --- | --- | --- |
| 仓库 | `/home/xingchao/workspace/nga`；远端 `git@github.com:chaosxingxc-orion/nga.git` | 先读取目标 `experiments/` 预注册协议和当前 Wiki；不要凭报告临时改指标或 split |
| 计算主机 | SSH 别名 `npu`，即 175 主机（`100.100.135.175`） | 设备使用由 lease/claim/release 回执决定；不要把静态 8 卡信息当作实时库存 |
| Qwen3.5 Base | `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-{0.8B,2B,4B,9B}-Base` | 同名镜像也位于 `/mnt/cephfs/xingchao/omni/models/jev/`；以接受的 manifest 和身份为准 |
| Qwen3.8-27B | `/mnt/cephfs/models/Qwen3.8-27B` | 已核对目录和 config 元数据；需要 2 或 4 卡的独立资源组。该检查不等于完整训练或公共 TEST 资格 |
| 27B Jev 候选 | `/mnt/cephfs/xingchao/models/jev/SimpleJev__JevAny-Qwen3.8-27B-LoRA`、`ZefanCai__Open-Jev-27B-v1.1`；对应镜像位于 `/mnt/cephfs/xingchao/omni/models/jev/` | 先确认任务协议指定的候选和来源，不要自行替换模型 |
| 训练数据 | `/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/` | `train.jsonl`、`dev.jsonl`、`test.jsonl`、`calibration.jsonl` 以及协议指定的 variants |
| 迁移数据 | `/mnt/cephfs/xingchao/experiments/jev/KEV/transfer-v4/` | 只使用预注册的 DEV/TEST 文件和顺序 |
| RC1 集成目录 | `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/` | 控制器、overlay、日志、心跳、终态、checkpoint 和 release 回执均落在 CephFS |
| H2 当前 stage | `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/h2-reviewed-training-fixes-3065900/` | 175 上的受保护 stage；`host-s2.json`、`host-s3.json` 及 `host/h2_host.py` 是已绑定的 H2 入口 |
| 宿主 Python | `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/half-lr-controller-2976573/venv/bin/python` | 使用 `python -P`；Ascend 容器内不要用 `python -I`，以免丢失 CANN/TBE 的 `PYTHONPATH` |

## 启动前检查

先在 175 上执行以下命令。它只验证配置，不领卡、不启动容器。命令必须在 175 上执行，
因为该 stage 受 CephFS 权限保护，本地工作区不能替代远端验证：

```bash
set -eu
STAGE=/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/h2-reviewed-training-fixes-3065900
PY=/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/half-lr-controller-2976573/venv/bin/python
CFG="$STAGE/host-s2.json"       # 新任务必须换成该任务自己的宿主配置
SHA=$(sha256sum "$CFG" | cut -d' ' -f1)
"$PY" -P "$STAGE/host/h2_host.py" validate --config "$CFG" --sha256 "$SHA"
```

验证成功的唯一形式是：

```text
{"status": "VALID"}
```

`host-s2.json` 只是现役 H2 配置示例，不能复制它来伪造新任务。新任务必须先完成
预注册、源码和资源身份绑定，再由负责人生成独立宿主配置和 receipt。若配置摘要、
owner、模型、数据、overlay 或输出路径发生变化，应停止并重新走该任务的准入流程。

## 镜像启动方式

### CPU 默认入口 smoke

下面的命令在 175 上创建一个保留退出容器，用来确认镜像入口和 CANN 环境可加载。它
不挂 NPU，不运行模型，也不是训练启动模板：

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
python3 -c 'import json,sys; json.dump({"container":sys.argv[1],"exit_code":int(sys.argv[2])},open(sys.argv[3],"w"))' \
  "$NAME" "$EXIT_CODE" "$DIR/terminal.json"
printf 'container=%s exit=%s evidence=%s\n' "$NAME" "$EXIT_CODE" "$DIR"
```

已验证的 smoke 容器为 `nga-onboarding-cpu-20261107T041908Z`，exit code 为 0，未挂
设备且 `tbe_available=true`。证据在：

```text
/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/onboarding/nga-onboarding-cpu-20261107T041908Z/
```

### 受支持的 NPU 任务

NPU 任务使用宿主控制器，而不是让参与者手写裸 `docker run`。配置验证通过、实时
lease/容器冲突检查通过且该任务的准入回执齐全后，使用：

```bash
"$PY" -P "$STAGE/host/h2_host.py" start --config "$NEW_HOST_CONFIG" --sha256 "$NEW_SHA"
```

其中 `NEW_HOST_CONFIG` 和 `NEW_SHA` 必须属于当前任务；启动前先执行：

```bash
NEW_SHA=$(sha256sum "$NEW_HOST_CONFIG" | cut -d' ' -f1)
"$PY" -P "$STAGE/host/h2_host.py" validate --config "$NEW_HOST_CONFIG" --sha256 "$NEW_SHA"
```

`start` 会以 detached、可恢复的方式启动监督进程并保留容器。不要再手动启动第二个
`supervise`，不要使用 `--rm`，不要在 SSH 会话中持续挂着前台进程。每次长任务必须
写入 CephFS 日志、heartbeat、`terminal.json`、`RELAUNCH.json` 和 release 回执。

## 监控与异常处理

2026-11-07 更正：当前 H2 使用 `training-progress-v1` 心跳，通用 watchdog 尚不能正确
识别该路径，可能显示 `unknown`。H2 已部署专用脚本，每 600 秒读取心跳、终态、容器
状态及有界日志片段；参与者直接查看现有摘要，不必再启动一份监控：

```bash
ssh npu 'cat /mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/_watchdog-h2/bounded-digest.md'
```

机器可读结果位于同目录的 `bounded-digest.json`，脚本为 `bounded_monitor.py`。
部署证据为维护者工作区中的
`.local/releases/engineering-base-rc1/tasks/execution/h2-script-watchdog-20261107/DEPLOYMENT.json`。
摘要时间戳过旧时先检查监控服务，不能据此重启训练。

以下通用入口仅适用于其已支持的任务格式，不替代上述 H2 专用监控：

日常监控由脚本完成，主协调者只读取脚本生成的 digest，不读取原始长日志。默认轮巡
间隔约 600 秒：

```bash
python3 -P tools/watchdog.py \
  --root /mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1 \
  --out-dir /mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/_watchdog \
  --chip-allocation /mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json \
  --watch --interval 600 --npu-host npu
```

查看 `.../_watchdog/digest.md` 和 `digest.json`。digest 只给出每个任务的状态行、进度、
吞吐、异常标志和原始日志指针。出现错误、心跳停滞、样本量不足或恰好为 0/1 的指标时，
才按指针读取有限日志片段。终态 marker 和 release 回执优先于 Docker 的容器状态；没有
终态 marker 不能宣布任务完成。

## 完成一次实验的固定环节

1. **预注册**：固定研究问题、假设、缺陷登记行、模型和数据身份、split、候选顺序、
   seed、指标、阈值、等价类和排除规则；DEV 用于方案选择，TEST 不得调参。
2. **CPU 准备**：生成任务配置、源码/数据 manifest、receipt 和独占输出目录；做 schema
   和路径校验，不提前占用 NPU。
3. **准入与启动**：在锁内核对实时 lease、Docker 冲突、镜像摘要、overlay、配置摘要
   和前驱 release；确认后由控制器 detached 启动。
4. **NPU 执行**：训练或推理按项可恢复；heartbeat 至少包含时间戳、进度、每卡吞吐、
   卡数和 reserved memory。NPU 任务持续排队，CPU 分析异步开展。
5. **终态交接**：检查 checkpoint、manifest、`terminal.json`、exit code、容器身份和
   release 回执。exit 0 只表示进程结束，不表示模型收益成立。
6. **CPU 评分与分析**：设备释放后，用固定 scorer 和有界 worker 生成向量、指标、配对
   统计和 bad case；分析不阻塞下一项 NPU 任务。
7. **独立审查**：核对 population、统计口径、失败项、反例和限制；数值型分析由脚本
   并行计算，审查者只消费受限摘要和证据指针。
8. **发布与归档**：只把最新结论、状态和证据链接更新到 GitHub Wiki；过程文件留在
   本地并按三天周期归档。

## 同事参与方式

| 角色 | 交付物 | 是否需要 NPU |
| --- | --- | --- |
| 数据/参考映射 | 数据来源、split、标签映射、顺序、manifest、缺失和歧义清单 | 否 |
| 结果分析 | 已发布 JSON 的复核、决策级配对表、bad case、反例和统计脚本输出 | 否 |
| 配置集成 | 任务 JSON、宿主 JSON、adapter/schema、源码和资源 receipt、准入检查结果 | 否，除非进入启动 |
| NPU 操作员 | 独占容器和输出、lease、设备映射、heartbeat、checkpoint、terminal、release | 是 |
| 评测与审查 | DEV/TEST scorer、CPU 数值包、独立复核、结论和限制 | 通常否 |

参与者提交时必须同时给出：任务 ID、目标、输入身份、配置摘要、输出路径、启动/重启
命令、结果文件、终态和限制。不要把 fixture、CPU transport 测试、配置完成或单次
forward 结果写成 NPU 科学结果。

## 已验证证据与验收边界

本报告对应的维护者验证记录为：

```text
.local/releases/engineering-base-rc1/evidence/onboarding/VERIFICATION.json
```

该记录确认：固定镜像 CPU smoke exit 0 且无设备、H2 宿主 `validate` 返回 `VALID`、
四个 Qwen3.5 Base、27B 元数据目录和预注册数据文件存在。当前 H2 运行快照来自：

```text
.local/releases/engineering-base-rc1/evidence/current-execution/ACTIVE-PROGRESS-LATEST.json
```

工程基座要达到正式 release 仍需完成 RC1 的 supervisor、capture、snapshot、实际
175 集成、四尺寸 NPU 数值/恢复和独立 release review。它们是基座发布门，不阻止已经
准入的实验路径继续执行；本报告也不替代任何实验的预注册协议或科学验收。
