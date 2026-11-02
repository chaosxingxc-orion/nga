# BEV 配置工作流：固定脚本、版本化模板、新实例配置

本工作流将同一种已冻结 BEV DEV 实验的建包、校验、准入绑定、NPU 启动、CPU 异步评分和状态读取纳入固定脚本。普通同契约实验填写配置，不复制修改准备/启动程序。首版复用同模型、同任务人口与统计协议；模型或协议变化需要新的受审查模板版本，不能借复制旧模板自动获得批准。

运行位置为当前分析主机（可访问共享 CephFS，具有固定 `ssh npu` 别名）。NPU 仍由 host175 上已冻结的 `bev_host.py` 管理资源和保留容器；CPU consumer 在分析主机 detached 运行、600 秒等终态。脚本不修改已经运行的冻结包。

## 1. 配置准备

固定入口为 `tools/experiment_workflow.py`。配置只接受下列字段，引用精确 SHA256；没有任意 shell、环境变量或“跳过审查”字段：

```json
{
  "schema": "nga-bev-workflow-prepare-v1",
  "template_plan": {"path": "/absolute/reviewed/inference/plan.json", "sha256": "EXACT_SHA256"},
  "template_cpu": {"path": "/absolute/reviewed/cpu/config.json", "sha256": "EXACT_SHA256"},
  "root": "/mnt/cephfs/xingchao/experiments/jev/r3_runs/NEW_RUN",
  "run": "r3_runs/NEW_RUN",
  "container": "nga-NEW_RUN",
  "chip": 6
}
```

`root` 必须不存在，`run` 与其目录名一致，容器与 run 不能复用模板身份。真实样例（只准备，未批准启动）在 [bev-workflow-prepare-example.json](bev-workflow-prepare-example.json)。不能为了填满算力启动无意义重复；样例主要说明配置格式。

```bash
python3 -B -P tools/experiment_workflow.py prepare --config /absolute/prepare.json --sha256 EXACT_PREPARE_SHA256
```

准备器验证模板所有代码/输入/模型和 CPU 依赖；复制到新 `inference/`、`cpu/`、`control/`，保留请求、gold、模型、精度与指标，生成新计划及 CPU 配置。随后调用真实 runner 校验和 CPU 人口检查。`PREPARED.json` 明确 `approved: false`。失败保留 `PREPARE_FAILED.json`，绝不覆盖半成品重试。

## 2. 新实例审查与绑定

独立审查应读取新的精确 plan、CPU config 和 consumer；报告须授权具体 attempt，并记录 `approved_plan_sha256`、所有代码/模型/输入 `hashes`、`deployment_suitable: true`、`cpu_config_sha256`、`consumer_sha256`。已有模板的审查不能直接复用。此步骤是工程准入，不授予 TEST 或科学资格。

```bash
python3 -B -P tools/experiment_workflow.py bind --config /absolute/NEW_RUN/PREPARED.json --sha256 EXACT_PREPARED_SHA256 --review /absolute/new-review.json --review-sha256 EXACT_REVIEW_SHA256 --attempt 1
```

输出 `control/attempt-1/activation.json` 和其指纹。它同时固定工具版本、prepared 记录、NPU entry 配置和 CPU 配置；后续统一使用该文件。

绑定先在本次调用独有的临时目录中完整校验审查。错误审查被拒绝后，可修正审查并绑定同一个 attempt；不会留下占用该 attempt 的最终目录。已经成功绑定的目录仍拒绝重复写入，脚本不删除或覆盖旧绑定。最终目录创建后的磁盘写入故障可能留下半成品，此类情况仍需核对后处理。

## 3. 校验与启动

```bash
python3 -B -P tools/experiment_workflow.py validate --config /absolute/activation.json --sha256 EXACT_ACTIVATION_SHA256
python3 -B -P tools/experiment_workflow.py dry-run --config /absolute/activation.json --sha256 EXACT_ACTIVATION_SHA256
python3 -B -P tools/experiment_workflow.py start --config /absolute/activation.json --sha256 EXACT_ACTIVATION_SHA256
python3 -B -P tools/experiment_workflow.py status --config /absolute/activation.json --sha256 EXACT_ACTIVATION_SHA256
```

`start` 经固定 SSH 别名调用原 guarded host 启动器；它返回后立即独立启动 CPU consumer，而不等待 NPU 完成或报告分析。CPU 复用原终态、容器、资源释放、身份和逐问题评分验证，最终生成 `report.json` 与 `EXIT.json`。启动命令、服务 PID、日志、relaunch 留在实例目录。脚本输出 `npu_start_returned` 只表示启动调用返回，不能充当实际运行、满载或实验完成证明。

如果 NPU 已启动而 CPU 接续失败，使用同一 activation 的 `start-cpu` 修复缺少的接续；不再调用 `start` 重启 NPU。CPU 已存在且精确进程仍在时返回 `already_running`；已有成功终态核验报告哈希后返回 `already_complete`。进程不确定、失败终态或只存在启动意图时拒绝自动重试，先完成 reconciliation。新的推理 attempt 必须有新的具体准入，并通过原 host 的前驱释放检查；同一人口保留逐 item 恢复能力。

## 4. 锁定范围与剩余工作

已支持一个真实 BEV DEV 模板的配置建包、审查绑定、推理启动、CPU 自动等待评分及结构化状态查询。没有读取原始日志、自动发布 GitHub、训练 adapter 或新增业务数据构造。消费者的完整报告仍须结果接受，不能把生成文件直接等同科学结论。

模板位于持久化 CephFS，按精确指纹引用；不依赖 `.local` 临时准备代码。代码与配置均须固定仓库版本，修改脚本后旧 activation 因版本变化被拒绝，应从原固定版本操作，不能原地升级运行包。

功能测试覆盖真实子进程参数传递、模板改变、重复目录、旧审查拒绝、CPU 错绑定、重复 NPU 启动拒绝、异步 CPU fixture 与不确定重启。另在真实 2B 模板上完成新目录建包、完整 6,516 人口及真实 runner/consumer 校验；未为验证而启动新 NPU 或生产 CPU 服务。
