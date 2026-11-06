# Matched current-runtime K0 DEV queue

Exact reviewed deployment packet for `engineering-base-rc1`. Frozen scope: [RC1-MATCHED-K0](../../../experiments/RC1-MATCHED-K0.md). Four Base models, three clean calibration/DEV groups each, 12,272 question conditions total. The full model paths, frozen evaluator closure, data pins and fixed image are configuration inputs in `config.json`.

The dispatcher runs on175 using Python3.12 `-B -P`. It schedules chips4–7 only after each configured predecessor completes training3116 and full DEV inference; it does not wait for CPU scoring. 27B uses0–3 under its separate plan. Each inference exits before its CPU scoring phase; at most two CPU phases, four cores each. Resource/dependency polling is600seconds. Containers, logs, heartbeats, terminal receipts and exact commands persist onCeph.

The deployed packet is `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106/matched-k0-source`; output is sibling `matched-k0-clean-dev`. `DISPATCH-LAUNCH.json`, `QUEUE-LAUNCH.json` and `RELAUNCH.json` record the actual detached process and command. `QUEUE-EXIT.json` is terminal authority. A missing marker is not success. Do not start a second queue or discard existing receipts to retry.

Independent review passed17 supplied and6 added CPU fixture tests, including actual frozen evaluator compatibility, safe-path host imports, deployed DEV receipt compatibility, busy/unknown ownership refusal and missing/changed artifacts. The exact review and approval pins are in the remote output directory. This permits conditional waiting dispatch, not a claim of numerical model results or TEST admission. The dispatcher verifies source/review hashes and actual dependencies before launches.

Run supplied tests separately with `python3 -B -P test_producer.py`, `test_queue.py`, `test_review.py`, `test_fixed.py` in this directory; they need the existing frozen Ceph evaluator closure. They use generated fixtures, not real TEST. Keep source filenames unchanged (`queue.py` must be loaded through the provided safe-path entrypoint).

Historical runtime8190 comparisons remain labelled separately. Current K0 reports need actual producer completion and independent numerical comparison with the new adapters before reporting training gains. No K0 variants/drop/blank were inferred by this three-group workload.
