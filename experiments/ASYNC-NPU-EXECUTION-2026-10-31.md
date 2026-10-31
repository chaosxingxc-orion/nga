# Asynchronous NPU execution controller

Status: implementation candidate; not launched and not an approval. This controller records the user's two engineering constraints: keep approved NPU jobs in per-chip FIFO queues, while CPU analysis and baseline publication run in a separate ordered lane.

The controller advances every eligible NPU lane before making one CPU-lane step. A completed NPU job is released only by an exact, separately reviewed operational-release adapter that proves retained container exit, receipt/terminal generation, allocation transition and preserved evidence. Scientific acceptance and Astra result analysis are recorded later by the CPU lane and cannot block an unrelated next NPU job. A failed or uncertain generation is quarantined; it is never retried implicitly.

`tools/async_experiment_queue.py` is standard-library orchestration only. It validates immutable queue and plan hashes, unique retained container names, per-chip FIFO order, exact approvals, no accelerator devices in the CPU lane, and immutable evidence manifests. It writes durable state, a heartbeat and a bounded digest. `--once` is provided for review fixtures; `prepare_detached()` writes a retained Docker specification but does not launch it. The controller must receive a new actual Astra review and a caller approval before deployment.

The 12 tests in `tools/test_async_experiment_queue.py` cover independent chip progress while analysis is pending, strict CPU ordering, duplicate/recovery handling, wrong generation, missing terminal, mutated evidence, target mismatch and failed action quarantine. Tests use synthetic Docker responses and do not establish live occupancy, release, NPU execution or scientific results.

The first queue entries should be E41 only after its corrected exact plans receive Astra PASS. The queue must not treat E41 v1 BLOCK plans as eligible. Current E40 results remain archived and do not authorize E41 execution.
