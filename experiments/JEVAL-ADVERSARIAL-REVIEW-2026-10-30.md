# JEVal 实质审查发现与独立补充验收预注册

日期：2026-10-30。审查身份：实际 Codex 审查代理及工程复核，**不是 Astra 审查**。
指定 Astra 尚未提交实质意见。本文件记录已经复现的验收缺口，并预注册 E35
补充验收；不会追溯修改 E33 已冻结的模型实现、指标、分母或运行产物。

## 1. 已复现的问题

| 级别 | 证据 | 影响与处理 |
| --- | --- | --- |
| P1 | E33 driver 按 `max_tokens` 选择最长输入 probe；Open-Jev 原生 `jev/model.py` 将一题所有候选整批 padding 后 forward。实际已测 index 9027 为 30×4,096＝122,880 padded tokens；E31 有 243 个 eligible 样本超过此量，index 633／637 为 255×2,156＝549,780，约 4.47 倍。9B 已测边界 reserved memory 为 56.728516 GiB／1 chip。 | 最长单序列可执行不证明最高候选批量可执行。Open-Jev 正式 JEVal 推理需另补资源包络准入；必要的候选分块须先验证数值影响。E35 不宣称解决此资源问题。 |
| P2 | 冻结 verifier 的 `validate_probe` 接受四组全部替换成 `native_probabilities={"wrong-schema": 0.0}` 的假输出；缺少 answer、logits、token 与类别 schema 的独立验证。 | 新补充验收重建各原生响应，核对概率／logits／温度、返回值、候选键及 token；对四个 probe 请求独立执行 CPU 原生分词。 |
| P2 | 将一个 full-population fixture receipt 的 `eligibility` 改成 `{}` 并重算 envelope hash，旧完整 verifier 仍给 `VERIFIED_SCOPED`。 | `all(...)` 子集比较不能证明完整字段。新验收按 family、status 和 reason 要求完整字段集，再逐值核对 E31；不要求失败分支原本不输出的 token 字段。 |
| P2 | 原 required set 未包含 `NPU_SPEC.json`、finisher 的 `run.sh`／`LAUNCH_EXACT.sh`。原 fixture 完全缺这些文件也通过。 | 新验收要求运行规格、全部实际 Python 执行文件、finisher wrapper／启动文件属于冻结闭包，并核实际容器环境、命令、挂载、设备、网络及退出。 |
| P2 | 原 verifier 仅标总体 classification accuracy 为 0／1。原全量 fixture 中 choice 为 9,582／9,582、noul 为 0／1,356、概率向量相同，仍无 flags。 | 新验收同时检查题型和 source×题型 cell 的边界率、相同指标／概率、score MAE 为零及小样本；保留指针，不用汇总分数稀释异常。 |

既有 14＋9＋4＝27 项 E33 测试在这些缺口存在时全部通过。以上负例证明的是验收器
覆盖不足，**不是实际模型预测已错误**。实际 preparer 已加入资源和 finisher 文件，
此前工程 probe 验收也包含额外核对；不能由上述漏洞直接断言当前产物失效。
未发现已声明完整分母和计分公式的直接算术错误。

## 2. E35 补充验收协议（运行前登记）

对应 defect 12／16：测量与任务身份。无约束最优解是只信某个成功标记、忽略缺字段
或重写假 receipt；反例是在保持原总分、部分哈希或容器名称的情况下删除／伪造关键
字段，补充验收必须拒绝。可疑成功 flags 是诊断，不是训练选择阈值，不改变主指标。

输入仍为 E33 原 JEVal 全 11,257 行，数据 SHA256
`88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82`。
分类总体为 10,938，score 总体为 319；不修改 eligible、unsupported、overlength、
温度、上下文限制、返回值与计分公式。每个模型单独启动 CPU 补充验收，不混用 import
后的原生模块。工具是 `tools/audit_jeval_inference_hardened.py`，须在独立输出目录
冻结其代码、wrapper 和准确启动命令；不得覆盖 E33 的原报告或旧审计。

### 完整推理模式

1. 先认证完整运行闭包、原生依赖及 E31 身份，再导入冻结原 verifier 并执行其完整
   11,257 receipt 验收与原指标重算。不会将补充工具冒充原计分实现。
2. 要求 receipt 的资格字段完整且与 E31 逐值相同，保留原失败分支字段。
3. 要求四组、八次 probe 输出 schema、native 概率质量、logits 算术、温度标记、
   原生 wire／score／confidence 均相符。四个请求用同一冻结 tokenizer/native
   encoder 独立 CPU 重分词，最长边界从完整 eligible 集重新选择。
4. 检查 probe／正式执行源码集合、依赖、运行配置的绑定。核对实际 retained
   inference、probe、finisher 容器身份、退出码、资源规格、wrapper 和终态哈希。
5. 检查期间前后核对 receipt 全集合与内容哈希，避免审查中被替换。输出原报告及
   原审计哈希，不把“未发现错误”写成跨硬件完全等价。

### Probe-only 模式

`--probe-only` 允许在全量推理尚未完成时独立核查上述四组 probe 的完整冻结闭包、
原生 metadata、CPU 重分词、实际容器退出和终态，不需要正式推理或 finisher 终态。
其成功状态 `VERIFIED_HARDENED_PROBE_SCOPED` **不提供全量 test 成绩，也不认证
全量候选批量的内存包络**。probe 目录不得有正式 test receipts。

### 可疑结果诊断

按题型及 source×题型分组。分类 accuracy 分母保留该 cell 全部题目，另外显示有效
回答上的 accuracy；score MAE 仍以 valid score 为分母，显示全体与有效数。
每个 cell 的总数或有效数小于 **30** 时标记；30 沿用 `tools/watchdog.py --min-n`
默认值，在读取 E35 输出前固定。标记任何 accuracy／valid accuracy 精确等于 0／1、
score MAE 精确为 0、至少两项有效结果的概率向量完全相同，以及同一题型跨 source
cell 的同名指标全部相同。概率向量比较保留维度和顺序；该诊断不能证明污染。

所有 flags 保留于 JSON，含 `/cells/...` 指针和首个 receipt 路径；摘要最多显示
12 项，每项至多 500 字符。原 verifier flags 另列继承，不静默清空。flags 触发
诊断与限定范围汇报，不自动改变模型结果或批准后续训练。

## 3. 命令与输出契约

在 175 的现有 immutable image 中运行，CPU 模式，无 NPU 设备。必须挂载 CephFS
及只用于 inspect 的 Docker socket；环境设置 `TORCH_DEVICE_BACKEND_AUTOLOAD=0`。
执行使用 `python3 -P`，长任务 detached、固定容器名、保留容器与日志／heartbeat／
终态、记录准确 relaunch；这些由外层 wrapper／E34 controller 负责。

```bash
python3 -P /frozen/audit_jeval_inference_hardened.py \
  --config /ceph/run/config.json --out /ceph/separate-audit/HARDENED_AUDIT.json
python3 -P /frozen/audit_jeval_inference_hardened.py \
  --config /ceph/probe/config.json --probe-only --out /ceph/separate-audit/HARDENED_PROBE.json
```

原路径必须替换为实际冻结绝对路径。已有输出拒绝覆盖。完整模式成功状态为
`VERIFIED_HARDENED_SCOPED` 或 `VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED`；
JSON 包含 config/report hash、原 verifier 结果、补充闭包计数、probe、实际容器、
cells、完整 flags 和 inherited flags。对应 `.digest.md` 是有界摘要。
异常以非零退出报告；外层 wrapper 写失败终态，不能把无 JSON 解释为成功。

## 4. 实现验证与限制

16 项 focused CPU 测试通过，覆盖三 family 正确原生输出、wrong-schema／零质量
伪造、缺 answer、错误 logits／tokens／score／legend／confidence、资格空字典／
缺字段、真实失败分支、闭包遗漏、实际 Docker 身份／环境／资源／退出改变，以及
被总体分母掩盖的分组异常。它们不是模型测试，也不替代即将执行的真实 probe
产物验收。本文件初版未启动 E35 长任务，真实结果待独立报告。

完整 test 的 token 仍是来源哈希绑定；只有四个 probe 请求新增独立重分词。
本补充验收没有新训练收益结论，没有 Astra 放行，也没有解决 Open-Jev 候选批量
资源准入。真实产物可能仍触发新问题，需保留失败证据再修正补充工具的独立版本。


## 5. 19:31 UTC 真实 probe 产物验收追加

E35 独立 CPU 审计已完成六个 accepted probe（Kev-4B／9B 使用 v2），全为
`VERIFIED_HARDENED_PROBE_SCOPED`，终态 rc=0、6/6，实际 retained 容器退出 0。
每模型四个请求独立 CPU 重分词、八次输出重建、完整闭包与实际容器核对通过。
运行目录、配置／报告哈希见 [E35](../wiki/E35-jeval-hardened-artifact-audit-20261030.md)。
这解决了当前真实 probe 产物的新增验收问题；正式推理全量补充验收仍待其完成，
Open-Jev 最大候选批量显存准入仍是独立工程事项，Astra 实质审查仍未获得。
