# Kev checkpoint 发布温度与来源补充审计

2026-10-30，预注册见 [E27](../wiki/E27-kev-checkpoint-binding-audit-20261030.md)。
现有独立计分器从 ENVIRONMENT 读取温度，再校验逐项与汇总的一致性；本次补充直接读取
冻结 `head.pt` 的温度、base/revision，并绑定 adapter、base marker、原生 driver 调用、
发布 README 的权重哈希与 release 标识。该补充不改动既有运行与指标。

范围：Kev 三尺寸的 main／extended／devtools 九次已完成运行。发布 README 只给前缀时
明确标为前缀证据，不冒充上游完整权重 SHA。旧运行没有的 launch receipt 不事后补造。
静态 driver AST 证明冻结代码请求 FP32/eager/merged 且无温度覆盖，不能单独证明历史硬件执行。

当前九次补充审计已完成；工具 [audit_kev_checkpoint_binding.py](../tools/audit_kev_checkpoint_binding.py)
和七项正反例测试已准备。独立计分和实质 Astra 审查仍分别保留自己的验收状态。

## 实际结果（17:00 UTC）

三个尺寸各三次运行全部通过 checkpoint／base／温度／冻结 driver／保存的结果绑定。
温度分别为 2.3510958125672174、2.406050072164233、2.193649959389252，与各次
ENVIRONMENT 和 suite report 完全相同；README 的 release 分别为 kev-08b-r15、
kev-4b-r10、kev-9b-r27。原生 driver 以 FP32/eager/merged、无温度覆盖调用 loader。

第一次审计因 README 不在原冻结清单而失败并保留；README 属于发布来源、非 loader
依赖。第二次执行前新增独立 publication manifest，将 README 明确标为事后补充来源，
不追溯修改原运行。原 head／adapter／base 仍必须通过原始冻结哈希。E7 缺少原始 launch
receipt，报告保留这一限制；其余八个已保存 receipt 的配置／镜像／wrapper 绑定通过。

输出：`/mnt/cephfs/xingchao/experiments/jev/reference_inference/kev_checkpoint_binding_audit_20261030_v2/report.json`。
SHA256：`9f5f7da56a2d3ad8753877815d60c704e1d3bc0c48878e9a0c74394d2670948e`。
结构化终态、wrapper 和固定 retained CPU 容器均为 0，18 个冻结输入复核通过。

这支持本次报告的“checkpoint 发布温度”归属；不能据此证明历史 logits 没有被伪造，
也不替代已有的独立计分、逐题差异说明或尚未完成的 Astra 实质审查。
