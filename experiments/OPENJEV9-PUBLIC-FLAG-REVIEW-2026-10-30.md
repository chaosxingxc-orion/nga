# Open-Jev-9B 公共 test：八项审查标记的定向核查

2026-10-30 18:34 UTC。核查对象为独立审计标出的五个 source、八个指标标记，共 4,495 条逐项记录；原始总体为 10,356 行。本诊断保留所有审查标记，不将完美分数解释为可靠部署或泛化证明。

## 可复算结果

| source | 总数 | hard 正确／hard 分母 | expected accuracy | group 数 | 不同原生 prompt 组数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| customer-control-v1 | 606 | 574／574 | 97.222222% | 101 | 606 |
| painting-geometry-v1 | 3,072 | 3,072／3,072 | 100% | 6 | 3,072 |
| trex_runner-v1 | 4 | 3／4 | 75% | 4 | 4 |
| workflow-controls-v1/agent_trace_observability | 357 | 357／357 | 100% | 17 | 357 |
| workflow-controls-v1/customer_service | 456 | 456／456 | 100% | 19 | 368 |

各 cohort 均按数据原有 `metadata.provenance.type` 标为 synthetic；这只是数据来源标记，并非已经验证其生成器、训练数据重叠或污染原因。group 数直接来自原始 `group_id`，不能把它解释为独立样本数。

customer-control 的 32 条 soft target 解释了 hard accuracy 为 1 而 expected accuracy 低于 1。painting 与两个 workflow cohort 的逐项正确数确实复现完美 aggregate，不能据此跳过审查。workflow customer_service 的 456 条只有 368 组不同原生 prompt，应保留这一重复性限制；painting 仅六个 group，也不能把 3,072 条当成同等数量独立场景。trex 只有四题，9B 的预测为 jump_short×2、jump_full×1、keep_running×1，gold 为 jump_short×2、jump_full×1、duck×1；一题错误不改变极小样本限制。

## 检查范围

工具 [review_openjev9_public_flags.py](../tools/review_openjev9_public_flags.py) 只读取标记涉及的五个 source 的 receipts，校验原始输入／配置／逐项身份及 receipt 校验和，从 logits 和冻结温度独立重算概率和 argmax，重新统计 hard numerator、hard denominator 与 expected correctness，并逐项对照已有独立审计。它不重新运行模型。

原生 `jev/api.py` 的 `_render` 与 `candidate_prompts` 经 AST 提取后，在无模型导入条件下执行。对全部 4,495 条：改变 target、id、source、group_id 和 metadata 不改变 prompt；改变实际 state 则改变 prompt。后一项是输入敏感性对照，避免只验证不变性。该结果仅证明这些渲染函数没有通过上述字段把 gold 放入 prompt，不证明 state 内不存在答案线索，更不证明没有训练集重叠。

## 实际运行和证据

175 上使用既有不可变镜像的 CPU 容器 `nga-openjev9-public-flag-review`，ID `02acd377e7e32e31788488a3103382533bfd5fe0b446d33551f97cdcb5d33e1e`，18:34:26 UTC 终态 rc=0、实际保留容器 exited/0。

目录：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev9_public_flag_review_20261030/`。其中 `SETUP.json` 在启动前记录诊断目的、假设和脚本哈希，`LAUNCH_EXACT.sh`、`REPRODUCE.sh` 保存确切命令，`report.json` 包含所有 4,495 条 cohort 记录、来源哈希与原八项 flags。未修改原推理目录，未占 NPU。

诊断 report SHA256：`f622733c3d0c3169e326a3df605e50ce27653e3cbfa5c3d93f965f3ce648038a`。

上游推理 report SHA256：`f8629708b4a8939d8cc6f62989a802658944085c2321e2b1c4b32cfd8c6382c5`；独立 audit SHA256：`28659624076fcfcb7387c1c3a532a808bdc6ce9a654d822355d17ff90adb7e1b`。本诊断不代替完整总体的独立审计、Astra 实质评审或原始完整 10,532 行合并验收。

18:38 UTC 父会话复核：使用同一冻结脚本与独立保留的 CPU 容器重新运行，输出 `parent-reproduced.json`。除生成时间外，全部结构化诊断逐字段相同；原诊断及原 flags 保留。
