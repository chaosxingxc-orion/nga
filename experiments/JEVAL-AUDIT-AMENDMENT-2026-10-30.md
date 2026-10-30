# E35 验收修订：逐题产物认证与 valid accuracy 异常标记

2026-10-30。依据：[Astra 实质代码审查](ASTRA-JEVAL-REVIEW-2026-10-30.md) finding 2／5。
本修订只影响新的外部验收工具；不修改已冻结模型运行、原生 scorer、旧审计结果或数据划分。
原 E35 六组 probe 审计的历史结论保留，不能把本修订追溯写成它们已执行的检查。

## 1. 缺陷与修复范围

原补充 auditor 在审计期间比较逐题 receipt 的前后哈希，但未把完整认证清单写入结果。
因此其下游只核对 report／terminal 时，不能发现审计结束后的逐题文件删除或修改。
新增完整有序 `receipt_manifest`，供队列在接受、恢复复核和资源释放前重新验证。
这修复的是证据链缺口；不是已经发现真实推理 receipt 被篡改。

原分类 cell 同时产生 `accuracy` 与 `valid_accuracy`，跨来源相同指标检查却只覆盖前者。
现在两项分别检查：同类型 source 的 `accuracy`、`valid_accuracy` 独立比较，score 保留
`mae` 检查。它们仍只是触发审查的标记，不改变主指标、有效分母或先前阈值。

## 2. 完整 receipt_manifest 契约

仅完整推理审计报告新增如下字段；probe-only 不声称产生完整测试 receipt 清单。

```json
{
  "receipt_manifest": {
    "schema": 1,
    "algorithm": "sha256",
    "count": 11257,
    "entries": [
      {"path": "records/000000.json", "sha256": "<64 lowercase hex>"},
      {"path": "records/000001.json", "sha256": "<64 lowercase hex>"}
    ],
    "root_sha256": "<64 lowercase hex>"
  }
}
```

上例缩写了 entries；真实报告必须包含恰好 11,257 项，按 `000000.json` 至
`011256.json` 排序。`records/` 目录及其每项必须是普通实际目录／文件，不能是符号链接。
任何额外文件（包括非 JSON）、目录、缺失、错序、错误路径或内容哈希变化都被拒绝。

`root_sha256` 的输入是除该字段外的完整对象，以 Python
`json.dumps(body, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))`
编码为 UTF-8 后计算 SHA256。每项 `sha256` 认证原文件字节，包含 JSON 格式本身；
文件内容相同但修改时间变化不改变认证。

公开辅助接口：

```python
receipt_manifest(run, expected_count=11257)
verify_receipt_manifest(run, manifest, expected_count=11257)
```

`run` 是模型输出目录，不是 `records/` 自身。后者重新读取整个真实集合并核对 schema、
数量、文件名／顺序、逐项内容和根哈希。完整验收在计分前取得清单，结束时重新核对，
然后将原清单写入结果。probe-only 对实际空 `records/` 目录做前后检查，但不附完整测试
manifest。消费者必须在接受、恢复和释放前对磁盘重核，不能只相信一个存储的根哈希。
队列／waiter 的相应消费者修复由独立任务完成，本文件不宣称尚未部署的消费者已经生效。

## 3. 产物发布与故障保留

新的 CLI 先把报告写入同目录唯一 `*.pending-*` 文件，flush 和 fsync 后，用同文件系统
原子 hard-link 发布到最终名称，再删除临时名称并 fsync 目录。这既避免半写入 JSON
被当作正式结果，又保证已有目标文件不会被覆盖（包括检查之后出现的竞争写入）。
写入／发布失败留下 pending 证据供诊断；已有最终输出仍拒绝覆盖。有限摘要也使用相同
方式。完整报告已发布而摘要尚未发布的中断仍可能存在，应由外围 attempt／terminal
恢复协议判断，不能直接把“文件存在”当作完成。

## 4. 验证与边界

2026-10-30 UTC 验证：`python3 -I tools/test_jeval_inference_hardened.py`
通过全部 25 项测试（3.514 秒）；`git diff --check` 通过。

新增反例覆盖：完整 11,257 文件清单及独立根哈希重算；审计后删除／修改 receipt；
额外 receipt／目录；相同字节的 symlink 替换；清单 count／order／path／hash／root
篡改；发布中断不产生半写入最终文件、保留 pending、拒绝覆盖已有结果。
跨来源反例使用总数 100／200、有效数均 50、正确数均 25：总体 accuracy 为
0.25／0.125，valid accuracy 同为 0.5，必须保留两个对应 cell 指针。

原主指标公式、分母、native／wire 差异、先前 flags 和 30 样本标记阈值均未修改。
修复不能证明 Open-Jev 全候选批量显存准入，也不构成 Astra 对修复版本的复审放行。
本修订尚未运行任何新模型推理或在活跃目录中替换冻结文件。
