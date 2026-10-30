# E13 — Open-Jev-2B native Ascend synthetic compatibility probe

Preregistered 2026-10-30 before launch. Development instrumentation, no test scores.

## Purpose and hypothesis

Verify released Open-Jev-2B independent-candidate scalar-head inference on 175's existing
Ascend image. Defect registry row 12: measurement validity. A constant finite vector could
satisfy structural checks, so this probe claims execution only, not semantic generalization.
Use three fixed synthetic choice/noul/score requests, repeat each twice and preserve logits,
probabilities and prompt mapping. No post-hoc equivalence threshold or quality claim.

## Frozen setup

Checkpoint `ZefanCai__Open-Jev-2B/package/checkpoint`, base Qwen/Qwen3.5-2B revision
`15852e8c16360a2fea060d615a32b45270f8a8fc`. This is the instruct base, not Kev's Base model.
Native DecisionModel.load, unmerged native adapter, original scalar head/candidate prompts,
bf16 backbone, float32 head, native SDPA, checkpoint temperature. No quantization, prefix
cache or truncation. A subclass resolves only the pinned Hub base ID to its local mirror;
model semantics and tokenizer are unchanged. Explicit torch_npu registration, device npu:0
and synchronization adapt device placement/timing; HF32 is off. Hash source, complete local
model files and fixture/driver before inference. No official test or NGA locked partition read.

## Execution and acceptance

Use chip 2 only after allocation and live Docker device checks. Fixed retained detached
container `nga-reference-openjev2-probe`, run directory
`/mnt/cephfs/xingchao/experiments/jev/reference_inference/openjev2_probe_20261030/`.
CephFS holds frozen code, preregistration, exact launch/relaunch, log, 15-second heartbeat,
atomic record receipts, terminal and wrapper DONE/FAILED. Validate complete finite logits,
simplex and native format_response. Record load time, each repeated-pass latency,
questions/s/chip (one chip) and reserved memory. Repeat deltas diagnostic only.
Saved records are resumed only with identical input/config/content hashes. No full benchmark
admission follows from three synthetic requests. Any load/operator failure is preserved.

## Results

**Completed 2026-10-30 15:15:14 UTC.** Container
`01697cb260e1c5030b05175d1bc0dead33653518be62e416a1adb7bc3de226f0`
(`nga-reference-openjev2-probe`) exited 0; PROBE_COMPLETE and wrapper DONE agree.
All three synthetic typed requests executed twice. Native temperature was
1.518796342858676; load time 4.5193 seconds. Repeated-pass rates were
3.6588, 3.6554 and 3.6755 questions/s/chip, one chip; reserved memory 4.1465 GiB.
Repeated probability differences were 0 for these requests, a diagnostic only.
All 82 frozen files were checked before and after inference; record receipt hashes
were separately rechecked. Source stamp:
`25fe04f9489eed86df0e9442350937fed9dce2d5fe043c6ab1f0835c0974063c`.
Chip 2 was released after terminal and Docker exit verification.

## Verdict

Native Open-Jev-2B scalar-head inference executes in the existing Ascend image with the
released bf16 backbone, original SDPA path and exact local instruct base revision.
No attention override, label-logprob replacement or model-weight modification was needed.
This three-request synthetic probe is not test performance, a broad throughput benchmark,
cross-hardware equivalence or Astra acceptance. Full public-projection inference, original
test reconstruction and independent aggregate verification remain separate tasks.
