# RC1 functional training campaign

Owner instruction: prioritize runnable experiments and NPU occupancy; deferred engineering hardening is not an execution gate. This is a new execution campaign, not the previous 36-process numerical-equivalence protocol.

Fixed before launch: Qwen3.5 Base 0.8B/2B/4B/9B, seeds 2 and 3, existing k1-family-train-v2 recipes, decision-v7 TRAIN 15576 rows, original project model/data manifests, fixed image sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d. One chip per run. LoRA r16/alpha32/dropout0.05, production schedule3116, existing optimizer/kernel/token budgets unchanged. Two-step functional smoke, then exact checkpoint resume to3116 on the same chip. Eight lanes and sixteen DAG nodes.

Purpose: verify runnable fixed-image training and produce reproducible adapters for the existing same-TEST comparisons. Hypothesis: existing recipe executes and yields nondegenerate trained artifacts; no accuracy gain or numerical equivalence asserted before evaluation. Defect12 measurement prerequisite; existing task discrimination counterparts remain normative. No new TEST access, thresholds or selection. All two seeds retained; failures retained. Later evaluation uses existing frozen same-TEST protocols with independent result review before publication.

Config inputs and executable queue: .local/releases/engineering-base-rc1/execution/functional; remote /mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106. Docker retained detached, logs and actual exit markers, checkpoints per existing trainer, monitor600s. Model/data checked by existing trainer at load; no admin-resistant custody claim. No claim of formal release.
