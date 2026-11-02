# 配置化 R3 训练 → BEV 后继

`tools/bev_successor.py` 是有限的一次性交接器，运行于分析主机，共享 CephFS，并通过固定 `ssh npu` 调用已有受保护启动器。它不修改资源账本，不改变冻结运行包，也不创建新的实验批准。

配置 schema 为 `nga-bev-successor-v1`，固定 controller、entrypoint、workflow、R3 前驱 plan/supervisor/launch、BEV entry、CPU config/consumer 的路径与 SHA256；固定前驱 attempt、输出目录与 `poll_seconds: 600`。BEV entry 必须已有独立精确准入，CPU 配置必须被同一审查绑定。

```bash
python3 -B -P /absolute/frozen/code/bev_successor.py validate --config /absolute/config.json --sha256 EXACT_CONFIG_SHA
python3 -B -P /absolute/frozen/code/bev_successor.py start --config /absolute/config.json --sha256 EXACT_CONFIG_SHA
python3 -B -P /absolute/frozen/code/bev_successor.py status --config /absolute/config.json --sha256 EXACT_CONFIG_SHA
```

`start` 先验证配置与后继，随后 detached 运行 `watch`，在独立目录保存 SERVICE、RELAUNCH、service.log、digest 和 EXIT。每600秒检查一次前驱终态，没有高频模型调用。启动前仍需发布实验预注册并接受该交接器的精确代码/配置。

交接要求真实 R3 `TRAIN_EXIT.json` 与 attempt `EXIT.json` 一致且成功；release 精确绑定 run/chip/container；保留容器真实 exited/exit0 且映射对应设备；ledger free 指向该前驱 release 代次。之后仅调用一次固定 BEV entrypoint。原 BEV host 在资源锁内再次核验实际占用并 claim，交接器不自行写 ledger。CPU 通过已有 `cpu_start` detached 启动，并独立等待完整推理终态评分。

启动调用超时或意图存在但返回凭据缺失时停止并写失败终态，不自动重放 NPU。成功返回后等待实际 launch receipt，核验保留容器身份再交接 CPU。`handed_off` 仅表示后继和消费者已接续，不表示实验成功、满载、结果通过或科学接受。现有失败或不确定状态需要明确 reconciliation，不能直接重新运行。

下一版 SSH 等待时限区分操作：固定入口 `start` 为300秒，Docker 状态观察仍为60秒。大模型启动前的完整指纹校验可能超过60秒，且本地观察超时不会证明远端启动已停止。超过新时限时仍保留 `START_INTENT`、停止并要求 reconciliation，绝不自动重放。此变更仅用于新冻结控制器版本；已有等待器、失败终态和运行包不原地替换或重启。

CPU 准备包可能已有仅描述计划的 `RELAUNCH.json`，而固定 `cpu_start` 要独占生成实际启动记录。部署者须在确认尚无消费者/writer 后，把原准备元数据原样保留到另一路径并记录哈希，然后启动本控制器；不得修改代码、配置、gold或推理包。此操作不是由交接器自动完成。

首个准备配置位于 CephFS `r3_runs/bev_9b_successor_20261102_v1/config.json`，绑定 chip1 的完整 seed2 工程重复训练 → BEV 9B DEV attempt1。它准备完成但不因存在即取得部署资格。未创建无效重复 NPU 任务；模型/数据/协议由原独立审查约束。

测试：`python3 -B -P tools/test_bev_successor.py`。覆盖真实 R3 收据格式、缺终态等待、失败/存活容器/错释放代次拒绝、前驱哈希变化、启动不确定不重放、一次 NPU 调用与 CPU 接续。远程 Docker/启动与 CPU handoff 使用明确 fixture；另完成真实配置、所有依赖、BEV runner/consumer 和真实前驱等待状态校验。没有借测试启动生产 NPU 或 CPU 服务。
